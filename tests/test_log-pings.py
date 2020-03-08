import importlib
import re
import socket as _socket

import pytest

log_pings = importlib.import_module('log-pings')

IP_HEADER = {'version_ihl': 0x45, 'tos': 0,
             'length': 60,
             'ident': 15,
             'flags_fragoffset': 0,
             'ttl': 42, 'proto': 1,
             'hdr_checksum': 0x92af,
             'src_addr': '127.0.0.2',
             'dst_addr': '127.0.0.1'}

ICMP_HEADER = {'type': 8, 'code': 0,
               'checksum': 0x4c33,
               'ident': 255,
               'seq_num': 42}

MSG = 'abcdefghijklmnopqrstuvwabcdefghi'


@pytest.fixture
def packet(msg=MSG, encoding='utf-8'):
    msg = msg.encode(encoding)

    icmp = log_pings.ICMPPacket(payload=msg, **ICMP_HEADER)
    ip = log_pings.IPPacket(payload=icmp.to_bytes(), **IP_HEADER)

    assert ip.to_bytes() == (# IP_HEADER
                             b'\x45\x00'  # version=4 ihl=5 tos=0
                             b'\x00\x3c'  # length=60
                             b'\x00\x0f'  # ident=15
                             b'\x00\x00'  # flags=0 fragoffset=0
                             b'\x2a\x01'  # ttl=42 proto=1
                             b'\x92\xaf'  # hdr_checksum=37551
                             b'\x7f\x00\x00\x02'  # scr_addr='127.0.0.2'
                             b'\x7f\x00\x00\x01'  # dst_addr='127.0.0.1'
                             # ICMP_HEADER
                             b'\x08\x00'  # type=8 code=0
                             b'\x4c\x33'  # checksum=19507
                             b'\x00\xff'  # ident=255
                             b'\x00\x2a'  # seq_num=42
                             + msg)

    return ip


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_pings(capsys, mocker, packet, host='127.0.0.1'):
    socket = mocker.patch('socket.socket', autospec=True)

    def recv():
        yield packet.to_bytes()
        icmp = log_pings.ICMPPacket.from_bytes(packet.payload)
        icmp = icmp._replace(payload=b'abcde', checksum=0xcd0f)
        yield packet._replace(payload=icmp.to_bytes()).to_bytes()
        yield packet._replace(hdr_checksum=0).to_bytes()
        raise SystemExit

    socket.return_value.recv.side_effect = recv()

    bufsize = 4242

    assert log_pings.main(['--host', host,
                           '--ipfmt', ' %(src_addr)s:%(ident)s [%(hdr_checksum)x]',
                           '--icmpfmt', ' <%(ident)d:%(seq_num)d>',
                           '--setuid', 'nonuser',
                           '--chroot', '.',
                           '--no-hardening',
                           '--encoding', 'ascii',
                           '--max-size', str(bufsize),
                           '--verbose']) is None

    out, err = capsys.readouterr()
    assert not err
    lines = out.splitlines()

    expected = ["... listening on '127.0.0.1'",
                "... serve_forever(...)",
                f'... 127.0.0.2:15 [92af] <255:42> {MSG}',
                '... 127.0.0.2:15 [92af] <255:42> abcde',
                '... InvalidChecksumError: 0x92af',
                '... SystemExit() exiting',
                '... socket.close()']

    for l, e in zip(lines, expected):
        pattern = re.escape(e).replace(r'\.\.\.', r'.*')
        assert re.fullmatch(pattern, l)

    s = mocker.call(_socket.AF_INET, _socket.SOCK_RAW, _socket.IPPROTO_ICMP)

    assert socket.mock_calls == [s,
                                 s.bind((host, _socket.IPPROTO_ICMP)),
                                 s.recv(bufsize),
                                 s.recv(bufsize),
                                 s.recv(bufsize),
                                 s.recv(bufsize),
                                 s.close()]
