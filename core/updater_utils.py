"""
Application update utility functions.

هذا الملف يحتوي على دوال مساعدة للتحقق من تحديثات التطبيق وتثبيتها.
"""

import os
import sys
import re
import json
import subprocess
import tempfile

# قائمة المكتبات التي نتحقق من تحديثاتها
UPDATE_PACKAGES = ['requests', 'PySide6', 'pyqtdarktheme', 'qtawesome']


def _get_subprocess_windows_args() -> tuple:
    """
    الحصول على معاملات subprocess لإخفاء نافذة Console على Windows.

    العائد:
        tuple: (startupinfo, creationflags)
    """
    startupinfo = None
    creationflags = 0
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW
    return startupinfo, creationflags


def check_for_updates(log_fn=None) -> list:
    """
    التحقق من وجود تحديثات للمكتبات.

    العائد:
        قائمة بالمكتبات التي تحتاج تحديث: [(name, current_version, latest_version), ...]
    """
    updates = []
    packages_lower = [p.lower() for p in UPDATE_PACKAGES]

    try:
        # إخفاء نافذة الـ Console على Windows
        startupinfo, creationflags = _get_subprocess_windows_args()

        # الحصول على قائمة المكتبات القديمة
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=json'],
            capture_output=True,
            text=True,
            timeout=30,  # تقليل من 60 إلى 30
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                outdated = json.loads(result.stdout)
                for pkg in outdated:
                    if pkg.get('name', '').lower() in packages_lower:
                        updates.append((
                            pkg.get('name'),
                            pkg.get('version'),
                            pkg.get('latest_version')
                        ))
            except json.JSONDecodeError:
                pass
    except subprocess.TimeoutExpired:
        if log_fn:
            log_fn('⚠️ انتهت مهلة التحقق من التحديثات')
    except Exception as e:
        if log_fn:
            log_fn(f'❌ خطأ في التحقق من التحديثات: {e}')

    return updates


def get_installed_versions() -> dict:
    """الحصول على إصدارات المكتبات المثبتة."""
    versions = {}

    try:
        # إخفاء نافذة الـ Console على Windows
        startupinfo, creationflags = _get_subprocess_windows_args()

        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            timeout=30,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        if result.returncode == 0:
            installed = json.loads(result.stdout)

            for pkg in installed:
                if pkg['name'].lower() in [p.lower() for p in UPDATE_PACKAGES]:
                    versions[pkg['name']] = pkg['version']
    except Exception:
        pass

    return versions


def _validate_package_name(package_name: str) -> bool:
    """
    Validate package name to prevent command injection.
    التحقق من صحة اسم الحزمة لمنع حقن الأوامر.

    Args:
        package_name: Package name to validate

    Returns:
        True if valid, False otherwise
    """
    # Package names should only contain alphanumeric, hyphen, underscore, dot
    # Hyphen at end of character class to avoid escaping
    pattern = r'^[a-zA-Z0-9_.]+[a-zA-Z0-9_.-]*$'
    return bool(re.match(pattern, package_name))


def create_update_script(packages_to_update: list) -> str:
    """
    Create temporary update script.
    إنشاء سكربت التحديث المؤقت.

    Args:
        packages_to_update: List of package names to update

    Returns:
        Path to temporary script
    """
    # Validate all package names to prevent command injection
    for pkg in packages_to_update:
        if not _validate_package_name(pkg):
            raise ValueError(f"Invalid package name: {pkg}")

    # Only allow packages from our whitelist
    allowed_packages = [p.lower() for p in UPDATE_PACKAGES]
    validated_packages = [pkg for pkg in packages_to_update if pkg.lower() in allowed_packages]

    if not validated_packages:
        raise ValueError("No valid packages to update")

    packages_str = ' '.join(validated_packages)
    python_path = sys.executable
    script_path = os.path.abspath(sys.argv[0])

    if sys.platform == 'win32':
        # Windows batch script
        script_content = f'''@echo off
chcp 65001 > nul
echo.
echo ══════════════════════════════════════════════════
echo    جاري تحديث المكتبات - يرجى الانتظار...
echo ══════════════════════════════════════════════════
echo.
timeout /t 3 /nobreak > nul
"{python_path}" -m pip install --upgrade {packages_str}
echo.
echo ══════════════════════════════════════════════════
echo    ✅ تم التحديث بنجاح!
echo    جاري إعادة تشغيل البرنامج...
echo ══════════════════════════════════════════════════
echo.
timeout /t 2 /nobreak > nul
start "" "{python_path}" "{script_path}"
del "%~f0"
'''
        script_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.bat', delete=False, encoding='utf-8'
        )
    else:
        # Linux/Mac shell script
        script_content = f'''#!/bin/bash
echo ""
echo "══════════════════════════════════════════════════"
echo "   جاري تحديث المكتبات - يرجى الانتظار..."
echo "══════════════════════════════════════════════════"
echo ""
sleep 3
"{python_path}" -m pip install --upgrade {packages_str}
echo ""
echo "══════════════════════════════════════════════════"
echo "   ✅ تم التحديث بنجاح!"
echo "   جاري إعادة تشغيل البرنامج..."
echo "══════════════════════════════════════════════════"
echo ""
sleep 2
"{python_path}" "{script_path}" &
rm -- "$0"
'''
        script_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sh', delete=False, encoding='utf-8'
        )

    script_file.write(script_content)
    script_file.close()

    # جعل السكربت قابل للتنفيذ على Linux/Mac
    if sys.platform != 'win32':
        os.chmod(script_file.name, 0o755)

    return script_file.name


def run_update_and_restart(packages_to_update: list):
    """
    تشغيل سكربت التحديث وإغلاق البرنامج.
    """
    script_path = create_update_script(packages_to_update)

    if sys.platform == 'win32':
        # تشغيل السكربت في نافذة جديدة
        os.startfile(script_path)
    else:
        # تشغيل السكربت في الخلفية
        subprocess.Popen(['bash', script_path], start_new_session=True)

    # إغلاق البرنامج
    sys.exit(0)
