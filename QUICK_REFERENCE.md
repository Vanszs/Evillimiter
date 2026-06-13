# Quick Reference Card

## Installation (One-Liner)
```bash
sudo pacman -S python python-pip nftables iproute2 && sudo pip install scapy netifaces tqdm netaddr colorama && git clone https://github.com/Masrkai/Evillimiter.git && cd Evillimiter && sudo python3 setup.py install
```

## Quick Start
```bash
sudo evillimiter --flush  # First time
sudo evillimiter          # Run
scan                      # Scan network
hosts                     # List devices
limit 1 100kbit          # Limit host #1
```

## Common Commands

| Action | Command |
|--------|---------|
| **Scan network** | `scan` or `scan --range 192.168.1.1-50` |
| **List hosts** | `hosts` |
| **Limit bandwidth** | `limit 1,2,3 100kbit` |
| **Limit download only** | `limit 1 500kbit --download` |
| **Limit upload only** | `limit 1 500kbit --upload` |
| **Block completely** | `block 1,2,3` |
| **Unblock/Unlimit** | `free 1,2,3` |
| **Monitor usage** | `monitor` |
| **Analyze traffic** | `analyze 1,2 --duration 60` |
| **Add to watchlist** | `watch add 1,2` |
| **Clear screen** | `clear` |
| **Quit** | `quit` or `Ctrl+C` |

## Speed Units
- `bit` - bits per second
- `kbit` - kilobits per second
- `mbit` - megabits per second  
- `gbit` - gigabits per second

## Examples
```bash
# Limit multiple hosts to 200kbit
limit 1,2,3,4 200kbit

# Block all hosts
block all

# Free all hosts
free all

# Monitor with 1-second refresh
monitor --interval 1000

# Analyze host #5 for 2 minutes
analyze 5 --duration 120
```

## Command-Line Arguments

```bash
sudo evillimiter [OPTIONS]

-h, --help              Show help
-i, --interface IFACE   Specify interface (auto-detected)
-g, --gateway IP        Specify gateway IP (auto-detected)
-m, --gateway-mac MAC   Specify gateway MAC (auto-detected)
-n, --netmask MASK      Specify netmask (auto-detected)
-f, --flush             Flush existing nftables/tc rules
--colorless             Disable colored output
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Gateway MAC not resolved** | `sudo evillimiter --flush` then retry |
| **Permission denied** | Always use `sudo evillimiter` |
| **Scan timeouts** | Normal! Stability feature for pentesting |
| **nft not found** | `sudo pacman -S nftables` |
| **tc not found** | `sudo pacman -S iproute2` |

## Files Modified (For Reference)

- `evillimiter/networking/scan.py` - Scan logic with pentest fixes
- `evillimiter/networking/utils.py` - Gateway MAC resolution with retry
- `README.md` - Updated documentation
- `.vscode/settings.json` - Pylance config to suppress warnings

## Performance Tuning

Edit `evillimiter/networking/scan.py`:

```python
# Conservative (stable, slower):
self.batch_size = 25
self.timeout = 10
self.inter_batch_delay = 0.2

# Balanced (default):
self.batch_size = 50
self.timeout = 5
self.inter_batch_delay = 0.1

# Aggressive (fast, may timeout):
self.batch_size = 75
self.timeout = 3
self.inter_batch_delay = 0.05
```

## Important Notes

✅ **Fixed Issues:**
- TimeoutError spam during scan
- Gateway MAC resolution failures
- Network flooding issues
- Crashes on busy networks

⚠️ **Legal Warning:**
Only use on networks you own or have explicit permission to test!

📚 **Full Documentation:**
- [README.md](README.md) - Main documentation
- [ARCH_LINUX_GUIDE.md](ARCH_LINUX_GUIDE.md) - Arch-specific guide
- [PENTEST_FIX_SUMMARY.md](PENTEST_FIX_SUMMARY.md) - Technical fixes
- [CHANGES_COMPARISON.md](CHANGES_COMPARISON.md) - Before/after comparison

---

**Version:** November 2025 (Pentest Stability Release)
**Platform:** Arch Linux, Python 3.13+
**Credits:** [bitbrute](https://github.com/bitbrute/) (original), [Masrkai](https://github.com/Masrkai/) (revival), [Vanszs](https://github.com/Vanszs/) (pentest fixes)
