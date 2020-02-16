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

MEDIAWIKI_EXPORT = rf'\{{{_MEDIAWIKI}/xml/export-\d+(?:\.\d+)*/\}}mediawiki'

ENCODING = 'utf-8'

GZIP = 'gzip'


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('page_title', help='title of the page on MediaWiki')

parser.add_argument('search_string', help='string to match page wikitext')

parser.add_argument('--export-url', metavar='URL', default=EXPORT_URL,
                    help=f'MediaWiki instance export url (default: {EXPORT_URL})')

parser.add_argument('--version', action='version', version=__version__)

args = parser.parse_args()

log = functools.partial(print, file=sys.stderr, sep='\n')

post = urllib.parse.urlencode({'pages': args.page_title, 'wpDownload': 1})
req = urllib.request.Request(args.export_url,
                             data=post.encode(ENCODING),
                             headers={'accept-encoding': GZIP})

log(f'export url: {args.export_url}', f'post: {post}', '')

log(f'urllib.request.urlopen({req})')
with urllib.request.urlopen(req) as f:
    c_headers = 'type', 'disposition', 'encoding'
    c_values = tuple(f.info().get(f'content-{h}') for h in c_headers)
    for h, v in zip(c_headers, c_values):
        log(f'content-{h}: {v}')
    ct, cd, ce = c_values

    assert ct == f'application/xml; charset={ENCODING}'
    assert cd.startswith('attachment;filename=')
    assert ce == GZIP

    with gzip.open(f) as z:
        tree = etree.parse(z)

root_tag = tree.getroot().tag
ns = root_tag.partition('{')[2].partition('}')[0]
log(f'xml: {ns}')
assert root_tag.startswith(f'{{{ns}}}')
assert re.fullmatch(MEDIAWIKI_EXPORT, root_tag)
ns = {'namespaces': {'ns': ns}}

info, = tree.findall('ns:siteinfo', **ns)
i_keys = 'sitename', 'dbname', 'base'
i_values = tuple(info.findtext(f'ns:{k}', **ns) for k in i_keys)
for k, v in zip(i_keys, i_values):
    log(f'siteinfo/{k}: {v}')

page, = tree.findall('ns:page', **ns)
p_keys = 'ns', 'title', 'id'
p_values = tuple(page.findtext(f'ns:{k}', **ns) for k in p_keys)
for k, v in zip(p_keys, p_values):
    log(f'page/{k}: {v}')

p_ns, p_title, _ = p_values
assert p_ns == '0'
assert p_title == args.page_title

log(f'search string: {args.search_string}')
for r in page.iterfind('ns:revision', **ns):
    if args.search_string in r.findtext('ns:text', '', **ns):
        log()
        etree.dump(r)

        break
