"""Archive obsolete localization backups after an explicitly verified game update."""
import json
import os
from pathlib import Path
import shutil
import tempfile


def supported_profiles():
    return json.loads(Path(__file__).with_name('supported_builds.json').read_text('utf-8'))


def prepare_update(game):
    from localization import sha256, catalog_entries, build_replacements
    from font_patch import build_fonts
    from assembly_patch import DATA_DIR, GAME_DLL, TIME_DLL, patch_game, patch_time
    from patcher import ensure_closed
    root = Path(game).resolve()
    exe = root / 'Melvor2.exe'
    digest = sha256(exe)
    profiles = supported_profiles()
    profile = next((p for p in profiles if p['files']['Melvor2.exe'] == digest), None)
    if profile is None:
        return ''  # Existing installers retain their strict unknown-update guard.
    pairs = [(exe, root / 'Melvor2.exe.before-zh.bak')]
    pairs += [(root / DATA_DIR / n, root / DATA_DIR / (n + '.before-zh.bak'))
              for n in (GAME_DLL, TIME_DLL)]
    records = [root / 'melvor-zh-patch.json', root / DATA_DIR / 'melvor-zh-assemblies.json']
    obsolete = any(backup.exists() and sha256(backup) != sha256(target) for target, backup in pairs)
    if records[0].exists():
        old = json.loads(records[0].read_text('utf-8'))
        obsolete |= old.get('original_sha256') != digest
    if records[1].exists():
        old = json.loads(records[1].read_text('utf-8'))
        obsolete |= any(old.get(n, {}).get('original') != sha256(root / DATA_DIR / n)
                        for n in (GAME_DLL, TIME_DLL))
    if not obsolete:
        return ''
    ensure_closed()
    for name, expected in profile['files'].items():
        if sha256(root / name) != expected:
            raise ValueError('新版游戏组件未匹配验证记录，不能迁移旧备份：' + name)
    # Complete compatibility/capacity checks before touching any backup records.
    entries = catalog_entries(exe, include_resources=True)
    replacements, _ = build_replacements(entries)
    replacements.update(build_fonts(entries))
    if any(len(data) > entries[name]['size'] for name, data in replacements.items()):
        raise ValueError('新版汉化资源容量不足，旧备份保持原样。')
    patch_game((root / DATA_DIR / GAME_DLL).read_bytes())
    patch_time((root / DATA_DIR / TIME_DLL).read_bytes())
    archive = root / 'melvor-zh-archives' / digest[:16]
    sources = [backup for _, backup in pairs if backup.exists()] + [p for p in records if p.exists()]
    checks = {}
    for source in sources:
        if not source.resolve().is_relative_to(root):
            raise ValueError('备份路径不在游戏目录内。')
        destination = archive / source.relative_to(root)
        if not destination.resolve().is_relative_to(root):
            raise ValueError('归档路径不在游戏目录内。')
        checks[source] = sha256(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            # A failed copy never leaves a partial file at the final archive path.
            fd, temp = tempfile.mkstemp(prefix='archive-', dir=destination.parent)
            try:
                with source.open('rb') as src, os.fdopen(fd, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())
                if sha256(temp) != checks[source]:
                    raise ValueError('旧备份归档校验失败，未删除原备份。')
                os.replace(temp, destination)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        if sha256(destination) != checks[source]:
            raise ValueError('旧备份归档校验失败，未删除原备份。')
    ensure_closed()
    for name, expected in profile['files'].items():
        if sha256(root / name) != expected:
            raise ValueError('归档期间游戏文件发生变化，停止安装。')
    for source, expected in checks.items():
        if sha256(source) != expected:
            raise ValueError('归档期间备份文件发生变化，停止安装。')
    # Only remove verified duplicate backup files; current game files stay intact.
    for source in sources:
        source.unlink()
    return '旧版汉化备份已校验并归档：' + str(archive)
