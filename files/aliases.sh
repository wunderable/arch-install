alias ls='ls --color=auto'
alias la='ls -a'
alias ll='ls -hAl'
alias lt='ls -hAlt'

alias ls..='ls ..'
alias la..='la ..'
alias ll..='ll ..'
alias lt..='lt ..'
alias cd..='cd ..'

alias view='vim -R'
alias bat='printf "%s%% - %s\n" $(cat /sys/class/power_supply/BAT0/capacity) $(cat /sys/class/power_supply/BAT0/status)'
alias term='neofetch --config ~/.config/neofetch/term.conf'

alias date_y='date +%F' # YYYY-MM-DD
alias date_t='date +%T' # HH:MM:SS
alias date_yt='date +%F\ %T' # YYYY-MM-DD HH:MM:SS
alias date_Y='date +%4Y%m%d' # YYYYMMDD
alias date_T='date +%H%M%S' # HHMMSS
alias date_YT='date +%4Y%m%d_%H%M%S' # YYYYMMDD_HHMMSS
