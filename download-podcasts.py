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

_NS = {'atom': 'http://www.w3.org/2005/Atom',
       'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}


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

parser.add_argument('--limit', metavar='N', type=int, default=None,
                    help='number of episodes to download'
                         ' (overrides --config file)')

parser.add_argument('--verbose', action='store_true',
                    help='log skipping of downloads that match present files')


class ConfigParser(configparser.ConfigParser):

    DEFAULTSECT = configparser.DEFAULTSECT

    @classmethod
    def from_path(cls, path, *, encoding=ENCODING):
        inst = cls()
        with path.open(encoding=encoding) as f:
            inst.read_file(f)
        return inst


class Subscriptions:

    _skip = 'skip'

    _directory = 'directory'

    _limit = 'limit'

    def __init__(self, config_path=CONFIG_FILE, encoding=ENCODING):
        self._config_path = config_path
        self._config = ConfigParser.from_path(config_path)

    def __repr__(self):
        return (f'<{self.__class__.__name__} from {str(self._config_path)!r}:'
                f' active={len(self)}, inactive={self.count(active=False)}>')

    def _config_items(self, *, active):
        active = bool(active) if active is not None else active
        for name, section in self._config.items(): 
            if (name == self._config.DEFAULTSECT
                or active == section.getboolean(self._skip)):
                continue
            yield name, section

    def _podcast_kwargs(self, name, section):
        kwargs = dict(section)
        del kwargs[self._skip]

        kwargs[self._directory] = (self._config_path.parent
                                   / kwargs.pop('base_directory')
                                   / kwargs.pop(self._directory, name))

        kwargs[self._limit] = int(kwargs.pop(self._limit))

        return kwargs

    def count(self, *, active=True):
        return sum(1 for _ in self._config_items(active=active))

    __len__ = count

    def podcasts(self, *, active=True, raw=False):
        for name, section in self._config_items(active=active):
            kwargs = self._podcast_kwargs(name, section)
            yield Podcast.from_url(**kwargs) if not raw else kwargs

    __iter__ = podcasts


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


def get_channel_items(url, *, limit):
    if limit is None:
        limit = float('inf')
    elif limit < 1:
        raise ValueError(f'limit {limit!r} (required: 1 or higher)')

    items = []
    while limit is None or len(items) < limit:
        tree = parse_rss(url)
        channel = tree.find('channel')
        items.extend(channel.iterfind('item'))

        next_link = channel.find('atom:link[@rel="next"]', _NS)
        if next_link is None:
            break

        url = next_link.attrib['href']

    return channel, items


class Podcast(list):

    ignore_size = staticmethod(lambda filename: False)

    ignore_file = staticmethod(lambda filename: False)

    @classmethod
    def from_url(cls, url, *, directory, limit=2, ignore_size=r'', ignore_file=r''):
        channel, items = get_channel_items(url, limit=limit)
        return cls(url, channel, items, directory=directory, limit=limit,
                   ignore_size=ignore_size, ignore_file=ignore_file)

    def __init__(self, url, channel, items, *, directory, limit=2,
                 ignore_size=r'', ignore_file=r''):
        super().__init__((Episode(self, i) for i in items))

        self.title = channel.findtext('title')
        self.url = url
        self.directory = directory
        self.limit = limit
        if ignore_size:
            self.ignore_size = re.compile(ignore_size).search
        if ignore_file:
            self.ignore_file = re.compile(ignore_file).search

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.title!r}, url={self.url!r}>'

    def download_episodes(self, *, limit=_UNSET, makedirs=True, verbose=True):
        if limit is _UNSET:
            limit = self.limit

        if makedirs:
            self.directory.mkdir(parents=True, exist_ok=True)

        print(self)
        for e in self[:limit] if limit is not None else self:
            print(f'  {e}')
            skip = None
            if self.ignore_file(e.filename):
                skip = f'{e.filename} matches ignore_file, ignored.'
            elif e.path.exists():
                size = e.path.stat().st_size
                if self.ignore_size(e.filename):
                    skip = (f'{e.filename} matches ignore_size,'
                            f' assume present ({size:_d} bytes) is correct'
                            f' (expected: {e.length!r}) , skipped.')
                elif e.length is None:
                    skip = (f'unknown file size,'
                            f' assume present ({size:_d} bytes) is correct,'
                            f' skipped.')
                elif e.length == size:
                    skip = 'already present, skipped.'
                else:
                    print(f'    overwriting {e.path} ({size:_d} bytes).')

            if skip:
                if verbose:
                    print(f'    {skip}')
                continue

            e.download()
            yield e


class Episode:

    def __init__(self, podcast, item):
        self.podcast = podcast
        self.title = item.findtext('title')
        self.description = item.findtext('description', '')
        self.duration = item.findtext('itunes:duration', None, _NS)

        enclosure = item.find('enclosure')

        self.mime_type = enclosure.attrib['type']
        length = enclosure.attrib.get('length')
        self.length = int(length) if length is not None else None
        self.url = enclosure.attrib['url']

        path = pathlib.Path(urllib.parse.urlparse(self.url).path)
        self.filename = path.name

    def __repr__(self):
        detail = self.duration or human_size(self.length)
        return f'<{self.__class__.__name__} {self.title!r} ({detail})>'

    @property
    def path(self):
        return self.podcast.directory / self.filename

    def download(self):
        target = self.path
        
        print('    downloading...  0%', end='')
        start = time.monotonic()
        urlretrieve(self.url, target)
        stop = time.monotonic()
        speed = target.stat().st_size / (stop - start)
        print(f', done. ({human_size(speed)}/sec)')

        return target


def human_size(n_bytes):
    for x in ('bytes', 'KiB', 'MiB', 'GiB', 'TiB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {x}'
        else:
            n_bytes /= 1024


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

    print(f'Config: {args.config} ({args.config.stat().st_size:_d} bytes)')
    subscribed = Subscriptions(args.config, encoding=args.encoding)
    print(subscribed)

    print(f'Download RSS feed XML for {len(subscribed)} active subscriptions...')
    podcasts = list(subscribed.podcasts())
    print(f'parsed {sum(map(len, podcasts))} episode descriptions.\n')

    downloaded = []
    for p in podcasts:
        episodes = p.download_episodes(verbose=args.verbose)
        downloaded.extend((p, e) for e in episodes)
        print()
    print()

    for p, e in downloaded:
        print(f'{p.title} -- {e.title}')

    input('Press any key to end...')

    return None


if __name__ == '__main__':
    parser.exit(main())
