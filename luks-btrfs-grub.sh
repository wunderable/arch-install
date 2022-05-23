#!/bin/sh

# Create partitions
sgdisk --zap-all /dev/nvme0n1
sgdisk --clear /dev/nvme0n1
sgdisk --new 1:0:+250M --typecode 1:ef00 /dev/nvme0n1
sgdisk --new 2:0:0 --typecode 2:8300 /dev/nvme0n1

# Format partitions
mkfs.fat -F32 -n BOOT /dev/nvme0n1p1
cryptsetup --type luks1 luksFormat /dev/nvme0n1p2
cryptsetup open /dev/nvme0n1p2 root
mkfs.btrfs -L ROOT /dev/mapper/root

# Create subvolumes
mount /dev/mapper/root /mnt
mkdir -p /mnt/var/cache/pacman
mkdir -p /mnt/home/dan
btrfs sub create /mnt/@
btrfs sub create /mnt/@home
btrfs sub create /mnt/.snapshots
btrfs sub create /mnt/var/cache/pacman/pkg
btrfs sub create /mnt/var/log
btrfs sub create /mnt/var/tmp
btrfs sub create /mnt/home/dan/.cache
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

# Create file to be run in arch-chrooted environment
tee /mnt/install.sh <<-"EOF"
#!/bin/sh

mkdir /.snapshots

# Update hooks
tee /etc/mkinitcpio.conf <<-"EOT"
	MODULES=(vmd)
	BINARIES=(/usr/bin/btrfs)
	HOOKS=(base udev autodetect keyboard consolefont modconf block encrypt btrfs filesystems fsck)
	EOT
mkinitcpio -p linux

# Install grub
mkdir /boot/efi
awk -vFPAT='([^=]*)|("[^"]+")' -vOFS== -vID="$(blkid -s PARTUIID -o value /dev/nvme0n1p2)" '{if($1=="GRUB_CMDLINE_LINUX_DEFAULT") $2="\"cryptodevice=PARTUUID=" ID ":root root=/dev/mapper/root " substr($2,2);if($1=="#GRUB_ENABLE_CRYPTODISK") $1=substr($1,2);print}' /etc/default/grub > /etc/default/grub.new
mv /etc/default/grub.new /etc/default/grub
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB

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
tee /etc/profile.d/aliases.sh <<-"EOT"
	alias view="vim -R"
	alias ls="ls --color=auto"
	alias ll="ls -hAl"
	alias la="ls -a"
	alias cd..="cd .."
	alias bat="cat /sys/class/power_supply/BAT0/capacity"
	EOT

# Create user and set passwords
useradd -m -G wheel dan
passwd
passwd dan
visudo
EOF

# Run the chrooted install file
arch-chroot /mnt sh install.sh
