#!/usr/bin/env python3

"""Create tar archive from given directory, optionally ask for its deletion."""

__title__ = 'tar-archive.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
from collections.abc import Iterable, Iterator
import datetime
import functools
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import time

NAME_TEMPLATE = '%Y%m%d-%H%M.tar.gz'

MODE_MASK = 0o777
assert stat.filemode(MODE_MASK) == '?rwxrwxrwx'
assert MODE_MASK == stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO

SET_UMASK = 0o177
assert stat.filemode(SET_UMASK) == '?--xrwxrwx'
assert SET_UMASK == stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO

CHMOD = 0o400
assert stat.filemode(CHMOD) == '?r--------'
assert CHMOD == stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'

ENCODING = 'utf-8'


def directory(s: str, /) -> pathlib.Path:
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


def template(s: str, /) -> str:
    try:
        result = time.strftime(s)
    except ValueError:
        result = None

    if not result:
        raise argparse.ArgumentTypeError(f'invalid or empty template: {s}')
    return result


def exclude_file(s: str, /) -> pathlib.Path:
    if not s:
        return None
    try:
        path = pathlib.Path(s)
    except ValueError:
        path = None

    if path is None or not path.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return path


def user(s: str, /) -> str:
    import pwd

    try:
        pwd.getpwnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown user: {s}')
    return s


def group(s: str, /) -> str:
    import grp

    try:
        grp.getgrnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown group: {s}')
    return s


def mode(s: str, /) -> int:
    try:
        result = int(s, 8)
    except ValueError:
        result = None

    if result is None or not 0 <= result <= MODE_MASK:
        raise argparse.ArgumentTypeError(f'need octal int between {oct(0)}'
                                         f' and {oct(MODE_MASK)}: {s}')
    return stat.S_IMODE(result)


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('source_dir', type=directory,
                    help='input root directory to archive')

parser.add_argument('dest_dir', type=directory,
                    help='output directory for writing the tar archive file')

parser.add_argument('--name', metavar='TEMPLATE', type=template,
                    default=NAME_TEMPLATE,
                    help='archive file name time.strftime() format string template'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--exclude-file', metavar='PATH', type=exclude_file,
                    help='path to file with one line per excluded dir/file')

parser.add_argument('--no-auto-compress', dest='auto_compress', action='store_false',
                    help="don't pass --auto-compress to tar")

parser.add_argument('--owner', type=user, help='archive file owner')

parser.add_argument('--group', type=group, help='archive file group')

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'archive file chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help=f'PATH for tar subprocess (default: {SUBPROCESS_PATH})')

parser.add_argument('--set-umask', metavar='MASK', type=mode, default=SET_UMASK,
                    help=f'umask for tar subprocess (default: {SET_UMASK:03o})')

parser.add_argument('--ask-for-deletion', action='store_true',
                    help='prompt for archive file deletion before exit')

parser.add_argument('--version', action='version', version=__version__)


def tar_archive(source_dir: pathlib.Path, dest_dir: pathlib.Path, *, name: str,
                exclude_file: pathlib.Path | None,
                auto_compress: bool,
                owner: str | None, group: str | None, chmod: int,
                set_path: str, set_umask: int,
                ask_for_deletion: bool) -> str | None:
    dest_path = dest_dir / name
    log(f'tar source: {source_dir}', f'tar destination: {dest_path}')
    if dest_path.exists():
        return f'error: result file {dest_path} already exists'

    log('', f'os.umask(0o{set_umask:03o})')
    os.umask(set_umask)

    infos = {}
    exclude_paths = iterpaths(exclude_file) if exclude_file is not None else None
    exclude_match_func = make_exclude_match(exclude_paths)
    files = sorted(iterfiles(source_dir, exclude_match_func, infos=infos))
    log('traversed source: (', end='')
    counts = 'dirs', 'files', 'symlinks', 'other', 'excluded'
    log(*(f"{infos['n_' + c]} {c}" for c in counts), sep=', ', end=')\n')
    log(f"file size sum: {infos['n_bytes']:_d} bytes")

    (cmd, kwargs) = run_args_kwargs(source_dir, dest_path,
                                    auto_compress=auto_compress,
                                    set_path=set_path)

    log(f'subprocess.Popen({cmd}, **{kwargs})')
    start = time.monotonic()
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, **kwargs) as proc:
        for f in files:
            print(f, file=proc.stdin, end='\0')
        proc.communicate()
    stop = time.monotonic()

    log(f'returncode: {proc.returncode}',
        f'time elapsed: {datetime.timedelta(seconds=stop - start)}')
    if not dest_path.exists():
        return 'error: result file not found'
    dest_stat = dest_path.stat()
    log(f'tar result: {dest_path} ({dest_stat.st_size:_d} bytes)')
    if not dest_stat.st_size:
        return 'error: result file is empty'
    log(format_permissions(dest_stat))

    log('', f'os.chmod(..., 0o{chmod:03o})')
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


def iterpaths(path: pathlib.Path, /, *,
              encoding: str = ENCODING) -> Iterator[pathlib.Path]:
    with open(path, encoding=encoding) as f:
        for line in f:
            if (line := line.strip()) and not line.startswith('#'):
                yield path
    

def make_exclude_match(exclude_paths: Iterable[pathlib.Path] | None):
    if exclude_paths is None:
        return lambda x: False

    patterns = {path.parts for path in exclude_paths}
    if any(not (relative_path := path).is_absolute() for path in patterns):
        raise NotImplementedError(f'{relative_path=}')

    tree = {'/': {}}
    for parts in sorted(patterns):
        (root, *parts) = parts
        root = tree[root]
        for has_next, p in enumerate(parts, 1 - len(parts)):
            if p in root:
                assert (root[p] is not None) == bool(has_next)
            else:
                root[p] = {} if has_next else None
            root = root[p]

    def make_regex(tree, /, *, indent: str = ' ' * 4):
        for name, root in tree.items():
            rest = ''
            if root is not None:
                root = '|\n'.join(make_regex(root, indent=indent + (' ' * 4)))
                assert root
                rest = f'(?:{os.sep}(?:\n{root}\n{indent}))'
            yield f'{indent}{re.escape(name)}{rest}'

    pattern = '|\n'.join(make_regex(tree['/']))
    pattern = f'/(?:\n{pattern}\n)(?:{os.sep}.*)?'
    pattern_fullmatch = re.compile(pattern, flags=re.VERBOSE).fullmatch
    return lambda x: pattern_fullmatch(x.path) is not None


def iterfiles(root, /, exclude_match, *, infos=None,
              sep: str = os.sep):
    n_dirs = n_files = n_symlinks = n_other = n_bytes = n_excluded = 0

    stack = [('', root)]
    while stack:
        (prefix, root) = stack.pop()
        try:
            dentries = os.scandir(root)
        except OSError as e:
            log(e)
            continue

        dirs = []
        for d in dentries:
            if exclude_match(d):
                n_excluded += 1
                continue

            path = prefix + d.name

            if d.is_file(follow_symlinks=False):
                yield path
                n_files += 1
                n_bytes += d.stat(follow_symlinks=False).st_size
            elif d.is_dir(follow_symlinks=False):
                dirs.append((path + sep, d))
            elif d.is_symlink():
                yield path
                n_symlinks += 1
            else:
                yield path
                n_other += 1

        stack.extend(reversed(dirs))
        n_dirs += len(dirs)

    if infos is not None:
        infos.update(n_items=sum([n_dirs, n_files, n_symlinks, n_other]),
                     n_dirs=n_dirs, n_files=n_files, n_symlinks=n_symlinks,
                     n_other=n_other,
                     n_bytes=n_bytes,
                     n_excluded=n_excluded)


def run_args_kwargs(source_dir, dest_path, *,
                    auto_compress: bool, set_path: str,
                    encoding: str = ENCODING):
    cmd = ['tar', '--create', '--file', dest_path,
           '--files-from', '-', '--null', '--verbatim-files-from']
    if auto_compress:
        cmd.append('--auto-compress')

    # CAVEAT: env cannot override PATH on Windows
    # see https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    return cmd, {'cwd': source_dir,
                 'env': {'PATH': set_path},
                 'encoding': encoding}


def format_permissions(stat_result, /) -> str:
    import grp  # not on Windows
    import pwd

    return (f'file permissions: {stat.filemode(stat_result.st_mode)}'
            f' (owner={pwd.getpwuid(stat_result.st_uid).pw_name},'
            f' group={grp.getgrgid(stat_result.st_gid).gr_name})')


def prompt_for_deletion(path: pathlib.Path, /) -> bool:  # pragma: no cover
    line: str | None = None
    while line is None or (line and line.strip().lower() not in ('q', 'quit')):
        if line is not None:
            print('  (enter q(uit) or use CTRL-C to exit and keep the file)')
        line = input(f'to delete {path}, press enter [ENTER=delete]: ')
    return not line


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    return tar_archive(args.source_dir, args.dest_dir, name=args.name,
                       exclude_file=args.exclude_file,
                       auto_compress=args.auto_compress,
                       owner=args.owner,
                       group=args.group,
                       chmod=args.chmod,
                       set_path=args.set_path,
                       set_umask=args.set_umask,
                       ask_for_deletion=args.ask_for_deletion)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
