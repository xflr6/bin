#!/usr/bin/env python3

"""Create SquashFS image from given directory, optionally ask for its deletion."""

__title__ = 'squashfs-image.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
from collections.abc import Sequence
import datetime
import functools
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import time

MODE_MASK = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO


def parse_args(args: Sequence[str] | None, /) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    def directory(s: str, /) -> pathlib.Path:
        try:
            result = pathlib.Path(s)
        except ValueError:
            result = None
        if result is None or not result.is_dir():
            raise argparse.ArgumentTypeError(f'not a present directory: {s}')
        return result

    parser.add_argument('source_dir', type=directory,
                        help='input root directory to image')

    parser.add_argument('dest_dir', type=directory,
                        help='output directory for writing the SquashFS image file')

    def template(s: str, /) -> str:
        try:
            result = time.strftime(s)
        except ValueError:
            result = None
        if not result:
            raise argparse.ArgumentTypeError(f'invalid or empty template: {s}')
        return result

    parser.add_argument('--name', metavar='TEMPLATE', type=template,
                        help='image file name time.strftime() format string template',
                        default='%Y%m%d-%H%M.sfs')

    def present_file(s: str, /) -> pathlib.Path:
        if not s:
            return None
        try:
            result = pathlib.Path(s)
        except ValueError:
            result = None
        if result is None or not result.is_file():
            raise argparse.ArgumentTypeError(f'not a present file: {s}')
        return result

    parser.add_argument('--exclude-file', metavar='PATH', type=present_file,
                        help='file with lines of excluded dirs/files')

    parser.add_argument('--comp', choices=('gzip', 'lz4', 'lzo', 'xz', 'zstd'),
                        help='override mksquashfs compression choice')

    def user(s: str, /) -> str:
        import pwd  # Availability: Unix
        try:
            pwd.getpwnam(s)
        except KeyError:
            raise argparse.ArgumentTypeError(f'unknown user: {s}')
        return s

    parser.add_argument('--owner', type=user,
                        help='image file owner')

    def group(s: str, /) -> str:
        import grp  # Availability: Unix
        try:
            grp.getgrnam(s)
        except KeyError:
            raise argparse.ArgumentTypeError(f'unknown group: {s}')
        return s

    parser.add_argument('--group', type=group,
                        help='image file group')

    def mode(s: str, /) -> int:
        try:
            result = int(s, base=8)
        except ValueError:
            result = None
        assert stat.filemode(MODE_MASK) == '?rwxrwxrwx'  # 0o777
        if result is None or not 0 <= result <= MODE_MASK:
            raise argparse.ArgumentTypeError(f'need octal int between {oct(0)}'
                                             f' and {oct(MODE_MASK)}: {s}')
        return stat.S_IMODE(result)

    parser.add_argument('--chmod', metavar='MODE', type=mode,
                        help='image file chmod',
                        default=f'{stat.S_IRUSR:3o}')
    assert stat.filemode(mode(parser.get_default('chmod'))) == '?r--------'  # 0o400

    parser.add_argument('--set-path', metavar='LINE',
                        help='PATH for mksquashfs subprocess',
                        default='/usr/bin')

    parser.add_argument('--set-umask', metavar='MASK', type=mode,
                        help='umask for mksquashfs subprocess',
                        default=f'{stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO:3o}')
    assert stat.filemode(mode(parser.get_default('set_umask'))) == '?--xrwxrwx'  # 0o177

    parser.add_argument('--quiet', action='store_true',
                        help='suppress stdout/stderr of mksquashfs')

    parser.add_argument('--ask-for-deletion', action='store_true',
                        help='ask for image deletion before exit')

    parser.add_argument('--version', action='version', version=__version__)
    return parser.parse_args(args)


def squashfs_image(source_dir: pathlib.Path, dest_dir: pathlib.Path, *, name: str,
                   exclude_file: pathlib.Path | None,
                   comp: str,
                   owner: str | None, group: str | None, chmod: int,
                   set_path: str, set_umask: int,
                   quiet: bool,
                   ask_for_deletion: bool) -> str | None:
    dest_path = dest_dir / name
    log(f'mksquashfs source: {source_dir}',
        f'mksquashfs destination: {dest_path}')
    if dest_path.exists():
        return f'error: result file {dest_path} already exists'

    log('', f'os.umask({oct(set_umask)}')
    os.umask(set_umask)

    (cmd, kwargs) = run_args_kwargs(source_dir, dest_path,
                                    exclude_file=exclude_file,
                                    comp=comp,
                                    set_path=set_path,
                                    quiet=quiet)

    log(f'subprocess.run({cmd}, **{kwargs})')
    if not quiet:
        log(f'{"[ start subprocess ]":-^80}')
    start = time.monotonic()
    proc = subprocess.run(cmd, check=True, **kwargs)
    stop = time.monotonic()
    if not quiet:
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

    log('', f'os.chmod(..., {oct(chmod)}')
    dest_path.chmod(chmod)

    if owner or group:
        log(f'shutil.chown(..., user={owner}, group={group})')
        shutil.chown(dest_path, user=owner, group=group)
    log(format_permissions(dest_path.stat()))

    if ask_for_deletion:
        if prompt_for_deletion(dest_path):  # pragma: no cover
            dest_path.unlink()
            log(f'{dest_path} deleted.')
        else:
            log(f'kept {dest_path}.')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def run_args_kwargs(source_dir: pathlib.Path, dest_path: pathlib.Path, *,
                    exclude_file: pathlib.Path | None,
                    comp: str, set_path: str, quiet: bool):
    cmd = ['mksquashfs', source_dir, dest_path, '-noappend']
    if exclude_file is not None:
        log(f'mksquashfs exclude file: {exclude_file}')
        cmd += ['-ef', exclude_file]
    if comp is not None:
        log(f'mksquashfs compression: {comp}')
        cmd += ['-comp', comp]

    # CAVEAT: env cannot override PATH on Windows
    # see https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    kwargs = {'env': {'PATH': set_path}}
    if quiet:
        kwargs.setdefault('stdout', subprocess.DEVNULL)
        kwargs.setdefault('stderr', subprocess.DEVNULL)

    return cmd, kwargs


def format_permissions(stat_result, /) -> str:
    import grp  # Availability: Unix
    import pwd  # Availability: Unix

    return (f'file permissions: {stat.filemode(stat_result.st_mode)}'
            f' (owner={pwd.getpwuid(stat_result.st_uid).pw_name},'
            f' group={grp.getgrgid(stat_result.st_gid).gr_name})')


def prompt_for_deletion(path: pathlib.Path, /) -> bool:  # pragma: no cover
    prompt = f'to delete {path}, press enter [ENTER=delete]: '
    while (line := input(prompt)) and line.strip().lower() not in ('q', 'quit'):
        print('  (enter q(uit) or use CTRL-C to exit and keep the file)')
    return not line


def main(args: Sequence[str] | None = None) -> str | None:
    args = parse_args(args)
    return squashfs_image(args.source_dir, args.dest_dir, name=args.name,
                          exclude_file=args.exclude_file,
                          comp=args.comp,
                          owner=args.owner,
                          group=args.group,
                          chmod=args.chmod,
                          set_path=args.set_path,
                          set_umask=args.set_umask,
                          quiet=args.quiet,
                          ask_for_deletion=args.ask_for_deletion)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
