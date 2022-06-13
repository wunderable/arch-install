#!/bin/sh

# Get base directory of this project
DIR="$( cd "../$( dirname "$0" )" && pwd )"

# Create partitions
sgdisk --clear /dev/nvme0n1
#badblocks -wsv -t random /dev/nvme0n1
sgdisk -n 1:0:+1280M -t 1:ef00 /dev/nvme0n1
sgdisk -N 2 /dev/nvme0n1

# Format partitions
mkfs.fat -F32 -n BOOT /dev/nvme0n1p1
cryptsetup --label CRYPT luksFormat /dev/nvme0n1p2
cryptsetup open /dev/nvme0n1p2 root
mkfs.btrfs -L ROOT /dev/mapper/root

# Create subvolumes
mount /dev/mapper/root /mnt
btrfs sub create /mnt/@
btrfs sub create /mnt/@home
btrfs sub create /mnt/@/.snapshots
btrfs sub create /mnt/@home/.snapshots
mkdir -p /mnt/@/var/cache/pacman
mkdir -p /mnt/@home/dan
btrfs sub create /mnt/@/var/cache/pacman/pkg
btrfs sub create /mnt/@/var/log
btrfs sub create /mnt/@/var/tmp
btrfs sub create /mnt/@home/dan/.cache
umount /mnt

# Mount partitions
mount -o noatime,compress=zstd,space_cache=v2,discard=async,ssd,subvol=@ /dev/mapper/root /mnt
mkdir /mnt/home
mount -o noatime,compress=zstd,space_cache=v2,discard=async,ssd,subvol=@home /dev/mapper/root /mnt/home
mkdir /mnt/boot
mount /dev/nvme0n1p1 /mnt/boot

# Install packages
pacstrap /mnt base linux linux-firmware intel-ucode btrfs-progs networkmanager vim man-db man-pages base-devel git grub efibootmgr

# Generate fstab file
genfstab -U /mnt >> /mnt/etc/fstab

# Copy files from github to installed OS
cp $DIR/profile.d/aliases.sh /mnt/etc/profile.d/aliases.sh

# Create file to be run in arch-chrooted environment
tee /mnt/install.sh <<"EOF"
#!/bin/sh

# Update hooks
tee /etc/mkinitcpio.conf <<-"END"
	MODULES=(vmd)
	BINARIES=(/usr/bin/btrfs)
	FILES=()
	HOOKS=(base udev autodetect keyboard consolefont modconf block encrypt btrfs filesystems fsck)
	END
mkinitcpio -p linux

# Install grub
awk -vFPAT='([^=]*)|("[^"]+")' -vOFS== -vID="$(blkid -s UUID -o value /dev/nvme0n1p2)" '{if($1=="GRUB_CMDLINE_LINUX_DEFAULT") $2="\"cryptdevice=UUID=" ID ":root root=/dev/mapper/root rootflags=subvol=@ " substr($2,2);print}' /etc/default/grub > /etc/default/grub.new
mv /etc/default/grub.new /etc/default/grub
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
tee -a /etc/grub.d/40_custom <<-"END"
	menuentry 'Live ISO' {
	    set imgdevpath='/dev/disk/by-uuid/xxxx-xxxx'
	    set isofile='/iso/archlinux-x86_64.iso'
	    loopback loop $isofile
	    linux (loop)/arch/boot/x86_64/vmlinuz-linux img_dev=$imgdevpath img_loop=$isofile earlymodules=loop
	    initrd (loop)/arch/boot/intel-ucode.img (loop)/arch/boot/x86_64/initramfs-linux.img
	}
	END
sed -i "s/xxxx-xxxx/$(blkid -s UUID -o value)" /etc/grub.d/40_custom
grub-mkconfig -o /boot/grub/grub.cfg

# Basic settings
ln -sf /usr/share/zoneinfo/America/Chicago /etc/localtime
hwclock --systohc
echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen
locale-gen
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
echo 'yoga' > /etc/hostname
echo -e "127.0.0.1\tlocalhost\n::1\t\tlocalhost\n127.0.1.1\tyoga" >> /etc/hosts
ln -s /usr/bin/vim /usr/bin/vi
echo 'export EDITOR=vim' > /etc/profile.d/env.sh

# Create user and set passwords
useradd -m -G wheel dan
cp /etc/skel/.* /home/dan
chown -R dan:dan /home/dan
passwd
passwd dan
visudo
EOF

# Run the chrooted install file
arch-chroot /mnt sh install.sh

# Finish installation
rm /mnt/install.sh
umount -R /mnt
reboot
