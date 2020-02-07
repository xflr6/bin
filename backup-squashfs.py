#!/usr/bin/env python3

"""Create SquashFS image from given directory and prompt for its deletion."""

__title__ = 'backup-squashfs.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import datetime
import functools
import itertools
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import time

NAME_TEMPLATE = '%Y%m%d-%H%M.sfs'

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin'

SET_UMASK = stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO


def directory(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None
    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


def template(s):
    result = datetime.datetime.now().strftime(s)
    if not result:
        raise argparse.ArgumentTypeError('empty string')
    return result


def present_file(s):
    if not s:
        return None
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None
    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return result


def user(s):
    import pwd

    try:
        pwd.getpwnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown user: {s}')
    return s


def group(s):
    import grp

    try:
        grp.getgrnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown group: {s}')
    return s


def mode(s, _mode_mask=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO):
    try:
        result = int(s, 8)
    except ValueError:
        result = None
    if result is None or not 0 <= result <= _mode_mask:
        raise argparse.ArgumentTypeError(f'need octal int between {0:03o}'
                                         f' and {_mode_mask:03o}: {s}')
    return result


def format_permissions(file_stat):

    def iterflags(mode):
        for u, f in itertools.product(('USR', 'GRP', 'OTH'), 'RWX'):
            if mode & getattr(stat, f'S_I{f}{u}'):
                yield f.lower()
            else:
                yield '-'

    mode = ''.join(iterflags(file_stat.st_mode))
    owner = pwd.getpwuid(file_stat.st_uid).pw_name
    group = grp.getgrgid(file_stat.st_gid).gr_name
    return f'file permissions: {mode} (owner={owner}, group={group})'


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('source_dir', type=directory, help='image source directory')

parser.add_argument('dest_dir', type=directory, help='image target directory')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help='image filename datetime.strftime() format string'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--exclude-file', metavar='PATH', type=present_file,
                    help='path to file with one line per blacklist item')

parser.add_argument('--comp', choices=('gzip', 'lzo', 'xz'),
                    help='compression (use mksquashfs default if omitted)')

parser.add_argument('--owner', type=user, help='image file owner')

parser.add_argument('--group', type=group, help='image file group')

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'image file chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help='PATH for mksquashfs subprocess'
                         f' (default: {SUBPROCESS_PATH})')

parser.add_argument('--set-umask', metavar='MASK', type=mode, default=SET_UMASK,
                    help='umask for mksquashfs subprocess'
                         f' (default: {SET_UMASK:03o})')

parser.add_argument('--keep', action='store_true',
                    help="don't prompt for image file deletion (exit directly)")

parser.add_argument('--quiet', action='store_true',
                    help='suppress stdout and stderr of mksquashfs subprocess')

parser.add_argument('--version', action='version', version=__version__)

args = parser.parse_args()

log = functools.partial(print, file=sys.stderr, sep='\n')

dest_path = args.dest_dir / args.name
assert not dest_path.exists()

log(f'mksquashfs source: {args.source_dir}', f'mksquashfs destination: {dest_path}')
if args.exclude_file is not None:
    log(f'mksquashfs exclude file: {args.exclude_file}')
if args.comp is not None:
    log(f'mksquashfs compression: {args.comp}')

cmd = ['mksquashfs', args.source_dir, dest_path, '-noappend']

if args.exclude_file is not None:
    cmd += ['-ef', args.exclude_file]

if args.comp is not None:
    cmd += ['-comp', args.comp]

kwargs = {'env': {'PATH': args.set_path}}
if args.quiet:
    kwargs['stdout'] = kwargs['stderr'] = subprocess.DEVNULL

log('', f'os.umask({args.set_umask:#05o})')
os.umask(args.set_umask)

log(f'subprocess.run({cmd!r}, **{kwargs})')
if not args.quiet:
    log(f'{"[ start subprocess ]":-^80}')
start = time.monotonic()
proc = subprocess.run(cmd, check=True, **kwargs)
stop = time.monotonic()
if not args.quiet:
    log(f'{"[ end subprocess ]":-^80}')
log(f'returncode: {proc.returncode}')
assert not proc.returncode
log(f'time elapsed: {datetime.timedelta(seconds=stop - start)}')

assert dest_path.exists()
dest_stat = dest_path.stat()
log(f'mksquashfs result: {dest_path} ({dest_stat.st_size} bytes)')
assert dest_stat.st_size
log(format_permissions(dest_stat))

log('', f'os.chmod(..., {args.chmod:#05o})')
dest_path.chmod(args.chmod)
if args.owner or args.group:
    log(f'shutil.chown(..., user={args.owner!r}, group={args.group!r})')
    shutil.chown(dest_path, user=args.owner, group=args.group)
log(format_permissions(dest_path.stat()))

line = 'quit' if args.keep else None
while line is None or (line != '' and line.strip().lower() not in ('q', 'quit')):
    if line is not None:
        print('  (enter q(uit) or use CTRL-C to exit and keep the file)')
    line = input(f'to delete {dest_path}, press enter [ENTER=delete]: ')

if line:
    log(f'kept {dest_path}.')
else:
    dest_path.unlink()
    log(f'{dest_path} deleted.')
