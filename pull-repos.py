#!/usr/bin/env python3

"""Git clone --mirror or git remote update git repositories."""

__title__ = 'pull-repos.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import pathlib
import shutil
import subprocess
import sys


def directory(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None
    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('target_dir', type=directory,
                    help='output directory for bare git clones')

parser.add_argument('repo_url', nargs='+', help='git repository url')

parser.add_argument('--reset', action='store_true',
                    help='delete present git clones first')

parser.add_argument('--detail', action='store_true',
                    help='show detailed info for each clone/update')

parser.add_argument('--version', action='version', version=__version__)

args = parser.parse_args()

if args.detail:
    log = functools.partial(print, file=sys.stderr, sep='\n')
else:
    log = lambda *args, **kwargs: None

print(f'pull {len(args.repo_url)} repo(s) into: {args.target_dir}/')

n_reset = n_cloned = n_updated = 0

for url in sorted(args.repo_url):
    print()
    log(f'source: {url}')

    if url.startswith('github.com:'):
        url = 'git@' + url

    if not url.endswith('.git'):
        url = url + '.git'

    rest, sep, g_dir = url.rpartition('/')
    assert rest and sep
    g_dir = args.target_dir / g_dir
    log(f'target: {g_dir}/', end='')

    if g_dir.exists():
        clone = False
        assert g_dir.is_dir()
        if args.reset:
            log()
            line = None
            while line is None or (line != '' and line not in ('y', 'yes')):
                line = input(f'delete {g_dir}/? [(y)es=delete/ENTER=keep]: ')
            if line in ('y', 'yes'):
                log(f'shutil.rmtree({g_dir})')
                shutil.rmtree(g_dir)
                n_reset += 1
                clone = True
            else:
                log(f'kept: {g_dir}/ (inode={g_dir.stat().st_ino})')
        else:
            log(f' (inode={g_dir.stat().st_ino})')
    else:
        clone = True
        log()

    if clone:
        cmd = ['git', 'clone', '--mirror', url]
        cwd = args.target_dir
        n_cloned += 1
    else:
        cmd = ['git', 'remote', 'update']
        cwd = g_dir
        n_updated += 1

    print(f'subprocess.run({cmd}, cwd={cwd})')
    log(f'{"[ start git ]":-^80}')
    proc = subprocess.run(cmd, cwd=cwd, check=True)
    log(f'{"[ end git ]":-^80}')
    log(f'returncode: {proc.returncode}')

print(f'\ndone (reset={n_reset}, cloned={n_cloned}, updated={n_updated}).')