"""
Thread Classes for Page Management Application

This module provides background thread classes for non-blocking operations.
"""

import json
import requests
from PySide6.QtCore import QThread, Signal
from core.constants import FACEBOOK_API_VERSION, FACEBOOK_API_TIMEOUT
from services.token_manager import get_pages


class TokenExchangeThread(QThread):
    """Thread منفصل لجلب التوكن الطويل بدون تجميد الواجهة"""
    # استخدام اسم مختلف لتجنب تعارض مع QThread.finished
    token_received = Signal(object)
    error = Signal(str)

    def __init__(self, app_id: str, app_secret: str, short_token: str):
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret
        self.short_token = short_token

    # رسالة الخطأ الافتراضية عند عدم العثور على التوكن
    DEFAULT_TOKEN_NOT_FOUND_MSG = 'لم يتم العثور على التوكن في الاستجابة'
    
    def _extract_fb_error_message(self, data: dict, fallback: str = None) -> str:
        """
        استخراج رسالة الخطأ من استجابة Facebook API.
        
        Args:
            data: قاموس الاستجابة من Facebook API
            fallback: رسالة بديلة في حالة عدم وجود رسالة خطأ
        
        Returns:
            رسالة الخطأ المستخرجة أو الرسالة البديلة
        """
        if fallback is None:
            fallback = self.DEFAULT_TOKEN_NOT_FOUND_MSG
        error_info = data.get('error', {})
        if isinstance(error_info, dict):
            return error_info.get('message', fallback)
        return fallback
    
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
                # استخراج رسالة الخطأ من الاستجابة بدون عرض البيانات الحساسة
                error_msg = self._extract_fb_error_message(data)
                self.error.emit(error_msg)
        except requests.exceptions.Timeout:
            self.error.emit('انتهت مهلة الاتصال بالخادم')
        except requests.exceptions.ConnectionError:
            self.error.emit('فشل الاتصال بالخادم - تحقق من اتصالك بالإنترنت')
        except requests.exceptions.HTTPError as e:
            # محاولة استخراج رسالة خطأ من استجابة Facebook
            try:
                error_data = e.response.json()
                error_msg = self._extract_fb_error_message(error_data, str(e))
            except (ValueError, json.JSONDecodeError):
                error_msg = str(e)
            self.error.emit(error_msg)
        except Exception as e:
            self.error.emit(str(e))


class FetchPagesThread(QThread):
    """Thread لجلب الصفحات من جميع التطبيقات بدون تجميد الواجهة"""
    # استخدام اسم مختلف لتجنب تعارض مع QThread.finished
    pages_fetched = Signal(object)  # dict {app_name: {'my_pages': [...], 'business_managers': [...]}}
    error = Signal(str)
    progress = Signal(str)  # رسائل التقدم

    def __init__(self, apps: list):
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
                    # استخدام الدالة الجديدة من token_manager التي تدعم Business Manager
                    pages_data = get_pages(long_token)
                    
                    # إنشاء نسخ جديدة من البيانات مع إضافة اسم التطبيق (تجنب تعديل الأصل)
                    enriched_data = {
                        'my_pages': [],
                        'business_managers': []
                    }
                    
                    for page in pages_data.get('my_pages', []):
                        enriched_page = dict(page)  # نسخة جديدة
                        enriched_page['app_name'] = name
                        enriched_data['my_pages'].append(enriched_page)
                    
                    for bm in pages_data.get('business_managers', []):
                        enriched_bm = {
                            'bm_name': bm.get('bm_name', 'Unknown BM'),
                            'bm_id': bm.get('bm_id'),
                            'pages': []
                        }
                        for page in bm.get('pages', []):
                            enriched_page = dict(page)  # نسخة جديدة
                            enriched_page['app_name'] = name
                            enriched_page['bm_name'] = enriched_bm['bm_name']
                            enriched_bm['pages'].append(enriched_page)
                        enriched_data['business_managers'].append(enriched_bm)
                    
                    result[name] = enriched_data
                        
                except Exception as e:
                    # معالجة أي استثناء غير متوقع لهذا التطبيق
                    result[name] = {"error": str(e)}
            
            self.pages_fetched.emit(result)
            
        except Exception as e:
            self.error.emit(f"خطأ عام: {str(e)}")


__all__ = [
    'TokenExchangeThread',
    'FetchPagesThread',
]
