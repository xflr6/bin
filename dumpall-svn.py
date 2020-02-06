#!/usr/bin/env python3

"""Svnadmin dump subversion repositories into target directory."""

__title__ = 'dumpall-svn.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import datetime
import functools
import os
import pathlib
import stat
import string
import subprocess
import sys
import time

NAME_TEMPLATE = '${name}.svndump'

COMP = {'gzip': (['gzip', '--stdout'], '.gz'),
        'xz':  (['xz', '--stdout'], '.xz')}

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'


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
    return string.Template(result)


def mode(s, _mode_mask=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO):
    try:
        result = int(s, 8)
    except ValueError:
        result = None
    if result is None or not 0 <= result <= _mode_mask:
        raise argparse.ArgumentTypeError(f'need octal int between {0:03o}'
                                         f' and {_mode_mask:03o}: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('target_dir', type=directory,
                    help='output directory for dump files')

parser.add_argument('repo_dir', nargs='+', type=directory,
                    help='subversion repository directory')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help=f'dump filename datetime.strftime() format string'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--comp', choices=list(COMP),
                    help='compress dump file(s) (no compression if omitted)')

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

args = parser.parse_args()

start = time.monotonic()

if args.detail:
    log = functools.partial(print, file=sys.stderr, sep='\n')
else:
    log = lambda *args, **kwargs: None

print(f'svnadmin dump {len(args.repo_dir)} repo(s) into: {args.target_dir}/')

dump = ['svnadmin', 'dump']

if not args.no_deltas:
    dump.append('--deltas')

if not args.verbose:
    dump.append('--quiet')

name_template = args.name
if args.comp in (None, ''):
    comp = None
else:
    comp, sfx = COMP[args.comp]
    name_template = string.Template(name_template.template + sfx)
log(f'file name template: {name_template}')

caption = ' | '.join(dump[:1] + (comp[:1] if comp is not None else []))

open_kwargs = {'opener': functools.partial(os.open, mode=args.chmod)}

kwargs = {'env': {'PATH': args.set_path}}

n_found = n_dumped = n_bytes = 0

for d in args.repo_dir:
    assert d.is_dir()
    dest_path = args.target_dir / name_template.substitute(name=d.name)
    log('', f'source: {d}/', f'target: {dest_path}')

    found_size = dest_path.stat().st_size if dest_path.exists() else None
    if found_size is not None:
        log(f'delete present {dest_path} ({found_size} bytes)')
        dest_path.unlink()
        n_found += 1

    cmd = dump + [d]

    dump_start = time.monotonic()
    with open(dest_path, 'xb', **open_kwargs) as f:
        log(f'subprocess.Popen({cmd}, **{kwargs})', end='')
        if comp is None:
            log(f' > {f}')
            with subprocess.Popen(cmd, stdout=f, **kwargs) as m:
                m.communicate()
        else:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, **kwargs) as m:
                log(f' | subprocess.Popen({comp}, **{kwargs}) > {f}')
                with subprocess.Popen(comp, stdin=m.stdout, stdout=f, **kwargs) as c:
                    m.communicate()
                    m.stdout.close()  # Allow m to receive a SIGPIPE if c exits.
                    c.communicate()
    dump_stop = time.monotonic()
    log(f'returncode(s): {cmd[0]}={m.returncode}', end='')
    assert not m.returncode
    log('' if comp is None else f', {comp[0]}={c.returncode}')
    assert comp is None or not c.returncode
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
