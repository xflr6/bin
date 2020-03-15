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
import ctypes
import logging
import operator
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

IP_INFO = ' %(src)s:%(ident)d'

ICMP_INFO = ' %(ident)d %(seq_num)d'

EX = {'ip': '', 'icmp': ''}

CHROOT = '/tmp'

SETUID = 'nobody'

ENCODING = 'utf-8'

BUFSIZE = 2**16

TIMEZONE = pathlib.Path('/etc/timezone')


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


class NetworkStructure(ctypes.BigEndianStructure):

    __slots__ = ()

    def __repr__(self):
        kwargs = ', '.join(f'{f}={getattr(self, f)}' for f, *_ in self._fields_)
        return f'{self.__class__.__name__}({kwargs})'

    def format(self, template):
        return template % MappingProxy(self)

    def replace(self, **kwargs):
        inst = self.__class__.from_buffer_copy(self)
        for k, v in kwargs.items():
            setattr(inst, k, v)
        return inst

    def to_bytes(self):
        return bytes(self)


class MappingProxy:

    def __init__(self, delegate):
        self._delegate = delegate

    def __getitem__(self, key):
        get_attr = operator.attrgetter(key)
        try:
            return get_attr(self._delegate)
        except AttributeError:
            raise KeyError(key)


B8, H16, L32 = ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32


class IPFlags(collections.namedtuple('_IPFlags', ['res', 'df', 'mf'])):

    __slots__= ()

    @classmethod
    def from_int(cls, i):

        def iterbools(i, mask):
            while mask:
                yield bool(i & mask)
                mask >>= 1

        return cls._make(iterbools(i, 0b100))


class IPHeader(NetworkStructure):

    __slots__ = ()

    _fields_ = [('version', B8, 4), ('ihl', B8, 4), ('tos', B8),
                ('length', H16),
                ('ident', H16),
                ('flags_fragoffset', H16),
                ('ttl', B8), ('proto', B8),
                ('hdr_checksum', H16),
                ('src_addr', L32),
                ('dst_addr', L32)]

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b, format='!10H')
        return cls.from_buffer_copy(b)

    @property
    def flags(self):
        return IPFlags.from_int(self.flags_fragoffset >> 13)

    @property
    def fragoffset(self):
        return self.flags_fragoffset & 0b1111111111111

    @property
    def src(self):
        return socket.inet_ntoa(struct.pack('!L', self.src_addr))

    @property
    def dst(self):
        return socket.inet_ntoa(struct.pack('!L', self.dst_addr))

    @src.setter
    def src(self, s):
        self.src_addr, = struct.unpack('!L', socket.inet_aton(s))

    @dst.setter
    def dst(self, s):
        self.dst_addr, = struct.unpack('!L', socket.inet_aton(s))


class ICMPPacket(NetworkStructure):

    __slots__ = ('payload',)

    _fields_ = [('type', B8), ('code', B8),
                ('checksum', H16),
                ('ident', H16),
                ('seq_num', H16)]

    @classmethod
    def from_bytes(cls, b):
        verify_checksum(b)
        inst = cls.from_buffer_copy(b)
        inst.payload = bytes(b[8:])
        return inst

    def is_ping(self, ICMP_ECHO=8, ICMP_NO_CODE=0):
        return self.type == ICMP_ECHO and self.code == ICMP_NO_CODE

    def to_bytes(self):
        return bytes(self) + self.payload


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

            logging.info(message, extra={'ip': ip.format(ip_tmpl),
                                         'icmp': icmp.format(icmp_tmpl)})


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
