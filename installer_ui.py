"""Small native installer window, also available from the frozen application."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel, QLineEdit,
                              QPushButton, QFileDialog, QHBoxLayout)
from app_info import APP_NAME, APP_VERSION
from netease_install import NeteaseInstaller, find_client, default_profile, atomic_write


class InstallWorker(QThread):
    completed = Signal(object, object)

    def __init__(self, installer, action, client, profile, framework, parent=None):
        super().__init__(parent)
        self.installer, self.action = installer, action
        self.client, self.profile, self.framework = client, profile, framework

    def run(self):
        try:
            result = (self.installer.install(self.client, self.profile, self.framework) if self.action == "install"
                      else self.installer.uninstall(self.client, self.profile))
            self.completed.emit(result, None)
        except Exception as error:
            self.completed.emit(None, error)


class InstallerWindow(QDialog):
    def __init__(self, installer, args):
        super().__init__()
        self.installer, self.args = installer, args
        self.worker = None
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} · 网易云联动")
        self.resize(600, 380)
        layout = QVBoxLayout(self)
        heading = QLabel("卸载网易云联动" if args.uninstall_netease else "安装网易云联动")
        heading.setStyleSheet("font-size:22px;font-weight:bold")
        layout.addWidget(heading)
        tip = QLabel("请先完全退出网易云（包括托盘）。自动识别 3.1.40.205461／3.1.41.205529 x64。\n安装成功后重新打开网易云，点击播放栏的“都市回响”。\n请将完整程序放在长期保留且可写的目录，安装后不要移动它。")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        try:
            saved = json.loads((installer.state / "netease-install.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        self.client = QLineEdit(str(args.client_directory or saved.get("client") or find_client() or ""))
        self.add_path(layout, "网易云目录", self.client, True)
        self.profile = QLineEdit(str(args.profile_directory or saved.get("profile") or default_profile()))
        self.profile.setToolTip("建议保留默认 C:\\betterncm；插件数据目录请使用英文路径。歌词程序目录可含中文。")
        self.add_path(layout, "BetterNCM 数据目录", self.profile, True)
        self.framework = QLineEdit(str(args.framework_dll or ""))
        self.framework.setPlaceholderText("可选；缺少框架时从官方自动下载并校验")
        if not args.uninstall_netease:
            self.add_path(layout, "本地框架 DLL（可选）", self.framework, False)
        self.status = QLabel("卸载仅移除本插件，保留个人设置、字体、预设及共用框架。" if args.uninstall_netease else "准备就绪。安装失败可在此查看原因并重试。")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.apply = QPushButton("卸载联动" if args.uninstall_netease else "安装联动")
        self.apply.clicked.connect(self.start)
        layout.addWidget(self.apply)
        self.admin = QPushButton("以管理员身份重试")
        self.admin.clicked.connect(self.elevate)
        self.admin.hide()
        layout.addWidget(self.admin)
        self.setStyleSheet(self.styleSheet() + "QPushButton{padding:8px} QLineEdit{padding:6px}")

    def add_path(self, layout, title, editor, directory):
        layout.addWidget(QLabel(title))
        row = QHBoxLayout()
        row.addWidget(editor)
        browse = QPushButton("选择")
        def select():
            value = (QFileDialog.getExistingDirectory(self, title, editor.text()) if directory else
                     QFileDialog.getOpenFileName(self, title, editor.text(), "DLL (*.dll)")[0])
            if value:
                editor.setText(value)
        browse.clicked.connect(select)
        row.addWidget(browse)
        layout.addLayout(row)

    def start(self):
        if not self.client.text().strip() or not self.profile.text().strip():
            self.status.setText("请选择网易云目录及 BetterNCM 数据目录。")
            return
        self.apply.setEnabled(False)
        self.admin.hide()
        self.client.setEnabled(False)
        self.profile.setEnabled(False)
        self.framework.setEnabled(False)
        self.status.setText("正在检查并处理，请稍候……")
        self.worker = InstallWorker(self.installer, "uninstall" if self.args.uninstall_netease else "install",
                                    Path(self.client.text()), Path(self.profile.text()),
                                    Path(self.framework.text()) if self.framework.text() else None, self)
        self.worker.completed.connect(self.complete)
        self.worker.start()

    def complete(self, result, error):
        self.worker.wait()
        self.apply.setEnabled(True)
        for editor in (self.client, self.profile, self.framework):
            editor.setEnabled(True)
        if error:
            self.status.setText(str(error) + ("\n目录需要写入权限，请点击管理员重试。" if isinstance(error, PermissionError) else ""))
            self.admin.setVisible(isinstance(error, PermissionError) and not self.args.installer_elevated)
        else:
            self.status.setText("卸载完成。请重新启动网易云。个人设置和共用框架已保留。" if self.args.uninstall_netease else "安装完成！请重新启动网易云，在播放栏点击“都市回响”，右键或点击“设置”调整效果。")

    def elevate(self):
        arguments = ["--uninstall-netease" if self.args.uninstall_netease else "--install-netease",
                     "--installer-elevated", "--client-directory", self.client.text(),
                     "--profile-directory", self.profile.text()]
        if self.framework.text():
            arguments += ["--framework-dll", self.framework.text()]
        if not getattr(sys, "frozen", False):
            arguments.insert(0, str(Path(__file__).parent / "main.py"))
        shell = ctypes.windll.shell32.ShellExecuteW
        shell.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
        shell.restype = ctypes.c_void_p
        result = shell(None, "runas", sys.executable, subprocess.list2cmdline(arguments), str(self.installer.app_dir), 1)
        if result and result > 32:
            self.accept()
        else:
            self.status.setText("管理员授权未完成。你可以再次重试，或将程序解压到个人可写目录。")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            event.ignore()
        else:
            event.accept()


def run_installer(args, app_dir, templates):
    installer = NeteaseInstaller(app_dir, templates)
    # Explicit automation mode for isolated native verification; normal BAT always shows the window.
    if args.installer_report:
        try:
            if not args.client_directory or not args.profile_directory:
                raise ValueError("自动验证需要明确指定两个目录。")
            result = (installer.uninstall(args.client_directory, args.profile_directory) if args.uninstall_netease else
                      installer.install(args.client_directory, args.profile_directory, args.framework_dll))
            report, code = {"passed": True, "result": result}, 0
        except Exception as error:
            report, code = {"passed": False, "error": str(error)}, 1
        atomic_write(args.installer_report, json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))
        return code
    app = QApplication(sys.argv[:1])
    from controls import app_icon
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(True)
    window = InstallerWindow(installer, args)
    window.show()
    return app.exec()
