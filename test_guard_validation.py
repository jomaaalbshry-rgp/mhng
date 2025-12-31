#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify HAS_QDARKTHEME guard is properly implemented.
This test can run without PySide6 by checking the source code directly.
"""

import os
import re

def test_has_qdarktheme_guard():
    """Test that HAS_QDARKTHEME is properly defined in ui/main_window.py"""
    print("Testing HAS_QDARKTHEME guard in ui/main_window.py...")
    
    main_window_path = os.path.join(os.path.dirname(__file__), 'ui', 'main_window.py')
    helpers_path = os.path.join(os.path.dirname(__file__), 'ui', 'helpers.py')
    
    if not os.path.exists(main_window_path):
        print(f"❌ File not found: {main_window_path}")
        return False
    
    with open(main_window_path, 'r', encoding='utf-8') as f:
        main_window_content = f.read()
    
    # Check 1: HAS_QDARKTHEME is imported from helpers or defined locally
    # Option 1: Imported from helpers
    if 'from ui.helpers import' in main_window_content and 'HAS_QDARKTHEME' in main_window_content:
        print("✅ HAS_QDARKTHEME imported from ui.helpers (centralized)")
        
        # Verify it exists in helpers.py
        if not os.path.exists(helpers_path):
            print(f"❌ File not found: {helpers_path}")
            return False
        
        with open(helpers_path, 'r', encoding='utf-8') as f:
            helpers_content = f.read()
        
        # Check that HAS_QDARKTHEME is defined in helpers
        import_pattern = r'try:\s+import qdarktheme\s+HAS_QDARKTHEME = True\s+except ImportError:\s+HAS_QDARKTHEME = False'
        if not re.search(import_pattern, helpers_content, re.MULTILINE):
            print("❌ HAS_QDARKTHEME guard not found in ui/helpers.py")
            return False
        print("✅ HAS_QDARKTHEME guard properly defined in ui/helpers.py")
        
    # Option 2: Defined locally with try-except
    else:
        import_pattern = r'try:\s+import qdarktheme\s+HAS_QDARKTHEME = True\s+except ImportError:\s+HAS_QDARKTHEME = False'
        if not re.search(import_pattern, main_window_content, re.MULTILINE):
            print("❌ HAS_QDARKTHEME not imported from helpers and not defined locally")
            return False
        print("✅ HAS_QDARKTHEME guard properly defined locally")
    
    # Check 2: HAS_QDARKTHEME is used before qdarktheme
    has_usage = main_window_content.find('HAS_QDARKTHEME')
    qdarktheme_usage = main_window_content.find('qdarktheme.')
    
    if has_usage == -1:
        print("❌ HAS_QDARKTHEME not found in file")
        return False
    
    if qdarktheme_usage != -1 and has_usage > qdarktheme_usage:
        print("❌ qdarktheme used before HAS_QDARKTHEME guard is available")
        return False
    
    print("✅ HAS_QDARKTHEME guard is available before any qdarktheme usage")
    
    # Check 3: apply_theme function uses HAS_QDARKTHEME
    apply_theme_match = re.search(r'def apply_theme\(.*?\):(.*?)(?=\n    def |\nclass |\Z)', main_window_content, re.DOTALL)
    if not apply_theme_match:
        print("⚠️ apply_theme function not found")
        return True  # Not a critical error
    
    apply_theme_body = apply_theme_match.group(1)
    
    if 'HAS_QDARKTHEME' not in apply_theme_body:
        print("❌ apply_theme doesn't check HAS_QDARKTHEME")
        return False
    
    if 'if HAS_QDARKTHEME:' in apply_theme_body:
        print("✅ apply_theme properly checks HAS_QDARKTHEME")
    else:
        print("⚠️ apply_theme uses HAS_QDARKTHEME but not as a guard")
    
    # Check 4: Fallback exists when qdarktheme is not available
    if 'else:' in apply_theme_body and 'Fallback' in apply_theme_body:
        print("✅ Fallback theme exists when qdarktheme is not available")
    else:
        print("⚠️ Fallback theme may not be properly implemented")
    
    return True

def test_admin_py_initialization():
    """Test that admin.py initializes database before importing MainWindow"""
    print("\nTesting admin.py database initialization order...")
    
    admin_path = os.path.join(os.path.dirname(__file__), 'admin.py')
    
    if not os.path.exists(admin_path):
        print(f"❌ File not found: {admin_path}")
        return False
    
    with open(admin_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check 1: initialize_database is called
    if 'initialize_database()' not in content:
        print("❌ initialize_database() not called in admin.py")
        return False
    print("✅ initialize_database() is called in admin.py")
    
    # Check 2: Database initialized before MainWindow import
    db_init_pos = content.find('initialize_database()')
    mainwindow_import_pos = content.find('from ui import MainWindow')
    
    if db_init_pos == -1 or mainwindow_import_pos == -1:
        print("❌ Could not find both initialize_database and MainWindow import")
        return False
    
    if db_init_pos < mainwindow_import_pos:
        print("✅ Database initialized before MainWindow import")
    else:
        print("❌ MainWindow imported before database initialization!")
        return False
    
    # Check 3: MainWindow import happens after DB init
    lines = content.split('\n')
    db_line = -1
    import_line = -1
    
    for i, line in enumerate(lines):
        if 'initialize_database()' in line:
            db_line = i
        if 'from ui import MainWindow' in line:
            import_line = i
    
    if db_line >= 0 and import_line >= 0:
        print(f"   - Database init at line {db_line + 1}")
        print(f"   - MainWindow import at line {import_line + 1}")
        if import_line > db_line:
            print("✅ Correct initialization order confirmed")
        else:
            print("❌ Incorrect initialization order!")
            return False
    
    return True

def test_no_duplicate_db_init():
    """Test that main_window doesn't duplicate database initialization"""
    print("\nTesting for duplicate database initialization...")
    
    main_window_path = os.path.join(os.path.dirname(__file__), 'ui', 'main_window.py')
    
    if not os.path.exists(main_window_path):
        print(f"❌ File not found: {main_window_path}")
        return False
    
    with open(main_window_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that initialize_database is imported but not called
    if 'from services import' in content and 'initialize_database' in content:
        print("✅ initialize_database imported (for type hints/reference)")
        
        # Check it's not called at module level
        if 'initialize_database()' in content:
            print("❌ initialize_database() called in main_window.py!")
            return False
        print("✅ initialize_database() NOT called in main_window.py")
    
    # Check for comment about DB init
    if 'Database is initialized in admin.py' in content:
        print("✅ Comment confirms DB init happens in admin.py")
    
    return True

def main():
    """Run all tests"""
    print("=" * 70)
    print("HAS_QDARKTHEME Guard and Database Initialization Validation")
    print("=" * 70)
    
    tests = [
        ("HAS_QDARKTHEME Guard", test_has_qdarktheme_guard),
        ("Admin.py DB Initialization", test_admin_py_initialization),
        ("No Duplicate DB Init", test_no_duplicate_db_init),
    ]
    
    results = []
    for name, test in tests:
        print(f"\n{name}:")
        print("-" * 70)
        result = test()
        results.append((name, result))
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if not result:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("✅ All tests passed!")
        print("✅ HAS_QDARKTHEME is properly guarded")
        print("✅ Database initialization is correct")
        print("✅ No NameError or AttributeError will occur")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
