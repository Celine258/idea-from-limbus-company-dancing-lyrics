# 网易云音乐联动

歌曲由网易云音乐 Windows 版播放，“跳动的歌词”接收当前歌曲、歌词时间轴和进度，在透明桌面层绘制动画。最小化网易云后，桌面歌词继续显示；歌词层不接管鼠标和键盘。

## 使用

本次适配网易云 **3.1.41.205529（64 位）**，插件版本 **0.1.1**，插件框架使用 **BetterNCM 1.3.4**。

安装后重新启动网易云，在底部播放栏的“词”按钮旁会出现红色 **跳动的词** 按钮：

- 点击开启或关闭桌面歌词效果。
- 右键打开歌词设置，可修改显示区域、颜色、字体、倾斜、跳动幅度和同步偏移。
- 播放、暂停、切歌、进度和音量继续在网易云中操作。
- 暂停时冻结歌词，跳转时重新定位；关闭网易云后清除歌词。
- 退出桌面歌词引擎后，插件停止自动启动它；再次点击按钮可开启。
- 无歌词歌曲保持空白。网易云提供纯音乐提示时，按该提示的时间轴显示。

原有本地音乐与 LRC 模式保留，可通过项目的 `启动.bat` 使用。网易云插件自动启动的是联动模式，不会在后台再播放一份音乐。

## 安装与更新

开发环境先构建，**完全退出网易云**后安装：

```powershell
.\build.ps1
.\tools\install_netease.ps1
```

脚本验证客户端的完整版本与官方框架 DLL 的 SHA-256；不同客户端版本或已有不同 `msimg32.dll` 时停止，不覆盖未知框架。安装到 `Program Files` 可能需要在管理员 PowerShell 中执行安装命令。

框架来自 [BetterNCM 官方 1.3.4 发布](https://github.com/std-microblock/chromatic/releases/tag/1.3.4)。安装步骤遵循 [官方安装器说明](https://github.com/std-microblock/BetterNCM-Installer)。只新增框架 `msimg32.dll` 和 `C:\betterncm\plugins\FloatingLyrics.plugin`，不修改客户端原有程序、曲库或登录数据。

客户端有其他安装位置时，可传入 `-ClientDirectory`。`-ProfileDirectory` 用于已通过 `BETTERNCM_PROFILE` 配置的框架目录；它不会自动设置系统环境变量。

更新打包版时，构建脚本保留原 `.state`，旧包备份到 `artifacts/previous-package-*`。安装记录及已有同名插件的备份保存在 `artifacts/netease-install-*`。不要移动打包目录；移动后需要重新安装插件以更新启动路径。

## 卸载与回滚

退出网易云和桌面歌词引擎，删除 `C:\betterncm\plugins\FloatingLyrics.plugin`，即可移除本插件。若本次替换了旧插件，可从安装记录所指向的备份恢复它。

若安装记录中 `createdFramework` 为 `true`，并且不再使用其他 BetterNCM 插件，可删除网易云安装目录里的 `msimg32.dll`。不要删除整个框架目录或覆盖其他插件。原网易云客户端无需重新安装。

## 技术边界

- [插件](plugins/netease/index.js)通过 3.1.41 播放组件取得 Redux store，只选取当前歌曲及歌词字段；订阅应用已有的 `audioPlayerPlayProgress$`、`audioPlayerSeek$` 事件流，取得秒级时间并转换为毫秒。只检查已加载模块的事件导出，不主动加载客户端其他模块。客户端歌词已经包含自身偏移，适配器不重复应用该偏移。
- 不通过独立的 `window.legacyNativeCmder` 实例注册播放回调：该实例的回调表与实际播放器分离，重新注册可能覆盖网易云的原生事件槽。插件读取或发送失败不会中断宿主的事件处理，退出页面时只取消自己的订阅。
- 插件复用网易云自己的歌词获取流程，切歌时清除旧歌词，只接受属于当前歌曲的歌词。无需额外网易云账号、Cookie、第三方歌词服务器或本地音乐文件。
- [本地桥接](netease.py)使用 `127.0.0.1:38473` 的 WebSocket 和每次安装生成的随机连接令牌；拒绝错误令牌、不兼容协议、无效时间或过大歌词。连接断开或超过四秒无数据时停止动画并清空歌词。
- [音频助手](native/process_energy.cpp)使用 Windows 的 [进程音频回环接口](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/)，只计算网易云进程及其子进程的 RMS，向界面传递一个强度数值，不录制麦克风或保存音频。此接口需要 Windows build 20348 或更新版本；不可用时面板提示切换“轻波浪”。
- 精确演唱到每个字的时间、精准节拍检测和其他客户端版本尚未实现。当前逐字跳动由音频强度及歌曲时间驱动。
- BetterNCM 的公开支持范围未包含全部 3.1 版本；本项目只声明已实测的 3.1.41。网易云更新后需重新验证适配。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py --smoke
.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\launcher-bat-netease"
```

联动观察必须使用真实网易云和已加载插件。下列命令采集 45 秒数据，在这期间操作网易云播放、暂停、跳转、最小化并最后退出客户端：

```powershell
.\dist\FloatingLyrics\FloatingLyrics.exe --netease --netease-smoke --report-dir "$PWD\artifacts\netease-live"
```

报告记录歌曲编号、进度、歌词数量、声音强度和画面验证，不保存完整歌词或音频。只有真实操作满足全部检查，报告才会显示 `passed: true`；接口单元测试不能替代真实客户端验证。

还需单独检查网易云自己的进度条及连续切歌，避免歌词引擎正常而宿主播放器异常。完全退出网易云后，仅在验证期间通过调试端口启动原客户端：

```powershell
& 'C:\Program Files\NetEase\CloudMusic\cloudmusic.exe' --remote-debugging-port=9229
node tools\verify_netease_host.mjs artifacts\netease-host-regression
```

[宿主验证工具](tools/verify_netease_host.mjs)通过外部定时驱动真实客户端，检查进度移动、暂停、跳转完成、连续三次切歌后保持播放和歌词所属歌曲。它会操作播放与切歌，输出 `host-report.json`；结束后退出客户端，再正常启动即可关闭调试端口。界面截图另行检查，避免后台截图接口等待帧绘制而影响验证时序。
