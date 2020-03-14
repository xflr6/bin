#!/usr/bin/env python3
# see also https://github.com/DavidFirth/pdfjam

"""Compile a 2up version of a PDF file using LaTeX pdfpages' \\includepdfmerge."""

__title__ = 'make-2up.py'
__version__ = '0.1.dev0'
__author__ = 'Sebastian Bank <sebastian.bank@uni-leipzig.de>'
__license__ = 'MIT, see LICENSE.txt'
__copyright__ = 'Copyright (c) 2020 Sebastian Bank'

import argparse
import functools
import pathlib
import string
import subprocess
import sys

NAME_TEMPLATE = '{stem}_2up.pdf'

PAPER = 'a4'

PAGES = '-'

SCALE = '1.01'

TEMPLATE = ('\\documentclass['  # http://www.ctan.org/pkg/pdfpages'
                'paper=$paper,'
                'paper=landscape'
            ']{scrartcl}\n'
                '\\usepackage{pdfpages}\n'
                '\\pagestyle{empty}\n'
            '\\begin{document}\n'
                '\\includepdfmerge['
                    'nup=2x1,'
                    'openright=$openright,'
                    'scale=$scale,'
                    'frame=$frame'
                ']{$filename,$pages}\n'
            '\\end{document}\n')

ENCODING = 'utf-8'


log = functools.partial(print, file=sys.stderr, sep='\n')


def present_pdf_file(s):
    try:
        result = pathlib.Path(s)
    except ValueError:
        result = None

    if result is None or not result.is_file():
        raise argparse.ArgumentTypeError(f'not a present file: {s}')
    elif result.suffix.lower() != '.pdf':
        raise argparse.ArgumentTypeError(f'not a pdf file: {s}')
    return result


def template(s):
    try:
        value = s.format(stem='')
    except (KeyError, IndexError):
        value = None

    if not value:
        raise argparse.ArgumentTypeError(f'invalid or empty template: {s}')
    elif pathlib.Path(value).parent.name:
        raise argparse.ArgumentTypeError(f'template contains directory: {s}')
    return s


def factor(s):
    try:
        value = float(s)
    except ValueError:
        value = None

    if not value or not 0 < value <= 10:
        raise argparse.ArgumentTypeError(f'invalid or zero factor: {s}')
    return s.strip()


parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('pdf_file', type=present_pdf_file,
                    help='name of the source PDF file for \\includepdfmerge')

parser.add_argument('--name', metavar='TMPL',
                    type=template, default=NAME_TEMPLATE,
                    help=f'template for 2up PDF file (default: {NAME_TEMPLATE})')

parser.add_argument('--paper', metavar='SIZE', default=PAPER,
                    help=f'output LaTeX paper size (default: {PAPER})')

parser.add_argument('--pages', metavar='RANGE', default=PAGES,
                    help=f'pages option for \\includepdfmerge (default: {PAGES})')

parser.add_argument('--scale', metavar='FACTOR', type=factor, default=SCALE,
                    help=f'scale option for \\includepdfmerge (default: {SCALE})')

parser.add_argument('--no-frame', dest='frame', action='store_false',
                    help="don't pass frame option to \\includepdfmerge")

parser.add_argument('--no-openright', dest='openright', action='store_false',
                    help="don't pass openright option to \\includepdfmerge")

parser.add_argument('--keep', dest='clean_up', action='store_false',
                    help="don't delete intermediate files (*.tex, *.log, etc.)")

parser.add_argument('--version', action='version', version=__version__)


def render_template(*, paper, filename, pages, openright, scale, frame):
    template = string.Template(TEMPLATE)
    context = {'paper': paper,
               'filename': filename,
               'pages': pages,
               'scale': scale,
               'openright': 'true' if openright else 'false',
               'frame': 'true' if frame else 'false'}
    return template.substitute(context)


def main(args=None):
    args = parser.parse_args(args)

    dest_path = args.name.format(stem=args.pdf_file.stem)
    dest_path = args.pdf_file.with_name(dest_path)

    doc_path = dest_path.with_suffix('.tex')

    log(f'source: {args.pdf_file}',
        f'pdfpages doc: {doc_path}',
        f'destination: {dest_path}', '')

    doc = render_template(paper=args.paper,
                          filename=args.pdf_file.name,
                          pages=args.pages,
                          openright=args.openright,
                          scale=args.scale,
                          frame=args.frame)

    log(f'{doc_path!r}.write_text(..., encoding={ENCODING!r})')
    with doc_path.open('wt', encoding=ENCODING, newline='\n') as f:
        f.write(doc)

    cmd = ['pdflatex', '-interaction=batchmode', doc_path.name]

    log(f'subprocess.run({cmd!r}, cwd={doc_path.parent})')
    log(f'{"[ start subprocess ]":-^80}')
    subprocess.run(cmd, check=True, cwd=doc_path.parent)
    log(f'{"[ end subprocess ]":-^80}')

    if not dest_path.exists():
        return 'error: result file not found'

    if args.clean_up:
        delete_glob = dest_path.with_suffix('.*').name
        delete_paths = set(dest_path.parent.glob(delete_glob)) - {dest_path}
        for p in sorted(delete_paths):
            log(f'{p!r}.unlink()')
            p.unlink()


if __name__ == '__main__':
    sys.exit(main())
