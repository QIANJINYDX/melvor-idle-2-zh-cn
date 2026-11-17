import hashlib
import json
import struct
import unittest
from unittest.mock import patch

from layout_patch import apply_layout


class LayoutTests(unittest.TestCase):
    def test_shared_variant_and_other_bytes_stay_unchanged(self):
        original = b'header' + struct.pack('<III', 2, 9, 9) + b'tail'
        manifest = {'scene.scn': {'sha256': hashlib.sha256(original).hexdigest(),
                                'edits': [{'offset': 10, 'before': 9, 'after': 30}]}}
        entries = {'scene.scn': {'data': original}}
        replacements = {'scene.scn': original.replace(b'tail', b'TAIL')}
        with patch('layout_patch.Path.read_text', return_value=json.dumps(manifest)):
            self.assertEqual(apply_layout(entries, replacements), 1)
        expected = b'header' + struct.pack('<III', 2, 30, 9) + b'TAIL'
        self.assertEqual(replacements['scene.scn'], expected)

    def test_changed_source_is_rejected(self):
        manifest = {'scene.scn': {'sha256': '0'*64, 'edits': []}}
        with patch('layout_patch.Path.read_text', return_value=json.dumps(manifest)):
            with self.assertRaises(ValueError):
                apply_layout({'scene.scn': {'data': b'updated'}}, {})

    def test_changed_property_is_rejected(self):
        original = struct.pack('<I', 9)
        manifest = {'scene.scn': {'sha256': hashlib.sha256(original).hexdigest(),
                                'edits': [{'offset': 0, 'before': 9, 'after': 30}]}}
        with patch('layout_patch.Path.read_text', return_value=json.dumps(manifest)):
            with self.assertRaises(ValueError):
                apply_layout({'scene.scn': {'data': original}}, {'scene.scn': b'abcd'})
