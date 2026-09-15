#!/usr/bin/env python3

"""Count page tags in MediaWiki XML export."""

__title__ = 'wiki-count.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
from collections.abc import Mapping, Sequence
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
import xml.etree.ElementTree as etree  # noqa: N813

PAGE_TAG = 'page'

DISPLAY_PATH = 'title'

DISPLAY_AFTER = 1_000

MOST_COMMON_N = 100

MEDIAWIKI_EXPORT = r'\{(?P<ns>http://www\.mediawiki\.org/xml/export-\d+(?:\.\d+)*/)\}mediawiki'

SUFFIX_OPEN_MODULE = {'.bz2': bz2,
                      '.gz': gzip,
                      '.xml': builtins,
                      '.xz': lzma}


def parse_args(args: Sequence[str] | None, /) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('filename', type=pathlib.Path,
                        help='path to MediaWiki XML export (format: .xml.bz2)')

    parser.add_argument('--tag', default=PAGE_TAG,
                        help=f'end tag to count (default: {PAGE_TAG})')

    parser.add_argument('--stats', dest='simple_stats', action='store_false',
                        help='also compute and display page edit statistics')

    def positive_int(s: str, /) -> int | None:
        if s is None or not s.strip():
            return None
        try:
            result = int(s)
        except ValueError:
            result = None
        if result is None or not result > 0:
            raise argparse.ArgumentTypeError(f'need positive int: {s}')
        return result

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
    return parser.parse_args(args)


def wiki_count(filename: pathlib.Path, /, *,
               tag: str,
               simple_stats: bool,
               most_common_n: int,
               display: str,
               display_after: int,
               stop_after: int) -> str | None:
    log(f'filename: {filename}', '')
    try:
        open_module = SUFFIX_OPEN_MODULE[filename.suffix]
    except KeyError:
        return ('error: invalid filename suffix'
                f" (need one of: {', '.join(SUFFIX_OPEN_MODULE)})")

    start = time.monotonic()
    log(f'{open_module.__name__}.open({filename!r})')
    with open_module.open(filename, mode='rb') as f:
        pairs = etree.iterparse(f, events=('start', 'end'))
        (_, root) = next(pairs)
        if (ma := re.fullmatch(MEDIAWIKI_EXPORT, root.tag)) is None:
            return f'error: invalid xml root tag {root.tag!r}'
        root_namespace = ma['ns']
        log(f'xml: {root_namespace!r}')
        namespaces = {'': root_namespace}

        elements = iterelements(pairs, tag=tag, exclude_with='redirect',
                                namespaces=namespaces)
        kwargs = {'display': display,
                  'display_after': display_after,
                  'stop_after': stop_after,
                  'namespaces': namespaces}
        if simple_stats:
            n = count_elements(root, elements, **kwargs)
            counters = []
        else:
            (n, n_edits, n_lines) = count_edits(root, elements, **kwargs)
            counters = [n_edits, n_lines]
    stop = time.monotonic()
    log(f'duration: {stop - start:.2f} seconds')

    print(n)
    for c in counters:
        top_n = c.most_common(most_common_n)
        lines = (f'{user!s:<16}\t{n:d}' for user, n in top_n)
        print('', *lines, sep='\n')
    return None


log = functools.partial(print, file=sys.stderr, sep='\n')


def iterelements(pairs, /, tag: str, *, exclude_with: str, namespaces: Mapping[str, str]):
    tag = make_epath(tag, namespaces)
    exclude_with = make_epath(exclude_with, namespaces)
    for event, elem in pairs:
        if elem.tag == tag and event == 'end' and elem.find(exclude_with) is None:
            yield elem


def make_epath(s: str, /, namespaces: Mapping[str, str]) -> str:
    assert s.strip(), 'must be non-empty'

    def repl(ma):
        try:
            ns = namespaces[prefix := ma['prefix'] or '']
        except KeyError:
            if ma['prefix'] is None:
                return ma['boundary']
            raise ValueError(f'unknown namespace prefix in {s!r}: {prefix!r}')
        return ma.expand(r'\g<boundary>{%s}' % ns)

    return re.sub(r'(?P<boundary>^|/)(?:(?P<prefix>\w+):)?', repl, s)


def count_elements(root, /, elements, *,
                   display: str | None,
                   display_after: int,
                   stop_after: int,
                   namespaces: Mapping[str, str]) -> int:
    if display_after in (None, 0):
        if stop_after is not None:
            raise NotImplementedError
        return sum(root.clear() is None for _ in elements)

    display_func = make_display_func(display, namespaces)

    count = 0
    for count, elem in enumerate(elements, start=1):
        if not count % display_after:
            display_func(count, elem)
        root.clear()  # free memory
        if count == stop_after:
            break
    return count


def make_display_func(display: str | None, /, namespaces: Mapping[str, str]):
    if display is not None:
        display_epath = make_epath(display, namespaces)
        return lambda n, elem: log(f'{n:,}\t{elem.findtext(display_epath)}')
    return lambda n, _: log(f'{n:,}')


def count_edits(root, /, pages, *,
                display: str | None,
                display_after: int,
                stop_after: int,
                namespaces: Mapping[str, str]) -> int:
    display_func = make_display_func(display, namespaces)

    rev_epath = make_epath('revision', namespaces)
    user_epath = make_epath('contributor/username', namespaces)
    text_epath = make_epath('text', namespaces)

    n_edits = collections.Counter()
    n_lines = collections.Counter()
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


def lines_changed(a: str, b: str, /, *,
                  _n_lines_factor={'insert': 2, 'replace': 1,
                                   'delete': 0, 'equal': 0}) -> int:
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


def main(args: Sequence[str] | None = None) -> str | None:
    args = parse_args(args)
    return wiki_count(args.filename,
                      tag=args.tag,
                      simple_stats=args.simple_stats,
                      most_common_n=args.most_common_n,
                      display=args.display,
                      display_after=args.display_after,
                      stop_after=args.stop_after)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
