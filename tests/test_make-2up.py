import contextlib
import importlib
import os
import subprocess

make_2up = importlib.import_module('make-2up')


@contextlib.contextmanager
def chdir(path):
    old = os.getcwd()

    os.chdir(path)
    yield None

    os.chdir(old)
    return


def test_make_2up(tmp_path, mocker, encoding='utf-8'):
    paths = 'spam.pdf', 'spam-2up.tex', 'spam-2up.pdf'
    pdf_path, tex_path, dest_path = (tmp_path / p for p in paths)

    pdf_path.write_bytes(b'')
    tex_path.write_text('', encoding=encoding)

    doc = None

    def run(*args, **kwargs):
        nonlocal doc
        doc = tex_path.read_text(encoding=encoding)
        dest_path.write_bytes(b'\xde\xad\xbe\xef')
        return mocker.create_autospec(subprocess.CompletedProcess, returncode=0)

    run = mocker.patch('subprocess.run', side_effect=run, autospec=True)

    with chdir(tmp_path):
        assert make_2up.main([pdf_path.name,
                              '{stem}-2up.pdf',
                              '--pages', '1-42',
                              '--scale', '.9',
                              '--no-frame']) is None

    assert not tex_path.exists()

    assert doc == ('\\documentclass[paper=a4,paper=landscape]{scrartcl}\n'
                   '\\usepackage{pdfpages}\n'
                   '\\pagestyle{empty}\n'
                   '\\begin{document}\n'
                   '% http://www.ctan.org/pkg/pdfpages\n'
                   '\\includepdfmerge[nup=2x1,openright,scale=.9,frame=false]'
                   '{spam.pdf,1-42}\n'
                   '\\end{document}')

    run.assert_called_once_with(['pdflatex',
                                 '-interaction=batchmode',
                                 tex_path.relative_to(tmp_path)],
                                check=True)
