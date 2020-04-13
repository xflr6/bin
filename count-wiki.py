#!/usr/bin/env python3

"""Count page tags in MediaWiki XML export."""

__title__ = 'count-wiki.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import builtins
import bz2
import collections
import difflib
import functools
import gzip
import lzma
import pathlib
import re
import sys
import time
import xml.etree.ElementTree as etree

PREFIX = 'mediawiki'

PAGE_TAG = f'{PREFIX}:page'

REDIRECT_PATH = f'{PREFIX}:redirect'

REVISION_PATH = f'{PREFIX}:revision'

USER_PATH = f'{PREFIX}:contributor/{PREFIX}:username'

TEXT_PATH = f'{PREFIX}:text'

DISPLAY_PATH = f'{PREFIX}:title'

DISPLAY_AFTER = 1000

MOST_COMMON_N = 100

_MEDIAWIKI = re.escape('http://www.mediawiki.org')

MEDIAWIKI_EXPORT = r'\{%s/xml/export-\d+(?:\.\d+)*/\}mediawiki' % _MEDIAWIKI

SUFFIX_OPEN_MODULE = {'.bz2':  bz2,
                      '.gz': gzip,
                      '.xml': builtins,
                      '.xz': lzma}


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

parser.add_argument('filename', type=pathlib.Path,
                    help='path to MediaWiki XML export (format: .xml.bz2)')

parser.add_argument('--tag', default=PAGE_TAG,
                    help=f'end tag to count (default: {PAGE_TAG})')

parser.add_argument('--stats', dest='simple_stats', action='store_false',
                    help='also compute and display page edit statistics')

parser.add_argument('--stats-top', dest='most_common_n',
                    metavar='N', type=positive_int, default=MOST_COMMON_N,
                    help='show top N users edits and lines'
                         f' (default: {MOST_COMMON_N})')

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


def make_display_func(display_epath):
    if display_epath is None:
        return lambda n, _: log(f'{n:,}')
    else:
        return lambda n, elem: log(f'{n:,}\t{elem.findtext(display_epath)}')


def count_elements(root, elements, *, display_after, display_epath, stop_after):
    if display_after in (None, 0):
        if stop_after is not None:
            raise NotImplementedError
        return sum(root.clear() is None for _ in elements)

    display_func = make_display_func(display_epath)

    count = 0

    for count, elem in enumerate(elements, start=1):
        if not count % display_after:
            display_func(count, elem)

        root.clear()  # free memory

        if count == stop_after:
            break

    return count


def count_edits(root, pages, *, display_after, display_epath, stop_after,
                rev_epath, user_epath, text_epath):
    display_func = make_display_func(display_epath)

    n_edits, n_lines = (collections.Counter() for _ in range(2))

    count = 0

    for count, p in enumerate(pages, start=1):
        if not count % display_after:
            display_func(count, p)

        old_text = ''
        for rev in p.iterfind(rev_epath):
            user = rev.findtext(user_epath)

            n_edits[user] += 1

            new_text = rev.findtext(text_epath)
            if new_text is not None:
                n_lines[user] += lines_changed(old_text, new_text)

                old_text = new_text

        root.clear()  # free memory

        if count == stop_after:
            break

    return count, n_edits, n_lines


def lines_changed(a, b, _n_lines_factor={'insert': 2, 'replace': 1,
                                        'delete': 0, 'equal': 0}):
    matcher = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines())

    total = 0

    for tiijj in matcher.get_opcodes():
        factor = _n_lines_factor[tiijj[0]]
        if factor:
            n_lines = tiijj[4] - tiijj[3]
            total += n_lines * factor

    if total:
        total = 1 + total // 2
    return total


def main(args=None):
    args = parser.parse_args(args)
    log(f'filename: {args.filename}', '')

    try:
        open_module = SUFFIX_OPEN_MODULE[args.filename.suffix]
    except KeyError:
        return ('error: invalid filename suffix'
                f" (need one of: {', '.join(SUFFIX_OPEN_MODULE)})")

    start = time.monotonic()

    log(f'{open_module.__name__}.open({args.filename!r})')
    with open_module.open(args.filename, 'rb') as f:
        pairs = etree.iterparse(f, events=('start', 'end'))

        _, root = next(pairs)
        if not re.fullmatch(MEDIAWIKI_EXPORT, root.tag):
            return f'error: invalid xml root tag {root.tag!r}'

        ns = extract_ns(root.tag)
        log(f'xml: {ns!r}')
        ns_map = {PREFIX: ns}

        elements = iterelements(pairs,
                                tag=make_epath(args.tag, ns_map),
                                exclude_with=make_epath(REDIRECT_PATH, ns_map))

        display_epath = make_epath(args.display, ns_map, optional=True)

        kwargs = {'display_after': args.display_after,
                  'display_epath': display_epath,
                  'stop_after': args.stop_after}

        if args.simple_stats:
            n = count_elements(root, elements, **kwargs)
            counters = ()
        else:
            kwargs.update(rev_epath=make_epath(REVISION_PATH, ns_map),
                          user_epath=make_epath(USER_PATH, ns_map),
                          text_epath=make_epath(TEXT_PATH, ns_map))

            n, n_edits, n_lines = count_edits(root, elements, **kwargs)
            counters = n_edits, n_lines

    stop = time.monotonic()
    log(f'duration: {stop - start:.2f} seconds')

    print(n)
    for c in counters:
        top_n = c.most_common(args.most_common_n)
        lines = (f'{user!s:<16}\t{n:d}' for user, n in top_n)
        print('', *lines, sep='\n')

    return None


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
