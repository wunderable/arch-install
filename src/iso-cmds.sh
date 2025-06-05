#!/bin/bash

CMD="\e[36m"
DESC="\e[90m"
END="\e[0m"

echo -e "\
${CMD}mfs$DESC - Mount the filesystem to /mnt$END
${CMD}subv$DESC - Utility for managing btrfs$END
${CMD}s$DESC - Short-hand tool for systemctl$END"
