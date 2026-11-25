from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import assembly_patch as asm
from localization import sha256
from update_migration import prepare_update


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / asm.DATA_DIR).mkdir()
        self.files = ['Melvor2.exe', asm.DATA_DIR + '/' + asm.GAME_DLL,
                      asm.DATA_DIR + '/' + asm.TIME_DLL]
        for name in self.files:
            (self.root / name).write_bytes(('new:' + name).encode())
            (self.root / (name + '.before-zh.bak')).write_bytes(('old:' + name).encode())
        self.record = self.root / 'melvor-zh-patch.json'
        self.record.write_text(json.dumps({'original_sha256': 'old'}))
        self.profile = {'files': {n: sha256(self.root / n) for n in self.files}}
        self.archive = self.root / 'melvor-zh-archives' / self.profile['files']['Melvor2.exe'][:16]
        stack = self.enterContext(ExitStack())
        stack.enter_context(patch('update_migration.supported_profiles', return_value=[self.profile]))
        stack.enter_context(patch('patcher.ensure_closed'))
        stack.enter_context(patch('localization.catalog_entries', return_value={}))
        stack.enter_context(patch('localization.build_replacements', return_value=({}, {})))
        stack.enter_context(patch('font_patch.build_fonts', return_value={}))
        stack.enter_context(patch('assembly_patch.patch_game', side_effect=lambda x: x))

    def test_archives_old_backups_without_changing_new_game(self):
        self.assertIn(str(self.archive), prepare_update(self.root))
        for name in self.files:
            self.assertEqual(sha256(self.root / name), self.profile['files'][name])
            self.assertFalse((self.root / (name + '.before-zh.bak')).exists())
            self.assertEqual((self.archive / (name + '.before-zh.bak')).read_bytes(), ('old:' + name).encode())
        self.assertTrue((self.archive / self.record.name).exists())
        self.assertEqual(prepare_update(self.root), '')

    def test_modified_component_blocks_before_archive(self):
        (self.root / self.files[1]).write_bytes(b'other mod')
        with self.assertRaises(ValueError):
            prepare_update(self.root)
        self.assertTrue(self.record.exists())
        self.assertFalse(self.archive.exists())

    def test_copy_failure_preserves_sources_and_can_retry(self):
        with patch('update_migration.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                prepare_update(self.root)
        self.assertTrue(self.record.exists())
        self.assertTrue((self.root / 'Melvor2.exe.before-zh.bak').exists())
        self.assertFalse((self.archive / 'Melvor2.exe.before-zh.bak').exists())
        prepare_update(self.root)

    def test_conflicting_archive_never_overwritten(self):
        self.archive.mkdir(parents=True)
        existing = self.archive / 'Melvor2.exe.before-zh.bak'
        existing.write_bytes(b'keep me')
        with self.assertRaises(ValueError):
            prepare_update(self.root)
        self.assertEqual(existing.read_bytes(), b'keep me')
        self.assertTrue(self.record.exists())
