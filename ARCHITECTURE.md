# هيكل المشروع - Project Architecture

## 📋 نظرة عامة - Overview

تم إعادة هيكلة المشروع من ملف واحد ضخم (admin.py - 430KB) إلى بنية متعددة الطبقات ومنظمة بشكل احترافي.

The project was restructured from a single massive file (admin.py - 430KB) to a multi-layered, professionally organized structure.

## 🏗️ البنية المعمارية - Architectural Pattern

يتبع المشروع نمط **الطبقات المتعددة (Multi-Layered Architecture)** مع فصل واضح للمسؤوليات:

The project follows a **Multi-Layered Architecture** pattern with clear separation of concerns:

```
┌─────────────────────────────────────┐
│      UI Layer (طبقة الواجهة)        │
│  - main_window.py                   │
│  - scheduler_ui.py                  │
│  - components/, panels/, dialogs/   │
└────────────┬────────────────────────┘
             │ Signals & Slots
┌────────────▼────────────────────────┐
│   Controllers Layer (طبقة التحكم)   │
│  - video_controller.py              │
│  - story_controller.py              │
│  - reels_controller.py              │
│  - scheduler_controller.py          │
└────────────┬────────────────────────┘
             │ Method Calls
┌────────────▼────────────────────────┐
│   Services Layer (طبقة الخدمات)     │
│  - facebook_api.py                  │
│  - upload_service.py                │
└────────────┬────────────────────────┘
             │ HTTP Requests
┌────────────▼────────────────────────┐
│   External APIs (واجهات خارجية)     │
│  - Facebook Graph API               │
└─────────────────────────────────────┘
```

## 📚 الطبقات - Layers

### 1️⃣ طبقة واجهة المستخدم - UI Layer

**المسؤولية**: عرض البيانات والتفاعل مع المستخدم
**Responsibility**: Display data and handle user interactions

#### الملفات الرئيسية - Main Files:

##### `ui/main_window.py`
- النافذة الرئيسية للتطبيق
- إدارة التبويبات (فيديو، ستوري، ريلز، مجدول)
- عرض السجلات والحالة
- Main application window
- Manages tabs (video, story, reels, scheduler)
- Displays logs and status
- **Phase 6**: Reduced from 7,868 to 6,822 lines (849 lines moved to services)

##### `ui/helpers.py`
- دوال مساعدة للواجهة
- UI helper functions
- **Phase 6**: Added formatting functions (mask_token, format_time, etc.)

##### `ui/scheduler_ui.py`
- واجهة المجدول
- إدارة المهام المجدولة
- Scheduler interface
- Manages scheduled tasks

##### `ui/components/`
- **progress_widget.py**: عنصر شريط التقدم
- **jobs_table.py**: جدول عرض المهام
- **log_viewer.py**: عارض السجلات
- **progress_widget.py**: Progress bar widget
- **jobs_table.py**: Jobs display table
- **log_viewer.py**: Log viewer

##### `ui/panels/`
- لوحات الواجهة القابلة لإعادة الاستخدام
- Reusable UI panels

**الهيكلة - Structure:**
```
ui/panels/
├── video_panel.py      → Helper widgets (DraggablePreviewLabel, WatermarkPreviewDialog)
│                         Shared between video and reels / مشتركة بين الفيديو والريلز
├── story_panel.py      → StoryPanel(QWidget) with unique story settings
│                         لوحة الستوري مع إعدادات فريدة
├── pages_panel.py      → PagesPanel(QWidget) for page management
│                         لوحة إدارة الصفحات
└── reels_panel.py      → Documentation ONLY - explains why NO ReelsPanel class
                          توثيق فقط - يشرح لماذا لا توجد ReelsPanel class
```

**ملاحظة معمارية مهمة - Important Architectural Note:**

⚠️ **الريلز لا يحتاج لوحة منفصلة** - Reels does NOT need a separate panel

**السبب - Reason:**
- الريلز يستخدم نفس واجهة الفيديو بالكامل (العنوان، الوصف، Anti-Ban، العلامة المائية)
- Reels use the EXACT SAME UI as video (title, description, Anti-Ban, watermark)
- الفرق الوحيد في Backend (نوع الوظيفة وطريقة الرفع)
- The only difference is in the backend (job type and upload method)

**مقارنة - Comparison:**
- ✅ **Story**: له إعدادات فريدة (عدد الستوريات، التأخير) → لوحة منفصلة
- ✅ **Story**: Has unique settings (stories per schedule, delay) → Separate panel
- ❌ **Reels**: نفس إعدادات الفيديو → لا لوحة منفصلة (يشارك مع الفيديو)
- ❌ **Reels**: Same settings as video → No separate panel (shares with video)

**لمزيد من التفاصيل، راجع:** `ui/panels/reels_panel.py`
**For more details, see:** `ui/panels/reels_panel.py`

##### `ui/widgets/`
- عناصر واجهة مخصصة (NoScrollComboBox, NoScrollSpinBox, etc.)
- Custom widgets (NoScrollComboBox, NoScrollSpinBox, etc.)

##### `ui/dialogs/`
- نوافذ الحوار (HashtagManagerDialog, etc.)
- Dialog windows (HashtagManagerDialog, etc.)

**التواصل**: تستخدم Qt Signals للتواصل مع Controllers
**Communication**: Uses Qt Signals to communicate with Controllers

---

### 2️⃣ طبقة التحكم - Controllers Layer

**المسؤولية**: إدارة منطق الأعمال وتنسيق العمليات
**Responsibility**: Manage business logic and coordinate operations

#### الملفات - Files:

##### `controllers/video_controller.py`
```python
class VideoController(QObject):
    """
    متحكم رفع الفيديو
    Handles video upload operations
    """
    # Signals
    upload_started = Signal(str)
    upload_progress = Signal(int, str)
    upload_completed = Signal(dict)
    upload_failed = Signal(str)
    
    # Methods
    - upload_video()
    - cancel_upload()
    - check_internet_connection()
```

**المسؤوليات**:
- إدارة عملية رفع الفيديو
- متابعة التقدم
- معالجة الأخطاء
- Manage video upload process
- Track progress
- Handle errors

##### `controllers/story_controller.py`
```python
class StoryController(QObject):
    """
    متحكم رفع الستوري
    Handles story upload operations
    """
    # Supports both single and batch mode
    - upload_story()
    - upload_story_batch()
```

**المسؤوليات**:
- إدارة رفع الستوريز (صور وفيديوهات)
- دعم الوضع الفردي ووضع الدُفعات
- Manage story uploads (photos and videos)
- Support single and batch modes

##### `controllers/reels_controller.py`
```python
class ReelsController(QObject):
    """
    متحكم رفع الريلز
    Handles reels upload operations
    """
    - upload_reels()
    - check_duration()
```

**المسؤوليات**:
- إدارة رفع الريلز
- التحقق من المدة
- Manage reels uploads
- Validate duration

##### `controllers/scheduler_controller.py`
```python
class SchedulerController(QObject):
    """
    متحكم المجدول
    Handles scheduling operations
    """
    - add_job()
    - remove_job()
    - execute_job()
```

**المسؤوليات**:
- إدارة المهام المجدولة
- تنفيذ المهام في الوقت المحدد
- Manage scheduled tasks
- Execute tasks at specified times

**التواصل**:
- **من UI**: يستقبل Signals من الواجهة
- **إلى Services**: يستدعي دوال الخدمات
- **From UI**: Receives Signals from UI
- **To Services**: Calls service methods

---

### 3️⃣ طبقة الخدمات - Services Layer

**المسؤولية**: التفاعل مع الخدمات الخارجية والـ APIs
**Responsibility**: Interact with external services and APIs

#### الملفات - Files:

##### `services/facebook_api.py`
```python
class FacebookAPIService:
    """
    خدمة التعامل مع Facebook Graph API
    Facebook Graph API service
    """
    
    # Token Management
    - exchange_token_for_long_lived()
    - validate_token()
    
    # Pages Management
    - get_user_pages()
    - get_page_access_token()
    
    # Content Operations
    - create_video_upload_session()
    - upload_video_chunk()
    - publish_video()
```

**المسؤوليات**:
- إدارة التوكينات (تبديل، تحديث، تحقق)
- جلب قائمة الصفحات
- التفاعل مع Facebook Graph API
- Token management (exchange, refresh, validate)
- Fetch pages list
- Interact with Facebook Graph API

##### `services/upload_service.py`
```python
class UploadService:
    """
    خدمة رفع الملفات
    File upload service
    """
    
    # Upload Methods
    - upload_video()
    - upload_story()
    - upload_reels()
    
    # Resumable Upload
    - resumable_upload()
    - upload_chunk()
    
    # Progress Tracking
    - track_progress()
```

**المسؤوليات**:
- رفع الملفات إلى فيسبوك
- دعم الرفع المتقطع (Resumable Upload)
- متابعة التقدم
- Upload files to Facebook
- Support resumable upload
- Track progress

##### `services/data_access.py` 🆕
```python
# Phase 6: Data access functions (24 functions)
# Moved from ui/main_window.py

# File Paths
- get_settings_file()
- get_jobs_file()
- get_database_file()
- migrate_old_files()

# Hashtag Management
- save_hashtag_group()
- get_hashtag_groups()
- delete_hashtag_group()

# Schedule Templates
- init_default_templates()
- ensure_default_templates()
- get_all_templates()
- get_template_by_id()
- save_template()
- delete_template()
- get_default_template()
- set_default_template()
- get_schedule_times_for_template()

# Upload Statistics
- log_upload()
- get_upload_stats()
- reset_upload_stats()
- generate_text_chart()

# Working Hours (Legacy)
- is_within_working_hours()
- calculate_time_to_working_hours_start()
```

**المسؤوليات**:
- الوصول إلى البيانات المحلية
- إدارة قاعدة البيانات
- إحصائيات الرفع
- Data access layer
- Database management
- Upload statistics

**التواصل**:
- **من Controllers**: يُستدعى من المتحكمات
- **إلى APIs**: يرسل طلبات HTTP إلى Facebook
- **From Controllers**: Called by controllers
- **To APIs**: Sends HTTP requests to Facebook

---

### 4️⃣ الوحدات الأساسية - Core Modules

**المسؤولية**: توفير وظائف أساسية مشتركة
**Responsibility**: Provide shared core functionality

#### `core/constants.py`
- ثوابت التطبيق (API versions, timeouts, limits)
- Application constants

#### `core/single_instance.py`
```python
class SingleInstanceManager:
    """
    ضمان تشغيل نسخة واحدة فقط من التطبيق
    Ensure only one instance of the app runs
    """
    - is_already_running()
    - send_restore_message()
```

#### `core/threads.py`
- **TokenExchangeThread**: خيط تبديل التوكن
- **FetchPagesThread**: خيط جلب الصفحات
- Background worker threads

#### `core/notifications.py`
- **TelegramNotifier**: إرسال إشعارات تلجرام
- **NotificationSystem**: نظام الإشعارات العام
- Telegram notifications
- General notification system

---

### 5️⃣ الوحدات المساعدة - Utility Modules

#### `database_manager.py`
```python
class DatabaseManager:
    """
    إدارة قاعدة البيانات
    Database management
    """
    - initialize_database()
    - get_connection()
    - execute_query()
```

**المسؤوليات**:
- إدارة الاتصالات بقاعدة البيانات
- تنفيذ الاستعلامات
- Database connection management
- Execute queries

#### `secure_utils/secure_storage.py`
```python
# التشفير والفك
- encrypt_text()
- decrypt_text()
```

**المسؤوليات**:
- تشفير البيانات الحساسة
- فك تشفير البيانات
- Encrypt sensitive data
- Decrypt data

#### `logger.py`
```python
# نظام السجلات
- log_info()
- log_error()
- log_warning()
- log_debug()
```

#### `utils.py`
- دوال مساعدة عامة
- **SmartUploadScheduler**: جدولة ذكية للرفع
- **APIUsageTracker**: تتبع استخدام API
- General utility functions

---

## 🔄 تدفق البيانات - Data Flow

### مثال: رفع فيديو - Example: Video Upload

```
1. المستخدم ينقر "رفع فيديو" في UI
   User clicks "Upload Video" in UI
   
   ↓
   
2. main_window.py يصدر signal
   main_window.py emits signal
   
   signal: upload_video_requested(video_path, page_id, options)
   
   ↓
   
3. video_controller.py يستقبل signal
   video_controller.py receives signal
   
   @Slot()
   def upload_video(self, video_path, page_id, options):
       # Validate inputs
       # Check internet connection
       # Call service
   
   ↓
   
4. upload_service.py يبدأ الرفع
   upload_service.py starts upload
   
   def upload_video(self, path, page_id, token):
       # Create upload session
       # Upload chunks
       # Track progress
       # Publish video
   
   ↓
   
5. facebook_api.py يتواصل مع API
   facebook_api.py communicates with API
   
   requests.post(url, data=data, headers=headers)
   
   ↓
   
6. النتيجة ترجع عبر نفس المسار
   Result returns through same path
   
   Controller emits signals:
   - upload_progress(percentage, message)
   - upload_completed(result)
   - upload_failed(error)
   
   ↓
   
7. UI تحدث العرض
   UI updates display
   
   - Update progress bar
   - Show success/error message
   - Add to log viewer
```

---

## 🎯 مبادئ التصميم - Design Principles

### 1. فصل المسؤوليات (Separation of Concerns)
كل طبقة لها مسؤولية واضحة ومحددة.

Each layer has a clear and specific responsibility.

### 2. الاعتماد على التجريد (Dependency on Abstraction)
Controllers تعتمد على Services، وليس على تفاصيل التنفيذ.

Controllers depend on Services, not on implementation details.

### 3. إعادة الاستخدام (Reusability)
Components و Services قابلة لإعادة الاستخدام في أماكن مختلفة.

Components and Services are reusable in different contexts.

### 4. قابلية الاختبار (Testability)
كل طبقة يمكن اختبارها بشكل مستقل.

Each layer can be tested independently.

### 5. قابلية الصيانة (Maintainability)
الكود منظم ومقسم إلى ملفات صغيرة سهلة الإدارة.

Code is organized into small, manageable files.

---

## 📊 إحصائيات المشروع - Project Statistics

### قبل إعادة الهيكلة - Before Restructuring:
- **ملف واحد**: admin.py (430KB, ~12,000 سطر)
- **Single file**: admin.py (430KB, ~12,000 lines)

### بعد إعادة الهيكلة - After Restructuring:
```
controllers/     : ~674 lines (4 files)
services/        : ~745 lines (2 files)
ui/main_window.py: ~8,776 lines
ui/components/   : ~400 lines
core/            : ~500 lines
Total organized  : Modular, maintainable structure
```

### الفوائد - Benefits:
- ✅ سهولة القراءة والفهم
- ✅ سهولة الصيانة والتطوير
- ✅ إمكانية الاختبار
- ✅ قابلية إعادة الاستخدام
- ✅ عمل الفريق بشكل أفضل

- ✅ Easier to read and understand
- ✅ Easier to maintain and develop
- ✅ Testable
- ✅ Reusable
- ✅ Better team collaboration

---

## 🔮 التطوير المستقبلي - Future Development

### المقترحات - Suggestions:

1. **Unit Tests**: إضافة اختبارات وحدة لكل طبقة
2. **API Abstraction**: إضافة طبقة تجريد للـ API
3. **Dependency Injection**: استخدام حقن التبعيات
4. **Async/Await**: تحسين الأداء باستخدام async
5. **Plugin System**: نظام إضافات (plugins)

1. **Unit Tests**: Add unit tests for each layer
2. **API Abstraction**: Add API abstraction layer
3. **Dependency Injection**: Use dependency injection
4. **Async/Await**: Improve performance with async
5. **Plugin System**: Add plugin system

---

## 📚 المراجع - References

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Facebook Graph API](https://developers.facebook.com/docs/graph-api/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [MVC Pattern](https://en.wikipedia.org/wiki/Model%E2%80%93view%E2%80%93controller)

---

**تم التوثيق بواسطة فريق Mang**

**Documented by Mang Team**

_آخر تحديث: 2025_

_Last updated: 2025_
