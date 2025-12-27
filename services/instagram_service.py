from models.instagram_models import InstagramModel
from services.instagram_scraper import InstagramScraper
from groq import Groq
from config import Config
import logging
import requests
import os

logger = logging.getLogger(__name__)

groq_client = Groq(api_key=Config.GROQ_API_KEY)


class InstagramService:
    
    @staticmethod
    def generate_summary(title: str, content: str) -> str:
        try:
            prompt = f"""
Sen profesyonel bir sosyal medya editörüsün. Verilen haberi Instagram için özetle.

HABER:
Başlık: {title}
İçerik: {content}

KRİTİK KURALLAR:
1. MİNİMUM 200 karakter, MAKSIMUM 250 karakter kullan.
2. Detaylı ve bilgilendirici ol. Haberin TÜM önemli detaylarını ekle.
3. Asla 280 karakteri geçme.
4. Clickbait yapma, haberin özünü ver.
5. Sonuna MUTLAKA 3-4 ilgili hashtag ekle (#Teknoloji #YapayZeka #AI gibi).
6. Yanıt olarak SADECE özet metnini ver, başka hiçbir şey yazma.
"""
            
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Groq AI özet oluşturdu: {len(summary)} karakter")
            return summary
            
        except Exception as e:
            logger.error(f"Groq AI özet hatası: {e}")
            return None
    
    @staticmethod
    def download_image(url: str, save_path: str = "temp_image.jpg") -> str:
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Görsel indirildi: {save_path}")
                return save_path
            else:
                logger.error(f"Görsel indirme başarısız: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Görsel indirme hatası: {e}")
            return None
    
    @staticmethod
    def post_to_instagram(post_id: int):
        try:
            posts = InstagramModel.get_unposted_posts(limit=1)
            
            if not posts:
                return {"success": False, "error": "Post bulunamadı"}
            
            post = posts[0]
            
            if not post.get('summary'):
                return {"success": False, "error": "Özet yok"}
            
            if not post.get('image_url'):
                return {"success": False, "error": "Görsel yok"}
            
            if not InstagramModel.can_post_today():
                return {"success": False, "error": "Günlük limit doldu"}
            
            image_path = InstagramService.download_image(post['image_url'])
            
            if not image_path:
                return {"success": False, "error": "Görsel indirilemedi"}
            
            scraper = InstagramScraper()
            
            result = scraper.post_photo(image_path, post['summary'])
            
            if os.path.exists(image_path):
                os.remove(image_path)
            
            if result.get('success'):
                InstagramModel.mark_as_posted(post_id)
                InstagramModel.increment_stats()
                
                return {
                    "success": True,
                    "media_id": result.get('media_id'),
                    "remaining": InstagramModel.get_stats()["daily_limit"] - InstagramModel.get_stats()["today_posts"]
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Instagram post hatası: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def auto_post_scheduler():
        try:
            if not InstagramModel.can_post_today():
                logger.info("Instagram günlük limit doldu")
                return
            
            posts = InstagramModel.get_unposted_posts(limit=1)
            
            if not posts:
                logger.info("Paylaşılacak post yok")
                return
            
            post = posts[0]
            
            result = InstagramService.post_to_instagram(post['id'])
            
            if result.get('success'):
                logger.info(f"Instagram otomatik post başarılı: {post['id']}")
            else:
                logger.error(f"Instagram otomatik post başarısız: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Auto post scheduler hatası: {e}")
