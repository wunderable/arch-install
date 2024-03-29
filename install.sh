#!/bin/bash

###########################################
# (OPTIONALLY) SET USER DEFINED VARIABLES #
###########################################

# User defined variables. Script will ask for them interactively if set to an empty string
DEV=''		# The block device to install to
LUKS_PASS=''	# The password to unlock encrypted partition
USER=''		# Username of primary user
USER_PASS=''	# Password of primary user and root
HOST=''		# Hostname of the computer

#########################
# SET MISSING VARIABLES #
#########################

# Select device (if $DEV isn't already set)
if [ -z "$DEV" ]; then
	IFS=$'\n'
	DEVS=($(lsblk --list --output path,size,type | grep disk | awk '{print $1 " - " $2}'))
	PS3='Select disk to install to: '
	select CHOICE in "${DEVS[@]}"; do
		if [[ $REPLY =~ ^[0-9]+$ && $REPLY -ge 1 && $REPLY -le ${#DEVS[@]} ]]; then break; fi
		echo 'Invalid option'
	done
	DEV=$(grep -Po "^[^\s]+" <<< "$CHOICE")
fi

# Ask for encryption password (if $LUKS_PASS isn't already set)
if [ -z "$LUKS_PASS" ]; then
	while true; do
		read -sp "Enter encryption password: " LUKS_PASS
  		echo
		read -sp "Verify encryption password: " LUKS_VERIFY
  		echo
		if [[ "$LUKS_PASS" == "$LUKS_VERIFY" ]]; then break; fi
		echo "Passwords did not match"
	done
 	unset LUKS_VERIFY
fi

# Ask for username (if $USER isn't already set)
if [ -z $USER ]; then
	read -p "Enter username: " USER
fi

# Ask for user password (if $USER_PASS isn't already set)
if [ -z "$USER_PASS" ]; then
	while true; do
		read -sp "Enter root/user password: " USER_PASS
  		echo
		read -sp "Verify root/user password: " USER_VERIFY
  		echo
		if [[ "$USER_PASS" == "$USER_VERIFY" ]]; then break; fi
		echo "Passwords did not match"
	done
 	unset USER_VERIFY
fi

# Ask for hostname (if $HOST isn't already set)
if [ -z "$HOST" ]; then
	read -p "Enter the desired hostname: " HOST
fi

######################
# SET MISC VARIABLES #
######################

# Set partition variables based on device
PART=$DEV
if [[ $PART =~ [0-9]$ ]]; then PART+="p"; fi
PART1="${PART}1"
PART2="${PART}2"
unset PART

# Determine which microcode, if any, to include
CPU=$(lscpu | grep "^Vendor ID" | awk '{print $3}')
UCODE=''
if [ "$CPU" = "GenuineIntel" ]; then UCODE='intel-ucode'; fi
if [ "$CPU" = "AuthenticAMD" ]; then UCODE='amd-ucode'; fi

# Get base directory of this project
DIR="$( cd "$( dirname "$0" )" && pwd )"

################
# PREPARE DISK #
################

# Create partitions
wipefs --all --force $DEV
sgdisk --zap-all --clear $DEV
sgdisk -n 0:0:+1536MiB -t 0:ef00 -c 0:esp $DEV
sgdisk -n 0:0:0 -t 0:8309 -c 0:luks $DEV

# Format partitions
echo -n $LUKS_PASS | cryptsetup --type luks1 luksFormat $PART2 -
echo -n $LUKS_PASS | cryptsetup open $PART2 root -
mkfs.vfat -F32 -n BOOT $PART1
mkfs.btrfs -L ROOT /dev/mapper/root

# Create subvolumes
mount /dev/mapper/root /mnt
btrfs sub create /mnt/@root
btrfs sub create /mnt/@home
btrfs sub create /mnt/@snapshots
btrfs sub create /mnt/@log
btrfs sub create /mnt/@swap
mkdir /mnt/@root/var
btrfs sub create /mnt/@root/var/cache
btrfs sub create /mnt/@root/var/tmp
btrfs sub create /mnt/@root/tmp
umount /mnt

# Mount partitions
OPTIONS='rw,noatime,discard=async,compress-force=zstd:1,space_cache=v2'
mount -o "${OPTIONS},subvol=@root" /dev/mapper/root /mnt
mkdir -p /mnt/{boot,home,etc,snapshots,var/log,swap}
mount -o "${OPTIONS},subvol=@home" /dev/mapper/root /mnt/home
mount -o "${OPTIONS},subvol=@snapshots" /dev/mapper/root /mnt/snapshots
mount -o "${OPTIONS},subvol=@log" /dev/mapper/root /mnt/var/log
mount -o "${OPTIONS},subvol=@swap" /dev/mapper/root /mnt/swap
mount $PART1 /mnt/boot

# Disable CoW for some directories
chattr +C /mnt/var/cache
chattr +C /mnt/var/tmp
chattr +C /mnt/var/log
chattr +C /mnt/tmp
chattr +C /mnt/swap

# Setup swapfile (size is RAM + square root of RAM)
btrfs filesystem mkswapfile --size $(free -g | awk 'NR==2 {printf("%.0fg", $2+1+sqrt($2+1))}') --uuid clear /mnt/swap/swapfile
swapon /mnt/swap/swapfile

###########
# INSTALL #
###########

# Install packages
reflector --verbose --protocol https --latest 5 --sort rate --country 'United States' --save /etc/pacman.d/mirrorlist
pacstrap -K /mnt base linux linux-firmware $UCODE btrfs-progs networkmanager vim man-db man-pages base-devel git grub efibootmgr

# Generate fstab file
genfstab -U /mnt >> /mnt/etc/fstab
sed -i "s/,subvolid=[0-9]\+//" /mnt/etc/fstab

##############
# COPY FILES #
##############

# Copy files from github src folder to os
mkdir -p /mnt/usr/local/src
for FILE in $DIR/src/*; do
	BASE=$(basename -- "$FILE")
	cp $FILE /mnt/usr/local/src/$BASE
	chmod +x /mnt/usr/local/src/$BASE
done

# Update files with appropriate values
if [ -n "$UCODE" ]; then sed -i "s/\(' >> \/tmp\/iso\/packages.x86_64\)/\\\\n$UCODE\1/" /mnt/usr/local/src/build-myarchiso.sh; fi
sed -i "s/<\$PART2>/${PART2//\//\\\/}/g" /mnt/usr/local/src/iso-mfs.sh
sed -i "s/<\$OPTIONS>/$OPTIONS/g" /mnt/usr/local/src/iso-mfs.sh

# Copy other miscellaneous files
cp $DIR/files/aliases.sh /mnt/etc/profile.d/aliases.sh


#####################################
# CREATE SCRIPT TO BE RUN IN CHROOT #
#####################################

# Create file to be run in arch-chrooted environment
tee /mnt/install.sh << "EOF"
#!/bin/bash

##################
# BASIC SETTINGS #
##################

# Basic settings
ln -sf /usr/share/zoneinfo/America/Chicago /etc/localtime
hwclock --systohc
echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
locale-gen
echo '<$HOST>' > /etc/hostname
echo -e "127.0.0.1\tlocalhost\n::1\t\tlocalhost\n127.0.1.1\t<$HOST>.localdomain <$HOST>" >> /etc/hosts
echo 'EDITOR=vim' >> /etc/environment
ln -s /usr/bin/vim /usr/bin/vi

###################
# CUSTOM COMMANDS #
###################

# Link custom scripts so they can be run from PATH
for FILE in /usr/local/src/*; do
	BASE=$(basename -- "$FILE")
	NAME="${BASE%.*}"
	ln -s $FILE /usr/local/bin/$NAME
done

##############
# MKINITCPIO #
##############

# Update hooks
tee /etc/mkinitcpio.conf <<-"END"
	MODULES=(vmd)
	BINARIES=(/usr/bin/btrfs)
	FILES=()
	HOOKS=(base udev keyboard autodetect keymap consolefont modconf kms block encrypt filesystems resume fsck)
	END
mkinitcpio -P

########
# GRUB #
########

# Prepare GRUB file
awk \
	-vFPAT='([^=]*)|("[^"]+")' \
	-vOFS== \
	-vPART_ID="$(blkid -s UUID -o value <$PART2>)" \
	-vSWAP_ID="$(findmnt -no UUID -T /swap/swapfile)" \
	-vSWAP_OFFSET="$(btrfs inspect-internal map-swapfile -r /swap/swapfile)" \
 	'{
		if($1=="GRUB_TIMEOUT")
			$2="2";
	  	if($1=="GRUB_CMDLINE_LINUX_DEFAULT")
			$2="\"cryptdevice=UUID=" PART_ID ":root root=/dev/mapper/root rootflags=subvol=@root resume=UUID=" SWAP_ID " resume_offset=" SWAP_OFFSET " loglevel=3 quiet\"";
		print
	}' /etc/default/grub > /etc/default/grub.new
mv /etc/default/grub.new /etc/default/grub

# Install GRUB
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB

# Customize GRUB
tee -a /etc/grub.d/40_custom <<-"END"
	menuentry 'Live ISO' --class disc --class iso {
	    set imgdevpath='/dev/disk/by-uuid/xxxx-xxxx'
	    set isofile='/iso/myarch.iso'
	    loopback loop $isofile
	    linux (loop)/arch/boot/x86_64/vmlinuz-linux img_dev=$imgdevpath img_loop=$isofile earlymodules=loop
	    initrd (loop)/arch/boot/intel-ucode.img (loop)/arch/boot/x86_64/initramfs-linux.img
	}
	END
mkdir /boot/iso
sed -i "/submenu.*Advanced options/,/is_top_level=false/s/^/#REMOVE_ADVANCED_OPTIONS#/" /etc/grub.d/10_linux
sed -i "/linux_entry.*advanced/,/done/{/done/b;s/^/#REMOVE_ADVACNED_OPTIONS#/}" /etc/grub.d/10_linux
sed -i "s/\(menuentry '\$LABEL'\)/\1 --class driver/" /etc/grub.d/30_uefi-firmware
sed -i "s/xxxx-xxxx/$(blkid -s UUID -o value <$PART1>)/" /etc/grub.d/40_custom
sed -i 's/^\s+/\t/' /etc/grub.d/40_custom

# Update GRUB
grub-mkconfig -o /boot/grub/grub.cfg
build-myarchiso

#########
# USERS #
#########

# Create user and set passwords
useradd -m -G wheel <$USER>
cp -a /etc/skel/. /home/<$USER>/
echo <$USER>:<$USER_PASS> | chpasswd
echo root:<$USER_PASS> | chpasswd
sed -Ei "s/^# (%wheel ALL=\(ALL:ALL\) ALL)/\1/" /etc/sudoers

##########
# PACMAN #
##########

# Config
sed -i "s/#Color/Color/" /etc/pacman.conf

# Install packages with pacman
pacman --noconfirm -S python3


#######
# YAY #
#######

# Config
echo '<$USER> ALL=(ALL:ALL) NOPASSWD: ALL' > /etc/sudoers.d/nopass

# Install yay
cd /home/<$USER>
git clone https://aur.archlinux.org/yay.git
chown -R <$USER>:<$USER> /home/<$USER>
cd yay
sudo -u <$USER> makepkg -s --noconfirm
pacman -U yay*-x86_64.pkg.tar.zst --noconfirm
cd ..
rm -r --interactive=never yay

# Install packages with yay
sudo -u <$USER> yay --noconfirm -Syu
sudo -u <$USER> yay --noconfirm -S neofetch
rm /etc/sudoers.d/nopass

########
# MISC #
########

# Hibernate 30 mins after sleeping
sed -Ei "s/^#(HibernateDelaySec=)$/\130min/" /etc/systemd/sleep.conf

EOF

# Replace variable placeholders with their variable values
sed -i "s/<\$HOST>/$HOST/g" /mnt/install.sh
sed -i "s/<\$PART1>/${PART1//\//\\\/}/g" /mnt/install.sh
sed -i "s/<\$PART2>/${PART2//\//\\\/}/g" /mnt/install.sh
sed -i "s/<\$USER>/$USER/g" /mnt/install.sh
sed -i "s/<\$USER_PASS>/$USER_PASS/g" /mnt/install.sh

# Run the chrooted install file
arch-chroot /mnt sh install.sh

########
# MISC #
########

# Verify permisions are correct on user's home dir
chown -R 1000:1000 /mnt/home/$USER

############
# FINALIZE #
############

# Clean up and finish installation
rm /mnt/install.sh
swapoff /mnt/swap/swapfile
umount -R /mnt
reboot
