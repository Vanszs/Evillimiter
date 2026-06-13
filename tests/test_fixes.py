"""
Unit tests for all fixes applied to Evillimiter.
Run with: python -m pytest tests/test_fixes.py -v
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Fix 9: validate_ip_address
# ---------------------------------------------------------------------------
class TestValidateIPAddress(unittest.TestCase):
    def setUp(self):
        from evillimiter.networking.utils import validate_ip_address
        self.validate = validate_ip_address

    def test_valid_ips(self):
        for ip in ["192.168.1.1", "10.0.0.1", "0.0.0.0", "255.255.255.255"]:
            self.assertTrue(self.validate(ip), ip)

    def test_invalid_octet_over_255(self):
        for ip in ["999.0.0.1", "192.168.1.256", "0.0.0.999"]:
            self.assertFalse(self.validate(ip), ip)

    def test_invalid_format(self):
        for ip in ["192.168.1", "abc.def.ghi.jkl", "", "1.2.3.4.5"]:
            self.assertFalse(self.validate(ip), ip)

    def test_boundary_values(self):
        self.assertTrue(self.validate("0.0.0.0"))
        self.assertTrue(self.validate("255.255.255.255"))
        self.assertFalse(self.validate("256.0.0.0"))


# ---------------------------------------------------------------------------
# Fix 3: flush_network_settings — only deletes inet limiter, not flush ruleset
# ---------------------------------------------------------------------------
class TestFlushNetworkSettings(unittest.TestCase):
    @patch("evillimiter.networking.utils.shell")
    def test_does_not_flush_ruleset(self, mock_shell):
        from evillimiter.networking.utils import flush_network_settings
        mock_shell.execute_suppressed.return_value = 0
        flush_network_settings("eth0")

        calls = [str(c) for c in mock_shell.execute_suppressed.call_args_list]
        self.assertFalse(any("flush ruleset" in c for c in calls),
                         "flush ruleset must not be called — it destroys all nftables")

    @patch("evillimiter.networking.utils.shell")
    def test_deletes_limiter_table(self, mock_shell):
        from evillimiter.networking.utils import flush_network_settings
        mock_shell.execute_suppressed.return_value = 0
        flush_network_settings("eth0")

        calls = [str(c) for c in mock_shell.execute_suppressed.call_args_list]
        self.assertTrue(any("inet limiter" in c for c in calls))

    @patch("evillimiter.networking.utils.shell")
    def test_deletes_tc_qdisc(self, mock_shell):
        from evillimiter.networking.utils import flush_network_settings
        mock_shell.execute_suppressed.return_value = 0
        flush_network_settings("eth0")

        calls = [str(c) for c in mock_shell.execute_suppressed.call_args_list]
        self.assertTrue(any("qdisc del dev eth0 root" in c for c in calls))


# ---------------------------------------------------------------------------
# Fix 4 & 5: BandwidthMonitor — race condition and sniff recovery
# ---------------------------------------------------------------------------
class TestBandwidthMonitor(unittest.TestCase):
    @patch("evillimiter.networking.monitor.sniff")
    def test_running_set_before_thread_start(self, mock_sniff):
        """_running must be True before the sniff thread reads it."""
        from evillimiter.networking.monitor import BandwidthMonitor

        start_order = []
        original_thread_start = threading.Thread.start

        def patched_start(self_thread):
            # At the moment thread.start() is called, _running should already be True
            start_order.append(monitor._running)
            original_thread_start(self_thread)

        mock_sniff.side_effect = lambda **kw: None  # immediate return

        monitor = BandwidthMonitor("eth0", 1)
        with patch.object(threading.Thread, "start", patched_start):
            monitor.start()

        self.assertTrue(start_order[0],
                        "_running must be True before thread.start() is called")

    @patch("evillimiter.networking.monitor.sniff")
    def test_start_idempotent(self, mock_sniff):
        """Calling start() twice should not spawn two threads."""
        mock_sniff.side_effect = lambda **kw: None
        from evillimiter.networking.monitor import BandwidthMonitor

        monitor = BandwidthMonitor("eth0", 1)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            monitor._running = True  # simulate already started
            monitor.start()
            mock_thread_cls.assert_not_called()

    @patch("evillimiter.networking.monitor.sniff")
    def test_sniff_restarts_on_exception(self, mock_sniff):
        """_sniff loop must retry after an exception instead of dying."""
        call_count = []

        def sniff_side_effect(**kwargs):
            call_count.append(1)
            if len(call_count) == 1:
                raise OSError("interface down")
            # second call: stop the monitor to exit loop
            from evillimiter.networking.monitor import BandwidthMonitor
            # simulate stop_filter returning True immediately
            kwargs['stop_filter'](None)

        mock_sniff.side_effect = sniff_side_effect

        from evillimiter.networking.monitor import BandwidthMonitor
        monitor = BandwidthMonitor("eth0", 1)
        monitor._running = True

        with patch("time.sleep"):  # skip the 1s sleep
            # Run _sniff in a thread, let it process 2 iterations
            t = threading.Thread(target=monitor._sniff, daemon=True)
            t.start()
            t.join(timeout=2)

        self.assertGreaterEqual(len(call_count), 2,
                                "sniff must be retried after exception")


# ---------------------------------------------------------------------------
# Fix 10: ARPSpoofer._spoof uses 'with' lock
# ---------------------------------------------------------------------------
class TestARPSpooferLock(unittest.TestCase):
    def test_spoof_uses_context_manager(self):
        """_spoof must acquire lock via 'with' to prevent deadlock on exception."""
        import inspect
        from evillimiter.networking.spoof import ARPSpoofer
        source = inspect.getsource(ARPSpoofer._spoof)

        self.assertIn("with self._hosts_lock", source,
                      "_spoof must use 'with self._hosts_lock' context manager")
        self.assertNotIn("_hosts_lock.acquire()", source,
                         "_spoof must not use manual acquire()")


# ---------------------------------------------------------------------------
# Fix 7: Limiter._ensure_* called only once (cache flags)
# ---------------------------------------------------------------------------
class TestLimiterEnsureCache(unittest.TestCase):
    def _make_limiter(self):
        with patch("evillimiter.networking.limit.shell") as mock_shell:
            mock_shell.execute_suppressed.return_value = 0
            mock_shell.output_suppressed.return_value = "htb 1: default 30\n1:30"
            from evillimiter.networking.limit import Limiter
            limiter = Limiter.__new__(Limiter)
            limiter.interface = "eth0"
            limiter._host_dict = {}
            limiter._host_dict_lock = threading.RLock()
            limiter._nft_tables_ready = False
            limiter._root_qdisc_ready = False
            return limiter, mock_shell

    def test_ensure_called_once_after_flag_set(self):
        """After _ensure_* runs once, subsequent limit() calls skip it."""
        from evillimiter.networking.limit import Limiter, Direction

        with patch.object(Limiter, "_ensure_nft_tables") as mock_nft, \
             patch.object(Limiter, "_ensure_root_qdisc") as mock_qdisc, \
             patch.object(Limiter, "_apply_limit_direction_locked", return_value=True), \
             patch.object(Limiter, "_clear_direction_locked", return_value=True), \
             patch.object(Limiter, "_finalize_host_state_locked"):

            limiter = Limiter.__new__(Limiter)
            limiter.interface = "eth0"
            limiter._host_dict = {}
            limiter._host_dict_lock = threading.RLock()
            limiter._nft_tables_ready = False
            limiter._root_qdisc_ready = False

            # Simulate _ensure_* setting the flags
            def set_nft_flag():
                limiter._nft_tables_ready = True
            def set_qdisc_flag():
                limiter._root_qdisc_ready = True

            mock_nft.side_effect = set_nft_flag
            mock_qdisc.side_effect = set_qdisc_flag

            host = MagicMock()
            host.ip = "192.168.1.10"
            host.mac = "aa:bb:cc:dd:ee:ff"

            from evillimiter.networking.units import BitRate
            rate = BitRate(1000000)

            limiter.limit(host, Direction.OUTGOING, rate)
            limiter.limit(host, Direction.OUTGOING, rate)
            limiter.limit(host, Direction.OUTGOING, rate)

            # _ensure_* should only be called once despite 3 limit() calls
            mock_nft.assert_called_once()
            mock_qdisc.assert_called_once()


# ---------------------------------------------------------------------------
# Fix 1 & 2: evillimiter.py — no create_qdisc_root in initialize, cleanup flushes nft
# ---------------------------------------------------------------------------
class TestEvillimiterInitCleanup(unittest.TestCase):
    @patch("evillimiter.evillimiter.netutils")
    def test_initialize_does_not_call_create_qdisc_root(self, mock_netutils):
        mock_netutils.enable_ip_forwarding.return_value = True
        from evillimiter.evillimiter import initialize
        initialize("eth0")
        mock_netutils.create_qdisc_root.assert_not_called()

    @patch("evillimiter.evillimiter.netutils")
    def test_cleanup_calls_flush_network_settings(self, mock_netutils):
        from evillimiter.evillimiter import cleanup
        cleanup("eth0")
        mock_netutils.flush_network_settings.assert_called_once_with("eth0")

    @patch("evillimiter.evillimiter.netutils")
    def test_cleanup_disables_ip_forwarding(self, mock_netutils):
        from evillimiter.evillimiter import cleanup
        cleanup("eth0")
        mock_netutils.disable_ip_forwarding.assert_called_once()


# ---------------------------------------------------------------------------
# Fix 8: scan.py — inter >= 10ms and multi=False
# ---------------------------------------------------------------------------
class TestScanSweepBatchParams(unittest.TestCase):
    @patch("evillimiter.networking.scan.srp")
    def test_inter_minimum_10ms(self, mock_srp):
        """inter packet delay must be at least 10ms to avoid WiFi NIC buffer drops."""
        mock_srp.return_value = ([], [])
        from evillimiter.networking.scan import HostScanner

        scanner = HostScanner.__new__(HostScanner)
        scanner.interface = "wlan0"
        scanner.timeout = 2.5
        scanner.retries = 1
        scanner.inter_packet_delay = 0.001  # intentionally low
        scanner.inter_batch_delay = 0.0

        scanner._sweep_batch(["192.168.1.1"])

        _, kwargs = mock_srp.call_args
        self.assertGreaterEqual(kwargs["inter"], 0.01,
                                "inter must be >= 0.01s (10ms) for WiFi reliability")

    @patch("evillimiter.networking.scan.srp")
    def test_multi_is_false(self, mock_srp):
        """multi=False prevents scapy waiting full timeout per batch."""
        mock_srp.return_value = ([], [])
        from evillimiter.networking.scan import HostScanner

        scanner = HostScanner.__new__(HostScanner)
        scanner.interface = "wlan0"
        scanner.timeout = 2.5
        scanner.retries = 1
        scanner.inter_packet_delay = 0.01
        scanner.inter_batch_delay = 0.0

        scanner._sweep_batch(["192.168.1.1"])

        _, kwargs = mock_srp.call_args
        self.assertFalse(kwargs.get("multi", True),
                         "multi must be False for faster scan completion")


if __name__ == "__main__":
    unittest.main()
