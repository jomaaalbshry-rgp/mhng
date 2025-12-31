"""
Statistics Tab - تبويب الإحصائيات
Contains upload statistics and charts.
"""

import threading
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)

from services import get_upload_stats, reset_upload_stats, generate_text_chart
from ui.helpers import create_icon_button, get_icon, ICONS, ICON_COLORS, HAS_QTAWESOME


class StatsTab(QWidget):
    """
    تبويب الإحصائيات
    Statistics tab showing upload history and stats.
    """
    
    # Signals
    refresh_requested = Signal()
    log_message = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """بناء واجهة الإحصائيات"""
        layout = QVBoxLayout(self)
        
        # مجموعة إحصائيات الرفع
        stats_group = self._build_stats_group()
        layout.addWidget(stats_group)
        
        # الرسم البياني الأسبوعي
        weekly_group = self._build_weekly_chart_group()
        layout.addWidget(weekly_group)
        
        # جدول آخر الرفع
        recent_group = self._build_recent_uploads_group()
        layout.addWidget(recent_group)
        
        layout.addStretch()
    
    def _build_stats_group(self) -> QGroupBox:
        """بناء مجموعة إحصائيات الرفع"""
        stats_group = QGroupBox('إحصائيات الرفع')
        stats_form = QFormLayout()
        
        # إحصائيات عامة
        self.stats_total_label = QLabel('0')
        stats_form.addRow('إجمالي الرفع:', self.stats_total_label)
        
        self.stats_success_label = QLabel('0')
        stats_form.addRow('الناجحة:', self.stats_success_label)
        
        self.stats_failed_label = QLabel('0')
        stats_form.addRow('الفاشلة:', self.stats_failed_label)
        
        # معدل النجاح
        self.stats_success_rate_label = QLabel('0%')
        stats_form.addRow('معدل النجاح:', self.stats_success_rate_label)
        
        stats_group.setLayout(stats_form)
        return stats_group
    
    def _build_weekly_chart_group(self) -> QGroupBox:
        """بناء مجموعة الرسم البياني الأسبوعي"""
        weekly_group = QGroupBox('الإحصائيات الأسبوعية')
        if HAS_QTAWESOME:
            weekly_group.setTitle('')
        weekly_layout = QVBoxLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            weekly_title_row = QHBoxLayout()
            weekly_icon_label = QLabel()
            weekly_icon_label.setPixmap(get_icon(ICONS['chart'], ICON_COLORS.get('chart')).pixmap(16, 16))
            weekly_title_row.addWidget(weekly_icon_label)
            weekly_title_row.addWidget(QLabel('الإحصائيات الأسبوعية'))
            weekly_title_row.addStretch()
            weekly_layout.addLayout(weekly_title_row)
        
        self.weekly_chart_text = QTextEdit()
        self.weekly_chart_text.setReadOnly(True)
        self.weekly_chart_text.setMaximumHeight(200)
        self.weekly_chart_text.setStyleSheet('font-family: monospace; font-size: 12px;')
        weekly_layout.addWidget(self.weekly_chart_text)
        
        weekly_group.setLayout(weekly_layout)
        return weekly_group
    
    def _build_recent_uploads_group(self) -> QGroupBox:
        """بناء مجموعة آخر الفيديوهات المرفوعة"""
        recent_group = QGroupBox('آخر الفيديوهات المرفوعة')
        recent_layout = QVBoxLayout()
        
        self.recent_uploads_table = QTableWidget()
        self.recent_uploads_table.setColumnCount(4)
        self.recent_uploads_table.setHorizontalHeaderLabels(['الملف', 'الصفحة', 'التاريخ', 'الحالة'])
        self.recent_uploads_table.horizontalHeader().setStretchLastSection(True)
        self.recent_uploads_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        recent_layout.addWidget(self.recent_uploads_table)
        
        # صف الأزرار (تحديث وتصفير)
        buttons_row = QHBoxLayout()
        
        refresh_btn = create_icon_button('تحديث الإحصائيات', 'refresh')
        refresh_btn.clicked.connect(self.refresh_stats)
        buttons_row.addWidget(refresh_btn)
        
        reset_btn = create_icon_button('تصفير الإحصائيات', 'delete')
        reset_btn.clicked.connect(self._reset_stats)
        buttons_row.addWidget(reset_btn)
        
        recent_layout.addLayout(buttons_row)
        
        recent_group.setLayout(recent_layout)
        return recent_group
    
    def refresh_stats(self):
        """تحديث الإحصائيات من قاعدة البيانات."""
        stats = get_upload_stats(days=30)
        
        self.stats_total_label.setText(str(stats.get('total', 0)))
        self.stats_success_label.setText(str(stats.get('successful', 0)))
        self.stats_failed_label.setText(str(stats.get('failed', 0)))
        
        # معدل النجاح
        success_rate = stats.get('success_rate', 0)
        self.stats_success_rate_label.setText(f'{success_rate:.1f}%')
        
        # الرسم البياني الأسبوعي
        weekly_stats = stats.get('weekly_stats', {})
        if weekly_stats:
            chart = generate_text_chart(weekly_stats)
            self.weekly_chart_text.setText(chart)
        else:
            self.weekly_chart_text.setText('لا توجد بيانات للأسبوع الماضي')
        
        # تحديث جدول آخر الرفع
        recent = stats.get('recent', [])
        self.recent_uploads_table.setRowCount(len(recent))
        
        for row, item in enumerate(recent):
            file_name, page_name, video_url, uploaded_at, status = item
            self.recent_uploads_table.setItem(row, 0, QTableWidgetItem(file_name or ''))
            self.recent_uploads_table.setItem(row, 1, QTableWidgetItem(page_name or ''))
            self.recent_uploads_table.setItem(row, 2, QTableWidgetItem(uploaded_at or ''))
            status_text = '✅ نجح' if status == 'success' else '❌ فشل'
            self.recent_uploads_table.setItem(row, 3, QTableWidgetItem(status_text))
        
        self.refresh_requested.emit()
    
    def _reset_stats(self):
        """تصفير الإحصائيات بعد تأكيد المستخدم."""
        reply = QMessageBox.question(
            self,
            'تأكيد التصفير',
            'هل أنت متأكد من تصفير جميع الإحصائيات؟\nلا يمكن التراجع عن هذا الإجراء.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # تشغيل العملية في خيط منفصل لمنع تجميد الواجهة
            def do_reset():
                try:
                    if reset_upload_stats():
                        # استخدام signal لتحديث الواجهة من الخيط الرئيسي
                        self.log_message.emit('✅ تم تصفير الإحصائيات بنجاح')
                        # تأخير قصير ثم تحديث العرض
                        QTimer.singleShot(100, self.refresh_stats)
                    else:
                        self.log_message.emit('❌ فشل تصفير الإحصائيات')
                except Exception as e:
                    self.log_message.emit(f'❌ خطأ: {e}')
            
            threading.Thread(target=do_reset, daemon=True).start()
    
    def update_stats(self, stats: dict):
        """تحديث الإحصائيات من بيانات معطاة"""
        self.stats_total_label.setText(str(stats.get('total', 0)))
        self.stats_success_label.setText(str(stats.get('successful', 0)))
        self.stats_failed_label.setText(str(stats.get('failed', 0)))
        
        success_rate = stats.get('success_rate', 0)
        self.stats_success_rate_label.setText(f'{success_rate:.1f}%')
        
        weekly_stats = stats.get('weekly_stats', {})
        if weekly_stats:
            chart = generate_text_chart(weekly_stats)
            self.weekly_chart_text.setText(chart)
        else:
            self.weekly_chart_text.setText('لا توجد بيانات للأسبوع الماضي')
        
        recent = stats.get('recent', [])
        self.recent_uploads_table.setRowCount(len(recent))
        
        for row, item in enumerate(recent):
            file_name, page_name, video_url, uploaded_at, status = item
            self.recent_uploads_table.setItem(row, 0, QTableWidgetItem(file_name or ''))
            self.recent_uploads_table.setItem(row, 1, QTableWidgetItem(page_name or ''))
            self.recent_uploads_table.setItem(row, 2, QTableWidgetItem(uploaded_at or ''))
            status_text = '✅ نجح' if status == 'success' else '❌ فشل'
            self.recent_uploads_table.setItem(row, 3, QTableWidgetItem(status_text))
