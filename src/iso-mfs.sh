#!/bin/bash

cryptsetup open <$PART2> root
mount -o <$OPTIONS> /dev/mapper/root /mnt
