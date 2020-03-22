import gzip
import http.client
import importlib
import io

blame_wiki = importlib.import_module('blame-wiki')

EXPORT = '''\
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/">
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
    with gzip.open(stream, 'wt', encoding=ENCODING) as f:
        f.write(EXPORT)
    stream.seek(0)

    resp = mocker.NonCallableMock(http.client.HTTPResponse,
                                  name='urllib.request.urlopen()',
                                  wraps=stream)
    resp.attach_mock(mocker.Mock(return_value=resp), '__enter__')
    resp.attach_mock(mocker.Mock(), '__exit__')
    resp.attach_mock(mocker.Mock(return_value=info), 'info')

    urlopen = mocker.patch('urllib.request.urlopen', autospec=True,
                           return_value=resp)

    page_title = 'Spam'
    search_string = 'spam'
    export_url = 'https://example.org/wiki/Special:Export'

    assert blame_wiki.main([page_title, search_string,
                            '--export-url', export_url]) is None

    out, _ = capsys.readouterr()
    assert 'spam lovely spam' in out

    urlopen.assert_called_once_with(mocker.ANY)
    req,  = urlopen.call_args.args
    assert req.full_url == export_url
    assert req.data == f'pages={page_title}&wpDownload=1'.encode(ENCODING)
    assert req.headers == {'Accept-encoding': 'gzip'}

    resp.info.assert_called_once_with()

    resp.read.assert_called_with(mocker.ANY)
