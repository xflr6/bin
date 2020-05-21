import importlib
import socket as _socket

import pytest

log_udp = importlib.import_module('log-udp')


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_udp(capsys, mocker, host='127.0.0.1', port=9, encoding='utf-8'):
    msg = 'spam lovely spam'

    packets = iter([msg.encode(encoding)])

    def recvfrom_into(buf):
        try:
            p = next(packets)
        except StopIteration:
            raise SystemExit
        assert len(p) <= len(buf)
        buf[:len(p)] = p
        return len(p), (host, port)

    socket = mocker.patch('socket.socket', autospec=True)
    socket.return_value.recvfrom_into.side_effect = recvfrom_into

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
    socket.assert_has_calls([s,
                             s.bind((host, port)),
                             s.recvfrom_into(mocker.ANY),
                             s.recvfrom_into(mocker.ANY),
                             s.close()])
