<p align="center"><img src="/evillimiter/image.png" /></p>

# Evil Limiter - Enterprise & Pentest Edition

[![License Badge](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Compatibility](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](PROJECT)
[![Platform](https://img.shields.io/badge/platform-Linux-blue.svg)](PROJECT)
[![Arch Linux](https://img.shields.io/badge/Arch%20Linux-optimized-success.svg)](PROJECT)

A powerful tool to monitor, analyze and limit bandwidth (upload/download) of devices on your local network without physical or administrative access. Enhanced for enterprise networks, mesh topology, and penetration testing scenarios.

```evillimiter``` employs [ARP spoofing](https://en.wikipedia.org/wiki/ARP_spoofing) and [traffic shaping](https://en.wikipedia.org/wiki/Traffic_shaping) to throttle the bandwidth of hosts on the network.

**This Fork Features:**
- 🎯 Adaptive configuration for networks of any size
- 🌐 Enterprise network support (10.x.x.x, /16-/24)
- 🔄 Mesh topology optimization with multi-path handling
- 🛡️ Enhanced stealth for monitored environments
- 🚀 Modern nftables implementation
- 🐛 Robust error handling and automatic recovery

> **⚠️ Note:** This fork is optimized and tested on **Arch Linux**. If you're using a different distribution (Debian, Ubuntu, Fedora, etc.), please review the installation instructions and adjust package names according to your OS. The tool should work on any modern Linux distribution with proper dependencies.

**Credits:**
- Original author: [bitbrute](https://github.com/bitbrute/)
- NixOS packaging: [Masrkai](https://github.com/Masrkai/)
- Enterprise & Pentest enhancements: [Vanszs](https://github.com/Vanszs/)

## Recent Improvements (November 2025)

### Enterprise Network & Mesh Topology Support
**NEW:** Optimized for large enterprise networks and mesh topology:

**Adaptive Configuration:**
- 🎯 **Auto-detects network size** and adjusts parameters automatically
- 📊 Small networks (<512 IPs): Fast scanning
- 🏢 Medium networks (512-1024 IPs): Balanced approach
- 🌐 Large networks (>1024 IPs): Conservative, reliable scanning

**Mesh Topology Features:**
- ✅ Multi-response ARP handling (accepts multiple replies)
- ✅ MAC-based deduplication for redundant paths
- ✅ Progressive timeout with exponential backoff
- ✅ Network condition detection and adaptation
- ✅ Batch retry mechanism with increased timeout
- ✅ Extra stability delays for complex topologies

**Enhanced Gateway Resolution:**
- 5 retry attempts (vs 3 previously)
- Progressive timeout: 3s → 11s (up to 45s total)
- ARP cache fallback via system `ip neigh`
- Ether frame compatibility for better mesh support

**Tested On:**
- ✅ 10.x.x.x enterprise networks (Class A private)
- ✅ Mesh topology with redundant paths
- ✅ Networks with 500+ devices
- ✅ IDS/IPS-monitored environments
- ✅ Campus/university networks
- ✅ Corporate networks with VLANs

See [ENTERPRISE_MESH_GUIDE.md](ENTERPRISE_MESH_GUIDE.md) for detailed configuration.

### Pentest Stability Fixes
This fork includes significant stability improvements for penetration testing environments:

**Fixed Issues:**
- ✅ Eliminated `TimeoutError` spam during network scanning
- ✅ Resolved gateway MAC address resolution failures
- ✅ Added retry mechanisms for unreliable networks
- ✅ Improved error handling for busy/monitored networks
- ✅ Suppressed verbose scapy output

**Technical Improvements:**
- Adaptive batch sizing (20-50 IPs based on network)
- Smart timeout adjustment (5-8 seconds based on conditions)
- Inter-batch delays (100-150ms) to prevent network flooding
- Implemented 5-retry mechanism for gateway MAC resolution
- Enhanced error suppression for cleaner console output
- Graceful degradation for hostname resolution failures

**Performance Characteristics:**
- Small networks: ~30-60 seconds for /24
- Medium networks: ~2-5 minutes for /23
- Large networks: ~8-15 minutes for /22
- Zero crashes on busy networks
- Clean console output without error spam
- Works reliably in pentesting/red team scenarios

See [PENTEST_FIX_SUMMARY.md](PENTEST_FIX_SUMMARY.md) and [CHANGES_COMPARISON.md](CHANGES_COMPARISON.md) for detailed technical documentation.

### Nftables Migration
- Migrated from legacy `iptables` to modern `nftables`
- Better performance and compatibility with modern Linux kernels
- Cleaner rule management and improved security


**Searching for a Windows-compatible version?**<br>
Check out the open-source alternative *"made by the original author [bitbrute](https://github.com/bitbrute/) not me "*
- [EvilLimiter for Windows](https://github.com/bitbrute/evillimiter-windows).

## Requirements
- Linux distribution (Primary: Arch Linux | Compatible: Debian, Ubuntu, Kali, NixOS, Fedora)
- Python 3.11 or greater
- Root/sudo privileges
- Modern Linux kernel (5.x+) with nftables support

Possibly missing python packages will be installed during the installation process.

## Installation

> **💡 Important:** This fork is developed and optimized on **Arch Linux**. Instructions below are provided for various distributions, but you may need to adjust package names and installation steps according to your specific OS. Check your distribution's documentation for package equivalents.

### Arch Linux / Manjaro (Recommended - Tested)

This is the primary development and testing environment:

```bash
# Install dependencies
sudo pacman -S python python-setuptools python-pip nftables iproute2

# Clone and install
git clone https://github.com/Vanszs/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install

# Verify installation
sudo python3 test_enterprise_mesh.py
```

### Debian / Ubuntu / Kali Linux (Community Tested)

```bash
# Install dependencies
sudo apt update
sudo apt install python3-setuptools python3-netifaces python3-pip nftables iproute2

# Clone and install
git clone https://github.com/Vanszs/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install
```

**Note for Debian/Ubuntu:** If you encounter issues with nftables, you may need to:
```bash
# Enable nftables
sudo systemctl enable nftables
sudo systemctl start nftables

# Or switch from iptables to nftables
sudo update-alternatives --set iptables /usr/sbin/iptables-nft
```

### Fedora / RHEL / CentOS (Adjust as Needed)

```bash
# Install dependencies (adjust package names)
sudo dnf install python3-setuptools python3-pip nftables iproute

# Clone and install
git clone https://github.com/Vanszs/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install
```

### Other Linux Distributions

Please adjust package names according to your distribution's package manager:

```bash
# Generic steps:
# 1. Install: python3 (>=3.11), pip, setuptools, nftables, iproute2/iproute
# 2. Clone repository
# 3. Install Python dependencies
# 4. Run setup

git clone https://github.com/Vanszs/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install
```

**Common package name equivalents:**
| Arch Linux | Debian/Ubuntu | Fedora/RHEL | OpenSUSE |
|------------|---------------|-------------|----------|
| `python` | `python3` | `python3` | `python3` |
| `python-pip` | `python3-pip` | `python3-pip` | `python3-pip` |
| `nftables` | `nftables` | `nftables` | `nftables` |
| `iproute2` | `iproute2` | `iproute` | `iproute2` |

**Note:** For NixOS users, a package is available at [Evillimiter.nix](https://github.com/Masrkai/Nix_Configuration/blob/main/Programs/Packages/evillimiter.nix)

### Verify Installation

After installation, test that everything works:

```bash
# Quick test
sudo evillimiter --help

# Comprehensive test (Arch Linux)
sudo python3 test_enterprise_mesh.py

# Basic functionality test
sudo ./test_pentest_fix.sh
```

## Usage

**Important:** Always run with sudo/root privileges:
```bash
sudo evillimiter
```

```evillimiter``` will try to resolve required information (network interface, netmask, gateway address, ...) on its own, automatically.

**First Time Setup (Recommended):**
```bash
# Flush existing network rules to start clean
sudo evillimiter --flush

# Run normally
sudo evillimiter

# In the interactive shell:
(Main) >>> scan              # Scan network for hosts
(Main) >>> hosts             # Display found hosts
(Main) >>> limit 1,2 100kbit # Limit bandwidth of hosts with ID 1 and 2
```

**For Enterprise Networks (10.x.x.x, Large Networks, Mesh Topology):**
```bash
# The scanner automatically detects network size and optimizes settings
sudo evillimiter

# Scan your enterprise network
(Main) >>> scan --range 10.201.3.1-10.201.3.254

# For very large networks, scan in chunks
(Main) >>> scan --range 10.201.3.1-10.201.3.100
(Main) >>> scan --range 10.201.3.101-10.201.3.200

# Gateway MAC resolution is enhanced with 5 retries (takes up to 45s)
# Just wait, it will succeed on enterprise networks
```

See [ENTERPRISE_MESH_GUIDE.md](ENTERPRISE_MESH_GUIDE.md) for advanced enterprise network usage.

#### Command-Line Arguments

| Argument | Explanation |
| -------- | ----------- |
| ```-h``` | Displays help message listing all command-line arguments |
| ```-i [Interface Name]``` | Specifies network interface (resolved if not specified)|
| ```-g [Gateway IP Address]``` | Specifies gateway IP address (resolved if not specified)|
| ```-m [Gateway MAC Address]``` | Specifies gateway MAC address (resolved if not specified)|
| ```-n [Netmask Address]``` | Specifies netmask (resolved if not specified)|
| ```-f``` | Flushes current nftables and tc configuration. Ensures that packets are dealt with correctly.|
| ```--colorless``` | Disables colored output |

#### ```evillimiter``` Commands

| Command | Explanation |
| ------- | ----------- |
| ```scan (--range [IP Range])``` | Scans your network for online hosts. One of the first things to do after start.<br>```--range``` lets you specify a custom IP range.<br>For example: ```scan --range 192.168.178.1-192.168.178.40``` or just ```scan``` to scan the entire subnet.
| ```hosts (--force)``` | Displays all the hosts/devices previously scanned and basic information. Shows ID for each host that is required for interaction.<br>```--force``` forces the table to be shown, even when it doesn't fit the terminal.
| ```limit [ID1,ID2,...] [Rate] (--upload) (--download)``` | Limits bandwidth of host(s) associated to specified ID. Rate determines the internet speed.<br>```--upload``` limits outgoing traffic only.<br>```--download``` limits incoming traffic only.<br>Valid rates: ```bit```, ```kbit```, ```mbit```, ```gbit```<br>For example: ```limit 4,5,6 200kbit``` or ```limit all 1gbit```
| ```block [ID1,ID2,...] (--upload) (--download)``` | Blocks internet connection of host(s) associated to specified ID.<br>```--upload``` limits outgoing traffic only <br>```--download``` limits incoming traffic only.
| ```free [ID1,ID2,...]``` | Unlimits/Unblocks host(s) associated to specified ID. Removes all further restrictions.
| ```add [IP] (--mac [MAC])``` | Adds custom host to host list. MAC-Address will be resolved automatically or can be specified manually.<br>For example: ```add 192.168.178.24``` or ```add 192.168.1.50 --mac 1c:fc:bc:2d:a6:37```
| ```monitor (--interval [time in ms])``` | Monitors bandwidth usage of limited host(s) (current usage, total bandwidth used, ...).<br>```--interval``` sets the interval after bandwidth information get refreshed in milliseconds (default 500ms).<br>For example: ```monitor --interval 1000```
| ```analyze [ID1,ID2,...] (--duration [time in s])``` | Analyzes traffic of host(s) without limiting to determine who uses how much bandwidth.<br>```--duration``` specifies the duration of the analysis in seconds (default 30s).<br>For example: ```analyze 2,3 --duration 120```
| ```watch``` | Shows current watch status. The watch feature detects when a host reconnects with a different IP address.
| ```watch add [ID1,ID2,...]``` | Adds specified host(s) to the watchlist.<br>For example: ```watch add 6,7,8```
| ```watch remove [ID1,ID2,...]``` | Removes specified host(s) from the watchlist.<br>For example: ```watch remove all```
| ```watch set [Attribute] [Value]``` | Changes current watch settings. The following attributes can be changed:<br>```range``` is the IP range to scan for reconnects.<br>```interval``` is the time to wait between each network scan (in seconds).<br>For example: ```watch set interval 120```
| ```clear``` | Clears the terminal window.
| ```quit``` | Quits the application.
| ```?```, ```help``` | Displays command information similar to this one.

## Restrictions

- **Limits IPv4 connctions only**, since [ARP spoofing](https://en.wikipedia.org/wiki/ARP_spoofing) requires the ARP packet that is only present  on IPv4 networks.

## Troubleshooting

### Gateway MAC Resolution Issues
If you encounter `ERR gateway mac address could not be resolved`:
```bash
# Try flushing network settings first
sudo evillimiter --flush

# Or specify gateway MAC manually
sudo evillimiter -m XX:XX:XX:XX:XX:XX
```

### Permission Errors
```bash
# Ensure you're running as root
sudo evillimiter

# Check if nftables and tc are available
which nft
which tc
```

### Scan Timeout Issues
The tool now handles timeouts gracefully. If scanning is slow:
- This is intentional for stability in pentesting scenarios
- Reduced batch sizes prevent network flooding
- Inter-batch delays improve reliability

### Testing Your Installation
```bash
# Run the comprehensive test suite
sudo python3 test_enterprise_mesh.py

# Or run the basic test script
sudo ./test_pentest_fix.sh

# Or test manually
sudo evillimiter
(Main) >>> scan
```

### Arch Linux Specific
```bash
# Enable and start nftables if needed
sudo systemctl enable nftables
sudo systemctl start nftables

# Check kernel modules
lsmod | grep -E 'sch_htb|ifb'
```

## Documentation

- **[README.md](README.md)** - This file, main documentation
- **[ENTERPRISE_MESH_GUIDE.md](ENTERPRISE_MESH_GUIDE.md)** - Enterprise networks & mesh topology guide
- **[ARCH_LINUX_GUIDE.md](ARCH_LINUX_GUIDE.md)** - Comprehensive Arch Linux setup guide
- **[PENTEST_FIX_SUMMARY.md](PENTEST_FIX_SUMMARY.md)** - Technical details of pentest fixes
- **[CHANGES_COMPARISON.md](CHANGES_COMPARISON.md)** - Before/after comparison
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick reference card
- **[CHANGELOG](CHANGELOG)** - Version history

## Disclaimer

**Legal Notice:** This tool is intended for authorized security testing and network administration only.

Evil Limiter is provided "as is" and "with all faults". The authors and contributors make no representations or warranties of any kind concerning the safety, suitability, or reliability of this software. There are inherent dangers in the use of any network security tool, and you are solely responsible for:

- Ensuring you have proper authorization to use this tool
- Determining compatibility with your equipment and network
- Protection of your equipment and backup of your data
- Compliance with all applicable laws and regulations

**Unauthorized use of this tool may be illegal.** ARP spoofing and traffic manipulation without permission may violate:
- Computer Fraud and Abuse Act (CFAA) in the US
- Computer Misuse Act in the UK  
- Similar laws in other jurisdictions

Use only on networks you own or have explicit written permission to test.

## Contributors

Special thanks to:
- **[bitbrute](https://github.com/bitbrute/)** - Original author and creator
- **[Masrkai](https://github.com/Masrkai/)** - Revival and nftables migration
- **[Vanszs](https://github.com/Vanszs/)** - Enterprise/mesh optimization, pentest stability, and Arch Linux support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes:
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Support

- **Issues:** [GitHub Issues](https://github.com/Vanszs/Evillimiter/issues)
- **Discussions:** [GitHub Discussions](https://github.com/Vanszs/Evillimiter/discussions)

## License

Copyright (c) 2025 by the contributors. Some rights reserved.<br>
Evil Limiter is licensed under the MIT License as stated in the [LICENSE file](LICENSE).

Original work by [bitbrute](https://github.com/bitbrute/)<br>
Enhanced and maintained by [Vanszs](https://github.com/Vanszs/) and contributors.