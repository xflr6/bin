#!/usr/bin/env python3

"""Count page tags in MediaWiki XML export."""

__title__ = 'count-wiki.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import bz2
import functools
import pathlib
import re
import sys
import time
import xml.etree.ElementTree as etree

PAGE_TAG = 'page'

DISPLAY_PATH = 'title'

DISPLAY_AFTER = 1000

MEDIAWIKI = re.escape('http://www.mediawiki.org')

MEDIAWIKI_EXPORT = rf'\{{{MEDIAWIKI}/xml/export-\d+(?:\.\d+)*/\}}mediawiki'


def present_file(s):
    if not s:
        return None
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None
    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    return result


def positive_int(s):
    try:
        result = int(s)
    except ValueError:
        result = None
    if result is None or not result > 0:
        raise argparse.ArgumentTypeError(f'need positive int: {s}')
    return result


def _extract_ns(tag):
    return tag.partition('{')[2].partition('}')[0]


def iterparse(filename, tag):
    with bz2.BZ2File(filename) as f:
        pairs = etree.iterparse(f, events=('start', 'end'))

        _, root = next(pairs)
        ns = _extract_ns(root.tag)
        assert root.tag.startswith(f'{{{ns}}}')
        yield root
        del root

        tag = f'{{{ns}}}{tag}'
        for event, elem in pairs:
            if elem.tag == tag and event == 'end':
                yield elem


def count_tags(filename, tag, *, display_path, display_after):
    tags = iterparse(filename, tag)

    root = next(tags)
    assert re.fullmatch(MEDIAWIKI_EXPORT, root.tag)
    ns = _extract_ns(root.tag)

    display_path = f'{{{ns}}}{display_path}' if display_path else None
    for count, elem in enumerate(tags, start=1):
        if not count % display_after:
            msg = f'{count:,}'
            if display_path is not None:
                msg += f'\t{elem.findtext(display_path)}'
            log(msg)
        root.clear()  # free memory
    return count


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('filename', type=present_file,
                    help='path to MediaWiki XML export (.xml.bz2)')

parser.add_argument('--tag', default=PAGE_TAG,
                    help=f'end tag to count (default: {PAGE_TAG})')

parser.add_argument('--display', metavar='PATH', default=DISPLAY_PATH,
                    help='ElementPath to log in sub-total'
                         f' (default: {DISPLAY_PATH})')

parser.add_argument('--display-after', metavar='N', type=positive_int,
                    default=DISPLAY_AFTER,
                    help='log sub-total after N tags'
                         f' (default: {DISPLAY_AFTER})')

parser.add_argument('--version', action='version', version=__version__)


log = functools.partial(print, file=sys.stderr, sep='\n')


if __name__ == '__main__':
    args = parser.parse_args()
    kwargs = {'display_path': args.display, 'display_after': args.display_after}
    start = time.monotonic()
    n = count_tags(args.filename, args.tag, **kwargs)
    stop = time.monotonic()
    log(f'duration: {stop - start:.2f} seconds')
    print(n)
