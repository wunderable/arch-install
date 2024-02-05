#!/bin/bash

cryptsetup open <$PART2> root
mount -o "<$OPTIONS>,subvolid=5" /dev/mapper/root /mnt
