#!python3

""" Fix Dropbox update messing up Toirtoise* overlay handlers in Windows registry."""

__title__ = 'fix-dropbox-overlays.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import itertools
import re
import sys

COMPUTER_NAME = None

SUB_KEY = (r'SOFTWARE\Microsoft\Windows\CurrentVersion'
           r'\Explorer\ShellIconOverlayIdentifiers')


log = functools.partial(print, file=sys.stderr, sep='\n')


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--dry-run', action='store_true',
                    help="show what would be changed (don't write to registry)")

parser.add_argument('--version', action='version', version=__version__)


def lspace_name(s):
    lspace, name = re.fullmatch(r'(\s*)(\w+)', s).groups()
    return len(lspace), name


def plain_name(lspace, name):
    return ' ' * lspace + name


def iterchanges(keys):
    pairs = map(lspace_name, keys)
    pairs = sorted(pairs, key=lambda x: (-x[0], x[1]))

    grouped = itertools.groupby(pairs, lambda x: x[0])
    grouped = [(ls, [n for _, n in g]) for ls, g in grouped]

    for (ls, ln), (rs, rn) in itertools.combinations(grouped, 2):
        if ln[:len(rn)] == rn:
            break
    else:
        return

    assert all(n.startswith('DropboxExt') for n in (ln + rn))

    for name in rn:
        yield plain_name(rs, name), None  # delete

    for name in ln:
        yield plain_name(ls, name), plain_name(rs, name)  # move


def main(args=None):
    import winreg

    args = parser.parse_args(args)

    handle = COMPUTER_NAME, winreg.HKEY_LOCAL_MACHINE

    log(f'winreg.ConnectRegistry(*{handle})',
        f'winreg.OpenKey(..., {SUB_KEY!r})')
    with winreg.ConnectRegistry(*handle) as h,\
         winreg.OpenKey(h, SUB_KEY) as o:

        nkeys, _, _ = winreg.QueryInfoKey(o)
        log(f'for i in range({nkeys!r}): winreg.EnumKey(..., i)')
        keys = [winreg.EnumKey(o, i) for i in range(nkeys)]
        log(f'keys: {keys!r}')

        changes = list(iterchanges(keys))
        log(f'changes: {changes!r}')

        for src, dst in iterchanges(keys):
            if dst is None:
                print(f'delete {src!r}')
                if args.dry_run:
                    continue

                log(f'winreg.DeleteKey(..., {src!r})')
                winreg.DeleteKey(o, src)

            else:
                print(f'move {src!r} to {dst!r}')
                if args.dry_run:
                    continue

                log(f'winreg.QueryValue(..., {src!r})')
                value = winreg.QueryValue(o, src)

                log(f'winreg.DeleteKey(..., {src!r})')
                winreg.DeleteKey(o, src)
                log(f'winreg.CreateKey(..., {dst!r})')
                winreg.CreateKey(o, dst)

                log('winreg.SetValue(..., {dst!r}, {winreg.REG_SZ!r}, {value!r})')
                winreg.SetValue(o, dst, winreg.REG_SZ, value)

    print('done')
    return None


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
