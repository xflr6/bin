#!/usr/bin/env python3

"""Create SquashFS image from given directory, optioally ask for its deletion."""

__title__ = 'backup-squashfs.py'
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

NAME_TEMPLATE = '%Y%m%d-%H%M.sfs'

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin'

SET_UMASK = stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO


log = functools.partial(print, file=sys.stderr, sep='\n')


def directory(s: str) -> pathlib.Path:
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


def template(s: str) -> str:
    try:
        result = time.strftime(s)
    except ValueError:
        result = None

    if not result:
        raise argparse.ArgumentTypeError(f'invalid or empty template: {s}')
    return result


def present_file(s: str) -> pathlib.Path:
    if not s:
        return None
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return result


def user(s: str) -> str:
    import pwd

    try:
        pwd.getpwnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown user: {s}')
    return s


def group(s: str) -> str:
    import grp

    try:
        grp.getgrnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown group: {s}')
    return s


def mode(s: str, *,
         _mode_mask=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO) -> int:
    try:
        result = int(s, 8)
    except ValueError:
        result = None

    if result is None or not 0 <= result <= _mode_mask:
        raise argparse.ArgumentTypeError(f'need octal int between {0:03o}'
                                         f' and {_mode_mask:03o}: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('source_dir', type=directory, help='image source directory')

parser.add_argument('dest_dir', type=directory, help='image target directory')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help='image filename time.strftime() format string template'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--exclude-file', metavar='PATH', type=present_file,
                    help='path to file with one line per blacklist item')

parser.add_argument('--comp', choices=('gzip', 'lz4', 'lzo', 'xz', 'zstd'),
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

parser.add_argument('--quiet', action='store_true',
                    help='suppress stdout and stderr of mksquashfs subprocess')

parser.add_argument('--ask-for-deletion', action='store_true',
                    help='prompt for image file deletion before exit')

parser.add_argument('--version', action='version', version=__version__)


def run_args_kwargs(source_dir, dest_path, *,
                    exclude_file, comp, set_path, quiet):
    cmd = ['mksquashfs',
           source_dir, dest_path,
           '-noappend']

    if exclude_file is not None:
        log(f'mksquashfs exclude file: {exclude_file}')
        cmd += ['-ef', exclude_file]

    if comp is not None:
        log(f'mksquashfs compression: {comp}')
        cmd += ['-comp', comp]

    kwargs = {'env': {'PATH': set_path}}
    if quiet:
        kwargs['stdout'] = kwargs['stderr'] = subprocess.DEVNULL

    return cmd, kwargs


def format_permissions(stat_result):
    import grp
    import itertools
    import pwd

    def iterflags(mode):
        for u, f in itertools.product(('USR', 'GRP', 'OTH'), 'RWX'):
            if mode & getattr(stat, f'S_I{f}{u}'):
                yield f.lower()
            else:
                yield '-'

    mode = ''.join(iterflags(stat_result.st_mode))
    owner = pwd.getpwuid(stat_result.st_uid).pw_name
    group = grp.getgrgid(stat_result.st_gid).gr_name
    return f'file permissions: {mode} (owner={owner}, group={group})'


def prompt_for_deletion(path: pathlib.Path) -> bool:  # pragma: no cover
    line = None
    while line is None or (line and line.strip().lower() not in ('q', 'quit')):
        if line is not None:
            print('  (enter q(uit) or use CTRL-C to exit and keep the file)')
        line = input(f'to delete {path}, press enter [ENTER=delete]: ')

    if line:
        log(f'kept {path}.')
    else:
        path.unlink()
        log(f'{path} deleted.')


def main(args=None) -> str | None:
    args = parser.parse_args(args)

    dest_path = args.dest_dir / args.name

    log(f'mksquashfs source: {args.source_dir}',
        f'mksquashfs destination: {dest_path}')

    if dest_path.exists():
        return f'error: result file {dest_path} already exists'

    (cmd, kwargs) = run_args_kwargs(args.source_dir, dest_path,
                                    exclude_file=args.exclude_file,
                                    comp=args.comp,
                                    set_path=args.set_path,
                                    quiet=args.quiet)

    log('', f'os.umask(0o{args.set_umask:03o})')
    os.umask(args.set_umask)

    log(f'subprocess.run({cmd}, **{kwargs})')
    if not args.quiet:
        log(f'{"[ start subprocess ]":-^80}')
    start = time.monotonic()
    proc = subprocess.run(cmd, check=True, **kwargs)
    stop = time.monotonic()
    if not args.quiet:
        log(f'{"[ end subprocess ]":-^80}')
    log(f'returncode: {proc.returncode}',
        f'time elapsed: {datetime.timedelta(seconds=stop - start)}')

    if not dest_path.exists():
        return 'error: result file not found'

    dest_stat = dest_path.stat()
    log(f'mksquashfs result: {dest_path} ({dest_stat.st_size:_d} bytes)')
    if not dest_stat.st_size:
        return 'error: result file is empty'
    log(format_permissions(dest_stat))

    log('', f'os.chmod(..., 0o{args.chmod:03o})')
    dest_path.chmod(args.chmod)
    if args.owner or args.group:
        log(f'shutil.chown(..., user={args.owner}, group={args.group})')
        shutil.chown(dest_path, user=args.owner, group=args.group)
    log(format_permissions(dest_path.stat()))

    if args.ask_for_deletion:
        prompt_for_deletion(dest_path)  # pragma: no cover

    return None


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
