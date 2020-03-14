#!/usr/bin/env python3

"""Log incoming ICMP echo request messages to stdout and optionally into file."""

__title__ = 'log-pings.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import codecs
import collections
import logging
import os
import pathlib
import signal
import socket
import struct
import sys
import time

HOST = '0.0.0.0'

FORMAT = '%(asctime)s%(ip)s%(icmp)s %(message)s'

DATEFMT = '%b %d %H:%M:%S'

IP_INFO = ' %(src_addr)s:%(ident)d'

ICMP_INFO = ' %(ident)d %(seq_num)d'

EX = {'ip': '', 'icmp': ''}

CHROOT = '/tmp'

SETUID = 'nobody'

ENCODING = 'utf-8'

BUFSIZE = 2**16

TIMEZONE = pathlib.Path('/etc/timezone')

IP_FIELDS = {'version_ihl': 'B', 'tos': 'B',
             'length': 'H',
             'ident': 'H',
             'flags_fragoffset': 'H',
             'ttl': 'B', 'proto': 'B',
             'hdr_checksum': 'H',
             'src_addr': '4s', 'dst_addr': '4s'}

ICMP_FIELDS = {'type': 'B', 'code': 'B',
               'checksum': 'H',
               'ident': 'H',
               'seq_num': 'H',
               'payload': None}


def datefmt(s):
    try:
        time.strftime(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f'invalid datefmt: {s}')
    else:
        return s


def user(s):
    import pwd

    try:
        return pwd.getpwnam(s)
    except KeyError:
        raise argparse.ArgumentTypeError(f'unknown user: {s}')


def directory(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_dir():
        raise argparse.ArgumentTypeError(f'not a present directory: {s}')
    return result


def encoding(s):
    try:
        return codecs.lookup(s).name
    except LookupError:
        raise argparse.ArgumentTypeError(f'unknown encoding: {s}')


def positive_int(s):
    try:
        result = int(s)
    except ValueError:
        result = None

    if result is None or not result > 0:
        raise argparse.ArgumentTypeError(f'need positive int: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--host', metavar='IP', default=HOST,
                    help=f'address to listen on (default: {HOST})')

parser.add_argument('--file', metavar='LOGFILE', type=pathlib.Path,
                    help='file to write log to (log only to stdout by default)')

parser.add_argument('--format', metavar='TMPL', default=FORMAT,
                    help=f'log format (default: {FORMAT.replace("%", "%%")})')

parser.add_argument('--datefmt', metavar='TMPL', type=datefmt, default=DATEFMT,
                    help='log time.strftime() format'
                         f' (default: {DATEFMT.replace("%", "%%")})')

parser.add_argument('--ipfmt', metavar='TMPL', default=IP_INFO,
                    help=f'log format (default: {IP_INFO.replace("%", "%%")})')

parser.add_argument('--icmpfmt', metavar='TMPL', default=ICMP_INFO,
                    help=f'log format (default: {ICMP_INFO.replace("%", "%%")})')

parser.add_argument('--setuid', metavar='USER', type=user, default=SETUID,
                    help='user to setuid to after binding'
                         f' (default: {SETUID})')

parser.add_argument('--chroot', metavar='DIR', type=directory, default=CHROOT,
                    help='directory to chroot into after binding'
                         f' (default: {CHROOT})')

parser.add_argument('--no-hardening', dest='hardening', action='store_false',
                    help="don't give up privileges (ignore --setuid and --chroot)")

parser.add_argument('--encoding', metavar='NAME', type=encoding, default=ENCODING,
                    help='try to decode data with this encoding'
                         f' (default: {ENCODING})')

parser.add_argument('--max-size', metavar='N', dest='bufsize',
                    type=positive_int, default=BUFSIZE,
                    help='byte limit for packages to accept'
                         f' (default: {BUFSIZE})')

parser.add_argument('--verbose', action='store_true',
                    help='increase stdout logging level to DEBUG')

parser.add_argument('--version', action='version', version=__version__)


def register_signal_handler(*signums):
    assert signums

    def decorator(func):
        for s in signums:
            signal.signal(s, func)
        return func

    return decorator


def configure_logging(filename=None, *, level, file_level, format_, datefmt):
    import logging.config

    cfg = {'version': 1,
           'root': {'handlers': ['stdout'], 'level': level},
           'handlers': {'stdout': {'formatter': 'plain',
                                   'stream': 'ext://sys.stdout',
                                   'class': 'logging.StreamHandler'}},
           'formatters': {'plain': {'format': format_,
                                    'datefmt': datefmt}}}

    if filename is not None:
        cfg['root']['handlers'].append('file')
        cfg['handlers']['file'] = {'formatter': 'plain',
                                   'level': file_level,
                                   'filename': filename,
                                   'class': 'logging.FileHandler'}

    return logging.config.dictConfig(cfg)


def verify_checksum(b, *, format=None):
    if format is None:
        n_ints, is_odd = divmod(len(b), 2)
        if is_odd:
            b = bytes(b) + b'\x00'
            n_ints += 1
        format = f'!{n_ints}H'

    ints = struct.unpack(format, b)
    result = rfc1071_checksum(ints)
    if result:
        raise InvalidChecksumError(f'0x{result:04x}')
    return result


def rfc1071_checksum(ints):
    val = sum(ints)
    while val >> 16:
        val = (val & 0xffff) + (val >> 16)
    return ~val & 0xffff


class InvalidChecksumError(ValueError):
    pass


class IPHeader(collections.namedtuple('_IPHeader', list(IP_FIELDS))):

    __slots__ = ()

    _header_format = '!' + ''.join(t for t in IP_FIELDS.values())

    _header_size = struct.calcsize(_header_format)

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b, format='!10H')
        fields = struct.unpack(cls._header_format, b)
        src_addr, dst_addr = map(socket.inet_ntoa, fields[-2:])
        return cls._make(fields[:-2] + (src_addr, dst_addr))

    def to_bytes(self):
        fields = self[:-2] + tuple(map(socket.inet_aton, self[-2:]))
        return struct.pack(self._header_format, *fields)


class ICMPPacket(collections.namedtuple('_ICMPPacket', list(ICMP_FIELDS))):

    __slots__ = ()

    _header_format = '!' + ''.join(t for t in ICMP_FIELDS.values() if t)

    _header_size = struct.calcsize(_header_format)

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b)
        header = struct.unpack(cls._header_format, b[:cls._header_size])
        payload = bytes(b[cls._header_size:])
        return cls._make(header + (payload,))

    def to_bytes(self):
        header = struct.pack(self._header_format, *self[:-1])
        return header + self.payload

    def is_ping(self, ICMP_ECHO=8, ICMP_NO_CODE=0):
        return self.type == ICMP_ECHO and self.code == ICMP_NO_CODE


def serve_forever(s, *, bufsize, encoding, ip_tmpl, icmp_tmpl):
    buf = bytearray(bufsize)
    view = memoryview(buf)

    while True:
        n_bytes = s.recv_into(buf)

        try:
            ip = IPHeader.from_bytes(view[:20])
            icmp = ICMPPacket.from_bytes(view[20:n_bytes])
        except InvalidChecksumError as e:
            logging.debug('%s: %s', e.__class__.__name__, e, extra=EX)
            continue

        if icmp.is_ping():
            try:
                message = icmp.payload.decode(encoding)
            except UnicodeDecodeError:
                message = ascii(icmp.payload)

            logging.info(message, extra={'ip': ip_tmpl % ip._asdict(),
                                         'icmp': icmp_tmpl % icmp._asdict()})


def main(args=None):
    args = parser.parse_args(args)

    @register_signal_handler(signal.SIGINT, signal.SIGTERM)
    def handle_with_exit(signum, _):
        sys.exit(f'received signal.{signal.Signals(signum).name}')

    configure_logging(args.file,
                      level='DEBUG' if args.verbose else 'INFO',
                      file_level='INFO',
                      format_=args.format, datefmt=args.datefmt)

    cmd = pathlib.Path(sys.argv[0]).name
    logging.info(f'{cmd} listening on %r', args.host, extra=EX)

    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    s.bind((args.host, socket.IPPROTO_ICMP))

    if args.hardening:
        logging.debug('os.chroot(%r)', args.chroot, extra=EX)
        with TIMEZONE.open(encoding=ENCODING) as f:
            os.environ['TZ'] = f.readline().strip()
        time.tzset()
        os.chroot(args.chroot)

        logging.debug('os.setuid(%r)', args.setuid.pw_name, extra=EX)
        os.setgid(args.setuid.pw_gid)
        os.setgroups([])
        os.setuid(args.setuid.pw_uid)

    kwargs = {'ip_tmpl': args.ipfmt,
              'icmp_tmpl': args.icmpfmt,
              'encoding': args.encoding,
              'bufsize': args.bufsize}

    logging.debug('serve_forever(%r, **%r)', s, kwargs, extra=EX)

    try:
        serve_forever(s, **kwargs)
    except socket.error:
        logging.exception('socket.error', extra=EX)
        return 'socket error'
    except SystemExit as e:
        logging.info(f'{cmd} %r exiting', e, extra=EX)
    finally:
        logging.debug('socket.close()', extra=EX)
        s.close()

    return None


if __name__ == '__main__':
    sys.exit(main())
