"""
خدمة Facebook API - Facebook API Service
تحتوي على التكامل مع واجهة برمجة تطبيقات فيسبوك
Contains integration with Facebook API
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

from core.logger import log_info, log_error, log_warning, log_debug


class FacebookAPIService:
    """
    خدمة التعامل مع Facebook Graph API
    Service for interacting with Facebook Graph API
    
    هذه الخدمة مسؤولة عن:
    - إدارة التوكينات (tokens)
    - تبديل التوكينات القصيرة إلى طويلة
    - التعامل مع Facebook Graph API
    """
    
    def __init__(self, api_version: str = 'v20.0', api_timeout: int = 30, 
                 default_token_expiry: int = 5184000):
        """
        تهيئة خدمة Facebook API
        Initialize Facebook API service
        
        Args:
            api_version: إصدار Facebook Graph API (default: v20.0)
            api_timeout: مهلة طلبات API بالثواني (default: 30)
            default_token_expiry: مدة صلاحية التوكن الطويل بالثواني (default: 5184000 = 60 يوم)
        """
        self.api_version = api_version
        self.api_timeout = api_timeout
        self.default_token_expiry = default_token_expiry
        self.base_url = f"https://graph.facebook.com/{api_version}"
    
    def exchange_token_for_long_lived(self, app_id: str, app_secret: str, 
                                       short_lived_token: str) -> Tuple[bool, str, Optional[str]]:
        """
        تحويل التوكن القصير إلى توكن طويل (60 يوم) عبر Facebook Graph API
        Exchange short-lived token for long-lived token (60 days) via Facebook Graph API
        
        Args:
            app_id: معرف التطبيق - App ID
            app_secret: كلمة المرور - App Secret
            short_lived_token: التوكن القصير - Short-lived token
        
        Returns:
            tuple: (نجاح: bool, التوكن الطويل أو رسالة الخطأ: str, تاريخ الانتهاء: str أو None)
            tuple: (success: bool, long-lived token or error message: str, expiry date: str or None)
        """
        try:
            url = f'{self.base_url}/oauth/access_token'
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': app_id,
                'client_secret': app_secret,
                'fb_exchange_token': short_lived_token
            }
            
            response = requests.get(url, params=params, timeout=self.api_timeout)
            data = response.json()
            
            if 'error' in data:
                error_msg = data['error'].get('message', 'خطأ غير معروف')
                return False, f'❌ {error_msg}', None
            
            if 'access_token' in data:
                long_lived_token = data['access_token']
                # حساب تاريخ الانتهاء (60 يوم من الآن)
                expires_in = data.get('expires_in', self.default_token_expiry)
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                expires_at_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                
                return True, long_lived_token, expires_at_str
            
            return False, '❌ لم يتم الحصول على التوكن', None
            
        except requests.exceptions.Timeout:
            return False, '❌ انتهت مهلة الاتصال', None
        except requests.exceptions.ConnectionError:
            return False, '❌ فشل الاتصال بالخادم', None
        except Exception as e:
            return False, f'❌ خطأ: {str(e)}', None
    
    @staticmethod
    def get_all_app_tokens(db_file_path: Path, decrypt_fn) -> List[Dict[str, Any]]:
        """
        الحصول على جميع التطبيقات والتوكينات المحفوظة
        Get all saved applications and tokens
        
        Args:
            db_file_path: مسار ملف قاعدة البيانات - Database file path
            decrypt_fn: دالة فك التشفير - Decryption function
        
        Returns:
            قائمة من القواميس تحتوي على بيانات التطبيقات
            List of dictionaries containing app data
        """
        try:
            db_path = str(db_file_path)
            log_debug(f'[TokenManager] تحميل التوكينات من: {db_path}')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, app_name, app_id, app_secret, short_lived_token, 
                       long_lived_token, token_expires_at, created_at, updated_at
                FROM app_tokens
                ORDER BY id
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            apps = []
            for row in rows:
                app_data = {
                    'id': row[0],
                    'app_name': row[1],
                    'app_id': row[2],
                    'app_secret': decrypt_fn(row[3]) if row[3] else '',
                    'short_lived_token': decrypt_fn(row[4]) if row[4] else '',
                    'long_lived_token': decrypt_fn(row[5]) if row[5] else '',
                    'token_expires_at': row[6],
                    'created_at': row[7],
                    'updated_at': row[8]
                }
                apps.append(app_data)
                
                # تسجيل تحذير إذا كانت البيانات الحساسة مفقودة رغم وجود التوكن الطويل
                if app_data['long_lived_token'] and (not app_data['app_secret'] or not app_data['short_lived_token']):
                    missing = []
                    if not app_data['app_secret']:
                        missing.append('app_secret')
                    if not app_data['short_lived_token']:
                        missing.append('short_lived_token')
                    log_warning(f'[TokenManager] التطبيق {app_data["app_name"]} (id={row[0]}) يحتوي على توكن طويل ولكن ينقصه: {", ".join(missing)}')
            
            log_info(f'[TokenManager] تم تحميل {len(apps)} تطبيق')
            return apps
        except Exception as e:
            log_error(f'[TokenManager] خطأ في جلب التطبيقات: {e}')
            return []
    
    @staticmethod
    def save_app_token(db_file_path: Path, encrypt_fn, app_name: str, app_id: str, 
                       app_secret: str = '', short_lived_token: str = '', 
                       long_lived_token: str = '', token_expires_at: str = None, 
                       token_id: int = None) -> Tuple[bool, Optional[int]]:
        """
        حفظ أو تحديث تطبيق وتوكيناته
        Save or update application and its tokens
        
        Args:
            db_file_path: مسار ملف قاعدة البيانات - Database file path
            encrypt_fn: دالة التشفير - Encryption function
            app_name: اسم التطبيق - App name
            app_id: معرف التطبيق - App ID
            app_secret: كلمة المرور - App secret
            short_lived_token: التوكن القصير - Short-lived token
            long_lived_token: التوكن الطويل - Long-lived token
            token_expires_at: تاريخ انتهاء التوكن - Token expiration date
            token_id: معرف التطبيق للتحديث (None لإضافة جديد) - App ID for update (None for new)
        
        Returns:
            tuple: (نجاح: bool, معرف السجل: int أو None)
            tuple: (success: bool, record ID: int or None)
        """
        try:
            conn = sqlite3.connect(str(db_file_path))
            cursor = conn.cursor()
            
            # تشفير البيانات الحساسة
            encrypted_secret = encrypt_fn(app_secret) if app_secret else ''
            encrypted_short = encrypt_fn(short_lived_token) if short_lived_token else ''
            encrypted_long = encrypt_fn(long_lived_token) if long_lived_token else ''
            
            if token_id:
                # عند التحديث: الاحتفاظ بالقيم القديمة إذا كانت القيم الجديدة فارغة
                cursor.execute('''
                    SELECT app_secret, short_lived_token FROM app_tokens WHERE id = ?
                ''', (token_id,))
                existing_row = cursor.fetchone()
                
                if existing_row:
                    if not encrypted_secret and existing_row[0]:
                        encrypted_secret = existing_row[0]
                        log_info(f'[TokenManager] الاحتفاظ بـ app_secret الموجود للتطبيق {app_name} (id={token_id})')
                    if not encrypted_short and existing_row[1]:
                        encrypted_short = existing_row[1]
                        log_info(f'[TokenManager] الاحتفاظ بـ short_lived_token الموجود للتطبيق {app_name} (id={token_id})')
                
                log_info(f'[TokenManager] تحديث التوكينات للتطبيق {app_name} (id={token_id})')
                
                cursor.execute('''
                    UPDATE app_tokens SET
                        app_name = ?,
                        app_id = ?,
                        app_secret = ?,
                        short_lived_token = ?,
                        long_lived_token = ?,
                        token_expires_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (app_name, app_id, encrypted_secret, encrypted_short,
                      encrypted_long, token_expires_at, token_id))
                result_id = token_id
            else:
                log_info(f'[TokenManager] إضافة تطبيق جديد: {app_name}')
                
                cursor.execute('''
                    INSERT INTO app_tokens 
                    (app_name, app_id, app_secret, short_lived_token, long_lived_token, token_expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (app_name, app_id, encrypted_secret, encrypted_short,
                      encrypted_long, token_expires_at))
                result_id = cursor.lastrowid
                log_info(f'[TokenManager] تم إنشاء التطبيق {app_name} بمعرف {result_id}')
            
            conn.commit()
            conn.close()
            return True, result_id
        except Exception as e:
            log_error(f'[TokenManager] خطأ في حفظ التطبيق {app_name}: {e}')
            return False, None
    
    @staticmethod
    def delete_app_token(db_file_path: Path, token_id: int) -> bool:
        """
        حذف تطبيق من قاعدة البيانات
        Delete application from database
        
        Args:
            db_file_path: مسار ملف قاعدة البيانات - Database file path
            token_id: معرف التطبيق - App ID
        
        Returns:
            True إذا نجح الحذف - True if deletion successful
        """
        try:
            conn = sqlite3.connect(str(db_file_path))
            cursor = conn.cursor()
            
            # الحصول على اسم التطبيق قبل الحذف للتسجيل
            cursor.execute('SELECT app_name FROM app_tokens WHERE id = ?', (token_id,))
            row = cursor.fetchone()
            app_name = row[0] if row else 'غير معروف'
            
            cursor.execute('DELETE FROM app_tokens WHERE id = ?', (token_id,))
            conn.commit()
            conn.close()
            
            log_info(f'[TokenManager] تم حذف التطبيق: {app_name} (id={token_id})')
            return True
        except Exception as e:
            log_error(f'[TokenManager] خطأ في حذف التطبيق (id={token_id}): {e}')
            return False
    
    @staticmethod
    def get_all_long_lived_tokens(db_file_path: Path, decrypt_fn) -> List[str]:
        """
        الحصول على جميع التوكينات الطويلة الصالحة
        Get all valid long-lived tokens
        
        Args:
            db_file_path: مسار ملف قاعدة البيانات - Database file path
            decrypt_fn: دالة فك التشفير - Decryption function
        
        Returns:
            قائمة من التوكينات الطويلة - List of long-lived tokens
        """
        apps = FacebookAPIService.get_all_app_tokens(db_file_path, decrypt_fn)
        tokens = []
        for app in apps:
            if app.get('long_lived_token'):
                tokens.append(app['long_lived_token'])
        return tokens
