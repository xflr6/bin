#!/usr/bin/env python3

"""Dump XML of first MediaWiki page revision containing a search string."""

__title__ = 'blame-wiki.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import gzip
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as etree

EXPORT_URL = 'https://en.wikipedia.org/wiki/Special:Export'

_MEDIAWIKI = re.escape('http://www.mediawiki.org')

MEDIAWIKI_EXPORT = r'\{%s/xml/export-\d+(?:\.\d+)*/\}mediawiki' % _MEDIAWIKI

ENCODING = 'utf-8'

GZIP = 'gzip'


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('page_title', help='title of the page on MediaWiki')

parser.add_argument('search_string', help='string to match page wikitext')

parser.add_argument('--export-url', metavar='URL', default=EXPORT_URL,
                    help=f'MediaWiki instance export url (default: {EXPORT_URL})')

parser.add_argument('--version', action='version', version=__version__)


log = functools.partial(print, file=sys.stderr, sep='\n')


def make_request(url: str, title: str, *,
                 encoding: str = ENCODING) -> urllib.request.Request:
    post = {'pages': title, 'wpDownload': 1}
    data = urllib.parse.urlencode(post).encode(encoding)
    kwargs = {'headers': {'accept-encoding': GZIP}}
    return urllib.request.Request(url, data=data, **kwargs)


def parse_response(resp, *, encoding: str = ENCODING) -> etree.ElementTree:
    info = resp.info()
    headers = {h: info.get(h) for h in ('content-type',
                                        'content-disposition',
                                        'content-encoding')}
    for key, value in headers.items():
        log(f'{key}: {value}')

    assert headers['content-type'] == f'application/xml; charset={encoding}'
    assert headers['content-disposition'].startswith('attachment;filename=')
    assert headers['content-encoding'] == GZIP

    with gzip.open(resp) as f:
        return etree.parse(f)


def extract_ns(tag: str) -> str:
    ns = tag.partition('{')[2].partition('}')[0]
    assert tag.startswith('{%s}' % ns)
    return ns


def elem_findtext(elem, *tags, prefix=None, **kwargs):
    prefix = prefix + ':' if prefix is not None else ''
    values = (elem.findtext(prefix + t, **kwargs) for t in tags)
    return dict(zip(tags, values))


def main(args=None) -> str | None:
    args = parser.parse_args(args)
    log(f'export url: {args.export_url}',
        f'title: {args.page_title}', '')

    req = make_request(args.export_url, args.page_title)
    log(f'urllib.request.urlopen({req})')
    with urllib.request.urlopen(req) as f:
        tree = parse_response(f)

    root = tree.getroot()
    if not re.fullmatch(MEDIAWIKI_EXPORT, root.tag):
        return f'error: invalid xml root tag {root.tag!r}'

    ns = extract_ns(root.tag)
    log(f'xml: {ns!r}')
    ns = {'namespaces': {'mw': ns}}

    (site,) = tree.findall('mw:siteinfo', **ns)
    for k, v in elem_findtext(site, 'sitename', 'dbname', 'base', prefix='mw', **ns).items():
        log(f'siteinfo/{k}: {v}')

    (page,) = tree.findall('mw:page', **ns)
    page_infos = elem_findtext(page, 'ns', 'title', 'id', prefix='mw', **ns)
    for k, v in page_infos.items():
        log(f'page/{k}: {v}')

    if page_infos['ns'] != '0':
        return 'error: mediawiki:ns mismatch'
    if page_infos['title'] != args.page_title:
        return 'error: mediawiki:title mismatch'

    log(f'search string: {args.search_string}')
    for r in page.iterfind('mw:revision', **ns):
        if args.search_string in r.findtext('mw:text', '', **ns):
            log()
            etree.dump(r)
            return None

    return 'not found'


if __name__ == '__main__':  # pragma: no cover
    parser.exit(main())
