import importlib
import json

git_pull_gists = importlib.import_module('git-pull-gists')


def test_main(tmp_path, mocker, mock_run, http_resp):
    present = tmp_path / 'present.git'
    present.mkdir()

    absent = tmp_path / 'absent.git'
    assert not absent.exists()
    absent_url = f'git@example.com:spam/{absent.name}'

    http_resp.read.return_value = json.dumps([
        {'git_push_url': f'git@example.com:spam/{present.name}'},
        {'git_push_url': absent_url}])

    urlopen = mocker.patch('urllib.request.urlopen', autospec=True,
                           return_value=http_resp)

    assert git_pull_gists.main([str(tmp_path), 'spam']) is None

    urlopen.assert_called_once_with('https://api.github.com/users/spam/gists')

    http_resp.assert_has_calls([mocker.call.__enter__(),
                                mocker.call.read(),
                                mocker.call.__exit__(None, None, None),
                                mocker.call.info()])

    clone = mocker.call(['git', 'clone', '--mirror', absent_url],
                        cwd=tmp_path, check=True)

    update = mocker.call(['git', 'remote', 'update'],
                         cwd=present, check=True)

    assert mock_run.call_args_list == [update, clone]

    assert not mock_run.return_value.mock_calls
