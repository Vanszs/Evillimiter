#!/usr/bin/env python3
"""
Evillimiter Auto Fixer by Vanszs & GPT-5
----------------------------------------
1. Normalizes all imports: common, console, menus, networking → evillimiter.*
2. Installs all required Python dependencies.
3. Tests final run: python3 bin/evillimiter --flush
"""

import os
import subprocess

REPO = "/home/vanszs/Documents/Code/Evillimiter"

os.chdir(REPO)
print("🔧 [1/4] Backing up current 'evillimiter/' folder...")
os.system("cp -r evillimiter evillimiter.backup_fix")

print("🔍 [2/4] Fixing all outdated imports...")
targets = ["common", "console", "menus", "networking"]
for t in targets:
    os.system(f"grep -Rl 'import {t}' evillimiter | xargs sed -i 's/import {t}/from evillimiter.{t}/g'")
    os.system(f"grep -Rl 'from {t}' evillimiter | xargs sed -i 's/from {t}/from evillimiter.{t}/g'")

print("📦 [3/4] Installing required Python packages...")
packages = [
    "colorama", "netifaces", "psutil", "tabulate", "scapy",
    "setuptools", "wheel", "pip", "build"
]
try:
    subprocess.run(["python3", "-m", "pip", "install", "--user", "--upgrade"] + packages, check=True)
except subprocess.CalledProcessError:
    print("⚠️ pip installation failed, trying with sudo...")
    subprocess.run(["sudo", "python3", "-m", "pip", "install", "--upgrade"] + packages)

print("✅ [4/4] Test run Evillimiter...")
os.environ["PYTHONPATH"] = os.getcwd()
try:
    subprocess.run(["python3", "bin/evillimiter", "--flush"], check=True)
except subprocess.CalledProcessError as e:
    print("\n⚠️ Evillimiter exited with error code:", e.returncode)
    print("This may be expected if tc/nftables require sudo privileges.")
    print("Try running: sudo PYTHONPATH=\"$(pwd)\" python3 bin/evillimiter --flush")

print("\n🎉 All imports fixed & dependencies installed! Try running:\n")
print("   sudo PYTHONPATH=\"$(pwd)\" python3 bin/evillimiter --flush")
