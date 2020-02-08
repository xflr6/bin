#!/usr/bin/env python3

"""Create tar archive from given directory and prompt for its deletion."""

__title__ = 'backup-tar.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import datetime
import functools
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import time

NAME_TEMPLATE = '%Y%m%d-%H%M.tar.gz'

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'

SET_UMASK = stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO

ENCODING = 'utf-8'


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


def iterfiles(root, infos=None, sep=os.sep):
    n_dirs = n_files = n_symlinks = n_other = n_bytes = 0

    stack = [('', root)]
    while stack:
        prefix, root = stack.pop()
        try:
            dentries = os.scandir(root)
        except OSError as e:
            log(e)
            continue

        dirs = []
        for d in dentries:
            path = prefix + d.name
            yield path

            if d.is_file():
                n_files += 1
                n_bytes += d.stat(follow_symlinks=False).st_size
            elif d.is_dir(follow_symlinks=False):
                dirs.append((path + sep, d))
            elif d.is_symlink():
                n_symlinks += 1
            else:
                n_other += 1

        stack.extend(reversed(dirs))
        n_dirs += len(dirs)

    if infos is not None:
        infos.update(n_items=sum([n_dirs, n_files, n_symlinks, n_other]),
                     n_dirs=n_dirs, n_files=n_files, n_symlinks=n_symlinks,
                     n_other=n_other,
                     n_bytes=n_bytes)


def format_permissions(file_stat):
    import pwd, grp, itertools

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

parser.add_argument('source_dir', type=directory, help='archive source directory')

parser.add_argument('dest_dir', type=directory, help='directory for tar archive')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help='archive filename datetime.strftime() format string'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--exclude-file', metavar='PATH', type=present_file,
                    help='path to file with one line per blacklist item')

parser.add_argument('--no-auto-compress', action='store_true',
                    help="don't pass --auto-compress to tar")

parser.add_argument('--owner', type=user, help='tar archive owner')

parser.add_argument('--group', type=group, help='tar archive group')

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'tar archive chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help=f'PATH for tar subprocess (default: {SUBPROCESS_PATH})')

parser.add_argument('--set-umask', metavar='MASK', type=mode, default=SET_UMASK,
                    help=f'umask for tar subprocess (default: {SET_UMASK:03o})')

parser.add_argument('--keep', action='store_true',
                    help="don't prompt for image file deletion (exit directly)")

parser.add_argument('--version', action='version', version=__version__)

args = parser.parse_args()

log = functools.partial(print, file=sys.stderr, sep='\n')

dest_path = args.dest_dir / args.name
assert not dest_path.exists()

log(f'tar source: {args.source_dir}', f'tar destination {dest_path}')

infos = {}
files = sorted(iterfiles(args.source_dir, infos=infos))
log('traversed source: (', end='')
counts = 'dirs', 'files', 'symlinks', 'other'
log(*(f"{infos['n_' + c]} {c}" for c in counts), sep=', ', end=')\n')
log(f"file size sum: {infos['n_bytes']} bytes")

cmd = ['tar', '--create', '--file', dest_path,
       '--files-from', '-', '--null', '--verbatim-files-from']

if args.exclude_file is not None:
    cmd += ['--exclude-from', args.exclude_file]

if not args.no_auto_compress:
    cmd.append('--auto-compress')

kwargs = {'cwd':  args.source_dir,
          'env': {'PATH': args.set_path},
          'encoding': ENCODING}

log('', f'os.umask({args.set_umask:#05o})')
os.umask(args.set_umask)

log(f'subprocess.Popen({cmd}, **{kwargs})')
start = time.monotonic()
with subprocess.Popen(cmd, stdin=subprocess.PIPE, **kwargs) as proc:
    for f in files:
        print(f, file=proc.stdin, end='\0')
    proc.communicate()
stop = time.monotonic()
log(f'returncode: {proc.returncode}')
assert not proc.returncode
log(f'time elapsed: {datetime.timedelta(seconds=stop - start)}')

assert dest_path.exists()
dest_stat = dest_path.stat()
log(f'tar result: {dest_path} ({dest_stat.st_size} bytes)')
assert dest_stat.st_size
log(format_permissions(dest_stat))

log('', f'os.chmod(..., {args.chmod:#05o})')
dest_path.chmod(args.chmod)
if args.owner or args.group:
    log(f'shutil.chown(..., user={args.owner}, group={args.group})')
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
