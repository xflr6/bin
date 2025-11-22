#!/usr/bin/env python3

"""SHA256sum file(s) and update text file with regex locating name and hash."""

from __future__ import annotations

__title__ = 'shasum-update.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2017,2020 Sebastian Bank'

import argparse
import codecs
from collections.abc import Sequence
import functools
import hashlib
import pathlib
import re
import sys

ENCODING = 'utf-8'


def present_file(s: str) -> pathlib.Path:
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return result


def encoding(s: str) -> str:
    try:
        return codecs.lookup(s).name
    except LookupError:
        raise argparse.ArgumentTypeError(f'unknown encoding: {s}')


def file_checksum_pattern(s: str):
    try:
        result = re.compile(s, flags=re.DOTALL)
    except re.error as e:
        raise argparse.ArgumentTypeError(f'invalid regex pattern: {s} ({e!r})')

    if result.groups != 2:
        argparse.ArgumentTypeError(f'need exactly 2 groups: {s}')
    return result


def present_file_glob(s: str) -> list[pathlib.Path]:
    paths = list(pathlib.Path().glob(s))
    if not paths:
        raise argparse.ArgumentTypeError(f'no file(s) matched: {s}')

    missing = [p for p in paths if not p.exists()]
    if missing:
        raise argparse.ArgumentTypeError(f'file(s) not found: {missing}')

    nonfiles = [p for p in paths if p.exists() and not p.is_file()]
    if nonfiles:
        raise argparse.ArgumentTypeError(f'matched non-file(s): {nonfiles}')

    return paths


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--target', metavar='TEXT_FILE', type=present_file,
                    help='path to the text file to be updated')

parser.add_argument('--encoding', metavar='NAME', type=encoding,
                    default=ENCODING,
                    help='target text file read/write encoding'
                         f' (default: {ENCODING})')

parser.add_argument('--pattern', metavar='REGEX', type=file_checksum_pattern,
                    help='re.sub() pattern with file and checksum group')

parser.add_argument('--confirm', action='store_true',
                    help='prompt for confirmation before exit when updated')

parser.add_argument('glob', nargs='+', type=present_file_glob,
                    help='glob pattern of file(s) to checksum')


def shasum_update(*glob_paths: Sequence[pathlib.Path], target: pathlib.Path | None,
                  encoding: str,
                  pattern: re.Patterm[str] | None,
                  confirm: bool) -> str | None:
    if any(target in paths for paths in glob_paths):
        ValueError(f'target {target} also in files: {glob_paths}')

    sums = {p.name: sha256sum(p) for paths in glob_paths for p in paths}
    log(*(f'{f} {s}' for f, s in sums.items()))

    if target is not None:
        updated = interpolate(target,
                              pattern=pattern,
                              sums=sums,
                              encoding=encoding)

        log('\n%d updated%s' % (len(updated),
                                (' %r' % updated) if updated else ''))
        if confirm and updated:
            input('enter any string to end: ')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def sha256sum(filename, /) -> str:
    with open(filename, 'rb') as f:
        s = hashlib.file_digest(f, hashlib.sha256)
    return s.hexdigest()


def interpolate(filename, *, pattern, sums, encoding: str):
    updated = []

    def repl(ma):
        hash_ = sums[ma.group(1)]
        if ma.group(2) != hash_:
            updated.append(ma.group(1))
        context = ma.string[ma.start():ma.start(2)]
        return context + hash_

    with open(filename, encoding=encoding) as f:
        text = f.read()

    (text, n) = pattern.subn(repl, text)

    if n != len(sums):
        raise ValueError(f'mismatch {len(sums)} files but {n} pattern matches')

    if updated:
        with open(filename, 'wt', encoding=encoding) as f:
            f.write(text)

    return updated


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    return shasum_update(*args.glob, target=args.target,
                         encoding=args.encoding,
                         pattern=args.pattern,
                         confirm=args.confirm)


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
