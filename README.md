# arch-install

### 1. Boot from Live ISO

### 2. Connect to internet
If using wifi:
* Get a list of devices `iwctl device list`
* Scan for networks `iwctl station <wlan> scan`
* View networks `iwctl station <wlan> get-networks`
* Connect to network `iwctl station <wlan> connect <ssid>`

### 3. Verify date/time
* `timedatectl set-ntp true`
* `date`

### 4. Install git
* Ensure repos are up-to-date `pacman -Syy`
* Install git `pacman -S git`

### 5. (Optional) Delete grub
* `efibootmgr -b 0 -B`

### 6. Clone repository
* `git clone https://github.com/wunderable/arch-install.git`

### 7. Install
* `cd arch-install`
* `sh install.sh`
