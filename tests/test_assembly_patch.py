import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import assembly_patch as ap


class AssemblyTransactionTests(unittest.TestCase):
    def make_root(self, folder):
        root = Path(folder)/ap.DATA_DIR
        root.mkdir()
        for name in (ap.GAME_DLL, ap.TIME_DLL): (root/name).write_bytes(b'original')
        return root

    @patch('patcher.ensure_closed')
    @patch('assembly_patch.patch_game', side_effect=lambda x: x + b'game-patch')
    @patch('assembly_patch.patch_time', side_effect=lambda x: x + b'time-patch')
    def test_partial_install_is_recoverable(self, *_):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            real_write = ap.atomic_bytes
            def fail_second(path, data):
                if path.name == ap.TIME_DLL: raise OSError('simulated disk failure')
                real_write(path, data)
            with patch('assembly_patch.atomic_bytes', side_effect=fail_second):
                with self.assertRaises(OSError): ap.install(folder)
            self.assertEqual((root/ap.GAME_DLL).read_bytes(), b'originalgame-patch')
            self.assertEqual((root/ap.TIME_DLL).read_bytes(), b'original')
            ap.restore(folder)
            for name in (ap.GAME_DLL, ap.TIME_DLL): self.assertEqual((root/name).read_bytes(), b'original')

    @patch('patcher.ensure_closed')
    @patch('assembly_patch.patch_game', side_effect=lambda x: x + b'game-patch')
    @patch('assembly_patch.patch_time', side_effect=lambda x: x + b'time-patch')
    def test_repeat_install_and_update_guard(self, *_):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            ap.install(folder)
            ap.install(folder)
            self.assertEqual((root/ap.GAME_DLL).read_bytes(), b'originalgame-patch')
            (root/ap.TIME_DLL).write_bytes(b'new-version')
            with self.assertRaises(ValueError): ap.restore(folder)
            self.assertEqual((root/ap.GAME_DLL).read_bytes(), b'originalgame-patch')
