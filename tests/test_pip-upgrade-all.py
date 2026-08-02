import importlib
import subprocess

import pytest

pip_upgrade_all = importlib.import_module('pip-upgrade-all')

PIP_LIST_STDOUT = '''
Package  Version Latest Type
-------- ------- ------ -----
docutils 0.22.4  0.23   wheel
pandas   2.3.3   3.0.5  wheel
pytest   8.0.2   9.1.1  wheel
'''.lstrip()


@pytest.fixture
def mock_input(monkeypatch, mocker):
    assert not hasattr(pip_upgrade_all, 'input')
    result = mocker.create_autospec(input)
    monkeypatch.setattr(pip_upgrade_all, 'input', result, raising=False)
    return result


@pytest.mark.parametrize(
    'pip_list_out, input_answers, asked_packages, upgraded_packages',
    [(PIP_LIST_STDOUT, ['yes', 'y', 'y', 'y'],
      ['docutils', 'pandas', 'pytest'], ['docutils', 'pandas', 'pytest']),
     (PIP_LIST_STDOUT, ['no', 'n', 'y', 'y'],
      ['docutils', 'pandas', 'pytest'], ['pytest']),
     (PIP_LIST_STDOUT, ['no', 'n', 'y', 'n'],
      ['docutils', 'pandas', 'pytest'], []),
     (PIP_LIST_STDOUT, ['no', 'n', 'n'],
      ['docutils', 'pandas', 'pytest'], []),
     ('\n', [], [], [])],
    ids=['three_outdated_all_confirmed_and_upgraded',
         'three_outdated_final_confirmed_and_upgraded',
         'three_outdated_final_confirmed_and_aborted',
         'three_outdated_zero_confirmed',
         'zero_outdated'])
def test_main(capsys, mocker, mock_run, mock_input, pip_list_out, input_answers,
              asked_packages, upgraded_packages):
    list_proc = mocker.create_autospec(subprocess.CompletedProcess,
                                       instance=True, name='subprocess.run()',
                                       returncode=0, stdout=pip_list_out)
    install_proc = mocker.create_autospec(subprocess.CompletedProcess,
                                          instance=True, name='subprocess.run()',
                                          returncode=0)
    mock_run.side_effect = [list_proc, install_proc]
    mock_input.side_effect = input_answers

    result = pip_upgrade_all.main()
    if (asked_packages and not upgraded_packages
        and len(input_answers) > len(asked_packages)):
        assert result == 'Upgrade aborted on request.'
    else:
        assert result is None

    (out, _) = capsys.readouterr()
    assert out.startswith(pip_list_out)

    list_call = mocker.call([mocker.ANY, '-m', 'pip', 'list', '--outdated'],
                            check=True, text=True, capture_output=True)
    install_call = mocker.call([mocker.ANY, '-m', 'pip', 'install', '--upgrade']
                               + upgraded_packages,
                               check=True, text=True, capture_output=False)
    if not asked_packages or not upgraded_packages:
        assert mock_run.mock_calls == [list_call]
        if not asked_packages:
            assert out.rstrip().endswith('No packages to --upgrade, exiting.')
        return
    assert mock_run.mock_calls == [list_call, install_call]

    input_calls = [mocker.call(mocker.ANY)] * (len(asked_packages) + 1)
    assert mock_input.mock_calls == input_calls
    (*list_prompts, install_prompt) = [c.args[0] for c in mock_input.mock_calls]
    for prompt, package in zip(list_prompts, asked_packages, strict=True):
        assert prompt.startswith(f'Upgrade {package}=')
    assert install_prompt.startswith(
        f'Run pip install --upgrade {" ".join(upgraded_packages)}')
