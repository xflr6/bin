import importlib
import subprocess

import pytest

dumpall_svn = importlib.import_module('dumpall-svn')


def test_dumpall_svn(tmp_path, mocker):
    present = tmp_path / 'present'
    present.mkdir()

    result = tmp_path / 'present.svndump.gz'
    assert not result.exists()

    proc = mocker.MagicMock(args=['nonarg'], returncode=0,
                            **{'communicate.return_value': ('', '')})
    proc.__enter__.return_value = proc

    def Popen(*args, stdout=None, **kwargs):
        if stdout not in (None, subprocess.PIPE):
            stdout.write(b'\xde\xad\xbe\xef')
        return proc

    Popen = mocker.patch('subprocess.Popen', side_effect=Popen, autospec=True)

    assert dumpall_svn.main([str(tmp_path), str(present)]) is None

    env = {'PATH': '/usr/bin:/bin'}

    dump = mocker.call(['svnadmin', 'dump', '--deltas', '--quiet', present],
                       stdin=None, stdout=subprocess.PIPE, env=env)

    compress = mocker.call(['gzip', '--stdout'],
                           stdin=mocker.ANY, stdout=mocker.ANY, env=env)

    assert Popen.call_args_list == [dump, compress]
