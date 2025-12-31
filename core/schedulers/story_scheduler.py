"""
Story Scheduler Thread
مجدول رفع الستوري

Extracted from ui/main_window.py as part of Phase 2 refactoring.
"""

import threading
import time
import random
import gc
import concurrent.futures
from pathlib import Path

import requests

from core import NotificationSystem
from core.constants import INTERNET_CHECK_INTERVAL, INTERNET_CHECK_MAX_ATTEMPTS
from core.utils import API_CALLS_PER_STORY, get_api_tracker, get_api_warning_system
from ui.signals import UiSignals
from controllers.story_controller import StoryJob, log_error_to_file


class StorySchedulerThread(threading.Thread):
    """
    خيط مجدول لنشر الستوري.
    يعالج وظائف الستوري ويرفعها إلى فيسبوك.
    """

    def __init__(self, story_jobs_map, token_getter, ui_signals: UiSignals, stop_event,
                 max_workers=3, auto_move_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.story_jobs_map = story_jobs_map
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
        self.log('تم تشغيل مجدول الستوري')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.story_jobs_map.values()):
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
        self.log('توقف مجدول الستوري.')

    def _upload_wrapper(self, job: StoryJob):
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع ستوري سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_story_job(job)
        finally:
            job.lock.release()

    def _process_story_job(self, job: StoryJob):
        """معالجة وظيفة ستوري واحدة مع حماية شاملة من الأخطاء."""
        # Import from storyTasks
        from controllers.story_controller import (
            get_story_files, get_next_story_batch, upload_story,
            is_story_upload_successful, log_error_to_file
        )
        from ui.main_window import (
            check_internet_connection, is_rate_limit_error,
            move_video_to_uploaded_folder, mask_token
        )
        from services import log_upload

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
                            self.log('تم إيقاف مجدول الستوري أثناء انتظار الاتصال')
                            return
                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الستوري أثناء انتظار الاتصال: {job.page_name}')
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
                files = get_story_files(str(folder), job.sort_by)
            except Exception as e:
                self.log(f'❌ فشل قراءة ملفات الستوري: {e}')
                log_error_to_file(e, f'get_story_files error for {folder}')
                return

            if not files:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    f'انتهت جميع الفيديوهات في المجلد ({job.folder})', job.page_name)
                return

            # الحصول على الدفعة التالية
            try:
                batch = get_next_story_batch(job, files)
            except Exception as e:
                self.log(f'❌ فشل تحديد الدفعة: {e}')
                log_error_to_file(e, f'get_next_story_batch error for {job.page_name}')
                return

            if not batch:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    'لا توجد ملفات في الدفعة للنشر', job.page_name)
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
                return

            # التحقق من حدود API
            try:
                tracker = get_api_tracker(job.hourly_limit, job.daily_limit)
                warning_system = get_api_warning_system(self.log)

                can_continue, warning_msg = warning_system.check_and_warn()
                if not can_continue:
                    NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                        warning_msg, job.page_name)
                    return
            except Exception as e:
                # استمر حتى لو فشل نظام التتبع
                self.log(f'⚠️ تحذير: فشل نظام تتبع API: {str(e)}')
                log_error_to_file(e, 'API tracker failed in _process_story_job')

            NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
                f'بدء نشر {len(batch)} ستوري', job.page_name)

            successful_count = 0
            failed_count = 0

            # استخدام Session لتحسين الأداء مع معالجة استثناءات
            session = None
            try:
                session = requests.Session()
                for file_path in batch:
                    try:
                        if self.stop_event.is_set():
                            self.log('تم إيقاف مجدول الستوري أثناء النشر')
                            break

                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الستوري: {job.page_name}')
                            break

                        self.log(f'📱 رفع ستوري: {file_path.name} -> {job.page_name} ({mask_token(token)})')

                        status, body = upload_story(job.page_id, str(file_path), token, self.log, session)

                        # تسجيل طلب API
                        try:
                            tracker.record_call(API_CALLS_PER_STORY)
                        except Exception:
                            pass

                        # تسجيل النتيجة
                        upload_success = is_story_upload_successful(status, body)

                        # التحقق من Rate Limit
                        if is_rate_limit_error(body):
                            self._handle_rate_limit(job)
                            break  # الخروج من حلقة الستوري

                        # تسجيل الرفع في قاعدة البيانات
                        story_id = body.get('id') if isinstance(body, dict) else None
                        log_upload(
                            job.page_id, job.page_name, str(file_path), file_path.name,
                            'story', video_id=story_id, video_url=None,
                            status='success' if upload_success else 'failed',
                            error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
                        )

                        if upload_success:
                            successful_count += 1
                            NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                                f'تم رفع الستوري بنجاح: {file_path.name}', job.page_name)
                            # نقل الملف إذا مفعّل
                            if self.auto_move_getter():
                                try:
                                    move_video_to_uploaded_folder(str(file_path), self.log)
                                except Exception as move_err:
                                    self.log(f'⚠️ فشل نقل الملف: {move_err}')
                        else:
                            failed_count += 1
                            error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
                            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                                f'فشل رفع الستوري: {error_msg[:50]}', job.page_name)

                        # تأخير بين كل ستوري لتجنب rate limiting (حماية من الحظر) - Requirement 4
                        if job.anti_ban_enabled and len(batch) > 1:
                            # استخدام التأخير العشوائي فقط
                            delay = random.randint(job.random_delay_min, job.random_delay_max)
                            NotificationSystem.notify(self.log, NotificationSystem.INFO,
                                f'⏳ استراحة حماية لمدة {delay} ثانية', job.page_name)
                            time.sleep(delay)

                    except requests.exceptions.Timeout as e:
                        failed_count += 1
                        self.log(f'⏱️ انتهت مهلة رفع الستوري ({file_path.name})')
                        log_error_to_file(e, f'Story upload timeout: {file_path}')

                    except requests.exceptions.ConnectionError as e:
                        failed_count += 1
                        self.log(f'🔌 فشل الاتصال أثناء رفع الستوري ({file_path.name})')
                        log_error_to_file(e, f'Story upload connection error: {file_path}')

                    except Exception as e:
                        failed_count += 1
                        self.log(f'❌ خطأ في رفع الستوري ({file_path.name}): {e}')
                        log_error_to_file(e, f'Story upload error: {file_path}')

            finally:
                # إغلاق Session بشكل آمن
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass
                # تنظيف الذاكرة بعد انتهاء الدفعة بالكامل
                gc.collect()

            # تحديث next_index
            job.next_index = (job.next_index + len(batch)) % len(files)

            self.log(f'📱 انتهى نشر الستوري: {successful_count} نجح، {failed_count} فشل')

        except Exception as e:
            self.log(f'❌ خطأ غير متوقع في معالجة وظيفة الستوري: {e}')
            log_error_to_file(e, f'Process story job error: {job.page_name}')
