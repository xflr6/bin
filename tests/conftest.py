import http.client
import io
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
def proc(mocker, name='subprocess.Popen()'):
    result = mocker.create_autospec(subprocess.Popen, instance=True, name=name,
                                    args=['nonarg'], pid=-1, returncode=0,
                                    stdin=mocker.NonCallableMock(),
                                    stdout=mocker.NonCallableMock(),
                                    stderr=mocker.NonCallableMock(),
                                    encoding=None, errors=None)

    result.__enter__.return_value = result

    result.communicate.return_value = ('', '')
    return result


@pytest.fixture
def completed_proc(mocker, name='subprocess.run()'):
    return mocker.create_autospec(subprocess.CompletedProcess, instance=True,
                                  name=name, returncode=0)


@pytest.fixture
def mock_run(mocker, completed_proc):
    yield mocker.patch('subprocess.run', autospec=True,
                       return_value=completed_proc)


@pytest.fixture
def http_resp(mocker, name='urllib.request.urlopen()'):
    result = mocker.NonCallableMock(http.client.HTTPResponse, name=name,
                                    wraps=io.BytesIO())

    result.attach_mock(mocker.Mock(return_value=result), '__enter__')
    result.attach_mock(mocker.Mock(), '__exit__')

    result.attach_mock(mocker.Mock(return_value={}), 'info')

    return result
