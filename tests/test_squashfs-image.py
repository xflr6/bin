import importlib

import pytest

squashfs_image = importlib.import_module('squashfs-image')


@pytest.mark.usefixtures('mock_pwd_grp', 'mock_strftime')
def test_main(tmp_path, mocker, completed_proc):
    s_dir = tmp_path / 'source'
    s_dir.mkdir()

    d_path = tmp_path / 'archive-19700101-0000.sfs'

    e_path = tmp_path / 'mock.excludes'
    e_path.write_bytes(b'\n')

    def run(*args, **kwargs):
        d_path.write_bytes(b'\xde\xad\xbe\xef')
        return completed_proc

    umask = mocker.patch('os.umask', autospec=True)
    run = mocker.patch('subprocess.run', autospec=True, side_effect=run)
    chown = mocker.patch('shutil.chown', autospec=True)

    assert squashfs_image.main([str(s_dir), str(d_path.parent),
                                '--name', 'archive-%Y%m%d-%H%M.sfs',
                                '--exclude-file', str(e_path),
                                '--comp', 'gzip',
                                '--owner', 'nonuser',
                                '--group', 'nongroup',
                                '--chmod', '440',
                                '--set-path', '/bin',
                                '--set-umask', '066']) is None

    umask.assert_called_once_with(0o066)

    run.assert_called_once_with(['mksquashfs', s_dir, d_path, '-noappend',
                                 '-ef', e_path,
                                 '-comp', 'gzip'],
                                check=True,
                                env={'PATH': '/bin'})

    assert not completed_proc.mock_calls

    chown.assert_called_once_with(d_path, user='nonuser', group='nongroup')
