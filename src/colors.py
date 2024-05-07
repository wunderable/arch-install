#! /usr/bin/python

import sys

# themes                    black     red       green     yellow    blue      magenta   cyan      white
#                           b-black   b-red     b-green   b-yellow  b-blue    b-magenta b-cyan    b-white
themes = {}
themes['default'] =       ['000000', 'ff0000', '00ff00', 'ffff00', '0000ff', 'ff00ff', '00ffff', 'ffffff', 
                           '000000', 'ff0000', '00ff00', 'ffff00', '0000ff', 'ff00ff', '00ffff', 'ffffff']

themes['tango'] =         ['2e3436', 'cc0000', '4e9a06', 'c4a000', '3465a4', '75507b', '06989a', 'd3d7cf', 
                           '555753', 'ef2929', '8ae234', 'fce94f', '729fcf', 'ad7fa8', '34e2e2', 'eeeeec']

themes['sapphire'] =      ['000000', 'cc6666', '62a47e', 'f0c574', '80a1bd', 'b294ba', '85cbbf', 'fffefe', 
                           '000000', 'cc6666', '62a47e', 'f0c574', '80a1bd', 'b294ba', '85cbbf', 'fffefe']

themes['solar-dark'] =    ['073642', 'dc322f', '859900', 'b58900', '268bd2', 'd33682', '2aa198', 'eee8d5',
                           '002b36', 'cb4b16', '586e75', '657b83', '839496', '6c71c4', '93a1a1', 'fdf6e3']

themes['gruv-dark'] =     ['282828', 'cc241d', '98971a', 'd79921', '458488', 'b16286', '689d6a', 'a89984',
                           '928374', 'fb4934', 'b8bb26', 'fabd2f', '83a598', 'd3869b', '8ec07c', 'fbf1c7']

names = ['bla', 'red', 'gre', 'yel', 'blu', 'mag', 'cya', 'whi', 'b bla', 'b red', 'b gre', 'b yel', 'b blu', 'b mag', 'b cya', 'b whi' ]


# Prints 16 basic terminal colors \e[30
def print_basic():
    out = ['', '', '', '']
    for i in range(8):
        out[0] += '\x1b[%sm%s\x1b[0m ' % (30+i, names[i])
        out[1] += '\x1b[%sm%s\x1b[0m ' % (90+i, names[i])
        out[2] += '\x1b[%sm   \x1b[0m ' % (40+i)
        out[3] += '\x1b[%sm   \x1b[0m ' % (100+i)
    for i in range(4): print(out[i])
    exit(0)


# Prints 256 extended terminal colors \e[38;5;n
def print_extended(bg):
    cols = 146
    color = '\x1b[48;5;%sm  \x1b[48;5;{0}m \x1b[48;5;%s;38;5;{0}m{0:03}\x1b[0m' % (bg,bg)
    space = '\x1b[48;5;%sm \x1b[0m' % bg
    print(space * cols)
    for n in range(0,8): print(color.format(n), end='')
    print(space * (cols-48))
    for n in range(8,16): print(color.format(n), end='')
    print(space * (cols-48))
    print(space * cols)
    for a in range(2):
        for b in range(6):
            for c in range(3):
                for d in range(6):
                    n = a*18+b*36+c*6+d+16
                    print(color.format(n), end='')
                print(space * 2, end='')
            print(space * (cols-114))
        print(space * cols)
    for n in range(232,256): print(color.format(n), end='')
    print(space * 2)
    print(space * cols)
    exit(0)


def list_themes():
    color = '\x1b[48;2;{0};{1};{2}m   \x1b[0m'
    for theme in themes.keys():
        print('%s' % theme.ljust(30), end='')
        for n in range(16):
            r = int(themes[theme][n][0:2], 16)
            g = int(themes[theme][n][2:4], 16)
            b = int(themes[theme][n][4:6], 16)
            print(color.format(r,g,b),end='')
        print()
    exit(0)


def set_theme(theme):
    for i in range(16):
        print('\x1b]P%s%s' % (hex(i).split('x')[-1].upper(), theme[i].upper()), end='')
    exit(0)


def parse_args():
    if '-h' in sys.argv: print_help()
    if len(sys.argv) == 1: print_basic()
    if sys.argv[1] == '256': print_extended(0)
    if sys.argv[1].isdigit() and 0 <= int(sys.argv[1]) <= 255: print_extended(sys.argv[1])
    if sys.argv[1] == 'themes': list_themes()
    if sys.argv[1] in themes.keys(): set_theme(themes[sys.argv[1]])
    print('[%s] theme not found!' % sys.argv[1])
    exit(0)


def print_help():
    print('''colors              Prints 16 base colors using both foreground and background
colors 256          Prints 256 colors
colors <0..255>     Prints 256 colors using specified background
colors themes       Prints a list of available themes
colors <theme>      Sets the terminal to use <theme> ''')
    exit(0)


def main():
    parse_args()

if __name__ == '__main__':
    main()
