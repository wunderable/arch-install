COLOR=$(( EUID == 0 ? 31 : 32))

USER="\[\e[${COLOR}m\]\u"
HOST="\[\e[90m\]@\h:"
DIR="\[\e[34m\]\w"
PROMPT="\[\e[${COLOR}m\]\$\[\e[0m\] "

export PS1="${USER}${HOST}${DIR}${PROMPT}"
