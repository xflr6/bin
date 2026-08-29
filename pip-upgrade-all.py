#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["packaging>=20"]
# ///

"""Run pip list --outdated, ask for confirmation, and run pip install --upgrade.

References:
- https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
"""

from __future__ import annotations

__title__ = 'pip-upgrade-all.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2026 Sebastian Bank'

import argparse
from collections.abc import Iterator, Sequence
import enum
import os
import re
import subprocess
import sys
import textwrap
from typing import Self, NamedTuple

import packaging.version


def parse_args(args: Sequence[str] | None, /) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.partition('\n')[0])
    parser.add_argument('--exclude', nargs='+', metavar='PKG',
                        help='package name(s) to exclude from upgrade.')
    parser.add_argument('--version', action='version', version=__version__)
    return parser.parse_args(args)


def pip_upgrade_all(*, exclude: Sequence[str] | None) -> str | None:
    print('Fetch --outdated packages to --upgrade...')
    exclude = set(exclude or [])
    candidates = [p for p in outdated_packages() if p.name not in exclude]
    if not (packages := [p for p in candidates if p.ask_for_confirmation()]):
        print('', 'No packages to --upgrade, exiting.', sep='\n')
        return None

    print('', 'Packages to --upgrade:', sep='\n')
    names = [p.name for p in packages]
    print(*names, sep='\n', end='\n\n')
    pip_args = ['install', '--upgrade'] + names
    if not user_confirmed(f'Run pip {" ".join(pip_args)}'):
        return 'Upgrade aborted on request.'

    run_pip(pip_args)
    return None


def outdated_packages() -> Iterator[OutdatedPackage]:
    if not (stdout := run_pip(['list', '--outdated'], capture_stdout=True)):
        return iter([])
    print(stdout, end='\n\n')
    return OutdatedPackage.iter_from_table(stdout)


def run_pip(args: Sequence[str], /, *,
            capture_stdout: bool = False) -> str | None:
    cmd = [sys.executable, '-m', 'pip'] + args
    proc = run(cmd, capture_output=capture_stdout)
    return proc.stdout.rstrip() if capture_stdout else None


def run(cmd: Sequence[str | os.PathLike[str]], /, *,
        capture_output: bool) -> subprocess.CompletedProcess[str]:
    print(f'subprocess.run({cmd})', file=sys.stderr)
    return subprocess.run(cmd, check=True, text=True,
                          capture_output=capture_output)


class OutdatedPackage(NamedTuple):

    name: str
    version: str
    latest: str
    type: str

    _pattern = re.compile(textwrap.dedent(r'''
                                          (?P<package>[\w.-]+)
                                          [ ]+
                                          (?P<version>\S+)
                                          [ ]+
                                          (?P<latest>\S+)
                                          [ ]+
                                          (?P<type>[\w]+)
                                          ''').strip(),
                          flags=re.VERBOSE | re.ASCII)

    @classmethod
    def iter_from_table(cls, stdout: str, /) -> Iterator[Self]:
        (header, sep, *body) = stdout.splitlines()
        assert re.fullmatch(r'Package +Version +Latest +Type', header)
        assert re.fullmatch(r'-+ -+ -+ -+', sep)
        return map(cls.from_line, body)

    @classmethod
    def from_line(cls, line: str, /) -> Self:
        if (ma := cls._pattern.fullmatch(line)) is None:
            raise ValueError(f'failed to parse {line=}')
        return cls(ma['package'], ma['version'], ma['latest'], ma['type'])

    @property
    def message(self) -> str:
        return (f'[{self.update.name}] Upgrade {self.name}'
                f' from {self.version} to {self.latest}'
                f' ({self.type})')

    @property
    def update(self) -> Update:
        (old, new) = map(Version, (self.version, self.latest))
        return Update.from_versions(old=old, new=new)

    def ask_for_confirmation(self) -> bool:
        return user_confirmed(self.message, default=self.update is Update.PATCH)


Version = packaging.version.Version


class Update(enum.Enum):

    @classmethod
    def from_versions(cls, *, old: Version, new: Version) -> Self:
        pairs = zip(*((v.epoch, v.major, v.minor, v.micro) for v in (old, new)))
        for (old_number, new_number), result in zip(pairs, cls):
            if old_number != new_number:
                return result
        return cls.OTHER

    EPOCH = 0
    MAJOR = 1
    MINOR = 2
    PATCH = 3
    OTHER = 4


def user_confirmed(message: str, /, *, default: bool | None = None) -> bool:
    possible_answers = ('y', 'yes', 'n', 'no')
    if default is not None:
        possible_answers = ('',) + possible_answers
        hint = '[yes]/no' if default else 'yes/[no]'
    else:
        hint = 'yes/no'

    prompt = f'{message}? {hint}: '
    while (line := input(prompt)) not in possible_answers:
        print('  (enter y(es) or n(o), or use CTRL-C to exit)')

    if not line:
        assert default is not None, "implied by '' in possible_answers"
        return default
    return line.startswith('y')


def main(args: Sequence[str] | None = None) -> str | None:
    args = parse_args(args)
    try:
        return pip_upgrade_all(exclude=args.exclude)
    except KeyboardInterrupt:
        return 'Aborted with CTRL-C.'


if __name__ == '__main__':  # pragma: no-cover
    sys.exit(main())
