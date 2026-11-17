import json
from pathlib import Path
import tempfile
import unittest
import struct
import hashlib
import patcher


class SettingsTests(unittest.TestCase):
    def test_pack_verifies_translation_hash(self):
        with tempfile.TemporaryDirectory() as d:
            po = b'Language: zh_CN'
            name = b'Locale/zh_CN.po\0\0'
            header = b'GDPC' + struct.pack('<5IQQ', 4, 4, 7, 2, 2, 104, 104 + len(po))
            header = header.ljust(104, b'\0')
            index = struct.pack('<II', 1, len(name)) + name + struct.pack('<QQ', 0, len(po)) + hashlib.md5(po).digest() + struct.pack('<I', 0)
            exe = Path(d) / 'Melvor2.exe'
            exe.write_bytes(header + po + index)
            self.assertEqual(patcher.inspect_game(d)['locale'], 'zh_CN')
            exe.write_bytes(header + b'X' + po[1:] + index)
            with self.assertRaises(ValueError):
                patcher.inspect_game(d)

    def test_apply_repeat_restore_preserves_other_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'userSettings.json'
            patcher.atomic_json(p, {'Language': 'en_GB', 'Audio': 0.5})
            patcher.set_language(p)
            patcher.set_language(p)
            obj = patcher.read_json(p)
            self.assertEqual(obj['Language'], 'zh_CN')
            obj['Audio'] = 0.8
            patcher.atomic_json(p, obj)
            patcher.set_language(p, True)
            self.assertEqual(patcher.read_json(p), {'Language': 'en_GB', 'Audio': 0.8})

    def test_missing_language_restored_as_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'userSettings.json'
            patcher.atomic_json(p, {'FirstTimeSetupComplete': False})
            patcher.set_language(p)
            patcher.set_language(p, True)
            self.assertEqual(patcher.read_json(p), {'FirstTimeSetupComplete': False})

    def test_bad_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'userSettings.json'
            p.write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                patcher.set_language(p)
            self.assertEqual(p.read_text(), '{broken')

    def test_already_chinese_needs_no_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'userSettings.json'
            patcher.atomic_json(p, {'Language': 'zh_CN'})
            patcher.set_language(p)
            self.assertFalse(p.with_name(p.name + patcher.BACKUP_SUFFIX).exists())


if __name__ == '__main__':
    unittest.main()
