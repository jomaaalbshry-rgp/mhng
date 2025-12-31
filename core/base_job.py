"""
وحدة قاعدة الوظائف - Base Job Module

هذه الوحدة تحتوي على الفئة الأساسية للوظائف المشتركة بين الفيديو والستوري.
تدعم الجدولة الذكية (Smart Scheduling) بالإضافة إلى الجدولة التقليدية القائمة على الفاصل الزمني.
"""

import time
import threading
from abc import ABC, abstractmethod
from typing import Optional

from .logger import log_debug, log_info, log_warning


class BaseJob(ABC):
    """
    الفئة الأساسية لجميع أنواع الوظائف (فيديو، ستوري، ريلز).
    تحتوي على المنطق المشترك للإدارة والجدولة.
    
    تدعم نوعين من الجدولة:
    - الجدولة التقليدية: باستخدام interval_seconds (الفاصل الزمني)
    - الجدولة الذكية: باستخدام use_smart_schedule و template_id
    
    ملاحظة ترتيب الأقفال:
    - _state_lock: قفل خفيف لحماية enabled و cancel_requested (لا يجب الاحتفاظ به أثناء I/O)
    - lock: قفل لمنع التشغيل المتزامن لعمليات الرفع (يمكن الاحتفاظ به لفترة طويلة)
    """
    
    def __init__(self, page_id: str, page_name: str, folder: str,
                 interval_seconds: int = 3600,
                 page_access_token: str = None,
                 enabled: bool = True,
                 is_scheduled: bool = False,
                 next_run_timestamp: float = None,
                 sort_by: str = 'name',
                 use_smart_schedule: bool = False,
                 template_id: Optional[int] = None,
                 app_name: str = ''):
        self.page_id = page_id
        self.page_name = page_name
        self.app_name = app_name  # اسم التطبيق المصدر للصفحة
        self.folder = folder
        self.interval_seconds = int(interval_seconds)
        self.page_access_token = page_access_token
        self.next_index = 0
        self.sort_by = sort_by
        
        # إعدادات الجدولة الذكية
        self.use_smart_schedule = use_smart_schedule
        self.template_id = template_id
        
        # حالات داخلية محمية بالقفل
        self._enabled = enabled
        self._is_scheduled = is_scheduled
        self._cancel_requested = False
        self._next_run_timestamp = next_run_timestamp if next_run_timestamp is not None else (time.time() + max(1, int(interval_seconds)))
        
        # أقفال
        self._state_lock = threading.Lock()
        self.lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """الحصول على حالة التفعيل بشكل آمن."""
        with self._state_lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """تعيين حالة التفعيل بشكل آمن."""
        with self._state_lock:
            self._enabled = value

    @property
    def is_scheduled(self) -> bool:
        """الحصول على حالة الجدولة بشكل آمن."""
        with self._state_lock:
            return self._is_scheduled

    @is_scheduled.setter
    def is_scheduled(self, value: bool):
        """تعيين حالة الجدولة بشكل آمن."""
        with self._state_lock:
            self._is_scheduled = value

    @property
    def cancel_requested(self) -> bool:
        """الحصول على حالة طلب الإلغاء بشكل آمن."""
        with self._state_lock:
            return self._cancel_requested

    @cancel_requested.setter
    def cancel_requested(self, value: bool):
        """تعيين حالة طلب الإلغاء بشكل آمن."""
        with self._state_lock:
            self._cancel_requested = value

    def check_and_reset_cancel(self) -> bool:
        """التحقق من حالة الإلغاء وإعادة ضبطها بشكل ذري."""
        with self._state_lock:
            if self._cancel_requested:
                self._cancel_requested = False
                return True
            return False

    @property
    def next_run_timestamp(self) -> float:
        """الحصول على ختم وقت التشغيل التالي بشكل آمن."""
        with self._state_lock:
            return self._next_run_timestamp

    @next_run_timestamp.setter
    def next_run_timestamp(self, value: float):
        """تعيين ختم وقت التشغيل التالي بشكل آمن."""
        with self._state_lock:
            self._next_run_timestamp = value

    def reset_next_run_timestamp(self):
        """
        إعادة ضبط وقت التشغيل التالي.
        
        تستخدم الجدولة الذكية إذا كانت مفعلة (use_smart_schedule=True و template_id موجود)،
        وإلا تستخدم الفاصل الزمني التقليدي.
        """
        next_time = None
        
        # محاولة استخدام الجدولة الذكية إذا كانت مفعلة
        if self.use_smart_schedule and self.template_id is not None:
            try:
                # استيراد محلي لتجنب الاستيراد الدائري
                from core.utils import calculate_next_run_from_template
                from services.database_manager import get_database_manager
                
                # الحصول على القالب من قاعدة البيانات
                db = get_database_manager()
                template = db.get_template_by_id(self.template_id)
                
                if template:
                    from datetime import datetime
                    next_datetime = calculate_next_run_from_template(template)
                    
                    if next_datetime:
                        next_time = next_datetime.timestamp()
                        log_debug(f"[SmartSchedule] الوقت التالي للوظيفة {self.page_name}: {next_datetime.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        log_warning(f"[SmartSchedule] فشل حساب الوقت التالي من القالب {self.template_id} - استخدام الفاصل الزمني")
                else:
                    log_warning(f"[SmartSchedule] القالب {self.template_id} غير موجود - استخدام الفاصل الزمني")
                    
            except Exception as e:
                log_warning(f"[SmartSchedule] خطأ في حساب الوقت من القالب: {e} - استخدام الفاصل الزمني")
        
        # إذا فشلت الجدولة الذكية أو لم تكن مفعلة، استخدم الفاصل الزمني
        if next_time is None:
            interval = self._calculate_interval()
            next_time = time.time() + max(1, int(interval))
            log_debug(f"[Schedule] استخدام الفاصل الزمني ({interval} ثانية) للوظيفة {self.page_name}")
        
        self.next_run_timestamp = next_time

    def _calculate_interval(self) -> int:
        """حساب الفاصل الزمني (يمكن للفئات الفرعية تجاوزها)."""
        return self.interval_seconds

    @abstractmethod
    def to_dict(self) -> dict:
        """تحويل الوظيفة إلى قاموس للحفظ."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict):
        """إنشاء وظيفة من قاموس محفوظ."""
        pass

    def _base_to_dict(self) -> dict:
        """الحقول المشتركة للتحويل إلى قاموس."""
        return {
            'page_id': self.page_id,
            'page_name': self.page_name,
            'app_name': self.app_name,  # اسم التطبيق المصدر
            'folder': self.folder,
            'interval_seconds': self.interval_seconds,
            'page_access_token': self.page_access_token,
            'next_index': self.next_index,
            'sort_by': self.sort_by,
            'enabled': self.enabled,
            'is_scheduled': self.is_scheduled,
            'next_run_timestamp': self.next_run_timestamp,
            # إعدادات الجدولة الذكية
            'use_smart_schedule': self.use_smart_schedule,
            'template_id': self.template_id
        }
