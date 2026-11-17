"""Narrow, reversible fixes for text that bypasses the game's PO catalog."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

import dnfile

DATA_DIR = 'data_GamesByMalcs.Melvor2_windows_x86_64'
GAME_DLL = 'GamesByMalcs.Melvor2.dll'
TIME_DLL = 'SmartFormat.Extensions.Time.dll'


def patch_time(data):
    pe = dnfile.dnPE(data=data, clr_lazy_load=True)
    resource = next((r for r in pe.net.mdtables.ManifestResource if str(r.Name) == 'SmartFormat.Extensions.Time.Resources.en.json'), None)
    if resource is None:
        raise ValueError('不支持此版本的时间格式资源。')
    offset = pe.get_offset_from_rva(pe.net.struct.ResourcesRva) + resource.Offset
    size, = struct.unpack_from('<I', data, offset)
    original = json.loads(data[offset+4:offset+4+size])
    expected = {'week': '周', 'day': '天', 'hour': '小时', 'minute': '分钟',
                'second': '秒', 'millisecond': '毫秒', 'w': '周', 'd': '天',
                'h': '小时', 'm': '分', 's': '秒', 'ms': '毫秒'}
    if set(original) != {'PluralRule', 'Ptxt_lessThan'} | {'Ptxt_' + k for k in expected}:
        raise ValueError('时间资源结构已变化。')
    for key, value in expected.items():
        original['Ptxt_' + key] = ['{0}' + value] * len(original['Ptxt_' + key])
    original['Ptxt_lessThan'] = '不足{0}'
    translated = json.dumps(original, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(translated) > size:
        raise ValueError('中文时间资源超出容量。')
    result = bytearray(data)
    # Pad with JSON whitespace, preserving every assembly/resource offset.
    result[offset+4:offset+4+size] = translated.ljust(size, b' ')
    return bytes(result)


def patch_game(data):
    pe = dnfile.dnPE(data=data, clr_lazy_load=True)
    heap = pe.net.user_strings
    payload = heap.__data__
    wanted = {'[center][b]You were away for {0:numbertime(ms):auto}[/b][/center]':
              '[center][b]你已离线 {0:numbertime(ms):auto}[/b][/center]'}
    wanted.update(json.loads(Path(__file__).with_name('assembly_translations.json').read_text('utf-8')))
    result = bytearray(data)
    found = set()
    pos = 1
    while pos < len(payload):
        first = payload[pos]
        if first < 0x80:
            width, size = 1, first
        elif first < 0xc0:
            width, size = 2, ((first & 0x3f) << 8) | payload[pos+1]
        else:
            width, size = 4, int.from_bytes(payload[pos:pos+4], 'big') & 0x1fffffff
        if not size:
            pos += width
            continue
        if pos + width + size > len(payload) or size % 2 != 1:
            raise ValueError('程序集字符串表损坏。')
        source = payload[pos+width:pos+width+size-1].decode('utf-16-le')
        if source in wanted:
            translated = wanted[source].encode('utf-16-le') + b'\x01'
            if len(translated) > size:
                raise ValueError('程序集译文超出容量。')
            # Keep token offsets fixed; encode new byte count using the original prefix width.
            length = len(translated)
            prefix = bytes([length]) if width == 1 else ((length | (0x8000 if width == 2 else 0xc0000000)).to_bytes(width, 'big'))
            start = heap.file_offset + pos
            result[start:start+width+size] = prefix + translated + bytes(size-length)
            found.add(source)
        pos += width + size
    if found != set(wanted):
        raise ValueError('未找到预期的显示文本模板，停止修改程序集。')
    return bytes(result)


def install(game):
    from patcher import ensure_closed, atomic_json
    ensure_closed()
    root = Path(game) / DATA_DIR
    manifest = root / 'melvor-zh-assemblies.json'
    previous = json.loads(manifest.read_text('utf-8')) if manifest.exists() else {}
    staged, state = {}, {}
    for name, transform in [(GAME_DLL, patch_game), (TIME_DLL, patch_time)]:
        target = root / name
        backup = root / (name + '.before-zh.bak')
        current = target.read_bytes()
        digest = hashlib.sha256(current).hexdigest()
        old = previous.get(name)
        source = current
        if old:
            if digest not in (old['original'], old['patched'], old.get('previous')):
                raise ValueError(f'{name} 已更新或被修改，停止安装。')
            source = backup.read_bytes()
            if hashlib.sha256(source).hexdigest() != old['original']:
                raise ValueError(f'{name} 备份校验失败。')
        elif backup.exists() and backup.read_bytes() != current:
            raise ValueError(f'{name} 已有不同版本备份。')
        patched = transform(source)
        state[name] = {'original': hashlib.sha256(source).hexdigest(), 'patched': hashlib.sha256(patched).hexdigest(), 'previous': digest}
        staged[name] = (source, patched)
    for name, (source, _) in staged.items():
        backup = root / (name + '.before-zh.bak')
        if not backup.exists():
            with backup.open('xb') as f:
                f.write(source)
                f.flush()
                os.fsync(f.fileno())
        if backup.read_bytes() != source:
            raise ValueError(f'{name} 备份校验失败。')
    atomic_json(manifest, state)
    for name, (_, patched) in staged.items():
        ensure_closed()
        current_hash = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if current_hash != state[name]['previous']:
            raise ValueError(f'{name} 在安装期间发生变化，停止写入。')
        atomic_bytes(root / name, patched)
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != state[name]['patched']:
            raise ValueError(f'{name} 安装后校验失败。')
    return '已修复显示提示与中文时间单位。'


def atomic_bytes(path, data):
    fd, temp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restore(game):
    from patcher import ensure_closed
    ensure_closed()
    root = Path(game) / DATA_DIR
    manifest = root / 'melvor-zh-assemblies.json'
    if not manifest.exists():
        return '未安装程序集补丁。'
    state = json.loads(manifest.read_text('utf-8'))
    payloads = {}
    if set(state) != {GAME_DLL, TIME_DLL}:
        raise ValueError('程序集备份记录损坏。')
    for name, hashes in state.items():
        current = (root / name).read_bytes()
        original = (root / (name + '.before-zh.bak')).read_bytes()
        if hashlib.sha256(current).hexdigest() not in (hashes['original'], hashes['patched'], hashes.get('previous')):
            raise ValueError(f'{name} 已发生变化，不能用旧备份覆盖。')
        if hashlib.sha256(original).hexdigest() != hashes['original']:
            raise ValueError(f'{name} 备份校验失败。')
        payloads[name] = original
    for name, data in payloads.items():
        ensure_closed()
        atomic_bytes(root / name, data)
    manifest.unlink()
    return '已恢复原版程序集，备份保留。'
