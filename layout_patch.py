"""Reviewed PackedScene node-property references: WORD -> WORD_SMART.

Only redirect autowrap_mode to an existing integer variant (3). Never mutate
the shared variant for integer 2, which also controls unrelated layout flags.
"""
import hashlib
import json
from pathlib import Path
import struct


def apply_layout(entries, replacements):
    manifest = json.loads(Path(__file__).with_name('layout_patches.json').read_text('utf-8'))
    count = 0
    for name, spec in manifest.items():
        if name not in entries:
            continue
        original = entries[name]['data']
        if hashlib.sha256(original).hexdigest() != spec['sha256']:
            raise ValueError('换行布局资源已变化，请更新汉化器：' + name)
        payload = bytearray(replacements.get(name, original))
        for edit in spec['edits']:
            offset = edit['offset']
            if struct.unpack_from('<I', payload, offset)[0] != edit['before']:
                raise ValueError('换行属性校验失败，停止修改。')
            struct.pack_into('<I', payload, offset, edit['after'])
            count += 1
        replacements[name] = bytes(payload)
    return count
