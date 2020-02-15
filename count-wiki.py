#!/usr/bin/env python3
# wikicount.py - count pages in wikipedia xml export

import bz2
import re
import sys
import time
import xml.etree.ElementTree as etree

FILENAME = 'dewiki-latest-pages-articles.xml.bz2'

MEDIAWIKI_EXPORT = r'http://www\.mediawiki\.org/xml/export-\d+(?:\.\d+)*/'

PAGE_TAG = 'page'

DISPLAY_TAG = 'title'


def ntags(filename, tag=PAGE_TAG, display_tag=DISPLAY_TAG, progress_after=1000):
    count = 0
    start = time.time()
    with bz2.BZ2File(filename) as f:
        pairs = etree.iterparse(f, events=('start', 'end'))
        _, root = next(pairs)
        ns = root.tag.partition('{')[2].partition('}')[0]
        assert re.fullmatch(MEDIAWIKI_EXPORT, ns)
        assert root.tag == f'{{{ns}}}mediawiki'
        tag = f'{{{ns}}}{tag}'
        display_tag = f'{{{ns}}}{display_tag}' if display_tag else None
        for event, elem in pairs:
            if elem.tag == tag and event == 'end':
                count += 1
                if not (count % progress_after):
                    msg = f'{count:,}'
                    if display_tag is not None:
                        msg += f'\t{elem.findtext(display_tag)}'
                    print(msg)
                root.clear()
    stop = time.time()
    if verbose:
        print(f'duration: {stop - start:.2f} seconds')
    return count


if __name__ == '__main__':
    if len(sys.argv) > 2:
        sys.exit(f'Usage: {sys.argv[0]} <filename>')
    elif len(sys.argv) == 1:
        filename = FILENAME
    elif len(sys.argv) == 2:
        filename = sys.argv[1]
    print(ntags(filename))
