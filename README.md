# Melvor Idle 2 简体中文启用器

Windows 一键启用游戏内置简体中文，附原语言备份与恢复功能。非官方工具，不是全新翻译补丁，也不承诺完整汉化。

## 使用

1. 从本仓库 Releases 下载 `Melvor2-Chinese-Enabler.exe`。无需安装 Python。
2. 正常退出游戏，运行工具。自动寻找 Steam 游戏目录，也可以手动浏览到含 `Melvor2.exe` 的目录。
3. 点击“一键汉化”，重新启动游戏。首次启动仍可能需要完成游戏自己的初始设置；如出现语言选择页，选择简体中文。
4. 需要撤销时，退出游戏并点击“恢复原语言”。

工具处理当前 Windows 用户目录下的所有本地游戏账号。尚未生成设置文件时，请先启动游戏进入初始设置并退出。请勿同时运行多个工具实例。

## 工作方式

- 读取游戏 EXE 内的 Godot PCK v3/v4 索引，确认 `Locale/zh_CN.po` 存在并通过 MD5 校验。
- 将 `%APPDATA%/Games By Malcs/Melvor Idle 2/**/userSettings.json` 的 `Language` 设为 `zh_CN`。
- 原语言保存在同目录的 `userSettings.json.melvor-zh-backup.json`，重复启用不覆盖首次备份。
- 恢复时只恢复原语言字段，保留后来修改的音量等其他设置。成功恢复后移除该备份。
- 采用临时文件及原子替换写入设置；检测游戏运行时拒绝修改。
- 不修改游戏 EXE、不修改角色存档、不上传任何用户数据、不捆绑游戏资产。

## 已检查版本与限制

本地验证版本为 **0.11.6 alpha.1 / Godot 4.7.2**。内置中文 PO 有 10,407 个词条，其中 10,406 条标记为已翻译，1 条为 fuzzy。英文和中文词条集合并不完全对应，英文中有 1,872 个 `(msgctxt, msgid)` 组合未出现在中文文件中；这不是实际界面的缺译率，部分可能是上下文或词条更新差异。新增内容、模组或未本地化文本仍可能显示英文。

其他版本须包含可识别的中文 PO 和相同的用户设置布局。工具不会为缺少中文资源的版本自动下载翻译。EXE 未做代码签名。

PCK 格式实现参考 [Godot 官方读取器](https://github.com/godotengine/godot/blob/master/core/io/file_access_pack.cpp)。

## 从源码构建

Windows + Python 3.10 或更新版本：

```powershell
.\build.ps1
```

输出：`dist/Melvor2-Chinese-Enabler.exe`。

```powershell
python -m unittest discover -s tests -v
python patcher.py --action inspect --game "D:\Steam\steamapps\common\Melvor Idle 2"
```

打包后的 EXE 同样支持 `--action inspect|apply|restore` 和 `--report <JSON路径>`。窗口程序没有控制台输出，自动化时请使用 `--report` 并等待进程退出。

本仓库仅包含原创工具代码及说明。游戏、内置翻译及商标归各自权利人所有。
