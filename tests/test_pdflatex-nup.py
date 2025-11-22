import importlib
import re

import pytest

pdflatex_nup = importlib.import_module('pdflatex-nup')


@pytest.mark.parametrize('keep', [False, True], ids=lambda x: 'keep=%r' % x)
def test_main(tmp_path, mocker, completed_proc, keep, encoding='utf-8'):
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

        return completed_proc

    run = mocker.patch('subprocess.run', autospec=True, side_effect=run)

    assert pdflatex_nup.main([str(pdf_path),
                              '--name', '{stem}-2UP.pdf',
                              '--paper', 'legal',
                              '--nup', '2x1',
                              '--pages', '1-42',
                              '--orient', 'a',
                              '--scale', '.942',
                              '--no-frame',
                              '--no-openright']
                             + (['--keep'] if keep else [])) is None

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

    assert tex_path.exists() == keep

    run.assert_called_once_with(['pdflatex', '-interaction=batchmode',
                                 tex_path.name], check=True, cwd=tmp_path)

    assert not completed_proc.mock_calls
