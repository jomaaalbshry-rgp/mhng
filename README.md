# Facebook Video Scheduler - مجدول فيديوهات فيسبوك

تطبيق سطح مكتب لجدولة ونشر الفيديوهات والستوريز والريلز على صفحات فيسبوك.

A desktop application for scheduling and publishing videos, stories, and reels to Facebook pages.

## 📋 المحتويات - Table of Contents

- [نظرة عامة](#نظرة-عامة---overview)
- [المميزات](#المميزات---features)
- [المتطلبات](#المتطلبات---requirements)
- [التثبيت](#التثبيت---installation)
- [التشغيل](#التشغيل---running)
- [هيكل المشروع](#هيكل-المشروع---project-structure)
- [الاستخدام](#الاستخدام---usage)

## 🌟 نظرة عامة - Overview

تطبيق Facebook Video Scheduler هو حل متكامل لإدارة المحتوى على صفحات فيسبوك، يتيح لك:
- جدولة الفيديوهات والستوريز والريلز
- رفع المحتوى بشكل تلقائي
- إدارة عدة صفحات من واجهة واحدة
- متابعة حالة الرفع والنشر

Facebook Video Scheduler is a comprehensive solution for managing content on Facebook pages, allowing you to:
- Schedule videos, stories, and reels
- Upload content automatically
- Manage multiple pages from one interface
- Track upload and publish status

## ✨ المميزات - Features

### 📹 إدارة الفيديوهات - Video Management
- رفع الفيديوهات إلى صفحات فيسبوك
- جدولة النشر في أوقات محددة
- إضافة علامة مائية للفيديوهات
- دعم الرفع المتقطع للملفات الكبيرة

### 📱 إدارة الستوريز - Stories Management
- نشر الستوريز (صور وفيديوهات)
- جدولة الستوريز بشكل تلقائي
- دعم الدُفعات (Batch Mode)
- إضافة تأخير عشوائي بين المنشورات

### 🎬 إدارة الريلز - Reels Management
- رفع الريلز إلى الصفحات
- التحقق من مدة الفيديو
- جدولة النشر

### 🔐 الأمان - Security
- تشفير التوكينات والبيانات الحساسة
- إدارة آمنة لمفاتيح التطبيقات
- دعم نسخة واحدة من التطبيق

### 🎨 الواجهة - Interface
- واجهة عربية كاملة (RTL)
- دعم الثيم الداكن
- سهلة الاستخدام والتنقل

## 📦 المتطلبات - Requirements

### متطلبات النظام - System Requirements
- Python 3.8 أو أحدث
- Windows / Linux / macOS
- اتصال بالإنترنت

### المكتبات المطلوبة - Required Libraries
```
PySide6>=6.6.0
requests>=2.31.0
pyqtdarktheme>=2.1.0
qtawesome>=1.3.1
cryptography>=41.0.0
```

## 🚀 التثبيت - Installation

### 1. استنساخ المستودع - Clone Repository
```bash
git clone https://github.com/jomaafor-code/mang.git
cd mang
```

### 2. إنشاء بيئة افتراضية - Create Virtual Environment
```bash
python -m venv venv

# على Windows - On Windows:
venv\Scripts\activate

# على Linux/macOS - On Linux/macOS:
source venv/bin/activate
```

### 3. تثبيت المتطلبات - Install Requirements
```bash
pip install -r requirements.txt
```

## ▶️ التشغيل - Running

### تشغيل التطبيق - Run Application
```bash
python admin.py
```

### بناء ملف تنفيذي - Build Executable
```bash
# على Windows - On Windows:
build.bat

# أو - Or:
pyinstaller PageManagement.spec
```

## 📁 هيكل المشروع - Project Structure

```
mang/
│
├── admin.py                    # نقطة الدخول الرئيسية - Main entry point
├── __init__.py                # ملف التعريف الرئيسي - Root package init
├── requirements.txt           # المتطلبات - Dependencies
│
├── controllers/               # طبقة التحكم - Controllers Layer
│   ├── __init__.py
│   ├── video_controller.py    # متحكم الفيديو - Video controller
│   ├── story_controller.py    # متحكم الستوري - Story controller
│   ├── reels_controller.py    # متحكم الريلز - Reels controller
│   └── scheduler_controller.py # متحكم المجدول - Scheduler controller
│
├── services/                  # طبقة الخدمات - Services Layer
│   ├── __init__.py
│   ├── facebook_api.py        # خدمة Facebook API - Facebook API service
│   └── upload_service.py      # خدمة الرفع - Upload service
│
├── ui/                        # طبقة واجهة المستخدم - UI Layer
│   ├── __init__.py
│   ├── main_window.py         # النافذة الرئيسية - Main window
│   ├── scheduler_ui.py        # واجهة المجدول - Scheduler UI
│   ├── helpers.py             # دوال مساعدة للواجهة - UI helpers
│   │
│   ├── components/            # المكونات المشتركة - Shared components
│   │   ├── __init__.py
│   │   ├── progress_widget.py
│   │   ├── jobs_table.py
│   │   └── log_viewer.py
│   │
│   ├── panels/                # لوحات الواجهة - UI panels
│   │   └── __init__.py
│   │
│   ├── widgets/               # عناصر الواجهة المخصصة - Custom widgets
│   │   └── __init__.py
│   │
│   └── dialogs/               # نوافذ الحوار - Dialogs
│       └── __init__.py
│
├── core/                      # الوحدات الأساسية - Core modules
│   ├── __init__.py
│   ├── constants.py           # الثوابت - Constants
│   ├── single_instance.py     # إدارة نسخة واحدة - Single instance
│   ├── threads.py             # خيوط العمل - Worker threads
│   └── notifications.py       # نظام الإشعارات - Notifications
│
├── secure_utils/              # أدوات التشفير - Security utilities
│   ├── __init__.py
│   └── secure_storage.py      # التخزين الآمن - Secure storage
│
├── assets/                    # الموارد - Resources
│   └── (icons, images, etc.)
│
├── baseJob.py                 # الفئة الأساسية للمهام - Base job class
├── videoTasks.py              # مهام الفيديو - Video tasks
├── storyTasks.py              # مهام الستوري - Story tasks
├── reelsTasks.py              # مهام الريلز - Reels tasks
├── database_manager.py        # إدارة قاعدة البيانات - Database manager
├── token_manager.py           # إدارة التوكينات - Token manager
├── logger.py                  # نظام السجلات - Logging system
├── utils.py                   # دوال مساعدة عامة - General utilities
└── updater.py                 # نظام التحديثات - Update system
```

### وصف المجلدات - Folder Descriptions

#### `controllers/` - طبقة التحكم
تحتوي على المتحكمات التي تدير منطق الأعمال:
- **video_controller.py**: إدارة رفع ونشر الفيديوهات
- **story_controller.py**: إدارة رفع ونشر الستوريز
- **reels_controller.py**: إدارة رفع ونشر الريلز
- **scheduler_controller.py**: إدارة جدولة المهام

Contains controllers that manage business logic:
- **video_controller.py**: Manages video upload and publishing
- **story_controller.py**: Manages story upload and publishing
- **reels_controller.py**: Manages reels upload and publishing
- **scheduler_controller.py**: Manages task scheduling

#### `services/` - طبقة الخدمات
تحتوي على الخدمات التي تتفاعل مع APIs الخارجية:
- **facebook_api.py**: التكامل مع Facebook Graph API
- **upload_service.py**: خدمة رفع الملفات

Contains services that interact with external APIs:
- **facebook_api.py**: Facebook Graph API integration
- **upload_service.py**: File upload service

#### `ui/` - طبقة واجهة المستخدم
تحتوي على جميع عناصر الواجهة:
- **main_window.py**: النافذة الرئيسية للتطبيق
- **scheduler_ui.py**: واجهة المجدول
- **components/**: مكونات قابلة لإعادة الاستخدام
- **panels/**: لوحات الواجهة
- **widgets/**: عناصر واجهة مخصصة
- **dialogs/**: نوافذ الحوار

Contains all UI elements:
- **main_window.py**: Main application window
- **scheduler_ui.py**: Scheduler interface
- **components/**: Reusable components
- **panels/**: UI panels
- **widgets/**: Custom widgets
- **dialogs/**: Dialog windows

#### `core/` - الوحدات الأساسية
تحتوي على الوظائف الأساسية للتطبيق:
- **constants.py**: ثوابت التطبيق
- **single_instance.py**: التأكد من تشغيل نسخة واحدة
- **threads.py**: خيوط العمل في الخلفية
- **notifications.py**: نظام الإشعارات

Contains core application functionality:
- **constants.py**: Application constants
- **single_instance.py**: Single instance enforcement
- **threads.py**: Background worker threads
- **notifications.py**: Notification system

## 💡 الاستخدام - Usage

### 1. إعداد التطبيق - Application Setup
1. قم بتشغيل التطبيق
2. أدخل App ID و App Secret من تطبيق فيسبوك
3. أدخل Access Token وقم بتبديله لتوكن طويل المدى

### 2. اختيار الصفحة - Select Page
1. انقر على "جلب الصفحات" للحصول على قائمة صفحاتك
2. اختر الصفحة المراد النشر عليها

### 3. رفع المحتوى - Upload Content

#### للفيديوهات - For Videos:
1. اختر تبويب "فيديو"
2. اختر مجلد الفيديوهات
3. حدد خيارات الرفع (عنوان، وصف، إلخ)
4. انقر "رفع فيديو"

#### للستوريز - For Stories:
1. اختر تبويب "ستوري"
2. اختر مجلد الستوريز
3. حدد عدد الستوريز لكل دفعة
4. انقر "نشر ستوري"

#### للريلز - For Reels:
1. اختر تبويب "ريلز"
2. اختر مجلد الريلز
3. حدد خيارات النشر
4. انقر "رفع ريلز"

### 4. جدولة المحتوى - Schedule Content
1. اذهب إلى تبويب "المجدول"
2. أضف مهمة جديدة
3. حدد الوقت والتكرار
4. احفظ المهمة

## 🔧 التطوير - Development

### البنية المعمارية - Architecture
التطبيق مبني على نمط MVC (Model-View-Controller):
- **Model**: قاعدة البيانات والبيانات (database_manager.py)
- **View**: واجهة المستخدم (ui/)
- **Controller**: المتحكمات (controllers/)

The application follows the MVC (Model-View-Controller) pattern:
- **Model**: Database and data (database_manager.py)
- **View**: User interface (ui/)
- **Controller**: Controllers (controllers/)

### تدفق البيانات - Data Flow
```
UI → Controller → Service → Facebook API
                    ↓
                 Database
```

للمزيد من التفاصيل، راجع [ARCHITECTURE.md](ARCHITECTURE.md)

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md)

## 📝 الترخيص - License

هذا المشروع ملك لفريق Mang.

This project belongs to Mang Team.

## 👥 المساهمة - Contributing

للمساهمة في المشروع، يرجى:
1. عمل Fork للمستودع
2. إنشاء فرع للميزة الجديدة
3. إجراء التغييرات
4. إرسال Pull Request

To contribute:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a Pull Request

## 📞 الدعم - Support

للدعم الفني أو الاستفسارات، يرجى فتح Issue في المستودع.

For technical support or inquiries, please open an Issue in the repository.

---

**صُنع بـ ❤️ بواسطة فريق Mang**

**Made with ❤️ by Mang Team**
