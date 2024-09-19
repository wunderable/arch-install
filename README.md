# arch-install

### Steps

1. Boot from Live ISO
2. `iwctl device list`
3. `iwctl station wlan0 scan`
4. `iwctl station wlan0 get-networks`
5. `iwctl station wlan0 connect 'SSID'`
6. `timedatectl set-ntp true`
7. `pacman -Syy`
8. `pacman -S git`
9. Wait for reflector to finish in the background
10. `efibootmgr` will list all boot managers. You can delete any of them with `efibootmgr -b # -B`
11. `git clone https://github.com/wunderable/arch-install.git`
12. `cd arch-install`
13. `sh install.sh`
