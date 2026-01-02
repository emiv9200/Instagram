import os
import logging
import requests
import pytz
import threading
import time
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from groq import Groq
from instagrapi import Client
from PIL import Image, ImageEnhance

# 1. Loglama ve Flask Ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 2. Yapılandırma (Render Environment Variables'dan çekilir)
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Istanbul')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

# Instagram Global Client
cl = Client()

def init_instagram():
    """Instagram oturumu açar veya mevcut oturumu kontrol eder."""
    try:
        if not cl.user_id:
            logger.info("Instagram girişi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            logger.info("Instagram girişi başarılı!")
    except Exception as e:
        logger.error(f"Instagram giriş hatası: {e}")

def process_image(input_path, output_path):
    """Görsele logo ekler ve hafif karartma (filigran) uygular."""
    try:
        base_image = Image.open(input_path).convert("RGBA")
        
        # Hafif karartma (Özgünlük için)
        enhancer = ImageEnhance.Brightness(base_image)
        base_image = enhancer.enhance(0.85)

        # Logoyu ekle (Dosya adının logo.png olduğundan emin ol)
        if os.path.exists("logo.png"):
            logo = Image.open("logo.png").convert("RGBA")
            base_w, base_h = base_image.size
            
            # Logoyu genişliğin %15'ine boyutlandır
            new_logo_w = int(base_w * 0.15)
            w_percent = (new_logo_w / float(logo.size[0]))
            new_logo_h = int((float(logo.size[1]) * float(w_percent)))
            logo = logo.resize((new_logo_w, new_logo_h), Image.Resampling.LANCZOS)
            
            # Sağ alt köşe (25px boşluk)
            position = (base_w - new_logo_w - 25, base_h - new_logo_h - 25)
            base_image.paste(logo, position, logo)
        
        final_image = base_image.convert("RGB")
        final_image.save(output_path, "JPEG", quality=90)
        return True
    except Exception as e:
        logger.error(f"Görsel işleme hatası: {e}")
        return False

def create_caption(news_item):
    """Groq AI kullanarak haber başlığı ve açıklamasından Instagram postu oluşturur."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"Aşağıdaki haberi Instagram için dikkat çekici, kısa bir bülten haline getir. En sona uygun hashtagler ekle.\nBaşlık: {news_item['title']}\nDetay: {news_item['description']}"
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq Caption hatası: {e}")
        return f"{news_item['title']}\n\nDetaylar için takipte kalın! #haber"

def post_to_instagram():
    """Haber çekme, düzenleme ve paylaşma ana döngüsü."""
    logger.info("Otomatik paylaşım süreci başladı...")
    try:
        init_instagram()
        
        # Haber Çek (NewsAPI TR)
        news_url = f'https://newsapi.org/v2/top-headlines?country=tr&apiKey={NEWS_API_KEY}'
        res = requests.get(news_url).json()
        
        if res.get('articles'):
            article = res['articles'][0] # En taze haberi al
            img_url = article.get('urlToImage')
            
            if img_url:
                # Görseli indir ve işle
                with open("raw.jpg", "wb") as f:
                    f.write(requests.get(img_url).content)
                
                if process_image("raw.jpg", "final.jpg"):
                    caption = create_caption(article)
                    cl.photo_upload("final.jpg", caption)
                    logger.info("Paylaşım başarıyla yapıldı!")
                
                # Temizlik
                for f in ["raw.jpg", "final.jpg"]:
                    if os.path.exists(f): os.remove(f)
            else:
                logger.warning("Haberin görseli yok, atlanıyor.")
    except Exception as e:
        logger.error(f"Paylaşım döngüsü hatası: {e}")

# 3. Zamanlayıcı (Her 2 saatte bir)
scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))
scheduler.add_job(post_to_instagram, 'interval', hours=2)
scheduler.start()

# 4. Web Sunucu Yolları
@app.route('/')
def home():
    return f"Bot Aktif. Sistem Saati: {datetime.now()}"

@app.route('/health')
def health():
    return jsonify(status="up"), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
