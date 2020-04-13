#!/usr/bin/env python3

"""Create tar archive from given directory, optionally ask for its deletion."""

__title__ = 'backup-tar.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
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

CHMOD = stat.S_IRUSR

SUBPROCESS_PATH = '/usr/bin:/bin'

SET_UMASK = stat.S_IXUSR | stat.S_IRWXG | stat.S_IRWXO

ENCODING = 'utf-8'


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
        result = time.strftime(s)
    except ValueError:
        result = None

    if not result:
        raise argparse.ArgumentTypeError(f'invalid or empty template: {s}')
    return result


def exclude_file(s):
    if not s:
        return None
    try:
        path = pathlib.Path(s)
    except ValueError:
        path = None

    if path is None or not path.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return path


def user(s):
    import pwd

    try:
        pwd.getpwnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown user: {s}')
    return s


def group(s):
    import grp

    try:
        grp.getgrnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown group: {s}')
    return s


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

parser.add_argument('source_dir', type=directory, help='archive source directory')

parser.add_argument('dest_dir', type=directory, help='directory for tar archive')

parser.add_argument('--name', metavar='TEMPLATE',
                    type=template, default=NAME_TEMPLATE,
                    help='archive filename time.strftime() format string template'
                         f' (default: {NAME_TEMPLATE.replace("%", "%%")})')

parser.add_argument('--exclude-file', metavar='PATH', type=exclude_file,
                    help='path to file with one line per blacklist item')

parser.add_argument('--no-auto-compress', dest='auto_compress', action='store_false',
                    help="don't pass --auto-compress to tar")

parser.add_argument('--owner', type=user, help='tar archive owner')

parser.add_argument('--group', type=group, help='tar archive group')

parser.add_argument('--chmod', metavar='MODE', type=mode, default=CHMOD,
                    help=f'tar archive chmod (default: {CHMOD:03o})')

parser.add_argument('--set-path', metavar='LINE', default=SUBPROCESS_PATH,
                    help=f'PATH for tar subprocess (default: {SUBPROCESS_PATH})')

parser.add_argument('--set-umask', metavar='MASK', type=mode, default=SET_UMASK,
                    help=f'umask for tar subprocess (default: {SET_UMASK:03o})')

parser.add_argument('--ask-for-deletion', action='store_true',
                    help='prompt for tar archive deletion before exit')

parser.add_argument('--version', action='version', version=__version__)


def make_exclude_match(path, encoding='utf-8'):
    if path is None:
        return lambda x: False

    def iterpatterns(lines):
        for l in lines:
            l = l.strip()
            if l and not l.startswith('#'):
                path = pathlib.Path(l)
                if not path.is_absolute():
                    raise NotImplementedError
                yield path.parts

    with path.open(encoding=encoding) as f:
        patterns = set(iterpatterns(f))

    tree = {'/': {}}
    for parts in sorted(patterns):
        root, *parts = parts
        root = tree[root]
        for has_next, p in enumerate(parts, 1 - len(parts)):
            if p in root:
                assert (root[p] is not None) == bool(has_next)
            else:
                root[p] = {} if has_next else None
            root = root[p]

    def make_regex(tree, indent=' ' * 4):
        for name, root in tree.items():
            rest = ''
            if root is not None:
                root = '|\n'.join(make_regex(root, indent=indent + (' ' * 4)))
                assert root
                rest = f'(?:{os.sep}(?:\n{root}\n{indent}))'
            yield f'{indent}{re.escape(name)}{rest}'

    pattern = '|\n'.join(make_regex(tree['/']))
    pattern = f'/(?:\n{pattern}\n)(?:{os.sep}.*)?'
    pattern = re.compile(pattern, flags=re.VERBOSE)

    def match(dentry, _fullmatch=pattern.fullmatch):
        return _fullmatch(dentry.path) is not None

    return match


def iterfiles(root, exclude_match, infos=None, sep=os.sep):
    n_dirs = n_files = n_symlinks = n_other = n_bytes = n_excluded = 0

    stack = [('', root)]
    while stack:
        prefix, root = stack.pop()
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


def run_args_kwargs(source_dir, dest_path, *, auto_compress, set_path, encoding=ENCODING):
    cmd = ['tar',
           '--create',
           '--file', dest_path,
           '--files-from', '-', '--null', '--verbatim-files-from']

    if auto_compress:
        cmd.append('--auto-compress')

    kwargs = {'cwd':  source_dir,
              'env': {'PATH': set_path},
              'encoding': encoding}

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


def prompt_for_deletion(path):
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


def main(args=None):
    args = parser.parse_args(args)

    dest_path = args.dest_dir / args.name

    log(f'tar source: {args.source_dir}',
        f'tar destination: {dest_path}')

    if dest_path.exists():
        return f'error: result file already exists'

    match = make_exclude_match(args.exclude_file)

    infos = {}
    files = sorted(iterfiles(args.source_dir, match, infos=infos))
    log('traversed source: (', end='')
    counts = 'dirs', 'files', 'symlinks', 'other', 'excluded'
    log(*(f"{infos['n_' + c]} {c}" for c in counts), sep=', ', end=')\n')
    log(f"file size sum: {infos['n_bytes']} bytes")

    cmd, kwargs = run_args_kwargs(args.source_dir, dest_path,
                                  auto_compress=args.auto_compress,
                                  set_path=args.set_path)

    log('', f'os.umask(0o{args.set_umask:03o})')
    os.umask(args.set_umask)

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
    log(f'tar result: {dest_path} ({dest_stat.st_size} bytes)')
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
        prompt_for_deletion(dest_path)

    return None


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
