import importlib
import re
import socket as _socket
import sys

import pytest

log_pings = importlib.import_module('log-pings')

MSG = 'abcdefghijklmnopqrstuvwabcdefghi'


if sys.version_info < (3, 8):
    def f_hex(b):
        result = b.hex()
        return re.sub(r'(\w\w)(?=.)', r'\1 ', result)

else:
    import operator
    f_hex = operator.methodcaller('hex', ' ')


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

    assert f_hex(ip.to_bytes()) == ('45 00 '
                                    '00 3c '
                                    '00 0f '
                                    '00 00 '
                                    '2a 01 '
                                    '92 af '
                                    '7f 00 00 02 '
                                    '7f 00 00 01')

    ip.validate_checksum()

    return ip


@pytest.fixture
def icmp_packet(encoding='utf-8'):
    msg = MSG.encode(encoding)

    icmp = log_pings.ICMPPacket(type=8, code=0,
                                checksum=0x4c33,
                                ident=255,
                                seq_num=42,
                                payload=msg)

    assert f_hex(icmp.to_bytes()) == ('08 00 '
                                      '4c 33 '
                                      '00 ff '
                                      '00 2a '
                                      + f_hex(msg))

    icmp.validate_checksum()

    return icmp


@pytest.mark.usefixtures('mock_pwd_grp')
def test_log_pings(capsys, mocker, ip_header, icmp_packet, host='127.0.0.1'):
    packets = iter([
        ip_header.to_bytes() + icmp_packet.to_bytes(),
        ip_header.to_bytes() + icmp_packet.replace(payload=b'abcde', checksum=0xcd0f).to_bytes(),
        ip_header.replace(hdr_checksum=0xdead).to_bytes() + icmp_packet.to_bytes(),
    ])

    def recv_into(buf):
        try:
            p = next(packets)
        except StopIteration:
            raise SystemExit
        assert len(p) <= len(buf)
        buf[:len(p)] = p
        return len(p)

    socket = mocker.patch('socket.socket', autospec=True)
    socket.return_value.recv_into.side_effect = recv_into

    bufsize = 128

    assert log_pings.main(['--host', host,
                           '--ipfmt', (' %(src)s:%(ident)s'
                                       ' [%(hdr_checksum)x]'
                                       ' %(flags.df)s'),
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

    if sys.version_info < (3, 7):
        pytest.skip('FIXME: test broken on 3.6')

    expected = ["... listening on '127.0.0.1'",
                '... serve_forever(...)',
                '... 60 = s.recv_into(<buffer>)',
                '... IPHeader(version=4, ihl=5, tos=0, length=60, ident=15,'
                ' flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=37551,'
                ' src_addr=2130706434, dst_addr=2130706433)',
                '... ICMPPacket(type=8, code=0, checksum=19507, ident=255,'
                ' seq_num=42)',
                '... <Timeval 2023-05-16 11:30:00.606885 [32]>',
                f'... 127.0.0.2:15 [92af] False <255:42> {MSG}',
                '... 33 = s.recv_into(<buffer>)',
                '... IPHeader(version=4, ihl=5, tos=0, length=60, ident=15,'
                ' flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=37551,'
                ' src_addr=2130706434, dst_addr=2130706433)',
                '... ICMPPacket(type=8, code=0, checksum=52495, ident=255,'
                ' seq_num=42)',
                '... 127.0.0.2:15 [92af] False <255:42> abcde',
                '... 60 = s.recv_into(<buffer>)',
                '... IPHeader(version=4, ihl=5, tos=0, length=60, ident=15,'
                ' flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=57005,'
                ' src_addr=2130706434, dst_addr=2130706433)',
                '... ICMPPacket(type=8, code=0, checksum=19507, ident=255,'
                ' seq_num=42)',
                "... InvalidChecksumError('0xdead (expected: 0x92af)'):"
                ' IPHeader(version=4, ihl=5, tos=0, length=60, ident=15,'
                ' flags_fragoffset=0, ttl=42, proto=1, hdr_checksum=57005,'
                ' src_addr=2130706434, dst_addr=2130706433)',
                '... SystemExit() exiting',
                '... socket.close()']

    for l, e in zip(lines, expected):
        pattern = re.escape(e).replace(r'\.\.\.', r'.*')
        assert re.fullmatch(pattern, l)

    s = mocker.call(_socket.AF_INET, _socket.SOCK_RAW, _socket.IPPROTO_ICMP)

    socket.assert_has_calls([s,
                             s.bind((host, _socket.IPPROTO_ICMP)),
                             s.recv_into(mocker.ANY),
                             s.recv_into(mocker.ANY),
                             s.recv_into(mocker.ANY),
                             s.recv_into(mocker.ANY),
                             s.close()])
