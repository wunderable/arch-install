#!/bin/bash

cryptsetup open /dev/nvme0n1p2 root
mount -o /dev/mapper/root /mnt
