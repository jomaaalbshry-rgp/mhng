#!/usr/bin/env python3
"""
وحدة التحديث المنفصلة - Separate Updater Module

هذا الملف يعمل كعملية منفصلة لتحديث المكتبات وإعادة تشغيل التطبيق.
يتم استدعاؤه من التطبيق الرئيسي عند الضغط على "تحديث الكل".

آلية العمل:
1. التطبيق الرئيسي يحفظ معلومات التحديث في ملف JSON مؤقت
2. التطبيق الرئيسي يشغّل هذا السكربت كعملية منفصلة
3. التطبيق الرئيسي يغلق نفسه
4. هذا السكربت ينتظر إغلاق التطبيق الرئيسي
5. يقوم بتحديث المكتبات المطلوبة
6. يعيد تشغيل التطبيق الرئيسي
"""

import sys
import os
import time
import json
import subprocess
import tempfile
import re
from pathlib import Path


# ==================== رموز الأخطاء ====================

class UpdateErrorCodes:
    """رموز الأخطاء للتحديث."""
    SUCCESS = 0
    NO_UPDATE_INFO = 1
    INVALID_UPDATE_INFO = 2
    NO_PACKAGES = 3
    NO_APP_PATH = 4
    UPDATE_FAILED = 5
    RESTART_FAILED = 6
    TIMEOUT = 7
    UNKNOWN_ERROR = 99
    
    MESSAGES = {
        SUCCESS: '✅ تم التحديث بنجاح',
        NO_UPDATE_INFO: '❌ ملف معلومات التحديث غير موجود',
        INVALID_UPDATE_INFO: '❌ فشل قراءة ملف معلومات التحديث',
        NO_PACKAGES: '❌ لا توجد مكتبات للتحديث',
        NO_APP_PATH: '❌ مسار التطبيق غير محدد',
        UPDATE_FAILED: '❌ فشل تحديث بعض المكتبات',
        RESTART_FAILED: '❌ فشل إعادة تشغيل التطبيق',
        TIMEOUT: '❌ انتهت مهلة التحديث',
        UNKNOWN_ERROR: '❌ خطأ غير متوقع'
    }
    
    @classmethod
    def get_message(cls, code: int) -> str:
        return cls.MESSAGES.get(code, cls.MESSAGES[cls.UNKNOWN_ERROR])


# ثوابت
UPDATE_INFO_FILENAME = 'update_info.json'
MAX_WAIT_SECONDS = 30  # الحد الأقصى للانتظار لإغلاق التطبيق
WAIT_INTERVAL = 1  # فاصل التحقق بالثواني


def get_update_info_path() -> Path:
    """الحصول على مسار ملف معلومات التحديث."""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            return Path(appdata) / 'Page management' / UPDATE_INFO_FILENAME
    # Fallback لأنظمة أخرى
    home = Path.home()
    return home / '.config' / 'Page management' / UPDATE_INFO_FILENAME


def wait_for_app_close(app_pid: int = None, timeout: int = MAX_WAIT_SECONDS) -> bool:
    """
    انتظار إغلاق التطبيق الرئيسي.
    
    Args:
        app_pid: معرف العملية للتطبيق الرئيسي (اختياري)
        timeout: الحد الأقصى للانتظار بالثواني
    
    Returns:
        True إذا تم إغلاق التطبيق، False إذا انتهت المهلة
    """
    if app_pid is None:
        # إذا لم يتم تمرير PID، انتظر فترة قصيرة فقط
        print('⏳ انتظار 3 ثواني لإغلاق التطبيق...')
        time.sleep(3)
        return True
    
    print(f'⏳ انتظار إغلاق التطبيق (PID: {app_pid})...')
    
    elapsed = 0
    while elapsed < timeout:
        try:
            # التحقق من أن العملية لا تزال موجودة
            if sys.platform == 'win32':
                # في Windows، استخدم tasklist
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {app_pid}', '/FO', 'CSV', '/NH'],
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if str(app_pid) not in result.stdout:
                    print('✅ تم إغلاق التطبيق')
                    return True
            else:
                # في Linux/Mac، استخدم kill -0
                os.kill(app_pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            # العملية غير موجودة = التطبيق مغلق
            print('✅ تم إغلاق التطبيق')
            return True
        
        time.sleep(WAIT_INTERVAL)
        elapsed += WAIT_INTERVAL
        print(f'   ... انتظار ({elapsed}/{timeout} ثانية)')
    
    print('⚠️ انتهت مهلة الانتظار - سنحاول التحديث على أي حال')
    return False


def validate_package_name(package_name: str) -> bool:
    """
    التحقق من صحة اسم الحزمة لمنع حقن الأوامر.
    
    Args:
        package_name: اسم الحزمة للتحقق
    
    Returns:
        True إذا كان الاسم صالحاً
    """
    # Package names must start with a letter and can contain alphanumeric, hyphen, underscore, dot
    pattern = r'^[a-zA-Z][a-zA-Z0-9_.-]*$'
    return bool(re.match(pattern, package_name))


def update_packages(packages: list) -> tuple:
    """
    تحديث المكتبات المحددة.
    
    Args:
        packages: قائمة بأسماء المكتبات المراد تحديثها
    
    Returns:
        (success: bool, message: str)
    """
    if not packages:
        return False, 'لا توجد مكتبات للتحديث'
    
    # قائمة المكتبات المسموح بتحديثها (whitelist)
    ALLOWED_PACKAGES = ['requests', 'pyside6', 'pyqtdarktheme', 'qtawesome']
    
    # التحقق من صحة أسماء المكتبات والتأكد من أنها في القائمة المسموحة
    valid_packages = []
    for pkg in packages:
        if not validate_package_name(pkg):
            print(f'⚠️ تخطي مكتبة غير صالحة: {pkg}')
            continue
        # التحقق من أن المكتبة في القائمة المسموحة
        if pkg.lower() not in ALLOWED_PACKAGES:
            print(f'⚠️ تخطي مكتبة غير مسموحة: {pkg}')
            continue
        valid_packages.append(pkg)
    
    if not valid_packages:
        return False, 'جميع أسماء المكتبات غير صالحة أو غير مسموحة'
    
    print(f'📦 تحديث المكتبات: {", ".join(valid_packages)}')
    
    try:
        # إخفاء نافذة الـ Console على Windows
        subprocess_kwargs = {}
        if sys.platform == 'win32':
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        
        # تحديث كل مكتبة على حدة
        failed = []
        for pkg in valid_packages:
            print(f'   📥 تحديث {pkg}...')
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', pkg],
                capture_output=True, text=True, timeout=300,
                **subprocess_kwargs
            )
            
            if result.returncode == 0:
                print(f'   ✅ تم تحديث {pkg}')
            else:
                print(f'   ❌ فشل تحديث {pkg}: {result.stderr[:100]}')
                failed.append(pkg)
        
        if failed:
            return False, f'فشل تحديث: {", ".join(failed)}'
        
        return True, 'تم التحديث بنجاح'
    
    except subprocess.TimeoutExpired:
        return False, 'انتهت مهلة التحديث - يرجى التحقق من اتصال الإنترنت والمحاولة مرة أخرى'
    except Exception as e:
        return False, f'خطأ في التحديث: {str(e)}'


def check_for_updates_cli(packages_to_check: list = None) -> tuple:
    """
    التحقق من وجود تحديثات للمكتبات (للاستخدام من سطر الأوامر).
    
    المعاملات:
        packages_to_check: قائمة بأسماء المكتبات للتحقق منها (اختياري)
    
    العائد:
        tuple: (توجد_تحديثات: bool, رسالة: str, قائمة_التحديثات: list)
    """
    if packages_to_check is None:
        packages_to_check = ['requests', 'pyside6', 'pyqtdarktheme', 'qtawesome']
    
    print('🔍 جاري التحقق من التحديثات...')
    
    try:
        # إخفاء نافذة الـ Console على Windows
        subprocess_kwargs = {}
        if sys.platform == 'win32':
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        
        # الحصول على قائمة المكتبات القديمة
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=json'],
            capture_output=True, 
            text=True, 
            timeout=60,
            **subprocess_kwargs
        )
        
        if result.returncode != 0:
            return False, '❌ فشل التحقق من التحديثات', []
        
        if not result.stdout.strip():
            print('✅ لا توجد تحديثات متاحة - جميع المكتبات محدثة!')
            return False, '✅ لا توجد تحديثات متاحة - جميع المكتبات محدثة!', []
        
        try:
            outdated = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, '❌ فشل تحليل نتائج التحقق', []
        
        # تصفية المكتبات المطلوبة فقط
        packages_lower = [p.lower() for p in packages_to_check]
        updates = []
        
        for pkg in outdated:
            if pkg.get('name', '').lower() in packages_lower:
                updates.append({
                    'name': pkg.get('name'),
                    'current': pkg.get('version'),
                    'latest': pkg.get('latest_version')
                })
        
        if not updates:
            print('✅ لا توجد تحديثات متاحة - جميع المكتبات محدثة!')
            return False, '✅ لا توجد تحديثات متاحة - جميع المكتبات محدثة!', []
        
        # عرض التحديثات المتاحة
        print(f'\n📦 يوجد {len(updates)} تحديثات متاحة:')
        print('-' * 50)
        for upd in updates:
            print(f"   • {upd['name']}: {upd['current']} ← {upd['latest']}")
        print('-' * 50)
        
        return True, f'⚠️ يوجد {len(updates)} تحديثات متاحة', updates
        
    except subprocess.TimeoutExpired:
        return False, '❌ انتهت مهلة التحقق من التحديثات', []
    except Exception as e:
        return False, f'❌ خطأ: {str(e)}', []


def restart_app(app_path: str) -> bool:
    """
    إعادة تشغيل التطبيق الرئيسي.
    
    Args:
        app_path: مسار ملف التطبيق الرئيسي
    
    Returns:
        True إذا نجح التشغيل
    """
    print(f'🔄 إعادة تشغيل التطبيق: {app_path}')
    
    try:
        if sys.platform == 'win32':
            # في Windows، استخدم start لتشغيل التطبيق في نافذة جديدة
            os.startfile(app_path)
        else:
            # في Linux/Mac، استخدم subprocess مع start_new_session
            subprocess.Popen(
                [sys.executable, app_path],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        print('✅ تم تشغيل التطبيق')
        return True
    except Exception as e:
        print(f'❌ فشل تشغيل التطبيق: {e}')
        return False


def cleanup_update_info():
    """حذف ملف معلومات التحديث."""
    try:
        info_path = get_update_info_path()
        if info_path.exists():
            info_path.unlink()
            print('🧹 تم حذف ملف معلومات التحديث')
    except Exception:
        pass


def main():
    """الدالة الرئيسية للمُحدّث."""
    print('=' * 60)
    print('   🔄 جاري تحديث المكتبات - يرجى الانتظار...')
    print('=' * 60)
    print()
    
    # قراءة معلومات التحديث
    info_path = get_update_info_path()
    
    if not info_path.exists():
        print(UpdateErrorCodes.get_message(UpdateErrorCodes.NO_UPDATE_INFO))
        print('   يرجى تشغيل التحديث من داخل التطبيق')
        print('\n💡 نصيحة: افتح التطبيق، اذهب إلى الإعدادات، ثم اضغط على "البحث عن تحديثات"')
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.NO_UPDATE_INFO
    
    try:
        with open(info_path, 'r', encoding='utf-8') as f:
            update_info = json.load(f)
    except json.JSONDecodeError as e:
        print(f'{UpdateErrorCodes.get_message(UpdateErrorCodes.INVALID_UPDATE_INFO)}: تنسيق JSON غير صالح')
        print(f'   التفاصيل: {e}')
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.INVALID_UPDATE_INFO
    except Exception as e:
        print(f'{UpdateErrorCodes.get_message(UpdateErrorCodes.INVALID_UPDATE_INFO)}: {e}')
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.INVALID_UPDATE_INFO
    
    packages = update_info.get('packages', [])
    app_path = update_info.get('app_path', '')
    app_pid = update_info.get('app_pid')
    
    if not packages:
        print(UpdateErrorCodes.get_message(UpdateErrorCodes.NO_PACKAGES))
        print('   تأكد من وجود تحديثات متاحة قبل تشغيل المُحدّث')
        cleanup_update_info()
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.NO_PACKAGES
    
    if not app_path:
        print(UpdateErrorCodes.get_message(UpdateErrorCodes.NO_APP_PATH))
        print('   يرجى إعادة تشغيل التحديث من داخل التطبيق')
        cleanup_update_info()
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.NO_APP_PATH
    
    # عرض معلومات التحديث
    print(f'📦 المكتبات للتحديث: {", ".join(packages)}')
    print(f'📂 مسار التطبيق: {app_path}')
    print()
    
    # انتظار إغلاق التطبيق الرئيسي
    wait_for_app_close(app_pid)
    
    # تحديث المكتبات
    success, message = update_packages(packages)
    
    print()
    if success:
        print('=' * 60)
        print('   ✅ تم التحديث بنجاح!')
        print('   جميع المكتبات محدثة الآن.')
        print('=' * 60)
    else:
        print('=' * 60)
        print(f'   ⚠️ {message}')
        print('   يمكنك المحاولة مرة أخرى لاحقاً.')
        print('=' * 60)
    
    # حذف ملف معلومات التحديث
    cleanup_update_info()
    
    # إعادة تشغيل التطبيق
    print()
    print('🔄 جاري إعادة تشغيل التطبيق...')
    time.sleep(2)
    
    if restart_app(app_path):
        return UpdateErrorCodes.SUCCESS if success else UpdateErrorCodes.UPDATE_FAILED
    else:
        print(UpdateErrorCodes.get_message(UpdateErrorCodes.RESTART_FAILED))
        print('   يرجى تشغيل التطبيق يدوياً.')
        input('\nاضغط Enter للخروج...')
        return UpdateErrorCodes.RESTART_FAILED


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print('\n⏹️ تم الإلغاء بواسطة المستخدم')
        sys.exit(1)
    except Exception as e:
        print(f'\n{UpdateErrorCodes.get_message(UpdateErrorCodes.UNKNOWN_ERROR)}: {e}')
        import traceback
        traceback.print_exc()
        input('\nاضغط Enter للخروج...')
        sys.exit(UpdateErrorCodes.UNKNOWN_ERROR)
