#!/usr/bin/env python3

"""Dump XML of first MediaWiki page revision containing a search string."""

__title__ = 'wiki-blame.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
from collections.abc import Mapping, Sequence
import functools
import gzip
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as etree  # noqa: N813

MEDIAWIKI_EXPORT = r'\{(?P<ns>http://www\.mediawiki\.org/xml/export-\d+(?:\.\d+)*/)\}mediawiki'

ENCODING = 'utf-8'


def parse_args(args: Sequence[str] | None, /) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('page_title', help='title of the page on MediaWiki')

    parser.add_argument('search_string', help='string to match page wikitext')

    parser.add_argument('--export-url', metavar='URL',
                        default='https://en.wikipedia.org/wiki/Special:Export',
                        help='MediaWiki instance export url')

    parser.add_argument('--version', action='version', version=__version__)
    return parser.parse_args(args)


def wiki_blame(*,
               page_title: str,
               search_string: str,
               export_url: str) -> str | None:
    log(f'export url: {export_url}', f'title: {page_title}')
    request = make_request(export_url, page_title)
    log(f'urllib.request.urlopen({request})')
    with urllib.request.urlopen(request) as f:
        tree = parse_response(f)

    root = tree.getroot()
    if (ma := re.fullmatch(MEDIAWIKI_EXPORT, root.tag)) is None:
        return f'error: invalid xml root tag {root.tag!r}'
    root_namespace = ma['ns']
    log('', f'xml: {root_namespace!r}')
    etree.register_namespace('', root_namespace)
    ns = {'namespaces': {'': root_namespace}}

    (site,) = tree.findall('siteinfo', **ns)
    for k, v in elem_findtext(site, 'sitename', 'dbname', 'base', **ns).items():
        log(f'siteinfo/{k}: {v}')

    (page,) = tree.findall('page', **ns)
    page_infos = elem_findtext(page, 'ns', 'title', 'id', **ns)
    for k, v in page_infos.items():
        log(f'page/{k}: {v}')
    if page_infos['ns'] != '0':
        return 'error: mediawiki:ns mismatch'
    if page_infos['title'] != page_title:
        return 'error: mediawiki:title mismatch'

    log(f'search string: {search_string}')
    for r in page.iterfind('revision', **ns):
        if search_string in r.findtext('text', '', **ns):
            log()
            etree.dump(r)
            return None
    return 'not found'


log = functools.partial(print, file=sys.stderr, sep='\n')


def make_request(url: str, /, title: str, *,
                 accept_encoding: str = 'gzip',
                 user_agent: str = ('Mozilla/5.0 (X11; U; Linux i686)'
                                    ' Gecko/20071127 Firefox/2.0.0.11'),
                 encoding: str = ENCODING) -> urllib.request.Request:
    post = {'pages': title, 'wpDownload': 1}
    data = urllib.parse.urlencode(post).encode(encoding)
    headers = {'Accept-encoding': accept_encoding,
               'User-agent': user_agent}
    return urllib.request.Request(url, data=data, headers=headers)


def parse_response(response, /, *,
                   encoding: str = ENCODING) -> etree.ElementTree:
    info = response.info()
    headers = {h: info.get(h) for h in ('content-type',
                                        'content-disposition',
                                        'content-encoding')}
    for key, value in headers.items():
        log(f'{key}: {value}')
    assert headers['content-type'] == f'application/xml; charset={encoding}'
    assert headers['content-disposition'].startswith('attachment;filename=')
    assert headers['content-encoding'] == 'gzip'

    with gzip.open(response) as f:
        return etree.parse(f)


def elem_findtext(elem, /, *tags: str,
                  prefix: str | None = None,
                  **kwargs) -> Mapping[str, str]:
    prefix = prefix + ':' if prefix is not None else ''
    values = (elem.findtext(prefix + t, **kwargs) for t in tags)
    return dict(zip(tags, values))


def main(args: Sequence[str] | None = None) -> str | None:
    args = parse_args(args)
    return wiki_blame(page_title=args.page_title,
                      search_string=args.search_string,
                      export_url=args.export_url)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
