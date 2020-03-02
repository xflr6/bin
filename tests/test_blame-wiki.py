import io
import gzip
import importlib

blame_wiki = importlib.import_module('blame-wiki')

EXPORT = '''\
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.10/ http://www.mediawiki.org/xml/export-0.10.xsd" version="0.10" xml:lang="en">
  <siteinfo>
    <sitename>Wikispam</sitename>
    <dbname>spamwiki</dbname>
    <base>https://example.org/wiki/Spam</base>
  </siteinfo>
  <page>
    <title>Spam</title>
    <ns>0</ns>
    <id>1</id>
    <revision>
      <text>spam lovely spam</text>
    </revision>
  </page>
</mediawiki>
'''

ENCODING = 'utf-8'


def test_blame_wiki(capsys, mocker):
    info = {'content-type':  f'application/xml; charset={ENCODING}',
            'content-disposition': 'attachment;filename=spam.xml',
            'content-encoding': 'gzip'}

    stream = io.BytesIO()
    with gzip.open(stream, 'wb') as f:
        f.write(EXPORT.encode(ENCODING))
    stream.seek(0)

    resp = mocker.Mock(wraps=stream)
    resp.info = mocker.Mock(name='info', return_value=info)
    resp.__enter__ = mocker.Mock(return_value=resp)
    resp.__exit__ = mocker.Mock()

    urlopen = mocker.patch('urllib.request.urlopen',
                           return_value=resp,
                           autospec=True)

    page_title = 'Spam'
    search_string = 'spam'
    export_url = 'https://example.org/wiki/Special:Export'

    assert blame_wiki.main([page_title, search_string,
                            '--export-url', export_url]) is None

    urlopen.assert_called_once_with(mocker.ANY)
    req,  = urlopen.call_args.args
    assert req.full_url == export_url
    assert req.headers == {'Accept-encoding': 'gzip'}

    out, _ = capsys.readouterr()
    assert 'spam lovely spam' in out
