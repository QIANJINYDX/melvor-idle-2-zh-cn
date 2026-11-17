import struct
import unittest
import font_patch as fp


class FontTests(unittest.TestCase):
    def test_resource_offsets_and_original_data_survive(self):
        # A minimal FontFile with an opaque data property, no game assets.
        names = ['data', 'fallbacks', 'font_weight']
        header = (fp.u32(0, 0, 4, 7, 6) + fp.string('FontFile')
                  + bytes(8) + fp.u32(3) + b'\xff'*8 + bytes(44))
        self.assertEqual(len(header), 97)
        header += fp.u32(len(names)) + b''.join(fp.string(n) for n in names) + fp.u32(0, 1)
        path = fp.string('local://FontFile_test')
        original = fp.u32(0, 31, 8) + b'FONTDATA'
        raw = header + path + struct.pack('<Q', len(header)+len(path)+8)
        raw += fp.string('FontFile') + fp.u32(1) + original + b'RSRC'
        changed = fp.decompress(fp.adapt_font(fp.compress(raw), 700, True))
        self.assertIn(original, changed)
        self.assertIn(fp.string('Microsoft YaHei'), changed)
        self.assertIn(fp.u32(2, 3, 700), changed)
        self.assertTrue(changed.endswith(fp.u32(1, 30, 1, 24, 2, 0) + b'RSRC'))
        self.assertIn(fp.string('FontFile') + fp.u32(2) + original, changed)

    def test_invalid_resource_is_rejected(self):
        for raw in (b'bad', bytes(200)):
            with self.assertRaises(ValueError):
                fp.adapt_font(fp.compress(raw))

    def test_compression_exact_block_and_empty_tail(self):
        for size in (0, 4095, 4096, 4097, 8192):
            raw = b'x' * size
            self.assertEqual(fp.decompress(fp.compress(raw)), raw)

    def test_weight_priorities(self):
        for name, expected in [('ExtraBoldItalic', 800), ('SemiBold', 600),
                               ('ExtraLight', 200), ('Regular', 400), ('Bold', 700)]:
            self.assertEqual(fp.weight_for(name), expected)
