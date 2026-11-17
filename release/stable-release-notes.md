# 都市回响 v0.8.0 · Windows 正式版

首个正式版，基于用户已验收的 beta.6。音乐由播放器负责，都市回响提供桌面歌词、逐字动画、字体效果、双语及主题设置。

请按播放器选择完整 ZIP，解压后保留 `_internal`，无需安装 Python：

- [网易云音乐版](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/releases/download/v0.8.0/dancing-lyrics-0.8.0-netease-windows-x64.zip)：首次运行“安装网易云联动.bat”，之后从网易云播放栏打开。
- [QQ 音乐版](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/releases/download/v0.8.0/dancing-lyrics-0.8.0-qqmusic-windows-x64.zip)：开启 QQ 音乐系统媒体控制并播放歌曲，运行“启动QQ音乐联动.bat”。
- [酷狗音乐版](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/releases/download/v0.8.0/dancing-lyrics-0.8.0-kugou-windows-x64.zip)：开启酷狗桌面歌词，运行“启动酷狗联动.bat”。

“歌词效果 → 律动与同步”开启“新句出现后保留旧句”后，可将“同时显示上限”选择为 **2／3／4 组**，默认 4 组。达到上限前最旧组完成退场，双语算一组；显示时长与组数自动保存，切换预设不会重置。实际数量仍受显示时长和可用空间影响。

支持“暂停播放时隐藏歌词”，默认关闭；开启后暂停隐藏，继续播放按当前进度显示。保留白芯发光、卡门的声音、自定义渐变、乱码退场、字体导入、多屏选择、纯音乐隐藏及三种主题。

已有实测范围：Windows 11 x64；网易云 3.1.40.205461／3.1.41.205529 x64 与 BetterNCM 1.3.4；QQ 音乐 22.52／22.75；酷狗 20.1.51.27967。QQ 首次无缓存取词仍可能较慢；酷狗未知结构可能回退为需要展开窗口的界面模式。正式版不扩大已验证客户端范围，Mac 维持原有实验版。

更新前退出歌词程序，完整替换 EXE 与 `_internal`，保留 `.state` 中的设置、字体和预设；网易云换目录后需退出客户端并重新安装联动以更新启动路径。酷狗个人数据位于 `%LOCALAPPDATA%\DancingLyrics-Kugou\.state`，升级保留。旧发行版和附件继续保留，可用于回退。

已验收的候选版通过 556 项自动测试、三档缩放和实际 Windows 启动入口检查；正式打包后的实际结果见仓库变更日志与验证记录。演示时间的自动检查与真实客户端播放回归分别记录，不将用户发布授权扩大为未逐项记录的手动测试结论。

正式成品检查：558 项运行时自动测试通过；三包共 171 项原生组数检查、两份演示 BAT 静音各 75 字段、QQ／酷狗入口共 10 项通过，暖绘制 P95 最大 12.059ms。六个公开附件的大小、SHA-256 和匿名下载已核对，校验文本已实际下载比对。最终交付共 560 项自动测试通过。

[完整正式版验证记录](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/blob/main/docs/research/stable-release-20261117.json)
