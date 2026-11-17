import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import polib
import localization
import data_catalog
import patcher


def po(locale, entries):
    catalog = polib.POFile()
    catalog.metadata = {'Language': locale, 'Content-Type': 'text/plain; charset=UTF-8'}
    for entry in entries:
        catalog.append(polib.POEntry(**entry))
    return str(catalog).encode('utf-8')


def fixture():
    english = po('en_GB', [dict(msgid='Options', msgstr='Options'),
                           dict(msgctxt='PluralName', msgid='Shrimp', msgstr='Shrimps')]) + b'\n'*10000
    chinese = po('zh_CN', [dict(msgid='Options', msgstr='选项'),
                           dict(msgid='Shrimp', msgid_plural='Shrimps', msgstr_plural={0:'虾'})])
    resources = {'Locale/en_GB.po': english, 'Locale/zh_CN.po': chinese,
                 'Data/Packages/MelvorBase.json': json.dumps({'Objects':[{'Name':'Options','DisplayName':'Options','Singular':'Shrimp','Plural':'Shrimps'}]}).encode() + b' '*500,
                 'export-tracker_experience_view.scn': b'RSRC'+struct.pack('<I',6)+b'Level\0'}
    body, directory = b'', struct.pack('<I', len(resources))
    for name, value in resources.items():
        encoded = name.encode()
        encoded += b'\0' * (-len(encoded)%4)
        directory += struct.pack('<I',len(encoded)) + encoded + struct.pack('<QQ',len(body),len(value)) + hashlib.md5(value).digest() + struct.pack('<I',0)
        body += value
    header = (b'GDPC'+struct.pack('<5IQQ',4,4,7,2,2,104,104+len(body))).ljust(104,b'\0')
    return header + body + directory


class LocalizationTests(unittest.TestCase):
    def test_concurrent_operation_is_rejected_and_lock_released(self):
        with tempfile.TemporaryDirectory() as folder:
            with patcher.installation_lock(folder):
                with self.assertRaises(RuntimeError):
                    with patcher.installation_lock(folder): pass
            with patcher.installation_lock(folder): pass

    @patch('patcher.ensure_closed')
    def test_interrupted_upgrade_can_restore_original(self, _):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder)/'Melvor2.exe'
            original = fixture()
            exe.write_bytes(original)
            localization.install(folder)
            first = exe.read_bytes()
            real_replace = localization.os.replace
            def fail_exe(src, dst):
                if Path(dst) == exe: raise OSError('simulated interrupted replacement')
                return real_replace(src, dst)
            with patch.dict(localization.EXTRA, {'Options':'设置选项'}):
                with patch('localization.os.replace', side_effect=fail_exe):
                    with self.assertRaises(OSError): localization.install(folder)
            self.assertEqual(exe.read_bytes(), first)
            localization.restore(folder)
            self.assertEqual(exe.read_bytes(), original)

    def test_data_changes_display_fields_only(self):
        source = {'Name':'Options','DisplayName':'Options','Reference':'Options','Quantity':123}
        result, report = data_catalog.translate_data(json.dumps(source).encode(), po('zh_CN',[dict(msgid='Options',msgstr='选项')]))
        self.assertEqual(json.loads(result), {'Name':'Options','DisplayName':'选项','Reference':'Options','Quantity':123})
        self.assertEqual(report['missing'], {})

    def test_missing_translation_is_reported(self):
        _, report = data_catalog.translate_data(b'{"Description":"New unknown text"}', po('zh_CN',[]))
        self.assertIn('New unknown text', report['missing'])

    @patch('patcher.ensure_closed')
    def test_install_repeat_upgrade_restore(self, _):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder)/'Melvor2.exe'
            original = fixture()
            exe.write_bytes(original)
            localization.install(folder)
            first = exe.read_bytes()
            self.assertNotEqual(first, original)
            entries = localization.catalog_entries(exe, True)
            self.assertEqual(json.loads(entries['Data/Packages/MelvorBase.json']['data'])['Objects'][0]['Name'], 'Options')
            self.assertIn('等级'.encode(), entries['export-tracker_experience_view.scn']['data'])
            localization.install(folder)
            self.assertEqual(exe.read_bytes(), first)
            with patch.dict(localization.EXTRA, {'Options':'设置选项'}):
                localization.install(folder)
            self.assertNotEqual(exe.read_bytes(), first)
            localization.restore(folder)
            self.assertEqual(exe.read_bytes(), original)
            self.assertEqual((Path(folder)/'Melvor2.exe.before-zh.bak').read_bytes(), original)

    @patch('patcher.ensure_closed')
    def test_game_update_is_never_overwritten(self, _):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder)/'Melvor2.exe'
            exe.write_bytes(fixture())
            localization.install(folder)
            updated = exe.read_bytes() + b'new game version'
            exe.write_bytes(updated)
            with self.assertRaises(ValueError): localization.install(folder)
            with self.assertRaises(ValueError): localization.restore(folder)
            self.assertEqual(exe.read_bytes(), updated)

    @patch('patcher.ensure_closed')
    def test_corrupt_backup_blocks_restore(self, _):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder)/'Melvor2.exe'
            exe.write_bytes(fixture())
            localization.install(folder)
            installed = exe.read_bytes()
            (Path(folder)/'Melvor2.exe.before-zh.bak').write_bytes(b'bad backup')
            with self.assertRaises(ValueError): localization.restore(folder)
            self.assertEqual(exe.read_bytes(), installed)
