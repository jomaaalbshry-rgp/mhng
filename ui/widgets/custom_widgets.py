"""
Custom Widgets for Page Management Application

This module contains custom Qt widgets that disable mouse wheel scrolling
when the widget doesn't have focus. This prevents accidental changes when
scrolling through the UI.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSpinBox, QDoubleSpinBox, QSlider


class NoScrollComboBox(QComboBox):
    """كومبو بوكس بدون تغيير بعجلة الماوس."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class NoScrollSpinBox(QSpinBox):
    """سبين بوكس بدون تغيير بعجلة الماوس."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """دبل سبين بوكس بدون تغيير بعجلة الماوس."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


class NoScrollSlider(QSlider):
    """سلايدر بدون تغيير بعجلة الماوس ومتوافق مع RTL."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        # جعل الشريط متوافق مع RTL - الأكبر على اليسار والأصغر على اليمين
        self.setInvertedAppearance(True)
    
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)
