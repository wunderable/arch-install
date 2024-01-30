#!/bin/bash

# Script will create a bootable ISO containing a few custom scripts

if [[ $EUID -ne 0 ]]; then
  echo "Permission denied"
  exit
fi

# We used to just download the latest ISO from a mirror
#mkdir -p /boot/iso
#curl https://mirrors.edge.kernel.org/archlinux/iso/latest/archlinux-x86_64.iso -o /boot/iso/myarch.iso

cp -r /usr/share/archiso/configs/releng /tmp/iso
cp /usr/local/src/iso-cmds.sh /tmp/iso/airootfs/usr/local/bin/cmds
sed -i '/^file_permissions=(/a \ \ ["/usr/local/bin/cmds"]="0:0:755"' /tmp/iso/profiledef.sh
mkdir -p /boot/iso
mkarchiso -v -w /tmp/iso -o /boot/iso/myarch.iso /tmp/iso
