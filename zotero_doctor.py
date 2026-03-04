#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import glob
import time
import argparse
from pathlib import Path

# --- Configuration & Constants ---
DEFAULT_FLATPAK_ID = "org.zotero.Zotero"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class ZoteroDoctor:
    def __init__(self, args):
        self.args = args
        self.flatpak_id = args.flatpak_id
        
        # Determine the real user (non-root)
        if args.target_user:
            self.real_user = args.target_user
        else:
            self.real_user = os.environ.get('SUDO_USER') or os.environ.get('USER')

        if self.real_user == "root":
            print(f"{Colors.RED}Error: Running as root without a detected SUDO_USER.{Colors.ENDC}")
            print("Please run via 'sudo ./zotero_doctor.py' or use '--target-user <username>'")
            sys.exit(1)

        # Get user home directory safely
        try:
            self.user_home = Path(subprocess.check_output(f"eval echo ~{self.real_user}", shell=True).decode().strip())
        except subprocess.CalledProcessError:
            print(f"{Colors.RED}Error: Could not determine home directory for user {self.real_user}.{Colors.ENDC}")
            sys.exit(1)

    def print_status(self, msg, status="info"):
        if status == "info":
            print(f"{Colors.BLUE}==>{Colors.ENDC} {msg}")
        elif status == "success":
            print(f"{Colors.GREEN}✔ {msg}{Colors.ENDC}")
        elif status == "error":
            print(f"{Colors.RED}✖ {msg}{Colors.ENDC}")
        elif status == "warn":
            print(f"{Colors.YELLOW}⚠ {msg}{Colors.ENDC}")

    def run_as_user(self, cmd_list):
        """Runs a command as the non-root user."""
        full_cmd = ["sudo", "-u", self.real_user] + cmd_list
        return subprocess.run(full_cmd, capture_output=True, text=True)

    def check_system_deps(self):
        """Checks and installs OS-level dependencies for LibreOffice Java integration."""
        self.print_status("Checking system dependencies...")
        
        distro = ""
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                data = f.read().lower()
                if "fedora" in data: distro = "fedora"
                elif "debian" in data or "ubuntu" in data or "mint" in data: distro = "debian"
                elif "arch" in data: distro = "arch"

        # Define packages based on distro
        cmd = []
        pkgs = []
        
        if distro == "fedora":
            cmd = ["dnf", "install", "-y"]
            pkgs = ["libreoffice-java-common", "java-latest-openjdk", "libreoffice-core"]
        elif distro == "debian":
            cmd = ["apt-get", "install", "-y"]
            pkgs = ["libreoffice-java-common", "default-jre", "libreoffice-core"]
        elif distro == "arch":
            cmd = ["pacman", "-S", "--noconfirm"]
            pkgs = ["libreoffice-fresh", "jre-openjdk"]
        
        if cmd and pkgs:
            try:
                subprocess.run(cmd + pkgs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.print_status("Dependencies verified.", "success")
            except Exception as e:
                self.print_status(f"Failed to install dependencies: {e}", "error")
        else:
            self.print_status("Could not detect distro or distro not supported. Skipping dependency check.", "warn")

    def find_oxt(self):
        """Locates the .oxt file."""
        # 1. Use explicit path if provided
        if self.args.oxt_path:
            p = Path(self.args.oxt_path)
            if p.exists():
                return p
            else:
                self.print_status(f"Custom path not found: {p}", "error")
                return None

        # 2. Search Flatpak locations
        self.print_status("Searching for Zotero_LibreOffice_Integration.oxt...")
        
        search_roots = [
            Path(f"/var/lib/flatpak/app/{self.flatpak_id}"),
            self.user_home / f".local/share/flatpak/app/{self.flatpak_id}"
        ]

        # Add custom flatpak directory if provided
        if self.args.flatpak_dir:
            search_roots.insert(0, Path(self.args.flatpak_dir))

        for root in search_roots:
            if root.exists():
                # Recursive search for the file
                candidates = list(root.rglob("Zotero_LibreOffice_Integration.oxt"))
                if candidates:
                    return candidates[0]
        
        return None

    def install_plugin(self):
        """Orchestrates the plugin installation."""
        self.check_system_deps()
        
        oxt_path = self.find_oxt()
        if not oxt_path:
            self.print_status("Could not locate the .oxt extension file. Is Zotero installed?", "error")
            return

        self.print_status(f"Found extension: {oxt_path}")

        # Check for running LibreOffice instances
        try:
            pgrep = subprocess.run(["pgrep", "-f", "soffice.bin"], capture_output=True)
            if pgrep.returncode == 0:
                if self.args.force or self.args.action != 'interactive':
                    self.print_status("Closing LibreOffice to perform installation...", "warn")
                    subprocess.run(["pkill", "-9", "-f", "soffice.bin"])
                    time.sleep(2)
                else:
                    self.print_status("LibreOffice is running.", "warn")
                    choice = input("Close LibreOffice now? (y/n): ")
                    if choice.lower().startswith('y'):
                        subprocess.run(["pkill", "-9", "-f", "soffice.bin"])
                        time.sleep(2)
                    else:
                        self.print_status("Aborted by user.", "error")
                        return
        except Exception:
            pass

        self.print_status(f"Installing extension for user: {self.real_user}")
        
        # Execute unopkg as the target user
        result = self.run_as_user([
            "unopkg", "add", "--force", "--suppress-license", str(oxt_path)
        ])

        if result.returncode == 0:
            self.print_status("LibreOffice extension installed successfully.", "success")
        else:
            self.print_status("Installation failed.", "error")
            print(result.stderr)

    def fix_wayland_crashes(self):
        """Applies Flatpak overrides to fix Wayland crashes."""
        self.print_status("Applying Wayland/Seccomp crash fixes...")
        
        overrides = [
            ["--nosocket=wayland"],
            ["--socket=x11"],
            ["--env=GDK_BACKEND=x11"]
        ]
        
        for flags in overrides:
            cmd = ["flatpak", "override", "--user"] + flags + [self.flatpak_id]
            self.run_as_user(cmd)
            
        self.print_status("Crash fixes applied.", "success")

    def fix_ui_scaling(self):
        """Fixes UI scaling issues in prefs.js and Flatpak env."""
        self.print_status("Applying UI scaling fixes (Force 1.0)...")
        
        # 1. Flatpak Environment
        self.run_as_user(["flatpak", "override", "--user", "--env=GDK_SCALE=1", self.flatpak_id])
        
        # 2. Internal prefs.js
        # Locate profile directory
        data_path = self.user_home / f".var/app/{self.flatpak_id}/data/zotero/zotero"
        if not data_path.exists():
            self.print_status("Zotero data directory not found. Run Zotero once to generate it.", "warn")
            return

        profile_dir = next(data_path.glob("*.default*"), None)
        if not profile_dir:
            self.print_status("No default profile found in Zotero data directory.", "warn")
            return

        prefs_file = profile_dir / "prefs.js"
        
        try:
            with open(prefs_file, "r") as f:
                lines = f.readlines()
            
            # Remove existing key
            lines = [l for l in lines if "layout.css.devPixelsPerPx" not in l]
            # Add new key
            lines.append('user_pref("layout.css.devPixelsPerPx", "1.0");\n')
            
            with open(prefs_file, "w") as f:
                f.writelines(lines)
                
            # Restore ownership to user (since script runs as root)
            subprocess.run(["chown", f"{self.real_user}:{self.real_user}", str(prefs_file)])
            
            self.print_status("Internal scaling preference updated.", "success")
        except Exception as e:
            self.print_status(f"Failed to edit prefs.js: {e}", "error")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="ZoteroDoctor: Fix Zotero Flatpak integration and stability issues."
    )
    
    parser.add_argument(
        "--action", 
        choices=["interactive", "plugin", "wayland", "scaling", "all"], 
        default="interactive",
        help="The specific action to perform. Default is interactive menu."
    )
    
    parser.add_argument(
        "--flatpak-id", 
        default=DEFAULT_FLATPAK_ID,
        help=f"The Flatpak Application ID (default: {DEFAULT_FLATPAK_ID})"
    )
    
    parser.add_argument(
        "--oxt-path", 
        help="Manually specify the path to 'Zotero_LibreOffice_Integration.oxt'"
    )
    
    parser.add_argument(
        "--flatpak-dir", 
        help="Custom directory to search for Flatpak data if installed in a non-standard location."
    )
    
    parser.add_argument(
        "--target-user", 
        help="Manually specify the non-root user (if SUDO_USER cannot be detected)."
    )
    
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force actions (e.g., kill LibreOffice without prompting) during programmatic runs."
    )

    return parser.parse_args()

def interactive_menu(doctor):
    while True:
        print(f"\n{Colors.BOLD}--- ZoteroDoctor Menu ---{Colors.ENDC}")
        print("1. Install LibreOffice Plugin")
        print("2. Fix Wayland Crashes")
        print("3. Fix UI Scaling")
        print("4. Apply All Fixes")
        print("5. Exit")
        
        try:
            choice = input(f"{Colors.BLUE}Select option [1-5]: {Colors.ENDC}")
            if choice == '1':
                doctor.install_plugin()
            elif choice == '2':
                doctor.fix_wayland_crashes()
            elif choice == '3':
                doctor.fix_ui_scaling()
            elif choice == '4':
                doctor.fix_wayland_crashes()
                doctor.fix_ui_scaling()
                doctor.install_plugin()
            elif choice == '5':
                sys.exit(0)
            else:
                print("Invalid selection.")
        except KeyboardInterrupt:
            sys.exit(0)

def main():
    if os.geteuid() != 0:
        print(f"{Colors.RED}This script requires root privileges for system modifications.{Colors.ENDC}")
        print("Please run with: sudo ./zotero_doctor.py")
        sys.exit(1)

    args = parse_arguments()
    doctor = ZoteroDoctor(args)

    if args.action == "interactive":
        interactive_menu(doctor)
    else:
        # Programmatic execution
        if args.action in ["plugin", "all"]:
            doctor.install_plugin()
        if args.action in ["wayland", "all"]:
            doctor.fix_wayland_crashes()
        if args.action in ["scaling", "all"]:
            doctor.fix_ui_scaling()

if __name__ == "__main__":
    main()
