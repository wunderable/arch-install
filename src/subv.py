#! /usr/bin/python

import re
import sys
import os.path
import argparse
import subprocess
import configparser
from datetime import datetime

fields = [
          ('i', 'id'),
          ('p', 'parent\'s id'),
          ('n', 'name'),
          ('l', 'location'),
          ('m', 'explictly mounted (yes or no)'),
          ('r', 'permissions (read-write or read-only)'),
          ('s', 'type (subvolume or snapshot)')
        ]

config_path = '$HOME/.config/subv/sources.cfg'


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
            if not os.path.exists(args.path):
                self.subs['list'].error(f'path [{args.path}] not found')
            field_str = ''
            for f in fields: field_str += f[0]
            field_reg = f'^[{field_str}]+$'
            if not re.match(field_reg, args.fields):
                self.subs['list'].error(f'unknown value [{args.fields}] for FIELDS')
            if not re.match(field_reg, args.order):
                self.subs['list'].error(f'unknown value [{args.order}] for ORDER')
            if args.all_fields:
                args.fields = field_str
        case 'snap':
            names, abbrevs = read_config()
            abbrev_reg = '^['
            for a in abbrevs: abbrev_reg += a[0]
            abbrev_reg += ']+$'
            for i,s in enumerate(args.sources):
                found_name = False
                for n in names:
                    if s == n[0]:
                        args.sources[i] = n[1]
                        found_name = True
                        break
                if found_name: continue
                if re.match(abbrev_reg, s):
                    for l in s:
                        for a in abbrevs:
                            if l == a[0]:
                                args.sources.append(a[1])
                                break
                    args.sources[i] = None
            args.sources = [s for s in args.sources if s is not None]
            args.sources = list(set(args.sources))
            args.names = names
            for s in args.sources:
                if not os.path.exists(s):
                    self.subs['snap'].error(f'source [{s}] not found')
                if not execute(f'ls -id {s}').split()[0] == '256':
                    self.subs['snap'].error(f'source [{s}] is not btrfs subvolume')
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
    for f in fields: listp_help += f'\n  {f[0]}  {f[1]}'
    listp.add_argument('path', nargs='?', default='/', help='list all subvolumes under PATH. Default is /')
    listp.add_argument('-o', '--order', default='i', help='ORDER is a series of letters indicating which fields to sort by. Default is \'i\'')
    listp.add_argument('-a', '--all-fields', action='store_true', help='all fields will be displayed in their default order. Overrides FIELDS if set')
    listp.add_argument('-f', '--fields', default='il', help=listp_help)
    listp.add_argument('-u', '--skip-path-filter', action='store_true', help='don\'t filter results by path')
    listp_mount = listp.add_mutually_exclusive_group()
    listp_mount.add_argument('-m', '--mounted', action='store_true', help='filter to show subvolumes that are explicitly mounted')
    listp_mount.add_argument('-M', '--unmounted', action='store_true', help='filter to show subvolumes that are NOT explicitly mounted')
    listp_read = listp.add_mutually_exclusive_group()
    listp_read.add_argument('-r', '--read-only', action='store_true', help='filter to show subvolumes that are read-only')
    listp_read.add_argument('-R', '--read-write', action='store_true', help='filter to show subvolumes that are NOT read-only')
    listp_snap = listp.add_mutually_exclusive_group()
    listp_snap.add_argument('-s', '--snapshot', action='store_true', help='filter to show subvolumes that are snapshots')
    listp_snap.add_argument('-S', '--subvolume', action='store_true', help='filter to show subvolumes that are NOT snapshots')

    # Snap subparser
    snapp = subs.add_parser('snap',
                            help='create a snapshot of the specified subvolumes',
                            description='Creates a snapshot of all specified subvolumes and saves it to /snapshots/YYYYMMDD_HHMMSS/',
                            formatter_class=RawFormatter)
    main.subs['snap'] = snapp
    snapp.add_argument('-r', '--read-only', action='store_true', help='create the snapshot(s) as read only')
    snapp.add_argument('-n', '--name', help='append NAME to the snapshot\'s datetime folder')
    snapp.add_argument('sources', nargs='+', help='space-separated locations to create a snapshot of. It first tries to match source to a name from the config file [names] section, it then tries to match source against abbrev(s) from the [abbrevs] section, then finally treats source as a path. If a location is found in the [names] section of the config file, the snapshot will use that name, otherwise it will use the location\'s name with /\'s replaced with _\'s. i.e. if the config file [names] section contains the line "log = /var/log", the snapshot will be placed in /snapshots/20240523_161238/log, otherwise it will be placed in /snapshots/20240523_161238/_var_log')

    # Add a function that can be called on our instansiated objects
    argparse.ArgumentParser.get_args = get_args
    return main


###### Gets a list of user defined sources from a config file
def read_config():
    config_file = os.path.expandvars(config_path)
    if not os.path.isfile(config_file): return [],[]
    try:
        names = []
        abbrevs = []
        config = configparser.ConfigParser()
        config.read(config_file)
        for key in config['names']:
            names.append((key, config['names'][key]))
        for key in config['abbrevs']:
            abbrevs.append((key, config['abbrevs'][key]))
        return names, abbrevs
    except:
        print(f'WARNING: There was an issue reading {config_path}', file=sys.stderr)
        return [],[]


###### A helper function to execute a command and return it's results in a string
def execute(cmd):
    return subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')


###### Returns a list of subvolumes as a tuple consisting of id, parent's id, and name
def get_subs(path):
    results = execute(f'sudo btrfs subvolume list -a {path}')
    subvolumes = []
    for line in results.splitlines():
        field = line.split()
        field[8] = re.sub(r'^<FS_TREE>/', '', field[8])
        subvolumes.append((field[1], field[6], field[8]))
    return subvolumes


###### Returns a list of subvolume ids for subvolumes that are snapshots
def get_snaps(path):
    results = execute(f'sudo btrfs subvolume list -s {path}')
    snaps = []
    for line in results.splitlines():
        field = line.split()
        snaps.append(field[1])
    return snaps


###### Returns a list of subvolume ids for subvolumes that are read-only
def get_ros(path):
    results = execute(f'sudo btrfs subvolume list -r {path}')
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
    if not args.skip_path_filter: subs = [s for s in subs if s[3].startswith(args.path)]
    if args.read_only: subs = [s for s in subs if s[5] == 'r']
    if args.read_write: subs = [s for s in subs if s[5] != 'r']
    if args.mounted: subs = [s for s in subs if s[4] == 'yes']
    if args.unmounted: subs = [s for s in subs if s[4] == 'no']
    if args.snapshot: subs = [s for s in subs if s[6] == 'snapshot']
    if args.subvolume: subs = [s for s in subs if s[6] == 'subvolume']
    for i,f in enumerate(fields):
        args.fields = args.fields.replace(f[0], str(i))
        args.order = args.order.replace(f[0], str(i))
    for s in reversed(args.order):
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
    now = datetime.now()
    dest_dir = '/snapshots/' + now.strftime('%Y-%m-%d')
    ext = now.strftime('%Y%m%d.%H%M%S')
    if args.name != None: dest_dir += '_' + args.name
    execute(f'sudo mkdir -p {dest_dir}')
    r = '-r' if args.read_only else ''
    for src in args.sources:
        dest_name = src.replace('_', '__')
        dest_name = dest_name.replace('/', '_')
        for n in args.names:
            if src == n[1]:
                dest_name = n[0]
                break
        dest = f'{dest_dir}/{dest_name}.{ext}'
        execute(f'sudo btrfs subvolume snapshot {r} {src} {dest}')
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
