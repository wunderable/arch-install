#! /usr/bin/python

import sys
import re
import argparse
import subprocess
from datetime import datetime

class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.subs = {}
    def error(self, message):
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

def get_subvolumes():
    subvolumes_string = subprocess.run(
            ['sudo', 'btrfs', 'subvolume', 'list', '-p', '/'],
            stdout=subprocess.PIPE).stdout.decode('utf-8')
    subvolumes = []
    for line in subvolumes_string.splitlines():
        field = line.split()
        subvolumes.append((int(field[1]), int(field[5]), field[10]))
    return subvolumes

def get_mounts():
    mounts_string = subprocess.run(
            ['findmnt', '-nl', '-tbtrfs', '-osource,target'],
            stdout=subprocess.PIPE).stdout.decode('utf-8')
    mounts = []
    for line in mounts_string.splitlines():
        field = line.split()
        match = re.search(r'\[/(.*?)\]', field[0])
        mounts.append((match.group(1), field[1]))
    return mounts

def snap(args):
    if not (args.home or args.etc or args.root):
        sys.stderr.write('error: required at least one of (-h | -e | -r)\n')
        parser.subs['snap'].print_help()
        sys.exit(2)

    name = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    if args.name:
        name += '_' + args.name

    source = ''
    destination = ''
    if args.home:
        source = '/home'
        destination = '/snapshots/home/' + name
    if args.etc:
        source = '/etc'
        destination = '/snapshots/etc/' + name
    if args.root:
        source = '/'
        destination = '/snapshots/root/' + name

    subprocess.run(['sudo', 'btrfs', 'subvolume', 'snapshot', source, destination])

def list(args):
    if args.tree:
        print_tree()
        sys.exit(0)
    subvolumes = get_subvolumes()
    line_format = '{:<6} {:<6} {}'
    print(line_format.format('ID', 'Parent', 'Name'))
    if args.sort_id:
        subvolumes.sort()
    if args.sort_parent:
        subvolumes.sort(key=lambda x: (x[1], x[2]))
    if args.sort_name:
        subvolumes.sort(key=lambda x: x[2])
#    subvolumes.insert(0, (5, 0, 'TOP'))
    for item in subvolumes:
        print(line_format.format(item[0], item[1], item[2]))

def delete(args):
    if args.id:
        subprocess.run(['sudo', 'btrfs', 'subvolume', 'delete', '--subvolid', str(args.id), '/'])
        sys.exit(0)
    print('delete')

def print_tree():
#    subvolumes = get_subvolumes()
#    mounts = get_mounts()
    print('tree')

def get_parser():
    main_parser = CustomArgumentParser(prog='subv', description='Utitlity to help manage btrfs subvolumes', add_help=False)
    main_parser.add_argument('--help', action='help', help='show this help message and exit')
    sub_parsers = main_parser.add_subparsers(title='subcommands')

    snap_parser = sub_parsers.add_parser('snap', help='create a snapshot', description='Creates a snapshot', add_help=False)
    snap_parser.add_argument('-h', '--home', dest='home', action='store_true', help='create a snapshot of /home')
    snap_parser.add_argument('-e', '--etc', dest='etc', action='store_true', help='create a snapshot of /etc')
    snap_parser.add_argument('-r', '--root', dest='root', action='store_true', help='create a snapshot of /root')
    snap_parser.add_argument('-n', '--name', dest='name', help='appends NAME to the snapshot\'s name')
    snap_parser.add_argument('--help', action='help', help='show this help message and exit')
    snap_parser.set_defaults(func=snap)
    main_parser.subs['snap'] = snap_parser

    list_parser = sub_parsers.add_parser('list', help='display subvolumes', description='Display subvolumes', add_help=False)
    list_group = list_parser.add_mutually_exclusive_group()
    list_group.add_argument('-t', '--tree', dest='tree', action='store_true', help='format output as a tree')
    list_group.add_argument('-i', '--id', dest='sort_id', action='store_true', help='sort output by id number')
    list_group.add_argument('-p', '--parent', dest='sort_parent', action='store_true', help='sort output by parent\'s id number')
    list_group.add_argument('-n', '--name', dest='sort_name', action='store_true', help='sort output by name')
    list_parser.add_argument('--help', action='help', help='show this help message and exit')
    list_parser.set_defaults(func=list)
    main_parser.subs['list'] = list_parser

    delete_parser = sub_parsers.add_parser('delete', help='delete subvolumes', description='Delete subvolumes', add_help=False)
    delete_group = delete_parser.add_mutually_exclusive_group(required=True)
    delete_group.add_argument('-i', '--id', dest='id', type=int, help='deletes the subvolume having ID')
    delete_group.add_argument('-p', '--path', dest='path', help='deletes the subvolume located at PATH')
    delete_group.add_argument('-a', '--age', dest='age', help='deletes subvolumes older than AGE')
    delete_parser.add_argument('--help', action='help', help='show this help message and exit')
    delete_parser.set_defaults(func=delete)
    main_parser.subs['delete'] = delete_parser

    return main_parser

def main():
    global parser
    parser = get_parser()

    # If no arguments are supplied, show help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
