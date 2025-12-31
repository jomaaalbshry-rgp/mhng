"""
Job Key Helpers
================

Helper functions for creating and retrieving unique job keys.
These functions are used to identify jobs by combining page_id and app_name.
"""


def make_job_key(page_id: str, app_name: str = '') -> str:
    """
    إنشاء مفتاح فريد للوظيفة يجمع بين page_id و app_name.

    هذا يسمح بإنشاء وظائف متعددة لنفس الصفحة من تطبيقات مختلفة.

    المعاملات:
        page_id: معرف الصفحة
        app_name: اسم التطبيق

    العائد:
        مفتاح فريد بصيغة "page_id:::app_name" أو "page_id" إذا لم يكن هناك app_name

    ملاحظة:
        يتم استخدام ::: كفاصل بدلاً من | لتجنب المشاكل مع أسماء التطبيقات
        التي قد تحتوي على حرف |
    """
    if app_name:
        return f"{page_id}:::{app_name}"
    return page_id


def get_job_key(job) -> str:
    """
    الحصول على مفتاح الوظيفة من كائن الوظيفة.

    المعاملات:
        job: كائن الوظيفة (PageJob, StoryJob, ReelsJob)

    العائد:
        مفتاح الوظيفة الفريد
    """
    # استخدام getattr لدعم التوافق مع الإصدارات القديمة والكائنات المختلفة
    app_name = getattr(job, 'app_name', '')
    return make_job_key(job.page_id, app_name)


__all__ = ['make_job_key', 'get_job_key']
