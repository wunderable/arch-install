#! /usr/bin/python

import re
import sys
import os.path
import argparse
import subprocess
import configparser
from datetime import datetime

fields = [
          ('i', 'ID',   'id'),                                      # id
          ('p', 'PID',  'parent\'s id'),                            # pid
          ('n', 'Name', 'name'),                                    # name
          ('l', 'Loc',  'location'),                                # loc
          ('t', 'Time', 'datetime'),                                # time
          ('m', 'Mount',  'mount type'),                              # mnt
          ('r', 'Read', 'permissions (read-write or read-only)'),   # read
          ('s', 'Snap', 'type (subvolume or snapshot)')             # snap
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
            args.path = args.PATH
            if not os.path.exists(args.path):
                self.subs['list'].error(f'path [{args.path}] not found')
            if os.stat(args.path).st_ino != 256:
                self.subs['list'].error(f'path [{args.path}] is not btrfs')
            field_str = ''
            for f in fields: field_str += f[0]
            field_reg = f'^[{field_str}]+$'
            if not re.match(field_reg, args.fields):
                self.subs['list'].error(f'unknown value [{args.fields}] for FIELDS')
            if not re.match(field_reg, args.order, re.IGNORECASE):
                self.subs['list'].error(f'unknown value [{args.order}] for ORDER')
            if args.all_fields:
                args.fields = field_str
        case 'snap':
            names, abbrevs = read_config()
            abbrev_reg = '^['
            for a in abbrevs: abbrev_reg += a[0]
            abbrev_reg += ']+$'
            if len(abbrevs) < 1: abbrev_reg = '^$'
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
    main = argparse.ArgumentParser(prog='subv', description='A utility to help manage btrfs subvolumes', formatter_class=RawFormatter)
    main.subs = {}
    subs = main.add_subparsers(help='commands', dest='cmd')

    # List subparser
    listp = subs.add_parser('list', help='list all subvolumes under /', description='Outputs a list of subvolumes in a btrfs filesystem', formatter_class=RawFormatter)
    main.subs['list'] = listp
    listp_fields_help = 'R|FIELDS is a series of letters that refer to the fields that will be displayed and in what order. Default is \'il\'. Fields can be:'
    listp_all_fields_help = 'all fields will be displayed. Equivelant to setting FIELDS to \''
    for f in fields:
        listp_fields_help += f'\n  {f[0]}  {f[2]}'
        listp_all_fields_help += f[0]
    listp_all_fields_help += '\'. Will override FIELDS if set'
    listp.add_argument('PATH', default='/', nargs='?', help='location of btrfs filesystem to list subvolumes from. Default is \'/\'')
    listp.add_argument('-f', '--fields', default='il', help=listp_fields_help)
    listp.add_argument('-o', '--order', default='i', help='ORDER is a series of letters indicating which fields to sort by. Uppercase letters will reverse the sort order. Default is \'i\'')
    listp.add_argument('-t', '--titles', action='store_true', help='display field titles on output')
    listp.add_argument('-a', '--all-fields', action='store_true', help=listp_all_fields_help)
    listp.add_argument('-p', '--filter-paths', action='store_true', help='filter to only show subvolumes that are under PATH')
    listp_mount = listp.add_mutually_exclusive_group()
    listp_mount.add_argument('-m', '--mounted', action='store_true', help='filter to only show subvolumes that are mounted')
    listp_mount.add_argument('-M', '--unmounted', action='store_true', help='filter to only show subvolumes that are NOT mounted')
    listp_read = listp.add_mutually_exclusive_group()
    listp_read.add_argument('-r', '--read-only', action='store_true', help='filter to only show subvolumes that are read-only')
    listp_read.add_argument('-R', '--read-write', action='store_true', help='filter to only show subvolumes that are NOT read-only')
    listp_snap = listp.add_mutually_exclusive_group()
    listp_snap.add_argument('-s', '--snapshot', action='store_true', help='filter to only show subvolumes that are snapshots')
    listp_snap.add_argument('-S', '--subvolume', action='store_true', help='filter to only show subvolumes that are NOT snapshots')
    listp.add_argument('-B', '--before', help='filter to only show subvolumes with a datetime before BEFORE')
    listp.add_argument('-A', '--after', help='filter to only show subvolumes with a datetime after AFTER')

    # Snap subparser
    snapp = subs.add_parser('snap', help='create a snapshot of the specified subvolumes', description='Creates a snapshot of all specified subvolumes and saves it to /snapshots/YYYYMMDD_HHMMSS/', formatter_class=RawFormatter)
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
    return subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode('utf-8')


###### Returns a list of subvolumes as a tuple consisting of id, parent's id, and name
def get_subs(path):
    results = execute(f'sudo btrfs subvolume list -a {path}')
    subvolumes = [('5', '0', '/')]
    for line in results.splitlines():
        field = line.split()
        if field[8].startswith('<FS_TREE>'):
            loc = field[8].replace('<FS_TREE>', '', 1)
        else:
            loc = '/' + field[8]
        subvolumes.append((field[1], field[6], loc))
    return subvolumes # [(id, pid, loc)]


###### Returns a list of subvolume ids for subvolumes that are snapshots
def get_snaps(path):
    results = execute(f'sudo btrfs subvolume list -s {path}')
    snaps = []
    for line in results.splitlines():
        field = line.split()
        snaps.append(field[1])
    return snaps # [id]


###### Returns a list of subvolume ids for subvolumes that are read-only
def get_ros(path):
    results = execute(f'sudo btrfs subvolume list -r {path}')
    ros = []
    for line in results.splitlines():
        field = line.split()
        ros.append(field[1])
    return ros # [id]


###### Returns a list of mounted subvolumes as a tuple consisting of id, name, and mount point
def get_mounts():
    results = execute('findmnt -nl -tbtrfs')
    mounts = []
    for line in results.splitlines():
        field = line.split()
        match_id = re.search(r'(?<=\bsubvolid=)\d+', field[3])
        match_name = re.search(r'(?<=\bsubvol=)[^,]*', field[3])
        mounts.append((match_id.group(0), match_name.group(0), field[0]))
    mounts = sorted(mounts, key=lambda x: x[1].count('/'), reverse=True) # sort descending by number of /'s in name
    return mounts # [(id, name, loc)]


###### Returns details from a subvolume
def get_details(path):
    results = execute(f'sudo btrfs subvolume show {path}')
    match_name = re.search(r'Name:\s+(.+)', results)
    match_time = re.search(r'Creation time:\s+(.+)', results)
    match_err = re.search(r'ERROR: not a btrfs filesystem', results)
    name = match_name.group(1) if match_name else '-'
    time = match_time.group(1) if match_time else '-'
    mount = False
    if match_err:
        #TODO: Attempt to unmount path, retrieve subvolume info again, and re-mount path
        name = '-'
        time = '-'
        mount = True
    return [name, time, mount] # (name, time, mount)


###### Creates a 2d array of subvolume info by combining the output of multiple system calls
def get_subvolumes(path):
    subs = get_subs(path) # [(id, pid, loc)]
    snaps = get_snaps(path) # [id]
    ros = get_ros(path) # [id]
    mounts = get_mounts() # [(id, name, loc)]
    subvolumes = []
    for sub in subs:
        # Set type to subvolume or snapshot
        typ = 'subvolume'
        if sub[0] in snaps:
            typ = 'snapshot'
            snaps.remove(sub[0])
        # Set permissions to r (read) or rw (read/write)
        r = 'rw'
        if sub[0] in ros:
            r = 'r'
            ros.remove(sub[0])
        # Set loc to explicitly mounted location and mnt to either - or btrfs
        mnt = '-'
        loc = '-'
        for mount in mounts:
            if mount[0] == sub[0]:
                mnt = 'btrfs'
                loc = mount[2]
                break
        # Set loc to implicitly mounted location
        if mnt != 'btrfs':
            for mount in mounts:
                if sub[2].startswith(mount[1]):
                    path = mount[2] if mount[2] != '/' else '' # if path is just /, remove it to avoid double /
                    if mount[1] == '/': path += '/' # if mount name is just /, append a / to path to avoid missing /
                    loc = sub[2].replace(mount[1], path, 1)
                    break
        # Set name and time
        details = get_details(loc)
        if details[0] == '-':
            details[0] = sub[2].rsplit('/', 1)[-1] if sub[0] != '5' else '<FS_TREE>'
        if details[2]: mnt = execute(f'findmnt -nl {loc}').split()[2] # subvolume is mounted as another mount type, get that type
        subvolumes.append((int(sub[0]), int(sub[1]), details[0], loc, details[1], mnt, r, typ))
    return subvolumes # (id, pid, name, loc, time, mnt, read, snap)


###### Prints a 2d array to stdout
def print_2d(arr, spaces=1, header=None):
    lengths = [0]*len(arr)
    if header is not None:
        for i, item in enumerate(header):
            lengths[i] = len(str(item))
    for row in arr:
        for i, item in enumerate(row):
            if len(str(item)) > lengths[i]:
                lengths[i] = len(str(item))
    if header is not None:
        for i, item in enumerate(header):
            print(item, end='')
            print(' ' * (lengths[i] - len(str(item)) + spaces), end='')
        print()
        for i, item in enumerate(header):
            print('-' * lengths[i], end='')
            print(' ' * spaces, end='')
        print()
    for row in arr:
        for i, item in enumerate(row):
            print(item, end='')
            print(' ' * (lengths[i] - len(str(item)) + spaces), end='')
        print()


###### Display list of subvolumes
def exec_list(args):
    subs = get_subvolumes(args.path) # (id, pid, name, loc, time, mnt, read, snap)
    if args.filter_paths: subs = [s for s in subs if s[3].startswith(args.path)]
    if args.read_only: subs = [s for s in subs if s[6] == 'r']
    if args.read_write: subs = [s for s in subs if s[6] != 'r']
    if args.mounted: subs = [s for s in subs if s[5] != '-']
    if args.unmounted: subs = [s for s in subs if s[5] == '-']
    if args.snapshot: subs = [s for s in subs if s[7] == 'snapshot']
    if args.subvolume: subs = [s for s in subs if s[7] == 'subvolume']
    if args.before: subs = [s for s in subs if s[4] < args.before]
    if args.after: subs = [s for s in subs if s[4] > args.after]
    field_dictionary = {}
    for i,f in enumerate(fields):
        field_dictionary[f[0]] = i
    for o in reversed(args.order):
        if o.islower():
            subs.sort(key = lambda x: x[field_dictionary[o]])
        else:
            subs.sort(key = lambda x: x[field_dictionary[o.lower()]], reverse = True)
    out = []
    for s in subs:
        out.append([])
        for f in args.fields:
            out[-1].append(s[field_dictionary[f]])
            if f == 'p' and out[-1][-1] == 0: out[-1][-1] = '-' # replace parent id of 0 with -
    if args.titles:
        header = []
        for f in args.fields:
            header.append(fields[field_dictionary[f]][1])
    else:
        header = None
    print_2d(out, 3, header)
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
