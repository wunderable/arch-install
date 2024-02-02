#!/bin/bash

cryptsetup open <$PART2> root
mount -o /dev/mapper/root /mnt
