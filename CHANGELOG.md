# 变更记录

每次改动按日期追加记录，包含改动目的、涉及文件、测试与验证结果、影响或已知限制。

## 2026-10-06：接入网易云音乐插件与桌面歌词引擎

### 改动

- 新增 [BetterNCM 插件](plugins/netease/index.js)和 [3.1.41 播放器适配](plugins/netease/adapter.js)，在网易云播放栏提供“跳动的词”开关和右键设置入口。读取当前歌曲、网易云自身歌词及原生播放进度，音乐由网易云播放。
- 新增 [本地连接与播放状态](netease.py)，用本机 WebSocket 和随机令牌传输歌词、播放位置与状态。连接丢失时停止动画并清空歌词；切歌清理旧歌词；暂停后忽略迟到的进度回调，未变化的歌词不重复随机布局。
- 新增 [进程音频助手](native/process_energy.cpp)及 [能量接入](process_audio.py)，仅计算网易云进程树的声音强度，不保存音频。复用透明歌词层和现有外观设置。
- [启动入口](main.py)增加网易云模式、后台启动和真实联动检查；[面板](controls.py)在联动模式显示歌曲及只读进度，播放和音量操作保留在网易云。退出歌词引擎后插件停止自动重启它。
- 新增 [打包](tools/package_netease.py)、[安装](tools/install_netease.ps1)及 [音频助手构建](tools/build_energy.ps1)工具。[构建脚本](build.ps1)先完成新包，再备份旧版并保留 `.state`；`.gitignore` 排除客户端产生的 `debug.log`。
- 新增协议、真实回环连接、插件生命周期、暂停迟到事件和 DOM 重复更新测试，扩展界面与文档测试；更新使用、产品和技术文档，增加 [网易云说明](NETEASE.md)及 [真实验证器](netease_validation.py)。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：41 项通过，包括原有 29 项及 12 项新增/扩展检查；JavaScript 适配与插件生命周期检查由 Node.js 执行，本地 WebSocket 使用真实握手验证。
- `.\.venv\Scripts\python.exe main.py --smoke --report-dir artifacts/netease-local-smoke`：原本地音乐流程 Windows 静音验证通过，真实解码、暂停、跳转、布局、透明穿透、置顶和禁止激活检查全部通过。
- `.\build.ps1 -SkipDependencies`：Visual Studio C++ 工具与 Windows SDK 成功构建音频助手；PyInstaller 6.11.1 完成新版打包。旧包备份为 `artifacts/previous-package-20261006-165349-025`。
- `.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\launcher-bat-netease"`：实际批处理入口退出码 0，原生控制面板可见，打包版全部静音检查通过。
- 使用项目内隔离副本验证 BetterNCM 1.3.4 在网易云 3.1.41.205529（64 位）实际可加载，再通过 `tools/install_netease.ps1` 安装到原客户端。普通权限写入安装目录被 Windows ACL 拒绝后，通过 Windows 管理员授权完成安装，未降级网易云；记录为 `artifacts/netease-install-20261006-165956-440/receipt.json`。
- `artifacts/netease-probe/run-installed.ps1`：原客户端与打包引擎真实联动验证通过，45 秒采集 220 个样本；9 项检查全部通过，包括真实歌曲、35 行歌词、实际歌词画面、暂停时间与画面冻结、跳转、最小化后进度继续、进程声音强度、退出客户端清除歌词及不创建第二个播放器。最终最高平滑强度约 0.0491；报告为 `artifacts/netease-live-installed/netease-report.json`。
- 已查看原网易云播放栏入口、联动面板及透明歌词截图。新旧打包版、安装及验证后的正常 `settings.ini` SHA-256 一致，记录为 `artifacts/netease-settings-preservation.json`。

### 影响与限制

- 本次适配网易云 Windows 3.1.41.205529（64 位），依赖第三方 BetterNCM 1.3.4。客户端更新后需重新验证；本地音乐模式保留。
- 进程音频回环需要 Windows build 20348 或更新版本；不可用时可以选择“轻波浪”。仍为按句同步，尚未实现逐字演唱时间或精准节拍检测。
- 真实客户端验证覆盖短时功能行为，未完成长时间稳定性、多显示器动态切换或所有歌曲类型检查。安装目录、产物、连接令牌、用户配置、截图和测试报告不纳入 Git。

## 2026-10-06：改为浅色音乐播放器布局

### 改动

- 参照用户提供的浅色音乐软件截图，重组 [控制面板](controls.py)：浅灰背景、白色圆角卡片、红色强调色、约 200px 侧栏，以及固定的底部播放栏。
- 增加“当前音乐”和“歌词效果”导航，分别呈现单首歌曲信息与分组设置；保留本地音乐导入、同名 LRC 匹配、演示、播放控制、透明桌面歌词和托盘操作。
- 歌曲信息同步到内容区与底栏，长名称省略并保留完整路径提示；错误提示跨页面保持可见，导入不存在的音乐时保留原歌曲和歌词。颜色选择按钮使用独立色块，浅色歌词颜色不会使按钮文字难以阅读。
- 更新 [启动入口](main.py) 的屏幕适配与 Qt 控件风格；使用绘制的本地图标和细进度条，保留 Windows 原生窗口操作及原有歌词颜色配置，更新 `assets/app.ico`。
- 新增 [界面测试](tests/test_controls.py)，扩展 [集成验证](validation.py) 和 [文档校验](tests/test_workflow_docs.py)，更新 [使用说明](README.md) 与 [验证记录](验证记录.md)。
- 在隔离目录构建新版，再替换 `dist/FloatingLyrics`。旧版保留在 `artifacts/ui-previous-package-20261006`，复制原有 `.state` 并核对用户设置文件 SHA-256。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：29 项通过，包含 11 项新增界面测试、15 项核心测试及 3 项扩展文档与 Git 范围校验。
- `.\.venv\Scripts\python.exe main.py --smoke --report-dir artifacts/ui-150`：Windows 集成验证通过，控制面板原生可见，真实音频解码、暂停、跳转、恢复、歌词动画与窗口输入标志均正常。
- 分别使用 `QT_SCALE_FACTOR=0.6666666667`、`0.8333333333` 及系统默认比例启动源码检查；报告的实际像素比例为 1.0、约 1.25、1.5，三个报告均通过。默认及最小窗口下播放栏可见、设置可通过滚动完整访问；已查看两个页面、空状态及缩放截图。
- PyInstaller 6.11.1 在隔离的 `artifacts/ui-package` 目录构建成功；打包版静音验证通过。
- 从 `D:\Work` 运行实际入口 `启动.bat -Smoke -ReportDirectory D:\Work\跳动的歌词\artifacts\launcher-bat-ui`：退出码 0，控制面板原生可见，全部集成检查通过。
- 替换打包版前后及入口验证后，正常用户配置 `settings.ini` 的 SHA-256 一致；保存记录为 `artifacts/ui-settings-preservation.json`。

### 影响与限制

- 本次改动为界面重排和视觉更新，功能仍以单首本地音频与 LRC 为基础；网易云截图仅用于视觉参考。
- 缩放检查通过 Qt 应用级比例完成，未修改 Windows 系统显示设置；跨显示器动态切换、独占全屏和 30 分钟稳定性测试仍需实际体验。
- 音频检查使用静音解码，未人工听音；打包产物、用户设置、验证报告和截图继续由 `.gitignore` 排除。

## 2026-10-06：建立 Git 基线与协作规则

### 改动

- 初始化 `main` 分支，将现有桌面歌词源码、文档、测试和演示资源纳入首次提交，建立后续追踪与回滚的基线。
- 新增 [AGENTS.md](AGENTS.md)，要求每次改动提交 commit、编写或更新相关测试、交付前全部验证通过，并记录每次改动。
- 新增本变更记录及 [协作文档校验](tests/test_workflow_docs.py)，校验文档编码、链接、记录结构和 Git 忽略范围。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：18 项测试全部通过，其中包括 15 项核心测试及 3 项新增文档与 Git 范围校验。
- 新增校验确认 UTF-8 文档可读、代码围栏配对、文件链接有效、变更条目完整，以及运行产物被忽略、源码可跟踪。
- `git diff --cached --check`：通过；人工检查暂存文件范围及三项协作要求，均符合本次任务。

### 影响与限制

- 本次新增协作规则和版本管理记录，应用功能未改动。
- 现有功能和此前启动修复作为初始基线纳入版本管理；它们的已有验证见 [验证记录.md](验证记录.md)。
- 虚拟环境、个人运行配置、打包产物和验证截图沿用 `.gitignore` 的忽略规则。
