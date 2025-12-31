"""
واجهة المجدول - Scheduler UI
واجهة إدارة المهام المجدولة
Scheduler user interface widget
"""

import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QMessageBox, QMenu, QSizePolicy
)
from PySide6.QtCore import Signal, Qt

from core import (
    NotificationSystem, log_info, log_debug, log_error,
    get_job_key
)
from controllers.story_controller import StoryJob
from controllers.reels_controller import ReelsJob
from controllers.video_controller import VideoJob, PageJob
from ui.components import JobsTable
from ui.helpers import create_icon_button, create_icon_action, HAS_QTAWESOME, get_icon
from ui.widgets import NoScrollSpinBox


class SchedulerUI(QWidget):
    """
    واجهة المجدول
    Scheduler user interface widget
    """
    
    # Signals
    job_scheduled = Signal(object)           # عند جدولة مهمة - When a job is scheduled  
    job_cancelled = Signal(object)           # عند إلغاء مهمة - When a job is cancelled
    scheduler_started = Signal()             # عند بدء المجدول - When scheduler starts
    scheduler_stopped = Signal()             # عند إيقاف المجدول - When scheduler stops
    save_requested = Signal()                # طلب حفظ - Save requested
    log_message = Signal(str)                # رسالة سجل - Log message
    run_job_now_requested = Signal(object)   # طلب تشغيل فوري - Run job now requested
    
    def __init__(self, parent=None):
        """
        تهيئة واجهة المجدول
        Initialize scheduler UI
        
        Args:
            parent: النافذة الأم - Parent widget
        """
        super().__init__(parent)
        
        # الخصائص - Properties
        self.jobs_map = {}          # قائمة وظائف الفيديو - Video jobs map
        self.story_jobs_map = {}    # قائمة وظائف الستوري - Story jobs map  
        self.reels_jobs_map = {}    # قائمة وظائف الريلز - Reels jobs map
        self.current_mode = 'video'  # الوضع الحالي - Current mode (video/story/reels)
        
        # Scheduler threads (will be set by parent)
        self.scheduler_thread = None
        self.story_scheduler_thread = None
        self.reels_scheduler_thread = None
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """
        إعداد الواجهة - Setup UI elements
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # مجموعة الوظائف - Jobs group
        jobs_group = QGroupBox('الوظائف')
        jobs_v = QVBoxLayout()
        
        # جدول الوظائف - Jobs table
        self.jobs_table = JobsTable()
        jobs_v.addWidget(self.jobs_table)
        
        # صف أزرار الوظائف - Job buttons row
        job_buttons_row = QHBoxLayout()
        job_buttons_row.setSpacing(5)
        job_buttons_row.setContentsMargins(0, 5, 0, 5)
        
        self.rem_btn = create_icon_button('حذف', 'delete')
        self.rem_btn.setToolTip('حذف الوظيفة المحددة')
        
        self.start_selected_btn = create_icon_button('تشغيل', 'play')
        self.start_selected_btn.setToolTip('تشغيل جدولة الوظيفة المحددة')
        
        self.stop_selected_btn = create_icon_button('إيقاف', 'stop')
        self.stop_selected_btn.setToolTip('إيقاف جدولة الوظيفة المحددة')
        
        self.schedule_all_btn = create_icon_button('جدولة الكل', 'schedule')
        self.schedule_all_btn.setToolTip('بدء جدولة جميع المهام المفعّلة')
        
        self.unschedule_all_btn = create_icon_button('إلغاء جدولة الكل', 'stop')
        self.unschedule_all_btn.setToolTip('إيقاف جدولة جميع المهام المجدولة حالياً')
        
        # إضافة الأزرار بشكل متجاوب
        buttons = [self.rem_btn, self.start_selected_btn, self.stop_selected_btn, 
                   self.schedule_all_btn, self.unschedule_all_btn]
        for btn in buttons:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumWidth(80)
            job_buttons_row.addWidget(btn, 1)
        
        jobs_v.addLayout(job_buttons_row)
        jobs_group.setLayout(jobs_v)
        layout.addWidget(jobs_group)
        
        # صف التحكم السفلي - Bottom controls
        bottom_controls = QHBoxLayout()
        
        bottom_controls.addWidget(QLabel('أقصى رفع:'))
        self.concurrent_spin = NoScrollSpinBox()
        self.concurrent_spin.setRange(1, 20)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.setToolTip('عدد الملفات التي يمكن رفعها في وقت واحد')
        bottom_controls.addWidget(self.concurrent_spin)
        
        bottom_controls.addStretch()
        layout.addLayout(bottom_controls)
    
    def _connect_signals(self):
        """
        ربط الإشارات - Connect signals
        """
        # ربط إشارات الجدول - Connect table signals
        self.jobs_table.job_double_clicked.connect(self._on_job_double_clicked)
        self.jobs_table.job_deleted.connect(self._on_job_deleted)
        self.jobs_table.job_enabled_toggled.connect(self._on_job_enabled_toggled)
        self.jobs_table.job_schedule_toggled.connect(self._on_job_schedule_toggled)
        self.jobs_table.customContextMenuRequested.connect(self._show_job_context_menu)
        
        # ربط إشارات الأزرار - Connect button signals
        self.rem_btn.clicked.connect(self.remove_job)
        self.start_selected_btn.clicked.connect(self.start_selected_job)
        self.stop_selected_btn.clicked.connect(self.stop_selected_job)
        self.schedule_all_btn.clicked.connect(self.schedule_all_jobs)
        self.unschedule_all_btn.clicked.connect(self.unschedule_all_jobs)
    
    def set_jobs_maps(self, video_jobs, story_jobs, reels_jobs):
        """
        تعيين قوائم الوظائف - Set jobs maps
        
        Args:
            video_jobs: قائمة وظائف الفيديو
            story_jobs: قائمة وظائف الستوري
            reels_jobs: قائمة وظائف الريلز
        """
        self.jobs_map = video_jobs
        self.story_jobs_map = story_jobs
        self.reels_jobs_map = reels_jobs
        self.refresh_jobs_list()
    
    def set_mode(self, mode: str):
        """
        تعيين الوضع الحالي - Set current mode
        
        Args:
            mode: الوضع (video/story/reels)
        """
        self.current_mode = mode
        self.refresh_jobs_list()
    
    def refresh_jobs_list(self):
        """تحديث جدول الوظائف بناءً على الوضع الحالي."""
        self.jobs_table.clear_all()
        
        # اختيار قائمة الوظائف حسب الوضع الحالي
        if self.current_mode == 'story':
            jobs_to_display = self.story_jobs_map.values()
        elif self.current_mode == 'reels':
            jobs_to_display = self.reels_jobs_map.values()
        else:
            jobs_to_display = self.jobs_map.values()
        
        # إضافة كل وظيفة للجدول
        for job in jobs_to_display:
            self.jobs_table.add_job(job)
    
    def update_all_countdowns(self):
        """تحديث حالات الجدولة والوقت المتبقي في الجدول."""
        self.jobs_table.update_all_countdowns()
    
    def remove_job(self):
        """حذف الوظيفة المحددة من الجدول."""
        current_row = self.jobs_table.currentRow()
        if current_row < 0:
            return
        
        page_item = self.jobs_table.item(current_row, 0)
        if page_item:
            job = page_item.data(Qt.UserRole)
            if job:
                self._delete_job_by_type(job)
        
        self.refresh_jobs_list()
        self.save_requested.emit()
    
    def _delete_job_by_type(self, job):
        """حذف وظيفة حسب نوعها."""
        job_key = get_job_key(job)
        
        if isinstance(job, StoryJob):
            if job_key in self.story_jobs_map:
                del self.story_jobs_map[job_key]
                return True
        elif isinstance(job, ReelsJob):
            if job_key in self.reels_jobs_map:
                del self.reels_jobs_map[job_key]
                return True
        else:
            if job_key in self.jobs_map:
                del self.jobs_map[job_key]
                return True
        return False
    
    def _get_selected_job_from_table(self):
        """الحصول على الوظيفة المحددة من الجدول."""
        current_row = self.jobs_table.currentRow()
        if current_row < 0:
            return None
        
        page_item = self.jobs_table.item(current_row, 0)
        if page_item:
            return page_item.data(Qt.UserRole)
        return None
    
    def start_selected_job(self):
        """تشغيل الجدولة للوظيفة المحددة."""
        job = self._get_selected_job_from_table()
        if not job:
            QMessageBox.warning(self, 'اختيار مطلوب', 'اختر وظيفة أولاً')
            return
        
        if not job.enabled:
            QMessageBox.warning(self, 'وظيفة معطّلة', 
                              'يجب تفعيل الوظيفة أولاً من القائمة السياقية (كليك يمين)')
            return
        
        # بدء الجدولة
        job.reset_next_run_timestamp()
        job.is_scheduled = True
        job.cancel_requested = False
        self.log_message.emit(f'تم تشغيل جدولة الوظيفة: {job.page_name} (سيبدأ العدّاد)')
        
        # إرسال إشارة بدء الجدولة
        self.job_scheduled.emit(job)
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def stop_selected_job(self):
        """إيقاف الجدولة للوظيفة المحددة."""
        job = self._get_selected_job_from_table()
        if not job:
            QMessageBox.warning(self, 'اختيار مطلوب', 'اختر وظيفة أولاً')
            return
        
        if not job.is_scheduled:
            self.log_message.emit(f'الوظيفة غير مجدولة مسبقاً: {job.page_name}')
        else:
            job.is_scheduled = False
            job.cancel_requested = True
            self.log_message.emit(f'تم إيقاف جدولة الوظيفة: {job.page_name}')
            self.job_cancelled.emit(job)
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def schedule_all_jobs(self):
        """جدولة جميع المهام المفعّلة (فيديو وستوري وريلز)."""
        count = 0
        scheduled_jobs = []
        
        # جدولة وظائف الفيديو
        for job in self.jobs_map.values():
            if job.enabled and not job.is_scheduled:
                job.reset_next_run_timestamp()
                job.is_scheduled = True
                job.cancel_requested = False
                count += 1
                scheduled_jobs.append(job)
        
        # جدولة وظائف الستوري
        for job in self.story_jobs_map.values():
            if job.enabled and not job.is_scheduled:
                job.reset_next_run_timestamp()
                job.is_scheduled = True
                job.cancel_requested = False
                count += 1
                scheduled_jobs.append(job)
        
        # جدولة وظائف الريلز
        for job in self.reels_jobs_map.values():
            if job.enabled and not job.is_scheduled:
                job.reset_next_run_timestamp()
                job.is_scheduled = True
                job.cancel_requested = False
                count += 1
                scheduled_jobs.append(job)
        
        if count == 0:
            self.log_message.emit('لا توجد مهام مفعّلة غير مجدولة.')
            return
        
        # إرسال إشعار لكل مهمة مجدولة
        for job in scheduled_jobs:
            next_run = datetime.fromtimestamp(job.next_run_timestamp).strftime('%H:%M:%S')
            NotificationSystem.notify(
                lambda msg: self.log_message.emit(msg),
                NotificationSystem.SCHEDULE,
                f'تم تفعيل الجدولة - الرفع القادم: {next_run}',
                job.page_name
            )
            self.job_scheduled.emit(job)
        
        self.log_message.emit(f'📅 تم جدولة {count} مهمة.')
        
        # إرسال إشارة بدء المجدول
        self.scheduler_started.emit()
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def unschedule_all_jobs(self):
        """إلغاء جدولة جميع المهام المجدولة حالياً."""
        count = 0
        unscheduled_jobs = []
        
        # إلغاء جدولة وظائف الفيديو
        for job in self.jobs_map.values():
            if job.is_scheduled:
                job.is_scheduled = False
                job.cancel_requested = True
                count += 1
                unscheduled_jobs.append(job)
        
        # إلغاء جدولة وظائف الستوري
        for job in self.story_jobs_map.values():
            if job.is_scheduled:
                job.is_scheduled = False
                job.cancel_requested = True
                count += 1
                unscheduled_jobs.append(job)
        
        # إلغاء جدولة وظائف الريلز
        for job in self.reels_jobs_map.values():
            if job.is_scheduled:
                job.is_scheduled = False
                job.cancel_requested = True
                count += 1
                unscheduled_jobs.append(job)
        
        if count == 0:
            self.log_message.emit('لا توجد مهام مجدولة لإلغائها.')
            return
        
        # إرسال إشعار لكل مهمة تم إلغاء جدولتها
        for job in unscheduled_jobs:
            NotificationSystem.notify(
                lambda msg: self.log_message.emit(msg),
                NotificationSystem.SCHEDULE,
                'تم إيقاف الجدولة',
                job.page_name
            )
            self.job_cancelled.emit(job)
        
        self.log_message.emit(f'📅 تم إلغاء جدولة {count} مهمة.')
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _show_job_context_menu(self, position):
        """عرض قائمة السياق عند النقر بالزر الأيمن على صف في جدول الوظائف."""
        row = self.jobs_table.rowAt(position.y())
        if row < 0:
            return
        
        page_item = self.jobs_table.item(row, 0)
        if not page_item:
            return
        
        job = page_item.data(Qt.UserRole)
        if not job:
            return
        
        menu = QMenu(self)
        
        # خيارات تفعيل/تعطيل
        if job.enabled:
            disable_action = create_icon_action('تعطيل', 'close', self)
            disable_action.triggered.connect(lambda: self._context_disable_job(job))
            menu.addAction(disable_action)
        else:
            enable_action = create_icon_action('تفعيل', 'check', self)
            enable_action.triggered.connect(lambda: self._context_enable_job(job))
            menu.addAction(enable_action)
        
        menu.addSeparator()
        
        # خيارات الجدولة (فقط للوظائف المفعّلة)
        if job.enabled:
            if job.is_scheduled:
                stop_schedule_action = create_icon_action('إيقاف الجدولة', 'pause', self)
                stop_schedule_action.triggered.connect(lambda: self._context_stop_schedule(job))
                menu.addAction(stop_schedule_action)
            else:
                start_schedule_action = create_icon_action('تشغيل الجدولة', 'play', self)
                start_schedule_action.triggered.connect(lambda: self._context_start_schedule(job))
                menu.addAction(start_schedule_action)
        
        menu.addSeparator()
        
        # حذف الوظيفة
        delete_action = create_icon_action('حذف الوظيفة', 'delete', self)
        delete_action.triggered.connect(lambda: self._context_delete_job(job))
        menu.addAction(delete_action)
        
        menu.exec(self.jobs_table.mapToGlobal(position))
    
    def _context_enable_job(self, job):
        """تفعيل وظيفة من قائمة السياق."""
        job.enabled = True
        self.log_message.emit(f'تم تفعيل الوظيفة: {job.page_name}')
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _context_disable_job(self, job):
        """تعطيل وظيفة من قائمة السياق."""
        job.enabled = False
        job.is_scheduled = False
        job.cancel_requested = True
        self.log_message.emit(f'تم تعطيل الوظيفة: {job.page_name}')
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _context_start_schedule(self, job):
        """بدء جدولة وظيفة من قائمة السياق."""
        if not job.enabled:
            self.log_message.emit(f'لا يمكن بدء الجدولة - الوظيفة معطّلة: {job.page_name}')
            return
        
        job.reset_next_run_timestamp()
        job.is_scheduled = True
        job.cancel_requested = False
        
        next_run = datetime.fromtimestamp(job.next_run_timestamp).strftime('%H:%M:%S')
        NotificationSystem.notify(
            lambda msg: self.log_message.emit(msg),
            NotificationSystem.SCHEDULE,
            f'تم تفعيل الجدولة - الرفع القادم: {next_run}',
            job.page_name
        )
        
        self.job_scheduled.emit(job)
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _context_stop_schedule(self, job):
        """إيقاف جدولة وظيفة من قائمة السياق."""
        if not job.is_scheduled:
            self.log_message.emit(f'الوظيفة غير مجدولة مسبقاً: {job.page_name}')
        else:
            job.is_scheduled = False
            job.cancel_requested = True
            NotificationSystem.notify(
                lambda msg: self.log_message.emit(msg),
                NotificationSystem.SCHEDULE,
                'تم إيقاف الجدولة',
                job.page_name
            )
            self.job_cancelled.emit(job)
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _context_delete_job(self, job):
        """حذف وظيفة من قائمة السياق."""
        if isinstance(job, StoryJob):
            job_type = 'ستوري'
        elif isinstance(job, ReelsJob):
            job_type = 'ريلز'
        else:
            job_type = 'فيديو'
        
        if self._delete_job_by_type(job):
            self.log_message.emit(f'تم حذف وظيفة {job_type}: {job.page_name}')
        
        self.refresh_jobs_list()
        self.save_requested.emit()
    
    def _on_job_enabled_toggled(self, job, enabled: bool):
        """معالج تبديل حالة تفعيل الوظيفة من JobsTable."""
        job.enabled = enabled
        if not enabled:
            job.is_scheduled = False
            job.cancel_requested = True
            self.log_message.emit(f'تم تعطيل الوظيفة: {job.page_name}')
        else:
            self.log_message.emit(f'تم تفعيل الوظيفة: {job.page_name}')
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _on_job_schedule_toggled(self, job, scheduled: bool):
        """معالج تبديل حالة جدولة الوظيفة من JobsTable."""
        if not job.enabled:
            self.log_message.emit(f'لا يمكن بدء الجدولة - الوظيفة معطّلة: {job.page_name}')
            return
        
        if scheduled:
            job.reset_next_run_timestamp()
            job.is_scheduled = True
            job.cancel_requested = False
            next_run = datetime.fromtimestamp(job.next_run_timestamp).strftime('%H:%M:%S')
            NotificationSystem.notify(
                lambda msg: self.log_message.emit(msg),
                NotificationSystem.SCHEDULE,
                f'تم تفعيل الجدولة - الرفع القادم: {next_run}',
                job.page_name
            )
            self.job_scheduled.emit(job)
        else:
            job.is_scheduled = False
            job.cancel_requested = True
            NotificationSystem.notify(
                lambda msg: self.log_message.emit(msg),
                NotificationSystem.SCHEDULE,
                'تم إيقاف الجدولة',
                job.page_name
            )
            self.job_cancelled.emit(job)
        
        self.save_requested.emit()
        self.refresh_jobs_list()
    
    def _on_job_double_clicked(self, job):
        """معالج النقر المزدوج على وظيفة."""
        # سيتم التعامل معه في MainWindow
        pass
    
    def _on_job_deleted(self, job):
        """معالج حذف وظيفة من الجدول."""
        self._delete_job_by_type(job)
        self.save_requested.emit()
    
    def get_max_workers(self) -> int:
        """
        الحصول على عدد العمال الأقصى
        Get maximum number of workers
        
        Returns:
            عدد العمال - Number of workers
        """
        return self.concurrent_spin.value()
    
    def set_max_workers(self, value: int):
        """
        تعيين عدد العمال الأقصى
        Set maximum number of workers
        
        Args:
            value: العدد - Number value
        """
        self.concurrent_spin.setValue(value)


# Export the class
__all__ = ['SchedulerUI']
