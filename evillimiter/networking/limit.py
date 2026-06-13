import re
import time
import threading

from evillimiter.console import shell

from evillimiter.common.globals import BIN_TC, BIN_NFTABLES


class Limiter(object):
    class HostLimitIDs(object):
        def __init__(self, upload_id, download_id):
            self.upload_id = upload_id
            self.download_id = download_id

    class HostState(object):
        def __init__(self, ids):
            self.ids = ids
            self.upload_mode = None
            self.upload_rate = None
            self.download_mode = None
            self.download_rate = None

    _RULE_HANDLE_PATTERN = re.compile(r"# handle (\d+)")

    def __init__(self, interface):
        self.interface = interface
        self._host_dict = {}
        self._host_dict_lock = threading.RLock()
        self._nft_tables_ready = False
        self._root_qdisc_ready = False
        self._ensure_nft_tables()
        self._ensure_root_qdisc()

    def limit(self, host, direction, rate):
        if direction == Direction.NONE:
            return False

        with self._host_dict_lock:
            if not self._nft_tables_ready:
                self._ensure_nft_tables()
            if not self._root_qdisc_ready:
                self._ensure_root_qdisc()

            host_key = self._host_key(host)
            directions = self._iter_directions(direction)
            host_state = self._get_or_create_host_state_locked(host_key)
            snapshots = {d: self._get_direction_snapshot(host_state, d) for d in directions}

            success = True
            for item_direction in directions:
                success = self._clear_direction_locked(host, host_key, host_state, item_direction) and success

            if success:
                for item_direction in directions:
                    if not self._apply_limit_direction_locked(host, host_key, host_state, item_direction, rate):
                        success = False
                        break

            if not success:
                for item_direction in directions:
                    self._clear_direction_locked(host, host_key, host_state, item_direction)

                for item_direction in directions:
                    self._restore_direction_locked(host, host_key, host_state, item_direction, snapshots[item_direction])

            self._finalize_host_state_locked(host, host_key, host_state)
            return success

    def block(self, host, direction):
        if direction == Direction.NONE:
            return False

        with self._host_dict_lock:
            if not self._nft_tables_ready:
                self._ensure_nft_tables()

            host_key = self._host_key(host)
            directions = self._iter_directions(direction)
            host_state = self._get_or_create_host_state_locked(host_key)
            snapshots = {d: self._get_direction_snapshot(host_state, d) for d in directions}

            success = True
            for item_direction in directions:
                success = self._clear_direction_locked(host, host_key, host_state, item_direction) and success

            if success:
                for item_direction in directions:
                    if not self._apply_block_direction_locked(host, host_key, host_state, item_direction):
                        success = False
                        break

            if not success:
                for item_direction in directions:
                    self._clear_direction_locked(host, host_key, host_state, item_direction)

                for item_direction in directions:
                    self._restore_direction_locked(host, host_key, host_state, item_direction, snapshots[item_direction])

            self._finalize_host_state_locked(host, host_key, host_state)
            return success

    def unlimit(self, host, direction):
        if direction == Direction.NONE:
            direction = Direction.BOTH

        with self._host_dict_lock:
            host_key = self._host_key(host)
            host_state = self._host_dict.get(host_key)

            if host_state is None:
                host.limited = False
                host.blocked = False
                return True

            success = True
            for item_direction in self._iter_directions(direction):
                success = self._clear_direction_locked(host, host_key, host_state, item_direction) and success

            self._finalize_host_state_locked(host, host_key, host_state)
            return success

    def replace(self, old_host, new_host):
        with self._host_dict_lock:
            host_state = self._host_dict.get(self._host_key(old_host))
            if host_state is None:
                return False

            snapshots = {
                Direction.OUTGOING: self._get_direction_snapshot(host_state, Direction.OUTGOING),
                Direction.INCOMING: self._get_direction_snapshot(host_state, Direction.INCOMING),
            }

        success = self.unlimit(old_host, Direction.BOTH)

        outgoing = snapshots[Direction.OUTGOING]
        incoming = snapshots[Direction.INCOMING]

        if outgoing["mode"] == "limit":
            success = self.limit(new_host, Direction.OUTGOING, outgoing["rate"]) and success
        elif outgoing["mode"] == "block":
            success = self.block(new_host, Direction.OUTGOING) and success

        if incoming["mode"] == "limit":
            success = self.limit(new_host, Direction.INCOMING, incoming["rate"]) and success
        elif incoming["mode"] == "block":
            success = self.block(new_host, Direction.INCOMING) and success

        return success

    def _run_command(self, command, attempts=2, delay=0.15):
        for attempt in range(attempts):
            if shell.execute_suppressed(command) == 0:
                return True
            if attempt < attempts - 1:
                time.sleep(delay * (attempt + 1))
        return False

    def _output_command(self, command):
        try:
            return shell.output_suppressed(command)
        except Exception:
            return ""

    def _ensure_root_qdisc(self):
        qdisc_output = self._output_command("{} qdisc show dev {}".format(BIN_TC, self.interface))
        if "htb 1:" not in qdisc_output:
            self._run_command("{} qdisc add dev {} root handle 1: htb default 30".format(BIN_TC, self.interface))

        class_output = self._output_command("{} class show dev {}".format(BIN_TC, self.interface))
        if not re.search(r"\b1:30\b", class_output):
            self._run_command("{} class add dev {} parent 1: classid 1:30 htb rate 1000mbit".format(BIN_TC, self.interface))

        self._root_qdisc_ready = True

    def _ensure_nft_tables(self):
        table_output = self._output_command("{} list table inet limiter".format(BIN_NFTABLES))
        if not table_output:
            self._run_command("{} 'add table inet limiter'".format(BIN_NFTABLES))

        prerouting_output = self._output_command("{} list chain inet limiter prerouting".format(BIN_NFTABLES))
        if not prerouting_output:
            self._run_command("{} 'add chain inet limiter prerouting {{ type filter hook prerouting priority mangle; }}'".format(BIN_NFTABLES))

        postrouting_output = self._output_command("{} list chain inet limiter postrouting".format(BIN_NFTABLES))
        if not postrouting_output:
            self._run_command("{} 'add chain inet limiter postrouting {{ type filter hook postrouting priority mangle; }}'".format(BIN_NFTABLES))

        forward_output = self._output_command("{} list chain inet limiter forward".format(BIN_NFTABLES))
        if not forward_output:
            self._run_command("{} 'add chain inet limiter forward {{ type filter hook forward priority filter; }}'".format(BIN_NFTABLES))

        self._nft_tables_ready = True

    def _host_key(self, host):
        mac = getattr(host, "mac", None)
        if isinstance(mac, str) and mac:
            return mac.lower()
        return host.ip

    def _iter_directions(self, direction):
        directions = []
        if (direction & Direction.OUTGOING) == Direction.OUTGOING:
            directions.append(Direction.OUTGOING)
        if (direction & Direction.INCOMING) == Direction.INCOMING:
            directions.append(Direction.INCOMING)
        return directions

    def _direction_label(self, direction):
        return "upload" if direction == Direction.OUTGOING else "download"

    def _comment_key(self, host_key):
        return re.sub(r"[^a-z0-9]+", "_", host_key.lower()).strip("_")

    def _rule_comment(self, host_key, direction, suffix):
        return "evillimiter_{}_{}_{}".format(self._comment_key(host_key), self._direction_label(direction), suffix)

    def _get_or_create_host_state_locked(self, host_key):
        host_state = self._host_dict.get(host_key)
        if host_state is None:
            host_state = Limiter.HostState(Limiter.HostLimitIDs(*self._create_ids_locked()))
            self._host_dict[host_key] = host_state
        return host_state

    def _create_ids_locked(self):
        used_ids = {30}
        for host_state in self._host_dict.values():
            used_ids.add(host_state.ids.upload_id)
            used_ids.add(host_state.ids.download_id)

        id_ = 1
        ids = []
        while len(ids) < 2:
            if id_ not in used_ids:
                ids.append(id_)
            id_ += 1
        return tuple(ids)

    def _get_direction_id(self, host_state, direction):
        if direction == Direction.OUTGOING:
            return host_state.ids.upload_id
        return host_state.ids.download_id

    def _get_direction_snapshot(self, host_state, direction):
        if direction == Direction.OUTGOING:
            return {"mode": host_state.upload_mode, "rate": host_state.upload_rate}
        return {"mode": host_state.download_mode, "rate": host_state.download_rate}

    def _set_direction_state(self, host_state, direction, mode, rate=None):
        if direction == Direction.OUTGOING:
            host_state.upload_mode = mode
            host_state.upload_rate = rate
        else:
            host_state.download_mode = mode
            host_state.download_rate = rate

    def _has_active_rules(self, host_state):
        return any([
            host_state.upload_mode is not None,
            host_state.download_mode is not None,
        ])

    def _finalize_host_state_locked(self, host, host_key, host_state):
        if not self._has_active_rules(host_state):
            self._host_dict.pop(host_key, None)
            host.limited = False
            host.blocked = False
            return

        host.limited = any([
            host_state.upload_mode == "limit",
            host_state.download_mode == "limit",
        ])
        host.blocked = any([
            host_state.upload_mode == "block",
            host_state.download_mode == "block",
        ])

    def _get_limit_rule_parts(self, host, direction):
        if direction == Direction.OUTGOING:
            return "postrouting", "ip saddr {}".format(host.ip)
        return "prerouting", "ip daddr {}".format(host.ip)

    def _get_block_rule_parts(self, host, direction):
        if direction == Direction.OUTGOING:
            return "forward", "ip saddr {}".format(host.ip)
        return "forward", "ip daddr {}".format(host.ip)

    def _find_rule_handles(self, chain, comment):
        chain_dump = self._output_command("{} -a list chain inet limiter {}".format(BIN_NFTABLES, chain))
        comment_marker = 'comment "{}"'.format(comment)
        handles = []

        for line in chain_dump.splitlines():
            if comment_marker not in line:
                continue

            match = self._RULE_HANDLE_PATTERN.search(line)
            if match:
                handles.append(match.group(1))

        return handles

    def _delete_nft_rule_by_comment(self, chain, comment):
        success = True
        handles = self._find_rule_handles(chain, comment)

        for handle in reversed(handles):
            success = self._run_command("{} delete rule inet limiter {} handle {}".format(BIN_NFTABLES, chain, handle)) and success

        return not self._find_rule_handles(chain, comment) and success

    def _delete_legacy_nftables_entries(self, host, direction, id_):
        if direction == Direction.OUTGOING:
            self._run_command("{} delete rule inet limiter postrouting ip saddr {} meta mark set {}".format(BIN_NFTABLES, host.ip, id_), attempts=1)
            self._run_command("{} delete rule inet limiter forward ip saddr {} drop".format(BIN_NFTABLES, host.ip), attempts=1)
            return

        self._run_command("{} delete rule inet limiter prerouting ip daddr {} meta mark set {}".format(BIN_NFTABLES, host.ip, id_), attempts=1)
        self._run_command("{} delete rule inet limiter forward ip daddr {} drop".format(BIN_NFTABLES, host.ip), attempts=1)

    def _delete_tc_class(self, id_):
        self._run_command("{} filter del dev {} parent 1: protocol ip prio {} handle {} fw".format(BIN_TC, self.interface, id_, id_), attempts=1)
        self._run_command("{} filter del dev {} parent 1: prio {}".format(BIN_TC, self.interface, id_), attempts=1)
        self._run_command("{} class del dev {} parent 1: classid 1:{}".format(BIN_TC, self.interface, id_), attempts=1)

        class_output = self._output_command("{} class show dev {}".format(BIN_TC, self.interface))
        return re.search(r"\b1:{}\b".format(id_), class_output) is None

    def _clear_direction_locked(self, host, host_key, host_state, direction):
        id_ = self._get_direction_id(host_state, direction)
        limit_chain, _ = self._get_limit_rule_parts(host, direction)
        block_chain, _ = self._get_block_rule_parts(host, direction)

        success = True
        success = self._delete_nft_rule_by_comment(limit_chain, self._rule_comment(host_key, direction, "mark")) and success
        success = self._delete_nft_rule_by_comment(block_chain, self._rule_comment(host_key, direction, "block")) and success
        success = self._delete_tc_class(id_) and success

        self._delete_legacy_nftables_entries(host, direction, id_)
        self._set_direction_state(host_state, direction, None, None)
        return success

    def _apply_limit_direction_locked(self, host, host_key, host_state, direction, rate):
        id_ = self._get_direction_id(host_state, direction)
        chain, rule_match = self._get_limit_rule_parts(host, direction)
        comment = self._rule_comment(host_key, direction, "mark")

        if not self._run_command("{} class add dev {} parent 1: classid 1:{} htb rate {} burst {}".format(
            BIN_TC, self.interface, id_, rate, rate * 1.1
        )):
            return False

        if not self._run_command("{} filter add dev {} parent 1: protocol ip prio {} handle {} fw flowid 1:{}".format(
            BIN_TC, self.interface, id_, id_, id_
        )):
            self._delete_tc_class(id_)
            return False

        if not self._run_command('{} add rule inet limiter {} {} meta mark set {} comment "{}"'.format(
            BIN_NFTABLES, chain, rule_match, id_, comment
        )):
            if not self._run_command('{} add rule inet limiter {} {} meta mark set {}'.format(
                BIN_NFTABLES, chain, rule_match, id_
            )):
                self._delete_tc_class(id_)
                return False

        self._set_direction_state(host_state, direction, "limit", rate)
        return True

    def _apply_block_direction_locked(self, host, host_key, host_state, direction):
        chain, rule_match = self._get_block_rule_parts(host, direction)
        comment = self._rule_comment(host_key, direction, "block")

        if not self._run_command('{} add rule inet limiter {} {} drop comment "{}"'.format(
            BIN_NFTABLES, chain, rule_match, comment
        )):
            if not self._run_command('{} add rule inet limiter {} {} drop'.format(
                BIN_NFTABLES, chain, rule_match
            )):
                return False

        self._set_direction_state(host_state, direction, "block", None)
        return True

    def _restore_direction_locked(self, host, host_key, host_state, direction, snapshot):
        if snapshot["mode"] == "limit":
            return self._apply_limit_direction_locked(host, host_key, host_state, direction, snapshot["rate"])
        if snapshot["mode"] == "block":
            return self._apply_block_direction_locked(host, host_key, host_state, direction)
        self._set_direction_state(host_state, direction, None, None)
        return True


class Direction:
    NONE = 0
    OUTGOING = 1
    INCOMING = 2
    BOTH = 3

    def pretty_direction(direction):
        if direction == Direction.OUTGOING:
            return 'upload'
        elif direction == Direction.INCOMING:
            return 'download'
        elif direction == Direction.BOTH:
            return 'upload / download'
        else:
            return '-'
