#!/usr/bin/env python3

"""Log incoming UDP messages to stdout and optionally into file."""

__title__ = 'log-udp.py'
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
import platform
import signal
import socket
import sys
import time
from typing import Optional

HOST = '0.0.0.0'

PORT = 'discard'

FORMAT = '%(asctime)s %(message)s'

DATEFMT = '%b %d %H:%M:%S'

CHROOT = '/tmp'

SETUID = 'nobody'

ENCODING = 'utf-8'

TIMEZONE = pathlib.Path('/etc/timezone')


def port(s: str) -> int:
    port = int(s) if s.isdigit() else socket.getservbyname(s)

    if not 1 <= port <= 2**16:
        raise argparse.ArgumentTypeError(f'invalid port: {s}')
    return port


def datefmt(s: str) -> str:
    try:
        time.strftime(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f'invalid datefmt: {s}')
    else:
        return s


def user(s: str) -> str:
    try:
        import pwd
    except ImportError:
        return None

    try:
        return pwd.getpwnam(s)
    except KeyError:
        return s


def directory(s: str):
    try:
        return pathlib.Path(s)
    except ValueError:
        return s


def encoding(s: str) -> str:
    try:
        return codecs.lookup(s).name
    except LookupError:
        raise argparse.ArgumentTypeError(f'unknown encoding: {s}')


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--host', metavar='IP', default=HOST,
                    help=f'address to listen on (default: {HOST})')

parser.add_argument('--port', metavar='SERVICE', type=port, default=PORT,
                    help='UDP port number or name to listen on'
                         f' (default: {PORT})')

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

parser.add_argument('--encoding', metavar='NAME', type=encoding, default=ENCODING,
                    help=f'encoding of UDP messages (default: {ENCODING})')

parser.add_argument('--verbose', action='store_true',
                    help='increase stdout logging level to DEBUG')

parser.add_argument('--version', action='version', version=__version__)


def configure_logging(filename=None, *,
                      level, file_level, format_, datefmt):
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


def register_signal_handler(*signums):
    assert signums

    def decorator(func):
        for s in signums:
            signal.signal(s, func)
        return func

    return decorator


def itertail(iterable, *, n: int):
    if n is not None:
        iterable = collections.deque(iterable, n)
    return iterable


def serve_forever(s, *, encoding: str, bufsize: int = 1_024):
    buf = bytearray(bufsize)

    while True:
        n_bytes, (host, port) = s.recvfrom_into(buf)
        raw = buf[:n_bytes]

        logging.debug('%d, (%r, %d) = s.recvfrom_into(<buffer>)',
                      n_bytes, host, port)

        try:
            msg = raw.decode(encoding).strip()
        except UnicodeDecodeError as e:
            msg = ascii(bytes(raw))
            logging.debug('%s: %s', e.__class__.__name__, e)

        logging.info('%s:%d %s', host, port, msg)


def main(args=None) -> Optional[str]:
    args = parser.parse_args(args)
    if args.hardening:
        if platform.system() == 'Windows':  # pragma: no cover
            raise NotImplementedError('require --no-hardening under Windows')
        if args.setuid is None or isinstance(args.setuid, str):
            parser.error(f'unknown --setuid user: {args.setuid}')
        if (args.chroot is None or isinstance(args.chroot, str)
            or not args.chroot.is_dir()):
            parser.error(f'not a present --chroot directory: {args.chroot}')

    configure_logging(args.file,
                      level='DEBUG' if args.verbose else 'INFO',
                      file_level='INFO',
                      format_=args.format, datefmt=args.datefmt)

    @register_signal_handler(signal.SIGINT, signal.SIGTERM)
    def handle_with_exit(signum, _):
        sys.exit(f'received signal.{signal.Signals(signum).name}')

    if args.file is not None and args.file.stat().st_size:
        logging.debug('replay tail of lof file: %r', args.file)
        with args.file.open(encoding=ENCODING) as f:
            for line in itertail(f, n=40):
                print(line, end='')

    cmd = pathlib.Path(sys.argv[0]).name
    logging.info(f'{cmd} listening on %r port %d udp', args.host, args.port)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((args.host, args.port))

    if args.hardening:
        with TIMEZONE.open(encoding=ENCODING) as f:
            tz = f.readline().strip()
        logging.debug('TZ=%r; time.tzset()', tz)
        os.environ['TZ'] = tz
        time.tzset()

        logging.debug('os.chroot(%r)', args.chroot)
        os.chroot(args.chroot)

        logging.debug('os.setuid(%r)', args.setuid.pw_name)
        os.setgid(args.setuid.pw_gid)
        os.setgroups([])
        os.setuid(args.setuid.pw_uid)

    logging.debug('serve_forever(%r)', s)
    try:
        serve_forever(s, encoding=args.encoding)
    except socket.error:  # pragma: no cover
        logging.exception('socket.error')
        return 'socket error'
    except SystemExit as e:
        logging.info(f'{cmd} %r exiting', e)
    finally:
        logging.debug('socket.close()')
        s.close()

    return None


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
