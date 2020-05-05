#!/usr/bin/env python3

"""Run server displaying asciimation via telnet."""

__title__ = 'serve-asciimation.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2017,2020 Sebastian Bank'

import argparse
import asyncore
import gzip
import logging
import os
import pathlib
import re
import signal
import socket
import sys
import time
import urllib.request

HOST = '127.0.0.1'

PORT = 'telnet'

FPS = 15

CHROOT = '/tmp'

SETUID = 'nobody'

URL = 'http://www.asciimation.co.nz'

CACHE = pathlib.Path(__file__).parent / 'asciimation.html.gz'

ENCODING = 'utf-8'


def port(s):
    port = int(s) if s.isdigit() else socket.getservbyname(s)

    if not 1 <= port <= 2**16:
        raise argparse.ArgumentTypeError(f'invalid port: {s}')
    return port


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--host', metavar='IP', default=HOST,
                    help=f'address to listen on (default: {HOST})')

parser.add_argument('--port', metavar='SERVICE', type=port, default=PORT,
                    help='UDP port number or name to listen on'
                         f' (default: {PORT})')

parser.add_argument('--fps', metavar='N', type=int, default=FPS,
                    help=f'frames per second to generate (default: {FPS})')

parser.add_argument('--setuid', metavar='USER', default=SETUID,
                    help='user to setuid to after binding'
                         f' (default: {SETUID})')

parser.add_argument('--chroot', metavar='DIR', default=CHROOT,
                    help='directory to chroot into after binding'
                         f' (default: {CHROOT})')

parser.add_argument('--no-hardening', dest='hardening', action='store_false',
                    help="don't give up privileges (ignore --setuid and --chroot)")

parser.add_argument('--verbose', action='store_true',
                    help='increase stdout logging level to DEBUG')

parser.add_argument('--version', action='version', version=__version__)


def read_page_bytes(url=URL, *, cache_path=CACHE):
    if not cache_path.exists():
        logging.info('download %r into %r', url, cache_path)
        with urllib.request.urlopen(url) as f:
            raw = f.read()
        with gzip.open(cache_path, 'wb') as f:
            f.write(raw)

    logging.info('read %r', cache_path)
    with gzip.open(cache_path, 'rb') as f:
        result = f.read()
    return result


def iterframes(page):
    film = re.search(rb"var film = '(.*)'\.split\('\\n'\);", page).group(1)
    film = film.decode('unicode_escape')

    duration = 1
    lines = range(2, 15)
    for ma in re.finditer(r'(\d+)\n' + 13 * r'(.*)\n', film):
        yield int(ma.group(duration)), centerframe(ma.group(*lines))


def apply(func):
    return func()


@apply
def centerframe(screen_size=(80, 24), frame_size=(67, 13)):
    hmargin, vmargin = (s - f for s, f in zip(screen_size, frame_size))
    screen = '\r\n' * (vmargin // 2) + '%s' + '\r\n' * (vmargin - vmargin // 2)
    content = '%%-%ds' % frame_size[0]
    row = ' ' * (hmargin // 2) + content + ' ' * (hmargin - hmargin // 2)
    screen = '\x1b[H' + '\x1b[J' + screen  # home cls

    def centerframe_func(lines):
        return screen % '\r\n'.join(row % l for l in lines)

    return centerframe_func


class Server(asyncore.dispatcher):

    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)

        if not isinstance(port, int):
            port = socket.getservbyname(port)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        logging.info('server listening on %s port %s', host, port)
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
        conn, address = self.accept()
        logging.info('accept %r from %r', conn, address)
        Handler(conn)

    def shutdown(self):
        asyncore.close_all()
        self.close()
        logging.info('server shut down')


class Handler(asyncore.dispatcher):

    _frames = None

    @classmethod
    def iterframes(cls):
        if cls._frames is None:
            page = read_page_bytes()
            frames = list(iterframes(page))
            cls._frames = frames
        return iter(cls._frames)

    def __init__(self, conn, encoding=ENCODING):
        asyncore.dispatcher.__init__(self, conn)
        self.encoding = encoding
        logging.info('client connect %s port %s', *self.addr)
        self.frames = self.iterframes()
        self.duration = 0

    def handle_read(self, bufsize=1024):
        self.recv(bufsize)

    def handle_write(self):
        if not self.duration:
            try:
                self.duration, frame = next(self.frames)
            except StopIteration:
                logging.info('close client %s port %s', *self.remote)
                self.close()
                return

            self.send(frame.encode(self.encoding))
        self.duration -= 1

    def handle_close(self):
        logging.info('client disconnect %s port %s', *self.addr)
        self.close()


def serve_forever(*, fps):
    interval = 1.0 / fps
    while True:
        asyncore.loop(interval, count=1)
        time.sleep(interval)


def chroot(*, username, directory, fix_time=True):
    try:
        import pwd
    except ImportError:
        return

    try:
        uid, gid = pwd.getpwnam(username)[2:4]
    except KeyError:
        raise ValueError(f'unknown user: {username}')

    try:
        path = pathlib.Path(directory)
    except ValueError:
        path = None

    if path is None or not path.is_dir():
        raise ValueError(f'not a present directory: {directory}')

    if fix_time:
        with pathlib.Path('/etc/timezone').open(encoding='utf-8') as f:
            tz = f.readline().strip()
        logging.debug('TZ=%r; time.tzset()', tz)
        os.environ['TZ'] = tz
        time.tzset()

    logging.debug('os.chroot(%r)', path)
    os.chroot(path)

    logging.debug('os.setuid(%r)', uid)
    os.setgid(gid)
    os.setgroups([])
    os.setuid(uid)


def register_signal_handler(*signums):
    assert signums

    def decorator(func):
        for s in signums:
            signal.signal(s, func)
        return func

    return decorator


def main(args=None):
    args = parser.parse_args(args)

    @register_signal_handler(signal.SIGINT, signal.SIGTERM)
    def handle_with_exit(signum, _):
        sys.exit(f'received signal.{signal.Signals(signum).name}')

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(message)s',
                        datefmt='%b %d %H:%M:%S')

    next(Handler.iterframes())  # pre-load frames

    s = Server(args.host, args.port)

    if args.hardening:
        chroot(username=args.setuid, directory=args.chroot)

    try:
        serve_forever(fps=args.fps)
    except socket.error:  # pragma: no cover
        logging.exception('socket.error')
        return 'socket error'
    except SystemExit as e:
        logging.info('%r exiting', e)
    finally:
        logging.debug('shutdown %r', s)
        s.shutdown()

    return None


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
