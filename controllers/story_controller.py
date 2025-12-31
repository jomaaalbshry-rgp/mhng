"""
متحكم الستوري - Story Controller
يدير منطق نشر الستوري
Manages story publishing logic

هذه الوحدة تحتوي على جميع الوظائف والمنطق الخاص بمهام نشر الستوري.
This module contains all functions and logic for story publishing tasks.
"""

import os
import sys
import json
import math
import random
import subprocess
import threading  # Used for threading.Lock() in StoryController class
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional, List, Any, Tuple, Dict

import requests

from services import FacebookAPIService
from core import BaseJob, NotificationSystem
from core import (
    get_subprocess_args, run_subprocess, SmartUploadScheduler,
    APIUsageTracker, APIWarningSystem, get_api_tracker, get_api_warning_system,
    API_CALLS_PER_STORY
)

from PySide6.QtCore import Signal, Slot, QObject, QThread


# ==================== ثوابت ====================
# Constants for story job defaults

# الامتدادات المدعومة للستوري - Supported Story extensions
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')
STORY_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS

# الحد الأقصى لمدة فيديو الستوري بالثواني (60 ثانية)
MAX_STORY_VIDEO_DURATION = 60

# عدد الستوريات الافتراضي لكل جدولة
DEFAULT_STORIES_PER_SCHEDULE = 1

# الحد الأدنى للتأخير العشوائي بين الستوريات (بالثواني)
DEFAULT_RANDOM_DELAY_MIN = 5

# الحد الأقصى للتأخير العشوائي بين الستوريات (بالثواني)
DEFAULT_RANDOM_DELAY_MAX = 15

# إصدار Facebook Graph API
FB_API_VERSION = 'v20.0'


# ==================== دوال مساعدة ====================
# Helper Functions

def _get_logs_dir() -> Path:
    """الحصول على مسار مجلد السجلات."""
    if sys.platform == 'win32':
        app_data = Path(os.environ.get('APPDATA', '.'))
    else:
        app_data = Path.home() / '.config'
    logs_dir = app_data / 'FBVideoScheduler' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def log_error_to_file(error, extra_info=None):
    """
    تسجيل الأخطاء في ملف لمنع إغلاق البرنامج.
    
    المعاملات:
        error: الخطأ الذي حدث
        extra_info: معلومات إضافية (اختياري)
    """
    try:
        logs_dir = _get_logs_dir()
        log_file = logs_dir / f'story_error_{datetime.now().strftime("%Y%m%d")}.log'
        
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            tb_str = ''.join(traceback.format_exception(*exc_info))
        else:
            tb_str = traceback.format_exc()
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'\n{"="*60}\n')
            f.write(f'الوقت: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write(f'الخطأ: {error}\n')
            if extra_info:
                f.write(f'معلومات إضافية: {extra_info}\n')
            f.write(f'التتبع:\n{tb_str}\n')
    except Exception:
        pass  # تجاهل أخطاء التسجيل


def get_random_emoji() -> str:
    """
    إرجاع إيموجي عشوائي من قائمة محددة.
    
    العائد:
        إيموجي عشوائي
    """
    emojis = ["🔥", "❤️", "💯", "✨", "🎉", "👍", "💪", "🌟", "😍", "🎊"]
    return random.choice(emojis)


def get_random_delay(min_delay: int = DEFAULT_RANDOM_DELAY_MIN, 
                     max_delay: int = DEFAULT_RANDOM_DELAY_MAX) -> int:
    """
    حساب تأخير عشوائي بين حد أدنى وأقصى.
    
    المعاملات:
        min_delay: الحد الأدنى للتأخير بالثواني
        max_delay: الحد الأقصى للتأخير بالثواني
    
    العائد:
        تأخير عشوائي بالثواني
    """
    return random.randint(min_delay, max_delay)


def simulate_human_behavior(log_fn: Callable[[str], None] = None):
    """
    محاكاة السلوك البشري بإضافة تأخير عشوائي قصير.
    
    المعاملات:
        log_fn: دالة للتسجيل (اختياري)
    """
    delay = random.uniform(0.5, 2.0)  # تأخير عشوائي بين 0.5 و 2 ثانية
    time.sleep(delay)


def interruptible_sleep(seconds: float, stop_event=None, check_interval: float = 1.0) -> bool:
    """
    نوم قابل للمقاطعة يتحقق من حدث الإيقاف بشكل دوري.
    
    المعاملات:
        seconds: عدد الثواني للانتظار
        stop_event: threading.Event للتحقق من طلب الإيقاف
        check_interval: الفاصل الزمني للتحقق من الإيقاف
    
    العائد:
        True إذا اكتمل الانتظار، False إذا تم مقاطعته
    """
    if stop_event is None:
        time.sleep(seconds)
        return True
    
    elapsed = 0.0
    while elapsed < seconds:
        if stop_event.is_set():
            return False
        sleep_time = min(check_interval, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
    return True


class StoryJob(BaseJob):
    """
    وظيفة نشر ستوري لصفحة فيسبوك.
    ترث من BaseJob وتضيف خصائص خاصة بالستوري.
    يدعم نشر الصور والفيديوهات في الستوري.
    """
    
    def __init__(self, page_id, page_name, folder,
                 interval_seconds=3600,
                 page_access_token=None,
                 stories_per_schedule=DEFAULT_STORIES_PER_SCHEDULE,
                 sort_by='name',
                 enabled=True,
                 is_scheduled=False,
                 next_run_timestamp=None,
                 delay_between_stories=DEFAULT_RANDOM_DELAY_MIN,  # للتوافق مع الإصدارات القديمة
                 anti_ban_enabled=True,
                 random_delay_min=DEFAULT_RANDOM_DELAY_MIN,
                 random_delay_max=DEFAULT_RANDOM_DELAY_MAX,
                 hourly_limit=20,
                 daily_limit=200,
                 use_smart_schedule=False,
                 template_id=None,
                 app_name=''):
        
        super().__init__(
            page_id=page_id,
            page_name=page_name,
            folder=folder,
            interval_seconds=interval_seconds,
            page_access_token=page_access_token,
            enabled=enabled,
            is_scheduled=is_scheduled,
            next_run_timestamp=next_run_timestamp,
            sort_by=sort_by,
            use_smart_schedule=use_smart_schedule,
            template_id=template_id,
            app_name=app_name
        )
        
        # خصائص خاصة بالستوري
        self.stories_per_schedule = stories_per_schedule
        # إعدادات الحماية من الحظر (Rate Limiting) - Requirement 4
        # تم إزالة delay_between_stories من الواجهة، نحتفظ به للتوافق مع البيانات القديمة
        self.delay_between_stories = delay_between_stories
        self.anti_ban_enabled = anti_ban_enabled
        # التأخير العشوائي فقط (Requirement 4)
        self.random_delay_min = random_delay_min if random_delay_min > 0 else DEFAULT_RANDOM_DELAY_MIN
        self.random_delay_max = random_delay_max if random_delay_max > 0 else DEFAULT_RANDOM_DELAY_MAX
        # التأكد من أن max >= min
        if self.random_delay_max < self.random_delay_min:
            self.random_delay_max = self.random_delay_min
        
        self.hourly_limit = hourly_limit
        self.daily_limit = daily_limit

    def to_dict(self) -> dict:
        """تحويل الوظيفة إلى قاموس للحفظ."""
        data = self._base_to_dict()
        data.update({
            'stories_per_schedule': self.stories_per_schedule,
            'anti_ban_enabled': self.anti_ban_enabled,
            'random_delay_min': self.random_delay_min,
            'random_delay_max': self.random_delay_max,
            # للتوافق مع الإصدارات القديمة - يمكن إزالته لاحقاً
            'delay_between_stories': self.delay_between_stories,
            'hourly_limit': self.hourly_limit,
            'daily_limit': self.daily_limit,
            'job_type': 'story'
        })
        return data

    @classmethod
    def from_dict(cls, d: dict):
        """إنشاء وظيفة من قاموس محفوظ."""
        # دعم التوافق مع القيمة القديمة stories_per_day
        stories_per_schedule = d.get('stories_per_schedule', d.get('stories_per_day', DEFAULT_STORIES_PER_SCHEDULE))
        # Requirement 4 - استخدام القيم العشوائية كافتراضي
        random_delay_min = d.get('random_delay_min', DEFAULT_RANDOM_DELAY_MIN)
        random_delay_max = d.get('random_delay_max', DEFAULT_RANDOM_DELAY_MAX)
        # التوافق مع الإصدارات القديمة التي لم تستخدم التأخير العشوائي
        if random_delay_min == 0 or random_delay_max == 0:
            random_delay_min = DEFAULT_RANDOM_DELAY_MIN
            random_delay_max = DEFAULT_RANDOM_DELAY_MAX
        obj = cls(
            page_id=d.get('page_id'),
            page_name=d.get('page_name', ''),
            folder=d.get('folder', ''),
            interval_seconds=d.get('interval_seconds', 3600),
            page_access_token=d.get('page_access_token'),
            stories_per_schedule=stories_per_schedule,
            sort_by=d.get('sort_by', 'name'),
            enabled=d.get('enabled', True),
            is_scheduled=d.get('is_scheduled', False),
            next_run_timestamp=d.get('next_run_timestamp'),
            delay_between_stories=d.get('delay_between_stories', DEFAULT_RANDOM_DELAY_MIN),
            anti_ban_enabled=d.get('anti_ban_enabled', True),
            random_delay_min=random_delay_min,
            random_delay_max=random_delay_max,
            hourly_limit=d.get('hourly_limit', 20),
            daily_limit=d.get('daily_limit', 200),
            use_smart_schedule=d.get('use_smart_schedule', False),
            template_id=d.get('template_id'),
            app_name=d.get('app_name', '')
        )
        obj.next_index = d.get('next_index', 0)
        return obj


def get_story_files(folder_path: str, sort_by: str = 'name') -> list:
    """
    الحصول على قائمة ملفات الستوري (صور + فيديوهات) من مجلد معين.
    
    المعاملات:
        folder_path: مسار المجلد
        sort_by: طريقة الترتيب ('name', 'random', 'date_created', 'date_modified')
    
    العائد:
        قائمة مسارات ملفات الستوري مرتبة
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    files = [p for p in folder.iterdir() 
             if p.is_file() and p.suffix.lower() in STORY_EXTENSIONS]
    
    if sort_by == 'random':
        random.shuffle(files)
        return files
    elif sort_by == 'date_created':
        try:
            return sorted(files, key=lambda f: f.stat().st_ctime)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower())
    elif sort_by == 'date_modified':
        try:
            return sorted(files, key=lambda f: f.stat().st_mtime)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower())
    else:
        # الافتراضي: ترتيب أبجدي
        return sorted(files, key=lambda f: f.name.lower())


def count_story_files(folder_path: str) -> int:
    """
    حساب عدد ملفات الستوري في مجلد.
    
    المعاملات:
        folder_path: مسار المجلد
    
    العائد:
        عدد ملفات الستوري
    """
    folder = Path(folder_path)
    if not folder.exists():
        return 0
    
    return len([p for p in folder.iterdir() 
                if p.is_file() and p.suffix.lower() in STORY_EXTENSIONS])


def is_image_file(file_path: str) -> bool:
    """
    التحقق مما إذا كان الملف صورة.
    
    المعاملات:
        file_path: مسار الملف
    
    العائد:
        True إذا كان الملف صورة
    """
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


def is_video_file(file_path: str) -> bool:
    """
    التحقق مما إذا كان الملف فيديو.
    
    المعاملات:
        file_path: مسار الملف
    
    العائد:
        True إذا كان الملف فيديو
    """
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def get_next_story_batch(job: StoryJob, files: list) -> list:
    """
    الحصول على الدفعة التالية من ملفات الستوري للنشر.
    
    المعاملات:
        job: وظيفة الستوري
        files: قائمة جميع الملفات
    
    العائد:
        قائمة الملفات للنشر في هذه الدورة
    """
    if not files:
        return []
    
    count = min(job.stories_per_schedule, len(files))
    start_index = job.next_index % len(files)
    
    batch = []
    for i in range(count):
        index = (start_index + i) % len(files)
        batch.append(files[index])
    
    return batch


def get_video_duration(video_path: str) -> float:
    """
    الحصول على مدة الفيديو بالثواني باستخدام ffprobe.
    
    المعاملات:
        video_path: مسار ملف الفيديو
    
    العائد:
        مدة الفيديو بالثواني، أو 0 إذا فشل القراءة
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        output = run_subprocess(cmd, timeout=30, text=True)
        
        if output.returncode == 0 and output.stdout.strip():
            return float(output.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    except Exception:
        pass
    
    return 0


def validate_story_video(video_path: str, log_fn=None) -> dict:
    """
    التحقق من صحة فيديو الستوري (يجب ألا يتجاوز 60 ثانية).
    
    المعاملات:
        video_path: مسار ملف الفيديو
        log_fn: دالة للتسجيل
    
    العائد:
        dict يحتوي على:
        - valid: bool - هل الملف صالح
        - duration: float - مدة الفيديو بالثواني
        - error: str - رسالة الخطأ إن وجدت
    """
    result = {'valid': False, 'duration': 0, 'error': None}
    
    if not os.path.exists(video_path):
        result['error'] = 'الملف غير موجود'
        return result
    
    duration = get_video_duration(video_path)
    result['duration'] = duration
    
    if duration > 0 and duration > MAX_STORY_VIDEO_DURATION:
        result['error'] = f'مدة الفيديو ({duration:.1f} ثانية) تتجاوز الحد الأقصى للستوري ({MAX_STORY_VIDEO_DURATION} ثانية)'
        if log_fn:
            log_fn(f'⚠️ {result["error"]}')
        return result
    
    result['valid'] = True
    return result


def upload_photo_story(page_id: str, photo_path: str, token: str, log_fn=None, session=None) -> tuple:
    """
    رفع صورة كستوري على صفحة فيسبوك باستخدام طريقة الخطوتين.
    
    الخطوة 1: رفع الصورة كـ unpublished
    الخطوة 2: إنشاء الستوري باستخدام photo_id
    
    Args:
        page_id: معرف الصفحة
        photo_path: مسار ملف الصورة
        token: توكن الصفحة
        log_fn: دالة التسجيل
        session: جلسة requests للأداء الأفضل (اختياري)
    
    Returns:
        (status_code, response_body)
    """
    # استخدام Session الممررة أو إنشاء واحدة جديدة للأداء الأفضل
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    try:
        # محاكاة السلوك البشري (حماية من الحظر)
        simulate_human_behavior(log_fn)
        
        # الخطوة 1: رفع الصورة كـ unpublished
        upload_url = f'https://graph.facebook.com/{FB_API_VERSION}/{page_id}/photos'
        
        with open(photo_path, 'rb') as f:
            files = {'source': (os.path.basename(photo_path), f)}
            data = {
                'access_token': token,
                'published': 'false',
                'temporary': 'true'
            }
            
            if log_fn:
                log_fn(f'📤 رفع الصورة... {os.path.basename(photo_path)}')
            
            upload_response = session.post(upload_url, data=data, files=files, timeout=120)
        
        try:
            upload_body = upload_response.json()
        except Exception:
            upload_body = {'raw_response': upload_response.text}
        
        if 'error' in upload_body:
            if log_fn:
                log_fn(f'❌ فشل رفع الصورة: {upload_body}')
            log_error_to_file(f'Photo upload failed: {upload_body}', f'Photo path: {photo_path}')
            return upload_response.status_code, upload_body
        
        photo_id = upload_body.get('id')
        if not photo_id:
            if log_fn:
                log_fn(f'❌ لم يتم الحصول على photo_id')
            log_error_to_file('Missing photo_id in response', f'Response: {upload_body}')
            return None, {'error': 'missing_photo_id'}
        
        if log_fn:
            log_fn(f'✅ تم رفع الصورة (photo_id: {photo_id})')
        
        # الخطوة 2: إنشاء الستوري باستخدام photo_id
        story_url = f'https://graph.facebook.com/{FB_API_VERSION}/{page_id}/photo_stories'
        story_response = session.post(story_url, data={
            'photo_id': photo_id,
            'access_token': token
        }, timeout=60)
        
        try:
            story_body = story_response.json()
        except Exception:
            story_body = {'raw_response': story_response.text}
        
        if log_fn:
            if story_response.status_code in (200, 201) and 'error' not in story_body:
                log_fn(f'✅ تم نشر صورة الستوري بنجاح: {os.path.basename(photo_path)}')
            else:
                log_fn(f'❌ فشل نشر صورة الستوري: {story_body}')
                log_error_to_file(f'Photo story publish failed: {story_body}', f'Photo path: {photo_path}')
        
        return story_response.status_code, story_body
        
    except Exception as e:
        if log_fn:
            log_fn(f'❌ خطأ رفع صورة الستوري: {e}')
        log_error_to_file(e, f'Photo story upload error: {photo_path}')
        return None, {'error': str(e)}
    finally:
        # إغلاق Session إذا كنا قد أنشأناها
        if own_session and session:
            session.close()


def upload_video_story(page_id: str, video_path: str, token: str, log_fn=None, session=None) -> tuple:
    """
    رفع فيديو كستوري على صفحة فيسبوك باستخدام طريقة 3 خطوات.
    
    الخطوة 1: بدء جلسة الرفع
    الخطوة 2: رفع الفيديو
    الخطوة 3: إنهاء ونشر الستوري
    
    Args:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        log_fn: دالة التسجيل
        session: جلسة requests للأداء الأفضل (اختياري)
    
    Returns:
        (status_code, response_body)
    """
    # استخدام Session الممررة أو إنشاء واحدة جديدة للأداء الأفضل
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    try:
        # التحقق من مدة الفيديو
        validation = validate_story_video(video_path, log_fn)
        if not validation['valid']:
            # تسجيل تحذير لكن متابعة الرفع - فيسبوك سيرفض إذا كان طويلاً جداً
            error_msg = validation.get('error', 'فشل التحقق من صحة الفيديو')
            if log_fn:
                log_fn(f'⚠️ تحذير: {error_msg} - سيتم محاولة الرفع على أي حال')
        
        # محاكاة السلوك البشري (حماية من الحظر)
        simulate_human_behavior(log_fn)
        
        start_endpoint = f'https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_stories'
        
        # الخطوة 1: بدء جلسة الرفع
        start_response = session.post(start_endpoint, data={
            'upload_phase': 'start',
            'access_token': token
        }, timeout=60)
        
        try:
            start_body = start_response.json()
        except Exception:
            start_body = {'raw_response': start_response.text}
        
        if 'error' in start_body:
            if log_fn:
                log_fn(f'❌ فشل بدء رفع فيديو الستوري: {start_body}')
            log_error_to_file(f'Video story start failed: {start_body}', f'Video path: {video_path}')
            return start_response.status_code, start_body
        
        video_id = start_body.get('video_id')
        upload_url = start_body.get('upload_url')
        
        if not video_id or not upload_url:
            if log_fn:
                log_fn(f'❌ لم يتم الحصول على video_id أو upload_url')
            log_error_to_file('Missing video_id or upload_url', f'Response: {start_body}')
            return None, {'error': 'missing_video_id_or_upload_url'}
        
        if log_fn:
            log_fn(f'📤 بدء رفع الفيديو... (video_id: {video_id})')
        
        # الخطوة 2: رفع الفيديو
        # ملاحظة: Facebook Graph API يستخدم صيغة 'OAuth {token}' للتفويض
        # وليس 'Bearer {token}' كما في بعض APIs الأخرى
        file_size = os.path.getsize(video_path)
        with open(video_path, 'rb') as f:
            upload_response = session.post(
                upload_url,
                headers={
                    'Authorization': f'OAuth {token}',
                    'offset': '0',
                    'file_size': str(file_size)
                },
                data=f.read(),
                timeout=300
            )
        
        if upload_response.status_code not in (200, 201):
            try:
                upload_body = upload_response.json()
            except Exception:
                upload_body = {'raw_response': upload_response.text}
            if log_fn:
                log_fn(f'❌ فشل رفع الفيديو: {upload_body}')
            log_error_to_file(f'Video upload failed: {upload_body}', f'Video path: {video_path}')
            return upload_response.status_code, upload_body
        
        if log_fn:
            log_fn(f'✅ تم رفع الفيديو، جاري النشر...')
        
        # الخطوة 3: إنهاء ونشر الستوري
        finish_response = session.post(start_endpoint, data={
            'upload_phase': 'finish',
            'video_id': video_id,
            'access_token': token
        }, timeout=60)
        
        try:
            finish_body = finish_response.json()
        except Exception:
            finish_body = {'raw_response': finish_response.text}
        
        if log_fn:
            if finish_response.status_code in (200, 201) and 'error' not in finish_body:
                log_fn(f'✅ تم نشر فيديو الستوري بنجاح: {os.path.basename(video_path)}')
            else:
                log_fn(f'❌ فشل نشر فيديو الستوري: {finish_body}')
                log_error_to_file(f'Video story publish failed: {finish_body}', f'Video path: {video_path}')
        
        return finish_response.status_code, finish_body
        
    except Exception as e:
        if log_fn:
            log_fn(f'❌ خطأ رفع فيديو الستوري: {e}')
        log_error_to_file(e, f'Video story upload error: {video_path}')
        return None, {'error': str(e)}
    finally:
        # إغلاق Session إذا كنا قد أنشأناها
        if own_session and session:
            session.close()


def upload_story(page_id: str, file_path: str, token: str, log_fn=None, session=None) -> tuple:
    """
    رفع ملف (صورة أو فيديو) كستوري - يحدد النوع تلقائياً.
    
    Args:
        page_id: معرف الصفحة
        file_path: مسار الملف
        token: توكن الصفحة
        log_fn: دالة التسجيل
        session: جلسة requests للأداء الأفضل (اختياري)
    
    Returns:
        (status_code, response_body)
    """
    if is_image_file(file_path):
        return upload_photo_story(page_id, file_path, token, log_fn, session)
    elif is_video_file(file_path):
        return upload_video_story(page_id, file_path, token, log_fn, session)
    else:
        if log_fn:
            log_fn(f'⚠️ نوع ملف غير مدعوم: {file_path}')
        return None, {'error': 'unsupported_file_type'}


def is_story_upload_successful(status, body) -> bool:
    """
    التحقق من نجاح عملية رفع الستوري.
    
    المعاملات:
        status: كود حالة HTTP للاستجابة.
        body: جسم الاستجابة (dict أو str).
    
    العائد:
        True إذا نجح الرفع، False خلاف ذلك.
    """
    if status is None:
        return False
    if not (200 <= status < 300):
        return False
    if isinstance(body, dict):
        # إذا كان هناك خطأ في الاستجابة
        if 'error' in body:
            return False
        # إذا كان هناك id أو success أو post_id يُعتبر الرفع ناجحاً
        if 'id' in body or 'success' in body or 'post_id' in body:
            return True
        # افتراض النجاح إذا لم يكن هناك خطأ
        return True
    if isinstance(body, str):
        return False
    return True


def translate_fb_error(body: dict) -> str:
    """
    ترجمة أخطاء فيسبوك للعربية المختصرة.
    
    المعاملات:
        body: جسم الاستجابة من Facebook API
    
    العائد:
        رسالة الخطأ بالعربية
    """
    if not isinstance(body, dict):
        return '❌ خطأ غير معروف'
    
    error = body.get('error', {})
    if not isinstance(error, dict):
        return '❌ خطأ غير معروف'
    
    code = error.get('code', 0)
    
    ARABIC_ERRORS = {
        4: '🚫 انتهت حصة API - الجلسة محظورة مؤقتاً',
        17: '🚫 انتهت حصة API',
        190: '🔑 التوكن منتهي الصلاحية',
        100: '⚠️ خطأ في البيانات',
        200: '🔒 صلاحيات غير كافية',
        368: '⏸️ الصفحة محظورة مؤقتاً',
        506: '📤 جاري معالجة فيديو سابق',
    }
    
    return ARABIC_ERRORS.get(code, f'❌ خطأ ({code})')


# ==================== Safe Story Job Processing ====================

def safe_process_story_job(job: StoryJob, token: str, log_fn: Callable = None,
                           auto_move: bool = False, stop_event=None) -> dict:
    """
    معالجة وظيفة ستوري مع حماية شاملة من الأخطاء.
    
    هذه الدالة تغلف جميع عمليات رفع الستوري وتمنع انهيار البرنامج
    عند حدوث أي خطأ.
    
    يتم رفع ونشر كل ملف على حدة (الوضع العادي).
    
    المعاملات:
        job: وظيفة الستوري
        token: توكن الوصول
        log_fn: دالة التسجيل
        auto_move: نقل الملفات بعد الرفع الناجح
        stop_event: حدث الإيقاف
    
    العائد:
        dict يحتوي على نتائج المعالجة
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass  # تجاهل أخطاء التسجيل
    
    result = {
        'success': False,
        'files_processed': 0,
        'files_uploaded': 0,
        'files_failed': 0,
        'error': None,
        'api_calls': 0
    }
    
    try:
        # التحقق من صحة المدخلات
        if not job:
            result['error'] = 'لم يتم توفير وظيفة الستوري'
            _log(f'❌ {result["error"]}')
            return result
        
        if not token:
            result['error'] = 'لم يتم توفير توكن الوصول'
            _log(f'❌ {result["error"]}')
            return result
        
        if not job.folder or not os.path.exists(job.folder):
            result['error'] = f'المجلد غير موجود: {job.folder}'
            _log(f'❌ {result["error"]}')
            return result
        
        # الحصول على ملفات الستوري
        try:
            files = get_story_files(job.folder, job.sort_by)
        except Exception as e:
            result['error'] = f'فشل قراءة الملفات: {str(e)}'
            _log(f'❌ {result["error"]}')
            log_error_to_file(e, f'safe_process_story_job: get_story_files failed for {job.folder}')
            return result
        
        if not files:
            _log(f'📂 لا توجد ملفات ستوري في: {job.folder}')
            result['success'] = True
            return result
        
        # الحصول على الدفعة التالية
        try:
            batch = get_next_story_batch(job, files)
        except Exception as e:
            result['error'] = f'فشل تحديد الدفعة: {str(e)}'
            _log(f'❌ {result["error"]}')
            log_error_to_file(e, f'safe_process_story_job: get_next_story_batch failed')
            return result
        
        if not batch:
            _log('📭 لا توجد ملفات للرفع في هذه الدورة')
            result['success'] = True
            return result
        
        result['files_processed'] = len(batch)
        
        # التحقق من حدود API
        tracker = None
        try:
            tracker = get_api_tracker(job.hourly_limit, job.daily_limit)
            warning_system = get_api_warning_system(log_fn)
            
            can_continue, warning_msg = warning_system.check_and_warn()
            if not can_continue:
                result['error'] = warning_msg
                result['rate_limited'] = True  # علامة خاصة لتأجيل النشر بدلاً من الإيقاف
                _log(f'⚠️ {warning_msg}')
                return result
        except Exception as e:
            # استمر حتى لو فشل نظام التتبع
            _log(f'⚠️ تحذير: فشل نظام تتبع API: {str(e)}')
            log_error_to_file(e, 'safe_process_story_job: API tracker failed')
        
        # إنشاء session للأداء الأفضل
        session = None
        try:
            session = requests.Session()
        except Exception as e:
            _log(f'⚠️ تحذير: فشل إنشاء session: {str(e)}')
            session = None
        
        try:
            # معالجة الستوري في الوضع العادي
            _log(f'📤 بدء رفع {len(batch)} ستوري لصفحة {job.page_name}')
            result = _process_normal_mode(
                job=job,
                batch=batch,
                files=files,
                token=token,
                session=session,
                tracker=tracker,
                auto_move=auto_move,
                stop_event=stop_event,
                log_fn=log_fn,
                result=result
            )
        finally:
            # إغلاق الجلسة
            if session:
                try:
                    session.close()
                except Exception:
                    pass
        
        # ملخص
        summary = f'''
📊 ملخص رفع الستوري:
├─ الصفحة: {job.page_name}
├─ المعالجة: {result['files_processed']}
├─ نجح: {result['files_uploaded']} ✅
├─ فشل: {result['files_failed']} ❌
└─ طلبات API: {result['api_calls']}'''
        
        _log(summary)
        
        return result
        
    except Exception as e:
        # التقاط أي خطأ غير متوقع ومنع انهيار البرنامج
        error_msg = f'خطأ غير متوقع في معالجة وظيفة الستوري: {str(e)}'
        result['error'] = error_msg
        _log(f'🚨 {error_msg}')
        log_error_to_file(e, f'safe_process_story_job: critical error for job {job.page_name if job else "unknown"}')
        return result


def _process_normal_mode(job: StoryJob, batch: list, files: list, token: str,
                         session, tracker, auto_move: bool, stop_event,
                         log_fn: Callable, result: dict) -> dict:
    """
    معالجة الستوري (رفع ونشر كل ملف على حدة).
    
    يتم رفع ونشر كل ملف بشكل مستقل في عملية واحدة.
    """
    def _log(msg):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass
    
    # رفع كل ملف
    for i, file_path in enumerate(batch):
        # التحقق من طلب الإيقاف
        if stop_event and stop_event.is_set():
            _log('⏹️ تم إيقاف الرفع بناءً على طلب المستخدم')
            break
        
        file_path_str = str(file_path)
        filename = os.path.basename(file_path_str)
        
        try:
            _log(f'📤 رفع ({i+1}/{len(batch)}): {filename}')
            
            # رفع الملف (رفع + نشر في خطوة واحدة)
            status, body = upload_story(
                job.page_id, file_path_str, token, log_fn, session
            )
            
            # تسجيل طلب API
            if tracker:
                try:
                    tracker.record_call(API_CALLS_PER_STORY)
                    result['api_calls'] += API_CALLS_PER_STORY
                except Exception:
                    pass
            
            # التحقق من النجاح
            if is_story_upload_successful(status, body):
                result['files_uploaded'] += 1
                _log(f'✅ تم رفع: {filename}')
                
                # نقل الملف إذا طُلب
                if auto_move:
                    try:
                        _move_file_to_uploaded(file_path_str, log_fn)
                    except Exception as move_err:
                        _log(f'⚠️ فشل نقل الملف: {str(move_err)}')
            else:
                result['files_failed'] += 1
                error_msg = body.get('error', {}).get('message', str(body)) if isinstance(body, dict) else str(body)
                _log(f'❌ فشل رفع: {filename} - {error_msg}')
            
            # تأخير بين الرفعات (حماية من الحظر)
            if i < len(batch) - 1 and job.anti_ban_enabled:
                delay = random.randint(job.random_delay_min, job.random_delay_max)
                _log(f'⏳ انتظار {delay} ثانية...')
                if not interruptible_sleep(delay, stop_event):
                    _log('⏹️ تم إيقاف الرفع')
                    break
            
        except requests.exceptions.Timeout as e:
            result['files_failed'] += 1
            _log(f'⏱️ انتهت مهلة رفع: {filename}')
            log_error_to_file(e, f'_process_normal_mode: timeout for {filename}')
            
        except requests.exceptions.ConnectionError as e:
            result['files_failed'] += 1
            _log(f'🔌 فشل الاتصال أثناء رفع: {filename}')
            log_error_to_file(e, f'_process_normal_mode: connection error for {filename}')
            
        except Exception as e:
            result['files_failed'] += 1
            _log(f'❌ خطأ غير متوقع أثناء رفع {filename}: {str(e)}')
            log_error_to_file(e, f'_process_normal_mode: unexpected error for {filename}')
    
    # تحديث مؤشر الوظيفة
    try:
        job.next_index = (job.next_index + len(batch)) % len(files) if files else 0
    except Exception:
        pass
    
    # تحديد النجاح
    result['success'] = result['files_uploaded'] > 0 or result['files_failed'] == 0
    
    return result


def _move_file_to_uploaded(file_path: str, log_fn: Callable = None):
    """
    نقل ملف إلى مجلد Uploaded بعد الرفع الناجح.
    
    المعاملات:
        file_path: مسار الملف
        log_fn: دالة التسجيل
    """
    import shutil
    
    try:
        parent_dir = os.path.dirname(file_path)
        uploaded_dir = os.path.join(parent_dir, 'Uploaded')
        os.makedirs(uploaded_dir, exist_ok=True)
        
        filename = os.path.basename(file_path)
        dest_path = os.path.join(uploaded_dir, filename)
        
        # التعامل مع الملفات المكررة
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(uploaded_dir, f'{name}_{counter}{ext}')
                counter += 1
        
        shutil.move(file_path, dest_path)
        
        if log_fn:
            log_fn(f'📁 تم نقل الملف إلى: Uploaded/{os.path.basename(dest_path)}')
            
    except Exception as e:
        if log_fn:
            log_fn(f'⚠️ فشل نقل الملف: {str(e)}')
        raise


class StoryController(QObject):
    """
    متحكم نشر الستوري
    Story publishing controller - handles story publishing logic
    
    يدير عملية نشر الستوريز على فيسبوك مع:
    - التحقق من صحة الملفات
    - معالجة الأخطاء
    
    Manages story publishing process on Facebook with:
    - File validation
    - Error handling
    """
    
    # Signals
    publish_started = Signal(str)        # بدء النشر - Publish started (page_name)
    publish_progress = Signal(int, str)  # تقدم النشر - Publish progress (count, message)
    publish_completed = Signal(dict)     # اكتمال النشر - Publish completed (result)
    publish_failed = Signal(str)         # فشل النشر - Publish failed (error_message)
    log_message = Signal(str)            # رسالة سجل - Log message
    
    def __init__(self, api_service: FacebookAPIService, parent: Optional[QObject] = None) -> None:
        """
        تهيئة متحكم الستوري
        Initialize story controller
        
        Args:
            api_service: خدمة Facebook API - Facebook API service
            parent: الكائن الأب - Parent QObject
        """
        super().__init__(parent)
        self.api_service = api_service
        self._current_publish: Optional[str] = None
        self._publish_lock = threading.Lock()
    
    @Slot(dict, list, str)
    def start_publish(self, page_job: Any, story_files: List[str], token: str) -> None:
        """
        بدء نشر الستوري - Start story publishing
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            story_files: قائمة ملفات الستوري - List of story files
            token: توكن الوصول - Access token
        """
        if not self._publish_lock.acquire(blocking=False):
            self.log_message.emit('تخطي: نشر ستوري سابق قيد التنفيذ')
            return
        
        try:
            self.publish_started.emit(page_job.page_name)
            self._current_publish = page_job.page_name
            
            # تنفيذ النشر
            result = self._perform_publish(page_job, story_files, token)
            
            if result.get('success', False):
                self.publish_completed.emit(result)
            else:
                error_msg = result.get('error', 'فشل النشر')
                self.publish_failed.emit(error_msg)
        except Exception as e:
            self.publish_failed.emit(str(e))
        finally:
            self._current_publish = None
            self._publish_lock.release()
    
    @Slot()
    def cancel_publish(self) -> None:
        """إلغاء النشر الحالي - Cancel current publish"""
        if self._current_publish:
            self.log_message.emit(f'إلغاء النشر: {self._current_publish}')
            self._current_publish = None
    
    def validate_story(self, story_path: str) -> Tuple[bool, str]:
        """
        التحقق من صحة ملف الستوري - Validate story file
        
        Args:
            story_path: مسار الستوري - Story path
        
        Returns:
            tuple: (valid: bool, error_message: str)
        """
        if not os.path.exists(story_path):
            return (False, 'الملف غير موجود')
        
        if not os.path.isfile(story_path):
            return (False, 'المسار ليس ملف')
        
        ext = Path(story_path).suffix.lower()
        if ext not in STORY_EXTENSIONS:
            return (False, f'امتداد غير مدعوم: {ext}')
        
        try:
            size = os.path.getsize(story_path)
            if size == 0:
                return (False, 'الملف فارغ')
        except Exception as e:
            return (False, f'خطأ في قراءة الملف: {e}')
        
        return (True, '')
    
    def _perform_publish(self, page_job: Any, story_files: List[str], token: str) -> Dict[str, Any]:
        """
        تنفيذ عملية النشر الفعلية - Perform actual publish
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            story_files: قائمة ملفات الستوري - List of story files
            token: توكن الوصول - Access token
        
        Returns:
            dict: نتيجة النشر - Publish result
        """
        try:
            success_count = 0
            total_count = len(story_files)
            
            for i, file_path in enumerate(story_files):
                status, body = upload_story(
                    page_job.page_id,
                    file_path,
                    token,
                    lambda msg: self.log_message.emit(msg)
                )
                
                if is_story_upload_successful(status, body):
                    success_count += 1
                
                # تأخير بين الرفعات لتجنب الحظر (إلا للملف الأخير)
                if i < total_count - 1 and hasattr(page_job, 'anti_ban_enabled') and page_job.anti_ban_enabled:
                    delay_min = getattr(page_job, 'random_delay_min', DEFAULT_RANDOM_DELAY_MIN)
                    delay_max = getattr(page_job, 'random_delay_max', DEFAULT_RANDOM_DELAY_MAX)
                    delay = random.randint(delay_min, delay_max)
                    time.sleep(delay)
            
            return {
                'success': success_count > 0,
                'success_count': success_count,
                'total_count': total_count,
                'error': None if success_count > 0 else 'فشل نشر جميع الستوريات'
            }
        except Exception as e:
            return {
                'success': False,
                'success_count': 0,
                'total_count': len(story_files),
                'error': str(e)
            }

