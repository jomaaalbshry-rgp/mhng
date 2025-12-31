"""
متحكم المجدول - Scheduler Controller
يدير جدولة المهام وتنفيذها
Manages task scheduling and execution
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any

from PySide6.QtCore import QObject, Signal, Slot, QTimer


class SchedulerController(QObject):
    """
    متحكم جدولة المهام
    Scheduler controller - manages scheduled tasks
    
    يدير:
    - إضافة وحذف المهام المجدولة
    - تشغيل وإيقاف المجدول
    - تنفيذ المهام في الأوقات المحددة
    
    Manages:
    - Adding and removing scheduled tasks
    - Starting and stopping the scheduler
    - Executing tasks at specified times
    """
    
    # Signals
    job_added = Signal(dict)          # إضافة مهمة - Job added
    job_removed = Signal(str)         # حذف مهمة - Job removed (job_id)
    job_started = Signal(str)         # بدء تنفيذ مهمة - Job started (job_id)
    job_completed = Signal(str, dict) # اكتمال مهمة - Job completed (job_id, result)
    job_failed = Signal(str, str)     # فشل مهمة - Job failed (job_id, error)
    scheduler_started = Signal()      # بدء المجدول - Scheduler started
    scheduler_stopped = Signal()      # إيقاف المجدول - Scheduler stopped
    log_message = Signal(str)         # رسالة سجل - Log message
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        """
        تهيئة متحكم المجدول
        Initialize scheduler controller
        
        Args:
            parent: الكائن الأب - Parent QObject
        """
        super().__init__(parent)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_jobs)
        self._timer_interval = 1000  # 1 second
        self._is_running = False
    
    @Slot(dict)
    def add_job(self, job_data: Dict[str, Any]) -> str:
        """
        إضافة مهمة جديدة - Add new scheduled job
        
        Args:
            job_data: بيانات المهمة - Job data
        
        Returns:
            str: معرف المهمة - Job ID
        """
        job_id = job_data.get('page_id', str(len(self._jobs)))
        self._jobs[job_id] = job_data
        self.job_added.emit(job_data)
        self.log_message.emit(f'تم إضافة مهمة: {job_data.get("page_name", job_id)}')
        return job_id
    
    @Slot(str)
    def remove_job(self, job_id: str) -> bool:
        """
        حذف مهمة - Remove scheduled job
        
        Args:
            job_id: معرف المهمة - Job ID
        
        Returns:
            bool: True إذا تم الحذف بنجاح - True if deletion successful
        """
        if job_id in self._jobs:
            job = self._jobs.pop(job_id)
            self.job_removed.emit(job_id)
            self.log_message.emit(f'تم حذف مهمة: {job.get("page_name", job_id)}')
            return True
        return False
    
    @Slot()
    def start_scheduler(self) -> None:
        """بدء المجدول - Start scheduler"""
        if not self._is_running:
            self._is_running = True
            self._timer.start(self._timer_interval)
            self.scheduler_started.emit()
            self.log_message.emit('تم بدء المجدول')
    
    @Slot()
    def stop_scheduler(self) -> None:
        """إيقاف المجدول - Stop scheduler"""
        if self._is_running:
            self._is_running = False
            self._timer.stop()
            self.scheduler_stopped.emit()
            self.log_message.emit('تم إيقاف المجدول')
    
    def is_running(self) -> bool:
        """
        التحقق من حالة المجدول - Check if scheduler is running
        
        Returns:
            bool: True إذا كان المجدول يعمل - True if scheduler is running
        """
        return self._is_running
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """
        الحصول على قائمة المهام - Get list of jobs
        
        Returns:
            list: قائمة المهام - List of jobs
        """
        return list(self._jobs.values())
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        الحصول على مهمة محددة - Get specific job
        
        Args:
            job_id: معرف المهمة - Job ID
        
        Returns:
            dict: بيانات المهمة أو None - Job data or None
        """
        return self._jobs.get(job_id)
    
    @Slot()
    def _check_jobs(self) -> None:
        """
        فحص المهام المجدولة - Check scheduled jobs
        
        يتم استدعاؤها دورياً بواسطة QTimer
        Called periodically by QTimer
        """
        if not self._is_running:
            return
        
        current_time = time.time()
        
        for job_id, job in list(self._jobs.items()):
            # تخطي المهام غير المجدولة أو المعطلة
            if not job.get('enabled', True) or not job.get('is_scheduled', False):
                continue
            
            # التحقق من وصول وقت التنفيذ
            next_run = job.get('next_run_timestamp', 0)
            if current_time >= next_run:
                self._execute_job(job_id, job)
    
    def _execute_job(self, job_id: str, job: Dict[str, Any]) -> None:
        """
        تنفيذ مهمة - Execute job
        
        Args:
            job_id: معرف المهمة - Job ID
            job: بيانات المهمة - Job data
        """
        self.job_started.emit(job_id)
        self.log_message.emit(f'بدء تنفيذ مهمة: {job.get("page_name", job_id)}')
        
        # TODO: تنفيذ المهمة الفعلي
        # هذا placeholder - سيتم ربطه بالمتحكمات الأخرى
        
        # تحديث وقت التنفيذ القادم
        interval = job.get('interval_seconds', 3600)
        job['next_run_timestamp'] = time.time() + interval
    
    def calculate_next_run_time(self, job: Dict[str, Any]) -> float:
        """
        حساب وقت التنفيذ القادم - Calculate next run time
        
        Args:
            job: بيانات المهمة - Job data
        
        Returns:
            float: timestamp للتنفيذ القادم - Next run timestamp
        """
        interval = job.get('interval_seconds', 3600)
        return time.time() + interval
    
    def schedule_all_jobs(self) -> None:
        """جدولة جميع المهام - Schedule all jobs"""
        count = 0
        for job in self._jobs.values():
            if job.get('enabled', True) and not job.get('is_scheduled', False):
                job['is_scheduled'] = True
                job['next_run_timestamp'] = self.calculate_next_run_time(job)
                count += 1
        
        if count > 0:
            self.log_message.emit(f'تم جدولة {count} مهمة')
    
    def unschedule_all_jobs(self) -> None:
        """إلغاء جدولة جميع المهام - Unschedule all jobs"""
        count = 0
        for job in self._jobs.values():
            if job.get('is_scheduled', False):
                job['is_scheduled'] = False
                count += 1
        
        if count > 0:
            self.log_message.emit(f'تم إلغاء جدولة {count} مهمة')

