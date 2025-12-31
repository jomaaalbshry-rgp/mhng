"""
عارض السجلات - Log Viewer
يعرض سجلات النظام والأحداث
Displays system logs and events
"""

from typing import Optional
from enum import Enum
from datetime import datetime

from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtCore import Qt


class LogLevel(Enum):
    """مستويات السجلات - Log levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    DEBUG = "debug"


class LogViewer(QTextEdit):
    """
    عارض السجلات مع دعم الألوان والمستويات
    Log viewer with color coding and log levels
    """
    
    # Log level colors (matching admin.py theme)
    LOG_COLORS = {
        LogLevel.INFO: QColor("#2196F3"),      # Blue
        LogLevel.WARNING: QColor("#FF9800"),   # Orange
        LogLevel.ERROR: QColor("#F44336"),     # Red
        LogLevel.SUCCESS: QColor("#4CAF50"),   # Green
        LogLevel.DEBUG: QColor("#9E9E9E"),     # Gray
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        
        # Enable text wrapping
        self.setLineWrapMode(QTextEdit.WidgetWidth)
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO, include_timestamp: bool = True):
        """
        إضافة سجل جديد - Add new log entry
        
        Args:
            message: Log message to display
            level: Log level (INFO, WARNING, ERROR, SUCCESS, DEBUG)
            include_timestamp: Whether to include timestamp prefix
        """
        # Format timestamp if requested
        if include_timestamp:
            timestamp = self._format_timestamp()
            full_message = f"[{timestamp}] {message}"
        else:
            full_message = message
        
        # Append message with color
        self._append_colored_text(full_message, level)
        
        # Auto-scroll to bottom
        self._scroll_to_bottom()
    
    def log_info(self, message: str):
        """Log info message - رسالة معلومات"""
        self.log(message, LogLevel.INFO)
    
    def log_warning(self, message: str):
        """Log warning message - رسالة تحذير"""
        self.log(message, LogLevel.WARNING)
    
    def log_error(self, message: str):
        """Log error message - رسالة خطأ"""
        self.log(message, LogLevel.ERROR)
    
    def log_success(self, message: str):
        """Log success message - رسالة نجاح"""
        self.log(message, LogLevel.SUCCESS)
    
    def log_debug(self, message: str):
        """Log debug message - رسالة تصحيح"""
        self.log(message, LogLevel.DEBUG)
    
    def clear_logs(self):
        """مسح السجلات - Clear all logs"""
        self.clear()
    
    def _format_timestamp(self) -> str:
        """
        تنسيق الطابع الزمني - Format timestamp for log entry
        
        Returns:
            Formatted timestamp string (12-hour format)
        """
        now = datetime.now()
        # 12-hour format with AM/PM in Arabic
        hour = now.hour
        am_pm = "م" if hour >= 12 else "ص"  # م = مساءً (PM), ص = صباحاً (AM)
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        return f"{hour_12:02d}:{now.minute:02d}:{now.second:02d} {am_pm}"
    
    def _append_colored_text(self, text: str, level: LogLevel):
        """
        إضافة نص ملون للسجل
        Append colored text to log
        
        Args:
            text: Text to append
            level: Log level for color coding
        """
        # Get color for this log level
        color = self.LOG_COLORS.get(level, QColor("#e6e6e6"))
        
        # Save current format
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Create format with color
        char_format = QTextCharFormat()
        char_format.setForeground(color)
        
        # Insert colored text
        cursor.insertText(text + "\n", char_format)
    
    def _scroll_to_bottom(self):
        """التمرير التلقائي للأسفل - Auto-scroll to bottom"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
