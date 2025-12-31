# سكربت تجميع المشروع - PowerShell
# Page Management Build Script with FFmpeg

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Building Page Management..." -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan

$projectPath = $PSScriptRoot
Set-Location $projectPath

# التحقق من وجود FFmpeg
$ffmpegPath = "C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
if (Test-Path "$ffmpegPath\ffmpeg.exe") {
    Write-Host "[OK] FFmpeg found at: $ffmpegPath" -ForegroundColor Green
} else {
    Write-Host "[WARNING] FFmpeg not found at: $ffmpegPath" -ForegroundColor Yellow
}

# تفعيل البيئة الافتراضية وتجميع البرنامج
& "$projectPath\.venv\Scripts\python.exe" -m PyInstaller `
    --clean `
    --noconfirm `
    --onedir `
    --windowed `
    --name PageManagement `
    --icon "$projectPath\assets\icon.ico" `
    --add-data "$projectPath\assets;assets" `
    --add-binary "$ffmpegPath\ffmpeg.exe;ffmpeg" `
    --add-binary "$ffmpegPath\ffprobe.exe;ffmpeg" `
    --hidden-import "core" `
    --hidden-import "core.base_job" `
    --hidden-import "core.logger" `
    --hidden-import "core.utils" `
    --hidden-import "services" `
    --hidden-import "services.facebook_api" `
    --hidden-import "services.upload_service" `
    --hidden-import "services.database_manager" `
    --hidden-import "services.token_manager" `
    --hidden-import "services.updater" `
    --hidden-import "controllers" `
    --hidden-import "controllers.video_controller" `
    --hidden-import "controllers.story_controller" `
    --hidden-import "controllers.reels_controller" `
    --hidden-import "controllers.scheduler_controller" `
    --hidden-import "ui" `
    --hidden-import "ui.main_window" `
    --hidden-import "ui.scheduler_ui" `
    --hidden-import "ui.components" `
    --hidden-import "ui.components.jobs_table" `
    --hidden-import "ui.components.log_viewer" `
    --hidden-import "ui.components.progress_widget" `
    --hidden-import "ui.panels" `
    --hidden-import "ui.panels.settings_panel" `
    --hidden-import "secure_utils" `
    --hidden-import "secure_utils.secure_storage" `
    --hidden-import "requests" `
    --hidden-import "PySide6" `
    --hidden-import "PySide6.QtCore" `
    --hidden-import "PySide6.QtGui" `
    --hidden-import "PySide6.QtWidgets" `
    --hidden-import "PySide6.QtNetwork" `
    --hidden-import "PySide6.QtSvg" `
    --hidden-import "pyqtdarktheme" `
    --hidden-import "qtawesome" `
    --hidden-import "cryptography" `
    --hidden-import "cryptography.fernet" `
    --hidden-import "sqlite3" `
    --hidden-import "json" `
    --hidden-import "threading" `
    --hidden-import "subprocess" `
    --hidden-import "pathlib" `
    --exclude-module PyQt5 `
    --exclude-module PyQt6 `
    --exclude-module PySide2 `
    --exclude-module qtpy `
    --exclude-module tkinter `
    --noconsole `
    "$projectPath\admin.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   Build completed successfully!" -ForegroundColor Green
    Write-Host "   Output: dist\PageManagement\" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    # التحقق من وجود FFmpeg في المخرجات
    if (Test-Path "dist\PageManagement\ffmpeg\ffmpeg. exe") {
        Write-Host "   [OK] FFmpeg included successfully" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "   Build failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Read-Host "Press Enter to exit"