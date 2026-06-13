import logging
from tqdm import tqdm
import time
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from scapy.all import ARP, Ether, srp, conf  # Using srp instead of sr1 for batch processing

# Suppress scapy warnings and errors
logging.getLogger("scapy.runtime").setLevel(logging.CRITICAL)
logging.getLogger("scapy").setLevel(logging.CRITICAL)

# Configure scapy to not show verbose output
conf.verb = 0

from .host import Host
from .utils import get_neighbor_cache_entries, resolve_host_name, normalize_host_name
from evillimiter.console.io import IO


class HostScanner(object):
    def __init__(self, interface, iprange):
        self.interface = interface
        self.iprange = iprange
        self._hostname_cache = {}

        self._base_settings = self._build_scan_settings(iprange)
        self._apply_scan_settings(self._base_settings)
        self.resolve_timeout = 1.5
        self.max_scan_attempts = 2
        self.recovery_scan_timeout = 2.0
        self.recovery_batch_size = 128

    def _build_scan_settings(self, iprange):
        network_size = len(iprange) if hasattr(iprange, '__len__') else 256

        # Balance fast ARP discovery with one controlled recovery pass.
        if network_size > 1024:
            return {
                "max_workers": 10,
                "retries": 1,
                "timeout": 3.5,
                "batch_size": 48,
                "inter_batch_delay": 0.04,
                "inter_packet_delay": 0.003,
            }
        if network_size > 512:
            return {
                "max_workers": 12,
                "retries": 1,
                "timeout": 3.0,
                "batch_size": 64,
                "inter_batch_delay": 0.03,
                "inter_packet_delay": 0.002,
            }
        return {
            "max_workers": 12,
            "retries": 1,
            "timeout": 2.5,
            "batch_size": 64,
            "inter_batch_delay": 0.02,
            "inter_packet_delay": 0.001,
        }

    def _apply_scan_settings(self, settings):
        self.max_workers = settings["max_workers"]
        self.retries = settings["retries"]
        self.timeout = settings["timeout"]
        self.batch_size = settings["batch_size"]
        self.inter_batch_delay = settings["inter_batch_delay"]
        self.inter_packet_delay = settings["inter_packet_delay"]

    def _detect_network_conditions(self, iprange):
        """
        Detects network conditions and adjusts parameters for mesh topology
        """
        if len(iprange) < 2:
            return

        try:
            probe_candidates = iprange[1:4] if len(iprange) > 3 else iprange[:1]
            if not probe_candidates:
                return

            start = time.time()
            probe_request = Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(op=1, pdst=probe_candidates)
            answered, _ = srp(
                probe_request,
                timeout=min(self.timeout, 1.2),
                retry=0,
                verbose=0,
                iface=self.interface,
                inter=0,
            )
            if not answered:
                return

            latency = ((time.time() - start) * 1000) / len(answered)

            if latency > 250:
                self.timeout = min(self.timeout + 0.75, 5)
                self.inter_batch_delay = min(self.inter_batch_delay + 0.03, 0.08)
                self.batch_size = max(self.batch_size - 16, 24)
        except Exception:
            pass  # Continue with default settings

    def _merge_hosts(self, discovered_hosts, new_hosts):
        for host in new_hosts:
            existing_host = discovered_hosts.get(host.mac)
            if existing_host is None:
                self._cache_hostname(host)
                discovered_hosts[host.mac] = host
                continue
            if existing_host.ip != host.ip:
                existing_host.ip = host.ip
            if not existing_host.name and host.name:
                existing_host.name = host.name
            self._cache_hostname(existing_host)

    def _split_batches(self, iprange, batch_size):
        return [iprange[i:i + batch_size] for i in range(0, len(iprange), batch_size)]

    def _resolve_hostnames(self, batch_hosts):
        if not batch_hosts:
            return

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            resolution_func = partial(self._resolve_hostname, timeout=self.resolve_timeout)
            try:
                list(executor.map(resolution_func, batch_hosts))
            except Exception:
                pass

    def _recover_missing_hosts(self, remaining_ips, discovered_hosts):
        if not remaining_ips:
            return

        recovered_hosts = []
        for ip_address, mac_address in get_neighbor_cache_entries(self.interface, remaining_ips):
            recovered_hosts.append(Host(ip_address, mac_address, self._hostname_cache.get(mac_address, "")))

        if recovered_hosts:
            self._merge_hosts(discovered_hosts, recovered_hosts)
            remaining_ips = [ip for ip in remaining_ips if ip not in {host.ip for host in recovered_hosts}]

        if not remaining_ips:
            return

        recovery_batch_size = min(self.recovery_batch_size, max(16, len(remaining_ips)))
        recovery_batches = self._split_batches(remaining_ips, recovery_batch_size)
        for batch in recovery_batches:
            batch_hosts = self._sweep_batch(
                batch,
                timeout=self.recovery_scan_timeout,
                retries=0,
                inter_packet_delay=0,
                inter_batch_delay=0,
            )
            if batch_hosts:
                self._merge_hosts(discovered_hosts, batch_hosts)

    def _cache_hostname(self, host):
        hostname = normalize_host_name(host.name)
        if hostname is None:
            return

        host.name = hostname
        self._hostname_cache[host.ip] = hostname
        if host.mac:
            self._hostname_cache[host.mac.lower()] = hostname

    def _get_cached_hostname(self, host):
        if host.mac:
            cached_name = self._hostname_cache.get(host.mac.lower())
            if cached_name:
                return cached_name
        return self._hostname_cache.get(host.ip)

    def scan(self, iprange=None):
        iprange = [str(x) for x in (self.iprange if iprange is None else iprange)]

        self._apply_scan_settings(self._build_scan_settings(iprange))

        self._detect_network_conditions(iprange)
        hosts = []
        scan_attempt = 0
        successful_scan = False

        while scan_attempt < self.max_scan_attempts and not successful_scan:
            discovered_hosts = {}
            try:
                with tqdm(total=len(iprange), ncols=45, bar_format="{percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt}") as pbar:
                    try:
                        ip_batches = self._split_batches(iprange, self.batch_size)
                        for batch_idx, batch in enumerate(ip_batches):
                            batch_hosts = self._sweep_batch(batch)

                            if batch_hosts:
                                self._merge_hosts(discovered_hosts, batch_hosts)

                            pbar.update(len(batch))

                            if (batch_idx + 1) % 5 == 0:
                                time.sleep(self.inter_batch_delay * 2)

                        discovered_ips = {host.ip for host in discovered_hosts.values()}
                        remaining_ips = [ip for ip in iprange if ip not in discovered_ips]
                        if remaining_ips:
                            self._recover_missing_hosts(remaining_ips, discovered_hosts)

                        hosts = list(discovered_hosts.values())
                        self._resolve_hostnames(hosts)
                        successful_scan = True

                    except KeyboardInterrupt:
                        pbar.close()
                        IO.ok("aborted. waiting for shutdown...")
                        return list(discovered_hosts.values())
                    except Exception:
                        pbar.close()
                        if scan_attempt < self.max_scan_attempts - 1:
                            IO.ok(f"scan interrupted, retrying... (attempt {scan_attempt + 2}/{self.max_scan_attempts})")
                            time.sleep(2)

            except Exception:
                pass

            scan_attempt += 1

        return hosts


    def scan_for_reconnects(self, hosts, iprange=None):
        iprange = [str(x) for x in (self.iprange if iprange is None else iprange)]
        scanned_hosts = []

        try:
            ip_batches = self._split_batches(iprange, self.batch_size)
            for batch in ip_batches:
                batch_hosts = self._sweep_batch(batch)
                if batch_hosts:
                    scanned_hosts.extend(batch_hosts)
        except Exception:
            # Silently handle errors during reconnect scanning
            pass

        # Create lookup dictionary by MAC for faster comparison
        mac_to_scanned_host = {host.mac: host for host in scanned_hosts}

        reconnected_hosts = {}
        for host in hosts:
            if host.mac in mac_to_scanned_host:
                s_host = mac_to_scanned_host[host.mac]
                if host.ip != s_host.ip:
                    s_host.name = host.name
                    reconnected_hosts[host] = s_host

        return reconnected_hosts

    def _sweep_batch(self, ips, timeout=None, retries=None, inter_packet_delay=None, inter_batch_delay=None):
        """
        Sends ARP packets in batch and processes responses with error handling
        Optimized for mesh topology and enterprise networks
        """
        if not ips:
            return []

        hosts = []
        current_timeout = self.timeout if timeout is None else timeout
        current_retries = self.retries if retries is None else retries
        current_inter_packet_delay = self.inter_packet_delay if inter_packet_delay is None else inter_packet_delay
        current_inter_batch_delay = self.inter_batch_delay if inter_batch_delay is None else inter_batch_delay

        try:
            arp_requests = [Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip) for ip in ips]
            responses, _ = srp(
                arp_requests,
                timeout=current_timeout,
                retry=current_retries,
                verbose=0,
                iface=self.interface,
                inter=max(current_inter_packet_delay, 0.01),  # minimum 10ms for WiFi NIC buffers
                multi=False  # True causes scapy to wait full timeout per-batch; False is faster
            )

            seen_macs = set()
            for sent, received in responses:
                if received.hwsrc not in seen_macs:
                    hosts.append(Host(received.psrc, received.hwsrc, ""))
                    seen_macs.add(received.hwsrc)

        except KeyboardInterrupt:
            raise
        except Exception:
            pass

        if current_inter_batch_delay > 0:
            time.sleep(current_inter_batch_delay)

        return hosts

    def _resolve_hostname(self, host, timeout=1.0):
        """
        Resolves hostname with timeout
        """
        cached_name = self._get_cached_hostname(host)
        if cached_name:
            host.name = cached_name
            return host

        name = resolve_host_name(self.interface, host.ip, host.mac, timeout=timeout)
        if name:
            host.name = name
            self._cache_hostname(host)

        return host

    # Keep the original _sweep method for backward compatibility
    def _sweep(self, ip):
        """
        Sends ARP packet and listens for answer,
        if present the host is online
        """
        try:
            arp_request = Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(op=1, pdst=ip)
            answered, _ = srp(arp_request, retry=self.retries, timeout=self.timeout, verbose=0, iface=self.interface)
            
            if answered:
                for sent, received in answered:
                    return Host(received.psrc, received.hwsrc, "")
        except Exception:
            pass
        
        return None
