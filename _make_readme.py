#!/ust/bin/env python3

import pathlib
import subprocess
import platform

PATH = pathlib.Path('README.md')

CWD = pathlib.Path()

ENCODING = 'utf-8'

REPLACE_AFTER = '\n## Usage\n'


def iterhelp(directory, pattern='*.py'):
    python = 'python' if platform.system() == 'Windows' else 'python3'
    for p in sorted(directory.glob(pattern)):
        if not p.name.startswith('_'):
            cmd = [python, p, '--help']
            kwargs = {'encoding': ENCODING}
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, **kwargs)
            stdout = None if proc.returncode else proc.stdout
            yield list(map(str, cmd[1:])), stdout


helps = list(iterhelp(CWD))

with PATH.open(encoding=ENCODING) as f:
    tmpl = f.read()

page, sep, rest = tmpl.partition(REPLACE_AFTER)

assert sep
assert page

rest = '\n\n\n'.join(f"### {cmd[0]}\n\n```sh\n$ {' '.join(cmd)}\n{stdout}```"
                     for cmd, stdout in helps if stdout)

doc = f'{page}{sep}\n\n{rest}'

with PATH.open('w', encoding=ENCODING) as f:
    print(doc, file=f)
