# المتحكمات - Controllers

هذا المجلد يحتوي على طبقة التحكم في منطق الأعمال (Business Logic Controllers).

## المتحكمات المتاحة

### 1. VideoController
متحكم رفع ونشر الفيديوهات
- **Signals**: `upload_started`, `upload_progress`, `upload_completed`, `upload_failed`, `log_message`
- **Methods**: `start_upload()`, `cancel_upload()`, `validate_video()`

**مثال الاستخدام:**
```python
from controllers import VideoController
from services import UploadService

upload_service = UploadService(api_version='v17.0')
video_controller = VideoController(upload_service)

# ربط الـ signals
video_controller.upload_completed.connect(on_upload_complete)
video_controller.upload_failed.connect(on_upload_failed)

# بدء الرفع
video_controller.start_upload(page_job, video_path, token, ui_signals)
```

### 2. StoryController
متحكم نشر الستوري
- **Signals**: `publish_started`, `publish_progress`, `publish_completed`, `publish_failed`, `log_message`
- **Methods**: `start_publish()`, `cancel_publish()`, `validate_story()`

**مثال الاستخدام:**
```python
from controllers import StoryController
from services import FacebookAPIService

api_service = FacebookAPIService()
story_controller = StoryController(api_service)

# ربط الـ signals
story_controller.publish_completed.connect(on_publish_complete)

# بدء النشر
story_controller.start_publish(page_job, story_files, token)
```

### 3. ReelsController
متحكم نشر الريلز
- **Signals**: `publish_started`, `publish_progress`, `publish_completed`, `publish_failed`, `log_message`
- **Methods**: `start_publish()`, `cancel_publish()`, `validate_reels()`

**ملاحظة**: هذا المتحكم لا يزال قيد التطوير.

### 4. SchedulerController
متحكم جدولة المهام
- **Signals**: `job_added`, `job_removed`, `job_started`, `job_completed`, `job_failed`, `scheduler_started`, `scheduler_stopped`, `log_message`
- **Methods**: `add_job()`, `remove_job()`, `start_scheduler()`, `stop_scheduler()`, `schedule_all_jobs()`, `unschedule_all_jobs()`

**مثال الاستخدام:**
```python
from controllers import SchedulerController

scheduler = SchedulerController()

# إضافة مهمة
job_id = scheduler.add_job(job_data)

# بدء المجدول
scheduler.start_scheduler()

# جدولة جميع المهام
scheduler.schedule_all_jobs()
```

## الملاحظات المهمة

1. **استخدام PySide6**: جميع المتحكمات تستخدم `Signal` و `Slot` من PySide6 وليس PyQt5/PyQt6
2. **Dependency Injection**: المتحكمات تستقبل الخدمات (Services) عبر الـ constructor
3. **Thread-Safe**: جميع العمليات محمية من مشاكل التزامن (Concurrency)
4. **توافقية**: المتحكمات الحالية لا تزال تستورد بعض الدوال من `admin.py` للحفاظ على التوافقية

## البنية المعمارية

```
controllers/
├── __init__.py                 # تصدير جميع المتحكمات
├── video_controller.py         # متحكم الفيديو
├── story_controller.py         # متحكم الستوري
├── reels_controller.py         # متحكم الريلز
├── scheduler_controller.py     # متحكم المجدول
└── README.md                   # هذا الملف
```

## التطوير المستقبلي

- [ ] نقل `SchedulerThread` كاملاً من `admin.py` إلى `VideoController`
- [ ] تنفيذ منطق نشر الريلز الكامل في `ReelsController`
- [ ] فصل المتحكمات تماماً عن `admin.py` (إزالة الاستيرادات المتبادلة)
- [ ] إضافة اختبارات وحدة (Unit Tests) لكل متحكم
