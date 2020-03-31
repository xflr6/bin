""" Fix Dropbox update messing up Toirtoise* overlay handlers in Windows registry."""

from __future__ import print_function

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

parser.add_argument('--version', action='version', version=__version__)


def lspace_name(s):
    lspace, name = re.match(r'(\s*)(\w+)$', s).groups()
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
    if sys.version_info.major == 2:
        import _winreg as winreg
    else:
        import winreg

    args = parser.parse_args(args)

    handle = COMPUTER_NAME, winreg.HKEY_LOCAL_MACHINE

    log('winreg.ConnectRegistry({!r}, {!r})'.format(*handle),
        'winreg.OpenKey(..., {!r})'.format(SUB_KEY))
    with winreg.ConnectRegistry(*handle) as h,\
         winreg.OpenKey(h, SUB_KEY) as o:

        nkeys, _, _ = winreg.QueryInfoKey(o)
        log('for i in range({!r}): winreg.EnumKey(..., i)'.format(nkeys))
        keys = [winreg.EnumKey(o, i) for i in range(nkeys)]
        log('keys: {!r}'.format(keys))

        changes = list(iterchanges(keys))
        log('changes: {!r}'.format(changes))

        for src, dst in iterchanges(keys):
            if dst is None:
                print('delete {!r}'.format(src))

                log('winreg.DeleteKey(..., {!r})'.format(src))
                winreg.DeleteKey(o, src)

            else:
                print('move {!r} to {!r}'.format(src, dst))

                log('winreg.QueryValue(..., {!r})'.format(src))
                value = winreg.QueryValue(o, src)

                log('winreg.DeleteKey(..., {!r})'.format(src))
                winreg.DeleteKey(o, src)
                log('winreg.CreateKey(..., {!r})'.format(dst))
                winreg.CreateKey(o, dst)

                args = o, dst, winreg.REG_SZ, value
                log('winreg.SetValue(..., {!r}, {!r}, {!r})'.format(*args[1:]))
                winreg.SetValue(o, *args)

    print('done')
    return None


if __name__ == '__main__':
    sys.exit(main())
