#!/usr/bin/env python3

"""Insert --help output of *.py as usage into README.md file."""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path()

PATH = ROOT / 'README.md'

REPLACE_AFTER = '\n## Usage\n'

REPLACE_BEFORE = '\n## License\n'

ENCODING = 'utf-8'


def iterhelp(directory: pathlib.Path = ROOT, *, pattern: str = '*.py'):
    for p in sorted(directory.glob(pattern)):
        if p.name.startswith('_'):
            continue
        cmd = [sys.executable, p, '--help']
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, encoding=ENCODING)
        stdout = proc.stdout if not proc.returncode else None
        yield list(map(str, cmd[1:])), stdout


usage = '\n\n\n'.join(f"### {cmd[0]}\n\n```shell\n$ {' '.join(cmd)}\n{stdout}```"
                      for cmd, stdout in iterhelp() if stdout)

old = PATH.read_text(encoding=ENCODING)

(head, sep_1, rest) = old.partition(REPLACE_AFTER)
assert head and sep_1 and rest

(_, sep_2, tail) = rest.partition(REPLACE_BEFORE)
assert sep_2 and tail

new = f'{head}{sep_1}\n\n{usage}\n\n{sep_2}{tail}'

PATH.write_text(new, encoding=ENCODING)
