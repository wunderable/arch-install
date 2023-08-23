# arch-install

### Steps

1. Boot from Live ISO
2. `iwctl station wlan0 connect 'SSID'`
3. `timedatectl set-ntp true`
4. `pacman -Syy`
5. `pacman -S git`
6. Wait for reflector to finish in the background
7. `efibootmgr` will list all boot managers. You can delete any of them with `efibootmgr -b # -B`
8. `git clone https://github.com/wunderable/arch-install.git`
10. `cd arch-install`
11. `sh install.sh`
