import functools
import importlib
import os
import subprocess

import pytest

dumpall_svn = importlib.import_module('dumpall-svn')


@pytest.mark.usefixtures('mock_strftime')
def test_dumpall_svn(tmp_path, mocker):
    present = tmp_path / 'present'
    present.mkdir()

    result = tmp_path / 'present-19700101-0000.svndump.gz'
    assert not result.exists()

    proc = mocker.MagicMock(args=['nonarg'], returncode=0,
                            **{'communicate.return_value': ('', '')})
    proc.__enter__.return_value = proc

    outfd = None

    def Popen(*args, stdout=None, **kwargs):
        if stdout not in (None, subprocess.PIPE):
            nonlocal outfd
            outfd = stdout
            stdout.write(b'\xde\xad\xbe\xef')
        return proc

    Popen = mocker.patch('subprocess.Popen', side_effect=Popen, autospec=True)

    open_spy = mocker.patch('builtins.open', wraps=open, autospec=True)

    path = '/bin'

    assert dumpall_svn.main([str(tmp_path), str(present),
                             '--name', '{name}-%Y%m%d-%H%M.svndump.gz',
                             '--chmod', '600',
                             '--set-path', path]) is None

    assert result.exists() and result.read_bytes() == b'\xde\xad\xbe\xef'

    assert outfd.name == str(result)

    open_spy.assert_called_once_with(result, 'xb', opener=mocker.ANY)
    opener = open_spy.call_args.kwargs['opener']
    assert isinstance(opener, functools.partial) and opener.func is os.open
    assert (opener.args,  opener.keywords) == ((), {'mode': 0o600})

    env = {'PATH': path}

    dump = mocker.call(['svnadmin', 'dump', '--deltas', '--quiet', present],
                       stdin=None, stdout=subprocess.PIPE, env=env)

    compress = mocker.call(['gzip', '--stdout'],
                           stdin=proc.stdout, stdout=outfd, env=env)

    assert Popen.call_args_list == [dump, compress]
