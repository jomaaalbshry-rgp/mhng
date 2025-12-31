# Event Handlers Module

## Overview / نظرة عامة

This module contains event handler classes that encapsulate event-driven logic for the main application window.

هذه الوحدة تحتوي على فئات معالجات الأحداث التي تلخص المنطق الموجه بالأحداث للنافذة الرئيسية للتطبيق.

## Structure / البنية

### TelegramHandlers - معالجات Telegram
Located in `telegram_handlers.py`

Handles Telegram notification events including:
- Testing connections / اختبار الاتصالات
- Sending notifications / إرسال الإشعارات
- Managing bot configuration / إدارة إعدادات البوت

**Methods:**
- `test_telegram_connection(bot_token, chat_id)` - Test Telegram connection
- `send_notification(message, silent)` - Send a notification
- `send_success_notification(page_name, video_name)` - Send success notification
- `send_error_notification(page_name, error)` - Send error notification
- `setup_notifier(bot_token, chat_id)` - Configure the notifier
- `is_enabled()` - Check if notifications are enabled

### UpdateHandlers - معالجات التحديثات
Located in `update_handlers.py`

Handles application update events including:
- Checking for updates / التحقق من التحديثات
- Downloading updates / تحميل التحديثات
- Managing update process / إدارة عملية التحديث

**Classes:**
- `UpdateCheckThread` - Background thread for checking updates
- `UpdateHandlers` - Main update handler class

**Methods:**
- `check_for_updates(silent)` - Check for available updates
- `_on_update_available(result, silent)` - Handle update available
- `_on_no_update(silent)` - Handle no update available
- `_on_update_error(error, silent)` - Handle update check error

### JobHandlers - معالجات الوظائف
Located in `job_handlers.py`

Handles job lifecycle events including:
- Job creation / إنشاء الوظائف
- Job updates / تحديث الوظائف
- Job deletion / حذف الوظائف
- Job execution / تنفيذ الوظائف

**Methods:**
- `on_job_created(job_data)` - Handle job creation
- `on_job_updated(job_data)` - Handle job update
- `on_job_deleted(job_key)` - Handle job deletion
- `on_job_started(job)` - Handle job start
- `on_job_completed(job, result)` - Handle job completion
- `on_job_error(job, error)` - Handle job error
- `on_schedule_toggled(job, enabled)` - Handle schedule toggle
- `confirm_delete(job_name)` - Confirm job deletion
- `confirm_stop_all()` - Confirm stopping all jobs

## Usage / الاستخدام

```python
from ui.handlers import TelegramHandlers, UpdateHandlers, JobHandlers

# In MainWindow.__init__
self.telegram_handlers = TelegramHandlers(self)
self.update_handlers = UpdateHandlers(self, current_version="1.0.0")
self.job_handlers = JobHandlers(self)

# Using the handlers
self.telegram_handlers.test_telegram_connection(token, chat_id)
self.update_handlers.check_for_updates(silent=False)
self.job_handlers.on_job_created(job_data)
```

## Benefits / الفوائد

1. **Separation of Concerns** - Each handler focuses on specific events
   فصل المسؤوليات - كل معالج يركز على أحداث محددة

2. **Testability** - Handlers can be tested independently
   قابلية الاختبار - يمكن اختبار المعالجات بشكل مستقل

3. **Maintainability** - Easier to maintain and extend
   سهولة الصيانة - أسهل في الصيانة والتوسع

4. **Reusability** - Handlers can be reused in different contexts
   إعادة الاستخدام - يمكن إعادة استخدام المعالجات في سياقات مختلفة

## Future Enhancements / التحسينات المستقبلية

- Add more specialized handlers for different event types
- Implement event bus pattern for loose coupling
- Add handler middleware for cross-cutting concerns
- Implement async/await patterns where appropriate
