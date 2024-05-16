#! /usr/bin/python

import re
import sys
import os.path
import argparse
import subprocess

# Formatter for argparse that preservers new lines if text begins with 'R|'
class MyFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)

# Get argparse instance for handling supplied arguments
def get_parser():
    main = argparse.ArgumentParser(
            prog='subv',
            description='A utility to help manage btrfs subvolumes',
            formatter_class=MyFormatter)
    main.subs = {}
    subs = main.add_subparsers(help='commands', dest='cmd')

    # List subparser
    listp = subs.add_parser('list',
                            help='list all subvolumes under /',
                            description='Outputs a list of all subvolumes under the / directory',
                            formatter_class=MyFormatter)
    main.subs['list'] = listp
    listp.add_argument('-f', '--fields',
                       default='ipnm',
                       help='R|FIELDS is a series of letters that refer to the fields that will be displayed and in what order. Default is \'ipnm\'. Fields can be:\n  i  id\n  p  parent\n  n  name\n  m  mount')
    listp.add_argument('-s', '--sort',
                       choices=['i','p','n','m'],
                       default='i',
                       help='SORT is a letter indicating which field to sort by. Default is \'i\'')

    # Snap subparser
    snapp = subs.add_parser('snap',
                            help='create a snapshot of the specified subvolumes',
                            description='Creates a snapshot of all specified subvolumes and saves it to /.snapshots',
                            formatter_class=MyFormatter)
    main.subs['snap'] = snapp
    snapp.add_argument('-n', '--name', help='append NAME to the snapshot\'s filename')
    snapp.add_argument('sources', nargs='*',#argparse.REMAINDER,
                       help='R|the source locations to create a snapshot of. Can either be a single argument made up of only valid letter abbreviations or a list of names separated by a space\n  r  root    /\n  h  home    /home\n  l  logs    /var/logs')

    return main

# Additional argument verification that argparse can't natively handle
def verify_args(parser, args):
    match(args.cmd):

        case 'list':
            if args.fields != None and not re.match("^[imnp]+$", args.fields):
                parser.subs['list'].error('Unknow value [' + args.fields + '] for FIELDS')

        case 'snap':
            if len(args.sources) == 1 and re.match("^[hlr]+$", args.sources[0]):
                print('abbrevs are good')
                return
            for s in args.sources:
                if not s in ['home', 'logs', 'root']:
                    parser.subs['snap'].error('Unknown source [' + s + ']')

def read_config():
    try:
        file = open(os.path.expandvars("$HOME/.config/subv/sources.cfg"), "r")
        for line in file:
            print(line)

    except:
        print('ERROR: There was an issue reading $HOME/.config/subv/sources.cfg', file=sys.stderr)
        exit(1)

    return True

def execute(cmd):
    return subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

def get_subs():
    results = execute('sudo btrfs subvolume list -a /')
    subvolumes = []
    for line in results.splitlines():
        field = line.split()
        field[8] = re.sub(r'^<FS_TREE>/', '', field[8])
        subvolumes.append((field[1], field[6], field[8]))
    return subvolumes

def get_snaps():
    results = execute('sudo btrfs subvolume list -s /')
    snaps = []
    for line in results.splitlines():
        field = line.split()
        snaps.append(field[1])
    return snaps

def get_ros():
    results = execute('sudo btrfs subvolume list -r /')
    ros = []
    for line in results.splitlines():
        field = line.split()
        ros.append(field[1])
    return ros

def get_mounts():
    results = execute('findmnt -nl -tbtrfs -ooptions,target')
    mounts = []
    for line in results.splitlines():
        field = line.split()
        match = re.search(r'subvolid=(\d+)', field[0])
        mounts.append((match.group(1), field[1]))
    return mounts

def get_subvolumes():
    subs = get_subs()
    snaps = get_snaps()
    ros = get_ros()
    mounts = get_mounts()
    subvolumes = []
    for s in subs:
        typ = 'Subvolume'
        if s[0] in snaps:
            typ = 'Snapshot'
            snaps.remove(s[0])
        r = 'rw'
        if s[0] in ros:
            r = 'ro'
            ros.remove(s[0])
        mnt = '-'
        for m in mounts:
            if m[0] == s[0]:
                mnt = m[1]
                mounts.remove(m)
                break
        subvolumes.append((int(s[0]), int(s[1]), s[2], typ, r, mnt))
    print_2d(subvolumes, 3)

def print_2d(arr, spaces=1):
    lengths = []
    first = True
    for i in arr:
        c = -1 
        for j in i:
            c += 1
            if first: lengths.append(0)
            if len(str(j)) > lengths[c]: lengths[c] = len(str(j))
        first = False
    for i in arr:
        c = -1
        for j in i:
            c += 1
            print(j, end='')
            print(' ' * (lengths[c] - len(str(j)) + spaces), end='')
        print()

# Program start
def main():
    get_subvolumes()
    exit(0)

    parser = get_parser()

    if len(sys.argv) == 1: # if no arguments are supplied
        parser.print_help()
        exit(1)

    args = parser.parse_args()
    verify_args(parser, args)

    print(args)

if __name__ == '__main__':
    main()
