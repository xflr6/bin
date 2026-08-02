import importlib

pip_upgrade_all = importlib.import_module('pip-upgrade-all')

PIP_STDOUT = '''
Package  Version Latest Type
-------- ------- ------ -----
docutils 0.22.4  0.23   wheel
pandas   2.3.3   3.0.5  wheel
pytest   8.0.2   9.1.1  wheel
'''.lstrip()


def test_main(mocker):
    mock_run = mocker.patch('subprocess.run', autospec=True,
                            **{'return_value.stdout': PIP_STDOUT})
    mock_input = mocker.patch.object(pip_upgrade_all, 'input', return_value='y')

    assert pip_upgrade_all.main() is None

    assert mock_input.mock_calls == [mocker.call(mocker.ANY)] * 4
    (*package_prompts, final_prompt) = [c.args[0] for c in mock_input.mock_calls]
    assert package_prompts == [
        'Upgrade docutils=0.22.4 to 0.23 (wheel)? [yes]/no: ',
        'Upgrade pandas=2.3.3 to 3.0.5 (wheel)? [yes]/no: ',
        'Upgrade pytest=8.0.2 to 9.1.1 (wheel)? [yes]/no: ']
    assert final_prompt.endswith(
        "'pip', 'install', '--upgrade', 'docutils', 'pandas', 'pytest']?"
        " yes/no: ")

    assert mock_run.mock_calls == [
        mocker.call([mocker.ANY, '-m', 'pip', 'list', '--outdated'],
                    check=True, capture_output=True, encoding='utf-8'),
        mocker.call([mocker.ANY,  '-m', 'pip', 'install',  '--upgrade',
                     'docutils', 'pandas', 'pytest'],
                    check=True, capture_output=False)]
