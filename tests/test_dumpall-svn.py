import functools
import importlib
import os
import subprocess

import pytest

dumpall_svn = importlib.import_module('dumpall-svn')


@pytest.mark.usefixtures('mock_strftime')
def test_dumpall_svn(tmp_path, mocker, proc):
    present = tmp_path / 'present'
    present.mkdir()

    result = tmp_path / 'present-19700101-0000.svndump.gz'
    assert not result.exists()

    outfd = None

    def Popen(*args, stdout=None, **kwargs):
        if stdout not in (None, subprocess.PIPE):
            nonlocal outfd
            outfd = stdout
            outfd.write(b'\xde\xad\xbe\xef')
        return proc

    Popen = mocker.patch('subprocess.Popen', autospec=True, side_effect=Popen)

    open_spy = mocker.patch('builtins.open', autospec=True, wraps=open)

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
    assert (opener.args, opener.keywords) == ((), {'mode': 0o600})

    env = {'PATH': path}

    dump = mocker.call(['svnadmin', 'dump', '--deltas', '--quiet', present],
                       stdin=None, stdout=subprocess.PIPE, env=env)

    compress = mocker.call(['gzip'], stdin=proc.stdout, stdout=outfd, env=env)

    assert Popen.call_args_list == [dump, compress]

    proc.assert_has_calls([mocker.call.__enter__(proc),
                           mocker.call.__enter__(proc),
                           mocker.call.communicate(),
                           mocker.call.communicate(),
                           mocker.call.__exit__(proc, None, None, None),
                           mocker.call.__exit__(proc, None, None, None)])
