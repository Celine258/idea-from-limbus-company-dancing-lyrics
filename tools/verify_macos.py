"""Launch the extracted frozen .app via LaunchServices without development PATH."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.package_macos import APP_BUNDLE, audit_archive


def verify(archive, report_dir):
    if sys.platform != "darwin":
        raise RuntimeError("Mac 成品必须在原生 macOS 验证")
    archive, report_dir = Path(archive).resolve(), Path(report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"passed": False, "archive": archive.name, "architecture": platform.machine(),
              "audit": audit_archive(archive), "live_playback_verified": False}
    with tempfile.TemporaryDirectory(prefix="都市回响 中文 path ") as temporary:
        extracted = Path(temporary)
        subprocess.run(["ditto", "-x", "-k", str(archive), str(extracted)], check=True)
        bundle = extracted / "CityEchoes" / APP_BUNDLE
        executable = bundle / "Contents/MacOS/CityEchoes"
        actual = subprocess.check_output(["lipo", "-archs", str(executable)], text=True).strip()
        if actual != platform.machine():
            raise RuntimeError(f"主程序架构不匹配：{actual}")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
        env = {k: v for k, v in os.environ.items() if k not in
               ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH")}
        env.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", QT_QPA_PLATFORM="cocoa")
        subprocess.run(["open", "-n", "-W", str(bundle), "--args", "--smoke", "--state-dir",
                        str(extracted / "独立设置"), "--report-dir", str(report_dir)], env=env, check=True, timeout=90)
        smoke = json.loads((report_dir / "smoke-report.json").read_text(encoding="utf-8"))
        report["smoke"] = smoke
        report["passed"] = smoke["passed"] and smoke["frozen"] and smoke["qt_platform"] == "cocoa"
        (report_dir / "package-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not report["passed"]:
            raise RuntimeError("Mac 原生冻结成品验证未通过")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.report_dir), ensure_ascii=False))
