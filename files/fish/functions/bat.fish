function bat
	if test -d /sys/class/power_supply/BAT0
		printf "%s%% - %s\n" (cat /sys/class/power_supply/BAT0/capacity) (cat /sys/class/power_supply/BAT0/status)
		return 0
	else
		printf "Battery not found!\n"
		return 1
	end
end
