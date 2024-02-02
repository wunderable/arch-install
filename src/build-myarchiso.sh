#!/bin/bash

# Script will create a bootable ISO containing a few custom scripts

# Ensure root permissions
if [[ $EUID -ne 0 ]]; then
  echo "Permission denied"
  exit
fi

# Ensure archiso is up-to-date
pacman -Syy
pacman --noconfirm -S archiso

# Start with baseline config
cp -r /usr/share/archiso/configs/baseline /tmp/iso

# Add additional packages
echo -e 'btrfs-progs\niwc\nvim' >> /tmp/iso/packages.x86_64

# Enable autologin
mkdir -p /tmp/iso/airootfs/etc/systemd/system/getty@tty1.service.d
cp /usr/share/archiso/configs/releng/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf /tmp/iso/airootfs/etc/systemd/system/getty@tty1.service.d

# Include our own scripts
mkdir -p /tmp/iso/airootfs/usr/local/bin
cp /usr/local/src/iso-cmds.sh /tmp/iso/airootfs/usr/local/bin/cmds
cp /usr/local/src/iso-mfs.sh /tmp/iso/airootfs/usr/local/bin/mfs

# Set permissions for our scripts (I should turn this into a loop)
sed -i '/^file_permissions=(/a \ \ ["/usr/local/bin/cmds"]="0:0:755"' /tmp/iso/profiledef.sh
sed -i '/^file_permissions=(/a \ \ ["/usr/local/bin/mfs"]="0:0:755"' /tmp/iso/profiledef.sh

# Allow ISO to be mounted via loop
sed -i 's/archiso/archiso archiso_loop_mnt/' /tmp/iso/airootfs/etc/mkinitcpio.conf.d/archiso.conf

# Create the ISO
mkarchiso -v -w /tmp/iso -o /tmp/out /tmp/iso

# Cleanup of files
rm -rf /tmp/iso
[ ! -e /boot/iso/myarch.iso ] || rm /boot/iso/myarch.iso
mkdir -p /boot/iso
mv /tmp/out/archlinux-*.iso /boot/iso/myarch.iso
rmdir /tmp/out
