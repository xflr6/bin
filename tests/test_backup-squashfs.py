import importlib
import subprocess

import pytest

backup_squashfs = importlib.import_module('backup-squashfs')


@pytest.mark.usefixtures('mock_strftime', 'mock_pwd_grp')
def test_backup_squashfs(tmp_path, mocker):
    s_dir = tmp_path / 'source'
    s_dir.mkdir()

    d_path = tmp_path / 'archive-19700101-0000.sfs'

    e_path = tmp_path / 'mock.excludes'
    e_path.write_bytes(b'\n')

    def run(*args, **kwargs):
        d_path.write_bytes(b'\xde\xad\xbe\xef')
        return mocker.create_autospec(subprocess.CompletedProcess, returncode=0)

    umask = mocker.patch('os.umask', autospec=True)
    run = mocker.patch('subprocess.run', side_effect=run, autospec=True)
    chown = mocker.patch('shutil.chown', autospec=True)

    backup_squashfs.main([str(s_dir), str(d_path.parent),
                          '--name', 'archive-%Y%m%d-%H%M.sfs',
                          '--exclude-file', str(e_path),
                          '--comp', 'gzip',
                          '--owner', 'nonuser',
                          '--group', 'nongroup',
                          '--chmod', '440',
                          '--set-path', '/bin',
                          '--set-umask', '066'])

    umask.assert_called_once_with(0o066)

    run.assert_called_once_with(['mksquashfs', s_dir, d_path, '-noappend',
                                 '-ef', e_path,
                                 '-comp', 'gzip'],
                                check=True,
                                env={'PATH': '/bin'})

    chown.assert_called_once_with(d_path, user='nonuser', group='nongroup')
