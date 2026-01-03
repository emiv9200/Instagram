import os
import time
import requests
import logging
import threading
import re
from PIL import Image
from instagrapi import Client
from groq import Groq
from flask import Flask
from datetime import datetime
import pytz

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

# --- TEMİZLEME FONKSİYONLARI (Artık app.py içinde, hata vermez) ---
def remove_html_tags(text):
    if not text: return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(clean.split()).strip()

def truncate_text(text, max_length=400):
    if not text or len(text) <= max_length: return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."

# --- WEB PANEL YOLLARI ---
@app.route('/')
def health_check():
    return f"""
    <html>
        <head><title>Bot Durum Paneli</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6;">
            <h1 style="color: #333;">Bot Durum Paneli</h1>
            <p><strong>Bot Durumu:</strong> Aktif ✅</p>
            <p><strong>Instagram Durumu:</strong> {instagram_status}</p>
            <p><strong>Son İşlem Zamanı:</strong> {last_update}</p>
            <hr>
            <a href="/test-run" style="display: inline-block; padding: 12px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Hemen Test Et (Manuel Çalıştır)</a>
            <p><small style="color: #666;">Not: Tıkladıktan sonra 15 saniye bekleyip sayfayı yenileyin.</small></p>
        </body>
    </html>
    """, 200

@app.route('/test-run')
def test_run():
    thread = threading.Thread(target=job)
    thread.start()
    return "Bot tetiklendi! Panelden durumu takip edin.", 200

# --- BOT MANTIĞI ---
def init_instagram():
    global instagram_status
    try:
        session_file = "session.json"
        if os.path.exists(session_file):
            logger.info("Session dosyası yükleniyor...")
            cl.load_settings(session_file)
            try:
                cl.get_timeline_feed() 
                instagram_status = "Bağlı (Session) ✅"
                return
            except Exception:
                logger.warning("Session geçersiz.")

        if not cl.user_id:
            logger.info("Giriş denemesi yapılıyor...")
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file)
            instagram_status = "Bağlı (Yeni Giriş) ✅"
    except Exception as e:
        error_msg = str(e)
        instagram_status = f"Hata: {error_msg[:60]}... ❌"
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
        r = requests.get(img_url, timeout=15)
        with open(img_path, "wb") as f:
            f.write(r.content)
        img = Image.open(img_path).convert("RGB")
        img = img.resize((1080, 1350))
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
    try:
        clean_title = remove_html_tags(title)
        clean_desc = truncate_text(remove_html_tags(description or ""), 400)
        prompt = f"Haber: {clean_title}\nDetay: {clean_desc}\nInstagram için kısa, etkileyici ve emojili açıklama yaz."
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception:
        return f"{title}\n\nTakipte kalın! #haber"

def job():
    global last_update
    tz = pytz.timezone('Europe/Istanbul')
    last_update = datetime.now(tz).strftime('%H:%M:%S')
    
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

def run_bot_loop():
    while True:
        job()
        time.sleep(14400) # 4 saat

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
