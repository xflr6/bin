#!/usr/bin/env python3

"""Svnadmin dump subversion repositories into target directory."""

__title__ = 'dumpall-svn.py'
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

COMPRESS = {'.bz2': ['bzip2', '--stdout'],
            '.gz': ['gzip', '--stdout'],
            '.xz':  ['xz', '--stdout']}

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'


log = functools.partial(print, file=sys.stderr, sep='\n')


def directory(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


def template(s):
    try:
        result = datetime.datetime.now().strftime(s)
    except ValueError:
        result = None

    if not result:
        raise argparse.ArgumentTypeError('empty string')
    return result


def mode(s, _mode_mask=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO):
    try:
        result = int(s, 8)
    except ValueError:
        result = None

    if result is None or not 0 <= result <= _mode_mask:
        raise argparse.ArgumentTypeError(f'need octal int between {0:03o}'
                                         f' and {_mode_mask:03o}: {s}')
    return result


def pipe_args_kwargs(name, *, deltas, auto_compress, quiet, set_path):
    cmd = ['svnadmin', 'dump']
    if deltas:
        cmd.append('--deltas')
    if quiet:
        cmd.append('--quiet')

    filter_cmds = []
    if auto_compress:
        suffix = pathlib.Path(name).suffix
        if suffix in COMPRESS:
            filter_cmds.append(COMPRESS[suffix])

    return cmd, filter_cmds, {'env': {'PATH': set_path}}


def pipe_into(file, cmd, *filter_cmds, check=False, **kwargs):
    assert all(kw not in kwargs for kw in ('stdin', 'stdout'))
    procs = map_popen([cmd] + list(filter_cmds), stdout=file, **kwargs)
    with contextlib.ExitStack() as s:
        procs = [s.enter_context(p) for p in procs]
        log(f'returncode(s): ', end='')
        for has_next, p in enumerate(procs, 1 - len(procs)):
            out, err = p.communicate()
            if has_next:  # Allow p to receive a SIGPIPE if next proc exits.
                p.stdout.close()
            log(f'{p.args[0]}={p.returncode}', end=', ' if has_next else '\n')
            if check and p.returncode:
                raise subprocess.CalledProcessError(p.returncode, p.args,
                                                    output=out, stderr=err)


def map_popen(commands, *, stdin=None, stdout=None, **kwargs):
    for has_next, cmd in enumerate(commands, 1 - len(commands)):
        log(f'subprocess.Popen({cmd}, **{kwargs})', end='')
        proc = subprocess.Popen(cmd,
                                stdin=stdin,
                                stdout=subprocess.PIPE if has_next else stdout,
                                **kwargs)
        yield proc
        stdin = proc.stdout
        if has_next:
            log(f' | ', end='')
        else:
            log(f' > {stdout}')


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('target_dir', type=directory,
                    help='output directory for dump files')

parser.add_argument('repo_dir', nargs='+', type=directory,
                    help='subversion repository directory')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help=f'dump filename datetime.strftime() format string'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--no-auto-compress', action='store_true',
                    help='never compress dump file(s)'
                         ' (default: auto-compress if --name ends with any of:'
                         f" {', '.join(COMPRESS)})")

parser.add_argument('--no-deltas', action='store_true',
                    help="don't pass --deltas to $(svnadmin dump)")

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'dump file chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help=f'PATH for subprocess(es) (default: {SUBPROCESS_PATH})')

parser.add_argument('--detail', action='store_true',
                    help='include detail infos for each repository')

parser.add_argument('--verbose', action='store_true',
                    help="don't pass --quiet to $(svnadmin dump)")

parser.add_argument('--version', action='version', version=__version__)


def main(args=None):
    args = parser.parse_args(args)

    if not args.detail:
        global log
        log = lambda *args, **kwargs: None

    start = time.monotonic()
    print(f'svnadmin dump {len(args.repo_dir)} repo(s) into: {args.target_dir}/')
    log(f'file name template: {args.name}')

    cmd, filter_cmds, kwargs = pipe_args_kwargs(args.name,
                                                deltas=not args.no_deltas,
                                                auto_compress=not args.no_auto_compress,
                                                quiet=not args.verbose,
                                                set_path=args.set_path)

    caption = ' | '.join(c for c, *_ in ([cmd] + filter_cmds))

    open_kwargs = {'opener': functools.partial(os.open, mode=args.chmod)}

    n_found = n_dumped = n_bytes = 0
    for d in args.repo_dir:
        assert d.is_dir()
        dest_path = args.target_dir / args.name.format(name=d.name)
        log('', f'source: {d}/', f'target: {dest_path}')

        found_size = dest_path.stat().st_size if dest_path.exists() else None
        if found_size is not None:
            log(f'delete present {dest_path} ({found_size} bytes)')
            dest_path.unlink()
            n_found += 1

        dump_start = time.monotonic()
        with open(dest_path, 'xb', **open_kwargs) as f:
            pipe_into(f, cmd + [d], *filter_cmds, check=True, **kwargs)
        dump_stop = time.monotonic()
        log(f'time elapsed: {datetime.timedelta(seconds=dump_stop - dump_start)}')
        n_dumped += 1

        assert dest_path.exists()
        dest_size = dest_path.stat().st_size
        print(f'{caption} result: {dest_path} ({dest_size} bytes)')
        assert dest_size
        n_bytes += dest_size

        if found_size is not None:
            diff = dest_size - found_size
            log(f'size difference: {diff}' if diff else 'no size difference')

    stop = time.monotonic()
    print('', f'total time: {datetime.timedelta(seconds=stop - start)}',
          f'done (removed={n_found}, dumped={n_dumped}) (total {n_bytes} bytes).',
          sep='\n')
    return None


if __name__ == '__main__':
    sys.exit(main())
