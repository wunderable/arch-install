#! /usr/bin/python

import re
import sys
import os.path
import argparse
import subprocess
import configparser
from datetime import datetime
from argparse import Namespace

fields = [
          ('i', 'ID',       'id'),                                      # id
          ('p', 'PID',      'parent\'s id'),                            # pid
          ('n', 'Name',     'name'),                                    # name
          ('l', 'Loc',      'location'),                                # loc
          ('t', 'Time',     'datetime'),                                # time
          ('m', 'Mount',    'mount type'),                              # mnt
          ('r', 'Read',     'permissions (read-write or read-only)'),   # read
          ('s', 'Snap',     'type (subvolume or snapshot)')             # snap
        ]

config_path = '/etc/subv.conf'


###### Custom class for ArgumentParser to tweak some functionality
class CustomArgumentParser(argparse.ArgumentParser):

    # Display error message followed by usage, instead of default of usage followed by error message
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_usage()
        sys.exit(2)


###### Custom class for HelpFormatter to tweak some functionality
class CustomHelpFormatter(argparse.HelpFormatter):

    # Moves the help message over 35 characters instead of default 24
    def __init__(self, prog, indent_increment=2, max_help_position=35, width=None):
        return super().__init__(prog, indent_increment, max_help_position, width)

    # Preserves new lines if text begins with 'R|'
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        return super()._split_lines(text, width)
    
    # Adding a helper function to remove aliases from SubParserAction
    def _remove_aliases(self, action):
        if not isinstance(action, argparse._SubParsersAction): return action
        unique = {}
        for choice in action.choices:
            prog = action.choices[choice].prog
            if prog not in unique: unique[prog] = choice
        removed = {}
        for choice in unique.values():
            removed[choice] = action.choices[choice]
        action.choices = removed
        return action
    
    # Remove aliases from actions
    def add_usage(self, usage, actions, groups, prefix=None):
        for action in actions:
            self._remove_aliases(action)
        return super().add_usage(usage, actions, groups, prefix)
    
    # Removes aliases between ()'s in subcommand help text
    def _format_action_invocation(self, action):
        if isinstance(action, argparse._SubParsersAction._ChoicesPseudoAction):
            action.metavar = re.sub(r'\(.*?\)$', '', action.metavar)
        return super()._format_action_invocation(action)


###### Converts a command into a list of aliases (shortcuts) for that command
def create_aliases(cmd):
    aliases = []
    for i,_ in enumerate(cmd):
        aliases.append(cmd[:i])
    del aliases[0]
    return aliases


###### Parses args using argparse and has some additional validation that argparse can't natively handle. Returns args
def get_args(self, config):
    args = self.parse_args()
    if args.cmd in create_aliases('list'): args.cmd = 'list'
    if args.cmd in create_aliases('snap'): args.cmd = 'snap'
    if args.cmd in create_aliases('restore'): args.cmd = 'restore'
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
            if args.name is not None:
                if not any(name[0] == args.name for name in config.names):
                    self.subs['list'].error(f'unknown value [{args.name}] for NAME')
        case 'snap':
            abbrev_reg = '^['
            for a in config.abbrevs: abbrev_reg += a[0]
            abbrev_reg += ']+$'
            if len(config.abbrevs) < 1: abbrev_reg = '^$' # if no abbrevs are set in config file
            for i, s in enumerate(args.sources):
                # A - First check if the source is a name in the config file
                found_name = False
                for n in config.names:
                    if s == n[0]:
                        args.sources[i] = n[1] # replace the source name with the path from the config file
                        found_name = True
                        break
                if found_name: continue
                # B - Then check if the source matches any of the abbrevs set in the config file
                if re.match(abbrev_reg, s): # if a source contains only abbrev letters
                    for l in s: # loop through each letter of the source
                        for a in config.abbrevs:
                            if l == a[0]:
                                args.sources.append(a[1]) # add the abbrev path to the end of the sources list
                                break
                    args.sources[i] = None # set the sources element to None so it can be filtered out
                # C - Otherwise treat source as a path
            args.sources = [s for s in args.sources if s is not None] # filter out elements that aren't needed
            args.sources = list(set(args.sources)) # removes duplicate paths from the sources list
            for s in args.sources:
                if not os.path.exists(s):
                    self.subs['snap'].error(f'source [{s}] not found')
                if not execute(f'ls -id {s}').split()[0] == '256':
                    self.subs['snap'].error(f'source [{s}] is not btrfs subvolume')
        case 'restore':
            subs = get_subvolumes(args.path)
    args.config = config
    return args


###### Get argparse instance for handling supplied arguments
def get_parser(config):
    main = CustomArgumentParser(prog='subv', description='A utility to help manage btrfs subvolumes', formatter_class=CustomHelpFormatter)
    main.subs = {}
    subs = main.add_subparsers(help='commands', dest='cmd')

    # List subparser
    listp = subs.add_parser('list', aliases=create_aliases('list'), help='list all subvolumes under /', description='Outputs a list of subvolumes in a btrfs filesystem', formatter_class=CustomHelpFormatter)
    main.subs['list'] = listp
    listp_fields_help = 'R|FIELDS is a series of letters that refer to the fields that will be displayed and in what order. Default is \'il\'. Fields can be:'
    listp_all_fields_help = 'all fields will be displayed. Equivelant to setting FIELDS to \''
    for f in fields:
        listp_fields_help += f'\n  {f[0]}  {f[2]}'
        listp_all_fields_help += f[0]
    listp_all_fields_help += '\'. Will override FIELDS if set'
    listp.add_argument('PATH', default=config.path, nargs='?', help='location of btrfs filesystem to list subvolumes from. Default is defined in /etc/subv.conf, otherwise it\'s \'/\'')
    listp.add_argument('-f', '--fields', default='il', help=listp_fields_help)
    listp.add_argument('-o', '--order', default='i', help='ORDER is a series of letters indicating which fields to sort by. Uppercase letters will reverse the sort order. Default is \'i\'')
    listp.add_argument('-t', '--titles', action='store_true', help='display field titles on output')
    listp.add_argument('-a', '--all-fields', action='store_true', help=listp_all_fields_help)
    listp.add_argument('-n', '--name', help='filter to only show subvolumes with NAME where NAME is defined in /etc/subv.conf')
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
    snapp = subs.add_parser('snap', aliases=create_aliases('snap'), help='create a snapshot of the specified subvolumes', description='Creates a snapshot of all specified subvolumes and saves it to /snapshots/YYYY-MM-DD/name.YYYYMMDD.HHMMSS', formatter_class=CustomHelpFormatter)
    main.subs['snap'] = snapp
    snapp.add_argument('-r', '--read-only', action='store_true', help='create the snapshot(s) as read only')
    snapp.add_argument('-n', '--name', help='append NAME to the snapshot\'s parent folder')
    snapp.add_argument('sources', nargs='+', help='space-separated locations to create a snapshot of. It first tries to match source to a name from the config file [names] section, it then tries to match source against abbrev(s) from the [abbrevs] section, then finally treats source as a path. If a location is found in the [names] section of the config file, the snapshot will use that name, otherwise it will use the location\'s name with /\'s replaced with _\'s. i.e. if the config file [names] section contains the line "log = /var/log", the snapshot will be placed in /snapshots/2024-05-23/log.20240523.153211, otherwise it will be placed in /snapshots/2024-05-23/_var_log.20240523.153211')

    # Restore subparser
    restp = subs.add_parser('restore', aliases=create_aliases('restore'), help='restore an earlier snapshot', formatter_class=CustomHelpFormatter)
    main.subs['restore'] = restp
    restp.add_argument('-p', '--path', default='/', help='path to find the snapshot ids under. Default is \'/\'')
    restp.add_argument('-k', '--keep-current', action='store_true', help='creates a snapshot of the location before restoring it to a previous version')
    restp.add_argument('ids', nargs='*', help='space-separated list of ids of the snapshots to restore')

    # Add a function that can be called on our instansiated objects
    argparse.ArgumentParser.get_args = get_args
    return main


###### Gets a list of user defined sources from a config file
def read_config():
    config = Namespace(path='/', names=[], abbrevs=[])
    config_file = os.path.expandvars(config_path)
    if not os.path.isfile(config_file): return config
    try:
        config_parser = configparser.ConfigParser()
        config_parser.read(config_file)
        if 'settings' in config_parser and 'default_path' in config_parser['settings']:
            config.path = config_parser['settings']['default_path']
        if 'names' in config_parser:
            for key in config_parser['names']:
                config.names.append((key, config_parser['names'][key]))
        if 'abbrevs' in config_parser:
            for key in config_parser['abbrevs']:
                config.abbrevs.append((key, config_parser['abbrevs'][key]))
    except:
        print(f'WARNING: There was an issue reading {config_path}', file=sys.stderr)
    return config


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
                    path = mount[2] if mount[2] != '/' else '' # if path is just /, remove it to avoid double //
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
    if args.name: subs = [s for s in subs if re.compile(fr'{args.name}\.\d{{8}}\.\d{{6}}$').search(s[3])]
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
        for n in args.config.names:
            if src == n[1]:
                dest_name = n[0]
                break
        dest = f'{dest_dir}/{dest_name}.{ext}'
        execute(f'sudo btrfs subvolume snapshot {r} {src} {dest}')
    exit(0)


###### Restore to an earlier snapshot
def exec_restore(args):
    print('restore')
    exit(0)


###### Program start
def main():
    config = read_config()
    parser = get_parser(config)
    if len(sys.argv) == 1: # if no arguments are supplied
        parser.print_help()
        exit(1)
    args = parser.get_args(config)
    match(args.cmd):
        case 'list': exec_list(args)
        case 'snap': exec_snap(args)
        case 'restore': exec_restore(args)

###### Program init
if __name__ == '__main__':
    main()
