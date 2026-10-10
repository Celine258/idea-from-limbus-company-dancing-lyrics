# 都市回响 · Mac 实验版 macos.1

首次提供内置 Python、Qt 与 NumPy 的 Mac 应用压缩包。Apple Silicon（M 系列）下载 `arm64`，Intel 下载 `x86_64`。
Windows 用户继续使用原来的 `v0.6.0-beta.2` Windows ZIP。

1. 下载对应 ZIP，完整解压，将 `都市回响.app` 拖到“应用程序”。
2. 首次运行包内“安装播放读取工具.command”。需要 Homebrew，通过 `brew install nowplaying-cli` 单独安装播放读取工具；无需安装 Python。
3. 网易云 Mac 版播放歌曲后打开应用。首次打开若提示开发者无法验证，按 [Mac 安装说明](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/blob/main/MACOS.md) 和 [Apple 说明](https://support.apple.com/zh-cn/102445) 为该应用选择“仍要打开”。

应用声明最低 macOS 13。实际 CI 环境为 macOS 15.7.9；其他系统仍待确认。
应用使用 ad-hoc 签名，**尚无 Apple Developer ID 签名或公证**。ZIP 未附带 nowplaying-cli 二进制。

个人设置、字体、预设和歌曲偏移保存在 `~/Library/Application Support/CityEchoes/`，更新或移走 `.app` 不删除这些文件。
从源码版迁移请先备份 `.state`，再手动复制至成品设置目录。

验证涵盖两个架构的原生构建、运行依赖与压缩包审计、中文路径、解压后冻结程序的 Cocoa 窗口启动与隔离静音模拟数据。
[实际构建验证](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/actions/runs/38069875108)：Mac 两架构各 92 项测试通过，两个成品启动报告均为 `passed=true`。
**不代表真实网易云歌曲播放或用户电脑上的 Gatekeeper / Finder / 全屏 Spaces 已验收**，请先小范围试用。
具体测试结果见 [验证记录](https://github.com/Celine258/idea-from-limbus-company-dancing-lyrics/blob/main/%E9%AA%8C%E8%AF%81%E8%AE%B0%E5%BD%95.md)。

初始 macOS 适配贡献者：[@qingyin-alice-zhong](https://github.com/qingyin-alice-zhong)。
各 ZIP 附带 SHA-256 校验文件、MIT 与第三方许可、构建版本及源提交记录。
