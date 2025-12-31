"""
متحكم الفيديو - Video Controller
يدير منطق رفع ونشر الفيديوهات
Manages video upload and publishing logic

هذه الوحدة تحتوي على جميع الوظائف والمنطق الخاص بمهام رفع الفيديوهات.
This module contains all functions and logic for video upload tasks.
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
from typing import Optional, Dict, Tuple, Any, Callable

import requests

from PySide6.QtCore import QObject, Signal, Slot, QThread

from services import UploadService
from core import BaseJob
from core import (
    get_subprocess_args, run_subprocess, check_internet_connection,
    check_disk_space, validate_file_extension, normalize_path,
    retry_with_backoff, RateLimiter, handle_rate_limit, get_file_info,
    get_temp_directory, NotificationSystem, VIDEO_EXTENSIONS
)

# ==================== ثوابت ====================

# الحد الأقصى لمدة الفيديو بالثواني (4 ساعات - حد فيسبوك)
MAX_VIDEO_DURATION_SECONDS = 4 * 60 * 60  # 14400 ثانية

# الحد الأقصى لحجم الفيديو (10 جيجابايت)
MAX_VIDEO_SIZE_BYTES = 10 * 1024 * 1024 * 1024

# حجم الجزء الافتراضي 32MB
CHUNK_SIZE_DEFAULT = 32 * 1024 * 1024

# الحد الأدنى للرفع المستأنف (50MB)
RESUMABLE_THRESHOLD_BYTES = 50 * 1024 * 1024

# ثوابت المحاولة والمهلة
MAX_UPLOAD_RETRIES = 3
UPLOAD_TIMEOUT_START = 60
UPLOAD_TIMEOUT_TRANSFER = 300
UPLOAD_TIMEOUT_FINISH = 180

# إصدار Facebook Graph API
FB_API_VERSION = 'v17.0'

# ثوابت العلامة المائية
WATERMARK_FFMPEG_TIMEOUT = 600
WATERMARK_MIN_OUTPUT_RATIO = 0.1  # الحد الأدنى لنسبة حجم الملف الناتج
WATERMARK_POSITIONS = {
    'top_left': 'x=20:y=20',
    'top_right': 'x=W-w-20:y=20',
    'bottom_left': 'x=20:y=H-h-20',
    'bottom_right': 'x=W-w-20:y=H-h-20',
    'center': 'x=(W-w)/2:y=(H-h)/2'
}


# ==================== تسجيل الأخطاء ====================

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
        log_file = logs_dir / f'video_error_{datetime.now().strftime("%Y%m%d")}.log'
        
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


def validate_video_file(video_path: str, log_fn=None) -> dict:
    """
    التحقق من صحة ملف الفيديو قبل الرفع.
    
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
    
    # التحقق من وجود الملف
    if not os.path.exists(video_path):
        result['error'] = 'الملف غير موجود'
        return result
    
    # التحقق من حجم الملف
    try:
        file_size = os.path.getsize(video_path)
        if file_size == 0:
            result['error'] = 'الملف فارغ'
            return result
    except OSError as e:
        result['error'] = f'فشل قراءة معلومات الملف: {e}'
        return result
    
    # محاولة استخدام ffprobe للتحقق من الفيديو
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_type', '-of', 'csv=p=0',
            video_path
        ]
        
        # استخدام run_subprocess لإخفاء نافذة FFmpeg على Windows
        probe_result = run_subprocess(cmd, timeout=30)
        
        if probe_result.returncode != 0 or b'video' not in probe_result.stdout:
            result['error'] = 'الملف ليس فيديو صالح'
            return result
        
        # الحصول على مدة الفيديو
        duration_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        duration_result = run_subprocess(duration_cmd, timeout=30, text=True)
        
        if duration_result.returncode == 0 and duration_result.stdout.strip():
            try:
                duration = float(duration_result.stdout.strip())
                result['duration'] = duration
                
                # التحقق من مدة الفيديو
                if duration > MAX_VIDEO_DURATION_SECONDS:
                    max_hours = MAX_VIDEO_DURATION_SECONDS // 3600
                    result['error'] = f'مدة الفيديو تتجاوز الحد الأقصى ({max_hours} ساعات)'
                    return result
            except ValueError:
                pass  # تجاهل خطأ تحويل المدة
        
        result['valid'] = True
        return result
        
    except FileNotFoundError:
        # ffprobe غير متوفر، نفترض صلاحية الملف بناءً على الحجم فقط
        if log_fn:
            log_fn('تحذير: ffprobe غير متوفر، تم تخطي التحقق من صحة الفيديو')
        result['valid'] = True
        return result
    except subprocess.TimeoutExpired:
        result['error'] = 'انتهت مهلة التحقق من الفيديو'
        return result
    except Exception as e:
        result['error'] = f'خطأ في التحقق: {str(e)}'
        return result


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


class VideoJob(BaseJob):
    """
    وظيفة رفع فيديوهات لصفحة فيسبوك.
    ترث من BaseJob وتضيف خصائص خاصة بالفيديو.
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
        
        # خصائص خاصة بالفيديو
        self.title_template = title_template
        self.description_template = description_template
        self.chunk_size = chunk_size
        self.use_filename_as_title = use_filename_as_title
        self.jitter_enabled = jitter_enabled
        self.jitter_percent = jitter_percent

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
            'job_type': 'video'
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
            use_smart_schedule=d.get('use_smart_schedule', False),
            template_id=d.get('template_id'),
            app_name=d.get('app_name', '')
        )
        obj.next_index = d.get('next_index', 0)
        return obj


def get_video_files(folder_path: str, sort_by: str = 'name') -> list:
    """
    الحصول على قائمة ملفات الفيديو من مجلد معين.
    
    المعاملات:
        folder_path: مسار المجلد
        sort_by: طريقة الترتيب ('name', 'random', 'date_created', 'date_modified')
    
    العائد:
        قائمة مسارات ملفات الفيديو مرتبة
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    files = [p for p in folder.iterdir() 
             if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
    
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


def count_video_files(folder_path: str) -> int:
    """
    حساب عدد ملفات الفيديو في مجلد.
    
    المعاملات:
        folder_path: مسار المجلد
    
    العائد:
        عدد ملفات الفيديو
    """
    folder = Path(folder_path)
    if not folder.exists():
        return 0
    
    return len([p for p in folder.iterdir() 
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])


# ==================== دوال العلامة المائية (Watermark) ====================

def add_watermark_to_video(video_path: str,
                           watermark_path: str,
                           output_path: str = None,
                           position: str = 'bottom_right',
                           opacity: float = 0.8,
                           scale: float = 0.15,
                           custom_x: int = None,
                           custom_y: int = None,
                           log_fn: Callable[[str], None] = None) -> Tuple[bool, str]:
    """
    إضافة علامة مائية إلى فيديو باستخدام FFmpeg.
    
    المعاملات:
        video_path: مسار الفيديو الأصلي
        watermark_path: مسار صورة العلامة المائية
        output_path: مسار الفيديو الناتج (اختياري - يتم إنشاؤه تلقائياً)
        position: موقع العلامة المائية ('top_left', 'top_right', 'bottom_left', 'bottom_right', 'center')
        opacity: شفافية العلامة المائية (0.0 - 1.0)
        scale: حجم العلامة المائية نسبة إلى الفيديو (0.0 - 1.0)
        custom_x: إحداثي X مخصص (اختياري)
        custom_y: إحداثي Y مخصص (اختياري)
        log_fn: دالة التسجيل (اختياري)
    
    العائد:
        tuple: (نجاح: bool, مسار_الفيديو_الناتج_أو_رسالة_الخطأ: str)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    # التحقق من وجود الملفات
    if not os.path.exists(video_path):
        return False, 'ملف الفيديو غير موجود'
    
    if not os.path.exists(watermark_path):
        return False, 'ملف العلامة المائية غير موجود'
    
    # إنشاء مسار الإخراج إذا لم يُحدد
    if output_path is None:
        temp_dir = get_temp_directory()
        video_name = Path(video_path).stem
        video_ext = Path(video_path).suffix
        output_path = str(temp_dir / f'{video_name}_watermarked{video_ext}')
    
    try:
        _log(f'🎨 جاري إضافة العلامة المائية...')
        
        # بناء فلتر العلامة المائية
        # حساب الحجم النسبي
        scale_filter = f'scale=iw*{scale}:-1'
        
        # تحديد الموقع
        if custom_x is not None and custom_y is not None:
            position_filter = f'x={custom_x}:y={custom_y}'
        else:
            position_filter = WATERMARK_POSITIONS.get(position, WATERMARK_POSITIONS['bottom_right'])
        
        # فلتر الشفافية
        opacity_filter = f'format=rgba,colorchannelmixer=aa={opacity}'
        
        # بناء الأمر
        filter_complex = f'[1:v]{scale_filter},{opacity_filter}[wm];[0:v][wm]overlay={position_filter}'
        
        cmd = [
            'ffmpeg', '-y',  # -y للكتابة فوق الملف إذا وجد
            '-i', video_path,
            '-i', watermark_path,
            '-filter_complex', filter_complex,
            '-c:a', 'copy',  # نسخ الصوت بدون إعادة ترميز
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            output_path
        ]
        
        # تنفيذ الأمر
        result = run_subprocess(cmd, timeout=WATERMARK_FFMPEG_TIMEOUT)
        
        if result.returncode == 0 and os.path.exists(output_path):
            # التحقق من أن الملف الناتج ليس فارغاً
            output_size = os.path.getsize(output_path)
            input_size = os.path.getsize(video_path)
            
            if output_size < input_size * WATERMARK_MIN_OUTPUT_RATIO:
                os.remove(output_path)
                return False, 'الملف الناتج صغير جداً - قد يكون تالفاً'
            
            _log(f'✅ تم إضافة العلامة المائية بنجاح')
            return True, output_path
        else:
            error_msg = result.stderr.decode('utf-8', errors='replace') if result.stderr else 'خطأ غير معروف'
            _log(f'❌ فشل إضافة العلامة المائية: {error_msg[:200]}')
            return False, f'فشل FFmpeg: {error_msg[:200]}'
            
    except subprocess.TimeoutExpired:
        _log('❌ انتهت مهلة إضافة العلامة المائية')
        return False, 'انتهت مهلة المعالجة'
    
    except FileNotFoundError:
        _log('❌ FFmpeg غير مثبت')
        return False, 'FFmpeg غير مثبت على النظام'
    
    except Exception as e:
        _log(f'❌ خطأ: {str(e)}')
        log_error_to_file(e, f'Watermark error: {video_path}')
        return False, str(e)


def remove_watermark_temp_file(temp_path: str, delay: float = 1.0):
    """
    حذف ملف العلامة المائية المؤقت بعد تأخير.
    
    المعاملات:
        temp_path: مسار الملف المؤقت
        delay: التأخير بالثواني قبل الحذف
    """
    import threading
    
    def delayed_delete():
        time.sleep(delay)
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except (OSError, PermissionError):
            pass
    
    threading.Thread(target=delayed_delete, daemon=True).start()


# ==================== دوال الرفع ====================

def upload_video(page_id: str,
                 video_path: str,
                 token: str,
                 title: str = '',
                 description: str = '',
                 log_fn: Callable[[str], None] = None,
                 progress_callback: Callable[[float], None] = None,
                 session: requests.Session = None) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو على صفحة فيسبوك.
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        title: عنوان الفيديو (اختياري)
        description: وصف الفيديو (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        session: جلسة requests للأداء الأفضل (اختياري)
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    def _progress(percent):
        if progress_callback:
            progress_callback(percent)
    
    # التحقق من صحة الفيديو
    validation = validate_video_file(video_path, log_fn)
    if not validation['valid']:
        error_msg = validation.get('error', 'فشل التحقق من صحة الفيديو')
        _log(f'❌ فشل التحقق: {error_msg}')
        return None, {'error': error_msg}
    
    file_size = os.path.getsize(video_path)
    
    # استخدام الرفع المستأنف للملفات الكبيرة
    if file_size > RESUMABLE_THRESHOLD_BYTES:
        _log(f'📤 ملف كبير ({file_size / (1024*1024):.2f} MB) - استخدام الرفع المستأنف')
        return resumable_upload(page_id, video_path, token, title, 
                                description, log_fn, progress_callback, session)
    
    # استخدام Session الممررة أو إنشاء واحدة جديدة
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    try:
        _log(f'📤 بدء رفع الفيديو: {os.path.basename(video_path)}')
        _progress(0)
        
        # إعداد البيانات
        url = f'https://graph-video.facebook.com/{FB_API_VERSION}/{page_id}/videos'
        
        with open(video_path, 'rb') as video_file:
            files = {
                'source': (os.path.basename(video_path), video_file, 'video/mp4')
            }
            data = {
                'access_token': token
            }
            
            if title:
                data['title'] = title
            if description:
                data['description'] = description
            
            # محاكاة التقدم
            _progress(30)
            
            # رفع الفيديو
            response = session.post(url, data=data, files=files, 
                                    timeout=UPLOAD_TIMEOUT_TRANSFER)
            
            _progress(80)
        
        try:
            body = response.json()
        except Exception:
            body = {'raw_response': response.text}
        
        # التحقق من الاستجابة
        if response.status_code in (200, 201) and 'error' not in body:
            video_id = body.get('id')
            _log(f'✅ تم رفع الفيديو بنجاح! (video_id: {video_id})')
            _progress(100)
            return response.status_code, body
        else:
            error = body.get('error', {})
            error_msg = error.get('message', 'خطأ غير معروف')
            _log(f'❌ فشل رفع الفيديو: {error_msg}')
            log_error_to_file(f'Video upload failed: {body}', video_path)
            return response.status_code, body
            
    except requests.exceptions.Timeout:
        error_msg = 'انتهت مهلة الرفع'
        _log(f'❌ {error_msg}')
        log_error_to_file(error_msg, video_path)
        return None, {'error': error_msg}
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f'خطأ في الاتصال: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': error_msg}
    
    except Exception as e:
        error_msg = f'خطأ غير متوقع: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': str(e)}
    
    finally:
        if own_session and session:
            session.close()


def resumable_upload(page_id: str,
                     video_path: str,
                     token: str,
                     title: str = '',
                     description: str = '',
                     log_fn: Callable[[str], None] = None,
                     progress_callback: Callable[[float], None] = None,
                     session: requests.Session = None,
                     chunk_size: int = CHUNK_SIZE_DEFAULT) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو باستخدام الرفع المستأنف (Resumable Upload).
    
    هذه الطريقة مناسبة للملفات الكبيرة وتدعم:
    - رفع الملف على مراحل (chunks)
    - استئناف الرفع في حالة الانقطاع
    - عرض تقدم الرفع بشكل دقيق
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        title: عنوان الفيديو (اختياري)
        description: وصف الفيديو (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        session: جلسة requests للأداء الأفضل (اختياري)
        chunk_size: حجم كل جزء بالبايت
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    def _progress(percent):
        if progress_callback:
            progress_callback(percent)
    
    # استخدام Session الممررة أو إنشاء واحدة جديدة
    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True
    
    rate_limiter = RateLimiter()
    file_size = os.path.getsize(video_path)
    file_name = os.path.basename(video_path)
    
    try:
        _log(f'📤 بدء الرفع المستأنف: {file_name} ({file_size / (1024*1024):.2f} MB)')
        _progress(0)
        
        # الخطوة 1: بدء جلسة الرفع
        start_url = f'https://graph-video.facebook.com/{FB_API_VERSION}/{page_id}/videos'
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
                time.sleep(wait_time)
                # إعادة المحاولة
                start_response = session.post(start_url, data=start_data, timeout=UPLOAD_TIMEOUT_START)
                start_body = start_response.json()
                if 'error' in start_body:
                    _log(f'❌ فشل بدء جلسة الرفع: {start_body}')
                    return start_response.status_code, start_body
            else:
                _log(f'❌ فشل بدء جلسة الرفع: {start_body}')
                return start_response.status_code, start_body
        
        upload_session_id = start_body.get('upload_session_id')
        video_id = start_body.get('video_id')
        
        if not upload_session_id:
            _log('❌ لم يتم الحصول على upload_session_id')
            return None, {'error': 'missing_upload_session_id'}
        
        _log(f'✅ تم بدء جلسة الرفع (video_id: {video_id})')
        _progress(5)
        
        # الخطوة 2: رفع الفيديو على مراحل
        uploaded_bytes = 0
        start_offset = 0
        
        with open(video_path, 'rb') as video_file:
            while uploaded_bytes < file_size:
                # قراءة الجزء التالي
                chunk = video_file.read(chunk_size)
                if not chunk:
                    break
                
                chunk_data = {
                    'access_token': token,
                    'upload_phase': 'transfer',
                    'upload_session_id': upload_session_id,
                    'start_offset': start_offset
                }
                
                files = {
                    'video_file_chunk': ('chunk', chunk, 'application/octet-stream')
                }
                
                # محاولة رفع الجزء مع إعادة المحاولة
                for attempt in range(MAX_UPLOAD_RETRIES):
                    try:
                        chunk_response = session.post(
                            start_url,
                            data=chunk_data,
                            files=files,
                            timeout=UPLOAD_TIMEOUT_TRANSFER
                        )
                        
                        try:
                            chunk_body = chunk_response.json()
                        except Exception:
                            chunk_body = {}
                        
                        if chunk_response.status_code in (200, 201) and 'error' not in chunk_body:
                            # تحديث الإزاحة
                            new_offset = chunk_body.get('start_offset', start_offset + len(chunk))
                            uploaded_bytes = int(new_offset)
                            start_offset = uploaded_bytes
                            
                            progress = (uploaded_bytes / file_size) * 85 + 5  # 5-90%
                            _progress(progress)
                            break
                        else:
                            # التحقق من Rate Limiting
                            wait_time = handle_rate_limit(chunk_body, rate_limiter, log_fn)
                            if wait_time > 0:
                                time.sleep(wait_time)
                                continue
                            
                            if attempt < MAX_UPLOAD_RETRIES - 1:
                                wait = (attempt + 1) * 5
                                _log(f'⚠️ فشل رفع الجزء - إعادة المحاولة بعد {wait} ثانية...')
                                time.sleep(wait)
                            else:
                                _log(f'❌ فشل رفع الجزء بعد {MAX_UPLOAD_RETRIES} محاولات')
                                return chunk_response.status_code, chunk_body
                                
                    except requests.exceptions.Timeout:
                        if attempt < MAX_UPLOAD_RETRIES - 1:
                            _log(f'⚠️ انتهت مهلة رفع الجزء - إعادة المحاولة...')
                            time.sleep(5)
                        else:
                            raise
                    
                    except requests.exceptions.ConnectionError:
                        # انتظار عودة الاتصال
                        _log('📶 فحص الاتصال بالإنترنت...')
                        if not check_internet_connection():
                            _log('📶 انتظار عودة الاتصال...')
                            time.sleep(30)
                            if not check_internet_connection():
                                raise
                        time.sleep(5)
        
        _progress(90)
        
        # الخطوة 3: إنهاء الرفع
        _log('📋 جاري إنهاء الرفع ونشر الفيديو...')
        
        finish_data = {
            'access_token': token,
            'upload_phase': 'finish',
            'upload_session_id': upload_session_id
        }
        
        if title:
            finish_data['title'] = title
        if description:
            finish_data['description'] = description
        
        finish_response = session.post(start_url, data=finish_data, timeout=UPLOAD_TIMEOUT_FINISH)
        
        try:
            finish_body = finish_response.json()
        except Exception:
            finish_body = {'raw_response': finish_response.text}
        
        _progress(100)
        
        if finish_response.status_code in (200, 201) and 'error' not in finish_body:
            final_video_id = finish_body.get('id') or video_id
            _log(f'✅ تم رفع ونشر الفيديو بنجاح! (video_id: {final_video_id})')
            finish_body['video_id'] = final_video_id
            return finish_response.status_code, finish_body
        else:
            error = finish_body.get('error', {})
            error_msg = error.get('message', 'خطأ في إنهاء الرفع')
            _log(f'❌ فشل نشر الفيديو: {error_msg}')
            log_error_to_file(f'Video finish failed: {finish_body}', video_path)
            return finish_response.status_code, finish_body
            
    except requests.exceptions.Timeout:
        error_msg = 'انتهت مهلة الرفع المستأنف'
        _log(f'❌ {error_msg}')
        log_error_to_file(error_msg, video_path)
        return None, {'error': error_msg}
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f'خطأ في الاتصال: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': error_msg}
    
    except Exception as e:
        error_msg = f'خطأ غير متوقع: {str(e)}'
        _log(f'❌ {error_msg}')
        log_error_to_file(e, video_path)
        return None, {'error': str(e)}
    
    finally:
        if own_session and session:
            session.close()


def upload_video_with_retry(page_id: str,
                            video_path: str,
                            token: str,
                            title: str = '',
                            description: str = '',
                            log_fn: Callable[[str], None] = None,
                            progress_callback: Callable[[float], None] = None,
                            max_retries: int = MAX_UPLOAD_RETRIES) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو مع إعادة المحاولة تلقائياً في حالة الفشل.
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        title: عنوان الفيديو (اختياري)
        description: وصف الفيديو (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
        max_retries: الحد الأقصى لعدد المحاولات
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    last_error = None
    
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = (attempt * 10) + random.randint(5, 15)  # Exponential backoff مع jitter
            _log(f'⏳ المحاولة {attempt + 1}/{max_retries} بعد {wait_time} ثانية...')
            time.sleep(wait_time)
        
        # التحقق من الاتصال بالإنترنت قبل المحاولة
        if not check_internet_connection():
            _log('📶 لا يوجد اتصال بالإنترنت - الانتظار...')
            for _ in range(6):  # انتظار حتى دقيقة
                time.sleep(10)
                if check_internet_connection():
                    break
            else:
                _log('📶 فشل استعادة الاتصال')
                continue
        
        try:
            status, body = upload_video(
                page_id=page_id,
                video_path=video_path,
                token=token,
                title=title,
                description=description,
                log_fn=log_fn,
                progress_callback=progress_callback
            )
            
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
            log_error_to_file(e, f'Video upload retry {attempt + 1}')
    
    _log(f'❌ فشل رفع الفيديو بعد {max_retries} محاولات')
    return None, last_error or {'error': 'فشل بعد عدة محاولات'}


def upload_video_with_watermark(page_id: str,
                                video_path: str,
                                token: str,
                                watermark_path: str,
                                title: str = '',
                                description: str = '',
                                watermark_position: str = 'bottom_right',
                                watermark_opacity: float = 0.8,
                                watermark_scale: float = 0.15,
                                watermark_x: int = None,
                                watermark_y: int = None,
                                log_fn: Callable[[str], None] = None,
                                progress_callback: Callable[[float], None] = None) -> Tuple[Optional[int], dict]:
    """
    رفع فيديو مع إضافة علامة مائية.
    
    المعاملات:
        page_id: معرف الصفحة
        video_path: مسار ملف الفيديو
        token: توكن الصفحة
        watermark_path: مسار صورة العلامة المائية
        title: عنوان الفيديو (اختياري)
        description: وصف الفيديو (اختياري)
        watermark_position: موقع العلامة المائية
        watermark_opacity: شفافية العلامة المائية
        watermark_scale: حجم العلامة المائية
        watermark_x: إحداثي X مخصص (اختياري)
        watermark_y: إحداثي Y مخصص (اختياري)
        log_fn: دالة التسجيل
        progress_callback: دالة لعرض التقدم
    
    العائد:
        (status_code, response_body)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    watermarked_path = None
    
    try:
        # إضافة العلامة المائية
        success, result = add_watermark_to_video(
            video_path=video_path,
            watermark_path=watermark_path,
            position=watermark_position,
            opacity=watermark_opacity,
            scale=watermark_scale,
            custom_x=watermark_x,
            custom_y=watermark_y,
            log_fn=log_fn
        )
        
        if not success:
            _log(f'⚠️ فشل إضافة العلامة المائية: {result} - سيتم رفع الفيديو بدون علامة مائية')
            watermarked_path = video_path
        else:
            watermarked_path = result
        
        # رفع الفيديو
        status, body = upload_video_with_retry(
            page_id=page_id,
            video_path=watermarked_path,
            token=token,
            title=title,
            description=description,
            log_fn=log_fn,
            progress_callback=progress_callback
        )
        
        return status, body
        
    finally:
        # حذف الملف المؤقت إذا تم إنشاؤه
        if watermarked_path and watermarked_path != video_path:
            remove_watermark_temp_file(watermarked_path)


def is_upload_successful(status: Optional[int], body: dict) -> bool:
    """
    التحقق من نجاح عملية رفع الفيديو.
    
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


def calculate_dynamic_timeout(file_size: int, base_timeout: int = 60) -> int:
    """
    حساب مهلة ديناميكية بناءً على حجم الملف.
    
    المعاملات:
        file_size: حجم الملف بالبايت
        base_timeout: المهلة الأساسية بالثواني
    
    العائد:
        المهلة المحسوبة بالثواني
    """
    # افتراض سرعة رفع 1 MB/s كحد أدنى
    size_mb = file_size / (1024 * 1024)
    estimated_time = size_mb * 2  # ضعف الوقت المتوقع للأمان
    
    # الحد الأدنى والأقصى
    min_timeout = base_timeout
    max_timeout = 3600  # ساعة كحد أقصى
    
    return min(max(int(estimated_time), min_timeout), max_timeout)


class VideoController(QObject):
    """
    متحكم رفع الفيديو
    Video upload controller - handles upload logic
    
    يدير عملية رفع الفيديوهات إلى فيسبوك مع:
    - التحقق من صحة الملفات
    - متابعة التقدم
    - معالجة الأخطاء
    
    Manages video upload process to Facebook with:
    - File validation
    - Progress tracking
    - Error handling
    """
    
    # Signals
    upload_started = Signal(str)         # بدء الرفع - Upload started (video_path)
    upload_progress = Signal(int, str)   # تقدم الرفع - Upload progress (percentage, message)
    upload_completed = Signal(dict)      # اكتمال الرفع - Upload completed (result)
    upload_failed = Signal(str)          # فشل الرفع - Upload failed (error_message)
    log_message = Signal(str)            # رسالة سجل - Log message
    
    def __init__(self, upload_service: UploadService, parent: Optional[QObject] = None) -> None:
        """
        تهيئة متحكم الفيديو
        Initialize video controller
        
        Args:
            upload_service: خدمة الرفع - Upload service
            parent: الكائن الأب - Parent QObject
        """
        super().__init__(parent)
        self.upload_service = upload_service
        self._current_upload: Optional[str] = None
        self._upload_lock = threading.Lock()
    
    @Slot(dict, str, str, object)
    def start_upload(self, page_job: Any, video_path: str, token: str, ui_signals: Any) -> None:
        """
        بدء رفع الفيديو - Start video upload
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            video_path: مسار الفيديو - Video path
            token: توكن الوصول - Access token
            ui_signals: إشارات الواجهة - UI signals
        """
        if not self._upload_lock.acquire(blocking=False):
            self.log_message.emit('تخطي: رفع سابق قيد التنفيذ')
            return
        
        try:
            self.upload_started.emit(video_path)
            self._current_upload = video_path
            
            # تنفيذ الرفع
            status, body = self._perform_upload(page_job, video_path, token, ui_signals)
            
            if self._is_upload_successful(status, body):
                result = {
                    'status': 'success',
                    'video_path': video_path,
                    'video_id': body.get('id') if isinstance(body, dict) else None,
                    'response': body
                }
                self.upload_completed.emit(result)
            else:
                error_msg = self._extract_error_message(body)
                self.upload_failed.emit(error_msg)
        except Exception as e:
            self.upload_failed.emit(str(e))
        finally:
            self._current_upload = None
            self._upload_lock.release()
    
    @Slot()
    def cancel_upload(self) -> None:
        """إلغاء الرفع الحالي - Cancel current upload"""
        if self._current_upload:
            self.log_message.emit(f'إلغاء الرفع: {self._current_upload}')
            self._current_upload = None
    
    def validate_video(self, video_path: str) -> Tuple[bool, str]:
        """
        التحقق من صحة الفيديو - Validate video file
        
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
        
        return (True, '')
    
    def _perform_upload(self, page_job: Any, video_path: str, token: str, 
                        ui_signals: Any) -> Tuple[int, Any]:
        """
        تنفيذ عملية الرفع الفعلية - Perform actual upload
        
        Args:
            page_job: وظيفة الصفحة - Page job object
            video_path: مسار الفيديو - Video path
            token: توكن الوصول - Access token
            ui_signals: إشارات الواجهة - UI signals
        
        Returns:
            tuple: (status_code: int, response_body: Any)
        """
        # استخدام upload_video_once من admin.py (سيتم استيرادها)
        from admin import upload_video_once
        
        status, body = upload_video_once(
            page_job, video_path, token, ui_signals,
            page_job.title_template, page_job.description_template,
            lambda msg: self.log_message.emit(msg)
        )
        
        return status, body
    
    def _is_upload_successful(self, status: int, body: Any) -> bool:
        """
        التحقق من نجاح الرفع - Check if upload was successful
        
        Args:
            status: رمز الحالة - Status code
            body: جسم الاستجابة - Response body
        
        Returns:
            bool: True إذا نجح الرفع - True if upload successful
        """
        from admin import is_upload_successful
        return is_upload_successful(status, body)
    
    def _extract_error_message(self, body: Any) -> str:
        """
        استخراج رسالة الخطأ من الاستجابة - Extract error message from response
        
        Args:
            body: جسم الاستجابة - Response body
        
        Returns:
            str: رسالة الخطأ - Error message
        """
        if isinstance(body, dict):
            error = body.get('error', {})
            if isinstance(error, dict):
                return error.get('message', str(body))
            return str(error)
        return str(body)

