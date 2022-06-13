#!/bin/sh

if [[ $EUID -ne 0 ]]; then
  echo "Permission denied"
  exit
fi
curl https://mirrors.edge.kernel.org/archlinux/iso/latest/archlinux-x86_64.iso -o /boot/iso/archlinux-x86_64.iso
