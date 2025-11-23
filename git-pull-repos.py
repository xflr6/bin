#!/usr/bin/env python3

"""Git clone --mirror or git remote update remote Git repositories."""

__title__ = 'git-pull-repos.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import pathlib
import re
import shutil
import subprocess
import sys


def directory(s: str, /) -> pathlib.Path:
    try:
        result = pathlib.Path(s)
    except (TypeError, ValueError):
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('target_dir', type=directory,
                    help='output directory for writing/updating bare Git clones')

parser.add_argument('repo_url', nargs='+', help='input Git repository URL')

parser.add_argument('--reset', action='store_true',
                    help='delete present Git clones first')

parser.add_argument('--detail', dest='quiet', action='store_false',
                    help='show detailed info for each clone/update')

parser.add_argument('--version', action='version', version=__version__)


def git_pull_repos(target_dir: pathlib.Path, *repo_urls: str,
                   reset: bool) -> str | None:
    print(f'pull {len(repo_urls)} repo(s) into: {target_dir}/')

    n_reset = n_cloned = n_updated = 0
    for url in sorted(repo_urls):
        print()
        log(f'source: {url}')

        url = parse_url(url)
        g_dir = target_dir / url['dir']
        log(f'target: {g_dir}/', end='')

        if reset and g_dir.exists():
            if not path.is_dir():
                raise RuntimeError(f'{g_dir} is not a directory')
            if prompt_for_deletion(g_dir):
                log(f'shutil.rmtree({g_dir})')
                shutil.rmtree(path)
                n_reset += 1
                assert g_dir.exists()
            else:
                log(f'kept: {path}/ (inode={path.stat().st_ino})')


        if not g_dir.exists():
            log()
            cmd = ['git', 'clone', '--mirror', url['url']]
            cwd = target_dir
            n_cloned += 1
        else:
            log(f' (inode={g_dir.stat().st_ino})')
            cmd = ['git', 'remote', 'update']
            cwd = g_dir
            n_updated += 1

        print(f'subprocess.run({cmd}, cwd={cwd})')
        log(f'{"[ start git ]":-^80}')
        proc = subprocess.run(cmd, cwd=cwd, check=True)
        log(f'{"[ end git ]":-^80}')
        log(f'returncode: {proc.returncode}')

    print(f'\ndone (reset={n_reset}, cloned={n_cloned}, updated={n_updated}).')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def parse_url(s: str, /) -> dict[str, str]:
    if s.startswith('github.com:'):
        s = f'git@{s}'
    if not s.endswith('.git'):
        s = f'{s}.git'
    return re.search(r'(?P<url>.*/(?P<dir>[^/]+))$', s).groupdict()


def prompt_for_deletion(path: pathlib.Path, /) -> bool:  # pragma: no cover
    line = None
    while line is None or (line and line not in ('y', 'yes')):
        line = input(f'delete {path}/? [(y)es=delete/ENTER=keep]: ')
    return line in ('y', 'yes')


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    if args.quiet:
        global log
        log = lambda *args, **kwargs: None
    return git_pull_repos(args.target_dir, *args.repo_url, reset=args.reset)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
