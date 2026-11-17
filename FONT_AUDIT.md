# 字体检查

检查安装包中实际字体文件的字形映射，不控制桌面、不启动或关闭游戏。

- 共 21 个字体资源：Noto Sans 默认可变字体与各静态字重，以及 Inter、Montserrat。
- 使用 FontTools 读取字体 cmap，21 个资源在 U+4E00–U+9FFF 常用汉字区间均为 0 个字形。
- 默认主题引用 Default Regular、Bold、BoldItalic、Italic、SemiBold，即 Noto Sans，不是 Noto Sans CJK。
- 场景另有 Inter 和 Montserrat 的直接引用，并混用多个字重。例：200 个场景引用 Default Bold，77 个引用 Default SemiBold，12 个引用 Inter w700，4 个引用 Montserrat。

因此中文显示必须依赖其他字体回退；中英文使用不同字形来源，以及页面之间不同的字体与字重配置，是外观不一致的依据。静态检查不能确定每个控件最终采用了哪款系统回退字体，也不能单凭此结果断言具体是哪一种宋体或黑体。

v2.8 已为 21 个 FontFile 资源加入内置 SystemFont 子资源，明确指定 Microsoft YaHei，并匹配原字体的字重请求（100–900）和斜体属性。原字体二进制、缓存属性和英文字形保持原样。系统按实际安装字重选择最接近的字体，变量字体控件的最终粗细仍需实机观察。

通过 Godot 4.5.1 headless 在本机加载全部 21 个新资源，检查后备字体类型、名称、字重、斜体、汉字字形及中文字符串排版尺寸：零失败。没有启动游戏或抢占桌面。所有压缩后资源均小于原槽位；游戏外部资源偏移保持不变。尚未逐页验证新字体的截断、行高和界面观感。

编码参考 [Godot 官方二进制资源格式](https://github.com/godotengine/godot/blob/master/core/io/resource_format_binary.cpp)。EXE 不捆绑 Godot 或字体文件，只修改用户本机资源。

提取的原始字体只保存在本机 `_work/font-audit/`，未上传仓库。

补充验证：从最终安装的 EXE 回读全部 21 个字体资源，内容与预期逐字节一致；从当前 PO 与显示数据提取 2,661 个不同汉字，逐一检查每个中文后备字体，零缺字。打包 EXE 的安装、恢复和再次安装成功，恢复后游戏 EXE 与两个 DLL 的 SHA-256 均与原版备份一致，重复安装不重复追加字体子资源。
