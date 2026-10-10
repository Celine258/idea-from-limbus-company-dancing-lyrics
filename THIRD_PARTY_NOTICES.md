# 第三方组件与许可

本项目自有源码采用 [MIT 许可](LICENSE)。该许可不覆盖第三方组件或原游戏的名称、角色与素材。
特殊主题中的钟头和机械图纸为本项目绘制的风格参考图形，不代表 Project Moon 官方产品或合作。
演示音乐和示例文本由本项目生成，不包含网易云歌曲音频或用户导入字体。

macOS 初始适配来源于 [qingyin-alice-zhong/mac-version](https://github.com/qingyin-alice-zhong/idea-from-limbus-company-dancing-lyrics/tree/mac-version)，采用 MIT 许可；作者贡献与固定参考提交见 [macOS 说明](MACOS.md)。
macOS 使用的 [nowplaying-cli](https://github.com/kirtan-shah/nowplaying-cli) 是通过 Homebrew 单独安装的 GPLv3 外部程序，本仓库及 Windows ZIP 不附带该二进制。
歌词接口沿用原 mac 分支的网易云在线接口，不分发歌曲音频或缓存的个人歌词。

| 组件 | 用途 | 许可与来源 |
| --- | --- | --- |
| Python 3.11.8 | 成品内置运行时 | PSF，https://www.python.org/downloads/release/python-3118/ |
| PySide6 / shiboken6 / Qt 6.8.3 | 界面、播放、文字绘制；保持独立 DLL 动态链接 | LGPLv3 / GPL / 商业多许可，使用 LGPL 允许的模块；https://doc.qt.io/qtforpython-6/licenses.html |
| NumPy 1.26.4 | 光晕遮罩计算 | BSD 与其随附组件许可，https://github.com/numpy/numpy/tree/v1.26.4 |
| FFmpeg 7.1 | Qt 音频后端随附动态库，已读取 `av_version_info()` 核验 | LGPLv2.1 及归属记录；https://github.com/FFmpeg/FFmpeg/tree/n7.1 |
| PyInstaller 6.11.1 | 冻结成品与启动引导 | GPLv2，包含允许分发成品的例外；https://pyinstaller.org/en/v6.11.1/license.html |
| BetterNCM 1.3.4 | 网易云插件宿主 | GPLv3，https://github.com/std-microblock/chromatic/tree/1.3.4；官方 DLL 单独下载，不装入 ZIP |

发布包的 `licenses` 文件夹保留上述运行组件的完整许可文本及 Qt 第三方归属记录。
公开包剔除自动收集但本程序未使用的 Qt PDF、Qt Virtual Keyboard 及对应插件。
Qt/PySide 使用独立共享库，保留 `_internal` 结构，允许按相同接口替换库以调试修改；
不限制用户为修改这些库而进行逆向工程。对应版本源码见下列地址：

- Qt 6.8.3：https://download.qt.io/archive/qt/6.8/6.8.3/single/
- PySide 6.8.3：https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
- Python：https://www.python.org/downloads/source/
- NumPy：https://github.com/numpy/numpy/tree/v1.26.4
- FFmpeg 7.1：https://github.com/FFmpeg/FFmpeg/tree/n7.1；Qt 网站的 6.8 归属页面会随补丁更新，随附文档作为许可归属参考。

导入字体由使用者提供；程序不分发 Windows 的微软雅黑、宋体和楷体字体文件。
保留 `licenses`、本说明和各库自带的许可。BetterNCM 原始源码与许可在其官方仓库公开可得。
