import sys
import time

import pytest

TEST_NOW = time.gmtime(0)


@pytest.fixture
def mock_pwd_grp(monkeypatch, mocker):
    pwd = mocker.NonCallableMock(**{'getpwuid.return_value.pw_name': 'nonuser'})
    grp = mocker.NonCallableMock(**{'getgrgid.return_value.pw_name': 'nongroup'})
    monkeypatch.setitem(sys.modules, 'pwd', pwd)
    monkeypatch.setitem(sys.modules, 'grp', grp)


@pytest.fixture
def mock_strftime(mocker):
    from time import strftime as _strftime

    def strftime(format, t=TEST_NOW):
        return _strftime(format, t)

    yield mocker.patch('time.strftime', side_effect=strftime, autospec=True)
