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

MEDIAWIKI_EXPORT = r'http://www\.mediawiki\.org/xml/export-\d+(?:\.\d+)*/'


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


def ntags(filename, tag, *, display_path, display_after):
    count = 0
    start = time.monotonic()
    with bz2.BZ2File(filename) as f:
        pairs = etree.iterparse(f, events=('start', 'end'))
        _, root = next(pairs)
        ns = root.tag.partition('{')[2].partition('}')[0]
        assert re.fullmatch(MEDIAWIKI_EXPORT, ns)
        assert root.tag == f'{{{ns}}}mediawiki'
        tag = f'{{{ns}}}{tag}'
        display_path = f'{{{ns}}}{display_path}' if display_path else None
        for event, elem in pairs:
            if elem.tag == tag and event == 'end':
                count += 1
                if not (count % display_after):
                    msg = f'{count:,}'
                    if display_path is not None:
                        msg += f'\t{elem.findtext(display_path)}'
                    log(msg)
                root.clear()
    stop = time.monotonic()
    if verbose:
        log(f'duration: {stop - start:.2f} seconds')
    return count


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('filename', type=present_file,
                    help='path to MediaWiki XML export (.xml.bz2)')

parser.add_argument('--tag', default=PAGE_TAG,
                    help=f'end tag to count (default: {PAGE_TAG})')

parser.add_argument('--display', metavar='PATH', default=DISPLAY_PATH,
                    help='ElementPath to log in sub-total'
                         f' (default: {DISPLAY_PATH})')

parser.add_argument('--display_after', metavar='N', type=int,
                    default=DISPLAY_AFTER,
                    help='log sub-total after N tags'
                         f' (default: {DISPLAY_AFTER})')

parser.add_argument('--version', action='version', version=__version__)


log = functools.partial(print, file=sys.stderr, sep='\n')


if __name__ == '__main__':
    args = parser.parse_args()
    kwargs = {'display_path': args.display, 'display_after': args.display_after}
    count = ntags(args.filename, args.tag, **kwargs)
    print(count)
