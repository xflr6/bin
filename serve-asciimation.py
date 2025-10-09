#!/usr/bin/env python3

"""Run async server displaying asciimation via telnet."""

__title__ = 'serve-asciimation.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2017,2020 Sebastian Bank'

import asyncio
import argparse
import functools
import gzip
import logging
import operator
import os
import pathlib
import platform
import re
import shutil
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

CACHE = (pathlib.Path(__file__).parent / 'asciimation.html.gz').resolve()

FILM = re.compile(rb"var film = '(?P<film>.*)'\.split\('\\n'\);")

FRAME = re.compile(r'(\d+)\n' + r'(.*)\n' * 13)

FRAMES = None

HOME, CLS = '\x1b[H', '\x1b[J'

ENCODING = 'utf-8'


def port(s: str) -> int:
    port = int(s) if s.isdigit() else socket.getservbyname(s)

    if not 1 <= port <= 2**16:
        raise argparse.ArgumentTypeError(f'invalid port: {s}')
    return port


def fps(s: str) -> int:
    try:
        fps = int(s)
    except ValueError:
        fps = None

    if fps is None or not (1 <= fps <= 100):
        raise argparse.ArgumentTypeError(f'invalid fps: {s}')
    return fps


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


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--host', metavar='IP', default=HOST,
                    help=f'address to listen on (default: {HOST})')

parser.add_argument('--port', metavar='SERVICE', type=port, default=PORT,
                    help='TCP port number or name to listen on'
                         f' (default: {PORT})')

parser.add_argument('--fps', metavar='N', type=fps, default=FPS,
                    help=f'frames (1-100) per second to generate (default: {FPS})')

parser.add_argument('--setuid', metavar='USER', type=user, default=SETUID,
                    help='user to setuid to after binding'
                         f' (default: {SETUID})')

parser.add_argument('--chroot', metavar='DIR', type=directory, default=CHROOT,
                    help='directory to chroot into after binding'
                         f' (default: {CHROOT})')

parser.add_argument('--no-hardening', dest='hardening', action='store_false',
                    help="don't give up privileges (ignore --setuid and --chroot)")

parser.add_argument('--verbose', action='store_true',
                    help='increase stdout logging level to DEBUG')

parser.add_argument('--version', action='version', version=__version__)


def read_page_bytes(url: str = URL, *,
                    cache_path: pathlib.Path = CACHE) -> bytes:
    if not cache_path.exists():
        logging.info('download %r into %r', url, cache_path)
        with urllib.request.urlopen(url) as src,\
             gzip.open(cache_path, 'wb') as dst:
            shutil.copyfileobj(src, dst)

    logging.debug('read %r', cache_path)
    with gzip.open(cache_path, 'rb') as f:
        result = f.read()
    return result


def extract_film(page_bytes, *, encoding: str = 'unicode_escape'):
    raw = FILM.search(page_bytes).group('film')
    if raw.endswith(b'\\n\xff\\n'):
        raw = raw[:-3]
    return raw.decode(encoding)


def generate_frames(film, *, screen_size=(80, 24), frame_size=(67, 13)):
    duration = operator.methodcaller('group', 1)
    lines = operator.methodcaller('group', *range(2, 15))
    centerframe = get_centerframe_func(screen_size=screen_size,
                                       frame_size=frame_size)
    pos = 0
    for ma in FRAME.finditer(film):
        assert ma.start() == pos
        yield int(duration(ma)), centerframe(lines(ma))
        pos = ma.end()
    assert pos == len(film)


def get_centerframe_func(*, screen_size, frame_size):
    hmargin, vmargin = (s - f for s, f in zip(screen_size, frame_size))
    screen = '\r\n' * (vmargin // 2) + '%s' + '\r\n' * (vmargin - vmargin // 2)
    content = '%%-%ds' % frame_size[0]
    row = ' ' * (hmargin // 2) + content + ' ' * (hmargin - hmargin // 2)
    screen = f'{HOME}{CLS}{screen}'

    def centerframe_func(lines):
        return screen % '\r\n'.join(row % l for l in lines)

    return centerframe_func


def iterframes():
    global FRAMES

    if FRAMES is None:
        logging.debug('load FRAMES')
        page = read_page_bytes()
        film = extract_film(page)
        FRAMES = list(generate_frames(film))

    return iter(FRAMES)


def register_signal_handler(*signums):
    assert signums

    def decorator(func):
        for s in signums:
            logging.debug('signal.signal(%s, ...)', s)
            signal.signal(s, func)
        return func

    return decorator


async def serve_forever(*, sock, fps):
    handler = functools.partial(handle_connect, sleep_delay=1.0 / fps)

    logging.debug('asyncio.start_server(..., sock=%r)', sock)
    server = await asyncio.start_server(handler, sock=sock, start_serving=False)

    async with server:
        logging.debug('%r.serve_forever()', server)
        await server.serve_forever()


async def handle_connect(reader, writer, *, sleep_delay,
                         encoding: str = ENCODING):
    address = writer.get_extra_info('peername')
    logging.info('client connected from %s port %s', *address)

    try:
        for duration, frame in iterframes():
            writer.write(frame.encode(encoding))
            await writer.drain()
            await asyncio.sleep(sleep_delay * duration)
        logging.info('last frame for %s port %s', *address)
    except ConnectionResetError:
        logging.info('client from %s port %s disconnected', *address)
        writer.close()
        return
    except (SystemExit, Exception):
        logging.info('disconnect client from %s port %s', *address)
        writer.close()
        await writer.wait_closed()
        raise


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    if args.hardening:
        if platform.system() == 'Windows':  # pragma: no cover
            raise NotImplementedError('require --no-hardening under Windows')
        if args.setuid is None or isinstance(args.setuid, str):
            parser.error(f'unknown --setuid user: {args.setuid}')
        if (args.chroot is None or isinstance(args.chroot, str)
            or not args.chroot.is_dir()):
            parser.error(f'not a present --chroot directory: {args.chroot}')

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(message)s',
                        datefmt='%b %d %H:%M:%S')

    logging.info('start asciimation server on %s port %s', args.host, args.port)

    @register_signal_handler(signal.SIGINT, signal.SIGTERM)
    def handle_with_exit(signum, _):
        sys.exit(f'received signal.{signal.Signals(signum).name}')

    next(iterframes())  # pre-load FRAMES

    logging.debug('socket.create_server(%r)', (args.host, args.port))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.host, args.port))
    logging.debug('%r', s)

    if args.hardening:
        with pathlib.Path('/etc/timezone').open(encoding='utf-8') as f:
            tz = f.readline().strip()
        logging.debug('TZ=%r; time.tzset()', tz)
        os.environ['TZ'] = tz
        time.tzset()

        logging.debug('os.chroot(%r)', args.chroot)
        os.chroot(args.chroot)

        logging.debug('os.setuid(%r)', args.setuid)
        os.setgid(args.setuid.pw_gid)
        os.setgroups([])
        os.setuid(args.setuid.pw_uid)

    logging.debug('asyncio.run(serve_forever(sock=%r))', s)
    try:
        asyncio.run(serve_forever(sock=s, fps=args.fps))
    except socket.error:  # pragma: no cover
        logging.exception('socket.error')
        return 'socket error'
    except SystemExit as e:
        logging.info('%r exiting', e)
    finally:
        try:
            s.shutdown(socket.SHUT_WR)
        except (socket.error, OSError):
            pass
        s.close()
        logging.info('asciimation server stopped')

    return None


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
