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
import re
import sys
import time
import xml.etree.ElementTree as etree

PREFIX = 'mediawiki'

PAGE_TAG = f'{PREFIX}:page'

REDIRECT = f'{PREFIX}:redirect'

DISPLAY_PATH = f'{PREFIX}:title'

DISPLAY_AFTER = 1000

_MEDIAWIKI = re.escape('http://www.mediawiki.org')

MEDIAWIKI_EXPORT = r'\{%s/xml/export-\d+(?:\.\d+)*/\}mediawiki' % _MEDIAWIKI


log = functools.partial(print, file=sys.stderr, sep='\n')


def positive_int(s):
    if s is None or not s.strip():
        return None

    try:
        result = int(s)
    except ValueError:
        result = None

    if result is None or not result > 0:
        raise argparse.ArgumentTypeError(f'need positive int: {s}')
    return result


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('filename', type=argparse.FileType('rb'),
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

parser.add_argument('--stop-after', metavar='N', type=positive_int,
                    help='stop after N tags')

parser.add_argument('--version', action='version', version=__version__)


def extract_ns(tag):
    ns = tag.partition('{')[2].partition('}')[0]
    assert tag.startswith('{%s}' % ns)
    return ns


def make_epath(s, namespace_map, optional=False):
    s = s.strip()
    if optional and not s:
        return None
    assert s

    def repl(ma):
        ns = ma.group('ns')
        try:
            ns = namespace_map[ns]
        except KeyError:
            raise ValueError(f'unknown namespace in {s!r}: {ns}')
        return ma.expand(r'\g<boundary>{%s}' % ns)

    return re.sub(r'(?P<boundary>^|/)(?P<ns>\w+):', repl, s)


def iterelements(pairs, tag, exclude_with):
    for event, elem in pairs:
        if elem.tag == tag and event == 'end' and elem.find(exclude_with) is None:
            yield elem


def count_elements(root, elements, *, display_after, display_path, stop_after):
    if display_after in (None, 0):
        if stop_after is not None:
            raise NotImplementedError
        return sum(root.clear() is None for _ in elements)

    count = 0

    for count, elem in enumerate(elements, start=1):
        if not count % display_after:
            msg = f'{count:,}'
            if display_path is not None:
                msg += f'\t{elem.findtext(display_path)}'
            log(msg)
        root.clear()  # free memory
        if count == stop_after:
            break

    return count


def main(args=None):
    args = parser.parse_args(args)

    start = time.monotonic()

    with args.filename as z, bz2.open(z) as f:
        pairs = etree.iterparse(f, events=('start', 'end'))

        _, root = next(pairs)
        if not re.fullmatch(MEDIAWIKI_EXPORT, root.tag):
            return 'error: invalid xml namespace'
        ns_map = {PREFIX: extract_ns(root.tag)}

        elements = iterelements(pairs,
                                tag=make_epath(args.tag, ns_map),
                                exclude_with=make_epath(REDIRECT, ns_map))

        n = count_elements(root, elements,
                           display_after=args.display_after,
                           display_path=make_epath(args.display, ns_map, optional=True),
                           stop_after=args.stop_after)

    stop = time.monotonic()
    log(f'duration: {stop - start:.2f} seconds')

    print(n)
    return None


if __name__ == '__main__':
    sys.exit(main())
