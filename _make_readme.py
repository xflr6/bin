#!/usr/bin/env python3

"""Insert --help output of *.py as usage into README file."""

import pathlib
import platform
import subprocess

README_PATH = pathlib.Path('README.md')

REPLACE_AFTER = '\n## Usage\n'

REPLACE_BEFORE = '\n## License\n'

ENCODING = 'utf-8'


def iterhelp(directory=pathlib.Path(), pattern='*.py'):
    python = 'python' if platform.system() == 'Windows' else 'python3'
    for p in sorted(directory.glob(pattern)):
        if not p.name.startswith('_'):
            cmd = [python, p, '--help']
            kwargs = {'encoding': ENCODING}
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, **kwargs)
            stdout = proc.stdout if not proc.returncode else None
            yield list(map(str, cmd[1:])), stdout


usage = '\n\n\n'.join(f"### {cmd[0]}\n\n```sh\n$ {' '.join(cmd)}\n{stdout}```"
                      for cmd, stdout in iterhelp() if stdout)

text = README_PATH.read_text(encoding=ENCODING)

head, sep_1, rest = text.partition(REPLACE_AFTER)
assert head and sep_1 and rest

_, sep_2, tail = rest.partition(REPLACE_BEFORE)
assert sep_2 and tail

text = f'{head}{sep_1}\n\n{usage}\n\n{sep_2}{tail}'

README_PATH.write_text(text, encoding=ENCODING)
