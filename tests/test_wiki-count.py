import bz2
import gzip
import importlib
import textwrap

wiki_count = importlib.import_module('wiki-count')

EXPORT = '''
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/">
  <page>
    <title>Main Page</title>
    <redirect title="Spam" />
  </page>
  <page>
    <title>Spam</title>
    <revision>
      <contributor><username>Vikings</username></contributor>
      <text>Spam, Spam, Spam, Spam</text>
    </revision>
    <revision>
      <contributor><username>Vikings</username></contributor>
      <text>Spam, Spam, Spam, Spam</text>
    </revision>
    <revision>
      <contributor><username>Vikings</username></contributor>
      <text>Spam, Spam, Spam, Spam</text>
    </revision>
    <revision>
      <contributor><username>Vikings</username></contributor>
      <text>Lovely Spam! Wonderful Spam!</text>
    </revision>
  </page>
  <page>
    <title>Eggs</title>
    <revision>
      <contributor><username>Waitress</username></contributor>
      <text>Eggs and bacon</text>
    </revision>
  </page>
</mediawiki>
'''.lstrip()

ENCODING = 'utf-8'


def test_main(capsys, tmp_path):
    export = tmp_path / 'spamwiki-latest-pages-articles.xml.bz2'

    with (export.open(mode='wb') as z,
          bz2.open(z, mode='wt', encoding=ENCODING) as f):
        f.write(EXPORT)

    assert wiki_count.main([str(export),
                            '--tag', 'mediawiki:page',
                            '--display', 'mediawiki:title',
                            '--display-after', '100',
                            '--stop-after', '1000']) is None

    (out, err) = capsys.readouterr()
    assert out == '2\n'
    assert not err


def test_main_gz_stats(capsys, tmp_path):
    export = tmp_path / 'spamwiki-latest-pages-articles.xml.gz'

    with (export.open(mode='wb') as z,
          gzip.open(z, mode='wt', encoding=ENCODING) as f):
        f.write(EXPORT)

    assert wiki_count.main([str(export), '--stats']) is None

    (out, err) = capsys.readouterr()
    assert out == textwrap.dedent(
        '''
        2

        Vikings         \t4
        Waitress        \t1

        Vikings         \t3
        Waitress        \t2
        ''').lstrip()
    assert not err
