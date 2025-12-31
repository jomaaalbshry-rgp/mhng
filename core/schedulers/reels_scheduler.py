"""
Reels Scheduler Thread
مجدول رفع الريلز

Extracted from ui/main_window.py as part of Phase 2 refactoring.
"""

import threading
import time
import random
import concurrent.futures
from pathlib import Path

from core import NotificationSystem
from core.constants import INTERNET_CHECK_INTERVAL, INTERNET_CHECK_MAX_ATTEMPTS
from ui.signals import UiSignals
from controllers.reels_controller import ReelsJob, log_error_to_file


class ReelsSchedulerThread(threading.Thread):
    """
    خيط مجدول لنشر الريلز.
    يعالج وظائف الريلز ويرفعها إلى فيسبوك.
    Reels scheduler thread - handles reels jobs and uploads them to Facebook.
    """

    def __init__(self, reels_jobs_map, token_getter, ui_signals: UiSignals, stop_event,
                 max_workers=3, auto_move_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.reels_jobs_map = reels_jobs_map
        self.token_getter = token_getter
        self.ui = ui_signals
        self.stop_event = stop_event
        self.max_workers = max_workers
        # دالة للحصول على حالة نقل الملفات تلقائياً
        self.auto_move_getter = auto_move_getter or (lambda: False)
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
        self.log('تم تشغيل مجدول الريلز')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.reels_jobs_map.values()):
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
        self.log('توقف مجدول الريلز.')

    def _upload_wrapper(self, job: ReelsJob):
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع ريلز سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_reels_job(job)
        finally:
            job.lock.release()

    def _process_reels_job(self, job: ReelsJob):
        """معالجة وظيفة ريلز واحدة مع حماية شاملة من الأخطاء."""
        # Import from reels_controller
        from controllers.reels_controller import (
            get_reels_files, upload_reels_with_retry, is_reels_upload_successful,
            log_error_to_file, check_reels_duration
        )
        from ui.main_window import (
            check_internet_connection, is_rate_limit_error,
            move_video_to_uploaded_folder
        )
        from services import log_upload
        from core.utils import apply_title_placeholders

        try:
            # فحص الاتصال بالإنترنت قبل الرفع
            if self.internet_check_getter():
                if not check_internet_connection():
                    NotificationSystem.notify(self.log, NotificationSystem.NETWORK,
                        'فشل الاتصال بالإنترنت - الدخول في وضع الغفوة', job.page_name)
                    # الانتظار حتى يعود الاتصال
                    attempts = 0
                    while not check_internet_connection() and attempts < INTERNET_CHECK_MAX_ATTEMPTS:
                        if self.stop_event.is_set():
                            self.log('تم إيقاف مجدول الريلز أثناء انتظار الاتصال')
                            return
                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الريلز أثناء انتظار الاتصال: {job.page_name}')
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
            try:
                files = get_reels_files(str(folder), job.sort_by)
            except Exception as e:
                self.log(f'❌ فشل قراءة ملفات الريلز: {e}')
                log_error_to_file(e, f'get_reels_files error for {folder}')
                return

            if not files:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    f'لا توجد ملفات ريلز في المجلد ({job.folder})', job.page_name)
                return

            # الحصول على الفيديو التالي
            idx = job.next_index % len(files)
            video_path = str(files[idx])

            # فحص مدة الفيديو قبل البدء بالرفع
            is_valid_duration, duration, error_msg = check_reels_duration(video_path)
            if not is_valid_duration:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'⚠️ تم رفض الفيديو: {error_msg}', job.page_name)
                # تخطي هذا الفيديو والانتقال للتالي
                job.next_index = (job.next_index + 1) % len(files)
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
                return

            NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
                f'بدء رفع ريلز: {Path(video_path).name}', job.page_name)
            if duration > 0:
                self.log(f'📊 مدة الفيديو: {duration:.1f} ثانية')

            # إعداد العنوان والوصف
            title = apply_title_placeholders(job.title_template, Path(video_path).name) if job.title_template else ''
            description = apply_title_placeholders(job.description_template, Path(video_path).name) if job.description_template else ''

            # رفع الريلز
            status, body = upload_reels_with_retry(
                page_id=job.page_id,
                video_path=video_path,
                token=token,
                description=description,
                title=title,
                log_fn=self.log,
                progress_callback=lambda p: self.ui.progress_signal.emit(int(p), f'رفع الريلز {int(p)}%'),
                stop_event=self.stop_event
            )

            # التحقق من النجاح
            upload_success = is_reels_upload_successful(status, body)

            # التحقق من Rate Limit
            if is_rate_limit_error(body):
                self._handle_rate_limit(job)
                return

            # تسجيل الرفع في قاعدة البيانات
            video_id = body.get('video_id') or body.get('id') if isinstance(body, dict) else None
            log_upload(
                job.page_id, job.page_name, video_path, Path(video_path).name,
                'reels', video_id=video_id, video_url=None,
                status='success' if upload_success else 'failed',
                error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
            )

            if upload_success:
                NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                    f'✅ تم رفع الريلز بنجاح: {Path(video_path).name}', job.page_name)
                # تحديث next_index للفيديو التالي
                job.next_index = (job.next_index + 1) % len(files)
                # نقل الملف إذا مفعّل
                if self.auto_move_getter():
                    try:
                        move_video_to_uploaded_folder(video_path, self.log)
                    except Exception as move_err:
                        self.log(f'⚠️ فشل نقل الملف: {move_err}')
            else:
                error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'❌ فشل رفع الريلز: {error_msg[:50]}', job.page_name)

        except Exception as e:
            self.log(f'❌ خطأ غير متوقع في معالجة وظيفة الريلز: {e}')
            log_error_to_file(e, f'Process reels job error: {job.page_name}')
