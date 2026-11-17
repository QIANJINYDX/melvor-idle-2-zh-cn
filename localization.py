"""Repair the shipped localization catalog using assets from the user's own install."""
import hashlib
import json
import mmap
import os
from pathlib import Path
import shutil
import struct
import tempfile

import polib
from format_literals import translate_format_literals

EXTRA = {
    '[color=#FFD16D]Alt (Hold)[/color]: [color=#E9DFC1]Interact[/color]':
        '[color=#FFD16D]按住Alt[/color]：[color=#E9DFC1]交互[/color]',
    'The delay in [seconds] for a Tooltip to appear.': '提示框显示前的延迟时间，单位为秒。',
    'Tooltip position offset in [pixels] from your cursor.': '提示框相对鼠标的位置偏移，单位为像素。',
    'Total Level {0:N0}': '总等级 {0:N0}',
    'Level {0:N0}': '等级 {0:N0}',
    'Level {0:n0}': '等级 {0:n0}',
    '[center][b]You were away for {0:numbertime(ms):auto}[/b][/center]': '[center][b]你已离线 {0:numbertime(ms):auto}[/b][/center]',
    'Language': '语言',
    'Waiting for Player Input...': '等待玩家操作……',
    'Select Language': '选择语言',
    '[color=orchid][Sighting] {0}[/color] {1}': '[color=orchid][目击] {0}[/color] {1}',
    '[color={2}][Observation] {0} {1}[/color]': '[color={2}][观察] {0} {1}[/color]',
    '<<ITEM NAME>>': '<<物品名称>>',
    '<<<MODE NAME>>': '<<<模式名称>>',
    '<<Category>>': '<<类别>>',
    '<Trap Type>': '<陷阱类型>',
    '<RECIPE_NAME>': '<配方名称>',
    '[Agility??] X/X [Agility?]': '[敏捷??] X/X [敏捷?]',
    '[Defeat] X/X [Soulsmith Novice] - [Combat Tab Link]': '[击败] X/X [铸魂学徒] - [战斗页面链接]',
    '[Exclusive Content Agility??] X/X [Exclusive Content Agility?]': '[专属内容：敏捷??] X/X [专属内容：敏捷?]',
    '[Exclusive Content Agility] X/X [Exclusive Content Agility]': '[专属内容：敏捷] X/X [专属内容：敏捷]',
}


def catalog_entries(exe, include_resources=False):
    with open(exe, 'rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        start = 0
        while True:
            base = data.find(b'GDPC', start)
            if base < 0:
                raise ValueError('找不到受支持的资源包。')
            start = base + 4
            if base + 104 > len(data):
                continue
            version, major, minor, patch, flags = struct.unpack_from('<5I', data, base + 4)
            if version not in (3, 4) or major != 4 or flags != 2:
                continue
            file_base, directory = struct.unpack_from('<QQ', data, base + 24)
            pos = base + directory
            if pos + 4 > len(data):
                continue
            count, = struct.unpack_from('<I', data, pos)
            pos += 4
            if count > 1000000:
                raise ValueError('资源数量异常。')
            result = {}
            for _ in range(count):
                length, = struct.unpack_from('<I', data, pos)
                pos += 4
                if length > 16384 or pos + length + 36 > len(data):
                    raise ValueError('资源索引损坏。')
                name = data[pos:pos+length].rstrip(b'\0').decode('utf-8').removeprefix('res://')
                pos += length
                offset, size = struct.unpack_from('<QQ', data, pos)
                digest = data[pos+16:pos+32]
                entry_flags, = struct.unpack_from('<I', data, pos+32)
                record = pos
                pos += 36
                if name in ('Locale/en_GB.po', 'Locale/zh_CN.po') or (include_resources and (name == 'Data/Packages/MelvorBase.json' or name.endswith('.scn'))):
                    begin = base + file_base + offset
                    if entry_flags or size > 50000000 or begin + size > len(data):
                        raise ValueError('不支持此语言资源格式。')
                    payload = data[begin:begin+size]
                    if hashlib.md5(payload).digest() != digest:
                        raise ValueError('语言资源校验失败。')
                    result[name] = {'offset': begin, 'size': size, 'record': record, 'data': payload}
            if not all(name in result for name in ('Locale/en_GB.po', 'Locale/zh_CN.po')):
                raise ValueError('此版本缺少英文或中文 PO 文件。')
            return result


def merge_catalogs(english, chinese):
    from additions import TRANSLATIONS
    stories = json.loads(Path(__file__).with_name('story_translations.json').read_text('utf-8'))
    source = polib.pofile(english.decode('utf-8'), encoding='utf-8')
    zh = polib.pofile(chinese.decode('utf-8'), encoding='utf-8')
    exact = {(x.msgctxt, x.msgid): x for x in zh if not x.obsolete}
    plain = {x.msgid: x for x in zh if not x.obsolete and not x.msgctxt}
    out = polib.POFile()
    # The current game registers only en_GB. Keep that locale to make its existing
    # TranslationServer lookups use Chinese without patching game logic or saves.
    out.metadata = {'Language': 'en_GB', 'Content-Type': 'text/plain; charset=UTF-8',
                    'Plural-Forms': 'nplurals=2; plural=(n != 1);',
                    'X-Melvor-ZH-Patch': '2'}
    missing = []
    contexts = 0
    for x in source:
        if x.obsolete:
            continue
        y = exact.get((x.msgctxt, x.msgid))
        if y is None and x.msgctxt == 'PluralName':
            y = plain.get(x.msgid)
            contexts += 1
        translated = stories.get(hashlib.sha256(x.msgid.encode()).hexdigest()) or TRANSLATIONS.get(x.msgid) or EXTRA.get(x.msgid)
        if translated is None and y:
            translated = y.msgstr or y.msgstr_plural.get(0, '')
        if not translated:
            missing.append(x.msgid)
            continue
        translated = translate_format_literals(translated)
        out.append(polib.POEntry(msgid=x.msgid, msgctxt=x.msgctxt,
                                msgid_plural=x.msgid_plural,
                                msgstr='' if x.msgid_plural else translated,
                                msgstr_plural={0: translated, 1: translated} if x.msgid_plural else {}))
    if missing:
        raise ValueError(f'当前版本有 {len(missing)} 条缺失译文，请更新汉化器。示例：{missing[:3]}')
    known = {(x.msgctxt, x.msgid) for x in out}
    for source_text, translated in EXTRA.items():
        if (None, source_text) not in known:
            out.append(polib.POEntry(msgid=source_text, msgstr=translated))
    return str(out).encode('utf-8'), {'entries': len(out), 'contexts_repaired': contexts}


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def build_replacements(entries):
    from data_catalog import translate_data
    from scene_translations import TRANSLATIONS as scene_translations
    chinese = entries['Locale/zh_CN.po']['data']
    merged, stats = merge_catalogs(entries['Locale/en_GB.po']['data'], chinese)
    replacements = {'Locale/en_GB.po': merged}
    data_key = 'Data/Packages/MelvorBase.json'
    if data_key not in entries:
        raise ValueError('缺少游戏数据资源。')
    translated, data_stats = translate_data(entries[data_key]['data'], chinese)
    if data_stats['missing']:
        raise ValueError(f'此版本存在 {len(data_stats["missing"])} 个未覆盖的数据文本，停止安装。')
    replacements[data_key] = translated
    stats['data_fields'] = data_stats['translated_fields']
    stats['scene_templates'] = 0
    formats = {'Total Level {0:N0}': '总等级 {0:N0}',
               'Level {0:N0}': '等级{0:N0}', 'Level {0:n0}': '等级{0:n0}',
               'Requirements / Recommendations': '要求 / 建议',
               'Select an Area to get started.': '请选择区域开始。',
               'Show Combat Header Button in Legacy Mode': '经典模式显示战斗按钮',
               "Whether to show the Combat Navigation button in the game's header while using Legacy Sidebar":
                   '使用经典侧边栏时，在顶部显示战斗导航按钮。',
               '[color=#FFD16D]Alt (Hold)[/color]: [color=#E9DFC1]Interact[/color]':
                   '[color=#FFD16D]按住Alt[/color]: [color=#E9DFC1]交互[/color]'}
    formats.update(scene_translations)
    for name, entry in entries.items():
        if not name.endswith('.scn'):
            continue
        payload = bytearray(entry['data'])
        changed = False
        local_formats = dict(formats)
        if name.endswith('-tracker_experience_view.scn'):
            local_formats['Level'] = '等级'
        for english, chinese_text in local_formats.items():
            old = english.encode() + b'\0'
            new = chinese_text.encode() + b'\0'
            if len(new) == len(old) + 1:
                # Godot's UTF-8 reader also accepts a fully occupied slot without a NUL.
                new = new[:-1]
            if len(new) > len(old):
                raise ValueError('界面模板超过原资源容量。')
            offset = payload.find(old)
            while offset >= 0:
                declared = struct.unpack_from('<I', payload, offset-4)[0] if offset >= 4 else 0
                if len(old) <= declared <= len(old) + 3 and not any(payload[offset+len(old):offset+declared]):
                    # Godot's length-delimited UTF-8 reader stops at the NUL terminator.
                    # Keep the original slot size so internal resource offsets are unchanged.
                    payload[offset:offset+declared] = new.ljust(declared, b'\0')
                    changed = True
                    stats['scene_templates'] += 1
                offset = payload.find(old, offset + len(old))
        if changed:
            replacements[name] = bytes(payload)
    return replacements, stats


def install(game):
    from patcher import ensure_closed, atomic_json
    ensure_closed()
    exe = Path(game) / 'Melvor2.exe'
    backup = exe.with_name('Melvor2.exe.before-zh.bak')
    manifest = exe.with_name('melvor-zh-patch.json')
    current_hash = sha256(exe)
    source_exe = exe
    baseline_hash = current_hash
    if manifest.exists():
        state = json.loads(manifest.read_text('utf-8'))
        if current_hash in (state['patched_sha256'], state.get('previous_sha256')):
            source_exe = backup
            baseline_hash = state['original_sha256']
            if sha256(backup) != baseline_hash:
                raise ValueError('原版备份校验失败。')
        elif current_hash != state['original_sha256']:
            raise ValueError('游戏文件已更新或被修改，旧补丁不能覆盖。请保留备份并更新汉化器。')
    entries = catalog_entries(source_exe, include_resources=True)
    original = entries['Locale/en_GB.po']
    if b'X-Melvor-ZH-Patch' in original['data']:
        raise ValueError('检测到补丁，但缺少有效安装记录。停止修改以保护备份。')
    replacements, stats = build_replacements(entries)
    current_entries = catalog_entries(exe, include_resources=True) if source_exe == backup else {}
    if source_exe == backup and all(current_entries[k]['data'] == v for k, v in replacements.items()):
        return '汉化补丁已经安装。'
    if any(len(payload) > entries[name]['size'] for name, payload in replacements.items()):
        raise ValueError('汉化资源超出预留容量；不支持此游戏版本。')
    if backup.exists():
        if sha256(backup) != baseline_hash:
            raise ValueError('已有不同版本的备份，停止修改。')
    else:
        with exe.open('rb') as src, backup.open('xb') as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        if sha256(backup) != current_hash:
            raise ValueError('原版备份校验失败。')
    fd, temp = tempfile.mkstemp(prefix='Melvor2-zh-', suffix='.tmp', dir=exe.parent)
    os.close(fd)
    try:
        shutil.copyfile(source_exe, temp)
        with open(temp, 'r+b') as f:
            for name, payload in replacements.items():
                entry = entries[name]
                f.seek(entry['offset'])
                f.write(payload)
                f.write(b'\0' * (entry['size'] - len(payload)))
                f.seek(entry['record'] + 8)
                f.write(struct.pack('<Q', len(payload)))
                f.write(hashlib.md5(payload).digest())
            f.flush()
            os.fsync(f.fileno())
        verified = catalog_entries(temp, include_resources=True)
        if not all(verified[name]['data'] == payload for name, payload in replacements.items()):
            raise ValueError('补丁资源回读校验失败。')
        state = dict(schema=2, original_sha256=baseline_hash, patched_sha256=sha256(temp),
                     previous_sha256=current_hash, **stats)
        # Write the recovery record before the atomic executable replacement.
        atomic_json(manifest, state)
        ensure_closed()
        if sha256(exe) != current_hash:
            raise ValueError('安装期间游戏文件发生变化，已停止。')
        os.replace(temp, exe)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return f'已安装汉化：{stats["entries"]} 条词条，修复 {stats["contexts_repaired"]} 条名称上下文。'


def restore(game):
    from patcher import ensure_closed
    ensure_closed()
    exe = Path(game) / 'Melvor2.exe'
    backup = exe.with_name('Melvor2.exe.before-zh.bak')
    manifest = exe.with_name('melvor-zh-patch.json')
    if not manifest.exists():
        return '未找到游戏补丁记录。'
    state = json.loads(manifest.read_text('utf-8'))
    if sha256(exe) not in (state['original_sha256'], state['patched_sha256'], state.get('previous_sha256')):
        raise ValueError('游戏已更新或被修改，不能用旧备份覆盖。')
    if sha256(backup) != state['original_sha256']:
        raise ValueError('原版备份校验失败。')
    fd, temp = tempfile.mkstemp(prefix='Melvor2-restore-', suffix='.tmp', dir=exe.parent)
    os.close(fd)
    try:
        shutil.copyfile(backup, temp)
        if sha256(temp) != state['original_sha256']:
            raise ValueError('恢复文件校验失败。')
        ensure_closed()
        os.replace(temp, exe)
        manifest.unlink()
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return '已恢复原版游戏；原版备份保留。'
