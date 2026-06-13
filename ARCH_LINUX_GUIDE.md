# Arch Linux Installation & Setup Guide

## Prerequisites

### Install Required Packages
```bash
# Update system
sudo pacman -Syu

# Install core dependencies
sudo pacman -S python python-setuptools python-pip nftables iproute2 git

# Install Python packages
sudo pip install scapy netifaces tqdm netaddr colorama
```

## Installation

```bash
# Clone repository
git clone https://github.com/Masrkai/Evillimiter.git
cd Evillimiter

# Install
sudo python3 setup.py install
```

## Post-Installation Setup

### 1. Enable nftables (if not already enabled)
```bash
sudo systemctl enable nftables
sudo systemctl start nftables
sudo systemctl status nftables
```

### 2. Check Kernel Modules
```bash
# Check if required modules are loaded
lsmod | grep -E 'sch_htb|ifb'

# Load if missing
sudo modprobe sch_htb
sudo modprobe ifb
```

### 3. Test Installation
```bash
# Run test script
sudo ./test_pentest_fix.sh

# Or test manually
sudo evillimiter --help
```

## First Run

### Recommended First-Time Setup
```bash
# 1. Flush any existing rules
sudo evillimiter --flush

# 2. Run normally
sudo evillimiter

# 3. In the interactive shell:
(Main) >>> scan
(Main) >>> hosts
```

### If Gateway MAC Resolution Fails
```bash
# Option 1: Specify manually
sudo evillimiter -m XX:XX:XX:XX:XX:XX

# Option 2: Check your gateway MAC first
ip neigh show

# Option 3: Flush and retry
sudo evillimiter --flush
sudo evillimiter
```

## Common Issues & Solutions

### Issue: "Permission denied"
```bash
# Always run as root
sudo evillimiter
```

### Issue: "nft not found"
```bash
# Install nftables
sudo pacman -S nftables
sudo systemctl start nftables
```

### Issue: "tc not found"
```bash
# Install iproute2
sudo pacman -S iproute2
```

### Issue: "module 'scapy' has no attribute 'ARP'"
```bash
# Reinstall scapy
sudo pip uninstall scapy scapy-python3
sudo pip install scapy
```

### Issue: Scan is slow or shows timeouts
This is **normal** and **intentional** for stability:
- Reduced batch size (50 IPs per batch)
- Inter-batch delays (100ms)
- Increased timeout (5 seconds)
- These changes prevent network flooding and improve reliability

## Configuration Tuning (Advanced)

If you need to adjust performance, edit:
`/home/vanszs/Documents/Code/Evillimiter/evillimiter/networking/scan.py`

```python
# For slower/busy networks (more stable):
self.batch_size = 25          # Smaller batches
self.timeout = 10             # Longer timeout
self.inter_batch_delay = 0.2  # More delay

# For fast/quiet networks (faster scan):
self.batch_size = 75          # Larger batches
self.timeout = 3              # Shorter timeout
self.inter_batch_delay = 0.05 # Less delay
```

## Usage Examples

### Basic Bandwidth Limiting
```bash
sudo evillimiter

(Main) >>> scan
(Main) >>> hosts
(Main) >>> limit 1,2,3 100kbit        # Limit hosts 1,2,3 to 100kbit
(Main) >>> limit 4 500kbit --download # Limit download only
(Main) >>> limit 5 1mbit --upload     # Limit upload only
```

### Blocking Hosts
```bash
(Main) >>> block 1,2              # Block completely
(Main) >>> block 3 --download     # Block download only
(Main) >>> free 1,2,3             # Unblock/unlimit
```

### Monitoring
```bash
(Main) >>> monitor                    # Monitor all limited hosts
(Main) >>> monitor --interval 1000    # Update every 1 second
(Main) >>> analyze 1,2 --duration 60  # Analyze for 60 seconds
```

### Watchlist (Track Reconnects)
```bash
(Main) >>> watch add 1,2,3           # Add to watchlist
(Main) >>> watch set interval 120    # Check every 2 minutes
(Main) >>> watch set range 192.168.1.1-192.168.1.50
(Main) >>> watch                     # Show status
```

## Uninstallation

```bash
# Remove installed files
sudo pip uninstall evillimiter

# Or manually
sudo rm -rf /usr/local/lib/python*/dist-packages/evillimiter*
sudo rm /usr/local/bin/evillimiter

# Clean up rules
sudo nft flush ruleset
sudo tc qdisc del dev <interface> root 2>/dev/null || true
```

## Arch-Specific Notes

### Firewall Interaction
If you use `ufw` or `firewalld`:
```bash
# Temporarily disable
sudo systemctl stop ufw
# or
sudo systemctl stop firewalld

# Run evillimiter
sudo evillimiter

# Re-enable after
sudo systemctl start ufw
```

### Network Manager
If NetworkManager interferes:
```bash
# Check connection
nmcli device status

# If needed, temporarily stop
sudo systemctl stop NetworkManager
sudo evillimiter
sudo systemctl start NetworkManager
```

### Systemd Service (Optional)
To run evillimiter as a service (advanced):
```bash
# Create service file
sudo nano /etc/systemd/system/evillimiter.service

# Add:
[Unit]
Description=Evil Limiter Network Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/evillimiter
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable evillimiter
sudo systemctl start evillimiter
```

## Security Considerations

⚠️ **Important:**
- Only use on networks you own or have permission to test
- ARP spoofing is detectable by IDS/IPS systems
- Use responsibly and ethically
- This is a penetration testing tool

## Performance Tips

1. **Scan smaller ranges** instead of entire subnet:
   ```
   scan --range 192.168.1.1-192.168.1.50
   ```

2. **Use specific host IDs** instead of 'all':
   ```
   limit 1,2,3 100kbit
   ```

3. **Adjust batch size** based on your network capacity

4. **Monitor system resources**:
   ```bash
   htop  # Watch CPU/RAM usage
   iftop # Watch network usage
   ```

## Getting Help

1. Check documentation:
   - [PENTEST_FIX_SUMMARY.md](PENTEST_FIX_SUMMARY.md)
   - [CHANGES_COMPARISON.md](CHANGES_COMPARISON.md)
   
2. Run help command:
   ```bash
   sudo evillimiter --help
   (Main) >>> help
   ```

3. Check issues: https://github.com/Masrkai/Evillimiter/issues

## Contributing

Found a bug? Want to improve Arch support?
1. Fork the repo
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

**Tested on:** Arch Linux (2025), Python 3.13, Kernel 6.x+
**Maintained by:** [Masrkai](https://github.com/Masrkai/)
**Pentest fixes by:** [Vanszs](https://github.com/Vanszs/)
