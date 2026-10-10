# macOS 实验支持

本仓库在 Windows 主线基础上整合 [@qingyin-alice-zhong](https://github.com/qingyin-alice-zhong) 的
[mac-version 分支](https://github.com/qingyin-alice-zhong/idea-from-limbus-company-dancing-lyrics/tree/mac-version)。
参考提交固定为 `5109df2c99ee87ee6ad5370fed70fa5d880336a5`；原分支与主线没有共同提交历史，
因此迁移平台相关改动，在提交中使用共同作者署名，并保留原作者贡献说明。

目前应用版本 **0.6.0-beta.2**，macOS 部分为实验源码支持。
Windows ZIP 和已有网易云联动安装流程继续使用；它们不适用于 macOS。
**尚未完成 macOS 真机播放、Finder 双击、全屏 Spaces 与权限验证，暂无经过验证的 Mac 安装包。**

自动测试已在 macOS 15.7.9 的 Intel 和 Apple Silicon 环境分别通过 81 项（Python 3.12.10）。
这些结果不代表真实网易云播放验收；具体 CI 链接与验证范围见 [验证记录](验证记录.md)。

## 安装与启动

需要 Python **3.10–3.12**（推荐 3.11 / 3.12）、网易云 Mac 客户端及 Homebrew 外部工具。
当前锁定的 NumPy 1.26.4 不支持 Python 3.13；安装脚本会拒绝不支持的解释器。
macOS 与网易云具体版本的兼容范围待真机确认，不套用 Windows 的客户端版本限制。

1. 通过 [Homebrew](https://brew.sh/) 安装 `python@3.12` 与
   [nowplaying-cli](https://github.com/kirtan-shah/nowplaying-cli)：

   ```bash
   brew install python@3.12 nowplaying-cli
   ```

2. [下载本仓库源码 ZIP](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/archive/refs/heads/main.zip)
   并解压，在项目目录打开终端，运行：

   ```bash
   bash 安装.sh
   ```

3. 打开网易云 Mac 客户端并播放歌曲，然后双击 **启动.command**，或运行：

   ```bash
   bash start.sh
   ```

`启动.command` 在启动失败时保留错误提示。需要帮助时附上终端输出及 `.state/app.log`，
分享日志前检查是否包含个人文件路径。
可用 `.venv/bin/python main_mac.py --check` 检查外部工具是否存在；这项检查不代表真实播放已经验证。
自定义工具路径可设置 `NOWPLAYING_CLI`，自定义设置目录使用 `bash start.sh --state-dir "/可写目录"`。
`bash start.sh --local` 启动原有本地音乐与 LRC 模式。

## 行为与限制

- 音乐播放、暂停、切歌、进度及音量都在网易云中操作；适配器仅读取信息，不发送播放控制命令。
- 系统 Now Playing 信息约每 500ms 读取一次。没有来源标识时无法保证它来自网易云，
  请暂停其他音乐或浏览器媒体；有已知来源标识时拒绝其他播放器。
- 外部工具的 `get-raw` 必须输出 JSON。工具使用 macOS 私有框架，系统升级可能使读取失效；
  [工具作者说明](https://github.com/kirtan-shah/nowplaying-cli#readme)中的测试记录不等于本项目验证结果。
- 根据歌名、艺人和时长联网匹配网易云歌词，使用原分支的接口；这些接口没有稳定性承诺。
  未准确匹配、纯音乐或无歌词时保持空白；网络失败显示提示并重试，不替换成另一首有歌词的歌。
- 中文翻译、真实 YRC 时间、白芯发光、卡门的声音、四种动画、效果预设与主题继续使用共用模块。
  YRC 只在原文一致且句首时间差不超过 250ms 时绑定，不人为拆分英文词或 emoji。
- 尚无真实音乐强弱采集，首次运行默认使用“轻波浪”，不使用模拟能量冒充音频分析。
- `⌘⌥↑` 提前 200ms、`⌘⌥↓` 延后 200ms，仅在应用处于前台时生效。
  每首歌的偏移自动保存到 `.state/offsets.json`，明确保存的零偏移也会恢复；
  未调整过的新歌继承当前偏移。偏移只作用于歌词，不修改歌曲进度条。
- 有可用菜单栏托盘时可从托盘恢复；无托盘时隐藏面板后点击 Dock 图标恢复。
  悬浮层采用 Qt 官方的 `WA_MacAlwaysShowToolWindow` 保持失焦可见，
  不遍历或修改其他窗口；跨 Spaces / 全屏行为仍待真机确认。

## 更新与卸载

退出程序后更新源码，保留 `.state`，再次运行 `bash 安装.sh`。
设置、导入字体、效果预设及歌曲偏移都不删除。
运行 `bash 卸载.sh` 并确认后，只删除当前项目的 `.venv`；不卸载 Homebrew 或共用 `nowplaying-cli`。
损坏的偏移文件保留原文件并提示，不自动覆盖。

## 验证清单

本轮实际结果见 [验证记录](验证记录.md)。自动测试覆盖 mac 适配器的状态与歌词解析，
并用模拟输入验证错误回退；不把模拟测试表述为真实网易云播放成功。
macOS CI 检查依赖、平台字体、共用渲染与适配器测试，不操作真实网易云或系统媒体。

真机验收需记录 macOS 版本、芯片、网易云版本、Python 与 nowplaying-cli 版本，并检查：

- 安装、重复安装、中文和空格路径、Finder 双击、重启后保留设置与导入字体。
- 中英文歌曲、翻译与逐字数据、纯音乐、暂停冻结、拖动进度、连续切歌、歌词请求迟到及断网恢复。
- 切换字体、主题和预设不影响音乐；最小窗口、Retina 缩放、切换其他应用、Dock 恢复及全屏 Spaces。
- 卸载只移除运行环境，不影响网易云、个人数据和外部共用工具。
