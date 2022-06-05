import contextlib
import hashlib
import importlib
import os
import pathlib

update_shasums = importlib.import_module('update-shasums')

ENCODING = 'utf-8'

PATTERN = r'- ([\w.-]+) ([0-9a-f]{64})(?=\W)'

DATA = b'\xde\xad\xbe\xef'

HASH = hashlib.sha256(DATA).hexdigest()


@contextlib.contextmanager
def chdir(path):
    cwd = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield None
    finally:
        os.chdir(cwd)


def test_update_shasums(tmp_path):
    globfile = tmp_path / 'data.bin'
    globfile.write_bytes(DATA)

    target = tmp_path / 'shasums.txt'
    target.write_text(f"# files\n\n- {globfile.name} {'0' * 64}\n",
                      encoding=ENCODING)

    with chdir(tmp_path):
        assert update_shasums.main(['--target', target.name,
                                    '--encoding', ENCODING,
                                    '--pattern', PATTERN,
                                    '*.bin']) is None

    assert globfile.read_bytes() == DATA

    result = target.read_text(encoding=ENCODING)

    assert result == ('# files\n'
                      '\n'
                      f'- {globfile.name} {HASH}\n')
