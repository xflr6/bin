import argparse
import importlib
import subprocess

import pytest

pull_repos = importlib.import_module('pull-repos')


def test_directory():
    with pytest.raises(argparse.ArgumentTypeError):
        pull_repos.directory(None)


@pytest.mark.parametrize('s, expected', [
    ('github.com:user/spam',
     {'dir': 'spam.git', 'url': 'git@github.com:user/spam.git'}),
])
def test_parse_url(s, expected):
    assert pull_repos.parse_url(s) == expected


def test_pull_repos(tmp_path, mocker):
    present = tmp_path / 'present.git'
    present.mkdir()

    absent = tmp_path / 'absent.git'
    assert not absent.exists()
    absent_url = f'git@example.com:spam/{absent.name}'

    proc = mocker.create_autospec(subprocess.CompletedProcess, instance=True,
                                  name='subprocess.run()', returncode=0)

    run = mocker.patch('subprocess.run', autospec=True, return_value=proc)

    assert pull_repos.main([str(tmp_path),
                            f'git@example.com:spam/{present.name}',
                            absent_url]) is None

    clone = mocker.call(['git', 'clone', '--mirror', absent_url],
                        cwd=tmp_path, check=True)

    update = mocker.call(['git', 'remote', 'update'],
                         cwd=present, check=True)

    assert run.call_args_list == [clone, update]

    assert not proc.mock_calls
