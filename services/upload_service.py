"""
خدمة الرفع - Upload Service
تحتوي على منطق رفع الملفات والمحتوى
Contains logic for uploading files and content
"""

import os
import time
import random
import subprocess
import requests
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Callable

from core.logger import log_info, log_error, log_warning, log_debug


class UploadService:
    """
    خدمة رفع الملفات إلى فيسبوك
    Service for uploading files to Facebook
    
    هذه الخدمة مسؤولة عن:
    - رفع الفيديوهات (بسيط ومجزأ)
    - تطبيق العلامات المائية
    - معالجة الملفات قبل الرفع
    """
    
    def __init__(self, api_version: str = 'v17.0'):
        """
        تهيئة خدمة الرفع
        Initialize upload service
        
        Args:
            api_version: إصدار Facebook Graph API (default: v17.0)
        """
        self.api_version = api_version
    
    def is_upload_successful(self, status: int, body: Any) -> bool:
        """
        التحقق من نجاح عملية رفع الفيديو إلى فيسبوك
        Check if video upload to Facebook was successful
        
        يُعتبر الرفع ناجحاً إذا:
        - كان status code بين 200-299
        - واستجابة الـ body تحتوي على id للفيديو (ولا تحتوي على خطأ)
        
        Args:
            status: كود حالة HTTP للاستجابة - HTTP status code
            body: جسم الاستجابة (dict أو str) - Response body (dict or str)
        
        Returns:
            True إذا نجح الرفع، False خلاف ذلك
            True if upload successful, False otherwise
        """
        if status is None:
            return False
        if not (200 <= status < 300):
            return False
        if isinstance(body, dict):
            # إذا كان هناك خطأ في الاستجابة
            if 'error' in body:
                return False
            # إذا كان هناك id للفيديو يُعتبر الرفع ناجحاً
            if 'id' in body:
                return True
            # افتراض النجاح إذا لم يكن هناك خطأ ولا id (حالة نادرة)
            return True
        # إذا كانت الاستجابة نصية (ليست dict)، نفترض الفشل لأن الاستجابة غير متوقعة
        if isinstance(body, str):
            return False
        # افتراض النجاح للحالات الأخرى غير المتوقعة
        return True
    
    def is_rate_limit_error(self, body: Any) -> bool:
        """
        التحقق مما إذا كان الخطأ هو Rate Limit من فيسبوك
        Check if error is a Rate Limit error from Facebook
        
        كود الخطأ 4 = Application request limit reached
        
        Args:
            body: جسم الاستجابة (dict) - Response body (dict)
        
        Returns:
            True إذا كان خطأ Rate Limit، False خلاف ذلك
            True if Rate Limit error, False otherwise
        """
        if not isinstance(body, dict):
            return False
        error = body.get('error', {})
        error_code = error.get('code')
        error_message = error.get('message', '').lower()
        
        # كود 4 = Rate Limit
        if error_code == 4:
            return True
        
        # أو رسالة تحتوي على "request limit"
        if 'request limit' in error_message or 'rate limit' in error_message:
            return True
        
        return False
    
    def resumable_upload(self, page_id: str, video_path: str, token: str, 
                        ui_signals, final_title: str = "", final_description: str = "",
                        chunk_size: int = 10 * 1024 * 1024,
                        upload_timeout_start: int = 60,
                        upload_timeout_transfer: int = 120,
                        upload_timeout_finish: int = 60,
                        page_job=None) -> Tuple[Optional[int], Dict]:
        """
        رفع فيديو بشكل مجزأ إلى فيسبوك
        Upload video to Facebook in chunks (resumable upload)
        
        Args:
            page_id: معرف الصفحة - Page ID
            video_path: مسار الفيديو - Video path
            token: توكن الوصول - Access token
            ui_signals: إشارات الواجهة - UI signals object
            final_title: عنوان الفيديو - Video title
            final_description: وصف الفيديو - Video description
            chunk_size: حجم الجزء بالبايت (default: 10MB) - Chunk size in bytes
            upload_timeout_start: مهلة بدء الرفع بالثواني - Start timeout in seconds
            upload_timeout_transfer: مهلة نقل البيانات بالثواني - Transfer timeout in seconds
            upload_timeout_finish: مهلة إنهاء الرفع بالثواني - Finish timeout in seconds
            page_job: وظيفة الصفحة للتحقق من الإلغاء - Page job for cancellation check
        
        Returns:
            tuple: (status_code, response_body)
        """
        file_size = os.path.getsize(video_path)
        endpoint = f'https://graph-video.facebook.com/{self.api_version}/{page_id}/videos'
        start_time = time.time()
        bytes_sent = 0
        
        def log(msg): 
            ui_signals.log_signal.emit(msg)
        
        log(f'بدء رفع مجزأ: الحجم={file_size} جزء={chunk_size}')
        
        # استخدام جلسة واحدة مع keep-alive لجميع الطلبات
        with requests.Session() as session:
            try:
                r = session.post(endpoint, data={
                    'upload_phase': 'start',
                    'file_size': str(file_size),
                    'access_token': token
                }, timeout=upload_timeout_start)
                r.raise_for_status()
                resp = r.json()
            except Exception as e:
                log(f'فشل البدء: {e}')
                return None, {'error': 'start_failed', 'detail': str(e)}
            
            session_id = resp.get('upload_session_id')
            start_offset = int(resp.get('start_offset', 0))
            end_offset = int(resp.get('end_offset', 0))
            if not session_id:
                log(f'لا جلسة: {resp}')
                return None, {'error': 'no_session', 'detail': resp}
            
            # التحقق من طلب الإيقاف قبل البدء بالنقل
            if page_job and hasattr(page_job, 'check_and_reset_cancel') and page_job.check_and_reset_cancel():
                log('تم طلب إيقاف الوظيفة أثناء الرفع المجزّأ، إنهاء مبكر.')
                return None, {'error': 'cancelled', 'detail': 'تم إلغاء الرفع بناءً على طلب المستخدم'}
            
            try:
                with open(video_path, 'rb') as f:
                    while start_offset != end_offset:
                        # التحقق من طلب الإيقاف بعد كل جزء بشكل ذري
                        if page_job and hasattr(page_job, 'check_and_reset_cancel') and page_job.check_and_reset_cancel():
                            log('تم طلب إيقاف الوظيفة أثناء الرفع المجزّأ، إنهاء مبكر.')
                            return None, {'error': 'cancelled', 'detail': 'تم إلغاء الرفع بناءً على طلب المستخدم'}
                        
                        f.seek(start_offset)
                        chunk_len = min(chunk_size, end_offset - start_offset) if end_offset > start_offset else chunk_size
                        data_chunk = f.read(chunk_len)
                        if not data_chunk:
                            log('انتهى الملف مبكراً.')
                            break
                        files = {'video_file_chunk': ('chunk', data_chunk)}
                        data = {
                            'upload_phase': 'transfer',
                            'start_offset': str(start_offset),
                            'upload_session_id': session_id,
                            'access_token': token
                        }
                        try:
                            r2 = session.post(endpoint, data=data, files=files, timeout=upload_timeout_transfer)
                            r2.raise_for_status()
                            resp2 = r2.json()
                        except Exception as e:
                            log(f'خطأ جزء: {e}')
                            return None, {'error': 'transfer_failed', 'detail': str(e)}
                        start_offset = int(resp2.get('start_offset', start_offset))
                        end_offset = int(resp2.get('end_offset', end_offset))
                        bytes_sent = start_offset
                        percent = int(bytes_sent / file_size * 100) if file_size else 0
                        elapsed = time.time() - start_time
                        speed = (bytes_sent / 1024 / 1024) / elapsed if elapsed > 0 else 0
                        remaining = max(0, file_size - bytes_sent)
                        eta = int(remaining / (bytes_sent / elapsed)) if bytes_sent > 0 and elapsed > 0 else 0
                        ui_signals.progress_signal.emit(percent, f'رفع مجزأ {percent}% | سرعة {speed:.2f} MB/s | متبقٍ ~{eta} ث')
            except Exception as e:
                log(f'خطأ قراءة/نقل: {e}')
                return None, {'error': 'file_read_or_transfer', 'detail': str(e)}
            
            try:
                finish_data = {
                    'upload_phase': 'finish',
                    'upload_session_id': session_id,
                    'access_token': token,
                    'title': final_title or '',
                    'description': final_description or '',
                    'published': 'true'
                }
                r3 = session.post(endpoint, data=finish_data, timeout=upload_timeout_finish)
                resp3 = r3.json()
            except Exception as e:
                log(f'فشل الإنهاء: {e}')
                return None, {'error': 'finish_failed', 'detail': str(e)}
            
            ui_signals.progress_signal.emit(100, 'تم الرفع المجزأ 100%')
            log(f'انتهى الرفع المجزأ: {resp3}')
            return r3.status_code if hasattr(r3, 'status_code') else 200, resp3
    
    def apply_watermark_to_video(self, video_path: str, watermark_path: str, 
                                 position: str = 'bottom_right', opacity: float = 0.8, 
                                 scale: float = 0.15, watermark_x: Optional[int] = None,
                                 watermark_y: Optional[int] = None, log_fn: Optional[Callable] = None,
                                 run_subprocess_fn: Optional[Callable] = None,
                                 notification_system=None, page_name: str = '',
                                 watermark_ffmpeg_timeout: int = 600,
                                 watermark_min_output_ratio: float = 0.5,
                                 watermark_file_close_delay: float = 0.5) -> str:
        """
        تطبيق العلامة المائية على الفيديو بشكل آمن
        Apply watermark to video safely
        
        Args:
            video_path: مسار الفيديو الأصلي - Original video path
            watermark_path: مسار العلامة المائية - Watermark path
            position: موقع العلامة المائية - Watermark position
            opacity: شفافية العلامة المائية (0.0 - 1.0) - Opacity (0.0 - 1.0)
            scale: حجم العلامة المائية (0.01 - 1.0) - Scale (0.01 - 1.0)
            watermark_x: الإحداثي X المخصص - Custom X coordinate
            watermark_y: الإحداثي Y المخصص - Custom Y coordinate
            log_fn: دالة التسجيل - Logging function
            run_subprocess_fn: دالة تشغيل subprocess - Subprocess execution function
            notification_system: نظام الإشعارات - Notification system
            page_name: اسم الصفحة - Page name
            watermark_ffmpeg_timeout: مهلة FFmpeg بالثواني - FFmpeg timeout in seconds
            watermark_min_output_ratio: الحد الأدنى لنسبة حجم الملف - Min output size ratio
            watermark_file_close_delay: تأخير إغلاق الملف بالثواني - File close delay in seconds
        
        Returns:
            مسار الفيديو النهائي (الأصلي أو المعدّل)
            Final video path (original or modified)
        """
        output_path = None
        
        try:
            # التحقق من وجود الملفات
            if not os.path.exists(video_path) or not os.path.exists(watermark_path):
                return video_path
            
            # التحقق من صلاحية المسارات (حماية أمنية)
            video_path = os.path.abspath(video_path)
            watermark_path = os.path.abspath(watermark_path)
            
            if not os.path.isfile(video_path) or not os.path.isfile(watermark_path):
                return video_path
            
            # التحقق من صحة الفيديو الأصلي قبل المعالجة
            original_size = os.path.getsize(video_path)
            if original_size == 0:
                if notification_system and log_fn:
                    notification_system.notify(log_fn, notification_system.WARNING, 
                                              'ملف الفيديو الأصلي فارغ، سيتم الرفع بدون علامة مائية', page_name)
                return video_path
            
            # إعلام المستخدم
            if notification_system and log_fn:
                notification_system.notify(log_fn, notification_system.WATERMARK, 
                                          'جاري إضافة العلامة المائية...', page_name)
            
            # إنشاء مجلد مؤقت للفيديو المعدّل
            video_dir = os.path.dirname(video_path)
            temp_dir = os.path.join(video_dir, '.temp_watermark')
            os.makedirs(temp_dir, exist_ok=True)
            
            # تحديد مسار الملف الناتج مع معرّف فريد لتجنب التصادم
            unique_id = f'{int(time.time() * 1000)}_{random.randint(1000, 9999)}'
            output_filename = f'wm_{unique_id}_{os.path.basename(video_path)}'
            output_path = os.path.join(temp_dir, output_filename)
            
            # التحقق من صلاحية القيم العددية
            opacity = max(0.0, min(1.0, float(opacity)))
            scale = max(0.01, min(1.0, float(scale)))
            
            # تحديد موقع العلامة المائية
            if (watermark_x is not None and watermark_y is not None and
                isinstance(watermark_x, (int, float)) and isinstance(watermark_y, (int, float))):
                overlay_pos = f'x={int(watermark_x)}:y={int(watermark_y)}'
            else:
                position_map = {
                    'top_left': 'x=10:y=10',
                    'top_right': 'x=W-w-10:y=10',
                    'bottom_left': 'x=10:y=H-h-10',
                    'bottom_right': 'x=W-w-10:y=H-h-10',
                    'center': 'x=(W-w)/2:y=(H-h)/2'
                }
                overlay_pos = position_map.get(position, position_map['bottom_right'])
            
            # بناء أمر FFmpeg
            filter_complex = (
                f'[1:v]scale=iw*{scale}:-1,format=rgba,'
                f'colorchannelmixer=aa={opacity}[wm];'
                f'[0:v][wm]overlay={overlay_pos}'
            )
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-i', watermark_path,
                '-filter_complex', filter_complex,
                '-c:a', 'copy',
                '-y', output_path
            ]
            
            # تنفيذ الأمر
            if run_subprocess_fn:
                result = run_subprocess_fn(cmd, timeout=watermark_ffmpeg_timeout)
            else:
                result = subprocess.run(cmd, timeout=watermark_ffmpeg_timeout, 
                                       capture_output=True)
            
            # التحقق من نجاح العملية
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')[:200] if result.stderr else 'خطأ غير معروف'
                if notification_system and log_fn:
                    notification_system.notify(log_fn, notification_system.WARNING, 
                                              f'فشل إضافة العلامة المائية: {error_msg}', page_name)
                if output_path and os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception:
                        pass
                return video_path
            
            # التحقق من وجود الملف الناتج
            if not os.path.exists(output_path):
                if notification_system and log_fn:
                    notification_system.notify(log_fn, notification_system.WARNING, 
                                              'الملف المؤقت غير موجود، سيتم الرفع بدون علامة مائية', page_name)
                return video_path
            
            # التحقق من أن الملف ليس فارغاً
            output_size = os.path.getsize(output_path)
            if output_size == 0:
                if notification_system and log_fn:
                    notification_system.notify(log_fn, notification_system.WARNING, 
                                              'الملف المؤقت فارغ، سيتم الرفع بدون علامة مائية', page_name)
                try:
                    os.remove(output_path)
                except Exception:
                    pass
                return video_path
            
            # التحقق من أن حجم الملف منطقي
            if output_size < original_size * watermark_min_output_ratio:
                if notification_system and log_fn:
                    notification_system.notify(log_fn, notification_system.WARNING, 
                                              'الملف المؤقت صغير جداً، قد يكون تالفاً. سيتم الرفع بدون علامة مائية', page_name)
                try:
                    os.remove(output_path)
                except Exception:
                    pass
                return video_path
            
            # انتظار قليلاً للتأكد من إغلاق الملف
            time.sleep(watermark_file_close_delay)
            
            if notification_system and log_fn:
                notification_system.notify(log_fn, notification_system.SUCCESS, 
                                          'تم إضافة العلامة المائية بنجاح', page_name)
            return output_path
                
        except FileNotFoundError:
            if notification_system and log_fn:
                notification_system.notify(log_fn, notification_system.WARNING, 
                                          'FFmpeg غير مثبت - سيتم الرفع بدون علامة مائية', page_name)
            return video_path
        except subprocess.TimeoutExpired:
            timeout_minutes = watermark_ffmpeg_timeout // 60
            if notification_system and log_fn:
                notification_system.notify(log_fn, notification_system.WARNING, 
                                          f'انتهت مهلة إضافة العلامة المائية ({timeout_minutes} دقائق)، سيتم الرفع بدونها', page_name)
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            return video_path
        except Exception as e:
            if notification_system and log_fn:
                notification_system.notify(log_fn, notification_system.WARNING, 
                                          f'خطأ في العلامة المائية: {e}', page_name)
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            return video_path
    
    def cleanup_temp_watermark_file(self, video_path: str, original_path: str, 
                                    log_fn: Optional[Callable] = None,
                                    watermark_cleanup_delay: float = 0.5):
        """
        حذف ملف الفيديو المؤقت بعد الرفع إذا كان مختلفاً عن الأصلي بشكل آمن
        Delete temporary video file after upload if different from original
        
        Args:
            video_path: مسار الفيديو المستخدم (قد يكون مؤقتاً) - Video path used (may be temporary)
            original_path: مسار الفيديو الأصلي - Original video path
            log_fn: دالة التسجيل - Logging function
            watermark_cleanup_delay: تأخير التنظيف بالثواني - Cleanup delay in seconds
        """
        if video_path == original_path:
            return
        
        if not video_path or not os.path.exists(video_path):
            return
        
        try:
            # انتظار قليلاً للتأكد من إغلاق الملف بشكل كامل
            time.sleep(watermark_cleanup_delay)
            
            # محاولة حذف الملف المؤقت
            try:
                os.remove(video_path)
            except PermissionError:
                # الملف لا يزال مستخدماً، انتظر ثم حاول مرة أخرى
                time.sleep(watermark_cleanup_delay * 2)
                try:
                    os.remove(video_path)
                except Exception:
                    if log_fn:
                        log_fn(f'⚠️ تعذر حذف الملف المؤقت (الملف مستخدم): {os.path.basename(video_path)}')
                    return
            
            # حاول حذف المجلد المؤقت إذا كان فارغاً
            temp_dir = os.path.dirname(video_path)
            if os.path.isdir(temp_dir) and os.path.basename(temp_dir) == '.temp_watermark':
                try:
                    if not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                except OSError:
                    pass
        except Exception as e:
            if log_fn:
                log_fn(f'⚠️ تعذر حذف الملف المؤقت: {e}')
