# 变更记录

每次改动按日期追加记录，包含改动目的、涉及文件、测试与验证结果、影响或已知限制。

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
