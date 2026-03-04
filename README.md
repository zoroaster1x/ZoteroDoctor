# ZoteroDoctor

ZoteroDoctor is a Linux utility designed to fix integration issues between the Zotero Flatpak and LibreOffice. It addresses the common problem where the Zotero Flatpak cannot automatically install the required `.oxt` extension into the host system's LibreOffice installation.

Additionally, it provides fixes for common Zotero Flatpak stability issues, specifically Wayland crashes and interface scaling problems on high-DPI displays.

## Features

*   **LibreOffice Integration:** Locates the `Zotero_LibreOffice_Integration.oxt` file hidden inside the Flatpak container (handling version-specific hash paths) and installs it into the host LibreOffice instance.
*   **Dependency Management:** Automatically checks for and installs required Java dependencies (`libreoffice-java-common`, `default-jre`) necessary for the plugin to function.
*   **Crash Prevention:** Applies Flatpak overrides to bypass Wayland socket issues that cause Zotero to crash when opening the citation picker.
*   **UI Scaling Fix:** Forces the interface scaling factor to 1.0 to prevent the application from appearing too large on GNOME/Wayland setups.

## Prerequisites

*   Python 3.6+
*   Root privileges (required to install system dependencies and modify Flatpak overrides).
*   Zotero (installed via Flatpak).
*   LibreOffice.

## Installation

Clone this repository or download the script directly.

```bash
git clone https://github.com/zoroaster1x/ZoteroDoctor.git
cd ZoteroDoctor
chmod +x zotero_doctor.py
```

## Usage

You can run the script interactively or via command-line arguments for automated setups.

### Interactive Mode

Running the script without arguments launches the interactive menu.

```bash
sudo ./zotero_doctor.py
```

### Command Line / Programmatic Mode

The script supports flags for automated deployment or specific repairs.

**Install the LibreOffice Plugin only:**
```bash
sudo ./zotero_doctor.py --action plugin
```

**Apply all fixes (Plugin, Wayland crash fix, UI scaling):**
```bash
sudo ./zotero_doctor.py --action all
```

**Specify a custom Flatpak ID (if using a fork or beta):**
```bash
sudo ./zotero_doctor.py --action plugin --flatpak-id org.zotero.ZoteroBeta
```

**Manually specify the location of the .oxt file:**
If the script cannot locate the extension automatically, you can provide the path explicitly.
```bash
sudo ./zotero_doctor.py --action plugin --oxt-path /path/to/Zotero_Integration.oxt
```

## Troubleshooting

**"javaloader error" in LibreOffice:**
If you see a Java error after installation, ensure you have a Java Runtime Environment (JRE) installed and selected in LibreOffice:
1. Open LibreOffice Writer.
2. Go to **Tools > Options > LibreOffice > Advanced**.
3. Ensure "Use a Java runtime environment" is checked and a vendor (e.g., Oracle, OpenJDK) is selected in the list.

**Script cannot find the user:**
This script relies on `SUDO_USER` to identify the non-root account. If you are running this in a chroot or a clean environment where `SUDO_USER` is not set, specify the target user manually:

```bash
sudo ./zotero_doctor.py --action all --target-user myusername
```

## License
MIT License
