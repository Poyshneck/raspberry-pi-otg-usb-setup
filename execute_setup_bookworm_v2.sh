#! /bin/sh

#######################################################################
# Script: Raspberry Pi OTG USB Configuration and Service Setup
# Version: 2
# Original Author: Koseng
# Edited by: Poyshneck
# Date: 2025-05-06 (YYYY-MM-DD)
# Description: This script configures the Raspberry Pi for OTG USB mode
# Changelog:
# - Comment out 'otg_mode=1' if present and uncommented to avoid conflicts. (Reason: Prevent conflict with dwc2 overlay.)
# - Added check to prevent overwriting existing /piusb.bin image file. (Reason: Avoid data loss.)
# - Added 'status=progress' to dd command for progress visibility. (Reason: Provide real-time operation feedback.)
# - Added error handling for losetup failure. (Reason: Avoid silent failures if loop device can't be created.)
# - Ensured exfatprogs installed before formatting. (Reason: mkfs.exfat not always pre-installed.)
# - Fallback to pip3 install for dropbox module if not available via apt. (Reason: Compatibility with newer OS versions.)
# - Added checks for existence of service files with feedback if missing. (Reason: Prevent silent failures during service setup.)
#######################################################################

echo "-----------------------------------------------------------------"
echo "Create configuration for loading OTG USB drivers on boot"
echo "-----------------------------------------------------------------"

# Version 2 Change:
# Reason: Ensure any existing 'otg_mode=1' line is commented out to avoid conflicts with dwc2 overlay.
sudo sed -i 's/^\(otg_mode=1\)/#\1/' /boot/firmware/config.txt

# Ensure dtoverlay=dwc2 is present
sudo grep -qxF 'dtoverlay=dwc2' /boot/firmware/config.txt || \
  echo 'dtoverlay=dwc2' | sudo tee -a /boot/firmware/config.txt

# Ensure dwc2 is in /etc/modules
sudo grep -qxF 'dwc2' /etc/modules || echo 'dwc2' | sudo tee -a /etc/modules

echo "Done"

echo "-----------------------------------------------------------------"
echo "Create the 3GB USB share"
echo "-----------------------------------------------------------------"

# Version 2 Change:
# Reason: Prevent accidental overwrite of an existing piusb.bin image file, which could cause data loss.
if [ -f "/piusb.bin" ]; then
  echo "/piusb.bin already exists. Exiting to avoid overwrite."
  exit 1
fi

echo "Create the 3GB USB image file - BE PATIENT FOR SEVERAL MINUTES"
# Version 2 Change:
# Reason: Added 'status=progress' to dd command for real-time feedback on operation progress.
sudo dd bs=1M if=/dev/zero of=/piusb.bin count=3072 status=progress

echo 'type=07' | sudo sfdisk /piusb.bin

# Version 2 Change:
# Reason: Added error handling to check if losetup succeeded in creating a loop device.
if ! loopd=$(sudo losetup --partscan --show --find /piusb.bin); then
  echo "Failed to set up loop device."
  exit 1
fi

# Version 2 Change:
# Reason: Ensure exFAT formatting utility is installed before attempting to format the image partition.
sudo apt-get update
sudo apt-get -y install exfatprogs

# Format partition with exFAT
sudo mkfs.exfat -L Raspi "${loopd}p1"

sudo mkdir -p /mnt/usb_share

echo "-----------------------------------------------------------------"
echo "Prepare Python copy and upload services"
echo "-----------------------------------------------------------------"

sudo apt-get -y install expect

# Version 2 Change:
# Reason: In newer Raspberry Pi OS versions, 'python3-dropbox' may be unavailable via apt.
# Fallback to pip3 installation ensures continued compatibility.
if ! dpkg -s python3-dropbox >/dev/null 2>&1; then
  sudo apt-get -y install python3-pip
  sudo pip3 install dropbox
fi

echo "-----------------------------------------------------------------"
echo "Add system services"
echo "-----------------------------------------------------------------"

# Version 2 Change:
# Reason: Added existence check for service files and appropriate feedback if missing.
# Prevents silent failures and improves script diagnostics.
for service in usb-storage.service usb-copy.service usb-upload.service; do
  if [ -f "/home/pi/$service" ]; then
    sudo mv "/home/pi/$service" /etc/systemd/system/
    sudo chmod 644 "/etc/systemd/system/$service"
    sudo systemctl enable "$service"
  else
    echo "$service not found!"
  fi
done

echo "-----------------------------------------------------------------"
echo "Setup complete."
echo "-----------------------------------------------------------------"
