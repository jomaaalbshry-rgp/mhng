"""
Video validation and utility functions.

هذا الملف يحتوي على دوال مساعدة للتحقق من صحة الفيديوهات ومعالجة أسمائها.
"""

import os
import re
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.jobs.video_job import PageJob

from core.utils import run_subprocess
from core.constants import MAX_VIDEO_DURATION_SECONDS
from controllers.story_controller import get_random_emoji


# كلمات يجب إزالتها من أسماء الملفات (lowercase فقط - المقارنة تتم بـ case-insensitive)
TITLE_CLEANUP_WORDS = [
    'hd', 'fhd', 'uhd', 'sd', '4k', '8k', '1080p', '720p', '480p', '360p', '240p',
    'mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm',
    'copyright', 'free', 'no copyright', 'royalty free', 'ncs', 'nocopyright',
    'official', 'video', 'clip', 'music', 'audio', 'lyrics', 'lyric',
    'download', 'full', 'complete', 'final', 'version', 'edit', 'remix',
    'www', 'http', 'https', 'com', 'net', 'org',
    'hq', 'lq', 'high quality', 'low quality',
]

# أنماط regex للتنظيف
TITLE_CLEANUP_PATTERNS = [
    r'\[.*?\]',           # إزالة النص بين الأقواس المربعة [...]
    r'\(.*?\)',           # إزالة النص بين الأقواس الدائرية (...)
    r'\{.*?\}',           # إزالة النص بين الأقواس المعقوصة {...}
    r'@\w+',              # إزالة mentions
    r'#\w+',              # إزالة hashtags من الاسم
    r'https?://\S+',      # إزالة الروابط
    r'\b\d{3,4}p\b',      # إزالة الدقة مثل 1080p, 720p
    r'\b[Hh][Dd]\b',      # إزالة HD
    r'\b[4-8][Kk]\b',     # إزالة 4K, 8K
    r'\b(19|20)\d{2}\b',  # إزالة السنوات (1900-2099)
]


def clean_filename_for_title(filename: str, remove_extension: bool = True) -> str:
    """
    تنظيف اسم الملف لاستخدامه كعنوان.

    المعاملات:
        filename: اسم الملف الأصلي
        remove_extension: إزالة امتداد الملف

    العائد:
        اسم الملف المُنظّف والمقروء
    """
    if not filename:
        return filename

    title = filename

    # إزالة الامتداد إذا طُلب
    if remove_extension:
        title = os.path.splitext(title)[0]

    # استبدال الرموز بمسافات
    title = title.replace('_', ' ')
    title = title.replace('-', ' ')
    title = title.replace('.', ' ')
    title = title.replace('+', ' ')
    title = title.replace('~', ' ')

    # تطبيق أنماط regex
    for pattern in TITLE_CLEANUP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    # إزالة الكلمات غير المرغوبة (TITLE_CLEANUP_WORDS already lowercase)
    words = title.split()
    cleaned_words = []
    for word in words:
        word_lower = word.lower().strip()
        # تحقق من الكلمات الكاملة فقط
        if word_lower not in TITLE_CLEANUP_WORDS:
            cleaned_words.append(word)

    title = ' '.join(cleaned_words)

    # إزالة المسافات المتعددة
    title = re.sub(r'\s+', ' ', title)

    # إزالة المسافات من البداية والنهاية
    title = title.strip()

    # تحويل الحرف الأول إلى حرف كبير
    if title:
        title = title[0].upper() + title[1:] if len(title) > 1 else title.upper()

    return title


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

    # حساب نطاق التباين
    variation = int(base_interval * jitter_percent / 100)

    # إنشاء قيمة عشوائية ضمن النطاق
    jitter = random.randint(-variation, variation)

    # التأكد من أن النتيجة إيجابية (حد أدنى 10 ثواني)
    return max(10, base_interval + jitter)


def sort_video_files(files: list, sort_by: str = 'name', reverse: bool = False) -> list:
    """
    ترتيب ملفات الفيديو حسب المعيار المحدد.

    المعاملات:
        files: قائمة مسارات الملفات (Path objects)
        sort_by: معيار الترتيب ('name', 'random', 'date_created', 'date_modified')
        reverse: عكس الترتيب

    العائد:
        القائمة المرتبة
    """
    if not files:
        return files

    if sort_by == 'random':
        # ترتيب عشوائي
        shuffled = list(files)
        random.shuffle(shuffled)
        return shuffled

    elif sort_by == 'date_created':
        # ترتيب حسب تاريخ الإنشاء
        try:
            return sorted(files, key=lambda f: f.stat().st_ctime, reverse=reverse)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)

    elif sort_by == 'date_modified':
        # ترتيب حسب تاريخ التعديل
        try:
            return sorted(files, key=lambda f: f.stat().st_mtime, reverse=reverse)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)

    else:
        # الافتراضي: ترتيب أبجدي
        return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)


def validate_video(video_path: str, log_fn=None) -> dict:
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
    def _log(msg):
        if log_fn:
            log_fn(msg)

    result = {'valid': False, 'duration': 0, 'error': None}

    if not os.path.exists(video_path):
        result['error'] = 'الملف غير موجود'
        return result

    # التحقق من حجم الملف
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        result['error'] = 'الملف فارغ'
        return result

    # محاولة استخدام ffprobe للتحقق من الفيديو
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        output = run_subprocess(cmd, timeout=30, text=True)

        if output.returncode == 0 and output.stdout.strip():
            duration = float(output.stdout.strip())
            result['valid'] = True
            result['duration'] = duration

            # التحقق من مدة الفيديو
            if duration > MAX_VIDEO_DURATION_SECONDS:
                result['valid'] = False
                result['error'] = 'مدة الفيديو تتجاوز الحد الأقصى (4 ساعات)'
        else:
            result['error'] = 'فشل في قراءة معلومات الفيديو'
    except FileNotFoundError:
        # ffprobe غير متوفر، نفترض صلاحية الملف
        _log('تحذير: ffprobe غير متوفر، تم تخطي التحقق من صحة الفيديو')
        result['valid'] = True
    except subprocess.TimeoutExpired:
        result['error'] = 'انتهت مهلة التحقق من الفيديو'
    except Exception as e:
        result['error'] = f'خطأ في التحقق: {str(e)}'

    return result


def apply_template(template_str, page_job: 'PageJob', filename: str, file_index: int, total_files: int):
    """
    تطبيق قالب على النص مع استبدال المتغيرات.

    المتغيرات المدعومة:
        {filename} - اسم الملف
        {page_name} - اسم الصفحة
        {page_id} - معرف الصفحة
        {index} - رقم الملف الحالي
        {total} - إجمالي الملفات
        {datetime} - التاريخ والوقت
        {date} - التاريخ فقط (YYYY-MM-DD)
        {date_ymd} - التاريخ (YYYY-MM-DD)
        {date_dmy} - التاريخ (DD/MM/YYYY)
        {date_time} - التاريخ والوقت (YYYY-MM-DD HH:MM)
        {time} - الوقت فقط
        {day} - اسم اليوم بالعربية
        {random_emoji} - إيموجي عشوائي
    """
    now = datetime.now()
    days_ar = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']

    repl = {
        'filename': filename,
        'page_name': page_job.page_name,
        'page_id': page_job.page_id,
        'index': file_index,
        'total': total_files,
        'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date': now.strftime('%Y-%m-%d'),
        'date_ymd': now.strftime('%Y-%m-%d'),
        'date_dmy': now.strftime('%d/%m/%Y'),
        'date_time': now.strftime('%Y-%m-%d %H:%M'),
        'time': now.strftime('%H:%M'),
        'day': days_ar[now.weekday()],
        'random_emoji': get_random_emoji(),
    }
    out = template_str or ""
    for k, v in repl.items():
        out = out.replace(f'{{{k}}}', str(v))
    return out
