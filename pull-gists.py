#!/usr/bin/env python3

"""Git clone --mirror or git remote update all public gists of GitHub user."""

__title__ = 'pull-gists.py'
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

GISTS = 'https://api.github.com/users/{username}/gists'


log = functools.partial(print, file=sys.stderr, sep='\n')


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

parser.add_argument('gh_username', help='GitHub username')

parser.add_argument('--reset', action='store_true',
                    help='delete present git clones first')

parser.add_argument('--detail', dest='quiet', action='store_false',
                    help='show detailed info for each clone/update')

parser.add_argument('--version', action='version', version=__version__)


def itergists(username):
    url = GISTS.format(username=username)
    while url is not None:
        log(f'urllib.request.urlopen({url})')
        with urllib.request.urlopen(url) as u:
            gists = json.load(u)
        links = [l.partition('; ') for l in u.info().get('Link', '').split(', ')]
        links = {r: u.partition('<')[2].partition('>')[0] for u, _, r in links}
        url = links.get('rel="next"')

        yield from gists


def parse_url(s):
    return re.search(r'(?P<url>.*/(?P<dir>[^/]+))$', s).groupdict()


def prompt_for_deletion(path):
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


def removed_clone(path, reset=False):
    removed = clone = False
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f'path is not a directory: {path}')
        if reset and prompt_for_deletion(path):
            removed = clone = True
    else:
        clone = True
    return removed, clone


def main(args=None):
    args = parser.parse_args(args)

    if args.quiet:
        global log
        log = lambda *args, **kwargs: None

    print(f'pull all public gist repos of {args.gh_username} into: {args.target_dir}/')

    gists = list(itergists(username=args.gh_username))
    print(f'pull {len(gists)} repo(s) into: {args.target_dir}/')

    n_reset = n_cloned = n_updated = 0
    for g in gists:
        print()
        url = g['git_push_url']
        log(f'source: {url}')

        url = parse_url(url)
        g_dir = args.target_dir / url['dir']
        log(f'target: {g_dir}/', end='')

        removed, clone = removed_clone(g_dir, reset=args.reset)
        if removed:
            n_reset += 1

        if clone:
            log()
            cmd = ['git', 'clone', '--mirror', url['url']]
            cwd = args.target_dir
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


if __name__ == '__main__':
    sys.exit(main())
