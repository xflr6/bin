#!/usr/bin/env python3

""" Fix Dropbox update messing up Toirtoise* overlay handlers in Windows registry."""

__title__ = 'fix-dropbox-overlays.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020-2021 Sebastian Bank'

import argparse
from collections.abc import Iterable, Iterator
import functools
import itertools
import pprint
import re
import sys

KEY = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers'

COMPUTER_NAME = None  # local


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--dry-run', action='store_true',
                    help="show what would be changed (don't write to registry)")

parser.add_argument('--version', action='version', version=__version__)


def fix_dropbox_overlays(*, dry_run: bool) -> None:
    global winreg
    import winreg

    (h_key, _, sub_key) = KEY.partition('\\')
    h_key = getattr(winreg, h_key)

    log(f'winreg.ConnectRegistry({COMPUTER_NAME}, {h_key})',
        f'winreg.OpenKey(..., {sub_key!r})')
    with (winreg.ConnectRegistry(COMPUTER_NAME, h_key) as handle,
          winreg.OpenKey(handle, sub_key) as sub_key):
        (nkeys, _, _) = winreg.QueryInfoKey(sub_key)
        log(f'for i in range({nkeys!r}): winreg.EnumKey(..., i)')
        keys = [winreg.EnumKey(sub_key, i) for i in range(nkeys)]
        log('keys:')
        pprint.pp(keys, stream=sys.stderr)

        changes = list(iterchanges(keys))
        log(f'changes: {changes!r}')
        for src, dst in iterchanges(keys):
            if dst is None:
                print(f'delete {src!r}')
                if not dry_run:
                    log(f'winreg.DeleteKey(..., {src!r})')
                    winreg.DeleteKey(sub_key, src)
            else:
                print(f'move {src!r} to {dst!r}')
                if not dry_run:
                    log(f'winreg.QueryValue(..., {src!r})')
                    value = winreg.QueryValue(sub_key, src)

                    log(f'winreg.DeleteKey(..., {src!r})')
                    winreg.DeleteKey(sub_key, src)

                    log(f'winreg.CreateKey(..., {dst!r})')
                    winreg.CreateKey(sub_key, dst)

                    log(f'winreg.SetValue(..., {dst!r}, {winreg.REG_SZ!r}, {value!r})')
                    winreg.SetValue(sub_key, dst, winreg.REG_SZ, value)

    print('done')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def iterchanges(keys: Iterable[str], /) -> Iterator[tuple[str, str | None]]:
    pairs = map(indent_name, keys)
    pairs = sorted(pairs, key=lambda x: (-x[0], x[1]))

    grouped = itertools.groupby(pairs, lambda x: x[0])
    grouped = [(indent, [n for _, n in g]) for indent, g in grouped]
    for (x_indent, x_name), (y_indent, y_name) in itertools.combinations(grouped, 2):
        if x_name[:len(y_name)] == y_name:
            break
    else:
        return

    assert all(n.startswith('DropboxExt') for n in (x_name + y_name))

    for name in y_name:  # delete
        yield plain_name(y_indent, name), None
    for name in x_name:  # move
        yield plain_name(x_indent, name), plain_name(y_indent, name)


def indent_name(s: str, /) -> tuple[int, str]:
    ma = re.fullmatch(r'(?P<indent>\s*)(?P<name>\w+)(?: \w+)?', s)
    return len(ma['indent']), ma['name']


def plain_name(indent: int, name: str) -> str:
    return ' ' * indent + name


def main(args=None) -> None:
    args = parser.parse_args(args)
    return fix_dropbox_overlays(dry_run=args.dry_run)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
