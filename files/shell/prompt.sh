source /usr/share/git/git-prompt.sh
export GIT_PS1_SHOWDIRTYSTATE=1
export GIT_PS1_SHOWSTASHSTATE=1
export GIT_PS1_SHOWUNTRACKEDFILES=1
COLOR=$(( EUID == 0 ? 31 : 32))

USER="\[\e[${COLOR}m\]\u"
HOST="\[\e[90m\]@\h:"
DIR="\[\e[34m\]\w"
GIT='\[\e[33m\]$(__git_ps1)'
CHAR="\[\e[${COLOR}m\]\$\[\e[0m\] "

export PS1="${USER}${HOST}${DIR}${GIT}${CHAR}"
