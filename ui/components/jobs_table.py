"""
جدول المهام - Jobs Table
يعرض قائمة المهام المجدولة وحالتها
Displays list of scheduled jobs and their status
"""

from typing import Optional, Dict, Any, Callable
import time

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

# Import from parent modules
from ui.helpers import create_icon_action, HAS_QTAWESOME


# Colors for job states (from admin.py constants)
COUNTDOWN_COLOR_GREEN = "#4CAF50"  # أخضر
COUNTDOWN_COLOR_YELLOW = "#FF9800"  # برتقالي/أصفر
COUNTDOWN_COLOR_RED = "#F44336"  # أحمر
COUNTDOWN_COLOR_GRAY = "#9E9E9E"  # رمادي

# Remaining time constants (from admin.py)
REMAINING_TIME_RUNNING = "🔴 جاري الرفع..."
REMAINING_TIME_NOT_SCHEDULED = "---"


class JobsTable(QTableWidget):
    """
    جدول عرض المهام المجدولة
    Table widget for displaying scheduled jobs
    """
    
    # Signals
    job_selected = Signal(object)  # عند اختيار مهمة - When job is selected
    job_deleted = Signal(object)  # عند حذف مهمة - When job is deleted
    job_double_clicked = Signal(object)  # عند النقر المزدوج - When job is double clicked
    job_enabled_toggled = Signal(object, bool)  # عند تفعيل/تعطيل - When job is enabled/disabled
    job_schedule_toggled = Signal(object, bool)  # عند بدء/إيقاف الجدولة - When schedule is toggled
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_table()
        
        # Connect internal signals
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
    
    def _setup_table(self):
        """إعداد الجدول - Setup table columns and headers"""
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "الصفحة",         # Column 0 - Page name
            "التطبيق",        # Column 1 - App name
            "المجلد",         # Column 2 - Folder path
            "الحالة",         # Column 3 - Status (enabled/disabled)
            "الجدولة",        # Column 4 - Schedule status
            "الوقت المتبقي"   # Column 5 - Remaining time
        ])
        
        # Table settings
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.setLayoutDirection(Qt.RightToLeft)  # RTL support for Arabic
        
        # Column widths
        self.setColumnWidth(0, 180)  # Page name
        self.setColumnWidth(1, 100)  # App name
        self.setColumnWidth(2, 180)  # Folder
        self.setColumnWidth(3, 70)   # Status
        self.setColumnWidth(4, 80)   # Schedule
        self.setColumnWidth(5, 120)  # Remaining time
        
        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
    
    def add_job(self, job_data: Any) -> int:
        """
        إضافة مهمة جديدة - Add new job to table
        
        Args:
            job_data: Job object containing all job information
        
        Returns:
            Row index where the job was added
        """
        row = self.rowCount()
        self.insertRow(row)
        
        # Column 0: Page name
        page_item = QTableWidgetItem(job_data.page_name)
        page_item.setTextAlignment(Qt.AlignCenter)
        page_item.setData(Qt.UserRole, job_data)  # Store job in item data
        self.setItem(row, 0, page_item)
        
        # Column 1: App name
        app_name = getattr(job_data, 'app_name', None) or "غير محدد"
        app_item = QTableWidgetItem(app_name)
        app_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 1, app_item)
        
        # Column 2: Folder (shortened path for better display)
        folder_path = job_data.folder or ""
        if len(folder_path) > 30:
            folder_display = "..." + folder_path[-27:]
        else:
            folder_display = folder_path
        folder_item = QTableWidgetItem(folder_display)
        folder_item.setTextAlignment(Qt.AlignCenter)
        folder_item.setToolTip(folder_path)  # Full path as tooltip
        self.setItem(row, 2, folder_item)
        
        # Column 3: Status (enabled/disabled)
        status = "مفعّل" if job_data.enabled else "معطّل"
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)
        # Color coding
        if job_data.enabled:
            status_item.setForeground(QColor(COUNTDOWN_COLOR_GREEN))
        else:
            status_item.setForeground(QColor(COUNTDOWN_COLOR_RED))
        self.setItem(row, 3, status_item)
        
        # Column 4: Schedule status
        if not job_data.enabled:
            schedule = "معطّل"
            schedule_color = QColor(COUNTDOWN_COLOR_GRAY)
        elif job_data.is_scheduled:
            schedule = "مجدول"
            schedule_color = QColor(COUNTDOWN_COLOR_GREEN)
        else:
            schedule = "غير مجدول"
            schedule_color = QColor(COUNTDOWN_COLOR_YELLOW)
        schedule_item = QTableWidgetItem(schedule)
        schedule_item.setTextAlignment(Qt.AlignCenter)
        schedule_item.setForeground(schedule_color)
        self.setItem(row, 4, schedule_item)
        
        # Column 5: Remaining time
        remaining_text = self._format_remaining_time(job_data)
        remaining_item = QTableWidgetItem(remaining_text)
        remaining_item.setTextAlignment(Qt.AlignCenter)
        remaining_item.setForeground(self._get_remaining_time_color(remaining_text))
        self.setItem(row, 5, remaining_item)
        
        return row
    
    def update_job_status(self, job_data: Any):
        """
        تحديث حالة المهمة - Update job status in table
        
        Args:
            job_data: Job object to update
        """
        # Find the row with this job
        for row in range(self.rowCount()):
            page_item = self.item(row, 0)
            if page_item and page_item.data(Qt.UserRole) == job_data:
                # Update status column
                status_item = self.item(row, 3)
                if status_item:
                    status = "مفعّل" if job_data.enabled else "معطّل"
                    status_item.setText(status)
                    if job_data.enabled:
                        status_item.setForeground(QColor(COUNTDOWN_COLOR_GREEN))
                    else:
                        status_item.setForeground(QColor(COUNTDOWN_COLOR_RED))
                
                # Update schedule column
                schedule_item = self.item(row, 4)
                if schedule_item:
                    if not job_data.enabled:
                        schedule_item.setText("معطّل")
                        schedule_item.setForeground(QColor(COUNTDOWN_COLOR_GRAY))
                    elif job_data.is_scheduled:
                        schedule_item.setText("مجدول")
                        schedule_item.setForeground(QColor(COUNTDOWN_COLOR_GREEN))
                    else:
                        schedule_item.setText("غير مجدول")
                        schedule_item.setForeground(QColor(COUNTDOWN_COLOR_YELLOW))
                
                # Update remaining time
                remaining_text = self._format_remaining_time(job_data)
                remaining_item = self.item(row, 5)
                if remaining_item:
                    remaining_item.setText(remaining_text)
                    remaining_item.setForeground(self._get_remaining_time_color(remaining_text))
                
                break
    
    def update_all_countdowns(self):
        """تحديث جميع العدادات - Update all countdown timers"""
        for row in range(self.rowCount()):
            page_item = self.item(row, 0)
            if not page_item:
                continue
            
            job_data = page_item.data(Qt.UserRole)
            if not job_data:
                continue
            
            self.update_job_status(job_data)
    
    def remove_job(self, job_data: Any):
        """
        حذف مهمة - Remove job from table
        
        Args:
            job_data: Job object to remove
        """
        for row in range(self.rowCount()):
            page_item = self.item(row, 0)
            if page_item and page_item.data(Qt.UserRole) == job_data:
                self.removeRow(row)
                self.job_deleted.emit(job_data)
                break
    
    def get_selected_job(self) -> Optional[Any]:
        """
        جلب المهمة المحددة - Get selected job data
        
        Returns:
            Job object or None if no selection
        """
        current_row = self.currentRow()
        if current_row < 0:
            return None
        
        page_item = self.item(current_row, 0)
        if page_item:
            return page_item.data(Qt.UserRole)
        return None
    
    def clear_all(self):
        """مسح جميع المهام - Clear all jobs from table"""
        self.setRowCount(0)
    
    def _format_remaining_time(self, job_data: Any) -> str:
        """
        حساب وتنسيق الوقت المتبقي للوظيفة
        Calculate and format remaining time for job
        
        Args:
            job_data: Job object
        
        Returns:
            Formatted remaining time string
        """
        # If job is disabled or not scheduled, return ---
        if not job_data.enabled or not job_data.is_scheduled:
            return REMAINING_TIME_NOT_SCHEDULED
        
        # Calculate remaining time
        next_run = getattr(job_data, 'next_run_timestamp', None)
        if next_run is None:
            return REMAINING_TIME_NOT_SCHEDULED
        
        remaining_seconds = int(next_run - time.time())
        
        # If time has passed
        if remaining_seconds <= 0:
            return REMAINING_TIME_RUNNING
        
        # Convert seconds to hours:minutes:seconds
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60
        
        if hours > 0:
            return f"⏰ {hours}:{minutes:02d}:{seconds:02d}"
        elif minutes > 0:
            return f"⏰ {minutes}:{seconds:02d}"
        else:
            return f"⏰ 0:{seconds:02d}"
    
    def _get_remaining_time_color(self, remaining_text: str) -> QColor:
        """
        الحصول على لون الوقت المتبقي حسب الحالة
        Get color for remaining time based on status
        
        Args:
            remaining_text: Remaining time text
        
        Returns:
            QColor for appropriate color
        """
        if remaining_text == REMAINING_TIME_RUNNING:
            return QColor(COUNTDOWN_COLOR_YELLOW)
        elif remaining_text == REMAINING_TIME_NOT_SCHEDULED:
            return QColor(COUNTDOWN_COLOR_GRAY)
        else:
            return QColor(COUNTDOWN_COLOR_GREEN)
    
    def _on_cell_double_clicked(self, row: int, column: int):
        """Handle double click on table cell"""
        page_item = self.item(row, 0)
        if page_item:
            job_data = page_item.data(Qt.UserRole)
            if job_data:
                self.job_double_clicked.emit(job_data)
    
    def _show_context_menu(self, position):
        """
        عرض قائمة السياق عند النقر بالزر الأيمن
        Show context menu on right-click
        """
        # Get the clicked row
        row = self.rowAt(position.y())
        if row < 0:
            return
        
        page_item = self.item(row, 0)
        if not page_item:
            return
        
        job_data = page_item.data(Qt.UserRole)
        if not job_data:
            return
        
        menu = QMenu(self)
        
        # Enable/Disable options
        if job_data.enabled:
            disable_action = create_icon_action('تعطيل', 'close', self)
            disable_action.triggered.connect(lambda: self._toggle_enabled(job_data, False))
            menu.addAction(disable_action)
        else:
            enable_action = create_icon_action('تفعيل', 'check', self)
            enable_action.triggered.connect(lambda: self._toggle_enabled(job_data, True))
            menu.addAction(enable_action)
        
        menu.addSeparator()
        
        # Schedule options (only for enabled jobs)
        if job_data.enabled:
            if job_data.is_scheduled:
                stop_schedule_action = create_icon_action('إيقاف الجدولة', 'pause', self)
                stop_schedule_action.triggered.connect(lambda: self._toggle_schedule(job_data, False))
                menu.addAction(stop_schedule_action)
            else:
                start_schedule_action = create_icon_action('تشغيل الجدولة', 'play', self)
                start_schedule_action.triggered.connect(lambda: self._toggle_schedule(job_data, True))
                menu.addAction(start_schedule_action)
        
        menu.addSeparator()
        
        # Delete job
        delete_action = create_icon_action('حذف الوظيفة', 'delete', self)
        delete_action.triggered.connect(lambda: self.remove_job(job_data))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def _toggle_enabled(self, job_data: Any, enabled: bool):
        """Toggle job enabled status"""
        self.job_enabled_toggled.emit(job_data, enabled)
    
    def _toggle_schedule(self, job_data: Any, scheduled: bool):
        """Toggle job schedule status"""
        self.job_schedule_toggled.emit(job_data, scheduled)
