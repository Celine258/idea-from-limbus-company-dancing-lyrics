# 变更记录

每次改动按日期追加记录，包含改动目的、涉及文件、测试与验证结果、影响或已知限制。

## 2026-10-09：中文译文优先显示

### 改动

- “显示与文字”新增默认关闭的“有中文翻译时优先显示译文”，立即应用和保存。每句无可靠中文译文时保留原文；歌词语言独立于效果预设。
- 插件 0.1.4 仅增加可选 `translation` 字段，读取客户端 `tlyricLines`，根据已经应用偏移的原文时间对齐；迟到译文触发更新，切歌清除旧内容。旧插件无需译文字段仍可使用。
- 原文和 YRC 保存在模型中，显示译文的句子不套用原文字词时间，按整句动画显示；保留空白边界、用户同步偏移与纯音乐处理。新增协议、逐句回退、偏移、迟到更新、暂停、设置和预设独立性测试。

### 测试与验证

- 全部 162 项自动测试通过，8.677 秒，`artifacts/translation-tests.txt`；实际 BAT 静音入口 `artifacts/translation-smoke` 通过，开关保存、演示译文重建、暂停时钟和小窗口滚动访问均通过。
- 真实 3.1.40 和 3.1.41 客户端均读取《Fly, My Wings》的 `tlyricLines`，与原文 `lyricLines` 时间一致，例如首个演唱句 13.535 秒；两个版本分别定位到原生详情模块 14/Oh 与 15/ji。证据在 `artifacts/compat-3140/translations.json`、`translations-41.json`，检查后恢复原播放队列和正常客户端。

### 影响与限制

- 不调用外部翻译服务、不修改网易云播放回调；译文演唱强调保持关闭，因为原文时间不能可靠映射译文。客户端 3.1.40 的完整插件播放回归与最终成品验证继续在兼容性改动中完成。

## 2026-10-09：卡门的声音发光风格

### 改动

- 在“白芯发光”内加入“发光风格 → 卡门的声音”，采用固定暖白 `#ffe6bd` 字芯、柔和琥珀描边与金色 `#ffb655` 光晕；强度仍可调，原有颜色保留。经典纯色和标准白芯保持现有效果。
- 新增 `glow_variant` 设置与预设保存，旧设置默认 `standard`；桌面与预览共用材质、渐隐、逐字动画和缓存，扩大卡门光晕布局边界。
- 新增设置、界面、预设和像素测试；静音验证加入真实样式切换、保存、暂停不变、深浅背景截图与独立暖缓存性能检查。

### 测试与验证

- 全部 157 项自动测试通过，7.948 秒，`artifacts/carmen-final-tests.txt`。首次沙箱运行受到原子替换和本机 WebSocket 限制，原生 Windows 重跑全部通过。
- 实际 `启动.bat -ForceSource -Smoke` 通过，`artifacts/carmen-final-smoke-fixed`；原生窗口、默认／最小尺寸滚动访问、暂停和跳转检查通过，DPR 1.5 下卡门双句暖帧 P95 为 4.907ms，复用缓存且低于 64MiB。
- 已查看真实渲染的 `carmen-dark.png`，同时生成浅色与透明底效果。验证截图曾使用临时 QImage 的缓冲引用而崩溃，现已改为保留图像对象后读取，最终入口退出码 0。

### 影响与限制

- 卡门风格仅改变歌词材质，不改变网易云播放接口；字体、动画、用户颜色和预设继续保留。更多缩放与两版本播放回归随最终发布包一起复核。

## 2026-10-09：应用更名为都市回响

### 改动

- 窗口、侧栏、托盘、网易云入口、安装界面及当前使用文档统一采用“都市回响”；应用名由 `APP_NAME` 管理。插件显示名称一起更新。
- 保留 `FloatingLyrics.exe`、插件 slug、连接协议、任务栏身份和用户设置目录，更新继续使用原设置、字体与预设。修正 BAT 启动器中的 Unicode 转义窗口标题匹配，并新增界面及安装身份回归检查。

### 测试与验证

- 全部 152 项自动测试通过，最终耗时 7.744 秒，日志 `artifacts/city-name-final-tests.txt`。
- 实际 `启动.bat -ForceSource -Smoke` 通过，报告 `artifacts/city-name-smoke-final`；Windows 原生新名称面板可见，主题、布局、静音播放及暂停／跳转检查通过。
- 首次启动器仍匹配旧名称的 Unicode 转义文本，导致应用自行检查通过但启动器报错；已修正并补测试，最终入口退出码 0。

### 影响与限制

- 本轮完成显示名称更新，仓库地址、EXE 文件名及已有安装身份不变；新版发布包将在后续功能与兼容性验证全部结束后统一生成。

## 2026-10-08：README 使用创作者提供的实机演示 GIF

### 改动

- 将用户提供的《演示.mp4》完整转换为 `docs/images/lyrics-demo.gif`，替换首页原有预览动图；README 图片说明改为网易云联动与桌面歌词实机演示，并说明无声循环播放。
- 保留原视频的 16:9 画面和全部时长，输出 960×540、15fps、128 色 GIF。新增两项文档／媒体测试，检查首页内嵌位置、完整帧解码、有效帧时长、循环、画面变化、比例和文件大小。
- 更新 `验证记录.md`，记录转码参数及实际媒体检查结果；没有新增程序运行依赖。

### 测试与验证

- `.venv/Scripts/python.exe -m unittest discover -s tests -v`：150 项全部通过，耗时 7.398 秒，日志为 `artifacts/readme-gif-tests.txt`。
- Qt 逐帧解码与 FFmpeg 全文件解码通过；输出 276 帧、总时长 18.400 秒、无限循环，文件 5,982,543 字节。已查看 GIF 的首帧、中间帧和末帧，确认完整画面与歌词效果保留。
- 文档更新后复核相关文档测试和本地链接，提交前检查 Git 差异及空白错误。

### 影响与限制

- 本次仅更新公开演示素材、README、测试和记录；应用版本、已发布 ZIP、用户设置及网易云播放行为保持当前状态。
- GIF 不支持音轨，播放采用 15fps 和缩小后的 960×540 画面；原视频未修改。未重新运行启动／播放集成检查，本次没有改动程序或启动入口。

## 2026-10-07：增加便携安装入口并准备首次公开试用版

### 改动

- 应用升级到 `0.5.1-beta.1`。`netease_install.py` 与 `installer_ui.py` 将安装／卸载封装进成品 EXE，提供原生窗口、客户端自动寻找、完整版本及 x64 检查、官方 BetterNCM 1.3.4 下载和 SHA-256 校验、管理员重试、原子写入及失败回滚；通过 `--install-netease`／`--uninstall-netease` 调用。记录安装目录，重装复用本机令牌；卸载仅删除指向本程序的插件，保留共用框架、设置、字体和预设。
- `build.ps1` 将无连接令牌的三个插件模板放入成品；`tools/package_netease.py` 复用安装器打包逻辑。`release` 提供安装、卸载、独立启动 BAT 和使用说明；入口失败保留提示。`tools/package_release.py` 只打包 EXE、运行目录、入口和许可，剔除 `.state`、预配置插件、日志、开发环境及未使用的 Qt PDF／Virtual Keyboard 组件，并生成 SHA-256。首次公开包约 67MiB。
- 新增 MIT、第三方归属与完整运行组件许可；只从官方固定版本单独下载 BetterNCM，不装入 ZIP。README 首屏添加动图、成品下载和三步安装说明；新增 Issues 模板、传播文案、原生公开包验证器及 30 秒无音乐演示制作工具。音乐协议、歌词、动画及纯音乐处理沿用原逻辑。

### 测试与验证

- Windows 全部自动测试最终 148 项通过。新增 16 项覆盖中文／空格路径、重复安装、网络失败、散列错误、不兼容／x86 客户端、失败回滚、损坏配置、目录记忆、所有权检查、用户数据保留、公开包内容和许可原字节；扩展文档校验。上游许可通过 Git 属性保留原始空白及来源散列，不进行项目格式化。实际完整版本字符串是 `3.1.41.205529`，数字资源的构建段会截成 `8921`，安装器已正确读取 Windows 的字符串资源并用独立原生版本读取验证。
- `build.ps1 -SkipDependencies`、源码实际启动器静音检查及成品 100%／125%／150% 的实际 `启动.bat -Smoke` 均通过，原生窗口、三种主题、默认／最小窗口、滚动及固定底栏正常；报告在 `artifacts/release-source-smoke` 和 `artifacts/release-launcher-*`。发光暖帧 P95 分别为 15.452／17.237／22.767ms，八种动画同步组合也均 ≤33ms。精简后的最终公开 ZIP 还通过三个 DPR 的同样完整检查，记录见验证记录；首次构建替换目录因旧引擎占用失败，退出旧进程后构建成功。
- `tools/verify_release.py` 对最终公开 ZIP 清除 Python／开发工具 PATH 后独立解压，安装、覆盖更新、卸载、重复卸载及三个 BAT 原生入口均通过；用户数据、令牌和共用框架保留。最终报告为 `artifacts/release-public-verified/release-report.json`。官方框架实际在线下载散列通过。程序本身在 EXE 内携带 Python，不依赖系统 Python。
- 真实网易云 `artifacts/release-netease-confirmed` 引擎 24 项、宿主 10 项及鼠标入口 3 项均通过，347 个采样、21 次重定位，真实演唱强调峰值 1.0；中英文 YRC、整句和纯音乐回退、进度、暂停、跳转、连续切歌及设置／预设切换不改变播放均通过。首次把初始化绘制基准合并到播放采样时，采样错过了逐字时间区间，仅“实际强调已观察”未通过；保留 `artifacts/release-netease-verified`，将已单独通过的绘制检查与真实播放采样分开后全部通过，未降低功能断言或改歌词协议。
- 30 秒 H.264 演示为 1280×720、900 帧／30fps，无歌曲音频；全文件解码及抽帧通过。安装截图使用原生窗口绘制，避免其他桌面窗口遮挡或进入公开素材。正常网易云及后台歌词引擎已恢复；`artifacts/release-user-preservation.json` 证明正常设置及连接配置 SHA-256 不变。

### 影响与限制

- 首次发布仅声明本机已验证的 Windows 11 x64、网易云 3.1.41.205529 x64、BetterNCM 1.3.4；不兼容客户端拒绝安装，不覆盖不同版本的框架。安装到长期保留且可写的目录；移动程序或更新后重新安装联动，退出网易云后再安装／卸载。
- 本机独立解压并移除开发环境路径不等同于干净电脑验证。尚无第二台无开发环境电脑或干净虚拟机的实测；朋友试装、Bilibili 投稿和群消息由创作者后续完成。发布为预发行版，保留上述边界；源码、标签与公开下载通过指定 GitHub 仓库发布。

## 2026-10-07：新增黑金特殊主题与但丁钟头运行图标

### 改动

- 应用升级到 `0.5.0`，保留默认主题和深色主题，新增“特殊主题”。`themes.py` 增加黑金配色、琥珀控件、切角双层边框及机械图纸底纹；`controls.py` 使用仅在该主题绘制装饰的框架，沿用原页面、滚动和底栏布局。新增透明矢量资源 `assets/dante-clock.svg`、`assets/special-blueprint.svg`。
- 特殊主题同时替换侧栏、窗口、运行中 Windows 任务栏和系统托盘图标，后台仍为但丁钟头；切回默认或深色主题恢复原红色波形。`settings.py` 接受 `theme=special`，即时保存并在重启时恢复，旧配置及无效值继续使用默认主题。歌词材质、预览背景、字体、动画、效果预设和音乐播放独立。
- `app_info.py`、`main.py` 在窗口创建前设置稳定的 Windows 任务栏应用标识，避免源码窗口使用 Python 分组图标。扩展 `validation.py` 和 `netease_validation.py`，检查实际 HICON 位图切换／恢复、应用／窗口／托盘图标一致及三种主题的原生布局。新增图标尺寸、透明背景、保存重建、原主题像素恢复、原生调用边界及文档测试，更新使用和设计文档，重新打包。

### 测试与验证

- Windows `.venv/Scripts/python.exe -m unittest discover -s tests -q`：最终 132 项全部通过，包含设置、界面、图标、字体、绘制、歌词同步、插件、启动及协作文档检查；实际结果见 [验证记录](验证记录.md)。
- `build.ps1 -SkipDependencies` 成功，旧包备份为 `artifacts/previous-package-20261007-220255-273`。最终包通过实际 `启动.bat -Smoke` 验证，报告为 `artifacts/special-launcher-100`、`special-launcher-125`、`special-launcher-150`；实际 DPR 为 1.0、约 1.25、1.5，三套主题在默认／最小窗口全部可访问，底栏、原生可见性及图标切换恢复均通过。已查看实际页面、最小窗口、125% 截图和任务栏钟头截图。
- 最终 150% 八种动画组合暖帧 P95 为 11.280–18.181ms，原有发光基准为 26.227ms。真实网易云最终 `artifacts/special-netease-verified` 的引擎 34 项、宿主 10 项、真实鼠标入口 3 项全部通过；75 秒记录 255 样本、21 次重定位。中英文 YRC、整句和纯音乐四类歌曲进度正常，连续三次切歌稳定；主题保存、原生图标恢复、暂停冻结、跳转和最小化继续正常，主题切换不改变播放锚点、歌词文档或预览。播放负载下发光 P95 为 26.852ms，八种动画组合为 13.926–21.837ms。
- 首轮源码窗口 HICON 正确，但实际任务栏仍显示 Python 图标；补上独立应用标识后最终包原生检查与截图通过。首次网易云回归只有发光基准略超目标（33.485ms），其余全部通过；保持相同测量方法和 33ms 阈值复核，最终全部通过，没有修改绘制规则或放宽检查。首轮报告保留在 `artifacts/special-netease-live`。
- `artifacts/special-preservation.json` 证明用户设置和桥接配置散列前后一致；个人字体原为空，自定义预设原不存在，均保持原样。正常网易云及新版后台引擎已恢复，不带调试端口；运行时插件仍为 `0.1.3`，适配器与原源码一致。实际演示设置截图为 `artifacts/special-preview/special-settings-preview.png`，采用独立静音示例，未改正常用户设置。

### 影响与限制

- 特殊主题由用户在侧栏选择，不会自动覆盖旧主题；没有新增运行依赖或改动网易云协议、播放订阅及纯音乐处理。默认和深色主题的原配色与红色图标保持原样。
- 本轮替换运行窗口／任务栏和后台托盘图标；EXE 文件和未运行的固定快捷方式仍由 Windows 管理。Windows 原生标题栏和文件对话框沿用系统外观。
- 缩放检查使用进程 Qt 比例，未改系统设置；软件绘制耗时会受当时机器负载影响，不是 GPU 帧率或长期稳定性保证。其他客户端版本、多屏与长时间运行的验证边界沿用既有说明。

## 2026-10-07：更新创作者文案与版本并增加界面主题

### 改动

- 新增 `app_info.py` 集中管理应用版本 `0.4.0`、创作者与标语；`main.py` 设置 Qt 应用版本，`controls.py` 将侧栏说明替换为“创作者：Bilibili-鈴仙優昙華院因幡”，其下显示版本号，底部标语改为“FACE THE SIN. SAVE THE E.G.O”。长文案按语义换行，最小窗口保持完整。
- 新增 `themes.py`，原浅色外观命名为“默认主题”，另提供“深色主题”；侧栏可切换，页面、底栏、图标、控件及托盘菜单一起更新。滑块仍使用红色进度，勾选框采用可见边框与 `assets/check-white.svg` 白色勾选标记。
- `settings.py` 新增 `theme=light/dark`，旧配置与无效值回退默认主题；立即保存，重启恢复。`presets.py` 明确排除界面主题，切换效果预设不覆盖主题，主题切换不修改歌词样式、预览背景或播放状态。
- 扩展设置、界面、像素、预设及文档测试，`validation.py` 生成两种主题的默认／最小窗口截图，`netease_validation.py` 检查播放中切换主题。`start.ps1` 仅将静音诊断的完成等待上限扩展至 120 秒，普通启动的原生窗口可见性期限仍为 30 秒。更新使用、网易云、产品、技术及验证说明，重新打包。

### 测试与验证

- Windows `.venv/Scripts/python.exe -m unittest discover -s tests -q`：127 项全部通过。覆盖文案与版本顺序、旧配置回退、主题持久化和重建窗口、预设独立、播放／歌词／预览不变、两种主题的滑块及勾选框像素、启动脚本语法与等待边界、文档链接和源码可追踪性。
- 最终打包版 `artifacts/themes-final-100`、`themes-final-125-verified`、`themes-launcher-complete` 全部静音检查通过，实际 DPR 为 1.0、约 1.25、1.5；默认及最小窗口两种主题的控件可滚动访问，侧栏完整，歌词画面、暂停时钟及预览背景保持不变，SVG 勾选资源加载成功。已查看实际深色／默认主题、最小窗口及 125% 截图。
- 最终 `启动.bat -Smoke -ReportDirectory artifacts/themes-launcher-complete` 退出码 0、Windows 原生面板可见；125% 同样通过实际 BAT 入口。最终 150% 静音报告中八种动画组合暖帧 P95 为 10.277–17.030ms，发光基准为 24.185ms，均小于 33ms。
- 首次 BAT 诊断窗口已经可见，但增加两套主题截图后完成阶段超过原 30 秒期限；补充有界诊断等待及测试后复验通过。125% 首次直接以 Hidden 启动验证进程导致原生可见性检查失败；改用实际 BAT 的原生窗口恢复流程后全部通过，没有绕过该检查。
- `artifacts/netease-probe/run-words-regression.ps1 -ReportName themes-netease-complete`：引擎 32 项、宿主 10 项、真实鼠标入口 3 项全部通过，75 秒记录 254 样本及 21 次重定位。中英文 YRC、整句歌词及纯音乐四类歌曲进度正常；主题切换保存且不改变播放锚点、歌词文档或预览背景，暂停冻结、跳转、连续三次切歌和最小化继续正常。
- 改动前包备份为 `artifacts/previous-package-20261007-205918-449`，最终构建前中间包为 `artifacts/previous-package-20261007-211047-539`。`artifacts/themes-preservation.json` 证明正常设置与连接配置散列前后一致；个人字体原为空，自定义预设原不存在，保持原样。正常网易云及新版引擎已恢复启动，无调试端口，运行时插件适配器与源码一致。

### 影响与限制

- 界面主题独立于歌词的白芯发光／经典纯色、动画、字体、效果预设和网易云协议；纯音乐行为保持原状，插件仍为 `0.1.3`。没有新增应用运行依赖。
- Windows 原生标题栏与文件对话框沿用系统外观；主题只控制应用界面与托盘菜单。缩放检查通过进程 Qt 比例完成，未改变系统设置；本轮没有扩展长期稳定性或其他网易云版本的验证范围。

## 2026-10-07：接入真实 YRC 演唱强调并完成参数与预设交付

### 改动

- 插件升级为 `0.1.3`，`adapter.js` 读取当前歌 `yrcInfo.yrc`，精确原文与句首 250ms 内匹配，应用一次客户端偏移，追加可选字词绝对时间和码点范围；没有新增歌词服务或播放回调，协议仍为 1，原整句与纯音乐流程兼容。
- `lrc.py`、`netease.py` 扩展可靠时间模型、逐项坏数据回退、同步偏移及收数状态；`animation.py` 为字形簇保留原文范围，`glyph_motion.py` 按歌曲位置计算平滑 8% 放大，`text_effects.py` 在缓存合成阶段增强光晕，零发光与经典模式保持原材质。`overlay.py` 保留迟到时间数据的布局，纳入强调边界，暂停与跳转不累积状态。
- `controls.py` 提供默认关闭的演唱同步、四种数据状态、中英文演示预览；开关包含在预设中，原偏好保持不变。补齐 `presets.py` 损坏文件移走后可重试保存的行为。
- 新增 `tests/test_singing_sync.py`、真实数据验证器 `tools/verify_netease_words.mjs` 及其证据校验测试，扩展界面、插件、打包保留及静音／网易云验证。`main.py`、`netease_validation.py` 增加 `--singing-smoke`；重复诊断已有开启状态时也明确保存。`animation_validation.py` 测量八种组合，`tools/record_animations.py` 支持标明演示时间的同步录制。
- 更新使用、网易云、产品、技术及验证文档；重新打包，原用户 `.state` 整体保留，完成真实 BAT 入口和原客户端插件更新。

### 测试与验证

- Windows `.venv/Scripts/python.exe -m unittest discover -s tests -q`：最终 121 项全部通过。覆盖配置与参数、预设保存／确认／重启／损坏、中文单字与多字词、英文单词、组合字符／emoji／换行、偏移、无数据／损坏／迟到／切歌、暂停／跳转、透明度及最大跌落／强调／光晕边界；包含文档和真实验证器拒绝假阳性检查。
- 原生 Windows 源码静音 `artifacts/singing-source-100`、`singing-source-125`、`singing-source-150` 全部通过，实际 DPR 为 1.0、约 1.25、1.5。默认与最小窗口滚动控件、固定底栏、暂停冻结及结束清理通过；100% 导入 TTF、125% 导入 TTC，最终网易云回归导入 OTF。已查看面板、最小窗口、深浅预览及演示中间帧，未发现裁切、残影或矩形底色。
- `build.ps1 -SkipDependencies` 通过；原任务开始前包备份到 `artifacts/previous-package-20261007-152754-763`，收尾诊断修复前的中间包为 `artifacts/previous-package-20261007-153456-326`。插件安装记录为 `artifacts/netease-install-20261007-152826-133`，确认运行时版本 0.1.3 和适配器散列一致。
- 最终 `启动.bat -Smoke -ReportDirectory artifacts/singing-launcher-final` 退出码 0，窗口 Windows 原生可见，全部静音检查通过。51 字符双句、八组合、每组合 90 个暖帧，P95 为 3.755–6.778ms；均小于 33ms，复用模糊缓存。
- `artifacts/netease-probe/run-words-regression.ps1 -ReportName singing-netease-verified2`：引擎 29 项、宿主 10 项、真实鼠标入口 3 项全部通过；75 秒采集 334 样本、21 次重定位。真实《Fly, My Wings》8 行／40 单位、《星辰大海》19 行／131 单位到达引擎，二者均观察到完整强调；《起风了》70 行整句正常回退，《Holy Termination》纯音乐保持无歌词。四类歌曲进度移动，暂停冻结画面，跳转结束，连续三次切歌保持选定歌曲，最小化继续及断连清理通过；参数、两个预设及同步开关不改变播放锚点／状态。播放负载下八组合 P95 为 3.929–6.487ms。
- 首轮宿主验证把跳转误差设为 150ms，并在纯音乐尚未开始音频时采样，导致不通过；修正为等待真实进度及记录原生解码落点，实测英文误差 227ms、中文 462ms，加载状态归零。又发现隔离诊断已有开关开启时未触发保存、原曲暂停时无法检验最小化推进；补回归测试并明确保存，验证阶段临时播放后恢复原状态。最终所有检查通过，未修改插件播放订阅。
- 四种强调演示 GIF 由 Windows Qt 窗口录制，`artifacts/singing-demo` 每份 5.5 秒，源 165 帧／30fps，编码重开确认 151 合并帧；明确为中英文演示时间，不冒充实际歌曲。真实客户端强调截图另存于 `singing-netease-verified2/netease-singing-overlay.png`。
- 正常设置与连接配置散列前后一致；个人字体目录原为空，自定义预设原不存在且未生成，打包保留非空文件由自动测试覆盖。证明为 `artifacts/singing-preservation.json`；原队列、歌曲和暂停状态恢复，正常网易云及新版引擎运行，无调试端口。

### 影响与限制

- 同步默认关闭，旧偏好保持当前体验；只有原文与时间都可靠的行增强，不能声称所有歌曲都有逐字支持。真实两首 YRC 的客户端偏移为 0；非零偏移由客户端格式化源码及自动测试验证，未改用户偏移进行人工校准。英文按词而非按字母强调，普通 LRC 不猜测演唱时间。
- 没有新增运行依赖；性能是本机暖缓存软件绘制，冷准备另见报告，不包含 GPU 合成，也不代表长时间稳定性。字体材质与句子缓冲另有开销；其他网易云版本、多屏和 30 分钟稳定性仍沿用原验证边界。

## 2026-10-07：增加内置和自定义效果预设

### 改动

- 新增 `presets.py`：安静办公／轻快律动内置只读方案，版本化 JSON 原子保存、完整视觉组合、同名保护、更新／删除、损坏文件保留；旧方案新增字段使用默认值，设置数值归一化复用 `settings.py`。
- `controls.py` 新增预设选择、另存、更新和删除入口，覆盖与删除确认，手动调整标记已修改；一次性应用与保存，缺失字体回退并提示，保留显示区域／偏移／音量／预览背景。预设包含默认关闭的 `singing_sync` 数据字段，其开关及绘制在下一项交付。
- 新增 `tests/test_presets.py`，扩展界面测试、`validation.py`，更新说明和验证记录。静音检查使用独立 `smoke-effect-presets.json`，不操作个人方案。

### 测试与验证

- Windows `.venv/Scripts/python.exe -m unittest discover -s tests -v`：108 项全部通过；覆盖原子替换失败、损坏／未知版本原文件不变、完整组合重启恢复、同名与内置保护、确认取消、更新删除、一次刷新及缺失字体回退。
- Windows `main.py --smoke --report-dir artifacts/presets-source-150`：全部通过；两个预设实际窗口截图、完整方案再加载、独立设置保留、暂停时切换及默认／最小窗口可访问。已查看原生预设面板截图。

### 影响与限制

- 内置方案不会覆盖当前设置，需手动选择；自定义方案保存在设置目录 `effect-presets.json`，包含字体家族名称，不重复打包字体文件。正式打包沿用整个设置目录保留流程。
- 损坏方案文件会保留且禁止覆盖写入，内置方案仍可用。演唱同步字段默认关闭，本次未改变歌曲或逐字时间处理。

## 2026-10-07：开放动画速度、抖动频率和跌落距离

### 改动

- `settings.py`、`lrc.py`、`glyph_motion.py`、`overlay.py` 新增并使用入场／退场速度 25–300%、抖动频率 1–15 次／秒、32px 基准跌落距离 0–128px；默认 100%／100%／6／48 保留原时序与运动。短句和结束边界继续压缩时长。
- `controls.py` 提供滑块与数值配对，禁用当前动画不适用的参数，动画、参数、深浅预览和重播归于同一分组；`animation.py`、`text_effects.py` 计入最大自定义跌落距离。扩展 `validation.py` 和界面测试，新增 `tests/test_effect_parameters.py`；更新使用说明和验证记录。

### 测试与验证

- Windows `.venv/Scripts/python.exe -m unittest discover -s tests -v`：100 项全部通过，覆盖旧配置、范围、速度反比、密集／空白／结束、确定性采样、零距离淡出及最大跌落高分屏边界。
- Windows `main.py --smoke --report-dir artifacts/parameters-source-150`：全部检查通过，实际 DPR 1.5；参数保存、暂停时修改不移动进度、默认／最小窗口滚动访问通过。四模式 P95 为 3.318／3.299／3.722／3.692ms，均低于 33ms。
- 独立网易云数据探测 `artifacts/word-data-probe/run-probe.ps1`：7 项宿主进度／暂停／跳转／切歌检查通过；探测到英文歌曲原生 YRC，数据保存在忽略的诊断目录。未修改插件或正式设置。

### 影响与限制

- 本次提交只交付参数；效果预设和演唱同步随后独立提交。跌落距离按实际字号缩放，速度较慢时仍受歌词边界限制；逐字时间不参与本次动画计算。
- 无新增运行依赖；首次受限环境测试无法完成字体文件替换和本机连接，已在正常 Windows 权限下重新运行全部测试通过。新增控件通过滚动访问。

## 2026-10-07：增加四种逐字歌词动画与重播预览

### 改动

- [设置](settings.py)新增 `animation_style`，提供波纹·波动、波纹·抖动、跌落·波动、跌落·抖动；旧配置和无效值仍使用原有效果。[面板](controls.py)增加歌词动画选择、独立重播预览，将跳动幅度改名为律动幅度；立即保存，隐藏或滚动不可见时停止预览刷新。
- 新增 [字符运动模块](glyph_motion.py)，按歌曲位置计算逐字透明度与运动，保持暂停、跳转和确定性随机颤动。通常 700ms 入场、下一句开始时 600ms 退场，密集歌词压缩；波动频率 1.5Hz，抖动每秒 6 次平滑采样。跌落按字号加速下移并旋转，整句倾斜时仍沿屏幕竖直方向。
- [时间轴](lrc.py)增加入场结束和退场起点；新模式长句保持到下一条标签，空白及结束边界前退出，未知时长最后一句沿用 6 秒兜底。[桌面层](overlay.py)共享字符状态，不叠加原整句渐隐，不改变播放控制或网易云协议。
- [文字效果](text_effects.py)缓存完整字符材质后统一施加逐字透明度，分层排除白芯下的邻字光晕，复用句子缓冲与光晕缓存。白芯发光、经典纯色和导入字体均可组合。[布局](animation.py)计入颤动、跌落、字符旋转及光晕；空格只保留宽度，极窄区域长句必要时取消句子倾斜。
- 新增 [动画测试](tests/test_glyph_motion.py)与 [性能验证器](animation_validation.py)，扩展 [界面测试](tests/test_controls.py)、[静音检查](validation.py)、[入口](main.py)、[网易云检查](netease_validation.py)、[外观验证器](effect_validation.py)，提供 `--animations-smoke`。
- 新增 [原生录制](tools/record_animations.py)及 [动图编码](tools/encode_animation_recording.py)，更新使用说明、网易云说明、产品设计、技术文档和验证记录；重新打包，插件 0.1.2 无需重装。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：94 项全部通过，新增覆盖四模式顺序、短句／单字／密集歌词、空格与组合字符、长停留、多行、空白及最后一句、确定性噪声、零幅度、竖直跌落、像素透明度、白芯、经典填充、自定义字体外伸、缓冲复用、暂停／往返跳转、保存及可见预览计时器。测试发现的空格替代字形和极窄区域长句运动余量问题已修正后复验。
- Windows 源码 `main.py --smoke --font-smoke-file <夹具> --report-dir artifacts/animations-source-<比例>`：100%／125%／150% 全部通过，分别使用 TTF／TTC／OTF，实际 DPR 为 1.0、约 1.25、1.5。进程缩放因子 0.6666666667／0.8333333333／1，未改系统比例；默认及最小窗口新控件可滚动访问、底栏完整，静音解码、暂停、跳转、恢复及结束清理通过。
- 51 字符双句、整屏透明画布、各 90 帧暖缓存绘制，按波纹·波动／波纹·抖动／跌落·波动／跌落·抖动顺序，P95：100% 为 `2.770 / 3.573 / 5.179 / 4.899ms`；125% 为 `5.065 / 5.154 / 6.823 / 6.858ms`；150% 为 `4.034 / 4.333 / 4.536 / 4.846ms`。全部低于 33ms，暖帧不生成新光晕。
- `.\build.ps1 -SkipDependencies` 通过，旧包为 `artifacts/previous-package-20261007-134824-197`。`.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\animations-launcher"` 退出码 0，原生面板可见，全部检查通过；最终包四模式 P95 为 `4.383 / 4.376 / 4.996 / 5.263ms`。
- `artifacts/netease-probe/run-fonts-regression.ps1 -ReportName animations-netease-live -Effects -Animations`：23 项桌面／字体／外观／动画检查、7 项宿主播放检查及 3 项实际鼠标入口检查全部通过；45 秒采集 189 个样本、10 次重定位，最高平滑能量 0.0714。四模式切换保存不改变播放锚点及状态；跌落·抖动参与随后真实暂停、跳转、连续三次切歌、最小化继续和断连清理。切换到《Value》《我们终会在大地深处重逢 (feat. 诗岸)》《Sinos De Natal》，宿主进度与歌词匹配正常，没有额外跳歌；同次四模式 P95 为 `7.661 / 6.616 / 7.131 / 7.545ms`。
- 录制实际 Windows Qt 预览窗口 165 帧，DPR 1.5，原生可见性为真；本机已有 Pillow 编码并重新打开四份 GIF，各为 151 个合并后帧、5.5 秒，保留平均 30fps 时钟。输出为 `artifacts/animations-demo`。已查看退场中间帧、125% 最小窗口及默认面板截图，光晕和控件无裁切、矩形底色或遮挡。
- 正常设置 SHA-256 前后保持 `8B191C98DB9E5456AB7489FFB7AB3872B95255A120F1D02DD883DC7D8462B645`，连接配置散列、字体目录一致，证明为 `artifacts/animations-preservation.json`。已恢复原网易云及新版后台引擎正常启动，无调试端口；文档收尾后单独运行文档校验。

### 影响与限制

- 默认动画保持原样，四种新效果需手动选择；字体、颜色与纯音乐流程保留。逐字入场属于句级视觉编排，尚未接入逐字演唱时间或精准节拍。
- 无新增应用运行依赖；Pillow 只用于开发录制输出。64MiB 限额仍针对共享光晕图像，当前字符材质与句子缓冲另有开销。
- 性能为本机暖缓存软件绘制，包含整屏清空和合成，不包含 GPU／桌面合成。首次字形冷准备另见报告；长期稳定性、多屏和其他网易云版本的验证范围未扩大。

## 2026-10-07：增加白芯彩色描边与柔和发光效果

### 改动

- [设置](settings.py)新增 `text_style` 和 `glow_strength`，默认白芯发光与 60% 强度；保留经典纯色。原颜色在新模式用作描边及同色光晕，字芯固定白色；旧配置保留原值并补齐新默认。
- [控制面板](controls.py)加入样式、描边颜色、0–100% 发光强度及白芯提示；经典模式恢复文字颜色并禁用强度。中英文预览共用实际绘制，默认深色背景，可切换浅色；背景只影响预览，不保存或改变桌面。
- 新增 [共享效果模块](text_effects.py)，用现有 NumPy 做字形 alpha 的分离式高斯模糊，缓存上限 64MiB，按实际路径、字体、字号、颜色及设备像素比分组。32px 下外露描边约 1.2px，光晕支撑约 8px，按字号缩放；强度为 0 保留字芯和描边。
- [桌面层](overlay.py)复用逐句透明缓冲，依次绘制所有光晕、描边和白芯，再统一施加淡出与总体透明度；每帧清空缓冲，避免染色、透明度叠加和残影。[布局](animation.py)计入光晕、实际图像舍入边界及动画余量，缩放改变时清理缓存。跳动、倾斜、歌曲时钟和纯音乐处理沿用原逻辑。
- 新增 [效果与性能验证器](effect_validation.py)、[像素测试](tests/test_text_effects.py)，扩展 [面板测试](tests/test_controls.py)、[配置测试](tests/test_core.py)与 [本地静音检查](validation.py)。[入口](main.py)和 [网易云检查](netease_validation.py)增加可选 `--effects-smoke`，检查播放中的设置与同步状态。
- 更新 [使用说明](README.md)、[网易云说明](NETEASE.md)、[产品设计](产品设计方案.md)、[技术文档](技术文档.md)和 [验证记录](验证记录.md)，重新打包引擎；现有插件 `0.1.2` 无需修改。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：最终 75 项全部通过，覆盖白芯与边色、光晕梯度及强度、相邻字重叠、整句透明度、经典样式、残影清理、缓存命中与限额、细笔画、自定义字体外伸、缩放失效、布局边界、保存及旧配置。文档收尾后另行运行文档校验。
- 普通沙箱下原有字体原子移动与本机 WebSocket 测试受 Windows 权限限制；在真实 Windows 环境复验后全部通过。静音验证器补齐已保存经典样式／零强度时的控件默认同步，并增加对应回归测试。
- 源码 `main.py --smoke --font-smoke-file <夹具> --report-dir artifacts/glow-source-<比例>`：100% 使用 TTF、125% 使用 TTC、150% 使用 OTF，三个报告全部通过。100%／125% 分别设置进程 `QT_SCALE_FACTOR=0.6666666667`／`0.8333333333`，实际设备比例为 1.0、约 1.25、1.5，未改系统比例。默认及小窗口控件可滚动访问，底栏可见，暂停、恢复、跳转及结束清理通过。
- 51 字符双句、整屏透明画布的 90 帧暖缓存软件绘制 P95：源码 100% 为 `4.398ms`、125% 为 `4.626ms`、150% 为 `6.785ms`，均小于 33ms。150% 缓存图像约 `1,267,040` 字节，暖帧无需重新生成光晕。
- `.\build.ps1 -SkipDependencies`：原生助手及 PyInstaller 构建通过。改动前包保留在 `artifacts/previous-package-20261007-124509-361`，最终构建前中间包为 `artifacts/previous-package-20261007-124954-595`。最终构建只额外更新本地验证器默认同步逻辑，发光、播放和网易云代码与已联动验证版本一致。
- `.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\glow-launcher-final"`：最终包实际入口退出码 0，面板 Windows 原生可见，全部静音检查通过。最终包暖缓存中位数 `6.288ms`、P95 `6.667ms`，冷准备 `23.078ms`。
- `artifacts/netease-probe/run-fonts-regression.ps1 -ReportName glow-netease-live -Effects`：18 项桌面／字体／发光检查、7 项宿主播放检查、3 项真实鼠标入口检查全部通过。45 秒采集 214 个样本、10 次重定位，最高平滑声音强度 `0.11`；播放中的样式切换和强度保存不改变同步锚点、歌曲与播放状态，暂停画面冻结、跳转、连续三次切歌、最小化继续及退出清理正常。该次暖缓存 P95 `11.877ms`，仍低于目标。
- 已查看深浅背景发光示例、150% 默认面板和 125% 小窗口截图，字芯、细描边与柔光清楚，新控件和底栏无遮挡。最终包 `glow-dark.png`、`glow-light.png` 使用独立粉色示例设置；正常颜色未被替换。
- 构建、联动及最终正常恢复后，用户 `settings.ini` SHA-256 仍为 `F1458570A9FD07A80953C98B3CA5345CDF01997D17334CD185134707BFE86754`，桥接配置散列一致，个人字体目录前后相同。证明见 `artifacts/glow-preservation.json` 及 `artifacts/glow-netease-live/settings-preservation.json`。已恢复原网易云及后台引擎正常启动，不带调试端口。

### 影响与限制

- 首次读取旧配置默认启用白芯发光；原颜色、字体、字号及其他设置保留，后续保存时写入两项新字段，可随时切回经典样式。光晕亮度不随音乐闪烁，运动仍由原歌曲时间及声音强度驱动。
- 无新增运行依赖。64MiB 限额针对共享缓存中的光晕图像，不代表整个程序内存上限；另有当前句子缓冲、路径和 Qt 界面开销。
- 性能数据为本机软件绘制测量，包含整屏透明画布和逐句合成，不包含 GPU／桌面合成，也不声明整机帧率。实测环境仍为网易云 `3.1.41.205529`、BetterNCM `1.3.4` 和 Windows 本机；长期稳定性及跨显示器动态体验范围未扩大。

## 2026-10-07：增加歌词字体选择与个人字体导入

### 改动

- [歌词效果面板](controls.py)增加“歌词字体”、中英文预览及“导入字体”，提供原有微软雅黑、宋体和楷体。选择立即应用并自动保存，预览与桌面文字使用相同字形布局。
- 新增 [字体库](fonts.py)，支持 TTF、OTF、TTC；通过 Qt 验证字体后按内容散列原子保存到 `.state/fonts`，重启时加载副本，移动原文件不影响使用。处理重复文件、损坏字体、导入失败及失效选择回退；TTC 中各家族分别加入列表。
- [设置](settings.py)新增 `font_family`，旧配置默认微软雅黑并保留其他值。[布局](animation.py)同时计算实际字形外伸范围，避免个人字体笔画越界；字体改变清理缓存，界面主题与歌词颜色保持独立。纯音乐及无歌词处理沿用原逻辑。
- 更新 [入口](main.py)、[本地验证器](validation.py)、[网易云验证器](netease_validation.py)，隔离正常与验证字体目录，增加可选 `--font-smoke-file`。新增 [字体测试](tests/test_fonts.py)、[原创夹具](tests/fixtures/README.md)及 [夹具生成器](tools/make_test_font.py)，扩展 [界面](tests/test_controls.py)、[配置](tests/test_core.py)和 [联动](tests/test_netease.py)回归测试。
- 更新 [使用说明](README.md)、[网易云说明](NETEASE.md)、[技术文档](技术文档.md)和 [验证记录](验证记录.md)，重新打包桌面引擎。网易云插件仍为 `0.1.2`，此次无需更新客户端或插件。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：59 项全部通过，覆盖三款预置字体、保存及重建面板、取消与无效导入、字体副本重载、重复导入、复制失败清理、TTC 多家族、OTF CFF 轮廓、字形外伸、旧配置和无歌词保持空白。文档收尾后另行运行文档校验。
- `.\.venv\Scripts\python.exe main.py --smoke --font-smoke-file tests/fixtures/lyrics-test.ttf --report-dir artifacts/fonts-source-150`：源码 Windows 静音检查通过。另以 `QT_SCALE_FACTOR=0.6666666667` 和 `0.8333333333` 验证 100% 与 125%；125% 使用 TTC 夹具。三个实际比例为 1.0、约 1.25、1.5，字体实际家族、三种歌词画面、默认及最小窗口可达性均通过。报告在 `artifacts/fonts-source-100`、`fonts-source-125`、`fonts-source-150`。
- `.\build.ps1 -SkipDependencies`：原生音频助手与 PyInstaller 构建通过。改动前包备份为 `artifacts/previous-package-20261007-000046-775`，最终构建前的中间包为 `artifacts/previous-package-20261007-000916-125`；正常 `.state` 保留。
- `.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\fonts-launcher-final"`：实际启动入口退出码 0，Windows 面板原生可见，最终打包版全部静音检查通过。最终 EXE 以 `--smoke --font-smoke-file tests/fixtures/lyrics-test.otf --report-dir artifacts/fonts-packaged-otf` 启动也全部通过，确认真实 OTF 导入、保存与副本重载。
- `artifacts/netease-probe/run-fonts-regression.ps1`：最终 `netease-report.json` 13 项桌面、字体与设置窗口检查、`host-report.json` 7 项宿主播放检查、`settings-clicks.json` 3 项真实鼠标检查全部通过。45 秒采集 218 个样本、12 次重定位，最高平滑声音强度 `0.1266`。播放时完成预置字体切换及导入，耗时与进度增加均为 735 毫秒，同步锚点、歌曲编号和播放状态未改变；覆盖暂停、跳转、连续三次切歌、最小化和退出清理。
- 首轮字体联动的固定时间差检查误将正常播放前进判为跳转，已改为验证同步锚点和状态不被修改，并增加接受正常前进、拒绝主动跳转的两项回归测试。一次真实鼠标复验未打开窗口；验证辅助脚本改为在窗口恢复后重新测量 CEF 按钮坐标，再次复验通过。首轮报告保留在 `artifacts/fonts-netease-first-run`。
- 已查看 150% 默认、小窗口及最终网易云字体设置截图，字体选择、导入按钮、预览和固定底栏完整，其他设置可滚动访问。原九项用户设置值保持一致，仅新增默认 `font_family`；证明见 `artifacts/fonts-update-settings-preservation.json`。最终联动前后正常设置 SHA-256 一致，见 `artifacts/fonts-netease-live/settings-preservation.json`；连接配置散列不变，正常字体库未混入测试夹具。原网易云已恢复正常启动，不带验证调试端口。

### 影响与限制

- 宋体、楷体引用本机系统字体，不分发 Windows 字体文件；字体未安装时标为不可用。个人字体仅加载到本程序并保存副本，不安装到系统；同一家族仅显示一次，使用常规字重，缺字继续由 Qt 回退。
- 验证字体采用项目原创矩形字形，仅用于测试，正常模式不加载它们。fontTools 仅供开发者重建夹具，应用无需新增依赖。
- 本次实测仍为 Windows 本机、网易云 `3.1.41.205529` 与 BetterNCM `1.3.4`；没有扩大对其他客户端、长时间稳定性或跨显示器动态缩放的验证范围。纯音乐维持原样。

## 2026-10-06：修复后台设置窗口右键无反馈

### 改动

- 用户反馈右键“跳动的词”没有反应。真实鼠标跟踪确认右键处理和打开请求均已执行，但后台启动的 Qt 面板在 Windows 原生状态中仍隐藏；直接调用原生窗口恢复后能够显示。
- [控制面板](controls.py)打开时增加 Windows 原生恢复、置前和可见状态日志，处理后台隐藏和最小化；新增 `show_effects()`，由 [联动入口](main.py)将插件的设置请求直接送到“歌词效果”页。
- [网易云插件](plugins/netease/index.js)保留右键入口，并在开关旁新增可左键点击的“设置”按钮。阻止设置点击传播，连接断开时允许显式重启引擎，连接恢复后补发打开请求；打开设置不会改变歌词开关。[插件清单](plugins/netease/manifest.json)升级至 `0.1.2`。
- 扩展 [面板测试](tests/test_controls.py)和 [插件测试](tests/test_netease_plugin.cjs)，覆盖隐藏及最小化恢复、页面选择、播放状态不变、两个设置入口、断线启动和补发请求。[真实联动验证器](netease_validation.py)新增可选 `--settings-smoke` 检查，要求效果页原生可见；此模式不自动显示面板，避免掩盖后台启动问题。
- 更新 [使用说明](README.md)、[网易云说明](NETEASE.md)和 [验证记录](验证记录.md)，重新打包引擎并更新本机插件。保留原 `.state`、网易云和 BetterNCM 框架。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：44 项全部通过，包含新增窗口恢复测试及扩展插件设置入口回归检查；文档更新后另行运行文档校验。
- `.\.venv\Scripts\python.exe main.py --smoke --report-dir artifacts/netease-settings-local-smoke`：源码 Windows 静音播放、动画、窗口和布局检查通过。
- `.\build.ps1 -SkipDependencies`：原生音频助手与 PyInstaller 打包通过；最终构建前的包保存在 `artifacts/previous-package-20261006-184534-637`，修复前的包保存在 `artifacts/previous-package-20261006-184015-885`。
- `.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\netease-settings-launcher"`：实际启动入口面板原生可见，打包版全部静音检查通过。
- `.\.venv\Scripts\python.exe tools\package_netease.py` 生成 `0.1.2` 插件包，已更新 `C:\betterncm\plugins\FloatingLyrics.plugin`。修复前插件备份为 `artifacts/netease-settings-fix-20261006-184706/FloatingLyrics.plugin`。
- `artifacts/netease-probe/run-settings-regression.ps1`：后台冷启动后，真实鼠标右键首次打开效果窗口通过；再次将窗口原生隐藏后，真实鼠标左键“设置”恢复窗口通过。`artifacts/netease-settings-live/settings-clicks.json` 三项检查全部为真。验证脚本等待客户端按钮就绪，并将尚未创建原生窗口的后台状态视为隐藏，不依赖预先打开面板。
- 同次验证的 `host-report.json` 7 项宿主播放检查、`netease-report.json` 10 项桌面与设置窗口检查全部通过。45 秒采集 217 个样本，9 次重定位，最高平滑声音强度 `0.1738`；包含暂停冻结、跳转、连续三次切歌、最小化继续同步及退出网易云清除歌词。
- 已查看 `netease-settings.png`，确认真实打开“歌词效果”页，150% 比例下字号、颜色和透明度控件显示完整，剩余效果可滚动访问。原用户设置 SHA-256 前后一致，记录在 `artifacts/netease-settings-live/settings-preservation.json`；最终恢复原网易云正常启动，关闭验证调试端口。

### 影响与限制

- 设置入口仍使用独立桌面效果面板；歌词透明层继续鼠标穿透。窗口恢复遵循 Windows 前台激活规则，不更改全局焦点策略。
- 本次实测网易云 `3.1.41.205529`、BetterNCM `1.3.4` 和本机 Windows；其他客户端版本及长期运行仍需另行验证。截图使用独立验证设置，正常用户偏好未被替换。

## 2026-10-06：修复网易云进度冻结并补齐切歌验证

### 改动

- 用户反馈网易云进度条停止、音乐和歌词仍播放，以及切歌跳过。确认旧 [适配器](plugins/netease/adapter.js)通过独立 `window.legacyNativeCmder` 注册 `PlayProgress`、`Seek`，其回调表与客户端播放器分离，可能覆盖客户端的原生事件槽，使网易云自身收不到进度和跳转完成事件。
- 改为订阅客户端已加载模块导出的 `audioPlayerPlayProgress$`、`audioPlayerSeek$`，复用播放器自己的事件实例；保留暂停迟到事件和歌曲编号过滤，隔离插件处理异常，卸载页面时只取消本插件的订阅。[插件入口](plugins/netease/index.js)接入新订阅方式，[清单](plugins/netease/manifest.json)升级为 `0.1.1`。
- 扩展适配器、插件生命周期测试，新增 [宿主回调隔离测试](tests/test_netease_host.cjs)与 [宿主验证器测试](tests/test_netease_host_validation.cjs)，纳入 [自动测试](tests/test_netease.py)。新增 [真实宿主验证工具](tools/verify_netease_host.mjs)，直接检查网易云进度条、暂停、跳转及连续切歌；外部驱动计时，兼容客户端旧 Chromium。
- 更新 [网易云说明](NETEASE.md)与 [验证记录](验证记录.md)。原桌面引擎不变，重新生成并安装插件包，保留原框架、客户端版本和用户配置。

### 测试与验证

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`：43 项通过。新增回归检查覆盖宿主回调不被覆盖、连续换歌后的事件过滤、插件异常不阻断宿主、退订不删除宿主回调，以及验证器能识别进度冻结和未经操作的跳歌。
- `.\.venv\Scripts\python.exe main.py --smoke --report-dir artifacts/netease-progress-local-smoke`：原本地播放和桌面动画的 Windows 静音集成验证通过。
- `.\启动.bat -Smoke -ReportDirectory "$PWD\artifacts\netease-progress-launcher"`：退出码 0，实际入口面板可见，打包版静音集成检查全部通过。
- `node tools/verify_netease_host.mjs artifacts/netease-host-regression`：真实网易云宿主 7 项检查通过，连续播放包含《感官过载》在内的多首歌曲，进度持续移动，切歌后没有再次跳过所选歌曲，歌词所属歌曲正确。
- `artifacts/netease-probe/run-progress-regression.ps1`：已安装 `0.1.1` 与原客户端联合检查通过，`artifacts/netease-progress-live/host-report.json` 的 7 项宿主检查、`netease-report.json` 的 9 项桌面检查全部通过。45 秒采集 220 个样本、10 次进度重定位，最高平滑声音强度约 `0.096`；覆盖暂停画面冻结、最小化后继续同步、退出网易云后清除歌词及不创建第二个播放器。
- 已查看修复后网易云及歌词面板截图。正常用户设置 SHA-256 前后一致，记录为 `artifacts/netease-progress-live/settings-preservation.json`。原有插件备份在 `artifacts/netease-progress-fix-20261006-174417/FloatingLyrics.plugin`；最终已恢复原网易云正常启动，不带调试端口，实际加载的适配器与项目源码 SHA-256 一致。

### 影响与限制

- 之前的 9 项桌面检查仅覆盖歌词引擎，没有检查网易云自身进度条及连续切歌，未能发现此次宿主干扰；本次增加独立宿主验证。
- 仍仅适配网易云 `3.1.41.205529`、BetterNCM `1.3.4`。验证覆盖本机多首歌曲与短时操作，不代表全部歌曲版权、网络状态或长期稳定性均已验证。

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
