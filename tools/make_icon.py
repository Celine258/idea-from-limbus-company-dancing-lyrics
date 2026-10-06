import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from controls import app_icon

app = QApplication([])
target = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
target.parent.mkdir(parents=True, exist_ok=True)
if not app_icon().pixmap(64, 64).save(str(target), "ICO"):
    raise SystemExit("Cannot save application icon")
