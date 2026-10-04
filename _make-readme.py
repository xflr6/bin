#!/usr/bin/env python3

"""Insert --help output of *.py as usage into README.md file."""

from collections.abc import Iterable
import pathlib
import subprocess
import sys

ROOT = pathlib.Path()

PATH = ROOT / 'README.md'

REPLACE_AFTER = '\n## Usage\n'

REPLACE_BEFORE = '\n## License\n'

TEMPLATE = '''
### {name}

```shell
$ {cmd}
{output}
```
'''.strip()

ENCODING = 'utf-8'


def iterhelp(directory: pathlib.Path = ROOT, /, *,
             pattern: str = '*.py') -> Iterator[tuple[str, str, str]]:
    for path in sorted(directory.glob(pattern)):
        if path.name.startswith('_'):
            continue
        cmd = [sys.executable, path, '--help']
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, encoding=ENCODING)
        stdout = proc.stdout if not proc.returncode else None
        yield path.name, ' '.join(map(str, cmd[1:])), stdout


usage = '\n\n\n'.join(TEMPLATE.format(name=name, cmd=cmd, output=stdout.rstrip())
                      for name, cmd, stdout in iterhelp() if stdout)

old = PATH.read_text(encoding=ENCODING).strip()

(head, sep_start, rest) = old.partition(REPLACE_AFTER)
assert head and sep_start and rest

(_, sep_end, tail) = rest.partition(REPLACE_BEFORE)
assert sep_end and tail

new = f'''
{head}{sep_start}

{usage}

{sep_end}{tail}
'''.lstrip()

PATH.write_text(new, encoding=ENCODING)
