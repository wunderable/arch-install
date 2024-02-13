#!/bin/bash

CMD="\e[0;32m" # Green
DESC="\e[2;37m" # Faint Light Gray
END="\e[0m" # Reset

function print_usage {
  echo -e "\
Alias for systemctl. Accepts the following short-hand arguments, otherwise passes all arguments directly to systemctl:
${CMD}reboot | restart${DESC} - Shut down and reboot the system${END}
${CMD}poweroff | off | shutdown${DESC} - Shut down and power-off the system${END}
${CMD}suspend | suspend-to-ram | deep | 3 | ram${DESC} - Limits power consumption by the system${END}
${CMD}hibernate | suspend-to-disk | disk | 4${DESC} - Saves RAM to disk and power-off the system${END}
${CMD}hybrid-sleep | suspend-to-both | both$DESC} - Saves RAM to disk then suspends${END}
${CMD}suspend-then-hibernate | sleep$DESC} - First suspend the system, then wake up after 45mins and hibernate${END}"
}

if [[ $# -eq 0 ]]; then
  print_usage
  exit
fi

if [[ $# -eq 1 ]]; then
  case $1 in
    reboot | restart) systemctl reboot; exit;;
    poweroff | off | shutdown) systemctl poweroff; exit;;
    suspend | suspend-to-ram | deep | 3 | ram) systemctl suspend; exit;;
    hibernate | suspend-to-disk | disk | 4) systemctl hibernate; exit;;
    hybrid-sleep | suspend-to-both | both) systemctl hybrid-sleep; exit;;
    suspend-then-hibernate | sleep) systemctl suspend-then-sleep; exit;;
  esac
fi

systemctl "$@"
