import os
import time
import requests
import logging
from PIL import Image
from instagrapi import Client
from groq import Groq
import config

# Logging Ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API İstemcileri
cl = Client()
# Config dosyasındaki değişkenleri güvenli şekilde alalım
try:
    groq_client = Groq(api_key=config.GROQ_API_KEY)
except AttributeError:
    logger.error("GROQ_API_KEY bulunamadı!")

def init_instagram():
    """Instagram'a session dosyası ile güvenli giriş yapar."""
    try:
        if not cl.user_id:
            if os.path.exists("session.json"):
                logger.info("Session dosyası bulundu, oturum yükleniyor...")
                cl.load_settings("session.json")
                cl.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)
            else:
                logger.info("Session dosyası yok, normal giriş deneniyor...")
                cl.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)
            logger.info("Instagram girişi başarılı!")
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")

def get_latest_news():
    """NewsData.io üzerinden güncel haberleri çeker."""
    url = f"https://newsdata.io/api/1/news?apikey={config.NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
    return None

def create_instagram_post(news_item):
    """Haber görseli ve logoyu birleştirir."""
    img_url = news_item.get("image_url")
    if not img_url: return None

    img_path = "news_image.jpg"
    final_path = "final_post.jpg"
    
    try:
        # Görseli indir
        with open(img_path, "wb") as f:
            f.write(requests.get(img_url).content)

        # Görsel işleme
        img = Image.open(img_path).convert("RGB")
        img = img.resize((1080, 1350)) # Instagram Portrait

        # Logo ekleme
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            logo.thumbnail((200, 200))
            img.paste(logo, (50, 50), logo)

        img.save(final_path, "JPEG", quality=95)
        return final_path
    except Exception as e:
        logger.error(f"Görsel oluşturma hatası: {e}")
        return None

def generate_ai_caption(title, description):
    """Groq AI ile açıklama oluşturur."""
    try:
        prompt = f"Şu haberi etkileyici bir Instagram gönderisi haline getir:\nBaşlık: {title}\nDetay: {description}\nKısa, çarpıcı ve emojili olsun."
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile",
        )
        return chat_completion.choices[0].message.content
    except Exception:
        return f"{title}\n\nDetaylar için takipte kalın! #haber"

def job():
    """Haber paylaşım görevi."""
    logger.info("Süreç başlatılıyor...")
    news = get_latest_news()
    
    if news:
        init_instagram()
        image_path = create_instagram_post(news)
        
        if image_path:
            caption = generate_ai_caption(news['title'], news.get('description', ''))
            try:
                cl.photo_upload(image_path, caption)
                logger.info("Instagram paylaşımı başarıyla yapıldı!")
            except Exception as e:
                logger.error(f"Paylaşım hatası: {e}")
    else:
        logger.warning("Yeni haber bulunamadı.")

if __name__ == "__main__":
    while True:
        job()
        logger.info("4 saat bekleniyor (Günde 6 haber ayarı)...")
        time.sleep(14400) # 4 saat
