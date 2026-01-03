import os
import time
import requests
import logging
import threading
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask
from datetime import datetime
import pytz

# Yardımcı fonksiyonları utils.py dosyasından alıyoruz
from utils import remove_html_tags, truncate_text

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Panel durum değişkenleri
instagram_status = "Başlatılmadı"
last_update = "Henüz işlem yapılmadı"

# Render Environment Variables
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
NEWSDATA_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

cl = Client()
groq_client = Groq(api_key=GROQ_API_KEY)

@app.route('/')
def health_check():
    # Tarayıcıda botun durumunu gösteren panel
    return f"""
    <html>
        <head><title>Bot Durum Paneli</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1>Bot Durum Paneli</h1>
            <p><strong>Bot Durumu:</strong> Aktif ✅</p>
            <p><strong>Instagram Durumu:</strong> {instagram_status}</p>
            <p><strong>Son İşlem Zamanı:</strong> {last_update}</p>
            <hr>
            <p><a href="/test-run" style="padding: 10px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">Hemen Test Et (Manuel Çalıştır)</a></p>
            <p><small>Not: Manuel çalıştırma sonrası sayfayı yenileyin.</small></p>
        </body>
    </html>
    """, 200

@app.route('/test-run')
def test_run():
    # Botu 4 saat beklemeden manuel tetikleyen rota
    thread = threading.Thread(target=job)
    thread.start()
    return "Bot tetiklendi! Lütfen 10 saniye sonra ana sayfayı yenileyin.", 200

def init_instagram():
    global instagram_status
    try:
        session_file = "session.json" #
        if os.path.exists(session_file):
            logger.info("Session dosyası bulundu, yükleniyor...")
            cl.load_settings(session_file)
            try:
                cl.get_timeline_feed() 
                logger.info("Oturum geçerli.")
                instagram_status = "Bağlı (Session) ✅"
                return
            except Exception:
                logger.warning("Session geçersiz.")

        if not cl.user_id:
            logger.info("Sıfırdan giriş yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file)
            instagram_status = "Bağlı (Yeni Giriş) ✅"
    except Exception as e:
        error_msg = str(e)
        instagram_status = f"Hata: {error_msg[:50]} ❌"
        logger.error(f"Instagram giriş hatası: {e}")

def get_latest_news():
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q=haber&country=tr&language=tr"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        logger.error(f"Haber çekme hatası: {e}")
    return None

def create_instagram_post(news_item):
    img_url = news_item.get("image_url")
    if not img_url: return None
    img_path = "news_image.jpg"
    final_path = "final_post.jpg"
    try:
        with open(img_path, "wb") as f:
            f.write(requests.get(img_url).content)
        img = Image.open(img_path).convert("RGB")
        img = img.resize((1080, 1350))
        if os.path.exists("logo.png"): #
            logo = Image.open("logo.png").convert("RGBA")
            logo.thumbnail((200, 200))
            img.paste(logo, (50, 50), logo)
        img.save(final_path, "JPEG", quality=95)
        return final_path
    except Exception as e:
        logger.error(f"Görsel oluşturma hatası: {e}")
        return None

def generate_ai_caption(title, description):
    try:
        # Metinleri temizle
        clean_title = remove_html_tags(title)
        clean_desc = truncate_text(remove_html_tags(description or ""), max_length=400)
        
        prompt = f"Şu haberi etkileyici bir Instagram gönderisi yap:\nBaşlık: {clean_title}\nDetay: {clean_desc}\nKısa ve emojili olsun."
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192", # Güncel stabil model
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API hatası: {e}")
        return f"{title}\n\nDetaylar için takipte kalın! #haber"

def job():
    global last_update
    tz = pytz.timezone('Europe/Istanbul')
    last_update = datetime.now(tz).strftime('%d/%m/%Y %H:%M:%S')
    
    logger.info(f"İşlem başlatıldı: {last_update}")
    news = get_latest_news()
    if news:
        init_instagram()
        if "Bağlı" in instagram_status:
            image_path = create_instagram_post(news)
            if image_path:
                caption = generate_ai_caption(news['title'], news.get('description', ''))
                try:
                    cl.photo_upload(image_path, caption)
                    logger.info("Paylaşım başarılı!")
                except Exception as e:
                    logger.error(f"Paylaşım hatası: {e}")
    else:
        logger.warning("Yeni haber bulunamadı.")

def run_bot_loop():
    while True:
        job()
        logger.info("4 saatlik uyku moduna geçiliyor...")
        time.sleep(14400)

if __name__ == "__main__":
    # Bot döngüsünü ayrı bir kanalda başlat
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
