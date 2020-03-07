#!/usr/bin/env python3

"""Log incoming UDP messages to stdout and optionally into file."""

__title__ = 'log-udp.py'
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
import sys
import time

HOST = '127.0.0.1'

PORT = 'discard'

FORMAT = '%(asctime)s %(message)s'

DATEFMT = '%b %d %H:%M:%S'

CHROOT = '/tmp'

SETUID = 'nobody'

ENCODING = 'utf-8'

TIMEZONE = pathlib.Path('/etc/timezone')


def port(s):
    port = int(s) if s.isdigit() else socket.getservbyname(s)

    if not 1 <= port <= 2**16:
        raise argparse.ArgumentTypeError(f'invalid port: {s}')
    return port


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

parser.add_argument('--no-hardening', action='store_true',
                    help="don't give up privileges (ignore --setuid and --chroot)")

parser.add_argument('--encoding', metavar='NAME', default=ENCODING,
                    help=f'encoding of UDP messages (default: {ENCODING})')

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


def itertail(iterable, *, n):
    if n is not None:
        iterable = collections.deque(iterable, n)
    return iterable


def serve_forever(s, *, encoding, bufsize=2**10):
    while True:
        raw, (host, port) = s.recvfrom(bufsize)

        try:
            msg = raw.decode(encoding).strip()
        except UnicodeDecodeError as e:
            msg = ascii(raw)
            logging.debug('%s: %s', e.__class__.__name__, e)

        logging.info('%s:%d %s', host, port, msg)


def main(args=None):
    args = parser.parse_args(args)

    @register_signal_handler(signal.SIGINT, signal.SIGTERM)
    def handle_with_exit(signum, _):
        sys.exit(f'received signal.{signal.Signals(signum).name}')

    configure_logging(args.file,
                      level='DEBUG' if args.verbose else 'INFO',
                      file_level='INFO',
                      format_=args.format, datefmt=args.datefmt)

    if args.file is not None and args.file.stat().st_size:
        logging.debug('replay tail of lof file: %r', args.file)
        with args.file.open(encoding=ENCODING) as f:
            for line in itertail(f, n=40):
                print(line, end='')

    cmd = pathlib.Path(sys.argv[0]).name
    logging.info(f'{cmd} listening on %r port %d udp', args.host, args.port)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.host, args.port))

    if not args.no_hardening:
        if args.chroot is not None:
            logging.debug('os.chroot(%r)', args.chroot)
            with TIMEZONE.open(encoding=ENCODING) as f:
                os.environ['TZ'] = f.readline().strip()
            time.tzset()
            os.chroot(args.chroot)

        if args.setuid is not None:
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
