import subprocess
import sys
import time

import pytest

TEST_NOW = time.gmtime(0)


@pytest.fixture
def mock_pwd_grp(monkeypatch, mocker):
    pwd = mocker.NonCallableMock(name='pwd')
    pwd.getpwuid.return_value.pw_name = 'nonuser'
    monkeypatch.setitem(sys.modules, 'pwd', pwd)

    grp = mocker.NonCallableMock(name='grp')
    grp.getgrgid.return_value.pw_name = 'nongroup'
    monkeypatch.setitem(sys.modules, 'grp', grp)


@pytest.fixture
def mock_strftime(mocker):
    from time import strftime as _strftime

    def strftime(format, t=TEST_NOW):
        return _strftime(format, t)

    yield mocker.patch('time.strftime', autospec=True, side_effect=strftime)


@pytest.fixture
def completed_proc(mocker):
    return mocker.create_autospec(subprocess.CompletedProcess, instance=True,
                                  name='subprocess.run()', returncode=0)


@pytest.fixture
def mock_run(mocker, completed_proc):
    yield mocker.patch('subprocess.run', autospec=True,
                       return_value=completed_proc)
