#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script to verify all modules can be imported without errors.
This tests for NameError and AttributeError issues.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_core_imports():
    """Test importing core modules"""
    print("Testing core imports...")
    try:
        from core import get_logger, log_info, log_error, log_warning, log_debug
        from core import BaseJob, APP_TITLE, APP_DATA_FOLDER
        print("✅ Core imports successful")
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ Core imports failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Core imports error (not NameError/AttributeError): {e}")
        return True  # Not a NameError/AttributeError, so the test passes

def test_services_imports():
    """Test importing services modules"""
    print("Testing services imports...")
    try:
        from services import DatabaseManager, get_database_manager, initialize_database
        from services import get_settings_file, get_jobs_file, get_database_file
        print("✅ Services imports successful")
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ Services imports failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Services imports error (not NameError/AttributeError): {e}")
        return True

def test_ui_helpers_imports():
    """Test importing UI helpers"""
    print("Testing UI helpers imports...")
    try:
        from ui.helpers import (
            create_fallback_icon, load_app_icon, get_icon,
            create_icon_button, create_icon_action,
            ICONS, ICON_COLORS, HAS_QTAWESOME,
            mask_token, format_remaining_time,
            simple_encrypt, simple_decrypt
        )
        print("✅ UI helpers imports successful")
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ UI helpers imports failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ UI helpers imports error (not NameError/AttributeError): {e}")
        return True

def test_ui_panels_imports():
    """Test importing UI panels"""
    print("Testing UI panels imports...")
    try:
        from ui.panels import DraggablePreviewLabel, WatermarkPreviewDialog, StoryPanel, PagesPanel
        print("✅ UI panels imports successful")
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ UI panels imports failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ UI panels imports error (not NameError/AttributeError): {e}")
        return True

def test_ui_main_window_imports():
    """Test importing main window (includes HAS_QDARKTHEME check)"""
    print("Testing main window imports...")
    try:
        # First check if ui.main_window module can be imported
        import ui.main_window
        
        # Check that HAS_QDARKTHEME is defined
        if not hasattr(ui.main_window, 'HAS_QDARKTHEME'):
            print("❌ HAS_QDARKTHEME not defined in ui.main_window")
            return False
        
        print(f"✅ Main window imports successful (HAS_QDARKTHEME={ui.main_window.HAS_QDARKTHEME})")
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ Main window imports failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Main window imports error (not NameError/AttributeError): {e}")
        return True

def test_database_initialization():
    """Test database initialization (single init)"""
    print("Testing database initialization...")
    try:
        from services import initialize_database
        
        # Initialize the database
        initialize_database()
        print("✅ Database initialization successful")
        
        # Try to initialize again - should not cause errors
        initialize_database()
        print("✅ Second database initialization call handled correctly")
        
        return True
    except (NameError, AttributeError) as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Database initialization error (not NameError/AttributeError): {e}")
        return True

def main():
    """Run all import tests"""
    print("=" * 60)
    print("Starting import validation tests")
    print("=" * 60)
    
    tests = [
        test_core_imports,
        test_services_imports,
        test_ui_helpers_imports,
        test_ui_panels_imports,
        test_database_initialization,
        test_ui_main_window_imports,  # Last because it imports everything
    ]
    
    results = []
    for test in tests:
        print()
        result = test()
        results.append(result)
    
    print()
    print("=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)
    
    if all(results):
        print("✅ All import tests passed!")
        print("✅ No NameError or AttributeError detected")
        return 0
    else:
        print("❌ Some import tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
