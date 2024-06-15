# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# Source aliases if they exist
source /etc/profile.d/aliases.sh || true

# Set prompt
PS1='\u@\h:\w \$ '
