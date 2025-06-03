#!/bin/bash

# Script will create a bootable ISO containing a few custom scripts to make managing btrfs easier

# Ensure root permissions
if [[ $EUID -ne 0 ]]; then
  echo "Permission denied"
  exit
fi

# Ensure archiso is up-to-date
pacman -Syy
pacman --noconfirm -S archiso

# Start with baseline config
cp -r /usr/share/archiso/configs/baseline /tmp
mv /tmp/baseline /tmp/iso

# Add additional packages
echo -e 'git\nbtrfs-progs\niwd\nvim' >> /tmp/iso/packages.x86_64

# Enable autologin
mkdir -p /tmp/iso/airootfs/etc/systemd/system/getty@tty1.service.d
cp /usr/share/archiso/configs/releng/airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf /tmp/iso/airootfs/etc/systemd/system/getty@tty1.service.d

# Set hostname
echo 'archiso' > /tmp/iso/airootfs/etc/hostname

# Add kernel parameters
#sed -i '/^\s*linux\s/s/$/ quiet loglevel=3/' /tmp/iso/airootfs/grub/grub.cfg

# Setup bash
mkdir -p /tmp/iso/airootfs/etc/profile.d
cp /etc/profile.d/aliases.sh /tmp/iso/airootfs/etc/profile.d
cp /etc/profile.d/prompt.sh /tmp/iso/airootfs/etc/profile.d
cp /etc/bash.bashrc /tmp/iso/airootfs/etc

# Include our scripts
mkdir -p /tmp/iso/airootfs/usr/local/bin
cp /usr/local/src/iso-cmds.sh /tmp/iso/airootfs/usr/local/bin/cmds
cp /usr/local/src/iso-mfs.sh /tmp/iso/airootfs/usr/local/bin/mfs
cp /usr/local/src/subv.py /tmp/iso/airootfs/usr/local/bin/subv
cp /usr/local/src/s.sh /tmp/iso/airootfs/usr/local/bin/s

# Set permissions for our scripts
for CMD in /tmp/iso/airootfs/usr/local/bin/*; do
  CMD=$(basename -- "$CMD")
  sed -i '/^file_permissions=(/a \ \ ["/usr/local/bin/'$CMD'"]="0:0:755"' /tmp/iso/profiledef.sh
done

# Settings for subv
tee /tmp/iso/airootfs/etc/subv.conf <<-END
	[settings]
	default_path = /mnt
	snapshot_dest = /mnt/snapshots

	[locations]
	root = /mnt/@root
	home = /mnt/@home
END

# Allow ISO to be mounted via loop
sed -i 's/archiso/archiso archiso_loop_mnt/' /tmp/iso/airootfs/etc/mkinitcpio.conf.d/archiso.conf

# Use squashfs instead of default erofs (because it's currently faster)
sed -i 's/erofs/squashfs/' /tmp/iso/profiledef.sh
sed -i '/image_tool/c\airootfs_image_tool_options=(-comp xz -b 256k -no-exports -no-xattrs)' /tmp/iso/profiledef.sh

# Create the ISO
mkdir /tmp/out
mkarchiso -v -w /tmp/iso -o /tmp/out /tmp/iso

# Cleanup of files
rm -rf /tmp/iso
[ ! -e /boot/iso/archiso.iso ] || rm /boot/iso/archiso.iso
mkdir -p /boot/iso
mv /tmp/out/archlinux-*.iso /boot/iso/archiso.iso
rmdir /tmp/out
mkdir -p /mnt/iso
mount -o loop /boot/iso/archiso.iso /mnt/iso
cp /mnt/iso/arch/boot/x86_64/vmlinuz-linux.img /boot/iso
cp /mnt/iso/arch/boot/x86_64/initramfs-linux.img /boot/iso
umount /mnt/iso
rmdir /mnt/iso
