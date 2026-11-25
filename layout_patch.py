"""Reviewed PackedScene node-property references: WORD -> WORD_SMART.

Only redirect autowrap_mode to an existing integer variant (3). Never mutate
the shared variant for integer 2, which also controls unrelated layout flags.
"""
import hashlib
import json
from pathlib import Path
import struct


def apply_layout(entries, replacements):
    manifests = [json.loads(Path(__file__).with_name(filename).read_text('utf-8'))
                 for filename in ('layout_patches.json', 'layout_patches_26886380.json')]
    candidates = {}
    for manifest in manifests:
        for name, spec in manifest.items():
            candidates.setdefault(name, []).append(spec)
    count = 0
    for name, options in candidates.items():
        if name not in entries:
            continue
        original = entries[name]['data']
        digest = hashlib.sha256(original).hexdigest()
        spec = next((item for item in options if item['sha256'] == digest), None)
        if spec is None:
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
