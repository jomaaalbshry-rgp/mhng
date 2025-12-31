"""
لوحة الريلز - Reels Panel
تحتوي على واجهة إدارة رفع الريلز
Contains the interface for managing reels uploads

ملاحظة هامة جداً - IMPORTANT NOTE:
===========================================
⚠️ الريلز لا يحتاج إلى لوحة منفصلة ⚠️
⚠️ Reels does NOT need a separate panel ⚠️

السبب - Reason:
================
الريلز يستخدم نفس عناصر الواجهة كالفيديو بالضبط:
Reels use the EXACT SAME UI elements as video:
- العنوان (Title)
- الوصف (Description)
- Anti-Ban (Jitter)
- العلامة المائية (Watermark)
- إعدادات الجدولة (Scheduling settings)

بخلاف الستوري الذي له إعدادات خاصة فريدة (عدد الستوريات، التأخير العشوائي)،
Unlike story which has UNIQUE settings (stories per schedule, random delay),
الريلز ليس له أي إعدادات خاصة.
reels has NO unique settings.

الفروقات الوحيدة (Backend Only) - The ONLY differences (Backend Only):
=========================================================================
1. نوع الوظيفة: ReelsJob بدلاً من VideoJob
   Job type: ReelsJob instead of VideoJob
   
2. طريقة الرفع: upload_reels_with_retry() بدلاً من upload_video()
   Upload method: upload_reels_with_retry() instead of upload_video()
   
3. التحقق من المدة: check_reels_duration() - يجب أن تكون بين 3-90 ثانية
   Duration validation: check_reels_duration() - must be between 3-90 seconds
   
4. API Endpoint: مختلف عن الفيديو العادي
   API Endpoint: Different from regular video

الهيكلة الحالية والصحيحة - Current and CORRECT Structure:
=============================================================
في main_window.py:
- job_type_combo يسمح باختيار: فيديو / ستوري / ريلز
- عند اختيار الريلز، يتم استخدام نفس عناصر الفيديو
- الفرق يكون في نوع Job المُنشأ (ReelsJob) والمنطق في الخلفية

القرار المعماري - Architectural Decision:
===========================================
✅ الريلز يشارك الواجهة مع الفيديو في main_window.py
✅ Reels shares UI with video in main_window.py

✅ لا داعي لإنشاء ReelsPanel(QWidget) لأنه سيكون مكرراً 100% من عناصر الفيديو
✅ No need to create ReelsPanel(QWidget) as it would be 100% duplicate of video elements

✅ المنطق الخاص بالريلز (ReelsJob, upload_reels, etc.) موجود في controllers/reels_controller.py
✅ Reels-specific logic (ReelsJob, upload_reels, etc.) is in controllers/reels_controller.py

الخلاصة - Summary:
===================
هذا الملف موجود للتوثيق فقط ولتوضيح سبب عدم وجود ReelsPanel class.
This file exists for documentation only, to clarify why there is no ReelsPanel class.

إذا أردت تعديل واجهة الريلز، عدّل الواجهة المشتركة في main_window.py.
If you want to modify reels UI, modify the shared UI in main_window.py.

إذا أردت تعديل منطق الريلز، عدّل controllers/reels_controller.py.
If you want to modify reels logic, modify controllers/reels_controller.py.
"""

# لا يوجد ReelsPanel كـ QWidget لأن الريلز يستخدم نفس واجهة الفيديو
# No ReelsPanel as QWidget because reels use the same video UI
# الكود موجود في main_window.py ضمن المنطق المشترك للفيديو/ريلز
# Code is in main_window.py within the shared video/reels logic

# Note to future developers:
# If you're tempted to create a ReelsPanel class, please read the documentation above first.
# Creating duplicate UI components is not DRY (Don't Repeat Yourself) and will lead to
# maintenance nightmares. The current architecture is correct.
