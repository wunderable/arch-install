#!/bin/bash

###########################################
# (OPTIONALLY) SET USER DEFINED VARIABLES #
###########################################

# User defined variables. Script will ask for them interactively if set to an empty string
DEV=''		# The block device to install to
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

################
# PREPARE DISK #
################

# Create partitions
wipefs --all --force $DEV
sgdisk --zap-all --clear $DEV
sgdisk -n 0:0:+1536MiB -t 0:ef00 -c 0:esp $DEV
sgdisk -n 0:0:0 -t 0:8309 -c 0:luks $DEV

# Format partitions
mkfs.vfat -F32 -n BOOT $PART1
mkfs.ext4 -L ROOT $PART2

# Mount partitions
mount $PART2 /mnt
mkdir -p /mnt/boot
mount $PART1 /mnt/boot

###########
# INSTALL #
###########

# Install packages
reflector --verbose --protocol https --latest 5 --sort rate --country 'United States' --save /etc/pacman.d/mirrorlist
pacstrap -K /mnt base linux linux-firmware intel-ucode networkmanager vim man-db man-pages base-devel git grub efibootmgr

# Generate fstab file
genfstab -U /mnt >> /mnt/etc/fstab

#####################################
# CREATE SCRIPT TO BE RUN IN CHROOT #
#####################################

# Create file to be run in arch-chrooted environment
tee /mnt/install.sh << "EOF"
#!/bin/bash

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

# Update hooks
tee /etc/mkinitcpio.conf <<-"END"
	MODULES=(vmd)
	BINARIES=()
	FILES=()
	HOOKS=(base udev keyboard autodetect keymap consolefont modconf kms block filesystems fsck)
	END
mkinitcpio -P

# Prepare GRUB file
awk -vFPAT='([^=]*)|("[^"]+")' -vOFS== '{
	if($1=="GRUB_TIMEOUT")
		$2="2";
	print
}' /etc/default/grub > /etc/default/grub.new
mv /etc/default/grub.new /etc/default/grub

# Install GRUB
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB

# Update GRUB
grub-mkconfig -o /boot/grub/grub.cfg

# Create user and set passwords
user add -m -G wheel <$USER>
cp -a /etc/skel/. /home/<$USER>/
echo <$USER>:<$USER_PASS> | chpasswd
echo root:<$USER_PASS> | chpasswd
sed -Ei "s/^# (%wheel ALL=\(ALL:ALL\) ALL)/\1/" /etc/sudoers

EOF

# Replace variable placeholders with their variable values
sed -i "s/<\$HOST>/$HOST/g" /mnt/install.sh
sed -i "s/<\$USER>/$USER/g" /mnt/install.sh
sed -i "s/<\$USER_PASS>/$USER_PASS/g" /mnt/install.sh

# Run the chrooted install file
arch-chroot /mnt sh install.sh

############
# FINALIZE #
############

# Clean up and finish installation
chown -R 1000:1000 /mnt/home/$USER
rm /mnt/install.sh
umount -R /mnt
reboot
