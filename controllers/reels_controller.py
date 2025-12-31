"""
متحكم الريلز - Reels Controller
يدير منطق نشر الريلز
Manages reels publishing logic

هذه الوحدة تحتوي على جميع الوظائف والمنطق الخاص بمهام نشر الريلز.
This module contains all functions and logic for reels publishing tasks.
"""

import os
import sys
import time
import random
import subprocess
import traceback
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Tuple, Union, Any, List, Dict

import requests

from services import FacebookAPIService
from core import BaseJob, NotificationSystem, VIDEO_EXTENSIONS
from core import (
    get_subprocess_args, run_subprocess, check_internet_connection,
    check_disk_space, validate_file_extension, normalize_path,
    retry_with_backoff, RateLimiter, handle_rate_limit, get_file_info
)

from PySide6.QtCore import Signal, Slot, QObject, QThread


# ==================== ثوابت ====================

# الامتدادات المدعومة للريلز - Supported Reels extensions
REELS_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')

# الحد الأقصى لمدة الريلز بالثواني (60 ثانية)
MAX_REELS_DURATION = 60

# الحد الأقصى لحجم الريلز (1 GB = 1024 * 1024 * 1024 bytes)
MAX_REELS_SIZE_BYTES = 1024 * 1024 * 1024

# إصدار Facebook Graph API
FB_API_VERSION = 'v20.0'

# ثواني الانتظار للاتصال بالإنترنت
CONNECTION_WAIT_TIMEOUT = 60

# حجم الجزء الافتراضي 32MB
CHUNK_SIZE_DEFAULT = 32 * 1024 * 1024

# الحد الأدنى للرفع المستأنف (50MB)
RESUMABLE_THRESHOLD_BYTES = 50 * 1024 * 1024

# ثوابت المحاولة والمهلة
MAX_UPLOAD_RETRIES = 3
UPLOAD_TIMEOUT_START = 60
UPLOAD_TIMEOUT_TRANSFER = 300
UPLOAD_TIMEOUT_FINISH = 180


# ==================== دوال مساعدة ====================

def _get_logs_dir() -> Path:
    """الحصول على مسار مجلد السجلات."""
    if sys.platform == 'win32':
        app_data = Path(os.environ.get('APPDATA', '.'))
    else:
        app_data = Path.home() / '.config'
    logs_dir = app_data / 'FBVideoScheduler' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def log_error_to_file(error: Union[Exception, str], extra_info: Optional[str] = None) -> None:
    """
    تسجيل الأخطاء في ملف لمنع إغلاق البرنامج.
    
    المعاملات:
        error: الخطأ الذي حدث (Exception أو str)
        extra_info: معلومات إضافية (اختياري)
    """
    try:
        logs_dir = _get_logs_dir()
        log_file = logs_dir / f'reels_error_{datetime.now().strftime("%Y%m%d")}.log'
        
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
    except (OSError, IOError, PermissionError):
        # تجاهل أخطاء الملفات فقط - لا نريد أن نفشل بسبب مشاكل في التسجيل
        pass


def calculate_jitter_interval(base_interval: int, jitter_percent: int = 10) -> int:
    """
    حساب الفاصل الزمني مع نطاق عشوائي لمحاكاة السلوك البشري.
    
    المعاملات:
        base_interval: الفاصل الزمني الأساسي بالثواني
        jitter_percent: نسبة التباين المئوية (مثلاً 10 = ±10%)
    
    العائد:
        الفاصل الزمني مع التباين العشوائي
    """
    if jitter_percent <= 0:
        return base_interval
    
    variation = int(base_interval * jitter_percent / 100)
    jitter = random.randint(-variation, variation)
    return max(10, base_interval + jitter)


class ReelsJob(BaseJob):
    """
    وظيفة نشر ريلز لصفحة فيسبوك.
    ترث من BaseJob وتضيف خصائص خاصة بالريلز.
    
    الريلز يشبه الفيديو العادي لكن:
    - مدة أقصر (حتى 90 ثانية)
    - يُنشر في قسم الريلز الخاص
    - يستخدم API مختلف
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
        
        # خصائص خاصة بالريلز (مشابهة للفيديو)
        self.title_template = title_template
        self.description_template = description_template
        self.chunk_size = chunk_size
        self.use_filename_as_title = use_filename_as_title
        self.jitter_enabled = jitter_enabled
        self.jitter_percent = jitter_percent
        # إعدادات العلامة المائية
        self.watermark_enabled = watermark_enabled
        self.watermark_path = watermark_path
        self.watermark_position = watermark_position
        self.watermark_opacity = watermark_opacity
        self.watermark_scale = watermark_scale
        # إحداثيات العلامة المائية المخصصة (من السحب بالماوس)
        self.watermark_x = None  # إحداثي X (None = استخدام position)
        self.watermark_y = None  # إحداثي Y (None = استخدام position)

    def _calculate_interval(self) -> int:
        """حساب الفاصل الزمني مع تطبيق التوقيت العشوائي."""
        if self.jitter_enabled and self.jitter_percent > 0:
            return calculate_jitter_interval(self.interval_seconds, self.jitter_percent)
        return self.interval_seconds

    def to_dict(self) -> dict:
        """تحويل الوظيفة إلى قاموس للحفظ."""
        data = self._base_to_dict()
        data.update({
            'title_template': self.title_template,
            'description_template': self.description_template,
            'chunk_size': self.chunk_size,
            'use_filename_as_title': self.use_filename_as_title,
            'jitter_enabled': self.jitter_enabled,
            'jitter_percent': self.jitter_percent,
            'watermark_enabled': self.watermark_enabled,
            'watermark_path': self.watermark_path,
            'watermark_position': self.watermark_position,
            'watermark_opacity': self.watermark_opacity,
            'watermark_scale': self.watermark_scale,
            'watermark_x': self.watermark_x,
            'watermark_y': self.watermark_y,
            'job_type': 'reels'
        })
        return data

    @classmethod
    def from_dict(cls, d: dict):
        """إنشاء وظيفة من قاموس محفوظ."""
        obj = cls(
            page_id=d.get('page_id'),
            page_name=d.get('page_name', ''),
            folder=d.get('folder', ''),
            interval_seconds=d.get('interval_seconds', 10800),
            page_access_token=d.get('page_access_token'),
            title_template=d.get('title_template', "{filename}"),
            description_template=d.get('description_template', ""),
            chunk_size=d.get('chunk_size', CHUNK_SIZE_DEFAULT),
            use_filename_as_title=d.get('use_filename_as_title', False),
            enabled=d.get('enabled', True),
            is_scheduled=d.get('is_scheduled', False),
            next_run_timestamp=d.get('next_run_timestamp'),
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


def get_reels_files(folder_path: str, sort_by: str = 'name') -> list:
    """
    الحصول على قائمة ملفات الريلز من مجلد معين.
    
    المعاملات:
        folder_path: مسار المجلد
        sort_by: طريقة الترتيب ('name', 'random', 'date_created', 'date_modified')
    
    العائد:
        قائمة مسارات ملفات الريلز مرتبة
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    files = [p for p in folder.iterdir() 
             if p.is_file() and p.suffix.lower() in REELS_EXTENSIONS]
    
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


def count_reels_files(folder_path: str) -> int:
    """
    حساب عدد ملفات الريلز في مجلد.
    
    المعاملات:
        folder_path: مسار المجلد
    
    العائد:
        عدد ملفات الريلز
    """
    folder = Path(folder_path)
    if not folder.exists():
        return 0
    
    return len([p for p in folder.iterdir() 
                if p.is_file() and p.suffix.lower() in REELS_EXTENSIONS])


# ==================== التحقق من صحة الفيديو ====================

def get_reels_duration(video_path: str) -> float:
    """
    الحصول على مدة فيديو الريلز بالثواني باستخدام ffprobe.
    
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


def check_reels_duration(video_path: str) -> Tuple[bool, float, str]:
    """
    فحص سريع لمدة فيديو الريلز قبل بدء الرفع.
    
    يجب استدعاء هذه الدالة قبل محاولة الرفع لإظهار تحذير مباشر للمستخدم
    إذا كانت مدة الفيديو تتجاوز الحد المسموح به (60 ثانية).
    
    المعاملات:
        video_path: مسار ملف الفيديو
    
    العائد:
        tuple: (is_valid: bool, duration: float, error_message: str)
        - is_valid: True إذا كانت المدة مقبولة
        - duration: مدة الفيديو بالثواني
        - error_message: رسالة الخطأ إذا كانت المدة غير مقبولة، وإلا سلسلة فارغة
    """
    if not os.path.exists(video_path):
        return False, 0, 'الملف غير موجود'
    
    duration = get_reels_duration(video_path)
    
    if duration <= 0:
        # لم نتمكن من قراءة المدة - نفترض أنها مقبولة ونترك التحقق للـ API
        return True, 0, ''
    
    if duration > MAX_REELS_DURATION:
        error_msg = (
            f'مدة الفيديو ({duration:.1f} ثانية) تتجاوز الحد الأقصى للريلز ({MAX_REELS_DURATION} ثانية).\n'
            f'يرجى اختيار فيديو بمدة أقل من {MAX_REELS_DURATION} ثانية (دقيقة واحدة).'
        )
        return False, duration, error_msg
    
    return True, duration, ''


def validate_reels_file(video_path: str, log_fn: Callable[[str], None] = None) -> dict:
    """
    التحقق من صحة ملف الريلز قبل الرفع.
    
    المعاملات:
        video_path: مسار ملف الفيديو
        log_fn: دالة للتسجيل
    
    العائد:
        dict يحتوي على:
        - valid: bool - هل الملف صالح
        - duration: float - مدة الفيديو بالثواني
        - size: int - حجم الملف بالبايت
        - error: str - رسالة الخطأ إن وجدت
        - error_code: int - رمز الخطأ إن وجد
    """
    result = {'valid': False, 'duration': 0, 'size': 0, 'error': None, 'error_code': None}
    
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    # التحقق من وجود الملف
    if not os.path.exists(video_path):
        result['error'] = 'الملف غير موجود'
        result['error_code'] = 3001
        _log(f'❌ {result["error"]}: {video_path}')
        return result
    
    # التحقق من امتداد الملف
    valid_ext, ext_msg = validate_file_extension(video_path, REELS_EXTENSIONS)
    if not valid_ext:
        result['error'] = ext_msg
        result['error_code'] = 3003
        _log(f'❌ {result["error"]}')
        return result
    
    # التحقق من حجم الملف
    try:
        file_size = os.path.getsize(video_path)
        result['size'] = file_size
        
        if file_size == 0:
            result['error'] = 'الملف فارغ'
            result['error_code'] = 3005
            _log(f'❌ {result["error"]}')
            return result
        
        if file_size > MAX_REELS_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            max_size_mb = MAX_REELS_SIZE_BYTES / (1024 * 1024)
            result['error'] = f'حجم الملف ({size_mb:.1f} MB) يتجاوز الحد الأقصى ({max_size_mb:.0f} MB)'
            result['error_code'] = 3002
            _log(f'❌ {result["error"]}')
            return result
    except OSError as e:
        result['error'] = f'فشل قراءة معلومات الملف: {e}'
        result['error_code'] = 3006
        _log(f'❌ {result["error"]}')
        return result
    
    # التحقق من مدة الفيديو
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_type', '-of', 'csv=p=0',
            video_path
        ]
        
        probe_result = run_subprocess(cmd, timeout=30)
        
        if probe_result.returncode != 0 or b'video' not in probe_result.stdout:
            result['error'] = 'الملف ليس فيديو صالح'
            result['error_code'] = 3005
            _log(f'❌ {result["error"]}')
            return result
        
        # الحصول على مدة الفيديو
        duration = get_reels_duration(video_path)
        result['duration'] = duration
        
        if duration > 0:
            if duration > MAX_REELS_DURATION:
                result['error'] = f'مدة الفيديو ({duration:.1f} ثانية) تتجاوز الحد الأقصى للريلز ({MAX_REELS_DURATION} ثانية)'
                result['error_code'] = 3004
                _log(f'⚠️ {result["error"]}')
                return result
        
        result['valid'] = True
        _log(f'✅ الفيديو صالح - المدة: {duration:.1f} ثانية - الحجم: {file_size / (1024*1024):.2f} MB')
        return result
        
    except FileNotFoundError:
        # ffprobe غير متوفر، نفترض صلاحية الملف بناءً على الحجم فقط
        _log('⚠️ تحذير: ffprobe غير متوفر، تم تخطي التحقق من صحة الفيديو')
        result['valid'] = True
        return result
    except subprocess.TimeoutExpired:
        result['error'] = 'انتهت مهلة التحقق من الفيديو'
        result['error_code'] = 1002
        _log(f'❌ {result["error"]}')
        return result
    except Exception as e:
        result['error'] = f'خطأ في التحقق: {str(e)}'
        result['error_code'] = 5003
        _log(f'❌ {result["error"]}')
        log_error_to_file(e, f'Reels validation error: {video_path}')
        return result


# ==================== دوال الرفع ====================

def upload_reels(page_id: str, 
                 video_path: str, 
                 token: str,
                 description: str = '',
                 title: str = '',
                 log_fn: Callable[[str], None] = None,
                 progress_callback: Callable[[float], None] = None,
                 session: requests.Session = None,
                 stop_event: threading.Event = None) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو ريلز على صفحة فيسبوك.
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        description: وصف الريلز (اختياري)
        title: عنوان الريلز (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        session: جلسة requests للأداء الأفضل (اختياري)
        stop_event: حدث لإيقاف الرفع (threading.Event)
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    def _progress(percent):
        if progress_callback:
            progress_callback(percent)
    
    def _is_stopped():
        return stop_event is not None and stop_event.is_set()
    
    # التحقق من طلب الإيقاف قبل البدء
    if _is_stopped():
        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
    
    # التحقق من صحة الفيديو
    validation = validate_reels_file(video_path, log_fn)
    if not validation['valid']:
        error_msg = validation.get('error', 'فشل التحقق من صحة الفيديو')
        _log(f'❌ فشل التحقق: {error_msg}')
        return None, {'error': error_msg, 'error_code': validation.get('error_code')}
    
    file_size = validation.get('size', os.path.getsize(video_path))
    
    # استخدام الرفع المستأنف للملفات الكبيرة
    if file_size > RESUMABLE_THRESHOLD_BYTES:
        _log(f'📤 ملف كبير ({file_size / (1024*1024):.2f} MB) - استخدام الرفع المستأنف')
        return resumable_upload_reels(page_id, video_path, token, description, 
                                       title, log_fn, progress_callback, session,
                                       stop_event=stop_event)
    
    # استخدام Session الممررة أو إنشاء واحدة جديدة
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    try:
        # التحقق من طلب الإيقاف
        if _is_stopped():
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        _log(f'📤 بدء رفع الريلز: {os.path.basename(video_path)}')
        _progress(0)
        
        # الخطوة 1: بدء جلسة الرفع
        url = f'https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_reels'
        
        start_data = {
            'access_token': token,
            'upload_phase': 'start',
            'file_size': file_size
        }
        
        start_response = session.post(url, data=start_data, timeout=UPLOAD_TIMEOUT_START)
        
        try:
            start_body = start_response.json()
        except Exception:
            start_body = {'raw_response': start_response.text}
        
        if 'error' in start_body:
            error = start_body.get('error', {})
            error_msg = error.get('message', 'خطأ في بدء الرفع')
            _log(f'❌ فشل بدء رفع الريلز: {error_msg}')
            log_error_to_file(f'Reels start failed: {start_body}', video_path)
            return start_response.status_code, start_body
        
        video_id = start_body.get('video_id')
        upload_url = start_body.get('upload_url')
        
        if not video_id or not upload_url:
            _log('❌ لم يتم الحصول على video_id أو upload_url')
            return None, {'error': 'missing_video_id_or_upload_url', 'error_code': 2004}
        
        _log(f'📋 تم بدء جلسة الرفع (video_id: {video_id})')
        _progress(20)
        
        # التحقق من طلب الإيقاف بعد بدء الجلسة
        if _is_stopped():
            _log('⏹️ تم إيقاف الرفع بعد بدء الجلسة')
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        # الخطوة 2: رفع الفيديو
        with open(video_path, 'rb') as video_file:
            upload_response = session.post(
                upload_url,
                headers={
                    'Authorization': f'OAuth {token}',
                    'offset': '0',
                    'file_size': str(file_size)
                },
                data=video_file.read(),
                timeout=UPLOAD_TIMEOUT_TRANSFER
            )
        
        # التحقق من طلب الإيقاف بعد رفع الفيديو
        if _is_stopped():
            _log('⏹️ تم إيقاف الرفع بعد نقل الفيديو')
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        if upload_response.status_code not in (200, 201):
            try:
                upload_body = upload_response.json()
            except Exception:
                upload_body = {'raw_response': upload_response.text}
            _log(f'❌ فشل رفع الفيديو: {upload_body}')
            log_error_to_file(f'Reels upload failed: {upload_body}', video_path)
            return upload_response.status_code, upload_body
        
        _log(f'✅ تم رفع الفيديو، جاري النشر...')
        _progress(70)
        
        # الخطوة 3: إنهاء الرفع ونشر الريلز
        finish_data = {
            'access_token': token,
            'upload_phase': 'finish',
            'video_id': video_id,
            'video_state': 'PUBLISHED'  # مطلوب لنشر الريلز وظهوره على الصفحة
        }
        
        if description:
            finish_data['description'] = description
        if title:
            finish_data['title'] = title
        
        finish_response = session.post(url, data=finish_data, timeout=UPLOAD_TIMEOUT_FINISH)
        
        try:
            finish_body = finish_response.json()
        except Exception:
            finish_body = {'raw_response': finish_response.text}
        
        _progress(90)
        
        # التحقق من الاستجابة
        if finish_response.status_code in (200, 201) and 'error' not in finish_body:
            _log(f'✅ تم رفع ونشر الريلز بنجاح! (video_id: {video_id})')
            finish_body['video_id'] = video_id
            _progress(100)
            return finish_response.status_code, finish_body
        else:
            error = finish_body.get('error', {})
            error_msg = error.get('message', 'خطأ في نشر الريلز')
            _log(f'❌ فشل نشر الريلز: {error_msg}')
            log_error_to_file(f'Reels finish failed: {finish_body}', video_path)
            return finish_response.status_code, finish_body
            
    except requests.exceptions.Timeout:
        error_msg = 'انتهت مهلة الرفع'
        _log(f'❌ {error_msg}')
        log_error_to_file(error_msg, video_path)
        return None, {'error': error_msg, 'error_code': 1002}
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f'خطأ في الاتصال: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': error_msg, 'error_code': 1001}
    
    except Exception as e:
        error_msg = f'خطأ غير متوقع: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': str(e), 'error_code': 5003}
    
    finally:
        if own_session and session:
            session.close()


def resumable_upload_reels(page_id: str,
                           video_path: str,
                           token: str,
                           description: str = '',
                           title: str = '',
                           log_fn: Callable[[str], None] = None,
                           progress_callback: Callable[[float], None] = None,
                           session: requests.Session = None,
                           chunk_size: int = CHUNK_SIZE_DEFAULT,
                           stop_event: threading.Event = None) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو ريلز باستخدام الرفع المستأنف (Resumable Upload).
    
    هذه الطريقة مناسبة للملفات الكبيرة وتدعم:
    - رفع الملف على مراحل (chunks)
    - استئناف الرفع في حالة الانقطاع
    - عرض تقدم الرفع بشكل دقيق
    - إيقاف الرفع فوراً عند طلب المستخدم
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        description: وصف الريلز (اختياري)
        title: عنوان الريلز (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        session: جلسة requests للأداء الأفضل (اختياري)
        chunk_size: حجم كل جزء بالبايت
        stop_event: حدث لإيقاف الرفع (threading.Event)
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    def _progress(percent):
        if progress_callback:
            progress_callback(percent)
    
    def _is_stopped():
        return stop_event is not None and stop_event.is_set()
    
    # التحقق من طلب الإيقاف قبل البدء
    if _is_stopped():
        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
    
    # استخدام Session الممررة أو إنشاء واحدة جديدة
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    rate_limiter = RateLimiter()
    file_size = os.path.getsize(video_path)
    file_name = os.path.basename(video_path)
    
    try:
        _log(f'📤 بدء الرفع المستأنف للريلز: {file_name} ({file_size / (1024*1024):.2f} MB)')
        _progress(0)
        
        # الخطوة 1: بدء جلسة الرفع
        start_url = f'https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_reels'
        start_data = {
            'access_token': token,
            'upload_phase': 'start',
            'file_size': file_size
        }
        
        _log('📋 بدء جلسة الرفع...')
        start_response = session.post(start_url, data=start_data, timeout=UPLOAD_TIMEOUT_START)
        
        try:
            start_body = start_response.json()
        except Exception:
            start_body = {'raw_response': start_response.text}
        
        if 'error' in start_body:
            # التحقق من Rate Limiting
            wait_time = handle_rate_limit(start_body, rate_limiter, log_fn)
            if wait_time > 0:
                # التحقق من طلب الإيقاف أثناء الانتظار
                for _ in range(int(wait_time)):
                    if _is_stopped():
                        _log('⏹️ تم إيقاف الرفع أثناء الانتظار')
                        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                    time.sleep(1)
                # إعادة المحاولة
                start_response = session.post(start_url, data=start_data, timeout=UPLOAD_TIMEOUT_START)
                start_body = start_response.json()
                if 'error' in start_body:
                    _log(f'❌ فشل بدء جلسة الرفع: {start_body}')
                    return start_response.status_code, start_body
            else:
                _log(f'❌ فشل بدء جلسة الرفع: {start_body}')
                return start_response.status_code, start_body
        
        video_id = start_body.get('video_id')
        upload_url = start_body.get('upload_url')
        
        if not video_id or not upload_url:
            _log('❌ لم يتم الحصول على video_id أو upload_url')
            return None, {'error': 'missing_video_id_or_upload_url', 'error_code': 2004}
        
        _log(f'✅ تم بدء جلسة الرفع (video_id: {video_id})')
        _progress(5)
        
        # التحقق من طلب الإيقاف بعد بدء الجلسة
        if _is_stopped():
            _log('⏹️ تم إيقاف الرفع بعد بدء الجلسة')
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        # الخطوة 2: رفع الفيديو على مراحل
        uploaded_bytes = 0
        retry_count = 0
        
        with open(video_path, 'rb') as video_file:
            while uploaded_bytes < file_size:
                # التحقق من طلب الإيقاف قبل كل جزء (Problem 2: تحسين سرعة الإيقاف)
                if _is_stopped():
                    _log('⏹️ تم إيقاف الرفع أثناء نقل البيانات')
                    return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                
                # قراءة الجزء التالي
                chunk = video_file.read(chunk_size)
                if not chunk:
                    break
                
                chunk_end = uploaded_bytes + len(chunk) - 1
                
                headers = {
                    'Authorization': f'OAuth {token}',
                    'offset': str(uploaded_bytes),
                    'file_size': str(file_size),
                    'Content-Type': 'application/octet-stream'
                }
                
                # محاولة رفع الجزء مع إعادة المحاولة
                for attempt in range(MAX_UPLOAD_RETRIES):
                    # التحقق من طلب الإيقاف قبل كل محاولة
                    if _is_stopped():
                        _log('⏹️ تم إيقاف الرفع أثناء المحاولات')
                        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                    
                    try:
                        chunk_response = session.post(
                            upload_url,
                            headers=headers,
                            data=chunk,
                            timeout=UPLOAD_TIMEOUT_TRANSFER
                        )
                        
                        if chunk_response.status_code in (200, 201):
                            uploaded_bytes += len(chunk)
                            progress = (uploaded_bytes / file_size) * 85 + 5  # 5-90%
                            _progress(progress)
                            break
                        else:
                            try:
                                chunk_body = chunk_response.json()
                            except Exception:
                                chunk_body = {}
                            
                            # التحقق من Rate Limiting
                            wait_time = handle_rate_limit(chunk_body, rate_limiter, log_fn)
                            if wait_time > 0:
                                # التحقق من طلب الإيقاف أثناء الانتظار
                                for _ in range(int(wait_time)):
                                    if _is_stopped():
                                        _log('⏹️ تم إيقاف الرفع أثناء انتظار Rate Limit')
                                        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                                    time.sleep(1)
                                continue
                            
                            if attempt < MAX_UPLOAD_RETRIES - 1:
                                wait = (attempt + 1) * 5
                                _log(f'⚠️ فشل رفع الجزء - إعادة المحاولة بعد {wait} ثانية...')
                                # التحقق من طلب الإيقاف أثناء الانتظار
                                for _ in range(int(wait)):
                                    if _is_stopped():
                                        _log('⏹️ تم إيقاف الرفع أثناء الانتظار للمحاولة التالية')
                                        return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                                    time.sleep(1)
                            else:
                                _log(f'❌ فشل رفع الجزء بعد {MAX_UPLOAD_RETRIES} محاولات')
                                return chunk_response.status_code, {'error': 'chunk_upload_failed'}
                                
                    except requests.exceptions.Timeout:
                        if attempt < MAX_UPLOAD_RETRIES - 1:
                            _log(f'⚠️ انتهت مهلة رفع الجزء - إعادة المحاولة...')
                            # التحقق من طلب الإيقاف
                            if _is_stopped():
                                _log('⏹️ تم إيقاف الرفع بعد انتهاء المهلة')
                                return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                            time.sleep(5)
                        else:
                            raise
                    
                    except requests.exceptions.ConnectionError:
                        # انتظار عودة الاتصال
                        _log('📶 فحص الاتصال بالإنترنت...')
                        if not check_internet_connection():
                            _log('📶 انتظار عودة الاتصال...')
                            # التحقق من طلب الإيقاف أثناء انتظار الاتصال
                            for _ in range(CONNECTION_WAIT_TIMEOUT):
                                if _is_stopped():
                                    _log('⏹️ تم إيقاف الرفع أثناء انتظار الاتصال')
                                    return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                                time.sleep(1)
                            if not check_internet_connection():
                                raise
                        time.sleep(5)
        
        _progress(90)
        
        # التحقق من طلب الإيقاف قبل إنهاء الرفع
        if _is_stopped():
            _log('⏹️ تم إيقاف الرفع قبل الإنهاء')
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        # الخطوة 3: إنهاء الرفع ونشر الريلز
        _log('📋 جاري إنهاء الرفع ونشر الريلز...')
        
        finish_data = {
            'access_token': token,
            'upload_phase': 'finish',
            'video_id': video_id,
            'video_state': 'PUBLISHED'  # مطلوب لنشر الريلز وظهوره على الصفحة
        }
        
        if description:
            finish_data['description'] = description
        if title:
            finish_data['title'] = title
        
        finish_response = session.post(start_url, data=finish_data, timeout=UPLOAD_TIMEOUT_FINISH)
        
        try:
            finish_body = finish_response.json()
        except Exception:
            finish_body = {'raw_response': finish_response.text}
        
        _progress(100)
        
        if finish_response.status_code in (200, 201) and 'error' not in finish_body:
            _log(f'✅ تم رفع ونشر الريلز بنجاح! (video_id: {video_id})')
            finish_body['video_id'] = video_id
            return finish_response.status_code, finish_body
        else:
            error = finish_body.get('error', {})
            error_msg = error.get('message', 'خطأ في إنهاء الرفع')
            _log(f'❌ فشل نشر الريلز: {error_msg}')
            log_error_to_file(f'Reels finish failed: {finish_body}', video_path)
            return finish_response.status_code, finish_body
            
    except requests.exceptions.Timeout:
        error_msg = 'انتهت مهلة الرفع المستأنف'
        _log(f'❌ {error_msg}')
        log_error_to_file(error_msg, video_path)
        return None, {'error': error_msg, 'error_code': 1002}
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f'خطأ في الاتصال: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': error_msg, 'error_code': 1001}
    
    except Exception as e:
        error_msg = f'خطأ غير متوقع: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': str(e), 'error_code': 5003}
    
    finally:
        if own_session and session:
            session.close()


def upload_reels_with_retry(page_id: str,
                            video_path: str,
                            token: str,
                            description: str = '',
                            title: str = '',
                            log_fn: Callable[[str], None] = None,
                            progress_callback: Callable[[float], None] = None,
                            max_retries: int = MAX_UPLOAD_RETRIES,
                            stop_event: threading.Event = None) -> Tuple[Optional[int], dict]:
    """
    رفع ريلز مع إعادة المحاولة تلقائياً في حالة الفشل.
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        description: وصف الريلز (اختياري)
        title: عنوان الريلز (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        max_retries: الحد الأقصى لعدد المحاولات
        stop_event: حدث لإيقاف الرفع (threading.Event)
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    def _is_stopped():
        return stop_event is not None and stop_event.is_set()
    
    last_error = None
    
    for attempt in range(max_retries):
        # التحقق من طلب الإيقاف قبل كل محاولة
        if _is_stopped():
            _log('⏹️ تم إيقاف الرفع')
            return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
        
        if attempt > 0:
            wait_time = (attempt * 10) + random.randint(5, 15)  # Exponential backoff مع jitter
            _log(f'⏳ المحاولة {attempt + 1}/{max_retries} بعد {wait_time} ثانية...')
            
            # التحقق من طلب الإيقاف أثناء الانتظار (Problem 2: تحسين سرعة الإيقاف)
            for _ in range(int(wait_time)):
                if _is_stopped():
                    _log('⏹️ تم إيقاف الرفع أثناء الانتظار')
                    return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                time.sleep(1)
        
        # التحقق من الاتصال بالإنترنت قبل المحاولة
        if not check_internet_connection():
            _log('📶 لا يوجد اتصال بالإنترنت - الانتظار...')
            for _ in range(6):  # انتظار حتى دقيقة
                if _is_stopped():
                    _log('⏹️ تم إيقاف الرفع أثناء انتظار الاتصال')
                    return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
                time.sleep(10)
                if check_internet_connection():
                    break
            else:
                _log('📶 فشل استعادة الاتصال')
                continue
        
        try:
            status, body = upload_reels(
                page_id=page_id,
                video_path=video_path,
                token=token,
                description=description,
                title=title,
                log_fn=log_fn,
                progress_callback=progress_callback,
                stop_event=stop_event
            )
            
            # التحقق من إيقاف العملية
            if _is_stopped() or (isinstance(body, dict) and body.get('cancelled')):
                _log('⏹️ تم إيقاف الرفع')
                return None, {'error': 'تم إيقاف الرفع بواسطة المستخدم', 'cancelled': True}
            
            # التحقق من النجاح
            if status in (200, 201) and 'error' not in body:
                return status, body
            
            # التحقق من أخطاء لا تستحق إعادة المحاولة
            if isinstance(body, dict) and 'error' in body:
                error = body['error']
                error_code = error.get('code', 0) if isinstance(error, dict) else 0
                
                # أخطاء دائمة لا تستحق إعادة المحاولة
                if error_code in [190, 100, 200]:  # توكن غير صالح، صلاحيات
                    _log(f'❌ خطأ دائم: {error}')
                    return status, body
            
            last_error = body
            
        except Exception as e:
            last_error = {'error': str(e)}
            _log(f'❌ خطأ في المحاولة {attempt + 1}: {e}')
            log_error_to_file(e, f'Reels upload retry {attempt + 1}')
    
    _log(f'❌ فشل رفع الريلز بعد {max_retries} محاولات')
    return None, last_error or {'error': 'فشل بعد عدة محاولات'}


def is_reels_upload_successful(status: Optional[int], body: dict) -> bool:
    """
    التحقق من نجاح عملية رفع الريلز.
    
    المعاملات:
        status: كود حالة HTTP للاستجابة
        body: جسم الاستجابة (dict أو str)
    
    العائد:
        True إذا نجح الرفع، False خلاف ذلك
    """
    if status is None:
        return False
    if not (200 <= status < 300):
        return False
    if isinstance(body, dict):
        if 'error' in body:
            return False
        if 'id' in body or 'video_id' in body or 'success' in body:
            return True
        return True
    if isinstance(body, str):
        return False
    return True


class ReelsController(QObject):
    """
    متحكم نشر الريلز
    Reels publishing controller - handles reels publishing logic
    
    يدير عملية نشر الريلز على فيسبوك مع:
    - التحقق من صحة الملفات
    - التحقق من مدة الفيديو
    - معالجة الأخطاء
    
    Manages reels publishing process on Facebook with:
    - File validation
    - Video duration validation
    - Error handling
    """
    
    # Signals
    publish_started = Signal(str)        # بدء النشر - Publish started (video_path)
    publish_progress = Signal(int, str)  # تقدم النشر - Publish progress (percentage, message)
    publish_completed = Signal(dict)     # اكتمال النشر - Publish completed (result)
    publish_failed = Signal(str)         # فشل النشر - Publish failed (error_message)
    log_message = Signal(str)            # رسالة سجل - Log message
    
    def __init__(self, api_service: FacebookAPIService, parent: Optional[QObject] = None) -> None:
        """
        تهيئة متحكم الريلز
        Initialize reels controller
        
        Args:
            api_service: خدمة Facebook API - Facebook API service
            parent: الكائن الأب - Parent QObject
        """
        super().__init__(parent)
        self.api_service = api_service
        self._current_publish: Optional[str] = None
        self._publish_lock = threading.Lock()
    
    @Slot(dict, str, str)
    def start_publish(self, page_job: Any, video_path: str, token: str) -> None:
        """
        بدء نشر الريلز - Start reels publishing
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            video_path: مسار الفيديو - Video path
            token: توكن الوصول - Access token
        """
        if not self._publish_lock.acquire(blocking=False):
            self.log_message.emit('تخطي: نشر ريلز سابق قيد التنفيذ')
            return
        
        try:
            self.publish_started.emit(video_path)
            self._current_publish = video_path
            
            # تنفيذ النشر
            result = self._perform_publish(page_job, video_path, token)
            
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
    
    def validate_reels(self, video_path: str) -> Tuple[bool, str]:
        """
        التحقق من صحة فيديو الريلز - Validate reels video
        
        Args:
            video_path: مسار الفيديو - Video path
        
        Returns:
            tuple: (valid: bool, error_message: str)
        """
        if not os.path.exists(video_path):
            return (False, 'الملف غير موجود')
        
        if not os.path.isfile(video_path):
            return (False, 'المسار ليس ملف')
        
        ext = Path(video_path).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            return (False, f'امتداد غير مدعوم: {ext}')
        
        try:
            size = os.path.getsize(video_path)
            if size == 0:
                return (False, 'الملف فارغ')
        except Exception as e:
            return (False, f'خطأ في قراءة الملف: {e}')
        
        # التحقق من مدة الفيديو (الريلز يجب أن يكون أقل من 90 ثانية)
        from reelsTasks import check_reels_duration
        is_valid, duration = check_reels_duration(video_path)
        if not is_valid:
            return (False, f'مدة الفيديو غير صالحة للريلز: {duration:.1f} ثانية')
        
        return (True, '')
    
    def _perform_publish(self, page_job: Any, video_path: str, token: str) -> Dict[str, Any]:
        """
        تنفيذ عملية النشر الفعلية - Perform actual publish
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            video_path: مسار الفيديو - Video path
            token: توكن الوصول - Access token
        
        Returns:
            dict: نتيجة النشر - Publish result
        """
        # استخدام دوال من reelsTasks
        # TODO: تنفيذ منطق نشر الريلز
        # هذا placeholder - سيتم تنفيذه عند الحاجة
        
        try:
            return {
                'success': False,
                'error': 'نشر الريلز غير مدعوم حالياً - قيد التطوير'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

