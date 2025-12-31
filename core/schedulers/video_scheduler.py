"""
Video Scheduler Thread
مجدول رفع الفيديوهات

Extracted from ui/main_window.py as part of Phase 2 refactoring.
"""

import threading
import time
import random
import os
import concurrent.futures
from pathlib import Path

from core import NotificationSystem
from core.constants import (
    VIDEO_EXTENSIONS, INTERNET_CHECK_INTERVAL, 
    INTERNET_CHECK_MAX_ATTEMPTS, UPLOADED_FOLDER_NAME
)
from ui.signals import UiSignals
from controllers.story_controller import log_error_to_file


class SchedulerThread(threading.Thread):
    def __init__(self, jobs_map, token_getter, ui_signals: UiSignals, stop_event, max_workers=3,
                 auto_move_getter=None, validate_videos_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.jobs_map = jobs_map
        self.token_getter = token_getter
        self.ui = ui_signals
        self.stop_event = stop_event
        self.max_workers = max_workers
        # دالة للحصول على حالة نقل الفيديوهات تلقائياً
        self.auto_move_getter = auto_move_getter or (lambda: False)
        # دالة للحصول على حالة التحقق من الفيديو
        self.validate_videos_getter = validate_videos_getter or (lambda: False)
        # دالة للحصول على حالة فحص الإنترنت
        self.internet_check_getter = internet_check_getter or (lambda: True)

    def log(self, text):
        self.ui.log_signal.emit(text)

    def _handle_rate_limit(self, job) -> bool:
        """
        معالجة خطأ Rate Limit - تأجيل النشر والمحاولة مرة أخرى بدلاً من الإيقاف.

        العائد: True لتخطي هذه المحاولة (سيتم المحاولة لاحقاً)
        """
        # Import here to avoid circular import
        from ui.main_window import send_telegram_error
        
        # تأخير عشوائي بين 30-60 دقيقة
        delay_minutes = random.randint(30, 60)
        delay_seconds = delay_minutes * 60

        NotificationSystem.notify(self.log, NotificationSystem.WARNING,
            f'⏳ تم الوصول لحد الطلبات (Rate Limit) - سيتم المحاولة تلقائياً بعد {delay_minutes} دقيقة', job.page_name)

        # تأجيل وقت النشر القادم بدلاً من الإيقاف
        job.next_run_timestamp = time.time() + delay_seconds

        # إرسال إشعار Telegram إذا كان مفعلاً
        try:
            send_telegram_error('تم الوصول لحد الطلبات',
                f'سيتم تأجيل النشر لمدة {delay_minutes} دقيقة والمحاولة مرة أخرى تلقائياً', job.page_name)
        except Exception:
            pass

        return True

    def run(self):
        self.log('تم تشغيل المجدول')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.jobs_map.values()):
                    if self.stop_event.is_set():
                        break
                    # تخطّي الوظائف غير المجدولة أو المعطّلة
                    if not job.enabled or not job.is_scheduled:
                        continue

                    # التحقق من وصول الوقت باستخدام job.next_run_timestamp
                    if now >= job.next_run_timestamp:
                        executor.submit(self._upload_wrapper, job)
                        # ضبط الوقت التالي بعد الرفع
                        job.reset_next_run_timestamp()
                time.sleep(1)
        self.log('توقف المجدول.')

    def _upload_wrapper(self, job):
        """غلاف آمن لعملية الرفع مع معالجة شاملة للأخطاء."""
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_job(job)
        except Exception as e:
            # التقاط أي استثناء غير متوقع لمنع crash البرنامج
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'خطأ غير متوقع في عملية الرفع: {str(e)[:100]}', job.page_name)
            try:
                # تسجيل الخطأ في ملف السجلات
                from controllers.story_controller import log_error_to_file
                log_error_to_file(e, f'Unexpected error in video upload for job: {job.page_name}')
            except Exception:
                pass  # تجاهل أخطاء التسجيل
        finally:
            try:
                job.lock.release()
            except Exception:
                pass  # تجاهل أي خطأ في تحرير القفل

    def _process_job(self, job):
        # Import functions from main_window here to avoid circular imports
        from ui.main_window import (
            check_internet_connection, sort_video_files, validate_video,
            upload_video_once, is_upload_successful, is_rate_limit_error,
            move_video_to_uploaded_folder
        )
        from services import log_upload
        
        # فحص الاتصال بالإنترنت قبل الرفع (Internet Safety Check)
        if self.internet_check_getter():
            if not check_internet_connection():
                NotificationSystem.notify(self.log, NotificationSystem.NETWORK,
                    'فشل الاتصال بالإنترنت - الدخول في وضع الغفوة', job.page_name)
                # الانتظار حتى يعود الاتصال
                attempts = 0
                while not check_internet_connection() and attempts < INTERNET_CHECK_MAX_ATTEMPTS:
                    if self.stop_event.is_set():
                        self.log('تم إيقاف المجدول أثناء انتظار الاتصال')
                        return
                    if job.check_and_reset_cancel():
                        self.log(f'تم إلغاء الوظيفة أثناء انتظار الاتصال: {job.page_name}')
                        return
                    attempts += 1
                    self.log(f'📶 المحاولة {attempts}/{INTERNET_CHECK_MAX_ATTEMPTS} - الانتظار {INTERNET_CHECK_INTERVAL} ثانية...')
                    time.sleep(INTERNET_CHECK_INTERVAL)

                if check_internet_connection():
                    NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                        'عاد الاتصال بالإنترنت - استئناف الرفع', job.page_name)
                else:
                    NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                        'انتهت المحاولات - تخطي الرفع', job.page_name)
                    return

        folder = Path(job.folder)
        if not folder.exists():
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'المجلد غير موجود: {folder}', job.page_name)
            return

        # الحصول على الملفات وترتيبها حسب الخيار المحدد
        raw_files = [p for p in folder.iterdir()
                     if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]

        # تطبيق ترتيب الملفات
        files = sort_video_files(raw_files, job.sort_by)

        if not files:
            NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                f'لا توجد فيديوهات في المجلد ({job.folder}) - تم إيقاف الرفع مؤقتاً', job.page_name)
            return
        idx = job.next_index % len(files)
        video_path = str(files[idx])

        # التحقق من صحة الفيديو قبل الرفع
        if self.validate_videos_getter():
            validation = validate_video(video_path, self.log)
            if not validation['valid']:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'تخطي الفيديو (غير صالح): {validation.get("error", "خطأ غير معروف")}', job.page_name)
                # تسجيل الفشل في قاعدة البيانات
                log_upload(job.page_id, job.page_name, video_path, os.path.basename(video_path),
                          'video', status='failed', error_message=validation.get('error'))
                job.next_index = (job.next_index + 1) % len(files)
                return

        job.next_index = (job.next_index + 1) % len(files)
        token = job.page_access_token or self.token_getter()
        if not token:
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
            return

        NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
            f'بدء رفع الفيديو: {os.path.basename(video_path)}', job.page_name)

        status, body = upload_video_once(job, video_path, token, self.ui,
                                         job.title_template, job.description_template, self.log)

        # التحقق من نجاح الرفع ونقل الفيديو إلى مجلد Uploaded
        upload_success = is_upload_successful(status, body)

        # التحقق من Rate Limit
        if is_rate_limit_error(body):
            self._handle_rate_limit(job)
            return  # الخروج فوراً بدون متابعة

        # تسجيل الرفع في قاعدة البيانات
        video_id = body.get('id') if isinstance(body, dict) else None
        video_url = f'https://www.facebook.com/{video_id}' if video_id else None
        log_upload(
            job.page_id, job.page_name, video_path, os.path.basename(video_path),
            'video', video_id=video_id, video_url=video_url,
            status='success' if upload_success else 'failed',
            error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
        )

        if upload_success:
            NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                f'تم رفع الفيديو بنجاح: {os.path.basename(video_path)}', job.page_name)
            if self.auto_move_getter():
                move_video_to_uploaded_folder(video_path, self.log)
        else:
            error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'فشل رفع الفيديو: {error_msg[:100]}', job.page_name)

        if status in (400, 403):
            if isinstance(body, dict):
                err = body.get('error', {})
                msg = err.get('message', '')
                code = err.get('code', '')
                if msg and ('permission' in msg.lower() or code == 100):
                    NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                        'صلاحيات غير كافية للنشر', job.page_name)
