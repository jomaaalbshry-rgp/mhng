"""
Upload helper functions for video, story, and reels uploads.

هذا الملف يحتوي على دوال مساعدة لرفع الفيديوهات والستوري والريلز.
"""

import os
import requests
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.jobs.video_job import PageJob

from core.video_utils import clean_filename_for_title, apply_template
from core.constants import (
    CHUNK_SIZE_DEFAULT, RESUMABLE_THRESHOLD_BYTES,
    UPLOAD_TIMEOUT_START, UPLOAD_TIMEOUT_TRANSFER, UPLOAD_TIMEOUT_FINISH,
    WATERMARK_FFMPEG_TIMEOUT, WATERMARK_MIN_OUTPUT_RATIO, WATERMARK_FILE_CLOSE_DELAY,
    WATERMARK_CLEANUP_DELAY, VIDEO_EXTENSIONS
)
from core.utils import run_subprocess
from core.notifications import NotificationSystem
from ui.signals import UiSignals
from services.upload_service import UploadService


# مثيل خدمة الرفع
_upload_service = UploadService()


def resumable_upload(page_job: 'PageJob', video_path, token, ui_signals: UiSignals,
                     final_title="", final_description=""):
    """
    رفع فيديو بشكل مجزأ إلى فيسبوك.
    Upload video to Facebook in chunks (resumable upload).

    Args:
        page_job: وظيفة الصفحة - Page job
        video_path: مسار الفيديو - Video path
        token: توكن الوصول - Access token
        ui_signals: إشارات الواجهة - UI signals
        final_title: عنوان الفيديو - Video title
        final_description: وصف الفيديو - Video description

    Returns:
        tuple: (status_code, response_body)
    """
    chunk_size = page_job.chunk_size if page_job.chunk_size > 0 else CHUNK_SIZE_DEFAULT

    return _upload_service.resumable_upload(
        page_id=page_job.page_id,
        video_path=video_path,
        token=token,
        ui_signals=ui_signals,
        final_title=final_title,
        final_description=final_description,
        chunk_size=chunk_size,
        upload_timeout_start=UPLOAD_TIMEOUT_START,
        upload_timeout_transfer=UPLOAD_TIMEOUT_TRANSFER,
        upload_timeout_finish=UPLOAD_TIMEOUT_FINISH,
        page_job=page_job
    )


def apply_watermark_to_video(video_path: str, job: 'PageJob', log_fn) -> str:
    """
    تطبيق العلامة المائية على الفيديو إذا كانت مفعلة بشكل آمن.
    Apply watermark to video if enabled.

    المعاملات:
        video_path: مسار الفيديو الأصلي - Original video path
        job: وظيفة الصفحة التي تحتوي على إعدادات العلامة المائية - Page job with watermark settings
        log_fn: دالة التسجيل - Logging function

    العائد:
        مسار الفيديو النهائي (الأصلي أو المعدّل)
        Final video path (original or modified)
    """
    # التحقق من تفعيل العلامة المائية
    if not getattr(job, 'watermark_enabled', False):
        return video_path

    watermark_path = getattr(job, 'watermark_path', '')
    if not watermark_path:
        return video_path

    # الحصول على إعدادات العلامة المائية
    position = getattr(job, 'watermark_position', 'bottom_right')
    opacity = getattr(job, 'watermark_opacity', 0.8)
    scale = getattr(job, 'watermark_scale', 0.15)
    watermark_x = getattr(job, 'watermark_x', None)
    watermark_y = getattr(job, 'watermark_y', None)

    return _upload_service.apply_watermark_to_video(
        video_path=video_path,
        watermark_path=watermark_path,
        position=position,
        opacity=opacity,
        scale=scale,
        watermark_x=watermark_x,
        watermark_y=watermark_y,
        log_fn=log_fn,
        run_subprocess_fn=run_subprocess,
        notification_system=NotificationSystem,
        page_name=job.page_name,
        watermark_ffmpeg_timeout=WATERMARK_FFMPEG_TIMEOUT,
        watermark_min_output_ratio=WATERMARK_MIN_OUTPUT_RATIO,
        watermark_file_close_delay=WATERMARK_FILE_CLOSE_DELAY
    )


def cleanup_temp_watermark_file(video_path: str, original_path: str, log_fn=None):
    """
    حذف ملف الفيديو المؤقت بعد الرفع إذا كان مختلفاً عن الأصلي بشكل آمن.
    Delete temporary video file after upload if different from original.

    المعاملات:
        video_path: مسار الفيديو المستخدم (قد يكون مؤقتاً) - Video path used (may be temporary)
        original_path: مسار الفيديو الأصلي - Original video path
        log_fn: دالة التسجيل - Logging function
    """
    _upload_service.cleanup_temp_watermark_file(
        video_path=video_path,
        original_path=original_path,
        log_fn=log_fn,
        watermark_cleanup_delay=WATERMARK_CLEANUP_DELAY
    )


def upload_video_once(page_job: 'PageJob', video_path, token, ui_signals: UiSignals,
                      title_tmpl, desc_tmpl, log_fn):
    """
    رفع فيديو واحد إلى فيسبوك مع دعم العلامة المائية.

    هذه الدالة محمية من الأخطاء لمنع crash البرنامج.
    """
    endpoint = f'https://graph-video.facebook.com/v17.0/{page_job.page_id}/videos'
    folder = Path(page_job.folder)

    # متغيرات للتتبع
    original_video_path = video_path
    video_path_to_upload = video_path

    try:
        # الحصول على قائمة الملفات
        try:
            files_all = sorted([p for p in folder.iterdir()
                                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])
        except Exception:
            files_all = [Path(video_path)]

        filename = os.path.basename(video_path)
        idx = files_all.index(Path(video_path)) if Path(video_path) in files_all else 0

        # تنظيف اسم الملف تلقائياً (داخلياً)
        original_name = os.path.splitext(filename)[0]
        display_filename = clean_filename_for_title(filename)
        # Problem 1 fix: إزالة رسالة السجل الزائدة
        # if display_filename != original_name:
        #     log_fn(f'🧹 تم تنظيف العنوان: "{original_name}" -> "{display_filename}"')

        title = display_filename if page_job.use_filename_as_title else apply_template(title_tmpl, page_job, display_filename, idx + 1, len(files_all))
        description = apply_template(desc_tmpl, page_job, display_filename, idx + 1, len(files_all))
        # Problem 1 fix: إزالة رسالة السجل الزائدة
        # log_fn(f'رفع بسيط: {filename} -> {page_job.page_name} عنوان="{title}"')

        # تطبيق العلامة المائية إذا كانت مفعلة
        try:
            video_path_to_upload = apply_watermark_to_video(video_path, page_job, log_fn)
        except Exception as wm_error:
            log_fn(f'⚠️ خطأ في العلامة المائية: {wm_error}')
            video_path_to_upload = video_path  # استخدام الفيديو الأصلي

        # محاولة الرفع البسيط
        try:
            with open(video_path_to_upload, 'rb') as f:
                data = {
                    'access_token': token,
                    'title': title,
                    'description': description,
                    'published': 'true'
                }
                r = requests.post(endpoint, data=data, files={'source': (filename, f, 'video/mp4')}, timeout=300)
        except Exception as e:
            log_fn(f'خطأ رفع بسيط: {e}')
            try:
                size = os.path.getsize(original_video_path)
            except Exception:
                size = 0

            if size >= RESUMABLE_THRESHOLD_BYTES:
                log_fn('تحويل للمجزأ بسبب الحجم.')
                # استخدام الفيديو مع العلامة المائية إذا كان موجوداً
                try:
                    result = resumable_upload(page_job, video_path_to_upload, token, ui_signals, title, description)
                    return result
                except Exception as res_error:
                    log_fn(f'❌ خطأ في الرفع المجزأ: {res_error}')
                    return None, {'error': 'resumable_exception', 'detail': str(res_error)}
            return None, {'error': 'simple_exception', 'detail': str(e)}

        status = getattr(r, 'status_code', None)
        try:
            body = r.json()
        except Exception:
            body = r.text

        # التحقق من الحاجة للرفع المجزأ
        try:
            file_size = os.path.getsize(video_path_to_upload) if os.path.exists(video_path_to_upload) else 0
        except Exception:
            file_size = 0

        if status == 413 or (isinstance(body, dict) and body.get('error', {}).get('code') == 413) \
           or file_size >= RESUMABLE_THRESHOLD_BYTES:
            log_fn('تحويل للمجزأ (413 أو الحجم).')
            try:
                result = resumable_upload(page_job, video_path_to_upload, token, ui_signals, title, description)
                return result
            except Exception as res_error:
                log_fn(f'❌ خطأ في الرفع المجزأ: {res_error}')
                return None, {'error': 'resumable_exception', 'detail': str(res_error)}

        try:
            ui_signals.progress_signal.emit(100, 'تم الرفع البسيط 100%')
        except Exception:
            pass  # تجاهل أخطاء إرسال الإشارة

        log_fn(f'نتيجة الرفع البسيط ({status}): {body}')
        return status, body

    except Exception as e:
        # التقاط أي خطأ غير متوقع
        log_fn(f'❌ خطأ غير متوقع في عملية الرفع: {e}')
        try:
            from controllers.story_controller import log_error_to_file
            log_error_to_file(e, f'Unexpected error in upload_video_once: {video_path}')
        except Exception:
            pass
        return None, {'error': 'unexpected_exception', 'detail': str(e)}

    finally:
        # تنظيف الملف المؤقت بشكل آمن (دائماً يتم تنفيذه)
        try:
            cleanup_temp_watermark_file(video_path_to_upload, original_video_path, log_fn)
        except Exception as cleanup_error:
            # تجاهل أي خطأ في التنظيف لمنع crash
            try:
                log_fn(f'⚠️ خطأ في تنظيف الملف المؤقت: {cleanup_error}')
            except Exception:
                pass
