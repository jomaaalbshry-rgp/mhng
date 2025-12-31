# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\JOMAAMSI\\Downloads\\Compressed\\facebook-main\\admin.py'],
    pathex=[],
    binaries=[('C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin\\ffmpeg.exe', 'ffmpeg'), ('C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin\\ffprobe.exe', 'ffmpeg')],
    datas=[('C:\\Users\\JOMAAMSI\\Downloads\\Compressed\\facebook-main\\assets', 'assets')],
    hiddenimports=['core', 'core.base_job', 'core.logger', 'core.utils', 'services', 'services.facebook_api', 'services.upload_service', 'services.database_manager', 'services.token_manager', 'services.updater', 'controllers', 'controllers.video_controller', 'controllers.story_controller', 'controllers.reels_controller', 'controllers.scheduler_controller', 'ui', 'ui.main_window', 'ui.scheduler_ui', 'ui.components', 'ui.components.jobs_table', 'ui.components.log_viewer', 'ui.components.progress_widget', 'ui.panels', 'ui.panels.settings_panel', 'secure_utils', 'secure_utils.secure_storage', 'requests', 'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtNetwork', 'PySide6.QtSvg', 'pyqtdarktheme', 'qtawesome', 'cryptography', 'cryptography.fernet', 'sqlite3', 'json', 'threading', 'subprocess', 'pathlib'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'qtpy', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PageManagement',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\JOMAAMSI\\Downloads\\Compressed\\facebook-main\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PageManagement',
)
