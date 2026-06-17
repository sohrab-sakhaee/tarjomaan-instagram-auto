#!/usr/bin/env python3
"""
سیستم اتوماتیک اینستاگرام - Tarjomaan
خلاصه‌سازی + عکس‌سازی + پست‌کردن
"""

import os
import requests
import feedparser
import time
import json
import logging
from datetime import datetime
import re

# لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== تنظیمات ====================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REPLICATE_TOKEN = os.getenv("REPLICATE_TOKEN")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
FEED_URL = os.getenv("FEED_URL", "https://tarjomaan.com/feed")

# ==================== تابع‌ها ====================

def get_latest_article():
    """آخرین مقاله از RSS فید"""
    try:
        logger.info("📡 دریافت مقالات...")
        feed = feedparser.parse(FEED_URL)
        
        if not feed.entries:
            logger.warning("❌ مقاله‌ای پیدا نشد")
            return None
        
        article = feed.entries[0]
        return {
            "title": article.title,
            "link": article.link,
            "summary": article.get("summary", ""),
            "published": article.get("published", "")
        }
    except Exception as e:
        logger.error(f"❌ خطا در دریافت مقالات: {e}")
        return None


def get_article_full_text(url):
    """متن کامل مقاله"""
    try:
        logger.info("📄 دریافت متن کامل...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        text = response.text
        
        # استخراج پاراگراف‌ها
        paragraphs = re.findall(r'<p[^>]*>([^<]+)</p>', text)
        full_text = '\n'.join(paragraphs[:5])
        
        return full_text[:2000]
    except Exception as e:
        logger.warning(f"⚠️ خطا در دریافت متن: {e}")
        return ""


def translate_and_summarize_with_groq(title, content):
    """ترجمه و خلاصه‌سازی با Groq"""
    try:
        logger.info("🤖 Groq: ترجمه و خلاصه‌سازی...")
        
        prompt = f"""شما یک مترجم و خلاصه‌کننده حرفه‌ای فارسی هستید.

عنوان مقاله:
{title}

متن مقاله:
{content}

کارهایی که باید انجام بدی:

1. اگر متن انگلیسی است: ترجمه کن به فارسی
2. خلاصه‌ای ۲-۳ سطر از مقاله بنویس (عامیانه و طبیعی - انگار برای دوست داری توضیح میدی)
3. ۳-۴ هشتگ مرتبط اضافه کن

فقط خلاصه + هشتگ‌ها برگردان، چیز دیگری نه.
"""

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mixtral-8x7b-32768",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result["choices"][0]["message"]["content"]
            logger.info(f"✅ خلاصه آماده:\n{summary}\n")
            return summary
        else:
            logger.error(f"❌ Groq Error: {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return None
        
    except Exception as e:
        logger.error(f"❌ خطا در Groq: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def generate_image_with_flux(title):
    """ساخت عکس با Flux"""
    try:
        logger.info("🎨 ساخت تصویر با Flux...")
        
        prompt = f"""Modern illustration, 1080x1080px, Instagram post style, professional design:
Title: {title}
Persian/Iranian aesthetics, clean, artistic, vibrant colors, modern layout.
Text: Not needed - just visual design."""

        headers = {
            "Authorization": f"Token {REPLICATE_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "version": "3f20e3d61ba7502ccbc75a45611e23e1412bde0d88e2e10fce371a493e11d148",
            "input": {
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "num_inference_steps": 25,
                "guidance": 3.5
            }
        }
        
        logger.info("⏳ ارسال درخواست به Flux...")
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 201:
            logger.error(f"❌ خطای Flux: {response.status_code}")
            return None
        
        prediction = response.json()
        prediction_id = prediction["id"]
        logger.info(f"⏳ ID: {prediction_id} - صبر برای نتیجه...")
        
        # پولینگ
        max_attempts = 240  # 20 دقیقه
        for attempt in range(max_attempts):
            time.sleep(5)
            
            response = requests.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers=headers,
                timeout=10
            )
            
            prediction = response.json()
            status = prediction.get("status", "unknown")
            
            if status == "succeeded":
                image_url = prediction["output"][0]
                logger.info(f"✅ تصویر آماده!\n🔗 {image_url}")
                return image_url
            
            elif status == "failed":
                logger.error(f"❌ خطا: {prediction.get('error', 'Unknown')}")
                return None
            
            if attempt % 12 == 0:  # هر دقیقه یک بار
                logger.info(f"  ⏳ تلاش {attempt//12+1}... (Status: {status})")
        
        logger.error("❌ timeout - خیلی طول کشید")
        return None
        
    except Exception as e:
        logger.error(f"❌ خطا در Flux: {e}")
        return None


def post_to_instagram(image_url, caption):
    """پست در اینستاگرام"""
    try:
        logger.info("📸 تلاش برای پست در اینستاگرام...")
        
        # سعی کن با Instagrapi
        try:
            from instagrapi import Client
            
            client = Client()
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            
            # دانلود عکس
            logger.info("⏳ دانلود عکس...")
            img_response = requests.get(image_url, timeout=15)
            img_path = "/tmp/instagram_post.jpg"
            with open(img_path, 'wb') as f:
                f.write(img_response.content)
            
            # پست
            logger.info("📱 پست در اینستاگرام...")
            media = client.photo_upload(img_path, caption=caption)
            
            logger.info(f"✅ پست شد! ID: {media.id}")
            return True
            
        except ImportError:
            logger.warning("⚠️ Instagrapi نصب نشده - فقط نتیجه نشان داده میشه")
            return False
        except Exception as e:
            logger.warning(f"⚠️ خطا در پست‌کردن: {e}")
            logger.info("💡 حتماً VPN فعال کن یا دستی پست کن")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا: {e}")
        return False


def save_result(article_title, summary, image_url):
    """نتیجه رو ذخیره کن"""
    try:
        result = {
            "timestamp": datetime.now().isoformat(),
            "title": article_title,
            "summary": summary,
            "image_url": image_url
        }
        
        # ذخیره در فایل JSON
        results_file = "results.json"
        results = []
        
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
        
        results.append(result)
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ نتیجه ذخیره شد")
        
    except Exception as e:
        logger.warning(f"⚠️ خطا در ذخیره: {e}")


# ==================== Main ====================

def main():
    logger.info("=" * 60)
    logger.info("🚀 شروع سیستم اتوماتیک Tarjomaan")
    logger.info("=" * 60)
    
    # بررسی API Keys
    if not GROQ_API_KEY or not REPLICATE_TOKEN:
        logger.error("❌ API Keys تنظیم نشده‌اند!")
        return
    
    # مرحله ۱: دریافت مقاله
    article = get_latest_article()
    if not article:
        logger.warning("❌ مقاله‌ای پیدا نشد")
        return
    
    logger.info(f"📰 عنوان: {article['title']}\n")
    
    # مرحله ۲: دریافت متن کامل
    full_text = get_article_full_text(article['link'])
    if not full_text:
        full_text = article['summary']
    
    # مرحله ۳: خلاصه‌سازی
    summary = translate_and_summarize_with_groq(article['title'], full_text)
    
    if not summary:
        logger.error("❌ خلاصه‌سازی ناموفق")
        return
    
    # مرحله ۴: ساخت تصویر
    image_url = generate_image_with_flux(article['title'])
    
    if not image_url:
        logger.error("❌ ساخت تصویر ناموفق")
        return
    
    # مرحله ۵: نتیجه
    logger.info("\n" + "=" * 60)
    logger.info("✅ تمام شد!")
    logger.info("=" * 60)
    logger.info(f"\n📸 عکس:\n{image_url}")
    logger.info(f"\n📝 متن پست:\n{summary}")
    logger.info("=" * 60)
    
    # مرحله ۶: ذخیره و پست
    save_result(article['title'], summary, image_url)
    
    # سعی برای پست در اینستاگرام
    if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        post_to_instagram(image_url, summary)
    else:
        logger.warning("⚠️ اطلاعات اینستاگرام تنظیم نشده")
    
    logger.info("\n✅ پایان اجرا")


if __name__ == "__main__":
    main()
