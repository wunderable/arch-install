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
GUI=''		# Whether or not to include a GUI (y or n)

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

# Ask to include a GUI
if [ -z "$GUI" ]; then
	while true; do
		read -p "Install a GUI? (y/n): " GUI
		if [[ "$GUI" == "y" || "$GUI" == "n" ]]; then break; fi
		echo "Invalid response"
	done
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

# Set mounting options
OPTIONS='rw,noatime,discard=async,compress-force=zstd:1,space_cache=v2'

############################################################################################

################
# PREPARE DISK #
################

# Get current partitions (if any)
CUR_PARTS=$(lsblk -lno NAME "$DEV" | grep -v "^$(basename $DEV)$")

# Unmount all partitions
for CUR_PART in $CUR_PARTS; do
	MOUNT_POINT=$(findmnt -n -o TARGET "/dev/$CUR_PART" || true)
	if [[ -n "$MOUNT_POINT" ]]; then
		umount -R "/dev/$CUR_PART"
	fi
done

# Close any LUKS mappings
for CUR_PART in $CUR_PARTS; do
	if cryptsetup isLuks "/dev/$CUR_PART" 2>/dev/null; then
		MAPS=$(lsblk -lno NAME,TYPE | awk '$2=="crypt" {print $1}')
		for MAP in $MAPS; do
			cryptsetup luksClose "$MAP" || true
		done
		cryptsetup luksErase "/dev/$CUR_PARTS"
	fi
done

# Create partitions
wipefs --all --force $DEV
sgdisk --zap-all --clear $DEV
sgdisk -n 0:0:+2048MiB -t 0:ef00 -c 0:esp $DEV
sgdisk -n 0:0:0 -t 0:8309 -c 0:luks $DEV

# Format partitions
echo -n $LUKS_PASS | cryptsetup luksFormat $PART2 -
echo -n $LUKS_PASS | cryptsetup open $PART2 cryptroot -
mkfs.vfat -F32 -n BOOT $PART1
mkfs.btrfs -L ROOT /dev/mapper/cryptroot

# Create subvolumes
mount /dev/mapper/cryptroot /mnt
btrfs sub create /mnt/@root
btrfs sub create /mnt/@home
btrfs sub create /mnt/@snapshots
btrfs sub create /mnt/@log
btrfs sub create /mnt/@swap
mkdir /mnt/@root/var
btrfs sub create /mnt/@root/tmp
btrfs sub create /mnt/@root/var/cache
btrfs sub create /mnt/@root/var/tmp
umount /mnt

# Mount partitions
mount -o "${OPTIONS},subvol=@root" /dev/mapper/cryptroot /mnt
mkdir -p /mnt/{boot,home,etc,snapshots,var/log,swap}
mount -o "${OPTIONS},subvol=@home" /dev/mapper/cryptroot /mnt/home
mount -o "${OPTIONS},subvol=@snapshots" /dev/mapper/cryptroot /mnt/snapshots
mount -o "${OPTIONS},subvol=@log" /dev/mapper/cryptroot /mnt/var/log
mount -o "${OPTIONS},subvol=@swap" /dev/mapper/cryptroot /mnt/swap
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

# Install base packages
reflector --verbose --protocol https --latest 5 --sort rate --country 'United States' --save /etc/pacman.d/mirrorlist
pacstrap -K /mnt base linux linux-firmware fwupd $UCODE udisks2 efibootmgr btrfs-progs networkmanager vim man-db man-pages base-devel git

# Generate fstab file
genfstab -U /mnt >> /mnt/etc/fstab
sed -i "s/,subvolid=[0-9]\+//" /mnt/etc/fstab

###################
# CUSTOM PROGRAMS #
###################

# Copy files from github src folder to os
mkdir -p /mnt/usr/local/src
for FILE in $DIR/src/*; do
	BASE=$(basename -- "$FILE")
	cp $FILE /mnt/usr/local/src/$BASE
	chmod +x /mnt/usr/local/src/$BASE
done

# Update files with appropriate values
if [ -n "$UCODE" ]; then sed -i "s/\(' >> \/tmp\/iso\/packages.x86_64\)/\\\\n$UCODE\1/" /mnt/usr/local/src/build-liveiso.sh; fi
sed -i "s/<\$PART2>/${PART2//\//\\\/}/g" /mnt/usr/local/src/iso-mfs.sh
sed -i "s/<\$OPTIONS>/$OPTIONS/g" /mnt/usr/local/src/iso-mfs.sh

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
ln -s /usr/bin/vim /usr/bin/vi

##############
# ENVIORMENT #
##############

tee -a /etc/enviornment <<-"END"
	EDITOR=vim
	XDG_CONFIG_HOME="$HOME/.config"
	LC_COLLATE=C
END

###################
# CUSTOM COMMANDS #
###################

# Link custom scripts so they can be run from PATH
for FILE in /usr/local/src/*; do
	BASE=$(basename -- "$FILE")
	NAME="${BASE%.*}"
	ln -s $FILE /usr/local/bin/$NAME
done

################
# SYSTEMD-BOOT #
################

bootctl install
echo -e "default 01-arch\ntimeout 5\neditor no" > /boot/loader/loader.conf
PART_ID="$(blkid -s UUID -o value <$PART2>)"
SWAP_ID="$(findmnt -no UUID -T /swap/swapfile)"
SWAP_OFFSET="$(btrfs inspect-internal map-swapfile -r /swap/swapfile)"
BOOT_ID="$(lsblk -no PARTUUID <$PART1>)"
tee /boot/loader/entries/01-arch.conf <<-END
	title	Arch Linux
	linux	/vmlinuz-linux
	initrd	/<$UCODE>.img
	initrd	/initramfs-linux.img
	options	cryptdevice=UUID=$PART_ID:cryptroot root=/dev/mapper/cryptroot rootflags=subvol=@root rootfstype=btrfs resume=UUID=$SWAP_ID resume_offset=$SWAP_OFFSET rw quiet
	sort-key 1
END
tee /boot/loader/entries/02-archiso.conf <<-END
	title	Arch ISO
	linux	/iso/vmlinuz-linux
	initrd	/iso/initramfs-linux.img
	options	img_dev=/dev/disk/by-partuuid/$BOOT_ID img_loop=/iso/archiso.iso earlymodules=loop
	sort-key 2
END
build-archiso

##############
# MKINITCPIO #
##############

# Update hooks
tee /etc/mkinitcpio.conf <<-"END"
	MODULES=(vmd)
	BINARIES=(/usr/bin/btrfs)
	FILES=()
	HOOKS=(base udev autodetect modconf kms keyboard keymap consolefont block encrypt resume filesystems fsck)
END
mkinitcpio -P

#########
# SHELL #
#########

# Set prompt and aliases for shells
sed -i '/^\s*PS1=/asource /etc/profile.d/prompt.sh || true' /etc/bash.bashrc
echo 'source /etc/profile.d/aliases.sh || true' >> /etc/bash.bashrc
cp /etc/bash.bashrc /etc/skel/.bashrc

#########
# USERS #
#########

# Create user and set passwords
useradd -m -G wheel <$USER>
echo <$USER>:<$USER_PASS> | chpasswd
echo root:<$USER_PASS> | chpasswd
sed -Ei "s/^# (%wheel ALL=\(ALL:ALL\) ALL)/\1/" /etc/sudoers

##########
# PACMAN #
##########

# Config
sed -i "s/#Color/Color/" /etc/pacman.conf

# Install packages with pacman
pacman --noconfirm -S acpid openssh python3 zsh zsh-autosuggestions zsh-syntax-highlighting # upower pipewire wireplumber alsa-utils
if [[ "<$GUI>" == "y" ]]; then
	pacman --noconfirm -S greetd greetd-tuigreet gtk4 hyprland kitty neofetch spotify-launcher ttf-joypixels ttf-roboto-mono-nerd vivaldi vivaldi-ffmpeg-codecs
fi

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
if [[ "<$GUI>" == "y" ]]; then
	sudo -u <$USER> yay --noconfirm -S anyrun-git visual-studio-code-bin
fi
rm /etc/sudoers.d/nopass

########
# SUBV #
########

# Create config file
tee /etc/subv.conf <<-"END"
	[settings]
	default_path = /
	snapshot_dest = /snapshots

	[locations]
	root = /
	home = /home
END

##########
# VSCODE #
##########

if [[ "<$GUI>" == "y" ]]; then
	# Pass touch events to electron when launching code
	sed -i 's|Exec=/usr/bin/code\(.*\)|Exec=/usr/bin/code --touch-events\1|' /usr/share/applications/code.desktop
	sed -i 's|Exec=/usr/bin/code\(.*\)|Exec=/usr/bin/code --touch-events\1|' /usr/share/applications/code-url-handler.desktop
fi

#############################
# GREETER / DISPLAY MANAGER #
#############################

if [[ "<$GUI>" == "y" ]]; then
	systemctl enable greetd
	tee /etc/greetd/config.toml <<-"END"
		[terminal]
		vt = 1

		[default_session]
		command = "tuigreet --time --time-format '%A, %B %-d %I:%M' --remember --user-menu --cmd 'Hyprland > /dev/null' --theme 'time=cyan;border=cyan;title=magenta;button=yellow'"
		user = "greeter"
	END
fi

########
# MISC #
########

# Hibernate 30 mins after sleeping
sed -Ei "s/^#(HibernateDelaySec=)$/\130min/" /etc/systemd/sleep.conf

# Change default shell
chsh -s /usr/bin/zsh

# Enable services at startup
systemctl enable NetworkManager
systemctl enable sshd

EOF

# Replace variable placeholders with their variable values
sed -i "s/<\$HOST>/$HOST/g" /mnt/install.sh
sed -i "s/<\$PART1>/${PART1//\//\\\/}/g" /mnt/install.sh
sed -i "s/<\$PART2>/${PART2//\//\\\/}/g" /mnt/install.sh
sed -i "s/<\$USER>/$USER/g" /mnt/install.sh
sed -i "s/<\$USER_PASS>/$USER_PASS/g" /mnt/install.sh
sed -i "s/<\$UCODE>/$UCODE/g" /mnt/install.sh
sed -i "s/<\$GUI>/$GUI/g" /mnt/install.sh

# Run the chrooted install file
arch-chroot /mnt sh install.sh

##############
# COPY FILES #
##############

if [[ "$GUI" == "y" ]]; then
	# Hyprland
	mkdir -p /mnt/home/$USER/.config/hypr
	cp $DIR/files/hypr/hyprland.conf /mnt/home/$USER/.config/hypr/hyprland.conf

	# Kitty
	mkdir -p /mnt/home/$USER/.config/kitty
	cp $DIR/files/kitty/kitty.conf /mnt/home/$USER/.config/kitty/kitty.conf
fi

# Shell
cp $DIR/files/shell/aliases.sh /mnt/etc/profile.d/aliases.sh
cp $DIR/files/shell/prompt.sh /mnt/etc/profile.d/prompt.sh
cp $DIR/files/shell/zshrc /mnt/etc/zsh/zshrc

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
