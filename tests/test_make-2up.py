import contextlib
import importlib
import os
import subprocess

import pytest

make_2up = importlib.import_module('make-2up')


@contextlib.contextmanager
def chdir(path):
    old = os.getcwd()

    os.chdir(path)
    yield None

    os.chdir(old)
    return


@pytest.mark.parametrize('keep', [False, True], ids=lambda x: 'keep=%r' % x)
def test_make_2up(tmp_path, mocker, keep, encoding='utf-8'):
    paths = 'spam.pdf', 'spam-2UP.tex', 'spam-2UP.pdf'
    pdf_path, tex_path, dest_path = (tmp_path / p for p in paths)

    pdf_path.write_bytes(b'')
    tex_path.write_text('', encoding=encoding)

    doc = None

    def run(*args, **kwargs):
        nonlocal doc

        with open(tex_path, encoding=encoding, newline='') as f:
            doc = f.read()

        dest_path.write_bytes(b'\xde\xad\xbe\xef')

        return mocker.create_autospec(subprocess.CompletedProcess, returncode=0)

    run = mocker.patch('subprocess.run', side_effect=run, autospec=True)

    with chdir(tmp_path):
        assert make_2up.main([pdf_path.name,
                              '{stem}-2UP.pdf',
                              '--paper', 'legal',
                              '--pages', '1-42',
                              '--scale', '.942',
                              '--no-frame',
                              '--no-openright']
                             + (['--keep'] if keep else [])) is None

    assert tex_path.exists() == keep

    assert doc == '''\
\\documentclass[paper=legal,paper=landscape]{scrartcl}
\\usepackage{pdfpages}
\\pagestyle{empty}
\\begin{document}
% http://www.ctan.org/pkg/pdfpages
\\includepdfmerge[nup=2x1,openright=false,scale=.942,frame=false]{spam.pdf,1-42}
\\end{document}
'''

    run.assert_called_once_with(['pdflatex',
                                 '-interaction=batchmode',
                                 tex_path.relative_to(tmp_path)],
                                check=True)
