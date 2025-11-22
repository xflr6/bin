#!/usr/bin/env python3

"""Git clone --mirror or git remote update all public Gists of GitHub user(s)."""

__title__ = 'git-pull-gists.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request
import warnings

GISTS = 'https://api.github.com/users/{username}/gists'


def directory(s: str) -> pathlib.Path:
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('target_dir', type=directory,
                    help='output directory for writing/updating bare Git clones')

parser.add_argument('gh_username', nargs='+',
                    help='name of the GitHub user account')

parser.add_argument('--reset', action='store_true',
                    help='delete present Git clones first')

parser.add_argument('--detail', dest='quiet', action='store_false',
                    help='show detailed info for each clone/update')

parser.add_argument('--version', action='version', version=__version__)


def git_pull_gists(target_dir: pathlib.Path, *gh_usernames: str,
                   reset: bool) -> str | None:
    for gh_username in gh_usernames:
        print(f'pull all public gist repos of {gh_username}'
              f' into: {target_dir}/')

        gists = list(itergists(username=gh_username))
        print(f'pull {len(gists)} repo(s) into: {target_dir}/')

        n_reset = n_cloned = n_updated = n_failed = 0
        for g in gists:
            print()
            url = g['git_push_url']
            log(f'source: {url}')

            url = parse_url(url)
            g_dir = target_dir / url['dir']
            log(f'target: {g_dir}/', end='')

            (removed, clone) = removed_clone(g_dir, reset=reset)
            if removed:
                n_reset += 1

            if clone:
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
            try:
                proc = subprocess.run(cmd, cwd=cwd, check=True)
            except subprocess.CalledProcessError as e:  # pragma: no cover
                n_failed += 1
                if clone:
                    n_cloned -= 1
                else:
                    n_updated -= 1
                log(f'{"[ end git ]":-^80}')
                warnings.warn(str(e))
                if not prompt_for_continuation():
                    return 'exiting'
            else:
                log(f'{"[ end git ]":-^80}')
                log(f'returncode: {proc.returncode}')

        print('\ndone'
              f'(reset={n_reset},'
              f' cloned={n_cloned},'
              f' updated={n_updated},'
              f' failed={n_failed}).')

    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def itergists(username: str):
    url = GISTS.format(username=username)
    while url is not None:
        log(f'urllib.request.urlopen({url})')
        with urllib.request.urlopen(url) as u:
            gists = json.load(u)
        links = [l.partition('; ') for l in u.info().get('Link', '').split(', ')]
        links = {r: u.partition('<')[2].partition('>')[0] for u, _, r in links}
        url = links.get('rel="next"')

        yield from gists


def parse_url(s: str):
    return re.search(r'(?P<url>.*/(?P<dir>[^/]+))$', s).groupdict()


def removed_clone(path: pathlib.Path, *, reset: bool = False):
    removed = clone = False
    if path.exists():
        if not path.is_dir():  # pragma: no cover
            raise RuntimeError(f'path is not a directory: {path}')
        if reset and prompt_for_deletion(path):
            removed = clone = True
    else:
        clone = True
    return removed, clone


def prompt_for_deletion(path: pathlib.Path) -> bool:  # pragma: no cover
    line = None
    while line is None or (line and line not in ('y', 'yes')):
        line = input(f'delete {path}/? [(y)es=delete/ENTER=keep]: ')

    if line in ('y', 'yes'):
        log(f'shutil.rmtree({path})')
        shutil.rmtree(path)
        return True
    else:
        log(f'kept: {path}/ (inode={path.stat().st_ino})')
        return False


def prompt_for_continuation():  # pragma: no cover
    line = None
    while line is None or (line and line.strip().lower() not in ('q', 'quit')):
        if line is not None:
            print('  (enter q(uit) or use CTRL-C to exit)')
        line = input('to continue, press enter [ENTER=continue]: ')
    return not line


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    if args.quiet:
        global log
        log = lambda *args, **kwargs: None
    return git_pull_gists(args.target_dir, *args.gh_username, reset=args.reset)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
