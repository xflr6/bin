#!/usr/bin/env python3

"""Svnadmin dump Subversion repositories into target directory."""

__title__ = 'svn-dumpall.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import contextlib
import datetime
import functools
import os
import pathlib
import stat
import subprocess
import sys
import time

NAME_TEMPLATE = '{name}.svndump.gz'

COMPRESS = {'.bz2': ['bzip2'],
            '.gz': ['gzip'],
            '.lz4': ['lz4'],
            '.lzo': ['lzop'],
            '.xz': ['xz'],
            '.zst': ['zstd']}

MODE_MASK = 0o777
assert stat.filemode(MODE_MASK) == '?rwxrwxrwx'
assert MODE_MASK == stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO

CHMOD = 0o400
assert stat.filemode(CHMOD) == '?r--------'
assert CHMOD == stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'


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
    elif pathlib.Path(result).parent.name:
        raise argparse.ArgumentTypeError(f'template contains directory: {s}')
    return result


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

parser.add_argument('target_dir', type=directory,
                    help='output directory for writing SVN dump file(s)')

parser.add_argument('repo_dir', nargs='+', type=directory,
                    help='input SVN repository directory')

parser.add_argument('--name', metavar='TEMPLATE', type=template,
                    default=NAME_TEMPLATE,
                    help=f'dump file name time.strftime() format string template'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--no-auto-compress', dest='auto_compress', action='store_false',
                    help='never compress dump file(s)'
                         ' (default: auto-compress if --name ends with any of:'
                         f" {', '.join(COMPRESS)})")

parser.add_argument('--no-deltas', dest='deltas', action='store_false',
                    help="don't pass --deltas to svnadmin dump")

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'dump file(s) chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help=f'PATH for subprocess(es) (default: {SUBPROCESS_PATH})')

parser.add_argument('--detail', action='store_true',
                    help='include detail infos for each repository')

parser.add_argument('--verbose', dest='quiet', action='store_false',
                    help="don't pass --quiet to svnadmin dump")

parser.add_argument('--version', action='version', version=__version__)


def svn_dumpall(target_dir: pathlib.Path, *repo_dirs: pathlib.Path, name: str,
                auto_compress: bool,
                deltas: bool,
                chmod: int,
                set_path: str,
                quiet: bool) -> str | None:
    start = time.monotonic()
    print(f'svnadmin dump {len(repo_dirs)} repo(s) into: {target_dir}/')
    log(f'file name template: {name}')

    (cmd, filter_cmds, kwargs) = pipe_args_kwargs(name,
                                                  deltas=deltas,
                                                  auto_compress=auto_compress,
                                                  quiet=quiet,
                                                  set_path=set_path)

    caption = ' | '.join(c for c, *_ in ([cmd] + filter_cmds))

    open_kwargs = {'opener': functools.partial(os.open, mode=chmod)}

    n_found = n_dumped = n_bytes = 0
    for d in repo_dirs:
        if not d.is_dir():
            return 'error: repo is not a directory'

        dest_path = target_dir / name.format(name=d.name)
        log('', f'source: {d}/', f'target: {dest_path}')

        found_size = dest_path.stat().st_size if dest_path.exists() else None
        if found_size is not None:
            log(f'delete present {dest_path} ({found_size:_d} bytes)')
            dest_path.unlink()
            n_found += 1

        dump_start = time.monotonic()
        with open(dest_path, mode='xb', **open_kwargs) as f:
            run_pipe(cmd + [d], *filter_cmds, stdout=f, check=True, **kwargs)
        n_dumped += 1
        dump_stop = time.monotonic()
        log(f'time elapsed: {datetime.timedelta(seconds=dump_stop - dump_start)}')

        if not dest_path.exists():
            return 'error: result file not found'
        n_bytes += (dest_size := dest_path.stat().st_size)
        print(f'{caption} > {dest_path} ({dest_size:_d} bytes)')
        if not dest_size:
            return 'error: result file is empty'
        if found_size is not None:
            diff = dest_size - found_size
            log(f'size difference: {diff}' if diff else 'no size difference')

    stop = time.monotonic()
    print('', f'total time: {datetime.timedelta(seconds=stop - start)}',
          f'done (removed={n_found}, dumped={n_dumped}) (total {n_bytes:_d} bytes).',
          sep='\n')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def pipe_args_kwargs(name, *,
                     deltas: bool,
                     auto_compress: bool,
                     quiet: bool,
                     set_path):
    cmd = ['svnadmin', 'dump']
    if deltas:
        cmd.append('--deltas')
    if quiet:
        cmd.append('--quiet')

    filter_cmds = []
    suffix = pathlib.Path(name).suffix
    if auto_compress:
        if (compress_cmd := COMPRESS.get(suffix)) is not None:
            filter_cmds.append(compress_cmd)
    elif suffix in COMPRESS:
        raise ValueError(f'{auto_compress=} but {name=} with compress {suffix=}')

    # CAVEAT: env cannot override PATH on Windows
    # see https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    return cmd, filter_cmds, {'env': {'PATH': set_path}}


def run_pipe(cmd, /, *filter_cmds, check: bool = False, **kwargs):
    procs = map_popen([cmd] + list(filter_cmds), **kwargs)
    with contextlib.ExitStack() as s:
        procs = [s.enter_context(p) for p in procs]

        log('returncode(s): ', end='')
        for has_next, p in enumerate(reversed(procs), 1 - len(procs)):
            (out, err) = p.communicate()
            log(f'{p.args[0]}={p.returncode}', end=', ' if has_next else '\n')
            if check and p.returncode:
                raise subprocess.CalledProcessError(p.returncode, p.args,
                                                    output=out, stderr=err)


def map_popen(commands, /, *, stdin=None, stdout=None, **kwargs):
    for has_next, cmd in enumerate(commands, 1 - len(commands)):
        log(f'subprocess.Popen({cmd}, **{kwargs})',
            '| ' if has_next else f'> {stdout}\n', sep=' ', end='')
        proc = subprocess.Popen(cmd,
                                stdin=stdin,
                                stdout=subprocess.PIPE if has_next else stdout,
                                **kwargs)
        yield proc
        stdin = proc.stdout


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    if not args.detail:
        global log
        log = lambda *args, **kwargs: None
    return svn_dumpall(args.target_dir, *args.repo_dir, name=args.name,
                       auto_compress=args.auto_compress,
                       deltas=args.deltas,
                       chmod=args.chmod,
                       set_path=args.set_path,
                       quiet=args.quiet)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
