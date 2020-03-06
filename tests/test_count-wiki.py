import bz2
import importlib

count_wiki = importlib.import_module('count-wiki')

EXPORT = '''\
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/">
  <page>
    <title>Main Page</title>
    <redirect title="Spam" />
  </page>
  <page>
    <title>Spam</title>
  </page>
</mediawiki>
'''

ENCODING = 'utf-8'


def test_blame_wiki(capsys, tmp_path):
    export = tmp_path / 'spamwiki-latest-pages-articles.xml.bz2'
    with export.open('wb') as z, bz2.open(z, 'wb') as f:
        f.write(EXPORT.encode(ENCODING))

    assert count_wiki.main([str(export)]) is None

    out, err = capsys.readouterr()
    assert out == '1\n'
    assert err == ''
