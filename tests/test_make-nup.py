import importlib
import re
import subprocess

import pytest

make_nup = importlib.import_module('make-nup')


@pytest.mark.parametrize('keep', [False, True], ids=lambda x: 'keep=%r' % x)
def test_make_nup(tmp_path, mocker, keep, encoding='utf-8'):
    pdf_path = tmp_path / 'spam.pdf'
    pdf_path.write_bytes(b'')

    tex_path = tmp_path / 'spam-2UP.tex'
    tex_path.write_text('')

    dest_path = tmp_path / 'spam-2UP.pdf'

    doc = newlines = None

    def run(*args, **kwargs):
        nonlocal doc, newlines

        with open(tex_path, encoding=encoding, newline='') as f:
            doc = f.read()

        newlines = f.newlines

        dest_path.write_bytes(b'\xde\xad\xbe\xef')

        return mocker.create_autospec(subprocess.CompletedProcess, returncode=0)

    run = mocker.patch('subprocess.run', side_effect=run, autospec=True)

    assert make_nup.main([str(pdf_path),
                          '--name', '{stem}-2UP.pdf',
                          '--paper', 'legal',
                          '--nup', '2x1',
                          '--pages', '1-42',
                          '--orient', 'a',
                          '--scale', '.942',
                          '--no-frame',
                          '--no-openright']
                         + (['--keep'] if keep else [])) is None

    assert tex_path.exists() == keep

    doc = re.sub(r'\s', '', doc)
    assert doc == ('\\documentclass['
                       'paper=legal,'
                       'paper=landscape'
                   ']{scrartcl}'
                       '\\usepackage{pdfpages}'
                       '\\pagestyle{empty}'
                   '\\begin{document}'
                       '\\includepdfmerge['
                           'nup=2x1,'
                           'openright=false,'
                           'scale=.942,'
                           'frame=false'
                       ']{spam.pdf,1-42}'
                   '\\end{document}')

    assert newlines == '\n'

    run.assert_called_once_with(['pdflatex', '-interaction=batchmode',
                                 tex_path.name], check=True, cwd=tmp_path)
