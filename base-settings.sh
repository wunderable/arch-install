#!/bin/sh

ln -sf /usr/share/zoneinfo/America/Chicago /etc/localtime
hwclock --systohc
echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen
locale-gen
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
echo 'yoga' > /etc/hostname
echo -e '127.0.0.1\tlocalhost\n::1\t\tlocalhost\n127.0.1.1\tyoga' >> /etc/hosts
ln -s /usr/bin/vim /usr/bin/vi
echo 'export EDITOR=vim' > /etc/profile.d/env.sh
passwd
useradd -m -G wheel dan
passwd dan
visudo
