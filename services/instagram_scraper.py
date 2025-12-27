from instagrapi import Client
from config import Config
import logging

logger = logging.getLogger(__name__)


class InstagramScraper:
    
    def __init__(self):
        self.client = None
        self.is_logged_in = False
    
    def login(self):
        try:
            if self.is_logged_in:
                logger.info("Instagram zaten giriş yapılmış")
                return True
            
            self.client = Client()
            self.client.login(Config.INSTAGRAM_USERNAME, Config.INSTAGRAM_PASSWORD)
            self.is_logged_in = True
            logger.info("Instagram login başarılı")
            return True
            
        except Exception as e:
            logger.error(f"Instagram login hatası: {e}")
            self.is_logged_in = False
            return False
    
    def post_photo(self, image_path: str, caption: str):
        try:
            if not self.is_logged_in:
                if not self.login():
                    return {"success": False, "error": "Login failed"}
            
            media = self.client.photo_upload(image_path, caption)
            
            logger.info(f"Instagram post başarılı: {media.pk}")
            
            return {
                "success": True,
                "media_id": media.pk,
                "media_code": media.code
            }
            
        except Exception as e:
            logger.error(f"Instagram post hatası: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def logout(self):
        try:
            if self.client and self.is_logged_in:
                self.client.logout()
                self.is_logged_in = False
                logger.info("Instagram logout başarılı")
        except Exception as e:
            logger.error(f"Instagram logout hatası: {e}")
