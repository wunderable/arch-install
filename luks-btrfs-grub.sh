#!/bin/sh

sgdisk --zap-all /dev/nvme0n1
sgdisk --clear /dev/nvme0n1
sgdisk --new 1:0:+100M --typecode 1:ef00 /dev/nvme0n1
sgdisk --new 2:0:0 --typecode 2:8300 /dev/nvme0n1

mkfs.fat -F32 -n EFI /dev/nvme0n1p1
cryptsetup --type luks1 luksFormat /dev/nvme0n1p2
cryptsetup open /dev/nvme0n1p2 root
mkfs.btrfs -L ROOT /dev/mapper/root

mount /dev/mapper/root /mnt
mkdir /mnt/.snapshots
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

mount -o noatime,compress=zstd,space_cache=v2,discard=async,ssd,subvol=@ /dev/mapper/root /mnt
mkdir /mnt/home
mount -o noatime,compress=zstd,space_cache=v2,discard=async,ssd,subvol=@home /dev/mapper/root /mnt/home
mkdir /mnt/efi
mount /dev/nvme0n1p1 /mnt/efi

pacstrap /mnt base linux linux-firmware intel-ucode btrfs-progs networkmanager vim man-db man-pages base-devel git grub efibootmgr

genfstab -U /mnt >> /mnt/etc/fstab
arch-chroot
