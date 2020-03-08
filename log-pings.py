#!/usr/bin/env python3

"""Log incoming ICMP echo request messages to stdout and optionally into file."""

__title__ = 'log-pings.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
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

FORMAT = '%(asctime)s %(message)s'

DATEFMT = '%b %d %H:%M:%S'

CHROOT = '/tmp'

SETUID = 'nobody'

ENCODING = 'utf-8'

TIMEZONE = pathlib.Path('/etc/timezone')

IP_FIELDS = ['version_ihl', 'tos', 'length', 'ident', 'flags_fragoffset',
             'ttl', 'proto', 'hdr_checksum', 'src_addr', 'dst_addr', 'payload']

ICMP_FIELDS = ['type', 'code', 'checksum', 'ident', 'seq_num', 'payload']


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


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--host', metavar='IP', default=HOST,
                    help=f'address to listen on (default: {HOST})')

parser.add_argument('--file', metavar='LOGFILE', type=pathlib.Path,
                    help='file to write log to (log only to stdout by default)')

parser.add_argument('--format', metavar='TMPL', default=FORMAT,
                    help='log format string'
                         f' (default: {FORMAT.replace("%", "%%")})')

parser.add_argument('--datefmt', metavar='TMPL', type=datefmt, default=DATEFMT,
                    help='log time.strftime() format string'
                         f' (default: {DATEFMT.replace("%", "%%")})')

parser.add_argument('--setuid', metavar='USER', type=user, default=SETUID,
                    help='user to setuid to after binding'
                         f' (default: {SETUID})')

parser.add_argument('--chroot', metavar='DIR', type=directory, default=CHROOT,
                    help='directory to chroot into after binding'
                         f' (default: {CHROOT})')

parser.add_argument('--no-hardening', dest='hardening', action='store_false',
                    help="don't give up privileges (ignore --setuid and --chroot)")

parser.add_argument('--encoding', metavar='NAME', default=ENCODING,
                    help=f'encoding of ping messages (default: {ENCODING})')

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


def rfc1071_checksum(ints):
    val = sum(ints)
    while val >> 16:
        val = (val & 0xffff) + (val >> 16)
    return ~val & 0xffff


def verify_checksum(b, *, format=None):
    if format is None:
        n_ints, is_odd = divmod(len(b), 2)
        if is_odd:
            b += b'\x00'
            n_ints += 1
        format = f'!{n_ints}H'

    ints = struct.unpack(format, b)
    result = rfc1071_checksum(ints)
    if result:
        raise InvalidChecksumError(f'0x{result:04x}')
    return result


class InvalidChecksumError(ValueError):
    pass


class IPPacket(collections.namedtuple('_IPPacket', IP_FIELDS)):

    __slots__ = ()

    _header = slice(None, 20)
    _int_fields = slice(None, 12)
    _src_addr = slice(12, 16)
    _dst_addr = slice(16, 20)
    _payload = slice(20, None)

    _int_fields_format = '!BBHHHBBH'

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b[cls._header], format='!10H')
        int_fields = struct.unpack(cls._int_fields_format, b[cls._int_fields])
        src_addr = socket.inet_ntoa(b[cls._src_addr])
        dst_addr = socket.inet_ntoa(b[cls._dst_addr])
        return cls._make(int_fields + (src_addr, dst_addr, b[cls._payload]))

    def to_bytes(self):
        int_fields = struct.pack(self._int_fields_format, *self[:-3])
        src_addr, dst_addr = map(socket.inet_aton, self[-3:-1])
        return b''.join([int_fields, src_addr, dst_addr, self.payload])


class ICMPPacket(collections.namedtuple('_ICMPPacket', ICMP_FIELDS)):

    __slots__ = ()

    _header = slice(None, 8)
    _payload = slice(8, None)

    _header_format = '!BBHHH'

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b)
        header = struct.unpack(cls._header_format, b[cls._header])
        return cls._make(header + ( b[cls._payload],))

    def to_bytes(self):
        header = struct.pack(self._header_format, *self[:-1])
        return header + self.payload

    def is_ping(self, ICMP_ECHO=8, ICMP_NO_CODE=0):
        return self.type == ICMP_ECHO and self.code == ICMP_NO_CODE


def serve_forever(s, *, encoding, bufsize=1472):
    while True:
        raw = s.recv(bufsize)

        try:
            ip = IPPacket.from_bytes(raw)
            icmp = ICMPPacket.from_bytes(ip.payload)
        except InvalidChecksumError as e:
            logging.debug('%s: %s', e.__class__.__name__, e)
            continue

        if icmp.is_ping():
            try:
                msg = icmp.payload.decode(encoding)
            except UnicodeDecodeError:
                msg = ascii(icmp.payload)

            logging.info('%s:%d %d %d %s', ip.src_addr, ip.ident,
                         icmp.ident, icmp.seq_num, msg)


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
    logging.info(f'{cmd} listening on %r', args.host)

    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    s.bind((args.host, socket.IPPROTO_ICMP))

    if args.hardening:
        logging.debug('os.chroot(%r)', args.chroot)
        with TIMEZONE.open(encoding=ENCODING) as f:
            os.environ['TZ'] = f.readline().strip()
        time.tzset()
        os.chroot(args.chroot)

        logging.debug('os.setuid(%r)', args.setuid.pw_name)
        os.setgid(args.setuid.pw_gid)
        os.setgroups([])
        os.setuid(args.setuid.pw_uid)

    logging.debug('serve_forever(%r)', s)

    try:
        serve_forever(s, encoding=args.encoding)
    except socket.error:
        logging.exception('socket.error')
        return 'socket error'
    except SystemExit as e:
        logging.info(f'{cmd} %r exiting', e)
    finally:
        logging.debug('socket.close()')
        s.close()

    return None


if __name__ == '__main__':
    sys.exit(main())
