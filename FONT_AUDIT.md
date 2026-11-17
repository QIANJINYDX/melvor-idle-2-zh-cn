# 字体检查

检查安装包中实际字体文件的字形映射，不控制桌面、不启动或关闭游戏。

- 共 21 个字体资源：Noto Sans 默认可变字体与各静态字重，以及 Inter、Montserrat。
- 使用 FontTools 读取字体 cmap，21 个资源在 U+4E00–U+9FFF 常用汉字区间均为 0 个字形。
- 默认主题引用 Default Regular、Bold、BoldItalic、Italic、SemiBold，即 Noto Sans，不是 Noto Sans CJK。
- 场景另有 Inter 和 Montserrat 的直接引用，并混用多个字重。例：200 个场景引用 Default Bold，77 个引用 Default SemiBold，12 个引用 Inter w700，4 个引用 Montserrat。

因此中文显示必须依赖其他字体回退；中英文使用不同字形来源，以及页面之间不同的字体与字重配置，是外观不一致的依据。静态检查不能确定每个控件最终采用了哪款系统回退字体，也不能单凭此结果断言具体是哪一种宋体或黑体。

此次仅检查，未替换游戏字体。若统一中文字体，应选择覆盖简体中文的字体家族，分别配置正文、标题与粗体，而不是让所有界面强制使用同一字重。需要额外处理资源容量、字体许可与实际排版验证。

提取的原始字体只保存在本机 `_work/font-audit/`，未上传仓库。
