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
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
FEED_URL = os.getenv("FEED_URL", "https://tarjomaan.com/feed")
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://tarjomaan.com")

# چندتا پست در هر اجرا؟
DAILY_POST_COUNT = int(os.getenv("DAILY_POST_COUNT", "5"))

# فاصله بین پست‌ها (دقیقه) - برای طبیعی به نظر رسیدن
DELAY_BETWEEN_POSTS_MIN = int(os.getenv("DELAY_BETWEEN_POSTS_MIN", "30"))

# مسیر ذخیره تاریخچه پست‌ها (باید روی Volume دائمی باشه)
DATA_DIR = os.getenv("DATA_DIR", "/data")
POSTED_TRACKER_FILE = os.path.join(DATA_DIR, "posted_articles.json")

# چند صفحه از آرشیو سایت بخونیم (هر صفحه ~20 مقاله)
MAX_ARCHIVE_PAGES = int(os.getenv("MAX_ARCHIVE_PAGES", "15"))

# ==================== تابع‌ها ====================

def load_posted_articles():
    """لیست مقالاتی که قبلاً پست شدن رو بخون"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(POSTED_TRACKER_FILE):
            with open(POSTED_TRACKER_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()
    except Exception as e:
        logger.warning(f"⚠️ خطا در خواندن تاریخچه: {e}")
        return set()


def save_posted_article(link):
    """یک مقاله رو به لیست پست‌شده‌ها اضافه کن"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        posted = load_posted_articles()
        posted.add(link)
        with open(POSTED_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(posted), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"⚠️ خطا در ذخیره تاریخچه: {e}")


def get_all_articles_from_archive():
    """
    همه مقالات سایت (قدیمی + جدید) رو از WordPress REST API بگیر.
    برخلاف RSS که فقط چندتای آخر رو میده، این کل آرشیو رو میده.
    """
    logger.info("📚 دریافت آرشیو کامل مقالات...")
    all_articles = []
    api_url = f"{SITE_BASE_URL}/wp-json/wp/v2/posts"
    
    try:
        for page in range(1, MAX_ARCHIVE_PAGES + 1):
            logger.info(f"  📄 دریافت صفحه {page}/{MAX_ARCHIVE_PAGES}...")
            
            try:
                response = requests.get(
                    api_url,
                    params={"page": page, "per_page": 20, "_fields": "title,link,date,excerpt"},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=(10, 20)  # (connect timeout, read timeout)
                )
            except requests.exceptions.Timeout:
                logger.warning(f"  ⏱️ صفحه {page}: timeout - رد شدن")
                break
            except requests.exceptions.ConnectionError as ce:
                logger.warning(f"  🔌 صفحه {page}: خطای اتصال - {ce}")
                break
            
            logger.info(f"  ↳ status: {response.status_code}")
            
            if response.status_code != 200:
                logger.warning(f"  ⚠️ صفحه {page} status {response.status_code} - متوقف شد")
                logger.warning(f"  ⚠️ پاسخ: {response.text[:200]}")
                break
            
            posts = response.json()
            if not posts:
                logger.info(f"  ✅ صفحه {page} خالی بود - آرشیو تمام شد")
                break
            
            for post in posts:
                title = post.get("title", {}).get("rendered", "")
                link = post.get("link", "")
                excerpt = post.get("excerpt", {}).get("rendered", "")
                date = post.get("date", "")
                
                if title and link:
                    all_articles.append({
                        "title": re.sub('<[^<]+?>', '', title).strip(),
                        "link": link,
                        "summary": re.sub('<[^<]+?>', '', excerpt).strip(),
                        "published": date
                    })
        
        logger.info(f"✅ {len(all_articles)} مقاله در آرشیو پیدا شد")
        return all_articles
        
    except Exception as e:
        logger.error(f"❌ خطا در دریافت آرشیو: {e}")
        return []


def get_articles_to_post():
    """
    مقالاتی که هنوز پست نشدن رو انتخاب کن.
    از قدیمی‌ترین شروع میکنه تا backlog پاک بشه، بعد میرسه به جدیدترین‌ها.
    """
    all_articles = get_all_articles_from_archive()
    
    if not all_articles:
        logger.warning("⚠️ آرشیو در دسترس نبود - استفاده از RSS")
        feed = feedparser.parse(FEED_URL)
        all_articles = [{
            "title": e.title,
            "link": e.link,
            "summary": e.get("summary", ""),
            "published": e.get("published", "")
        } for e in feed.entries]
    
    posted = load_posted_articles()
    unposted = [a for a in all_articles if a["link"] not in posted]
    
    if not unposted:
        logger.info("✅ همه مقالات پست شدن! منتظر مقاله جدید...")
        return []
    
    # قدیمی‌ترین‌ها اول (برای پاک‌کردن backlog)
    unposted.sort(key=lambda a: a.get("published", ""))
    
    selected = unposted[:DAILY_POST_COUNT]
    logger.info(f"📋 {len(selected)} مقاله برای پست امروز انتخاب شد (از {len(unposted)} باقیمانده)")
    
    return selected


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
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_completion_tokens": 800,  # فضای کافی برای reasoning + جواب نهایی
            "reasoning_effort": "low",     # کم‌کردن فکرکردن داخلی تا توکن برای جواب بمونه
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
            summary = (result["choices"][0]["message"]["content"] or "").strip()
            
            if not summary:
                logger.warning("⚠️ Groq جواب خالی برگردوند - تلاش دوباره با تنظیمات متفاوت...")
                # تلاش دوم: بدون reasoning_effort و با توکن بیشتر
                retry_payload = {
                    "model": "openai/gpt-oss-120b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_completion_tokens": 1200,
                    "temperature": 0.7
                }
                retry_response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=retry_payload,
                    headers=headers,
                    timeout=30
                )
                if retry_response.status_code == 200:
                    retry_result = retry_response.json()
                    summary = (retry_result["choices"][0]["message"]["content"] or "").strip()
            
            if not summary:
                logger.error("❌ بعد از تلاش دوباره هم خلاصه خالی بود")
                return None
            
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
    """
    ساخت کارت گرافیکی با Pillow (بدون هیچ API خارجی)
    ✅ ۱۰۰٪ رایگان، بدون اکانت، بدون محدودیت، برای همیشه
    """
    try:
        logger.info("🎨 ساخت تصویر با Pillow (محلی - کاملاً رایگان)...")
        from PIL import Image, ImageDraw
        import hashlib

        W, H = 1080, 1080

        # ۵ تم رنگی متنوع
        palettes = [
            {'bg': [(30,30,60),(60,30,90)],   'accent': (150,100,255), 'text': (240,240,255)},
            {'bg': [(15,40,30),(20,70,50)],   'accent': (80,200,120),  'text': (220,255,230)},
            {'bg': [(50,20,20),(90,30,30)],   'accent': (255,100,80),  'text': (255,230,220)},
            {'bg': [(20,30,60),(20,60,90)],   'accent': (60,160,255),  'text': (220,235,255)},
            {'bg': [(40,30,10),(70,50,10)],   'accent': (255,180,40),  'text': (255,245,220)},
        ]

        # انتخاب تم بر اساس عنوان (هر مقاله تم ثابت داره)
        idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(palettes)
        pal = palettes[idx]

        # ساخت گرادیان پس‌زمینه
        img = Image.new('RGB', (W, H))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            r = int(pal['bg'][0][0]*(1-t) + pal['bg'][1][0]*t)
            g = int(pal['bg'][0][1]*(1-t) + pal['bg'][1][1]*t)
            b = int(pal['bg'][0][2]*(1-t) + pal['bg'][1][2]*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))

        # دایره‌های تزئینی (overlay شفاف)
        overlay = Image.new('RGBA', (W,H), (0,0,0,0))
        d2 = ImageDraw.Draw(overlay)
        ac = pal['accent']
        d2.ellipse([W-320,-120, W+80,280],   fill=(ac[0],ac[1],ac[2],45))
        d2.ellipse([-80,H-280, 280,H+80],    fill=(ac[0],ac[1],ac[2],30))
        d2.ellipse([W//2-200,H//2-200, W//2+200,H//2+200], fill=(ac[0],ac[1],ac[2],12))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)

        # خط عمودی تزئینی سمت چپ
        draw.rectangle([55, 55, 63, H-55], fill=pal['accent'])

        # نوار نام سایت بالا
        draw.rectangle([80, 78, 360, 118], fill=pal['accent'])
        draw.text((90, 83), 'tarjomaan.com', fill=(10,10,10))

        # شکستن عنوان به خطوط
        words = title.split()
        lines, cur = [], []
        for w in words:
            test = ' '.join(cur + [w])
            if len(test) > 20 and cur:
                lines.append(' '.join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(' '.join(cur))

        # رسم عنوان وسط
        line_h = 80
        total_h = len(lines) * line_h
        y0 = (H - total_h) // 2 - 20
        for i, ln in enumerate(lines[:7]):
            draw.text((80, y0 + i*line_h), ln, fill=pal['text'])

        # خط و متن پایین
        draw.rectangle([80, H-110, W-80, H-103], fill=pal['accent'])
        draw.text((80, H-88), 'ترجمان  |  روایت دانش', fill=pal['accent'])

        # ذخیره
        os.makedirs("/tmp", exist_ok=True)
        image_path = f"/tmp/post_image_{int(time.time())}.jpg"
        img.save(image_path, 'JPEG', quality=93)

        size_kb = os.path.getsize(image_path) // 1024
        logger.info(f"✅ تصویر ساخته شد: {image_path} ({size_kb} KB)")
        return image_path

    except Exception as e:
        logger.error(f"❌ خطا در ساخت تصویر: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def post_to_instagram(image_path, caption):
    """پست در اینستاگرام - image_path یه فایل محلیه (نه URL)"""
    try:
        logger.info("📸 تلاش برای پست در اینستاگرام...")
        
        try:
            from instagrapi import Client
            
            client = Client()
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            
            logger.info("📱 پست در اینستاگرام...")
            media = client.photo_upload(image_path, caption=caption)
            
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

def process_single_article(article, index, total):
    """یک مقاله رو کامل پردازش کن: متن → خلاصه → عکس → پست"""
    logger.info("\n" + "━" * 60)
    logger.info(f"📰 مقاله {index}/{total}: {article['title']}")
    logger.info("━" * 60)
    
    # متن کامل
    full_text = get_article_full_text(article['link'])
    if not full_text:
        full_text = article['summary']
    
    # خلاصه‌سازی
    summary = translate_and_summarize_with_groq(article['title'], full_text)
    if not summary:
        logger.error(f"❌ خلاصه‌سازی ناموفق برای: {article['title']}")
        return False
    
    # ساخت تصویر
    image_path = generate_image_with_flux(article['title'])
    if not image_path:
        logger.error(f"❌ ساخت تصویر ناموفق برای: {article['title']}")
        return False
    
    logger.info(f"\n📸 عکس ذخیره شد در: {image_path}")
    logger.info(f"\n📝 متن پست:\n{summary}\n")
    
    save_result(article['title'], summary, image_path)
    
    # پست در اینستاگرام
    posted = False
    if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
        posted = post_to_instagram(image_path, summary)
    else:
        logger.warning("⚠️ اطلاعات اینستاگرام تنظیم نشده")
    
    # پاک‌کردن فایل موقت عکس (دیگه لازم نیست)
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
    except Exception:
        pass
    
    # این مقاله رو به‌عنوان "پست‌شده" ثبت کن - حتی اگر پست در اینستاگرام
    # ناموفق بود ولی خلاصه/عکس ساخته شد (برای جلوگیری از تکرار بی‌نهایت)
    save_posted_article(article['link'])
    
    return posted


def main():
    logger.info("=" * 60)
    logger.info("🚀 شروع سیستم اتوماتیک Tarjomaan")
    logger.info(f"🎯 هدف: {DAILY_POST_COUNT} پست در این اجرا")
    logger.info("=" * 60)
    
    # دیباگ: ببینیم دقیقاً چه متغیرهایی به کانتینر رسیدن (بدون نشون‌دادن مقدار واقعی)
    logger.info("🔍 بررسی متغیرهای محیطی:")
    for var_name in ["GROQ_API_KEY", "INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD", "FEED_URL"]:
        val = os.environ.get(var_name)
        if val:
            logger.info(f"  ✅ {var_name}: موجوده (طول={len(val)}, شروع با: {val[:5]}...)")
        else:
            logger.info(f"  ❌ {var_name}: موجود نیست")
    
    logger.info("=" * 60)
    
    if not GROQ_API_KEY:
        logger.error("❌ GROQ_API_KEY تنظیم نشده!")
        return
    
        return
    
    articles = get_articles_to_post()
    
    if not articles:
        logger.info("ℹ️ مقاله جدیدی برای پست وجود نداره")
        return
    
    success_count = 0
    
    for i, article in enumerate(articles, start=1):
        success = process_single_article(article, i, len(articles))
        if success:
            success_count += 1
        
        if i < len(articles):
            if success:
                # فقط بعد از پست موفق صبر کن (برای طبیعی به‌نظررسیدن در اینستاگرام)
                wait_seconds = DELAY_BETWEEN_POSTS_MIN * 60
                logger.info(f"⏳ صبر {DELAY_BETWEEN_POSTS_MIN} دقیقه تا پست بعدی...")
                time.sleep(wait_seconds)
            else:
                # اگه این مقاله fail شد (نه به‌خاطر اینستاگرام بلکه خلاصه/عکس)
                # نیازی به صبر طولانی نیست - فقط یه مکث کوتاه و برو سراغ بعدی
                logger.info("⏳ این مقاله fail شد - بدون صبر طولانی میریم سراغ بعدی...")
                time.sleep(5)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ پایان اجرا: {success_count}/{len(articles)} پست موفق")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
