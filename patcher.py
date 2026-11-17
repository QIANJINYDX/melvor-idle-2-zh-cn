"""Install a reversible Chinese localization repair for Melvor Idle 2."""
import argparse
import ctypes
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from contextlib import contextmanager

VERSION = '2.7.0'
DEFAULT_GAME = Path(r'D:\Steam\steamapps\common\Melvor Idle 2')
USER_ROOT = Path(os.environ.get('APPDATA', str(Path.home()))) / 'Games By Malcs/Melvor Idle 2'
BACKUP_SUFFIX = '.melvor-zh-backup.json'


def atomic_json(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('设置文件格式不正确：' + str(path))
    return value


def inspect_game(folder):
    """Read only the PCK directory and verify the bundled Chinese PO digest."""
    exe = Path(folder) / 'Melvor2.exe'
    with exe.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        start = 0
        while True:
            base = data.find(b'GDPC', start)
            if base < 0:
                raise ValueError('未找到支持的 Godot PCK 资源包（支持 v3/v4）。')
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
                raise ValueError('资源索引数量异常。')
            for _ in range(count):
                length, = struct.unpack_from('<I', data, pos)
                pos += 4
                if length > 16384 or pos + length + 36 > len(data):
                    raise ValueError('资源索引损坏。')
                name = data[pos:pos+length].rstrip(b'\0').decode('utf-8')
                pos += length
                offset, size = struct.unpack_from('<QQ', data, pos)
                digest = data[pos+16:pos+32]
                entry_flags, = struct.unpack_from('<I', data, pos+32)
                pos += 36
                if name.removeprefix('res://') == 'Locale/zh_CN.po':
                    begin = base + file_base + offset
                    if entry_flags or size > 50000000 or begin + size > len(data):
                        raise ValueError('不支持此语言资源格式。')
                    po = data[begin:begin+size]
                    if hashlib.md5(po).digest() != digest:
                        raise ValueError('中文语言资源校验失败。')
                    if b'Language: zh_CN' not in po:
                        raise ValueError('资源语言标记不正确。')
                    return {'engine': f'{major}.{minor}.{patch}', 'locale': 'zh_CN', 'bytes': size}
            raise ValueError('此游戏版本没有内置简体中文语言资源。')


def settings_files(root=USER_ROOT):
    root = Path(root).resolve()
    files = []
    if root.exists():
        for p in root.rglob('userSettings.json'):
            if p.resolve().is_relative_to(root) and p.is_file():
                files.append(p)
    return sorted(files)


def ensure_closed():
    if os.name == 'nt':
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Melvor2.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
        if b'melvor2.exe' in result.stdout.lower():
            raise RuntimeError('请先正常退出 Melvor Idle 2，再修改语言设置。')


def set_language(path, restore=False):
    path = Path(path)
    data = read_json(path)
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if restore:
        if not backup.exists():
            return '无备份，跳过'
        original = read_json(backup)
        if original.get('schema') != 1 or not isinstance(original.get('had_language'), bool):
            raise ValueError('备份格式错误。')
        if original['had_language']:
            data['Language'] = original['language']
        else:
            data.pop('Language', None)
        atomic_json(path, data)
        backup.unlink()
        return '已恢复原语言'
    if data.get('Language') == 'zh_CN':
        return '已是简体中文'
    if not backup.exists():
        atomic_json(backup, {'schema': 1, 'had_language': 'Language' in data,
                             'language': data.get('Language')})
    else:
        original = read_json(backup)
        if original.get('schema') != 1:
            raise ValueError('已有备份格式不正确，停止修改。')
    data['Language'] = 'zh_CN'
    atomic_json(path, data)
    return '已启用简体中文（原语言已备份）'


@contextmanager
def installation_lock(game):
    """OS lock is released after a crash; the harmless lock file may remain."""
    path = Path(game) / '.melvor-zh.lock'
    with path.open('a+b') as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('另一个汉化器正在处理此游戏，请等待它完成。') from exc
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def operate(game, restore=False, root=USER_ROOT):
    with installation_lock(game):
        return _operate_locked(game, restore, root)


def _operate_locked(game, restore=False, root=USER_ROOT):
    import localization
    import assembly_patch
    ensure_closed()
    if restore:
        results = [assembly_patch.restore(game), localization.restore(game)]
        for path in settings_files(root):
            if path.with_name(path.name + BACKUP_SUFFIX).exists():
                set_language(path, True)
        return '\n'.join(results)
    inspect_game(game)
    return '\n'.join([localization.install(game), assembly_patch.install(game)])


def find_game():
    candidates = [DEFAULT_GAME, Path.cwd(), Path(__file__).resolve().parent]
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
                steam = Path(winreg.QueryValueEx(k, 'SteamPath')[0])
            libraries = [steam]
            vdf = steam / 'steamapps/libraryfolders.vdf'
            if vdf.exists():
                libraries.extend(Path(x.replace('\\\\', '\\')) for x in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text()))
            candidates += [x / 'steamapps/common/Melvor Idle 2' for x in libraries]
        except OSError:
            pass
    return next((p for p in candidates if (p / 'Melvor2.exe').is_file()), DEFAULT_GAME)


def gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    if os.name == 'nt':
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    root.title('Melvor Idle 2 汉化补丁 v' + VERSION)
    root.geometry('760x440')
    root.minsize(700, 420)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Melvor Idle 2 · 一键汉化', font=('Microsoft YaHei UI', 21, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='修复语言加载与漏译 · 自动备份游戏原文件 · 一键恢复', padding=(0, 8)).pack(anchor='w')
    row = ttk.Frame(frame)
    row.pack(fill='x', pady=12)
    folder = tk.StringVar(value=str(find_game()))
    ttk.Entry(row, textvariable=folder).pack(side='left', fill='x', expand=True)
    def browse():
        selected = filedialog.askdirectory(title='选择包含 Melvor2.exe 的游戏文件夹')
        if selected:
            folder.set(selected)
    ttk.Button(row, text='浏览…', command=browse).pack(side='right', padx=(8, 0))
    status = tk.StringVar(value='请先退出游戏，然后点击“一键汉化”。\n首次安装需要约 650 MB 空间保存原版备份。')
    def run(restore=False):
        try:
            status.set('正在校验并处理游戏文件，请稍候……')
            root.update_idletasks()
            status.set(operate(folder.get(), restore) + '\n通过 Steam 重新启动游戏后生效。')
        except Exception as exc:
            status.set(str(exc))
            messagebox.showerror('操作未完成', str(exc))
    buttons = ttk.Frame(frame)
    buttons.pack(fill='x', pady=12)
    ttk.Button(buttons, text='一键汉化', command=run).pack(side='left', ipadx=24, ipady=10)
    ttk.Button(buttons, text='恢复原版', command=lambda: run(True)).pack(side='left', padx=12, ipadx=16, ipady=10)
    ttk.Label(frame, textvariable=status, wraplength=680).pack(anchor='w', pady=12)
    ttk.Label(frame, text='非官方补丁。修复内置中文并补译遗漏文本，不修改角色存档。\n游戏更新后需重新检查兼容性；遇到未知版本或异常备份会停止安装。',
              foreground='#666666', wraplength=680).pack(side='bottom', anchor='w')
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=find_game())
    parser.add_argument('--action', choices=['inspect', 'apply', 'restore', 'self-test'])
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.action:
        gui()
        return
    try:
        if args.action == 'self-test':
            import tkinter as tk
            from tkinter import ttk
            window = tk.Tk()
            window.withdraw()
            ttk.Button(window, text='一键汉化').pack()
            window.update()
            window.destroy()
            result = 'Tk GUI runtime OK'
        else:
            result = inspect_game(args.game) if args.action == 'inspect' else operate(args.game, args.action == 'restore')
        report = {'ok': True, 'result': result}
    except Exception as exc:
        report = {'ok': False, 'error': str(exc)}
    if args.report:
        atomic_json(args.report, report)
    if __import__('sys').stdout is not None:
        print(json.dumps(report, ensure_ascii=False))
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
