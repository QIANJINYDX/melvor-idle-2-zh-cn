"""Attach an explicit Windows Chinese fallback, retaining original Latin fonts.

Godot binary format 6: one existing FontFile plus a built-in SystemFont.
No Windows or game font binaries are distributed with this program.
"""
import struct
import zstandard


def u32(*values):
    return struct.pack('<' + 'I' * len(values), *values)


def string(value):
    encoded = value.encode('utf-8') + b'\0'
    return u32(len(encoded)) + encoded


def decompress(data):
    if data[:4] != b'RSCC':
        raise ValueError('不支持的字体资源。')
    mode, block, total = struct.unpack_from('<III', data, 4)
    if mode != 2 or block != 4096 or total > 50000000:
        raise ValueError('不支持的字体压缩格式。')
    count = total // block + 1
    sizes = struct.unpack_from('<' + 'I' * count, data, 16)
    pos = 16 + 4 * count
    chunks = []
    for size in sizes:
        chunks.append(zstandard.ZstdDecompressor().decompress(data[pos:pos+size], max_output_size=block))
        pos += size
    raw = b''.join(chunks)
    if len(raw) != total:
        raise ValueError('字体解压校验失败。')
    return raw


def compress(raw):
    block = 4096
    encoder = zstandard.ZstdCompressor(level=9)
    chunks = [encoder.compress(raw[p:p+block]) for p in range(0, len(raw)+1, block)]
    return b'RSCC' + u32(2, block, len(raw)) + u32(*(len(c) for c in chunks)) + b''.join(chunks)


def adapt_font(data, weight=400, italic=False):
    raw = decompress(data)
    # Fixed header for FontFile, format 6, no script class/import metadata.
    if (raw[:12] != u32(0, 0, 4) or raw[16:33] != u32(6) + string('FontFile')
            or raw[33:41] != bytes(8) or raw[41:45] != u32(3)
            or raw[-4:] != b'RSRC'):
        raise ValueError('字体资源结构已变化，停止适配。')
    pos = 97
    count, = struct.unpack_from('<I', raw, pos)
    pos += 4
    strings = []
    for _ in range(count):
        size, = struct.unpack_from('<I', raw, pos)
        pos += 4
        strings.append(raw[pos:pos+size-1].decode('utf-8'))
        pos += size
    if raw[pos:pos+8] != u32(0, 1):
        raise ValueError('字体包含未知子资源，停止适配。')
    pos += 8
    size, = struct.unpack_from('<I', raw, pos)
    old_path = raw[pos:pos+4+size]
    pos += 4+size
    old_offset, = struct.unpack_from('<Q', raw, pos)
    if old_offset != pos+8 or raw[old_offset:old_offset+13] != string('FontFile'):
        raise ValueError('字体资源偏移异常。')
    for name in ('font_names', 'font_italic'):
        if name not in strings:
            strings.append(name)
    idx = strings.index
    fallback = (string('SystemFont') + u32(3)
                + u32(idx('font_names'), 34, 1) + string('Microsoft YaHei')
                + u32(idx('font_weight'), 3, weight)
                + u32(idx('font_italic'), 2, int(italic)))
    main = bytearray(raw[old_offset:-4])
    properties, = struct.unpack_from('<I', main, 13)
    struct.pack_into('<I', main, 13, properties+1)
    main += u32(idx('fallbacks'), 30, 1, 24, 2, 0)
    header = raw[:97] + u32(len(strings)) + b''.join(string(s) for s in strings) + u32(0, 2)
    fallback_path = string('local://SystemFont_Chinese')
    first_offset = len(header) + len(fallback_path) + 8 + len(old_path) + 8
    header += fallback_path + struct.pack('<Q', first_offset)
    header += old_path + struct.pack('<Q', first_offset + len(fallback))
    return compress(header + fallback + main + b'RSRC')


def weight_for(name):
    for token, weight in [('ExtraLight', 200), ('ExtraBold', 800), ('SemiBold', 600),
                          ('Thin', 100), ('Light', 300), ('Medium', 500),
                          ('Black', 900), ('Bold', 700)]:
        if token in name:
            return weight
    return 400


def build_fonts(entries):
    return {name: adapt_font(entry['data'], weight_for(name), 'Italic' in name)
            for name, entry in entries.items() if name.endswith('.fontdata')}
