import importlib
import socket as _socket

import pytest

log_udp = importlib.import_module('log-udp')


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_udp(capsys, mocker, host='127.0.0.1', port=9, encoding='utf-8'):
    socket = mocker.patch('socket.socket', autospec=True)

    msg = 'spam lovely spam'

    def recvfrom():
        yield msg.encode(encoding), (host, port)
        raise SystemExit

    socket.return_value.recvfrom.side_effect = recvfrom()

    assert log_udp.main(['--host', host,
                         '--port', str(port),
                         '--setuid', 'nonuser',
                         '--chroot', '.',
                         '--no-hardening',
                         '--verbose']) is None

    out, err = capsys.readouterr()
    assert msg in out
    assert not err

    s = mocker.call(_socket.AF_INET, _socket.SOCK_DGRAM)
    setsockopt = s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)

    assert socket.mock_calls == [s, setsockopt,
                                 s.bind((host, port)),
                                 s.recvfrom(1024),
                                 s.recvfrom(1024),
                                 s.close()]
