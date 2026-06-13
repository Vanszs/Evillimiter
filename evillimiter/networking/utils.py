import glob
import re
import time
import socket
import shutil
import ipaddress
import subprocess
import netifaces
from scapy.all import ARP, Ether, srp # pylint: disable=no-name-in-module

# cara absolut (disarankan)
from evillimiter.console import shell

from evillimiter.common.globals import BIN_TC, BIN_NFTABLES, BIN_SYSCTL, IP_FORWARD_LOC

_OPTIONAL_BIN_CACHE = {}
_EMPTY_HOSTNAMES = {
    '', '*', '?', '(none)', '(null)', 'unknown',
    'localhost', 'localhost.localdomain'
}


def _has_optional_binary(name):
    present = _OPTIONAL_BIN_CACHE.get(name)
    if present is None:
        present = shutil.which(name) is not None
        _OPTIONAL_BIN_CACHE[name] = present
    return present


def normalize_host_name(name):
    if not isinstance(name, str):
        return None

    name = name.strip().strip('.')
    if not name:
        return None

    lowered = name.lower()
    if lowered in _EMPTY_HOSTNAMES:
        return None

    if lowered.endswith('.local'):
        name = name[:-6]

    if '.' in name and ' ' not in name:
        name = name.split('.', 1)[0]

    name = name.strip()
    return None if not name else name


def _read_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read()
    except (OSError, PermissionError):
        return ''


def _iter_dnsmasq_lease_paths():
    seen = set()
    patterns = [
        '/var/lib/misc/dnsmasq.leases',
        '/var/lib/NetworkManager/*.leases',
        '/var/lib/NetworkManager/*dnsmasq*.leases',
        '/var/lib/NetworkManager/*lease',
    ]

    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            yield path


def _resolve_hostname_from_leases(ip_address, mac_address=None):
    mac_address = None if mac_address is None else mac_address.lower()

    for lease_path in _iter_dnsmasq_lease_paths():
        content = _read_text_file(lease_path)
        if not content:
            continue

        for line in content.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue

            lease_mac = parts[1].lower()
            lease_ip = parts[2]
            lease_name = normalize_host_name(parts[3])
            if lease_name is None:
                continue

            if lease_ip == ip_address or (mac_address is not None and lease_mac == mac_address):
                return lease_name

    return None


def _resolve_hostname_from_reverse_dns(ip_address, timeout):
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        host_info = socket.gethostbyaddr(ip_address)
        if host_info is None:
            return None
        return normalize_host_name(host_info[0])
    except (socket.herror, socket.timeout, OSError):
        return None
    finally:
        socket.setdefaulttimeout(old_timeout)


def _resolve_hostname_from_getent(ip_address, timeout):
    if not _has_optional_binary('getent'):
        return None

    try:
        result = subprocess.run(
            ['getent', 'hosts', ip_address],
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        parts = line.split()
        for candidate in parts[1:]:
            hostname = normalize_host_name(candidate)
            if hostname:
                return hostname

    return None


def _resolve_hostname_from_avahi(ip_address, timeout):
    if not _has_optional_binary('avahi-resolve-address'):
        return None

    try:
        result = subprocess.run(
            ['avahi-resolve-address', ip_address],
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    parts = result.stdout.strip().split()
    if len(parts) < 2:
        return None

    return normalize_host_name(parts[-1])


def _resolve_hostname_from_nmblookup(ip_address, timeout):
    if not _has_optional_binary('nmblookup'):
        return None

    try:
        result = subprocess.run(
            ['nmblookup', '-A', ip_address],
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if '<00>' not in line or '<GROUP>' in line:
            continue
        candidate = normalize_host_name(line.split('<', 1)[0].strip())
        if candidate:
            return candidate

    return None


def resolve_host_name(interface, ip_address, mac_address=None, timeout=1.0):
    del interface  # reserved for future interface-aware resolvers

    resolvers = (
        lambda: _resolve_hostname_from_leases(ip_address, mac_address),
        lambda: _resolve_hostname_from_reverse_dns(ip_address, timeout),
        lambda: _resolve_hostname_from_getent(ip_address, timeout),
        lambda: _resolve_hostname_from_avahi(ip_address, timeout),
        lambda: _resolve_hostname_from_nmblookup(ip_address, timeout),
    )

    for resolver in resolvers:
        try:
            hostname = resolver()
        except Exception:
            hostname = None

        hostname = normalize_host_name(hostname)
        if hostname:
            return hostname

    return None


def get_neighbor_cache_entries(interface, candidate_ips=None):
    candidate_ips = None if candidate_ips is None else {str(ip) for ip in candidate_ips}

    try:
        result = subprocess.run(
            ['ip', 'neigh', 'show', 'dev', interface],
            capture_output=True,
            text=True
        )
    except (subprocess.SubprocessError, OSError):
        return []

    if result.returncode != 0:
        return []

    entries = []
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) < 5 or 'lladdr' not in parts:
            continue

        ip_address = parts[0]
        if candidate_ips is not None and ip_address not in candidate_ips:
            continue

        lladdr_index = parts.index('lladdr')
        if lladdr_index + 1 >= len(parts):
            continue

        mac_address = parts[lladdr_index + 1].lower()
        state = parts[-1].upper()
        if state in ('FAILED', 'INCOMPLETE', 'NONE'):
            continue
        if not validate_mac_address(mac_address) or mac_address == '00:00:00:00:00:00':
            continue

        entries.append((ip_address, mac_address))

    return entries



def _run_ip_command(args, timeout=3):
    """
    Runs an iproute2 command and returns stdout, or None on any failure.
    iproute2 is the authoritative source on Linux; netifaces is only a fallback.
    """
    if not _has_optional_binary('ip'):
        return None

    try:
        result = subprocess.run(
            ['ip'] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout


def _parse_default_route():
    """
    Parses `ip route show default` and returns (gateway_ip, interface),
    using either field as available. Returns (None, None) on failure.

    Example line:
        default via 192.168.0.1 dev wlan0 proto dhcp src 192.168.0.142 metric 600
    """
    output = _run_ip_command(['-4', 'route', 'show', 'default'])
    if not output:
        return None, None

    # Prefer the lowest-metric default route for determinism.
    best = (None, None)
    best_metric = None
    for line in output.splitlines():
        parts = line.split()
        if not parts or parts[0] != 'default':
            continue

        gateway_ip = None
        interface = None
        metric = None
        for idx, token in enumerate(parts):
            if token == 'via' and idx + 1 < len(parts):
                gateway_ip = parts[idx + 1]
            elif token == 'dev' and idx + 1 < len(parts):
                interface = parts[idx + 1]
            elif token == 'metric' and idx + 1 < len(parts):
                try:
                    metric = int(parts[idx + 1])
                except ValueError:
                    metric = None

        if gateway_ip is not None and not validate_ip_address(gateway_ip):
            gateway_ip = None

        if gateway_ip is None and interface is None:
            continue

        effective_metric = metric if metric is not None else 1 << 30
        if best_metric is None or effective_metric < best_metric:
            best = (gateway_ip, interface)
            best_metric = effective_metric

    return best


def get_default_interface():
    """
    Returns the default IPv4 interface.

    Resolution order:
      1. iproute2 (`ip route show default`) - authoritative on Linux
      2. netifaces - fallback when iproute2 is unavailable
    """
    _, interface = _parse_default_route()
    if interface and exists_interface(interface):
        return interface

    gateways = netifaces.gateways()
    if "default" in gateways and netifaces.AF_INET in gateways["default"]:
        candidate = gateways["default"][netifaces.AF_INET][1]
        if candidate and exists_interface(candidate):
            return candidate

    return None


def get_default_gateway():
    """
    Returns the default IPv4 gateway address.

    Resolution order:
      1. iproute2 (`ip route show default`) - authoritative on Linux
      2. netifaces - fallback when iproute2 is unavailable
    """
    gateway_ip, _ = _parse_default_route()
    if gateway_ip and validate_ip_address(gateway_ip):
        return gateway_ip

    gateways = netifaces.gateways()
    if "default" in gateways and netifaces.AF_INET in gateways["default"]:
        candidate = gateways["default"][netifaces.AF_INET][0]
        if candidate and validate_ip_address(candidate):
            return candidate

    return None


def _netmask_from_iproute2(interface):
    """
    Derives the IPv4 netmask for an interface from `ip -o -f inet addr show dev <iface>`.

    Example line:
        5: wlan0    inet 192.168.0.142/24 brd 192.168.0.255 scope global dynamic wlan0
    """
    output = _run_ip_command(['-o', '-f', 'inet', 'addr', 'show', 'dev', interface])
    if not output:
        return None

    for line in output.splitlines():
        match = re.search(r'inet\s+(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})', line)
        if not match:
            continue

        ip_address = match.group(1)
        prefix = int(match.group(2))

        # Skip loopback / link-local; we want a real LAN address.
        if ip_address.startswith('127.') or ip_address.startswith('169.254.'):
            continue
        if not 0 <= prefix <= 32:
            continue

        try:
            network = ipaddress.IPv4Network('{}/{}'.format(ip_address, prefix), strict=False)
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            continue

        return str(network.netmask)

    return None


def get_default_netmask(interface):
    """
    Returns the default IPv4 netmask associated with an interface.

    Resolution order:
      1. iproute2 (`ip addr show dev <iface>`) - authoritative on Linux
      2. netifaces - fallback when iproute2 is unavailable
    """
    netmask = _netmask_from_iproute2(interface)
    if netmask:
        return netmask

    try:
        ifaddrs = netifaces.ifaddresses(interface)
    except ValueError:
        return None

    if netifaces.AF_INET in ifaddrs:
        for entry in ifaddrs[netifaces.AF_INET]:
            candidate = entry.get("netmask")
            if candidate:
                return candidate

    return None


def get_mac_by_ip(interface, address):
    """
    Resolves hardware address from IP by sending ARP request
    and receiving ARP response with retry mechanism for stability.
    Enhanced for enterprise networks and mesh topology.
    """
    max_retries = 5
    base_timeout = 3

    def read_mac_from_neighbor_cache():
        """
        Reads resolved MAC from kernel neighbor table.
        This is useful as a fallback when active ARP probing is noisy/unreliable.
        """
        try:
            result = subprocess.run(
                ['ip', 'neigh', 'show', address, 'dev', interface],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return None

            output = result.stdout.strip().lower()
            # Example: "192.168.1.1 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
            if 'lladdr' not in output:
                return None

            parts = output.split()
            idx = parts.index('lladdr')
            if idx + 1 < len(parts):
                mac = parts[idx + 1]
                if validate_mac_address(mac) and mac != '00:00:00:00:00:00':
                    return mac
        except Exception:
            return None

        return None
    
    for attempt in range(max_retries):
        try:
            # Progressive timeout: increase on each retry
            timeout = base_timeout + (attempt * 2)  # 3, 5, 7, 9, 11 seconds

            # ARP who-has over Ethernet broadcast (L2)
            packet = ARP(op=1, pdst=address)
            arp_request = Ether(dst="ff:ff:ff:ff:ff:ff")/packet

            # L2 send/receive (correct API for iface-bound ARP)
            answered, _ = srp(arp_request, timeout=timeout, verbose=0, 
                            iface=interface, retry=2, multi=True)

            if answered:
                for sent, received in answered:
                    if received.haslayer(ARP):
                        mac = received[ARP].hwsrc
                        if mac and mac != "00:00:00:00:00:00":
                            return mac.lower()

            # If no direct ARP reply, try neighbor cache before next retry
            cached_mac = read_mac_from_neighbor_cache()
            if cached_mac:
                return cached_mac
                
        except KeyboardInterrupt:
            raise  # Allow user to interrupt
        except Exception:
            if attempt == max_retries - 1:
                # Last attempt failed - try one more time with broadcast
                try:
                    # Ping to populate ARP cache
                    subprocess.run(['ping', '-c', '1', '-W', '2', address], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
                    time.sleep(0.5)

                    # Try to read from OS neighbor cache as final fallback
                    cached_mac = read_mac_from_neighbor_cache()
                    if cached_mac:
                        return cached_mac
                except Exception:
                    pass
            else:
                # Wait before retrying, with exponential backoff
                time.sleep(0.5 * (attempt + 1))
    
    return None


def exists_interface(interface):
    """
    Determines whether or not a given interface exists
    """
    return interface in netifaces.interfaces()


def flush_network_settings(interface):
    """
    Flushes only evillimiter's nftables table and tc qdisc.
    Does NOT flush the entire ruleset to avoid disrupting other applications
    (docker, firewalld, ufw, etc.).
    """
    shell.execute_suppressed("{} delete table inet limiter".format(BIN_NFTABLES))
    shell.execute_suppressed("{} qdisc del dev {} root".format(BIN_TC, interface))


def flush_network_settings_selective(interface, table_names=None):
    """
    Alternative flush function that only removes specific nftables tables
    instead of flushing the entire ruleset. This is safer if other applications
    are also using nftables.
    
    Args:
        interface: Network interface name
        table_names: List of table names to delete (e.g., ['inet limiter', 'ip nat'])
                    If None, deletes commonly used tables for traffic limiting
    """
    if table_names is None:
        table_names = ['inet limiter', 'ip nat', 'ip mangle', 'ip filter']
    
    for table in table_names:
        shell.execute_suppressed("{} delete table {} 2>/dev/null || true".format(BIN_NFTABLES, table))
    
    # delete root qdisc for given interface
    shell.execute_suppressed("{} qdisc del dev {} root".format(BIN_TC, interface))


def validate_ip_address(ip):
    if not re.match(r"^(\d{1,3}\.){3}(\d{1,3})$", ip):
        return False
    return all(0 <= int(octet) <= 255 for octet in ip.split('.'))


def validate_mac_address(mac):
    return re.match(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$", mac) is not None


def create_qdisc_root(interface):
    """
    Creates a root htb qdisc in traffic control for a given interface
    """
    return shell.execute_suppressed("{} qdisc add dev {} root handle 1:0 htb".format(BIN_TC, interface)) == 0


def delete_qdisc_root(interface):
    return shell.execute_suppressed("{} qdisc del dev {} root handle 1:0 htb".format(BIN_TC, interface))


def enable_ip_forwarding():
    return shell.execute_suppressed("{} -w {}=1".format(BIN_SYSCTL, IP_FORWARD_LOC)) == 0


def disable_ip_forwarding():
    return shell.execute_suppressed("{} -w {}=0".format(BIN_SYSCTL, IP_FORWARD_LOC)) == 0


def setup_basic_nftables_structure():
    """
    Sets up basic nftables structure that applications can use.
    This replaces the need for setting default policies since nftables
    uses a different approach (default is to accept unless explicitly dropped).
    """
    # Create basic inet table for general use
    shell.execute_suppressed("{} 'add table inet filter' 2>/dev/null || true".format(BIN_NFTABLES))
    
    # Create basic chains (optional - nftables doesn't require default policies)
    shell.execute_suppressed("{} 'add chain inet filter input {{ type filter hook input priority filter; }}' 2>/dev/null || true".format(BIN_NFTABLES))
    shell.execute_suppressed("{} 'add chain inet filter forward {{ type filter hook forward priority filter; }}' 2>/dev/null || true".format(BIN_NFTABLES))
    shell.execute_suppressed("{} 'add chain inet filter output {{ type filter hook output priority filter; }}' 2>/dev/null || true".format(BIN_NFTABLES))


def reset_nftables_to_permissive():
    """
    Ensures nftables is in a permissive state (equivalent to the old iptables default policies).
    Since nftables default behavior is to accept unless explicitly blocked,
    this mainly involves clearing any restrictive rules.
    """
    shell.execute_suppressed("{} flush ruleset".format(BIN_NFTABLES))
