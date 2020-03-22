import importlib
import subprocess

import pytest

backup_tar = importlib.import_module('backup-tar')


@pytest.mark.usefixtures('mock_pwd_grp', 'mock_strftime')
def test_backup_tar(tmp_path, mocker):
    s_dir = tmp_path / 'source'
    s_dir.mkdir()

    d_path = tmp_path / 'archive-19700101-0000.tar.gz'

    e_path = tmp_path / 'mock.excludes'
    e_path.write_bytes(b'\n')

    proc = mocker.create_autospec(subprocess.Popen, instance=True,
                                  name='subprocess.Popen()', returncode=0)
    proc.__enter__.return_value = proc
    proc.communicate.return_value = ('', '')

    def Popen(*args, **kwargs):
        d_path.write_bytes(b'\xde\xad\xbe\xef')
        return proc

    umask = mocker.patch('os.umask', autospec=True)
    Popen = mocker.patch('subprocess.Popen', autospec=True, side_effect=Popen)
    chown = mocker.patch('shutil.chown', autospec=True)

    assert backup_tar.main([str(s_dir), str(d_path.parent),
                            '--name', 'archive-%Y%m%d-%H%M.tar.gz',
                            '--exclude-file', str(e_path),
                            '--owner', 'nonuser',
                            '--group', 'nongroup',
                            '--chmod', '440',
                            '--set-path', '/bin',
                            '--set-umask', '066']) is None

    umask.assert_called_once_with(0o066)

    Popen.assert_called_once_with(['tar', '--create', '--file', d_path,
                                   '--files-from', '-',
                                   '--null', '--verbatim-files-from',
                                   '--auto-compress'],
                                  stdin=mocker.ANY,
                                  cwd=s_dir,
                                  encoding='utf-8',
                                  env={'PATH': '/bin'})

    proc.assert_has_calls([mocker.call.__enter__(),
                           mocker.call.communicate()])

    chown.assert_called_once_with(d_path, user='nonuser', group='nongroup')
