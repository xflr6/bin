import importlib
import socket as _socket

import pytest

log_udp = importlib.import_module('log-udp')


@pytest.mark.usefixtures('mock_pwd_grp', 'mock_strftime')
def test_log_udp(capsys, mocker, host='127.0.0.1', port=9):
    def recvfrom():
        yield b'spam lovely spam', (host, port)
        raise SystemExit

    socket = mocker.patch('socket.socket', autospec=True)
    socket.return_value.recvfrom.side_effect = recvfrom()

    assert log_udp.main(['--host', host,
                         '--port', str(port),
                         '--setuid', 'nonuser',
                         '--chroot', '.',
                         '--no-hardening',
                         '--verbose']) is None

    captured = capsys.readouterr()
    assert 'spam lovely' in captured.out
    assert captured.err == ''

    s = mocker.call()
    socket_calls = [mocker.call(_socket.AF_INET, _socket.SOCK_DGRAM),
                    s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1),
                    s.bind((host, port)),
                    s.recvfrom(1024),
                    s.recvfrom(1024),
                    s.close()]

    assert socket.mock_calls == socket_calls
