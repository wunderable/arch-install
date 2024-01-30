#!/bin/bash

# Script will create a bootable ISO containing a few custom scripts

if [[ $EUID -ne 0 ]]; then
  echo "Permission denied"
  exit
fi

pacman -Syy
pacman --noconfirm -S archiso

cp -r /usr/share/archiso/configs/releng /tmp/iso
mkdir -p /tmp/iso/airootfs/usr/local/bin
mkdir -p /boot/iso
echo -e 'btrfs-progs\nintel-ucode\niwc\nvim' >> /tmp/iso/packages.x86_64
cp /usr/local/src/iso-cmds.sh /tmp/iso/airootfs/usr/local/bin/cmds
sed -i '/^file_permissions=(/a \ \ ["/usr/local/bin/cmds"]="0:0:755"' /tmp/iso/profiledef.sh
mkdir -p /boot/iso
mkarchiso -v -w /tmp/iso -o /tmp/out /tmp/iso

rm -rf /tmp/iso
[ ! -e /boot/iso/myarch.iso ] || rm /boot/iso/myarch.iso
mv /tmp/out/archlinux-*.iso /boot/iso/myarch.iso
rmdir /tmp/out
