"""
وحدة إدارة التوكينات - Token Manager Module

هذه الوحدة مسؤولة عن:
- تخزين واسترجاع التوكينات
- تبديل التوكينات القصيرة إلى طويلة
- التحقق من صلاحية التوكينات
- جلب الصفحات (الشخصية + Business Manager)
"""

import json
import os
import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from core.logger import log_info, log_error, log_debug
from PySide6.QtCore import QThread, Signal


# ==================== ثوابت ====================

# إصدار Facebook Graph API
FACEBOOK_API_VERSION = "v20.0"

# مهلة طلبات API بالثواني
FACEBOOK_API_TIMEOUT = 30

# الحد الأقصى للصفحات لكل طلب API
PAGES_FETCH_LIMIT = 500

# الحد الأقصى لـ Business Managers
BUSINESS_FETCH_LIMIT = 100

# مدة صلاحية التوكن الطويل (60 يوم)
DEFAULT_TOKEN_EXPIRY_SECONDS = 5184000


class TokenManager:
    """مدير التوكينات"""
    
    def __init__(self, tokens_file: str = "tokens.json"):
        self.tokens_file = tokens_file
        self.tokens: Dict = {}
        self.load_tokens()
    
    def load_tokens(self) -> None:
        """تحميل التوكينات من الملف"""
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, 'r', encoding='utf-8') as f:
                    self.tokens = json.load(f)
                log_info(f"[TokenManager] تم تحميل {len(self.tokens)} توكين")
            except Exception as e:
                log_error(f"[TokenManager] خطأ في تحميل التوكينات: {e}")
                self.tokens = {}
    
    def save_tokens(self) -> None:
        """حفظ التوكينات إلى الملف"""
        try:
            with open(self.tokens_file, 'w', encoding='utf-8') as f:
                json.dump(self.tokens, f, indent=2, ensure_ascii=False)
            log_info("[TokenManager] تم حفظ التوكينات")
        except Exception as e:
            log_error(f"[TokenManager] خطأ في حفظ التوكينات: {e}")
    
    def add_token(self, app_name: str, app_id: str, app_secret: str, 
                  short_token: str, long_token: str = None) -> bool:
        """إضافة توكين جديد"""
        self.tokens[app_name] = {
            'app_id': app_id,
            'app_secret': app_secret,
            'short_token': short_token,
            'long_token': long_token
        }
        self.save_tokens()
        return True
    
    def get_token(self, app_name: str) -> Optional[Dict]:
        """الحصول على توكين بالاسم"""
        return self.tokens.get(app_name)
    
    def get_all_tokens(self) -> Dict:
        """الحصول على جميع التوكينات"""
        return self.tokens
    
    def delete_token(self, app_name: str) -> bool:
        """حذف توكين"""
        if app_name in self.tokens:
            del self.tokens[app_name]
            self.save_tokens()
            return True
        return False
    
    def exchange_short_to_long_token(self, app_id: str, app_secret: str, 
                                      short_token: str) -> Optional[str]:
        """تبديل التوكين القصير إلى طويل"""
        try:
            url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/oauth/access_token"
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': app_id,
                'client_secret': app_secret,
                'fb_exchange_token': short_token
            }
            response = requests.get(url, params=params, timeout=FACEBOOK_API_TIMEOUT)
            data = response.json()
            
            if 'access_token' in data:
                log_info("[TokenManager] تم تبديل التوكين بنجاح")
                return data['access_token']
            else:
                log_error(f"[TokenManager] فشل تبديل التوكين: {data}")
                return None
        except Exception as e:
            log_error(f"[TokenManager] خطأ في تبديل التوكين: {e}")
            return None


# ==================== جلب الصفحات ====================

def get_pages(long_token: str) -> Dict:
    """
    جلب جميع الصفحات (الشخصية + Business Manager)
    
    يتم جلب الصفحات الشخصية في طلب منفصل عن صفحات Business Manager
    لتجنب فشل الطلب إذا لم يكن لدى المستخدم صلاحية business_management.
    
    Args:
        long_token: التوكين الطويل
    
    Returns:
        {
            'my_pages': [{'id': ..., 'name': ..., 'access_token': ...}],
            'business_managers': [
                {
                    'bm_name': 'BM 1',
                    'bm_id': '123',
                    'pages': [{'id': ..., 'name': ..., 'access_token': ...}]
                }
            ]
        }
    """
    result = {
        'my_pages': [],
        'business_managers': []
    }
    
    # ========== الخطوة 1: جلب الصفحات الشخصية من /me/accounts ==========
    try:
        url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/me/accounts"
        params = {
            'access_token': long_token,
            'fields': 'name,id,access_token',
            'limit': PAGES_FETCH_LIMIT
        }
        
        response = requests.get(url, params=params, timeout=FACEBOOK_API_TIMEOUT)
        data = response.json()
        
        if 'error' in data:
            log_error(f"[PageFetcher] خطأ في جلب الصفحات الشخصية: {data.get('error', {}).get('message', 'خطأ غير معروف')}")
        elif 'data' in data:
            for page in data['data']:
                result['my_pages'].append({
                    'id': page.get('id'),
                    'name': page.get('name'),
                    'access_token': page.get('access_token')
                })
            log_info(f"[PageFetcher] تم جلب {len(result['my_pages'])} صفحة شخصية")
        
    except requests.exceptions.Timeout:
        log_error("[PageFetcher] انتهت مهلة الاتصال أثناء جلب الصفحات الشخصية")
    except requests.exceptions.ConnectionError:
        log_error("[PageFetcher] فشل الاتصال بالخادم أثناء جلب الصفحات الشخصية")
    except Exception as e:
        log_error(f"[PageFetcher] خطأ في جلب الصفحات الشخصية: {e}")
    
    # ========== الخطوة 2: محاولة جلب صفحات Business Manager (في طلب منفصل) ==========
    try:
        url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/me/businesses"
        params = {
            'access_token': long_token,
            'fields': f'name,id,owned_pages.limit({PAGES_FETCH_LIMIT}){{name,id,access_token}}',
            'limit': BUSINESS_FETCH_LIMIT
        }
        
        response = requests.get(url, params=params, timeout=FACEBOOK_API_TIMEOUT)
        data = response.json()
        
        # إذا حدث خطأ (مثل عدم وجود صلاحية business_management)، لا نوقف العملية
        if 'error' in data:
            error_msg = data.get('error', {}).get('message', 'خطأ غير معروف')
            log_debug(f"[PageFetcher] لم يتم جلب صفحات Business Manager: {error_msg}")
        elif 'data' in data:
            for bm in data['data']:
                bm_data = {
                    'bm_name': bm.get('name', 'Unknown BM'),
                    'bm_id': bm.get('id'),
                    'pages': []
                }
                
                if 'owned_pages' in bm and 'data' in bm['owned_pages']:
                    for page in bm['owned_pages']['data']:
                        bm_data['pages'].append({
                            'id': page.get('id'),
                            'name': page.get('name'),
                            'access_token': page.get('access_token')
                        })
                
                if bm_data['pages']:  # فقط إذا كان هناك صفحات
                    result['business_managers'].append(bm_data)
            
            if result['business_managers']:
                log_info(f"[PageFetcher] تم جلب {len(result['business_managers'])} Business Manager")
        
    except requests.exceptions.Timeout:
        log_debug("[PageFetcher] انتهت مهلة الاتصال أثناء جلب Business Manager")
    except requests.exceptions.ConnectionError:
        log_debug("[PageFetcher] فشل الاتصال بالخادم أثناء جلب Business Manager")
    except Exception as e:
        # لا نوقف العملية إذا فشل جلب Business Manager
        log_debug(f"[PageFetcher] لم يتم جلب Business Manager: {e}")
    
    # ملخص النتيجة
    total_bm_pages = sum(len(bm['pages']) for bm in result['business_managers'])
    log_info(f"[PageFetcher] المجموع: {len(result['my_pages'])} صفحة شخصية + {total_bm_pages} صفحة من Business Manager")
    
    return result


# ==================== Worker Threads ====================

class PageFetchWorker(QThread):
    """Worker Thread لجلب الصفحات"""
    
    finished = Signal(dict)  # إشارة عند الانتهاء
    error = Signal(str)      # إشارة عند حدوث خطأ
    progress = Signal(str)   # رسائل التقدم
    
    def __init__(self, long_token: str):
        super().__init__()
        self.long_token = long_token
    
    def run(self):
        try:
            self.progress.emit('📥 جاري جلب الصفحات...')
            result = get_pages(self.long_token)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TokenExchangeWorker(QThread):
    """Worker Thread لتبديل التوكين القصير إلى طويل"""
    
    token_received = Signal(object)  # إشارة عند الحصول على التوكين
    error = Signal(str)              # إشارة عند حدوث خطأ
    
    def __init__(self, app_id: str, app_secret: str, short_token: str):
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.short_token = short_token
    
    def run(self):
        try:
            url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/oauth/access_token"
            params = {
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": self.short_token,
            }
            r = requests.get(url, params=params, timeout=FACEBOOK_API_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if "access_token" in data:
                self.token_received.emit(data)
            else:
                self.error.emit(json.dumps(data))
        except Exception as e:
            self.error.emit(str(e))


class AllPagesFetchWorker(QThread):
    """
    Worker Thread لجلب الصفحات من جميع التطبيقات
    يدعم جلب الصفحات الشخصية + Business Manager لكل تطبيق
    """
    
    pages_fetched = Signal(object)  # dict {app_name: {'my_pages': [...], 'business_managers': [...]}}
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, apps: list):
        """
        Args:
            apps: قائمة التطبيقات، كل تطبيق يحتوي على 'app_name' و 'long_lived_token'
        """
        super().__init__()
        self.apps = apps
    
    def run(self):
        result = {}
        try:
            for app in self.apps:
                name = app.get("app_name", "Unnamed")
                long_token = app.get("long_lived_token")
                
                if not long_token:
                    result[name] = {"error": "لا يوجد توكن طويل"}
                    continue
                
                self.progress.emit(f'📥 جاري جلب صفحات {name}...')
                
                try:
                    pages_data = get_pages(long_token)
                    result[name] = pages_data
                except Exception as e:
                    result[name] = {"error": str(e)}
            
            self.pages_fetched.emit(result)
            
        except Exception as e:
            self.error.emit(f"خطأ عام: {str(e)}")


# ==================== Singleton Instance ====================

_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """الحصول على مثيل مدير التوكينات"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
