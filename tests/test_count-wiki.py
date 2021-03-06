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
  <page>
    <title>Eggs</title>
  </page>
</mediawiki>
'''

ENCODING = 'utf-8'


def test_count_wiki(capsys, tmp_path):
    export = tmp_path / 'spamwiki-latest-pages-articles.xml.bz2'

    with export.open('wb') as z, bz2.open(z, 'wt', encoding=ENCODING) as f:
        f.write(EXPORT)

    assert count_wiki.main([str(export),
                            '--tag', 'mediawiki:page',
                            '--display', 'mediawiki:title',
                            '--display-after', '100',
                            '--stop-after', '1000']) is None

    out, err = capsys.readouterr()
    assert out == '2\n'
    assert not err
