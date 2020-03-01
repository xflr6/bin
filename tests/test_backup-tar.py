import importlib

import pytest

backup_tar = importlib.import_module('backup-tar')


@pytest.mark.usefixtures('mock_pwd_grp', 'mock_strftime')
def test_backup_tar(tmp_path, mocker):
    s_dir = tmp_path / 'source'
    s_dir.mkdir()

    d_path = tmp_path / 'archive-19700101-0000.tar.gz'

    e_path = tmp_path / 'mock.excludes'
    e_path.write_bytes(b'\n')

    def Popen(*args, **kwargs):
        d_path.write_bytes(b'\xde\xad\xbe\xef')
        return mocker.DEFAULT

    umask = mocker.patch('os.umask', autospec=True)
    run = mocker.patch('subprocess.Popen', side_effect=Popen, autospec=True)
    chown = mocker.patch('shutil.chown', autospec=True)

    backup_tar.main([str(s_dir), str(d_path.parent),
                     '--name', 'archive-%Y%m%d-%H%M.tar.gz',
                     '--exclude-file', str(e_path),
                     '--owner', 'nonuser',
                     '--group', 'nongroup',
                     '--chmod', '440',
                     '--set-path', '/bin',
                     '--set-umask', '066'])

    umask.assert_called_once_with(0o066)

    run.assert_called_once_with(['tar', '--create', '--file', d_path,
                                 '--files-from', '-',
                                 '--null', '--verbatim-files-from',
                                 '--auto-compress'],
                                stdin=mocker.ANY,
                                cwd=s_dir,
                                encoding='utf-8',
                                env={'PATH': '/bin'})

    chown.assert_called_once_with(d_path, user='nonuser', group='nongroup')
