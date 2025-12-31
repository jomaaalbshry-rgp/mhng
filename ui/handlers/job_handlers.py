"""
Job Event Handlers - معالجات أحداث الوظائف
Contains handlers for job-related events.
"""

from typing import Optional, Dict, List, Callable
from PySide6.QtWidgets import QMessageBox
from core import log_info, log_error, log_warning


class JobHandlers:
    """
    معالجات أحداث الوظائف
    Handles job-related events and actions.
    """
    
    def __init__(self, parent=None):
        self.parent = parent
        self._jobs_map: Dict = {}
    
    def on_job_created(self, job_data: dict):
        """معالجة إنشاء وظيفة جديدة"""
        log_info(f"Job created: {job_data.get('page_name', 'Unknown')}")
        # ... معالجة إنشاء الوظيفة
    
    def on_job_updated(self, job_data: dict):
        """معالجة تحديث وظيفة"""
        log_info(f"Job updated: {job_data.get('page_name', 'Unknown')}")
        # ... معالجة تحديث الوظيفة
    
    def on_job_deleted(self, job_key: str):
        """معالجة حذف وظيفة"""
        log_info(f"Job deleted: {job_key}")
        # ... معالجة حذف الوظيفة
    
    def on_job_started(self, job):
        """معالجة بدء تشغيل وظيفة"""
        log_info(f"Job started: {job.page_name}")
        # ... معالجة بدء الوظيفة
    
    def on_job_completed(self, job, result: dict):
        """معالجة اكتمال وظيفة"""
        if result.get('success'):
            log_info(f"Job completed successfully: {job.page_name}")
        else:
            log_warning(f"Job failed: {job.page_name} - {result.get('error')}")
    
    def on_job_error(self, job, error: str):
        """معالجة خطأ في وظيفة"""
        log_error(f"Job error: {job.page_name} - {error}")
        # ... معالجة الخطأ
    
    def on_schedule_toggled(self, job, enabled: bool):
        """معالجة تغيير حالة الجدولة"""
        status = "enabled" if enabled else "disabled"
        log_info(f"Job schedule {status}: {job.page_name}")
    
    def confirm_delete(self, job_name: str) -> bool:
        """تأكيد حذف وظيفة"""
        reply = QMessageBox.question(
            self.parent,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الوظيفة '{job_name}'؟",
            QMessageBox.Yes | QMessageBox.No
        )
        return reply == QMessageBox.Yes
    
    def confirm_stop_all(self) -> bool:
        """تأكيد إيقاف جميع الوظائف"""
        reply = QMessageBox.question(
            self.parent,
            "تأكيد الإيقاف",
            "هل أنت متأكد من إيقاف جميع الوظائف المجدولة؟",
            QMessageBox.Yes | QMessageBox.No
        )
        return reply == QMessageBox.Yes
