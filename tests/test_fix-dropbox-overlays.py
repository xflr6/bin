import importlib
import sys
import types

import pytest

fix_dropbox_overlays = importlib.import_module('fix-dropbox-overlays')

KEYS = ['   DropboxExt01', '   DropboxExt02', '   DropboxExt03',
        '   DropboxExt04', '   DropboxExt05', '   DropboxExt06',
        '   DropboxExt07', '   DropboxExt08', '   DropboxExt09',
        '   DropboxExt10',
        '  Tortoise1Normal', '  Tortoise2Modified', '  Tortoise3Conflict',
        '  Tortoise4Locked', '  Tortoise5ReadOnly', '  Tortoise6Deleted',
        '  Tortoise7Added', '  Tortoise8Ignored', '  Tortoise9Unversioned',
        ' DropboxExt01', ' DropboxExt02', ' DropboxExt03',
        ' DropboxExt04', ' DropboxExt05', ' DropboxExt06',
        ' DropboxExt07', ' DropboxExt08', ' DropboxExt09',
        'EnhancedStorageShell', 'SharingPrivate']


@pytest.fixture
def winreg(mocker):
    name = '_winreg' if sys.version_info.major == 2 else 'winreg'

    module = mocker.NonCallableMock(name=name,
                                    HKEY_LOCAL_MACHINE=mocker.sentinel.HKEY_LOCAL_MACHINE,
                                    REG_SZ = mocker.sentinel.REG_SZ)

    module.attach_mock(mocker.MagicMock(), 'ConnectRegistry')
    module.attach_mock(mocker.MagicMock(), 'OpenKey')

    module.attach_mock(mocker.Mock(return_value=(len(KEYS), None, None)),
                       'QueryInfoKey')
    module.attach_mock(mocker.Mock(side_effect=iter(KEYS)),
                       'EnumKey')

    module.attach_mock(mocker.Mock(), 'DeleteKey')
    module.attach_mock(mocker.Mock(), 'QueryValue')
    module.attach_mock(mocker.Mock(), 'CreateKey')
    module.attach_mock(mocker.Mock(), 'SetValue')

    sys.modules[name] = module
    yield module
    del sys.modules[name]


def test_fix_dropox_overlays(mocker, winreg):
    conn = winreg.ConnectRegistry.return_value.__enter__.return_value
    key = winreg.OpenKey.return_value.__enter__.return_value

    assert fix_dropbox_overlays.main([]) is None

    connect = mocker.call.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

    open_key = mocker.call.OpenKey(conn,
                                   r'SOFTWARE\Microsoft\Windows\CurrentVersion'
                                   r'\Explorer\ShellIconOverlayIdentifiers')

    query_info = mocker.call.QueryInfoKey(key)

    enum_keys = [mocker.call.EnumKey(key, i) for i in range(len(KEYS))]

    delete_keys = [mocker.call.DeleteKey(key, k)
                   for k in (' DropboxExt01', ' DropboxExt02', ' DropboxExt03',
                             ' DropboxExt04', ' DropboxExt05', ' DropboxExt06',
                             ' DropboxExt07', ' DropboxExt08', ' DropboxExt09')]

    set_values = [c
                  for k in ('   DropboxExt01', '   DropboxExt02', '   DropboxExt03',
                            '   DropboxExt04', '   DropboxExt05', '   DropboxExt06',
                            '   DropboxExt07', '   DropboxExt08', '   DropboxExt09',
                            '   DropboxExt10')
                  for c in (mocker.call.QueryValue(key, k),
                            mocker.call.DeleteKey(key, k),
                            mocker.call.CreateKey(key, k[2:]),
                            mocker.call.SetValue(key, k[2:], winreg.REG_SZ,
                                                 winreg.QueryValue.return_value))]

    winreg.assert_has_calls([connect,
                             connect.__enter__(),
                             open_key,
                             open_key.__enter__(),
                             query_info]
                            + enum_keys
                            + delete_keys
                            + set_values +
                            [open_key.__exit__(None, None, None),
                               connect.__exit__(None, None, None)])


def test_fix_dropox_overlays_dry(mocker, winreg):
    conn = winreg.ConnectRegistry.return_value.__enter__.return_value
    key = winreg.OpenKey.return_value.__enter__.return_value

    assert fix_dropbox_overlays.main(['--dry-run']) is None

    connect = mocker.call.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

    open_key = mocker.call.OpenKey(conn,
                                   r'SOFTWARE\Microsoft\Windows\CurrentVersion'
                                   r'\Explorer\ShellIconOverlayIdentifiers')

    query_info = mocker.call.QueryInfoKey(key)

    enum_keys = [mocker.call.EnumKey(key, i) for i in range(len(KEYS))]

    winreg.assert_has_calls([connect,
                             connect.__enter__(),
                             open_key,
                             open_key.__enter__(),
                             query_info]
                            + enum_keys +
                            [open_key.__exit__(None, None, None),
                             connect.__exit__(None, None, None)])
