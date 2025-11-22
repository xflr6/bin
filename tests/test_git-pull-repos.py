import argparse
import importlib

import pytest

git_pull_repos = importlib.import_module('git-pull-repos')


def test_directory():
    with pytest.raises(argparse.ArgumentTypeError):
        git_pull_repos.directory(None)


@pytest.mark.parametrize('s, expected', [
    ('github.com:user/spam',
     {'dir': 'spam.git', 'url': 'git@github.com:user/spam.git'}),
])
def test_parse_url(s, expected):
    assert git_pull_repos.parse_url(s) == expected


def test_main(tmp_path, mocker, mock_run):
    present = tmp_path / 'present.git'
    present.mkdir()

    absent = tmp_path / 'absent.git'
    assert not absent.exists()
    absent_url = f'git@example.com:spam/{absent.name}'

    assert git_pull_repos.main([str(tmp_path),
                               f'git@example.com:spam/{present.name}',
                               absent_url]) is None

    clone = mocker.call(['git', 'clone', '--mirror', absent_url],
                        cwd=tmp_path, check=True)

    update = mocker.call(['git', 'remote', 'update'],
                         cwd=present, check=True)

    assert mock_run.call_args_list == [clone, update]

    assert not mock_run.return_value.mock_calls
