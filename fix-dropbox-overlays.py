#!/usr/bin/env python3

""" Fix Dropbox update messing up Toirtoise* overlay handlers in Windows registry."""

__title__ = 'fix-dropbox-overlays.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020-2021 Sebastian Bank'

import argparse
import functools
import itertools
import re
import sys

COMPUTER_NAME = None

SUB_KEY = (r'SOFTWARE\Microsoft\Windows\CurrentVersion'
           r'\Explorer\ShellIconOverlayIdentifiers')


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--dry-run', action='store_true',
                    help="show what would be changed (don't write to registry)")

parser.add_argument('--version', action='version', version=__version__)


def main(args=None) -> None:
    global winreg
    import winreg

    args = parser.parse_args(args)

    handle = COMPUTER_NAME, winreg.HKEY_LOCAL_MACHINE

    log(f'winreg.ConnectRegistry(*{handle})',
        f'winreg.OpenKey(..., {SUB_KEY!r})')
    with (winreg.ConnectRegistry(*handle) as h,
          winreg.OpenKey(h, SUB_KEY) as o):

        keys = get_enum_keys(o)
        log(f'keys: {keys!r}')

        changes = list(iterchanges(keys))
        log(f'changes: {changes!r}')

        for src, dst in iterchanges(keys):
            if dst is None:
                print(f'delete {src!r}')
                if args.dry_run:
                    continue
                delete_key(o, src)
            else:
                print(f'move {src!r} to {dst!r}')
                if args.dry_run:
                    continue
                move_key(o, src, dst)

    print('done')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def get_enum_keys(key):
    (nkeys, _, _) = winreg.QueryInfoKey(key)
    log(f'for i in range({nkeys!r}): winreg.EnumKey(..., i)')
    return [winreg.EnumKey(key, i) for i in range(nkeys)]


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


def lspace_name(s: str):
    (lspace, name) = re.fullmatch(r'(\s*)(\w+)(?: \w+)?', s).groups()
    return len(lspace), name


def plain_name(lspace: int, name: str) -> str:
    return ' ' * lspace + name


def delete_key(key, sub_key):
    log(f'winreg.DeleteKey(..., {sub_key!r})')
    winreg.DeleteKey(key, sub_key)


def move_key(key, src, dst):
    log(f'winreg.QueryValue(..., {src!r})')
    value = winreg.QueryValue(key, src)

    log(f'winreg.DeleteKey(..., {src!r})')
    winreg.DeleteKey(key, src)

    log(f'winreg.CreateKey(..., {dst!r})')
    winreg.CreateKey(key, dst)

    log(f'winreg.SetValue(..., {dst!r}, {winreg.REG_SZ!r}, {value!r})')
    winreg.SetValue(key, dst, winreg.REG_SZ, value)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
