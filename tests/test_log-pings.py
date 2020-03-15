import importlib
import re
import socket as _socket

import pytest

log_pings = importlib.import_module('log-pings')

MSG = 'abcdefghijklmnopqrstuvwabcdefghi'


@pytest.fixture
def ip_header():
    ip = log_pings.IPHeader(version=4, ihl=5, tos=0,
                            length=60,
                            ident=15,
                            flags_fragoffset=0,
                            ttl=42, proto=1,
                            hdr_checksum=0x92af,
                            src='127.0.0.2',
                            dst='127.0.0.1')

    assert ip.to_bytes() == (b'\x45\x00'
                             b'\x00\x3c'
                             b'\x00\x0f'
                             b'\x00\x00'
                             b'\x2a\x01'
                             b'\x92\xaf'
                             b'\x7f\x00\x00\x02'
                             b'\x7f\x00\x00\x01')

    return ip


@pytest.fixture
def icmp_packet(encoding='utf-8'):
    msg = MSG.encode(encoding)

    icmp = log_pings.ICMPPacket(type=8, code=0,
                                checksum=0x4c33,
                                ident=255,
                                seq_num=42,
                                payload=msg)

    assert icmp.to_bytes() == (b'\x08\x00'
                               b'\x4c\x33'
                               b'\x00\xff'
                               b'\x00\x2a'
                               + msg)

    return icmp


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_pings(capsys, mocker, ip_header, icmp_packet, host='127.0.0.1'):
    socket = mocker.patch('socket.socket', autospec=True)

    packets = iter([
        ip_header.to_bytes() + icmp_packet.to_bytes(),
        ip_header.to_bytes() + icmp_packet.replace(payload=b'abcde', checksum=0xcd0f).to_bytes(),
        ip_header.replace(hdr_checksum=0).to_bytes() + icmp_packet.to_bytes(),
    ])

    def recv_into(buf):
        try:
            p = next(packets)
        except StopIteration:
            raise SystemExit
        assert len(p) <= len(buf)
        buf[:len(p)] = p
        return len(p)

    socket.return_value.recv_into.side_effect = recv_into

    bufsize = 128

    assert log_pings.main(['--host', host,
                           '--ipfmt', ' %(src)s:%(ident)s [%(hdr_checksum)x] %(flags.df)s',
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
                '... serve_forever(...)',
                '... IPHeader(version=4, ihl=5, tos=0, length=60, ident=15, flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=37551, src_addr=2130706434, dst_addr=2130706433)',
                f'... 127.0.0.2:15 [92af] False <255:42> {MSG}',
                '... IPHeader(version=4, ihl=5, tos=0, length=60, ident=15, flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=37551, src_addr=2130706434, dst_addr=2130706433)',
                '... 127.0.0.2:15 [92af] False <255:42> abcde',
                '... InvalidChecksumError: 0x92af',
                '... SystemExit() exiting',
                '... socket.close()']

    for l, e in zip(lines, expected):
        pattern = re.escape(e).replace(r'\.\.\.', r'.*')
        assert re.fullmatch(pattern, l)

    s = mocker.call(_socket.AF_INET, _socket.SOCK_RAW, _socket.IPPROTO_ICMP)

    assert socket.mock_calls == [s,
                                 s.bind((host, _socket.IPPROTO_ICMP)),
                                 s.recv_into(mocker.ANY),
                                 s.recv_into(mocker.ANY),
                                 s.recv_into(mocker.ANY),
                                 s.recv_into(mocker.ANY),
                                 s.close()]
