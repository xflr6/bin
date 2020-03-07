import importlib
import socket as _socket

import pytest

log_pings = importlib.import_module('log-pings')


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_pings(capsys, mocker, host='127.0.0.1', encoding='utf-8'):
    socket = mocker.patch('socket.socket', autospec=True)

    msg = 'abcdefghijklmnopqrstuvwabcdefghi'

    headers = (b'\x45'              # version=4 ihl=5
               b'\x00'              # tos=0
               b'\x00\x3c'          # length=60
               b'\x00\x0f'          # ident=15
               b'\x00\x00'          # flags=0 fragoffset=0
               b'\x2a'              # ttl=42
               b'\x01'              # proto=1
               b'\xff\xff'          # checksum=65535
               b'\x7f\x00\x00\x02'  # scr_addr='127.0.0.2'
               b'\x7f\x00\x00\x01'  # dst_addr='127.0.0.1'
               b'\x08'              # type=8
               b'\x00'              # code=0
               b'\xff\xff'          # checksum=65535
               b'\x00\xff'          # ident=255
               b'\x00\x2a')         # seqnum=42

    def recv():
        yield headers + msg.encode(encoding)
        raise SystemExit

    socket.return_value.recv.side_effect = recv()

    assert log_pings.main(['--host', host,
                           '--setuid', 'nonuser',
                           '--chroot', '.',
                           '--no-hardening',
                           '--verbose']) is None

    out, err = capsys.readouterr()
    assert f'127.0.0.2:15 255 42 {msg}' in out
    assert not err

    s = mocker.call(_socket.AF_INET, _socket.SOCK_RAW, _socket.IPPROTO_ICMP)

    assert socket.mock_calls == [s,
                                 s.bind((host, _socket.IPPROTO_ICMP)),
                                 s.recv(1472),
                                 s.recv(1472),
                                 s.close()]
