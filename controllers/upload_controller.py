"""
Upload Controller - متحكم عمليات الرفع الفوري
Controller for immediate upload operations

This controller handles immediate upload operations for videos, stories, and reels.
"""

import threading
import gc
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

from core.jobs import PageJob
from controllers.story_controller import (
    StoryJob, get_story_files, safe_process_story_job, log_error_to_file
)
from controllers.reels_controller import (
    ReelsJob, get_reels_files, check_reels_duration,
    upload_reels_with_retry, is_reels_upload_successful
)
from controllers.video_controller import is_upload_successful
from core.constants import VIDEO_EXTENSIONS, MAX_VIDEO_DURATION_SECONDS
from core.utils import apply_title_placeholders
from services import upload_video_once, move_video_to_uploaded_folder


class UploadController:
    """
    متحكم عمليات الرفع الفوري
    Controller for immediate upload operations
    """
    
    def __init__(self, main_window):
        """
        تهيئة متحكم الرفع الفوري
        Initialize upload controller
        
        Args:
            main_window: النافذة الرئيسية - Main window instance
        """
        self.main_window = main_window
    
    def run_selected_job_now(self):
        """تشغيل فوري للوظيفة المحددة - يدعم الفيديو والستوري والريلز (Requirement 6)."""
        job = self.main_window._get_selected_job_from_table()
        if not job:
            QMessageBox.warning(self.main_window, 'اختيار مطلوب', 'اختر وظيفة أولاً')
            return

        # التفريق بين نوع الوظيفة
        if isinstance(job, StoryJob):
            self.run_story_job_now(job)
        elif isinstance(job, ReelsJob):
            self.run_reels_job_now(job)
        else:
            self.run_video_job_now(job)

    def run_story_job_now(self, job: StoryJob):
        """رفع ستوري فوري للوظيفة المحددة باستخدام نظام Batch Requests."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self.main_window, 'مجلد غير موجود', 'المجلد غير موجود')
                return

            # استخدام STORY_EXTENSIONS بدلاً من VIDEO_EXTENSIONS
            files = get_story_files(str(folder), job.sort_by)
            if not files:
                QMessageBox.warning(self.main_window, 'لا يوجد ملفات', 'لا توجد ملفات ستوري (صور/فيديو) في المجلد')
                return

            token = job.page_access_token or self.main_window.token_getter()
            if not token:
                QMessageBox.warning(self.main_window, 'توكن مفقود', 'لا يوجد توكن')
                return

            self.main_window._log_append(f'📱 رفع ستوري فوري: {job.page_name}')

            should_move = self.main_window.auto_move_uploaded

            # تفعيل زر الإيقاف
            self.main_window._on_upload_started()

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.main_window.ui_signals.log_signal.emit(msg)

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        self.main_window.ui_signals.clear_progress_signal.emit()

                        # استخدام safe_process_story_job مع دعم Batch Requests
                        result = safe_process_story_job(
                            job=job,
                            token=token,
                            log_fn=thread_safe_log,
                            auto_move=should_move,
                            stop_event=self.main_window._upload_stop_requested
                        )

                        # عرض ملخص النتائج
                        if result.get('success'):
                            thread_safe_log(f'✅ تم رفع {result.get("files_uploaded", 0)} ستوري بنجاح')
                            if result.get('saved_calls', 0) > 0:
                                thread_safe_log(f'📦 تم توفير {result.get("saved_calls", 0)} طلب API باستخدام Batch')
                        else:
                            thread_safe_log(f'⚠️ فشل: {result.get("error", "خطأ غير معروف")}')

                        if result.get('files_failed', 0) > 0:
                            thread_safe_log(f'❌ فشل رفع {result.get("files_failed", 0)} ملف')

                        job.reset_next_run_timestamp()
                        self.main_window._save_jobs()

                        # تنظيف الذاكرة
                        gc.collect()

                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Story job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected story error')
                finally:
                    # إخفاء زر الإيقاف
                    self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.main_window._log_append(f'❌ خطأ: {e}')
            self.main_window._on_upload_finished()
            log_error_to_file(e, 'run_story_job_now error')

    def run_video_job_now(self, job: PageJob):
        """رفع فيديو فوري للوظيفة المحددة (Requirement 6 - مع دعم الإيقاف)."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self.main_window, 'مجلد غير موجود', 'المجلد غير موجود')
                return
            files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])
            if not files:
                QMessageBox.warning(self.main_window, 'لا يوجد ملفات', 'لا فيديوهات في المجلد')
                return
            idx = job.next_index % len(files)
            video_path = str(files[idx])
            token = job.page_access_token or self.main_window.token_getter()
            if not token:
                QMessageBox.warning(self.main_window, 'توكن مفقود', 'لا يوجد توكن')
                return
            self.main_window._log_append(f'رفع فوري للوظيفة: {job.page_name}')

            # حفظ حالة نقل الفيديوهات محلياً للاستخدام داخل الـ worker
            should_move = self.main_window.auto_move_uploaded

            # تفعيل زر الإيقاف (Requirement 6)
            self.main_window._on_upload_started()

            # تتبع الوظيفة الحالية للإيقاف السريع
            self.main_window._current_uploading_job = job

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.main_window.ui_signals.log_signal.emit(msg)

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        # التحقق من طلب الإيقاف قبل البدء (Requirement 6)
                        if self.main_window._upload_stop_requested.is_set():
                            thread_safe_log('⏹️ تم إلغاء الرفع قبل البدء')
                            return

                        self.main_window.ui_signals.clear_progress_signal.emit()
                        status, body = upload_video_once(job, video_path, token, self.main_window.ui_signals,
                                                         job.title_template, job.description_template, thread_safe_log)

                        # التحقق من نجاح الرفع ونقل الفيديو إلى مجلد Uploaded
                        upload_success = is_upload_successful(status, body)
                        if upload_success:
                            thread_safe_log('اكتمل الرفع، إعادة ضبط العدّاد')
                            # بعد النجاح نضبط next_run_timestamp = الآن + الفاصل الزمني
                            job.reset_next_run_timestamp()
                            if should_move:
                                move_video_to_uploaded_folder(video_path, thread_safe_log)

                        if status in (400, 403) and isinstance(body, dict):
                            err = body.get('error', {})
                            msg = err.get('message', '')
                            code = err.get('code', '')
                            if msg and ('permission' in msg.lower() or code == 100):
                                thread_safe_log('تحذير: صلاحيات غير كافية.')
                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Video job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected video error')
                finally:
                    # إخفاء زر الإيقاف (Requirement 6)
                    self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.main_window._log_append(f'❌ خطأ: {e}')
            self.main_window._on_upload_finished()
            log_error_to_file(e, 'run_video_job_now error')

    def run_reels_job_now(self, job: ReelsJob):
        """رفع ريلز فوري للوظيفة المحددة (Requirement 6 - مع دعم الإيقاف)."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self.main_window, 'مجلد غير موجود', 'المجلد غير موجود')
                return
            files = get_reels_files(str(folder), job.sort_by)
            if not files:
                QMessageBox.warning(self.main_window, 'لا يوجد ملفات', 'لا ريلز في المجلد')
                return
            idx = job.next_index % len(files)
            video_path = str(files[idx])

            # Problem 1: فحص مدة الفيديو قبل البدء بالرفع
            duration = check_reels_duration(video_path)
            if duration > MAX_VIDEO_DURATION_SECONDS:
                self.main_window._log_append(f'⚠️ تم رفض الفيديو: المدة {duration:.1f} ثانية تتجاوز الحد الأقصى (60 ثانية)')
                return

            token = job.page_access_token or self.main_window.token_getter()
            if not token:
                QMessageBox.warning(self.main_window, 'توكن مفقود', 'لا يوجد توكن')
                return
            self.main_window._log_append(f'🎬 رفع ريلز فوري: {job.page_name}')
            if duration > 0:
                self.main_window._log_append(f'📊 مدة الفيديو: {duration:.1f} ثانية')

            # حفظ حالة نقل الفيديوهات محلياً للاستخدام داخل الـ worker
            should_move = self.main_window.auto_move_uploaded

            # تفعيل زر الإيقاف (Requirement 6)
            self.main_window._on_upload_started()

            # إنشاء مرجع للـ stop event للاستخدام في العامل
            stop_event = self.main_window._upload_stop_requested

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.main_window.ui_signals.log_signal.emit(msg)

                # Problem 3: دالة تحديث شريط التقدم
                def progress_callback(percent):
                    # التحقق من طلب الإيقاف أثناء تحديث التقدم
                    if stop_event.is_set():
                        return
                    self.main_window.ui_signals.progress_signal.emit(int(percent), f'رفع الريلز {int(percent)}%')

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        # التحقق من طلب الإيقاف قبل البدء (Requirement 6)
                        if stop_event.is_set():
                            thread_safe_log('⏹️ تم إلغاء الرفع قبل البدء')
                            return

                        self.main_window.ui_signals.clear_progress_signal.emit()

                        # استخدام دالة رفع الريلز
                        # إعداد العنوان والوصف باستخدام المتغيرات الجديدة
                        title = apply_title_placeholders(job.title_template, Path(video_path).name) if job.title_template else ''
                        description = apply_title_placeholders(job.description_template, Path(video_path).name) if job.description_template else ''

                        # Problem 2 & 3: تمرير progress_callback و stop_event
                        status, body = upload_reels_with_retry(
                            page_id=job.page_id,
                            video_path=video_path,
                            token=token,
                            description=description,
                            title=title,
                            log_fn=thread_safe_log,
                            progress_callback=progress_callback,
                            stop_event=stop_event
                        )

                        # التحقق من إيقاف العملية
                        if stop_event.is_set():
                            thread_safe_log('⏹️ تم إيقاف الرفع بنجاح')
                            return

                        # التحقق من نجاح الرفع
                        upload_success = is_reels_upload_successful(status, body)
                        if upload_success:
                            thread_safe_log('✅ اكتمل رفع الريلز')
                            job.next_index = (job.next_index + 1) % len(files)
                            job.reset_next_run_timestamp()
                            if should_move:
                                move_video_to_uploaded_folder(video_path, thread_safe_log)
                        else:
                            thread_safe_log(f'❌ فشل رفع الريلز')

                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Reels job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected reels error')
                finally:
                    # إخفاء زر الإيقاف (Requirement 6)
                    self.main_window.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.main_window._log_append(f'❌ خطأ: {e}')
            self.main_window._on_upload_finished()
            log_error_to_file(e, 'run_reels_job_now error')
