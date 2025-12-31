"""
Video Job class for scheduling video uploads.

هذا الملف يحتوي على فئة PageJob التي تمثل وظيفة رفع فيديوهات لصفحة فيسبوك.
"""

import time
import threading
from core.logger import log_debug, log_warning
from core.constants import CHUNK_SIZE_DEFAULT


class PageJob:
    """
    تمثيل وظيفة رفع فيديوهات لصفحة فيسبوك.

    ملاحظة ترتيب الأقفال:
    - _state_lock: قفل خفيف لحماية enabled و cancel_requested (لا يجب الاحتفاظ به أثناء I/O)
    - lock: قفل لمنع التشغيل المتزامن لعمليات الرفع (يمكن الاحتفاظ به لفترة طويلة)

    لا يجب أبداً الحصول على _state_lock أثناء الاحتفاظ بـ lock لتجنب حالات الجمود.

    الفرق بين enabled و is_scheduled:
    - enabled: حالة التفعيل (مفعّل/معطّل) - لا يؤثر على العدّاد أو الجدولة
    - is_scheduled: حالة الجدولة الفعلية - عند True يبدأ العدّاد والجدولة
    """
    def __init__(self, page_id, page_name, folder,
                 interval_seconds=10800,
                 page_access_token=None,
                 title_template="{filename}",
                 description_template="",
                 chunk_size=CHUNK_SIZE_DEFAULT,
                 use_filename_as_title=False,
                 enabled=True,
                 is_scheduled=False,
                 next_run_timestamp=None,
                 sort_by='name',
                 jitter_enabled=False,
                 jitter_percent=10,
                 watermark_enabled=False,
                 watermark_path='',
                 watermark_position='bottom_right',
                 watermark_opacity=0.8,
                 watermark_scale=0.15,
                 use_smart_schedule=False,
                 template_id=None,
                 app_name=''):
        self.page_id = page_id
        self.page_name = page_name
        self.app_name = app_name  # اسم التطبيق المصدر للصفحة
        self.folder = folder
        self.interval_seconds = int(interval_seconds)
        self.page_access_token = page_access_token
        self.next_index = 0
        self.title_template = title_template
        self.description_template = description_template
        self.chunk_size = chunk_size
        self.use_filename_as_title = use_filename_as_title
        self._enabled = enabled
        self._is_scheduled = is_scheduled
        self._cancel_requested = False
        # ختم وقت يونكس للتشغيل التالي - إذا لم يُحدد يتم تعيينه إلى الآن + الفاصل الزمني
        self._next_run_timestamp = next_run_timestamp if next_run_timestamp is not None else (time.time() + max(1, int(interval_seconds)))
        # قفل خفيف لحماية القيم البولية - لا يحتفظ به أثناء عمليات I/O
        self._state_lock = threading.Lock()
        # قفل لمنع التشغيل المتزامن لعمليات الرفع - قد يحتفظ به لفترة طويلة
        self.lock = threading.Lock()
        # خيارات جديدة
        self.sort_by = sort_by  # 'name', 'random', 'date_created', 'date_modified'
        self.jitter_enabled = jitter_enabled  # تفعيل التوقيت العشوائي
        self.jitter_percent = jitter_percent  # نسبة التباين %
        # إعدادات العلامة المائية لكل مهمة
        self.watermark_enabled = watermark_enabled
        self.watermark_path = watermark_path
        self.watermark_position = watermark_position
        self.watermark_opacity = watermark_opacity
        self.watermark_scale = watermark_scale
        # إحداثيات العلامة المائية المخصصة (من السحب بالماوس)
        self.watermark_x = None  # إحداثي X (None = استخدام position)
        self.watermark_y = None  # إحداثي Y (None = استخدام position)
        # إعدادات الجدولة الذكية
        self.use_smart_schedule = use_smart_schedule
        self.template_id = template_id

    @property
    def enabled(self):
        """الحصول على حالة التفعيل بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value):
        """تعيين حالة التفعيل بشكل آمن من الـ threads."""
        with self._state_lock:
            self._enabled = value

    @property
    def is_scheduled(self):
        """الحصول على حالة الجدولة بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._is_scheduled

    @is_scheduled.setter
    def is_scheduled(self, value):
        """تعيين حالة الجدولة بشكل آمن من الـ threads."""
        with self._state_lock:
            self._is_scheduled = value

    @property
    def cancel_requested(self):
        """الحصول على حالة طلب الإلغاء بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._cancel_requested

    @cancel_requested.setter
    def cancel_requested(self, value):
        """تعيين حالة طلب الإلغاء بشكل آمن من الـ threads."""
        with self._state_lock:
            self._cancel_requested = value

    def check_and_reset_cancel(self):
        """التحقق من حالة الإلغاء وإعادة ضبطها بشكل ذري."""
        with self._state_lock:
            if self._cancel_requested:
                self._cancel_requested = False
                return True
            return False

    @property
    def next_run_timestamp(self):
        """الحصول على ختم وقت التشغيل التالي بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._next_run_timestamp

    @next_run_timestamp.setter
    def next_run_timestamp(self, value):
        """تعيين ختم وقت التشغيل التالي بشكل آمن من الـ threads."""
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
                from core import calculate_next_run_from_template
                from services import get_database_manager

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
            # تطبيق التوقيت العشوائي إذا كان مفعّلاً
            interval = self.interval_seconds
            if self.jitter_enabled and self.jitter_percent > 0:
                # استيراد محلي لتجنب الاستيراد الدائري
                from core.video_utils import calculate_jitter_interval
                interval = calculate_jitter_interval(interval, self.jitter_percent)
            next_time = time.time() + max(1, int(interval))

        self.next_run_timestamp = next_time

    def to_dict(self):
        return {
            'page_id': self.page_id,
            'page_name': self.page_name,
            'app_name': self.app_name,
            'folder': self.folder,
            'interval_seconds': self.interval_seconds,
            'page_access_token': self.page_access_token,
            'next_index': self.next_index,
            'title_template': self.title_template,
            'description_template': self.description_template,
            'chunk_size': self.chunk_size,
            'use_filename_as_title': self.use_filename_as_title,
            'enabled': self.enabled,
            'is_scheduled': self.is_scheduled,
            'next_run_timestamp': self.next_run_timestamp,
            'sort_by': self.sort_by,
            'jitter_enabled': self.jitter_enabled,
            'jitter_percent': self.jitter_percent,
            'watermark_enabled': self.watermark_enabled,
            'watermark_path': self.watermark_path,
            'watermark_position': self.watermark_position,
            'watermark_opacity': self.watermark_opacity,
            'watermark_scale': self.watermark_scale,
            'watermark_x': self.watermark_x,
            'watermark_y': self.watermark_y,
            'use_smart_schedule': self.use_smart_schedule,
            'template_id': self.template_id
        }

    @classmethod
    def from_dict(cls, d):
        secs = d.get('interval_seconds', 10800)
        # إذا كان next_run_timestamp محفوظاً نستخدمه، وإلا نعيّنه إلى الآن + الفاصل الزمني
        saved_timestamp = d.get('next_run_timestamp')
        obj = cls(
            d['page_id'],
            d.get('page_name', ''),
            d.get('folder', ''),
            secs,
            d.get('page_access_token'),
            d.get('title_template', "{filename}"),
            d.get('description_template', ""),
            d.get('chunk_size', CHUNK_SIZE_DEFAULT),
            d.get('use_filename_as_title', False),
            d.get('enabled', True),
            d.get('is_scheduled', False),
            next_run_timestamp=saved_timestamp,
            sort_by=d.get('sort_by', 'name'),
            jitter_enabled=d.get('jitter_enabled', False),
            jitter_percent=d.get('jitter_percent', 10),
            watermark_enabled=d.get('watermark_enabled', False),
            watermark_path=d.get('watermark_path', ''),
            watermark_position=d.get('watermark_position', 'bottom_right'),
            watermark_opacity=d.get('watermark_opacity', 0.8),
            watermark_scale=d.get('watermark_scale', 0.15),
            use_smart_schedule=d.get('use_smart_schedule', False),
            template_id=d.get('template_id'),
            app_name=d.get('app_name', '')
        )
        obj.next_index = d.get('next_index', 0)
        obj.watermark_x = d.get('watermark_x')
        obj.watermark_y = d.get('watermark_y')
        return obj
