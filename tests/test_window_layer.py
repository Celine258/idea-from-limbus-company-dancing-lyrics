import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import unittest
from PySide6.QtCore import QObject
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from window_layer import TopmostGuard

APP = QApplication.instance() or QApplication([])


class Widget(QObject):
    visible = True
    handle = 12
    def isVisible(self): return self.visible
    def winId(self): return self.handle


class Layer:
    def __init__(self):
        self.applied, self.needed, self.closed = [], False, False
    def watch(self, notify): self.notify = notify; self.closed = False
    def needs_repair(self, *_): return self.needed
    def apply(self, hwnd): self.applied.append(hwnd); self.needed = False
    def close(self): self.closed = True


class WindowLayerTests(unittest.TestCase):
    def test_visible_overlay_recovers_foreign_window_without_repeated_raises(self):
        widget, backend = Widget(), Layer()
        guard = TopmostGuard(widget, backend)
        try:
            guard.start()
            self.assertEqual(backend.applied, [12])
            backend.needed = True
            for _ in range(30): backend.notify(90)
            QTest.qWait(100)
            self.assertEqual(backend.applied, [12,12])
            guard._repair()
            self.assertEqual(backend.applied, [12,12])
        finally:
            guard.stop()

    def test_hiding_cancels_repair_and_handle_changes_use_current_window(self):
        widget, backend = Widget(), Layer()
        guard = TopmostGuard(widget, backend)
        try:
            guard.start()
            backend.needed = True
            backend.notify(90)
            widget.visible = False
            guard.stop()
            QTest.qWait(100)
            self.assertEqual(backend.applied, [12])
            self.assertTrue(backend.closed)
            self.assertFalse(guard.watchdog.isActive())
            widget.handle, widget.visible = 34, True
            guard.start()
            self.assertEqual(backend.applied, [12,34])
        finally:
            guard.stop()
