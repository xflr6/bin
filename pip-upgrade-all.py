#!/usr/bin/env python3

"""Run pip list --outdated, ask for confirmation, and run pip install --upgrade.

References:
- https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
"""

__title__ = 'pip-upgrade-all.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2026 Sebastian Bank'

import argparse
from collections.abc import Iterator, Sequence
import re
import textwrap
import subprocess
import sys
from typing import Self, NamedTuple
import os

ROW_PATTERN = re.compile(textwrap.dedent(r'''
                                         (?P<package>[\w.-]+)
                                         [ ]+
                                         (?P<version>\S+)
                                         [ ]+
                                         (?P<latest>\S+)
                                         [ ]+
                                         (?P<type>[\w]+)
                                         ''').strip(),
                         flags=re.VERBOSE | re.ASCII)


parser = argparse.ArgumentParser(description=__doc__.partition('\n')[0])

parser.add_argument('--version', action='version', version=__version__)


def pip_upgrade_all() -> str | None:
    candidates = outdated_packages()
    if not (packages := [c for c in candidates if c. ask_for_confirmation()]):
        print('', 'No packages to --upgrade, exiting.', sep='\n')
        return None

    print('', 'Packages to --upgrade:', sep='\n')
    names = [p.name for p in packages]
    print(*names, sep='\n', end='\n\n')
    args = ['install', '--upgrade'] + names
    if not user_confirmed(f'Run pip {" ".join(args)}', default=None):
        return 'Upgrade aborted on request.'
    run_pip(args, capture_stdout=False)


def outdated_packages() -> Iterator[str]:
    stdout = run_pip(['list', '--outdated'], capture_stdout=True).rstrip()
    print(stdout, end='\n\n')
    if not stdout:
        return iter([])
    (header, sep, *body) = stdout.splitlines()
    assert re.fullmatch(r'Package +Version +Latest +Type', header)
    assert re.fullmatch(r'-+ -+ -+ -+', sep)
    return map(OutdatedPackage.from_line, body)


def run_pip(args: Sequence[str], /, *, capture_stdout: bool) -> str | None:
    cmd = [sys.executable, '-m', 'pip'] + args
    proc = run(cmd, capture_output=capture_stdout)
    return proc.stdout if capture_stdout else None


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

    _pattern = ROW_PATTERN

    @classmethod
    def from_line(cls, line: str, /) -> Self:
        if (ma := cls._pattern.fullmatch(line)) is None:
            raise ValueError(f'failed to parse {line=}')
        return cls(ma['package'], ma['version'], ma['latest'], ma['type'])

    def ask_for_confirmation(self) -> bool:
        message = (f'Upgrade {self.name}={self.version}'
                   f' to {self.latest} ({self.type})')
        return user_confirmed(message, default=True)


def user_confirmed(message: str, /, default: bool | None) -> bool:
    possible_answers = ('y', 'yes', 'n', 'no')
    if default is not None:
        hint = '[yes]/no' if default else 'yes/[no]'
        possible_answers = ('',) + possible_answers
    else:
        hint = 'yes/no'

    prompt = f'{message}? {hint}: '
    while (line := input(prompt)) not in possible_answers:
        print('  (enter y(es) or n(o), or use CTRL-C to exit)')

    if not line:
        assert default is not None
        return default
    return line.startswith('y')


def main(args: Sequence[str] | None = None) -> str | None:
    args = parser.parse_args(args)
    return pip_upgrade_all()


if __name__ == '__main__':
    parser.exit(main())
