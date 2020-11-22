#!/usr/bin/env python3

"""Download podcast episodes from subscriptions in config file sections."""

__title__ = 'download-podcasts.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import codecs
import configparser
import pathlib
import re
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as etree

CONFIG_FILE = pathlib.Path('podcasts.ini')

ENCODING = 'utf-8'

_UNSET = object()


def present_file(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return result


def encoding(s):
    try:
        return codecs.lookup(s).name
    except LookupError:
        raise argparse.ArgumentTypeError(f'unknown encoding: {s}')


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('--config', metavar='PATH',
                    type=present_file, default=str(CONFIG_FILE),
                    help='INI file with one section per podcast subscription,'
                         ' result paths relative to its directory'
                         f' (default: {CONFIG_FILE})')

parser.add_argument('--encoding', metavar='NAME',
                    type=encoding, default=ENCODING,
                    help=f'config file encoding (default: {ENCODING})')

parser.add_argument('--verbose', action='store_true',
                    help='log skipping of downloads that match present files')


def itersections(config_path=CONFIG_FILE, *, encoding):
    cfg = configparser.ConfigParser()
    with config_path.open(encoding=encoding) as f:
        cfg.read_file(f)

    for s, section in cfg.items():
        if s == 'DEFAULT' or section.getboolean('skip'):
            continue

        section = dict(section)
        del section['skip']

        section['directory'] = (config_path.parent
                                / section.pop('base_directory')
                                / section.pop('directory', s))

        section['number'] = int(section.pop('number'))

        yield section


def parse_rss(url, *, require_root_tag='rss', verbose=True):
    if verbose:
        print(url)

    with urllib.request.urlopen(url) as f:
        tree = etree.parse(f)

    if require_root_tag is not None:
        root_tag = tree.getroot().tag
        if root_tag != require_root_tag:
            raise RuntimeError(f'bad xml root tag {root_tag!r}'
                               f' (required: {require_root_tag!r})')

    return tree


class Podcast(list):

    _ns = {'atom': 'http://www.w3.org/2005/Atom'}

    ignore_size = staticmethod(lambda filename: False)

    ignore_file = staticmethod(lambda filename: False)

    def __init__(self, url, *, directory, number=2, ignore_size=r'', ignore_file=r''):
        if ignore_size:
            ignore_size = re.compile(ignore_size).search
        if ignore_file:
            ignore_file = re.compile(ignore_file).search

        tree = parse_rss(url)
        channel = tree.find('channel')
        title = channel.findtext('title')

        episodes = [Episode(i) for i in channel.iterfind('item')]

        while number is None or len(episodes) < number:
            try:
                url = channel.find('atom:link[@rel="next"]', self._ns).attrib['href']
            except AttributeError:
                break
            channel = parse_rss(url).find('channel')
            episodes += [Episode(i) for i in channel.iterfind('item')]

        self.title = title
        self.url = url
        self.directory = directory
        self.number = number
        if ignore_size:
            self.ignore_size = ignore_size
        if ignore_file:
            self.ignore_file = ignore_file
        super().__init__(episodes)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.title!r}, url={self.url!r}>'

    def iterepisodes(self, *, number=_UNSET):
        if number is _UNSET:
            number = self.number
        return iter(self[:number] if number is not None else self)

    def downloads(self, *, makedirs=False, number=_UNSET):
        if makedirs:
            self.directory.mkdir(parents=True, exist_ok=True)
        return [(e, self.directory / e.filename) for e in self.iterepisodes(number=number)]


class Episode:

    _ns = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}

    def __init__(self, item):
        self.title = item.findtext('title')
        self.description = item.findtext('description', '')
        self.duration = item.findtext('itunes:duration', None, self._ns)

        enclosure = item.find('enclosure')

        self.mime_type = enclosure.attrib['type']
        length = enclosure.attrib.get('length')
        self.length = int(length) if length is not None else None
        self.url = enclosure.attrib['url']

        path = pathlib.Path(urllib.parse.urlparse(self.url).path)
        self.filename = path.name

    def __repr__(self):
        detail = self.duration or self.size
        return f'<{self.__class__.__name__} {self.title!r} ({detail})>'

    @property
    def size(self):
        return human_size(self.length)


def human_size(n_bytes):
    for x in ('bytes', 'KiB', 'MiB', 'GiB', 'TiB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {x}'
        else:
            n_bytes /= 1024


def download_podcast_episodes(podcast, *, verbose=True):
    for episode, path in podcast.downloads(makedirs=True):
        print('  %s' % episode)
        if podcast.ignore_file(episode.filename):
            print('    matches ignore_file pattern, ignored.')
            continue
        elif path.exists() and (podcast.ignore_size(episode.filename)
                                or episode.length is None
                                or episode.length == path.stat().st_size):
            if verbose:
                print('    already present, skipped.')
            continue

        print('    downloading...  0%', end='')
        start = time.monotonic()
        urlretrieve(episode.url, path)
        stop = time.monotonic()
        speed = path.stat().st_size / (stop - start)
        print(f', done. ({human_size(speed)}/sec)')

        yield episode


def urlretrieve(url, filename):
    pos = 0

    def progress_func(gotblocks, blocksize, totalsize):
        nonlocal pos

        newpos = gotblocks * blocksize * 100 // totalsize
        if newpos > pos:
            print(f'\b\b\b\b{newpos:3d}%',  end='', file=sys.stdout, flush=True)
            pos = newpos

    return urllib.request.urlretrieve(url, filename, progress_func)


def main(args=None):
    args = parser.parse_args(args)

    print(f'Config file: {args.config} ({args.config.stat().st_size} bytes)')
    sections = list(itersections(args.config, encoding=args.encoding))

    print(f'Download RSS feeds for {len(sections)} active subscriptions...')
    podcasts = [Podcast(**kwargs) for kwargs in sections]
    print(f'parsed {sum(map(len, podcasts))} episode descriptions.\n')

    downloaded = []
    for p in podcasts:
        print(p)
        episodes = download_podcast_episodes(p, verbose=args.verbose)
        downloaded.extend((p, e) for e in episodes)
        print()
    print()

    for p, e in downloaded:
        print(f'{p.title} -- {e.title}')

    input('Press any key to end...')

    return None


if __name__ == '__main__':
    parser.exit(main())
