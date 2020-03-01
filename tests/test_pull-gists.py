import importlib
import json

pull_gists = importlib.import_module('pull-gists')


def test_pull_repos(tmp_path, mocker):
    present = tmp_path / 'present.git'
    present.mkdir()

    absent = tmp_path / 'absent.git'
    assert not absent.exists()
    absent_url = f'git@example.com:spam/{absent.name}'

    gists = json.dumps([{'git_push_url': f'git@example.com:spam/{present.name}'},
                        {'git_push_url': absent_url}])

    resp = mocker.NonCallableMock(**{'read.return_value': gists,
                                     'info.return_value': {}})

    urlopen = mocker.patch('urllib.request.urlopen', autospec=True,
                           **{'return_value.__enter__.return_value': resp})
    run = mocker.patch('subprocess.run', autospec=True)

    assert pull_gists.main([str(tmp_path), 'spam']) is None

    urlopen.assert_called_once_with('https://api.github.com/users/spam/gists')

    clone = mocker.call(['git', 'clone', '--mirror', absent_url],
                        cwd=tmp_path, check=True)

    update = mocker.call(['git', 'remote', 'update'],
                         cwd=present, check=True)

    assert run.call_args_list == [update, clone]
