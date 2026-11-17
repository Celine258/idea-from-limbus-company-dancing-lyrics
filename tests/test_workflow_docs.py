"""Validate the deliverable documentation and the source-control boundary."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = tuple(ROOT / name for name in ("AGENTS.md", "CHANGELOG.md", "README.md", "验证记录.md", "NETEASE.md",
                                         "产品设计方案.md", "技术文档.md", "THIRD_PARTY_NOTICES.md",
                                         "docs/传播文案.md", "release/release-notes.md", "MACOS.md",
                                         "release/macos/release-notes.md", "QQMUSIC.md",
                                         "docs/QQ歌词缓存研究.md", "docs/客户端兼容维护.md", "KUGOU-MACOS.md"))


class WorkflowDocumentationTests(unittest.TestCase):
    def test_qq_autostart_release_describes_opt_in_disable_reuse_and_update(self):
        from app_info import APP_VERSION
        guide = (ROOT/'QQMUSIC.md').read_text(encoding='utf-8')
        for phrase in ('随 QQ 音乐启动', '默认关闭', 'Windows 登录', '托盘', '已有歌词实例会复用',
                       '关闭开关', '约 2 秒', '手动退出', '重开 QQ 音乐', '移动目录', '效果预设',
                       '无需管理员权限', '260 字符', f'v{APP_VERSION}'):
            self.assertIn(phrase, guide)
        package_guide = (ROOT/'release/qqmusic/使用说明.txt').read_text(encoding='utf-8')
        for phrase in ('随 QQ 音乐启动', '默认关闭', '关闭开关', '本版 ZIP', '移动完整目录'):
            self.assertIn(phrase, package_guide)
        readme = (ROOT/'README.md').read_text(encoding='utf-8')
        introduction = readme.split('**使用 QQ 音乐**', 1)[1].split('**使用网易云音乐**', 1)[0]
        for phrase in ('首次双击', '当前音乐 → QQ 音乐自动联动 → 随 QQ 音乐启动', '默认关闭',
                       'Windows 登录', '系统托盘', '已有窗口', '更新或删除前', '移动目录', '.state'):
            self.assertIn(phrase, introduction)
        notes = (ROOT/'release/release-notes.md').read_text(encoding='utf-8')
        for text in (guide, package_guide, introduction, notes):
            self.assertNotIn('本地设计预览', text)
            self.assertNotIn('尚未发布', text)
        self.assertIn('随 QQ 音乐启动', notes)

    def test_readme_highlights_cache_first_support_and_latency_limits_in_qq_intro(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        introduction = text.split("**使用 QQ 音乐**", 1)[1].split("**使用网易云音乐**", 1)[0]
        self.assertIn("> [!IMPORTANT]", introduction)
        for phrase in ("新版已接入本地缓存优先", "联网搜索歌曲再获取歌词", "已缓存的歌曲",
                       "首次播放或没有缓存", "不是切歌到歌词显示的总延迟", "不能保证所有歌曲",
                       "本地缓存优先、现有官方接口兜底", "docs/QQ歌词缓存研究.md"):
            self.assertIn(phrase, introduction)
        for phrase in ('选择歌词缓存目录','20 秒','22ms','非零外层偏移'):
            self.assertIn(phrase,introduction)

    def test_qq_22_75_guides_explain_single_package_and_opened_state(self):
        for name in ('README.md', 'QQMUSIC.md', 'release/qqmusic/使用说明.txt', 'release/release-notes.md'):
            text = (ROOT/name).read_text(encoding='utf-8')
            for phrase in ('22.52／22.75', '无需选择客户端版本', 'Opened', '系统媒体控制'):
                self.assertIn(phrase, text)

    def test_qq_autostart_release_evidence_keeps_native_and_playback_scope_explicit(self):
        data = json.loads((ROOT/'docs/research/qq-autostart-release-20261011.json').read_text(encoding='utf-8'))
        self.assertEqual(data['app_version'], '0.7.0-beta.5')
        self.assertEqual(data['environment']['qq_music'], '22.75')
        native = data['native_autostart']
        self.assertTrue(native['passed'])
        self.assertEqual(len(native['checks']), 14)
        self.assertTrue(all(native['checks'].values()))
        self.assertEqual(native['playback_commands'], 0)
        live = data['real_qq_22_75']
        self.assertFalse(live['simulated_data'])
        self.assertTrue(all(live['checks'].values()))
        self.assertGreater(live['word_intervals'], 0)
        self.assertEqual(live['latency_sample_count'], 1)
        self.assertFalse(live['real_seek_or_switch_verified'])
        self.assertEqual(data['layout']['checks'], 18)
        self.assertTrue(data['layout']['enabled_status_is_fixture'])
        self.assertEqual(data['preserved_user_files'], 8)
        for report in data['public_packages'].values():
            self.assertTrue(report['passed'])
            self.assertFalse(report['clean_machine'])
        for archive in data['archives']:
            self.assertRegex(archive['sha256'], r'^[0-9a-f]{64}$')
        self.assertIn('windows_logoff_or_reboot', data['not_verified'])
        self.assertNotIn('decoded_text', json.dumps(data))
        from PySide6.QtGui import QImageReader
        image = QImageReader(str(ROOT/'docs/images/qqmusic-autostart.png')).read()
        self.assertFalse(image.isNull())
        self.assertGreaterEqual(image.width(), 900)
        self.assertGreaterEqual(image.height(), 560)

    def test_qq_decoder_mit_attributions_and_cache_guides_are_shipped(self):
        license_text = (ROOT/'release/licenses/qq-qrc-MIT.txt').read_text(encoding='utf-8')
        for phrase in ('MIT','2026 valenbine','2023 WXRIW','Permission is hereby granted'):
            self.assertIn(phrase,license_text)
        notices = (ROOT/'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
        self.assertIn('release/licenses/qq-qrc-MIT.txt',notices)
        self.assertIn('2cc0e67dcfc567a122ebb953ef696783a6760d17',notices)
        for name in ('QQMUSIC.md','release/qqmusic/使用说明.txt'):
            text = (ROOT/name).read_text(encoding='utf-8')
            for phrase in ('QQMusicLyricNew','真实字词时间','整句 LRC','20 秒','自动查找缓存'):
                self.assertIn(phrase,text)

    def test_qq_cache_research_distinguishes_measurement_and_product_support(self):
        text = (ROOT / "docs/QQ歌词缓存研究.md").read_text(encoding="utf-8")
        for phrase in ("本轮只做研究", "首次播放写盘延迟", "非零偏移尚未验证", "第二台电脑",
                       "无法唯一确认", "尚未接入缓存", "GPL-3.0-only", "MIT", "1.262–3.845ms"):
            self.assertIn(phrase, text)
        self.assertIn("docs/QQ歌词缓存研究.md", (ROOT / "QQMUSIC.md").read_text(encoding="utf-8"))

    def test_qq_cache_research_evidence_is_consistent_and_excludes_lyrics(self):
        data = json.loads((ROOT / "docs/research/qq-cache-20261011.json").read_text(encoding="utf-8"))
        self.assertEqual(data["scope"], "research_only")
        self.assertEqual(data["cache"]["decoded_files"], 2 * len(data["songs"]))
        self.assertEqual(data["cache"]["failed_files"], 0)
        self.assertEqual(data["cache"]["network_requests"], 0)
        self.assertEqual(data["observation"]["playback_commands"], 0)
        self.assertTrue(data["observation"]["unique_filename_match"])
        for song in data["songs"]:
            self.assertGreater(song["original_time_tags"], 0)
            self.assertGreater(song["word_intervals"], 0)
            self.assertEqual(song["aligned_original_lines_10ms"], song["original_time_tags"])
            self.assertTrue(song["original_hash_unchanged"])
            self.assertEqual(song["invalid_word_starts"], 0)
            self.assertRegex(song["original_sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse({"text", "lyrics", "decoded_text", "cookie", "token"} & song.keys())
        self.assertEqual(len(data["warm_benchmarks"]), 4)
        for sample in data["warm_benchmarks"]:
            self.assertEqual(sample["runs"], 100)
            self.assertLessEqual(sample["median_ms"], sample["p95_ms"])
            self.assertLessEqual(sample["p95_ms"], sample["max_ms"])
        self.assertTrue(all(item["rejected"] for item in data["negative_checks"]))
        for field in ("first_load_write_latency", "nonzero_offset", "second_machine", "memory_reader", "packaged_integration"):
            self.assertFalse(data["validated"][field])

    def test_qq_cache_product_evidence_is_separate_from_historical_research(self):
        data = json.loads((ROOT/'docs/research/qq-cache-product-20261011.json').read_text(encoding='utf-8'))
        self.assertEqual(data['scope'],'product_cache_integration')
        self.assertEqual(data['app_version'],'0.7.0-beta.4')
        self.assertEqual(data['decoder']['original_files'],14)
        self.assertEqual(data['decoder']['valid_word_intervals'],3910)
        self.assertTrue(data['decoder']['identical_to_mit_reference'])
        self.assertFalse(data['live']['simulated_data'])
        self.assertEqual(data['live']['network_requests'],0)
        self.assertGreater(data['live']['word_intervals'],0)
        self.assertTrue(all(data['live']['checks'].values()))
        for archive in data['archives']:
            self.assertRegex(archive['sha256'],r'^[0-9a-f]{64}$')
            self.assertIn(data['app_version'],archive['filename'])
        self.assertFalse(data['qq_public_zip']['clean_machine'])
        self.assertIn('client_first_load_write_latency',data['not_verified'])
        self.assertNotIn('decoded_text',json.dumps(data))

    def test_mac_download_guides_distinguish_architecture_dependency_and_validation(self):
        from tools.package_macos import MAC_RELEASE_TAG, archive_name
        for name in ("README.md", "MACOS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for arch in ("arm64", "x86_64"):
                self.assertIn(f"releases/download/{MAC_RELEASE_TAG}/{archive_name(arch)}", text)
            self.assertIn("Homebrew", text)
            self.assertIn("nowplaying-cli", text)
            self.assertIn("不需要安装 Python", text)
        guide = (ROOT / "MACOS.md").read_text(encoding="utf-8")
        self.assertIn("尚未完成 macOS 真机播放", guide)
        self.assertIn("没有 Apple Developer ID", guide)
        self.assertIn("~/Library/Application Support/CityEchoes/", guide)

    def test_brand_name_and_existing_plugin_identity(self):
        from app_info import APP_NAME
        self.assertEqual(APP_NAME, "都市回响")
        self.assertTrue((ROOT / "README.md").read_text(encoding="utf-8").startswith(f"# {APP_NAME}\n"))
        manifest = json.loads((ROOT / "plugins/netease/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], APP_NAME)
        self.assertEqual(manifest["slug"], "floating-lyrics", "改名不能变成另一个安装实例")
        launcher = (ROOT / "start.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("".join(f"\\u{ord(char):04x}" for char in APP_NAME), launcher,
                      "原生启动器必须匹配新窗口名称")

    def test_carmen_guide_describes_fixed_palette_and_retained_original_color(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("卡门的声音", "固定暖白字芯与琥珀金光晕", "原有自定义颜色会保留", "效果预设保存"):
            self.assertIn(phrase, text)
        for phrase in ("有中文翻译时优先显示译文", "无中文翻译", "不套用原文逐字时间", "独立于效果预设"):
            self.assertIn(phrase, text)
        from PySide6.QtGui import QImageReader
        fingerprints = []
        for background in ("dark", "light"):
            relative = f"docs/images/carmen-{background}.png"
            self.assertIn(f"]({relative})", text)
            reader = QImageReader(str(ROOT / relative))
            image = reader.read()
            self.assertFalse(image.isNull(), reader.errorString())
            self.assertGreaterEqual(image.width(), 700)
            self.assertGreaterEqual(image.height(), 200)
            fingerprints.append(hashlib.sha256(image.constBits()).digest())
        self.assertNotEqual(*fingerprints, "深浅背景预览应为不同的实际渲染图片")

    def test_readme_embeds_desktop_recording_before_download_link(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        image = re.search(r"!\[([^\]]+)\]\((docs/images/lyrics-demo\.gif)\)", text)
        self.assertIsNotNone(image, "首页需要内嵌演示，而不是只提供文件链接")
        self.assertIn("实机演示", image.group(1))
        self.assertLess(image.start(), text.index("下载 Windows x64 正式版"))
        self.assertTrue((ROOT / image.group(2)).is_file())

    def test_readme_gif_decodes_complete_recording_and_loops(self):
        from PySide6.QtGui import QImageReader

        path = ROOT / "docs/images/lyrics-demo.gif"
        self.assertLess(path.stat().st_size, 8 * 1024 * 1024, "避免首页演示文件过大")
        reader = QImageReader(str(path))
        self.assertTrue(reader.supportsAnimation())
        self.assertEqual(reader.loopCount(), -1, "演示需要无限循环播放")
        count = reader.imageCount()
        self.assertGreater(count, 100, "必须保留完整动画，不能退化为静态图片")
        width, height = reader.size().width(), reader.size().height()
        self.assertGreaterEqual(width, 640)
        self.assertLessEqual(width, 1280)
        self.assertAlmostEqual(width / height, 16 / 9)
        duration = 0
        frame_hashes = set()
        for frame in range(count):
            decoded = reader.read()
            self.assertFalse(decoded.isNull(), f"第 {frame} 帧解码失败：{reader.errorString()}")
            self.assertEqual((decoded.width(), decoded.height()), (width, height))
            delay = reader.nextImageDelay()
            self.assertGreater(delay, 0)
            duration += delay
            frame_hashes.add(hashlib.sha256(decoded.constBits()).digest())
        self.assertGreaterEqual(duration, 18_000)
        self.assertLessEqual(duration, 19_000)
        self.assertGreater(len(frame_hashes), 10, "录屏需要有实际画面变化")

    def test_current_guides_describe_all_themes_and_runtime_icon_scope(self):
        from app_info import APP_VERSION
        for name in ("README.md", "NETEASE.md", "产品设计方案.md", "技术文档.md"):
            with self.subTest(document=name):
                text = (ROOT / name).read_text(encoding="utf-8-sig")
                self.assertIn(APP_VERSION, text)
                for theme in ("默认主题", "深色主题", "特殊主题", "但丁钟头", "托盘"):
                    self.assertIn(theme, text)
        guide = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        self.assertIn("EXE 文件图标仍为原图标", guide)
        self.assertIn("固定快捷方式由 Windows 管理", guide)

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows 启动脚本语法验证")
    def test_launcher_diagnostic_wait_is_bounded_and_powershell_syntax_valid(self):
        script = ROOT / "start.ps1"
        text = script.read_text(encoding="utf-8-sig")
        self.assertIn("$taskWatch.ElapsedMilliseconds -lt 30000", text)
        self.assertIn("$taskSmokeWatch.ElapsedMilliseconds -lt 120000", text)
        self.assertIn("$taskProcess.WaitForExit(1000)", text)
        command = ("$taskTokens=$null;$taskErrors=$null;"
                   f"[System.Management.Automation.Language.Parser]::ParseFile('{str(script).replace(chr(39), chr(39)*2)}',"
                   "[ref]$taskTokens,[ref]$taskErrors)|Out-Null;"
                   "if($taskErrors.Count){$taskErrors|Out-String;exit 1}")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_documents_are_readable_and_local_links_resolve(self):
        for path in DOCUMENTS:
            with self.subTest(document=path.name):
                text = path.read_bytes().decode("utf-8-sig", errors="strict")
                self.assertTrue(text.startswith("# "))
                self.assertNotIn("\x00", text)
                self.assertNotIn("\ufffd", text)
                self.assertEqual(text.count("```") % 2, 0, "代码围栏必须配对")
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                    if "://" in target or target.startswith("#"):
                        continue
                    destination = (path.parent / target.split("#", 1)[0]).resolve()
                    self.assertTrue(destination.is_relative_to(ROOT), target)
                    self.assertTrue(destination.is_file(), f"失效的文件链接：{target}")

    def test_changelog_entries_have_date_details_validation_and_impact(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        entries = re.split(r"(?m)^## ", text)[1:]
        self.assertTrue(entries, "需要至少一条变更记录")
        for entry in entries:
            self.assertRegex(entry.splitlines()[0], r"^\d{4}-\d{2}-\d{2}[：:]\S")
            sections = {heading: body for heading, body in re.findall(
                r"(?ms)^### ([^\n]+)\n(.*?)(?=^### |\Z)", entry)}
            for heading in ("改动", "测试与验证", "影响与限制"):
                self.assertIn(heading, sections)
                self.assertTrue(sections[heading].strip(), f"{heading}不能为空")

    def test_runtime_files_ignored_and_source_files_trackable(self):
        ignored = [".venv/probe.txt", ".state/probe.txt", "build/probe.txt",
                   "dist/probe.txt", "artifacts/probe.txt", "__pycache__/probe.pyc", "debug.log"]
        sources = ["AGENTS.md", "CHANGELOG.md", "main.py", "controls.py", "validation.py", "themes.py", "app_info.py",
                   "CityEchoes.spec", "main_mac.py", "tools/build_macos.py",
                   "assets/app.ico", "assets/check-white.svg", "assets/dante-clock.svg", "assets/special-blueprint.svg",
                   "tests/test_controls.py", "tests/test_workflow_docs.py"]
        result = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "check-ignore", "--no-index", "--stdin", "-z"],
            cwd=ROOT, input="\0".join(ignored + sources) + "\0", text=True,
            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.rstrip("\0").split("\0")), set(ignored))


if __name__ == "__main__":
    unittest.main()
