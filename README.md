<p align="center"><img src="/evillimiter/image.png" /></p>

# Evil Limiter, Originally developed by [bitbrute](https://github.com/bitbrute/) brought back to life by [Masrkai](https://github.com/Masrkai/) 

[![License Badge](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Compatibility](https://img.shields.io/badge/python-3-brightgreen.svg)](PROJECT)
<!-- [![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/Naereen/StrapDown.js/graphs/commit-activity) -->
[![Open Source Love](https://badges.frapsoft.com/os/v3/open-source.svg?v=102)](https://github.com/ellerbrock/open-source-badge/)

A tool to monitor, analyze and limit the bandwidth (upload/download) of devices on your local network without physical or administrative access.<br>
```evillimiter``` employs [ARP spoofing](https://en.wikipedia.org/wiki/ARP_spoofing) and [traffic shaping](https://en.wikipedia.org/wiki/Traffic_shaping) to throttle the bandwidth of hosts on the network.

## Nix / NixOS ?
I packaged it for my system, as this is a fork that doesn't have a specific name "YET" I didn't request merging it into the [Nixpkgs](https://github.com/NixOS/nixpkgs)

you can find the configuration here (it will take you there directly): [Evillimiter.nix](https://github.com/Masrkai/Nix_Configuration/blob/main/Programs/Packages/evillimiter.nix)

## Recent Improvements (November 2025)

### Pentest Stability Fixes
This fork includes significant stability improvements for penetration testing environments:

**Fixed Issues:**
- ✅ Eliminated `TimeoutError` spam during network scanning
- ✅ Resolved gateway MAC address resolution failures
- ✅ Added retry mechanisms for unreliable networks
- ✅ Improved error handling for busy/monitored networks
- ✅ Suppressed verbose scapy output

**Technical Improvements:**
- Reduced batch size (75→50 IPs) for better reliability
- Increased timeout (3→5 seconds) for stability
- Added inter-batch delays (100ms) to prevent network flooding
- Implemented 3-retry mechanism for gateway MAC resolution
- Enhanced error suppression for cleaner console output
- Added graceful degradation for hostname resolution failures

**Performance Characteristics:**
- ~10-15% slower scanning (trade-off for reliability)
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
- Linux distribution (Tested on Arch Linux, Debian, Ubuntu, NixOS)
- Python 3 or greater
- Root/sudo privileges

Possibly missing python packages will be installed during the installation process.

## Installation

### Arch Linux / Manjaro
```bash
# Install dependencies
sudo pacman -S python python-setuptools python-pip nftables iproute2

# Clone and install
git clone https://github.com/Masrkai/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install
```

### Debian / Ubuntu / Kali Linux
```bash
# Install dependencies
sudo apt update
sudo apt install python3-setuptools python3-netifaces python3-pip nftables iproute2

# Clone and install
git clone https://github.com/Masrkai/Evillimiter.git
cd Evillimiter
sudo python3 setup.py install
```

### NixOS
I packaged it for my system, as this is a fork that doesn't have a specific name "YET" I didn't request merging it into the [Nixpkgs](https://github.com/NixOS/nixpkgs)

you can find the configuration here (it will take you there directly): [Evillimiter.nix](https://github.com/Masrkai/Nix_Configuration/blob/main/Programs/Packages/evillimiter.nix)

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
# Run the test script
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

## Disclaimer
[Evil Limiter](https://github.com/Masrkai/Evillimiter) is provided by [Masrkai](https://github.com/Masrkai) "as is" and "with all faults". The provider makes no representations or warranties of any kind concerning the safety, suitability, lack of viruses, inaccuracies, typographical errors, or other harmful components of this software. There are inherent dangers in the use of any software, and you are solely responsible for determining whether Evil Limiter is compatible with your equipment and other software installed on your equipment. You are also solely responsible for the protection of your equipment and backup of your data, and the provider will not be liable for any damages you may suffer in connection with using, modifying, or distributing this software.

## Contributors

Special thanks to:
- **[bitbrute](https://github.com/bitbrute/)** - Original author and creator
- **[Masrkai](https://github.com/Masrkai/)** - Revival, nftables migration, and active maintenance
- **[Vanszs](https://github.com/Vanszs/)** - Pentest stability fixes and Arch Linux testing

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for more details.

## Changelog

For detailed changes and version history, see [CHANGELOG](CHANGELOG).

## License

Copyright (c) 2025 by [Masrkai](https://github.com/Masrkai). Some rights reserved.<br>
[Evil Limiter](https://github.com/Masrkai/evillimiter) is licensed under the MIT License as stated in the [LICENSE file](LICENSE).