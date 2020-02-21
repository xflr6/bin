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

PREFIX = 'mediawiki'

PAGE_TAG = f'{PREFIX}:page'

DISPLAY_PATH = f'{PREFIX}:title'

DISPLAY_AFTER = 1000

_MEDIAWIKI = re.escape('http://www.mediawiki.org')

MEDIAWIKI_EXPORT = r'\{%s/xml/export-\d+(?:\.\d+)*/\}mediawiki' % _MEDIAWIKI


log = functools.partial(print, file=sys.stderr, sep='\n')


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


def extract_ns(tag):
    ns = tag.partition('{')[2].partition('}')[0]
    assert tag.startswith('{%s}' % ns)
    return ns


def make_epath(s, namespace_map):
    start, sep, rest = s.strip().partition(':')
    assert start
    if sep:
        assert rest
        try:
            ns = namespace_map[start]
        except KeyError:
            raise ValueError(f'unknown namespace: {start}')
        return '{%s}%s' % (ns, rest)
    else:
        return start


def iterelements(pairs, tag):
    for event, elem in pairs:
        if elem.tag == tag and event == 'end':
            yield elem


def count_elements(root, elements, *, display_path, display_after):
    for count, elem in enumerate(elements, start=1):
        if not count % display_after:
            msg = f'{count:,}'
            if display_path is not None:
                msg += f'\t{elem.findtext(display_path)}'
            log(msg)
        root.clear()  # free memory
    return count


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('filename', type=present_file,
                    help='path to MediaWiki XML export (format: .xml.bz2)')

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


def main(args=None):
    args = parser.parse_args(args)

    start = time.monotonic()
    with bz2.BZ2File(args.filename) as f:
        pairs = etree.iterparse(f, events=('start', 'end'))

        _, root = next(pairs)
        assert re.fullmatch(MEDIAWIKI_EXPORT, root.tag)
        ns_map = {PREFIX: extract_ns(root.tag)}
        tag = make_epath(args.tag, ns_map)
        display_path = make_epath(args.display, ns_map) if args.display else None

        elements = iterelements(pairs, tag=tag)
        n = count_elements(root, elements,
                           display_path=display_path,
                           display_after=args.display_after)
    stop = time.monotonic()
    log(f'duration: {stop - start:.2f} seconds')

    print(n)
    return None


if __name__ == '__main__':
    sys.exit(main())
