#source /usr/share/git/git-prompt.sh
export GIT_PS1_SHOWDIRTYSTATE=1
export GIT_PS1_SHOWSTASHSTATE=1
export GIT_PS1_SHOWUNTRACKEDFILES=1
COLOR=$(( EUID == 0 ? 31 : 32))

PS1_USER="\[\e[${COLOR}m\]\u"
PS1_HOST="\[\e[90m\]@\h:"
PS1_DIR="\[\e[34m\]\w"
#PS1_GIT='\[\e[33m\]$(__git_ps1)'
PS1_PROMPT="\[\e[${COLOR}m\]\$\[\e[0m\] "

export PS1="${PS1_USER}${PS1_HOST}${PS1_DIR}${PS1_PROMPT}"
