#!/usr/bin/env bash
# fix_ifb.sh - Auto Wi-Fi traffic redirect (for Evillimiter on noqueue interfaces)
# by Vanszs & GPT-5

set -e

echo "=== [IFB Fix Utility for Evillimiter] ==="
IFACE=${1:-wlan0}
IFB=ifb0

echo "[+] Checking kernel version..."
KERNEL=$(uname -r)
echo "    Kernel: $KERNEL"

# 1. Check if module path exists
if [[ ! -d "/lib/modules/$KERNEL" ]]; then
  echo "[!] /lib/modules/$KERNEL not found."
  echo "    This means kernel modules are missing for current kernel."
  echo "    Recommended fix: reinstall linux-lts + headers."
  echo "    Run:"
  echo "      sudo pacman -S --needed linux-lts linux-lts-headers"
  echo "      sudo mkinitcpio -P && sudo reboot"
  exit 1
fi

# 2. Try load IFB
echo "[+] Checking IFB kernel module..."
if ! sudo modprobe ifb 2>/dev/null; then
  echo "[!] Failed to load ifb module."
  echo "    Searching module file..."
  if ! find "/lib/modules/$KERNEL" -type f -name 'ifb.ko*' | grep -q ifb; then
    echo "❌ IFB module not found in kernel $KERNEL"
    echo "💡 Please reinstall your kernel with headers:"
    echo "    sudo pacman -S --needed linux-lts linux-lts-headers"
    echo "    sudo mkinitcpio -P && sudo reboot"
    exit 1
  fi
else
  echo "✅ ifb module loaded successfully."
fi

# 3. Create IFB interface
echo "[+] Setting up IFB virtual interface..."
sudo ip link del $IFB 2>/dev/null || true
sudo ip link add $IFB type ifb || {
  echo "❌ Failed to create IFB device."
  exit 1
}
sudo ip link set $IFB up

# 4. Add qdisc to IFB
echo "[+] Adding qdisc root to $IFB ..."
sudo tc qdisc del dev $IFB root 2>/dev/null || true
sudo tc qdisc add dev $IFB root handle 1: htb default 12 || {
  echo "❌ Failed to add root qdisc on $IFB"
  exit 1
}

# 5. Add ingress on original interface & redirect
echo "[+] Redirecting ingress from $IFACE → $IFB ..."
sudo tc qdisc del dev $IFACE ingress 2>/dev/null || true
sudo tc qdisc add dev $IFACE ingress 2>/dev/null || true
sudo tc filter add dev $IFACE parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev $IFB || {
  echo "❌ Failed to set tc filter redirect."
  exit 1
}

# 6. Display current qdiscs
echo "[+] Current TC status:"
sudo tc qdisc show dev $IFACE
sudo tc qdisc show dev $IFB

echo ""
echo "✅ IFB redirect configured successfully!"
echo "Now you can run Evillimiter with:"
echo "   sudo ./evillimiter --interface $IFB"
echo ""
echo "⚙️  To clean up later:"
echo "   sudo tc qdisc del dev $IFACE ingress || true"
echo "   sudo tc qdisc del dev $IFB root || true"
echo "   sudo ip link del $IFB || true"
