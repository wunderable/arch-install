#! /usr/bin/python

import re
import sys
import os.path
import argparse
import subprocess

fields = [
          ('i', 'id'),
          ('p', 'parent\'s id'),
          ('n', 'name'),
          ('l', 'location'),
          ('m', 'explictly mounted (yes or no)'),
          ('r', 'permissions (read-write or read-only)'),
          ('t', 'type (subvolume or snapshot)')
        ]


###### Formatter for argparse that preservers new lines if text begins with 'R|'
class RawFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)


###### Parses args using argparse and has some additional validation that argparse can't natively handle. Returns args
def get_args(self):
    args = self.parse_args()
    match(args.cmd):
        case 'list':
            field_str = ''
            for f in fields: field_str += f[0]
            field_reg = '^[' + field_str + ']+$'
            if args.fields != None and not re.match(field_reg, args.fields):
                self.subs['list'].error('Unknown value [' + args.fields + '] for FIELDS')
            if args.sort != None and not re.match(field_reg, args.sort):
                self.subs['list'].error('Unknown value [' + args.sort + '] for SORT')
            if args.all_fields:
                args.fields = field_str
        case 'snap':
            if len(args.sources) == 1 and re.match("^[hlr]+$", args.sources[0]):
                print('abbrevs are good')
                return
            for s in args.sources:
                if not s in ['home', 'logs', 'root']:
                    self.subs['snap'].error('Unknown source [' + s + ']')
    return args


###### Get argparse instance for handling supplied arguments
def get_parser():
    main = argparse.ArgumentParser(
            prog='subv',
            description='A utility to help manage btrfs subvolumes',
            formatter_class=RawFormatter)
    main.subs = {}
    subs = main.add_subparsers(help='commands', dest='cmd')

    # List subparser
    listp = subs.add_parser('list',
                            help='list all subvolumes under /',
                            description='Outputs a list of all subvolumes under the specified path',
                            formatter_class=RawFormatter)
    main.subs['list'] = listp
    listp_help = 'R|FIELDS is a series of letters that refer to the fields that will be displayed and in what order. Default is \'il\'. Fields can be:'
    for f in fields: listp_help += '\n  ' + f[0] + '  ' + f[1]
    listp.add_argument('path', nargs='?', default='/', help='list all subvolumes under PATH. Default is /')
    listp.add_argument('-s', '--sort', default='i', help='SORT is a series of letters indicating which fields to sort by. Default is \'i\'')
    listp.add_argument('-a', '--all-fields', action='store_true', help='if present, all fields will be displayed in their default order. Overrides FIELDS if set')
    listp.add_argument('-f', '--fields', default='il', help=listp_help)
    listp_read = listp.add_mutually_exclusive_group()
    listp_read.add_argument('-r', '--read-only', action='store_true', help='filter to show subvolumes that are read-only')
    listp_read.add_argument('-R', '--read-write', action='store_true', help='filter to show subvolumes that are NOT read-only')
    listp_mount = listp.add_mutually_exclusive_group()
    listp_mount.add_argument('-m', '--mounted', action='store_true', help='filter to show subvolumes that are explicitly mounted')
    listp_mount.add_argument('-M', '--unmounted', action='store_true', help='filter to show subvolumes that are NOT explicitly mounted')
    listp_snap = listp.add_mutually_exclusive_group()
    listp_snap.add_argument('-t', '--snapshot', action='store_true', help='filter to show subvolumes that are snapshots')
    listp_snap.add_argument('-T', '--subvolume', action='store_true', help='filter to show subvolumes that are NOT snapshots')

    # Snap subparser
    snapp = subs.add_parser('snap',
                            help='create a snapshot of the specified subvolumes',
                            description='Creates a snapshot of all specified subvolumes and saves it to /.snapshots',
                            formatter_class=RawFormatter)
    main.subs['snap'] = snapp
    snapp.add_argument('-n', '--name', help='append NAME to the snapshot\'s filename')
    snapp.add_argument('sources', nargs='*',#argparse.REMAINDER,
                       help='R|the source locations to create a snapshot of. Can either be a single argument made up of only valid letter abbreviations or a list of names separated by a space\n  r  root    /\n  h  home    /home\n  l  logs    /var/logs')

    # Add a function that can be called on our instansiated objects
    argparse.ArgumentParser.get_args = get_args
    return main


###### Not implemented
def read_config():
    try:
        file = open(os.path.expandvars("$HOME/.config/subv/sources.cfg"), "r")
        for line in file:
            print(line)
    except:
        print('ERROR: There was an issue reading $HOME/.config/subv/sources.cfg', file=sys.stderr)
        exit(1)
    return True


###### A helper function to execute a command and return it's results in a string
def execute(cmd):
    return subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')


###### Returns a list of subvolumes as a tuple consisting of id, parent's id, and name
def get_subs(path):
    results = execute('sudo btrfs subvolume list -a ' + path)
    subvolumes = []
    for line in results.splitlines():
        field = line.split()
        field[8] = re.sub(r'^<FS_TREE>/', '', field[8])
        subvolumes.append((field[1], field[6], field[8]))
    return subvolumes


###### Returns a list of subvolume ids for subvolumes that are snapshots
def get_snaps(path):
    results = execute('sudo btrfs subvolume list -s ' + path)
    snaps = []
    for line in results.splitlines():
        field = line.split()
        snaps.append(field[1])
    return snaps


###### Returns a list of subvolume ids for subvolumes that are read-only
def get_ros(path):
    results = execute('sudo btrfs subvolume list -r ' + path)
    ros = []
    for line in results.splitlines():
        field = line.split()
        ros.append(field[1])
    return ros


###### Returns a list of mounted subvolumes as a tuple consisting of id, name, and mount point
def get_mounts():
    results = execute('findmnt -nl -tbtrfs')
    mounts = []
    for line in results.splitlines():
        field = line.split()
        match_id = re.search(r'subvolid=(\d+)', field[3])
        match_name = re.search(r'\[/(.*?)\]', field[1])
        mounts.append((match_id.group(1), match_name.group(1), field[0]))
    return mounts


###### Creates a 2d array of subvolume info by combining the output of multiple system calls
def get_subvolumes(path):
    subs = get_subs(path)
    snaps = get_snaps(path)
    ros = get_ros(path)
    mounts = get_mounts()
    subvolumes = []
    for s in subs:
        typ = 'subvolume'
        if s[0] in snaps:
            typ = 'snapshot'
            snaps.remove(s[0])
        r = 'rw'
        if s[0] in ros:
            r = 'r'
            ros.remove(s[0])
        mnt = 'no'
        loc = ''
        for m in mounts:
            if m[0] == s[0]:
                mnt = 'yes'
                loc = m[2]
                break
        if mnt == 'no':
            parent_dir = s[2].split('/')[0] # substring of name before first /
            for m in mounts:
                if parent_dir == m[1]:
                    loc = s[2].replace(parent_dir, m[2])
                    if m[2] == '/': loc = loc[1:]
                    break
        subvolumes.append((int(s[0]), int(s[1]), s[2], loc, mnt, r, typ))
    return subvolumes


###### Prints a 2d array to stdout
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


###### Display list of subvolumes
def exec_list(args):
    subs = get_subvolumes(args.path)
    subs = [s for s in subs if s[3].startswith(args.path)]
    if args.read_only: subs = [s for s in subs if s[5] == 'r']
    if args.read_write: subs = [s for s in subs if s[5] != 'r']
    if args.mounted: subs = [s for s in subs if s[4] == 'yes']
    if args.unmounted: subs = [s for s in subs if s[4] == 'no']
    if args.snapshot: subs = [s for s in subs if s[6] == 'snapshot']
    if args.subvolume: subs = [s for s in subs if s[6] == 'subvolume']
    for i,f in enumerate(fields):
        args.fields = args.fields.replace(f[0], str(i))
        args.sort = args.sort.replace(f[0], str(i))
    for s in reversed(args.sort):
        subs.sort(key = lambda x: x[int(s)])
    out = []
    for s in subs:
        out.append([])
        for f in args.fields:
            out[-1].append(s[int(f)])
    print_2d(out, 3)
    exit(0)


###### Create snapshot(s)
def exec_snap(args):
    print('snap: ', end=''); print(args)
    exit(0)


###### Program start
def main():
    parser = get_parser()
    if len(sys.argv) == 1: # if no arguments are supplied
        parser.print_help()
        exit(1)
    args = parser.get_args()
    match(args.cmd):
        case 'list': exec_list(args)
        case 'snap': exec_snap(args)


###### Program init
if __name__ == '__main__':
    main()
