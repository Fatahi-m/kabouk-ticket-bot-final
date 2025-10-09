import logging
import qrcode
from PIL import Image
from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackContext,
    MessageHandler, filters, CallbackQueryHandler,
    # 🆕 کلاس برای هندل کردن خطاها
    ContextTypes
)
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from database import init_db, get_db, User, Event, Ticket
import os
from collections import defaultdict


# 🔧 تنظیمات اولیه
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "922402042"))

# 🆕 آی‌دی کانال‌های اجباری (تنظیمات خود را وارد کنید)
TELEGRAM_CHANNEL_ID = -1003098867362
TELEGRAM_CHANNEL_USERNAME = "kabouk_events"
WHATSAPP_CHANNEL_LINK = "https://whatsapp.com/channel/0029Vb6Ahlm7DAWtIN4bbO30"

# --- لینک‌های اجتماعی ---
SOCIAL_MEDIA_LINKS = [
    {"name": "📷 Instagram", "url": "https://www.instagram.com/kabouk_events?igsh=ZnBwbHppcWdnazl5"},
    {"name": "📢 WhatsApp Channel", "url": WHATSAPP_CHANNEL_LINK},
]

# --- لینک‌های تماس ---
CONTACT_LINKS = [
    {"name": "📞 WhatsApp Support", "url": "https://wa.me/message/E4ABKNYYTWHOJ1"},
    {"name": "📨 Telegram Admin", "url": "https://t.me/Fetahi_M"},
]

# 🌍 دایرکتوری زبان‌ها (Language Packs)
LANGUAGES = {
    "de": {
        "welcome_message": "Willkommen zum *Kabouk-Ticket-Bot*!\nWas möchtest du tun?",
        "start_message_unsubscribed": "Hallo! Um unseren Ticket-Service nutzen zu können, musst du unseren Kanälen beitreten.",
        "join_telegram_button": "Telegram Kanal beitreten",
        "join_whatsapp_button": "WhatsApp Kanal beitreten",
        "check_subscription_button": "Mitgliedschaft prüfen und fortfahren",
        "thank_you_for_joining": "Vielen Dank für den Beitritt! Du kannst den Bot jetzt nutzen.",
        "not_subscribed_error": "Es tut uns leid, aber wir können deine Mitgliedschaft nicht bestätigen. Bitte trete den Kanälen bei und versuche es erneut.",

        "ticket_buy_button": "🎫 Ticket kaufen",
        "next_event_button": "🎶 Nächstes Event",
        "past_events_button": "🗓️ Vergangene Events",
        "contact_button": "📱 Kontakt",
        "social_media_button": "📢 Social Media",
        "language_select_button": "🌐 Sprache ändern",

        "no_events_available": "Aktuell sind keine Events zum Kauf verfügbar.",
        "event_caption_format": "*{name}*\n🗓️ Datum: {date}\n📍 Ort: {location}\n⏰ Uhrzeit: {time} Uhr\n💰 Preis: {price} EUR\n\n*{description}*",
        "event_caption_no_poster": "(Kein Poster verfügbar)",
        "buy_ticket_button_text": "🎫 Jetzt Ticket(s) kaufen",
        "error_loading_poster": "(Fehler beim Laden des Posters)",

        "no_upcoming_events": "Es sind keine zukünftigen Events geplant.",
        "upcoming_events_title": "*Unsere kommenden Events:*\n",
        "past_events_title": "*Ein Blick zurück auf unsere unvergesslichen Momente:*\n",
        "no_past_events": "Es gibt noch keine vergangenen Events zum Anzeigen.",
        "event_caption_past": "*{name}*\n🗓️ Datum: {date}\n📍 Ort: {location}\n*{description}*\n\n*(Dieses Event ist bereits vorbei)*",
        "no_poster_past_event": "(Kein Poster verfügbar für dieses vergangene Event)",

        "contact_prompt": "Wie möchtest du uns erreichen?",
        "social_media_prompt": "Folge uns auf unseren Social Media Kanälen:",

        "payment_received_text": "Zahlung bestätigen",
        "no_pending_payment": "⚠️ Keine offenen Zahlungsanfragen gefunden. Bitte zuerst Ticket kaufen.",
        "payment_request_admin": "💰 Neue Zahlungsanfrage:\nName: {name}\nUsername: @{username}\nUserID: {user_id}\nEvent: {event_name}\n<b>Verwendungszweck/Ref:</b> {reference_code}\n\n<b>{notes}</b>",
        "confirm_payment_button": "✅ Zahlung bestätigen für {name}",
        "payment_request_sent": "Ihre Zahlungsanfrage wurde an den Admin gesendet. Bitte warten Sie auf die Bestätigung der Zahlung anhand Ihres Beleges/Codes.",
        "not_authorized": "Du bist nicht berechtigt, diese Aktion auszuführen.",
        "ticket_not_pending": "⚠️ Dieses Ticket ist nicht mehr ausstehend oder wurde bereits bearbeitet.",
        "error_user_event_not_found": "Fehler: Benutzer- oder Eventdaten für dieses Ticket fehlen.",
        "payment_confirmed_ticket_sent_user": "🎫 Hier ist dein Ticket für {event_name}!",
        "thank_you_message_user": "🎉 Vielen Dank für deinen Einkauf! Wir freuen uns darauf, dich bei unserem Event begrüßen zu dürfen!",
        "payment_confirmed_admin": "✅ Zahlung und Ticket bestätigt für: {name}. Referenzcode: {reference_code} wurde erfolgreich versendet.",
        "error_sending_ticket_admin": "Fehler beim Ausstellen von Ticket {reference_code}: {error}",
        "error_sending_ticket_user": "Es gab ein Problem beim Senden deines Tickets. Bitte kontaktiere den Support.",
        "tickets_sent_multiple": "Hier sind deine {count} Tickets für {event_name}!",

        "event_selected_prompt_vorname": "Du hast '{event_name}' ausgewählt. Bitte gib deinen Vornamen ein:",
        "event_not_found_restart": "Ausgewähltes Event nicht gefunden. Bitte starte den Ticketkauf neu.",
        "enter_vorname_prompt": "Bitte gib deinen Vornamen ein:",
        "enter_nachname_prompt": "Nachname eingeben:",
        "enter_anzahl_prompt": "Wie viele Tickets möchtest du?",
        "invalid_amount": "❌ Ungültige Anzahl. Bitte gib eine positive Zahl ein (z.B. 1, 2).",
        "problem_reselect_event": "Es gab ein Problem. Bitte starte den Ticketkauf neu.",
        "ticket_purchase_summary": "✅ Du möchtest {amount} Ticket(s) für '{event_name}' kaufen.\nGesamtpreis: {total_price} EUR.\n\nBitte überweise den Betrag an die folgende Bankverbindung:\n\n*Bankname: Ihre Bank*\n*Kontoinhaber: Kabouk Events*\n*IBAN: DE12345678901234567890*\n*BIC: ABCD1234567*\n\n<b>WICHTIG:</b> Bitte gib den Code <code>{reference_code}</code> als Verwendungszweck an.\n\nNach der Überweisung sende uns bitte <b>die Quittung (Foto/PDF) oder den genauen Verwendungszweck-Text</b> zurück.\n\n---\n<b>WICHTIGER HINWEIS ZUM TICKETVERSAND:</b>\n\n* Sofortige Ticketzustellung: Bitte nutze die <b>Echtzeitüberweisung (Instant Transfer)</b>. Deine Tickets werden sofort nach Bestätigung versendet.\n* Standard-Überweisung: Die Gutschrift des Betrags dauert in der Regel 1–2 Werktage. Der Ticketversand erfolgt erst nach Gutschrift und Prüfung durch den Admin.",
        "unrecognized_message": "Entschuldigung, ich habe dich nicht verstanden. Bitte nutze die Tasten oder starte mit /start.",
        "start_bot_prompt": "Bitte starte den Bot mit /start.",
        "language_select_prompt": "Bitte wähle deine Sprache:",
        "language_changed": "Sprache wurde auf Deutsch geändert.",

        "admin_sales_report_title": "--- Verkaufsbericht ---",
        "admin_no_sales_found": "Es wurden noch keine Tickets verkauft oder es gibt keine offenen Anfragen.",
        "admin_sales_item": "<b>{index}. Käufer:</b> {name} (@{username})\n<b>Event:</b> {event_name}\n<b>Anzahl Tickets:</b> {amount}\n<b>Status:</b> {status}\n<b>Datum:</b> {date}",
        "admin_sales_status_pending": "Ausstehende Zahlung ⏳",
        "admin_sales_status_issued": "Bezahlt ✅",

        "payment_proof_received": "✅ Dokument/Text als Zahlungsnachweis erhalten. Wird zur Prüfung an Admin gesendet.",
        "payment_proof_forwarded": "👆 مدرک واریزی کاربر در پیام بالاست.",

        # 🆕 Neue Admin-Texte
        "clear_sales_prompt": "⚠️ *ACHTUNG!* Bist du sicher, dass du *ALLE* Verkaufsdaten (Tickets) unwiderruflich löschen möchtest? Diese Aktion kann nicht rückgängig gemacht werden!",
        "clear_sales_confirm_button": "✅ JA, ALLE Verkäufe löschen",
        "clear_sales_success": "✅ Alle {count} Ticket-Einträge wurden erfolgreich aus der Datenbank gelöscht. Der Verkaufsbericht ist jetzt leer.",
        "clear_sales_failure": "❌ Fehler beim Löschen der Verkaufsdaten. Keine Aktion ausgeführt.",
    },
    "fa": {
        "welcome_message": "به *ربات بلیط کابوک* خوش آمدید!\nچه کاری می‌خواهید انجام دهید؟",
        "start_message_unsubscribed": "سلام! برای استفاده از خدمات بلیط ما، باید عضو کانال‌های ما شوید.",
        "join_telegram_button": "عضویت در کانال تلگرام",
        "join_whatsapp_button": "عضویت در کانال واتساپ",
        "check_subscription_button": "بررسی عضویت و ادامه",
        "thank_you_for_joining": "از عضویت شما متشکریم! اکنون می‌توانید از ربات استفاده کنید.",
        "not_subscribed_error": "متأسفیم، ما نمی‌توانیم عضویت شما را تأیید کنیم. لطفاً در کانال‌ها عضو شوید و دوباره امتحان کنید.",

        "ticket_buy_button": "🎫 خرید بلیط",
        "next_event_button": "🎶 رویدادهای آینده",
        "past_events_button": "🗓️ رویدادهای گذشته",
        "contact_button": "📱 تماس با ما",
        "social_media_button": "📢 شبکه‌های اجتماعی",
        "language_select_button": "🌐 تغییر زبان",

        "no_events_available": "در حال حاضر هیچ رویدادی برای خرید بلیط موجود نیست.",
        "event_caption_format": "*{name}*\n🗓️ تاریخ: {date}\n📍 مکان: {location}\n⏰ ساعت: {time} \n💰 قیمت: {price} یورو\n\n*{description}*",
        "event_caption_no_poster": "(پوستر موجود نیست)",
        "buy_ticket_button_text": "🎫 خرید بلیط",
        "error_loading_poster": "(خطا در بارگذاری پوستر)",

        "no_upcoming_events": "هیچ رویداد آتی برنامه‌ریزی نشده است.",
        "upcoming_events_title": "*رویدادهای آینده ما:*\n",
        "past_events_title": "*نگاهی به لحظات فراموش‌نشدنی گذشته:*\n",
        "no_past_events": "هیچ رویداد گذشته‌ای برای نمایش وجود ندارد.",
        "event_caption_past": "*{name}*\n🗓️ تاریخ: {date}\n📍 مکان: {location}\n*{description}*\n\n*(این رویداد به پایان رسیده است)*",
        "no_poster_past_event": "(پوستری برای این رویداد گذشته موجود نیست)",

        "contact_prompt": "چگونه می‌خواهید با ما در تماس باشید؟",
        "social_media_prompt": "ما را در شبکه‌های اجتماعی دنبال کنید:",

        "payment_received_text": "تأیید پرداخت",
        "no_pending_payment": "⚠️ هیچ درخواست پرداخت در انتظار یافت نشد. لطفاً ابتدا بلیط بخرید.",
        "payment_request_admin": "💰 درخواست پرداخت جدید:\nنام: {name}\nنام کاربری: @{username}\nشناسه کاربری: {user_id}\nرویداد: {event_name}\n<b>هدف واریز/کد مرجع:</b> {reference_code}\n\n<b>{notes}</b>",
        "confirm_payment_button": "✅ تأیید پرداخت برای {name}",
        "payment_request_sent": "درخواست تأیید پرداخت شما ارسال شد. لطفاً منتظر بررسی رسید/کد توسط ما باشید.",
        "not_authorized": "شما مجاز به انجام این عمل نیستید.",
        "ticket_not_pending": "⚠️ این بلیط در انتظار نیست یا قبلاً پردازش شده است.",
        "error_user_event_not_found": "خطا: اطلاعات کاربر یا رویداد برای این بلیط یافت نشد.",
        "payment_confirmed_ticket_sent_user": "🎫 بلیط شما برای {event_name} اینجاست!",
        "thank_you_message_user": "🎉 از خرید شما متشکریم! مشتاقانه منتظر دیدار شما در رویدادمان هستیم!",
        "payment_confirmed_admin": "✅ پرداخت و بلیط برای: {name} تأیید شد. کد مرجع: {reference_code} با موفقیت ارسال شد.",
        "error_sending_ticket_admin": "خطا در صدور بلیط {reference_code}: {error}",
        "error_sending_ticket_user": "مشکلی در ارسال بلیط شما پیش آمد. لطفاً با پشتیبانی تماس بگیرید.",
        "tickets_sent_multiple": "اینجا {count} بلیط شما برای {event_name} است!",

        "event_selected_prompt_vorname": "شما '{event_name}' را انتخاب کرده‌اید. لطفاً نام کوچک خود را وارد کنید:",
        "event_not_found_restart": "رویداد انتخاب شده یافت نشد. لطفاً دوباره تلاش کنید.",
        "enter_vorname_prompt": "لطفاً نام کوچک خود را وارد کنید:",
        "enter_nachname_prompt": "نام خانوادگی را وارد کنید:",
        "enter_anzahl_prompt": "چند بلیط می‌خواهید؟",
        "invalid_amount": "❌ تعداد نامعتبر است. لطفاً یک عدد مثبت وارد کنید (مثلاً 1، 2).",
        "problem_reselect_event": "مشکلی پیش آمد. لطفاً فرآیند خرید بلیط را دوباره شروع کنید.",
        "ticket_purchase_summary": "✅ شما می‌خواهید {amount} بلیط برای '{event_name}' بخرید.\nمبلغ کل: {total_price} یورو.\n\nلطفاً مبلغ را به حساب بانکی زیر واریز کنید:\n\n*نام بانک: بانک شما*\n*صاحب حساب: Kabouk Events*\n*شماره شبا: YOUR_IBAN_HERE*\n*سوییفت کد: YOUR_BIC_HERE*\n\n<b>توجه:</b> لطفاً کد <code>{reference_code}</code> را به عنوان هدف واریز (Verwendungszweck) وارد نمایید.\n\nپس از واریز، <b>عکس رسید (مانند PDF) یا کد مرجع را برای ما ارسال کنید.</b>\n\n---\n<b>تذکر مهم در مورد ارسال بلیط:</b>\n\n* برای دریافت *آنی* بلیط، لطفاً از گزینه <b>واریز آنی (Instant Transfer)</b> استفاده کنید. بلیط‌های شما بلافاصله پس از تأیید ارسال می‌شوند.\n* در صورت استفاده از واریز عادی، واریز مبلغ معمولاً ۱ تا ۲ روز کاری طول می‌کشد. ارسال بلیط تنها پس از دریافت مبلغ و بررسی دستی توسط ادمین امکان‌پذیر است.",
        "unrecognized_message": "متاسفم، متوجه نشدم. لطفاً از دکمه‌ها استفاده کنید یا با /start شروع کنید.",
        "start_bot_prompt": "لطفاً ربات را با /start شروع کنید.",
        "language_select_prompt": "لطفا زبان خود را انتخاب کنید:",
        "language_changed": "زبان به فارسی تغییر یافت.",

        "admin_sales_report_title": "--- گزارش فروش بلیط ---",
        "admin_no_sales_found": "هنوز هیچ بلیطی فروخته نشده یا درخواست باز وجود ندارد.",
        "admin_sales_item": "<b>{index}. خریدار:</b> {name} (@{username})\n<b>رویداد:</b> {event_name}\n<b>تعداد بلیط:</b> {amount}\n<b>وضعیت:</b> {status}\n<b>تاریخ:</b> {date}",
        "admin_sales_status_pending": "در انتظار پرداخت ⏳",
        "admin_sales_status_issued": "پرداخت شده ✅",

        "payment_proof_received": "✅ مدرک پرداخت (عکس/فایل) دریافت شد. در حال ارسال برای بررسی ادمین...",
        "payment_proof_forwarded": "👆 مدرک واریزی کاربر در پیام بالاست.",

        # 🆕 Neue Admin-Texte
        "clear_sales_prompt": "⚠️ *توجه!* آیا مطمئن هستید که می‌خواهید *همه* داده‌های فروش (بلیط‌ها) را به طور غیرقابل برگشت حذف کنید؟ این عمل قابل برگشت نیست!",
        "clear_sales_confirm_button": "✅ بله، حذف *همه* فروش‌ها",
        "clear_sales_success": "✅ همه {count} ورودی بلیط با موفقیت از پایگاه داده حذف شدند. گزارش فروش اکنون خالی است.",
        "clear_sales_failure": "❌ خطایی در حذف داده‌های فروش رخ داد. عملیاتی انجام نشد.",
    },
    "ckb": { # کوردی سورانی (CKB)
        "welcome_message": "بەخێربێن بۆ *بۆتی بلیتەکانی کابوک*!\نچی دەتەوێت بیکەیت؟",
        "start_message_unsubscribed": "سڵاو! بۆ ئەوەی خزمەتگوزاری بلیتەکانمان بەکاربهێنیت، دەبێت بچیتە ناو کەناڵەکانمان.",
        "join_telegram_button": "چوونە ناو کەناڵی تێلێگرام",
        "join_whatsapp_button": "چوونە ناو کەناڵی واتساپ",
        "check_subscription_button": "پشکنینی ئەندامێتی و بەردەوامبوون",
        "thank_you_for_joining": "سوپاس بۆ چوونە ژوورەوە! ئێستا دەتوانیت بۆتەکە بەکاربهێنیت.",
        "not_subscribed_error": "ببورە، ناتوانین ئەندامێتییەکەت پشتڕاست بکەینەوە. تکایە بچۆرە ناو کەناڵەکان و دووبارە هەوڵبدەوە.",

        "ticket_buy_button": "🎫 کڕینی بلیت",
        "next_event_button": "🎶 بۆنە تازەکان",
        "past_events_button": "🗓️ بۆنە کۆنەکان",
        "contact_button": "📱 پەیوەندی",
        "social_media_button": "📢 سۆشیال میدیا",
        "language_select_button": "🌐 گۆڕینی زمان",

        "no_events_available": "لە ئێستادا هیچ بۆنەیەک بۆ کڕین بەردەست نییە.",
        "event_caption_format": "*{name}*\n🗓️ ڕێکەوت: {date}\n📍 شوێن: {location}\n⏰ کات: {time}\n💰 نرخ: {price} یۆرۆ\n\n*{description}*",
        "event_caption_no_poster": "(پۆستەر نییە)",
        "buy_ticket_button_text": "🎫 کڕینی بلیت ئێستا",
        "error_loading_poster": "(هەڵە لە بارکردنی پۆستەردا)",

        "no_upcoming_events": "هیچ بۆنەیەکی داهاتوو پلان نەکراوە.",
        "upcoming_events_title": "*بۆنە داهاتووەکانمان:*\n",
        "past_events_title": "*سەیرێک لە ساتە لەبیرنەکراوەکانی ڕابردوومان:*\n",
        "no_past_events": "هیچ بۆنەیەکی ڕابردوو نییە بۆ پیشاندان.",
        "event_caption_past": "*{name}*\n🗓️ ڕێکەوت: {date}\n📍 شوێن: {location}\n*{description}*\n\n*(ئەم بۆنەیە کۆتایی هاتووە)*",
        "no_poster_past_event": "(پۆستەر نییە بۆ ئەم بۆنەیە)",

        "contact_prompt": "چۆن دەتەوێت پەیوەندیمان پێوە بکەیت؟",
        "social_media_prompt": "لە سۆشیال میدیا فۆڵۆمان بکە:",

        "payment_received_text": "پارەم ناردووە",
        "no_pending_payment": "⚠️ هیچ داواکارییەکی پارەدان نەدۆزرایەوە. تکایە سەرەتا بلیت بکڕە.",
        "payment_request_admin": "💰 داواکاری پارەدانی نوێ بۆ بلیت:\nناو: {name}\nناوی بەکارهێنەر: @{username}\nناسنامەی بەکارهێنەر: {user_id}\نرووداو: {event_name}\n<b>مەبەستی پارەدان/کۆدی ئاماژە:</b> {reference_code}\n\n<b>{notes}</b>",
        "confirm_payment_button": "✅ پشتڕاستکردنەوەی پارەدان بۆ {name}",
        "payment_request_sent": "داواکاری پشتڕاستکردنەوەی پارەدانی تۆ نێردرا. تکایە چاوەڕێی پشکنینی وەسڵ/کۆد بە.",
        "not_authorized": "تۆ مۆڵەتی ئەنجامدانی ئەم کردارەت نییە.",
        "ticket_not_pending": "⚠️ ئەم بلیتە لە چاوەڕوانیدا نییە یان پێشتر مامەڵەی لەگەڵدا کراوە.",
        "error_user_event_not_found": "هەڵە: زانیاری بەکارهێنەر یان بۆنە بۆ ئەم بلیتە نەدۆزرایەوە.",
        "payment_confirmed_ticket_sent_user": "🎫 ئەمە بلیتەکەتە بۆ {event_name}!",
        "thank_you_message_user": "🎉 زۆر سوپاس بۆ کڕینەکەت! خۆشحاڵین بە بینینت لە بۆنەکەماندا!",
        "payment_confirmed_admin": "✅ پارەدان و بلیت بۆ: {name} پشتڕاستکرایەوە. کۆدی ئاماژە: {reference_code} بە سەرکەوتوویی نێردرا.",
        "error_sending_ticket_admin": "هەڵە لە دەرکردنی بلیت {reference_code}: {error}",
        "error_sending_ticket_user": "کێشەیەک لە ناردنی بلیتەکەتدا ڕوویدا. تکایە پەیوەندی بە پشتیوانییەوە بکە.",
        "tickets_sent_multiple": "ئەمە {count} بلیتەکەتە بۆ {event_name}!",

        "event_selected_prompt_vorname": "تۆ '{event_name}'ـت هەڵبژارد. تکایە ناوی یەکەم (پێش ناو) بنووسە:",
        "event_not_found_restart": "بۆنەی هەڵبژێردراو نەدۆزرایەوە. تکایە دووبارە هەوڵبدە.",
        "enter_vorname_prompt": "تکایە ناوی یەکەم (پێش ناو) بنووسە:",
        "enter_nachname_prompt": "ناوی دووەم (پاش ناو) بنووسە:",
        "enter_anzahl_prompt": "چەند بلیت دەتەوێت؟",
        "invalid_amount": "❌ ژمارەی هەڵە. تکایە ژمارەیەکی پۆزەتیڤ بنووسە (بۆ نموونە 1، 2).",
        "problem_reselect_event": "کێشەیەک ڕوویدا. تکایە دووبارە دەست بە کڕینی بلیت بکەوە.",
        "ticket_purchase_summary": "✅ تۆ دەتەوێت {amount} بلیت بۆ '{event_name}' بکڕیت.\nنرخی گشتی: {total_price} یۆرۆ.\n\nتکایە بڕەکە بۆ ئەم ژمارە بانکییە بگوازەوە:\n\n*ناوی بانک: بانکی تۆ*\n*خاوەن هەژمار: Kabouk Events*\n*IBAN: YOUR_IBAN_HERE*\n*BIC: YOUR_BIC_HERE*\n\n<b>گرنگ:</b> تکایە کۆدی <code>{reference_code}</code> وەکو مەبەستی پارەدان (Verwendungszweck) بنووسە.\n\nدوای گواستنەوەی پارە، <b>وێنەی وەسڵ (وەکو PDF/Photo) یان کۆدی ئاماژەمان بۆ بنێرە.</b>\n\n---\n<b>تێبینی گرنگ سەبارەت بە ناردنی بلیت:</b>\n\n* بۆ وەرگرتنی *دەستبەجێ*ی بلیت، تکایە لە گواستنەوەی <b>دەستبەجێ (Instant Transfer)</b> بەکاربهێنە. بلیتەکانت ڕاستەوخۆ دوای پشتڕاستکردنەوە دەنێردرێن.\n* لە ئەگەری بەکارهێنانی گواستنەوەی ئاسایی، وەرگرتنی پارەکە بەزۆری ١-٢ ڕۆژی کارکردن دەخایەنێت. بلیتەکان تەنها دوای وەرگرتنی پارە و پشکنینی دەستی لەلایەن ئەدمینەوە دەتوانرێن بنێردرێن.",

        "admin_sales_report_title": "--- ڕاپۆرتی فرۆش ---",
        "admin_no_sales_found": "تا ئێستا هیچ بلیتێک نەفرۆشراوە یا درخواست باز وجود ندارد.",
        "admin_sales_item": "<b>{index}. کڕیار:</b> {name} (@{username})\n<b>بۆنە:</b> {event_name}\n<b>ژمارەی بلیت:</b> {amount}\n<b>دۆخ:</b> {status}\n<b>ڕێکەوت:</b> {date}",
        "admin_sales_status_pending": "چاوەڕوانیی پارەدان ⏳",
        "admin_sales_status_issued": "پارە دراوە ✅",

        "payment_proof_received": "✅ بەڵگەی پارەدان (وێنە/فایل) وەرگیرا. بۆ پشکنین دەینێرین بۆ ئەدمین.",
        "payment_proof_forwarded": "👆 بەڵگەی پارەدانی کڕیار لە پەیامی سەرەوەدایە.",

        # 🆕 Neue Admin-Texte
        "clear_sales_prompt": "⚠️ *ئاگاداری!* ئایا دڵنیایت کە دەتەوێت *هەموو* داتای فرۆشتنەکان (بلیتەکان) بە شێوەیەکی نەگەڕێنراوە بکوژێنیتەوە؟ ئەم کردارە ناتوانرێت هەڵگیرێتەوە!",
        "clear_sales_confirm_button": "✅ بەڵێ، سڕینەوەی *هەموو* فرۆشتنەکان",
        "clear_sales_success": "✅ هەموو {count} تۆماری بلیت بە سەرکەوتوویی لە داتابەیس سڕدرانەوە. ڕاپۆرتی فرۆشتن ئێستا بەتاڵە.",
        "clear_sales_failure": "❌ هەڵەیەک لە سڕینەوەی داتای فرۆشتن ڕوویدا. هیچ کارێک ئەنجام نەدرا.",
    }
}


# 🆕 تابع برای Escape کردن کاراکترهای خاص Markdown
def escape_markdown_v2(text: str) -> str:
    """Helper function to escape telegram markup symbols."""
    # کاراکترهای خاص Markdown V2 که نیاز به Escape دارند
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in text)


# ➡️ تابع کمکی برای دریافت متن بر اساس زبان کاربر
def get_text(user_language_code, key):
    # Ensure user_language_code is a string key
    if user_language_code not in LANGUAGES:
        user_language_code = "de" # Fallback to German if language code is not recognized

    # First try to get the text for the specific user_language_code
    # If not found, try to get from the default language ("de")
    return LANGUAGES.get(user_language_code, LANGUAGES["de"]).get(key, LANGUAGES["de"].get(key, f"Missing key: {key}"))

# 🆕 تابع جدید برای استخراج توضیحات چند زبانه از رشته ذخیره شده در دیتابیس
def get_localized_description(description_str, user_lang_code):
    parts = description_str.split('|')
    desc_dict = {}
    for part in parts:
        if ':' in part:
            lang, text = part.split(':', 1)
            desc_dict[lang] = text
    return desc_dict.get(user_lang_code, desc_dict.get('de', "No description available."))

# 🆕 تابع برای بررسی عضویت کاربر در کانال تلگرام
async def is_member_of_channel(bot, chat_id, channel_id):
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=chat_id)
        # وضعیت‌های عضویت معتبر: 'member', 'creator', 'administrator'
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logging.error(f"Error checking channel membership for {chat_id}: {e}")
        return False

# ✅ شروع ربات
async def start(update: Update, context: CallbackContext):
    db: Session = next(get_db())
    user_telegram_id = update.effective_chat.user.id

    try:
        first_name = update.message.from_user.first_name or ""
        last_name = update.message.from_user.last_name or ""
        username = update.message.from_user.username
    except:
        first_name = ""
        last_name = ""
        username = None

    user = db.query(User).filter(User.telegram_id == user_telegram_id).first()

    if not user:
        user = User(
            telegram_id=user_telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            current_step="start",
            language_code="de"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    user.current_step = "start"
    user.selected_event_id = None
    db.commit()

    user_lang = user.language_code

    is_subscribed = await is_member_of_channel(context.bot, user_telegram_id, TELEGRAM_CHANNEL_ID)

    if not is_subscribed:
        subscribe_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user_lang, "join_telegram_button"), url=f"https://t.me/{TELEGRAM_CHANNEL_USERNAME}")],
            [InlineKeyboardButton(get_text(user_lang, "join_whatsapp_button"), url=WHATSAPP_CHANNEL_LINK)],
            [InlineKeyboardButton(get_text(user_lang, "check_subscription_button"), callback_data="check_subscription")],
        ])
        await update.message.reply_text(
            get_text(user_lang, "start_message_unsubscribed"),
            reply_markup=subscribe_keyboard,
            parse_mode='Markdown'
        )
    else:
        keyboard = [
            [KeyboardButton(get_text(user_lang, "ticket_buy_button"))],
            [KeyboardButton(get_text(user_lang, "next_event_button")), KeyboardButton(get_text(user_lang, "past_events_button"))],
            [KeyboardButton(get_text(user_lang, "contact_button")), KeyboardButton(get_text(user_lang, "social_media_button"))],
            [KeyboardButton(get_text(user_lang, "language_select_button"))],
        ]
        await update.message.reply_text(
            get_text(user_lang, "welcome_message"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
    db.close()

# 🎫 مراحل خرید و ارسال درخواست
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    chat_id = update.effective_chat.id
    db: Session = next(get_db())
    user = db.query(User).filter(User.telegram_id == chat_id).first()

    if not user:
        await update.message.reply_text("Bitte starte den Bot mit /start.")
        db.close()
        return

    user_lang = user.language_code

    is_subscribed = await is_member_of_channel(context.bot, user.telegram_id, TELEGRAM_CHANNEL_ID)
    if not is_subscribed:
        subscribe_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user_lang, "join_telegram_button"), url=f"https://t.me/{TELEGRAM_CHANNEL_USERNAME}")],
            [InlineKeyboardButton(get_text(user_lang, "join_whatsapp_button"), url=WHATSAPP_CHANNEL_LINK)],
            [InlineKeyboardButton(get_text(user_lang, "check_subscription_button"), callback_data="check_subscription")],
        ])
        await update.message.reply_text(
            get_text(user_lang, "start_message_unsubscribed"),
            reply_markup=subscribe_keyboard,
            parse_mode='Markdown'
        )
        db.close()
        return

    # 🚨🚨🚨 منطق اصلی پردازش پیام (بالاترین اولویت) 🚨🚨🚨

    if user.current_step == "entering_vorname":
        user.first_name = text
        user.current_step = "entering_nachname"
        db.commit()
        await update.message.reply_text(get_text(user_lang, "enter_nachname_prompt"))
        db.close()
        return

    elif user.current_step == "entering_nachname":
        user.last_name = text
        user.current_step = "entering_anzahl"
        db.commit()
        await update.message.reply_text(get_text(user_lang, "enter_anzahl_prompt"))
        db.close()
        return

    elif user.current_step == "entering_anzahl":
        try:
            anzahl = int(text)
            if anzahl <= 0:
                raise ValueError("Anzahl muss positiv sein.")

            selected_event_id = user.selected_event_id
            if not selected_event_id:
                await update.message.reply_text(get_text(user_lang, "problem_reselect_event"))
                user.current_step = "start"
                db.commit()
                db.close()
                return

            selected_event = db.query(Event).filter(Event.id == selected_event_id).first()

            # ثبت بلیت‌ها در دیتابیس (status='pending_payment')
            # گرفتن کد مرجع از اولین بلیطی که ثبت می شود (برای نمایش به کاربر)
            first_ticket_id_str = str(uuid4())
            for i in range(anzahl):
                ticket_id_str = first_ticket_id_str if i == 0 else str(uuid4()) # استفاده از اولین UUID به عنوان مرجع
                new_ticket = Ticket(
                    ticket_id_str=ticket_id_str,
                    user_id=user.id,
                    event_id=selected_event.id,
                    status="pending_payment"
                )
                db.add(new_ticket)
            db.commit()

            reference_code = first_ticket_id_str

            # 🚨🚨🚨 فراخوانی صحیح متن زمانبندی و کد مرجع 🚨🚨🚨
            summary_text = get_text(user_lang, "ticket_purchase_summary").format(
                amount=anzahl,
                event_name=selected_event.name,
                total_price=anzahl * selected_event.price,
                reference_code=reference_code # 🚨 ارسال کد مرجع به متن خلاصه
            )

            await update.message.reply_text(summary_text, parse_mode='HTML') # 🚨 استفاده از HTML
            user.current_step = "waiting_for_payment"
            db.commit()

        except ValueError:
            await update.message.reply_text(get_text(user_lang, "invalid_amount"))
        finally:
            db.close()
            return

    # 🚨🚨🚨 منطق دریافت مدرک پرداخت (عکس، فایل، متن) 🚨🚨🚨
    elif user.current_step == "waiting_for_payment":

        latest_pending_ticket = db.query(Ticket).filter(
            Ticket.user_id == user.id,
            Ticket.status == "pending_payment"
        ).order_by(Ticket.issue_date.desc()).first()

        if not latest_pending_ticket:
            await update.message.reply_text(get_text(user_lang, "no_pending_payment"))
            db.close()
            return

        # از کد مرجع اولین بلیط در مجموعه pending برای این کاربر و ایونت استفاده می کنیم.
        first_pending_ticket = db.query(Ticket).filter(
            Ticket.user_id == user.id,
            Ticket.event_id == latest_pending_ticket.event_id,
            Ticket.status == "pending_payment"
        ).order_by(Ticket.issue_date.asc()).first()

        event = db.query(Event).filter(Event.id == latest_pending_ticket.event_id).first()
        reference_code = first_pending_ticket.ticket_id_str if first_pending_ticket else "N/A"

        # 1. اگر کاربر عکس یا سند ارسال کرد (مدرک قوی)
        if update.message.photo or update.message.document:

            caption_admin = (
                f"💰 *درخواست تأیید پرداخت (تصویر رسید) از:* {user.first_name} {user.last_name or ''}\n"
                f"*رویداد:* {event.name if event else 'N/A'}\n"
                f"<b>کد مرجع سیستمی (برای تطبیق Verwendungszweck):</b> <code>{reference_code}</code>"
            )

            button = InlineKeyboardMarkup.from_button(
                InlineKeyboardButton(get_text("de", "confirm_payment_button").format(name=user.first_name), callback_data=f"confirm_{reference_code}")
            )

            # 3. ارسال عکس یا سند به ادمین به صورت فوروارد
            await context.bot.send_message(chat_id=ADMIN_ID, text=caption_admin, parse_mode='HTML')
            await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=chat_id, message_id=update.message.message_id)
            await context.bot.send_message(chat_id=ADMIN_ID, text=get_text("de", "payment_proof_forwarded"), reply_markup=button)

            await update.message.reply_text(get_text(user_lang, "payment_request_sent"))
            user.current_step = "payment_sent"
            db.commit()

        # 4. اگر کاربر پیام متنی ارسال کرد (کد مرجع یا توضیحات)
        elif update.message.text:
            text_input = update.message.text

            text_to_admin = (
                f"⚠️ *درخواست تأیید پرداخت (متن مرجع) از:* {user.first_name} {user.last_name or ''}\n"
                f"*رویداد:* {event.name if event else 'N/A'}\n"
                f"<b>کد مرجع ارسالی توسط کاربر:</b> <code>{text_input}</code>\n"
                f"<b>کد مرجع سیستمی (برای تطبیق):</b> <code>{reference_code}</code>\n\n"
                f"❗️ *نیاز به بررسی در پنل بانکی: از ادمین انتظار می‌رود تا Verwendungszweck را با کد بالا تطبیق دهد.*"
            )

            button = InlineKeyboardMarkup.from_button(
                InlineKeyboardButton(get_text("de", "confirm_payment_button").format(name=user.first_name), callback_data=f"confirm_{reference_code}")
            )

            await context.bot.send_message(chat_id=ADMIN_ID, text=text_to_admin, reply_markup=button, parse_mode='HTML')
            await context.bot.send_message(chat_id=chat_id, text=get_text(user_lang, "payment_request_sent"))

            user.current_step = "payment_sent"
            db.commit()

        else:
            await update.message.reply_text(get_text(user_lang, "unrecognized_message"))

        db.close()
        return


    # --- C. پردازش دکمه‌های اصلی منو ---
    elif text == get_text(user_lang, "ticket_buy_button"):
        active_events = db.query(Event).filter(Event.is_active == True, Event.is_past_event == False).order_by(Event.date).all()
        if not active_events:
            await context.bot.send_message(chat_id, get_text(user_lang, "no_events_available"))
            db.close()
            return

        for event in active_events:
            event_date_str = event.date.strftime('%d.%m.%Y')
            event_time_str = event.date.strftime('%H:%M')

            localized_description = escape_markdown_v2(get_localized_description(event.description, user_lang))

            caption = get_text(user_lang, "event_caption_format").format(
                name=event.name, date=event_date_str, location=event.location,
                time=event_time_str, price=event.price, description=localized_description
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(get_text(user_lang, "buy_ticket_button_text"), callback_data=f"buy_ticket_for_{event.id}")]
            ])
            if event.poster_path and os.path.exists(event.poster_path):
                try:
                    with open(event.poster_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode='Markdown', reply_markup=keyboard)
                except Exception as e:
                    logging.error(f"Error sending photo for event {event.name}: {e}")
                    await context.bot.send_message(chat_id, f"{get_text(user_lang, 'error_loading_poster')}\n{caption}", parse_mode='Markdown', reply_markup=keyboard)
            else:
                caption += f"\n\n{get_text(user_lang, 'event_caption_no_poster')}"
                await context.bot.send_message(chat_id, caption, parse_mode='Markdown', reply_markup=keyboard)

        user.current_step = "select_event"
        db.commit()

    elif text == get_text(user_lang, "next_event_button"):
        active_events = db.query(Event).filter(Event.is_active == True, Event.is_past_event == False).order_by(Event.date).all()
        if not active_events:
            await context.bot.send_message(chat_id, get_text(user_lang, "no_upcoming_events"))
            db.close()
            return

        await context.bot.send_message(chat_id, get_text(user_lang, "upcoming_events_title"), parse_mode='Markdown')
        for event in active_events:
            event_date_str = event.date.strftime('%d.%m.%Y')
            event_time_str = event.date.strftime('%H:%M')

            localized_description = escape_markdown_v2(get_localized_description(event.description, user_lang))

            caption = get_text(user_lang, "event_caption_format").format(
                name=event.name, date=event_date_str, location=event.location,
                time=event_time_str, price=event.price, description=localized_description
            )
            if event.poster_path and os.path.exists(event.poster_path):
                try:
                    with open(event.poster_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode='Markdown')
                except Exception as e:
                    logging.error(f"Error sending photo for event {event.name}: {e}")
                    await context.bot.send_message(chat_id, f"{get_text(user_lang, 'error_loading_poster')}\n{caption}", parse_mode='Markdown')
            else:
                caption += f"\n\n{get_text(user_lang, 'event_caption_no_poster')}"
                await context.bot.send_message(chat_id, caption, parse_mode='Markdown')
        user.current_step = "start"
        db.commit()

    elif text == get_text(user_lang, "past_events_button"):
        past_events = db.query(Event).filter(Event.is_past_event == True).order_by(Event.date.desc()).all()
        if not past_events:
            await context.bot.send_message(chat_id, get_text(user_lang, "no_past_events"))
            db.close()
            return

        await context.bot.send_message(chat_id, get_text(user_lang, "past_events_title"), parse_mode='Markdown')
        for event in past_events:
            event_date_str = event.date.strftime('%d.%m.%Y')

            localized_description = escape_markdown_v2(get_localized_description(event.description, user_lang))

            caption = get_text(user_lang, "event_caption_past").format(
                name=event.name, date=event_date_str, location=event.location, description=localized_description
            )
            if event.poster_path and os.path.exists(event.poster_path):
                try:
                    with open(event.poster_path, 'rb') as photo:
                        await context.bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode='Markdown')
                except Exception as e:
                    logging.error(f"Error sending photo for past event {event.name}: {e}")
                    await context.bot.send_message(chat_id, f"{get_text(user_lang, 'error_loading_poster')}\n{caption}", parse_mode='Markdown')
            else:
                caption += f"\n\n{get_text(user_lang, 'no_poster_past_event')}"
                await context.bot.send_message(chat_id, caption, parse_mode='Markdown')
        user.current_step = "start"
        db.commit()

    elif text == get_text(user_lang, "contact_button"):
        keyboard_buttons = [[InlineKeyboardButton(link["name"], url=link["url"])] for link in CONTACT_LINKS]
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        await update.message.reply_text(
            get_text(user_lang, "contact_prompt"),
            reply_markup=reply_markup
        )
        user.current_step = "start"
        db.commit()

    elif text == get_text(user_lang, "social_media_button"):
        keyboard_buttons = [[InlineKeyboardButton(link["name"], url=link["url"])] for link in SOCIAL_MEDIA_LINKS]
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        await update.message.reply_text(
            get_text(user_lang, "social_media_prompt"),
            reply_markup=reply_markup
        )
        user.current_step = "start"
        db.commit()

    elif text == get_text(user_lang, "language_select_button"):
        language_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="set_lang_de")],
            [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang_fa")],
            [InlineKeyboardButton("کوردی 🇮🇶", callback_data="set_lang_ckb")],
        ])
        await update.message.reply_text(get_text(user_lang, "language_select_prompt"), reply_markup=language_keyboard)
        user.current_step = "select_language"
        db.commit()


    # --- D. پردازش پیام‌های خارج از نوبت (اگر متن بود) ---
    elif update.message.text and update.message.text.lower() == get_text(user_lang, "payment_received_text").lower():
        # اگر کاربر پیام قدیمی را تایپ کرد
        await update.message.reply_text("لطفاً به جای تایپ کردن، عکس رسید یا کد مرجع را برای ما ارسال کنید تا پرداخت شما تأیید شود.")

    else:
        await update.message.reply_text(get_text(user_lang, "unrecognized_message"))

    db.close()

# ✅ مدیریت CallbackQuery برای انتخاب رویداد و تأیید پرداخت و تغییر زبان
async def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    db: Session = next(get_db())
    chat_id = query.message.chat_id

    current_user = db.query(User).filter(User.telegram_id == chat_id).first()
    if not current_user:
        current_user = User(
            telegram_id=chat_id,
            first_name=query.from_user.first_name or "",
            last_name=query.from_user.last_name or "",
            username=query.from_user.username,
            current_step="start",
            language_code="de"
        )
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    user_lang = current_user.language_code

    if query.data.startswith("buy_ticket_for_"):
        event_id = int(query.data.split("_")[3])
        selected_event = db.query(Event).filter(Event.id == event_id).first()
        if selected_event:
            current_user.selected_event_id = event_id
            current_user.current_step = "entering_vorname"
            db.commit()

            await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(user_lang, "event_selected_prompt_vorname").format(event_name=selected_event.name)
            )

        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(user_lang, "event_not_found_restart")
            )
        db.close()
        return

    elif query.data.startswith("confirm_"):
        if chat_id != ADMIN_ID:
            await query.edit_message_text(get_text("de", "not_authorized"))
            db.close()
            return

        ticket_id_str_to_confirm = query.data.split("_")[1]

        sample_ticket = db.query(Ticket).filter(
            Ticket.ticket_id_str == ticket_id_str_to_confirm,
            Ticket.status == "pending_payment"
        ).first()

        if not sample_ticket:
            await query.edit_message_text(get_text("de", "ticket_not_pending"))
            db.close()
            return

        ticket_holder_user = db.query(User).filter(User.id == sample_ticket.user_id).first()
        ticket_event = db.query(Event).filter(Event.id == sample_ticket.event_id).first()

        if not ticket_holder_user or not ticket_event:
            logging.error(f"Critical error: User or Event not found for ticket {sample_ticket.ticket_id_str}.")
            await query.edit_message_text(get_text("de", "error_user_event_not_found"))
            db.close()
            return

        all_pending_tickets = db.query(Ticket).filter(
            Ticket.user_id == ticket_holder_user.id,
            Ticket.event_id == ticket_event.id,
            Ticket.status == "pending_payment"
        ).all()

        if not all_pending_tickets:
            await query.edit_message_text(get_text("de", "ticket_not_pending"))
            db.close()
            return

        issued_tickets_count = 0
        full_name = f"{ticket_holder_user.first_name} {ticket_holder_user.last_name or ''}".strip()

        for ticket in all_pending_tickets:
            try:
                # 2. ایجاد و ارسال تیکت PDF
                pdf_path = create_ticket(full_name, ticket.ticket_id_str, ticket_event.name)

                await context.bot.send_document(
                    chat_id=ticket_holder_user.telegram_id,
                    document=open(pdf_path, "rb"),
                    caption=get_text(ticket_holder_user.language_code, "payment_confirmed_ticket_sent_user").format(event_name=ticket_event.name)
                )

                # 3. به‌روزرسانی وضعیت در دیتابیس
                ticket.status = "issued"
                db.commit()

                # 4. حذف فایل موقت
                os.remove(pdf_path)
                issued_tickets_count += 1

                logging.info(f"Ticket {ticket.ticket_id_str} issued to {ticket_holder_user.telegram_id}")

            except Exception as e:
                logging.error(f"Error issuing ticket {ticket.ticket_id_str} for user {ticket_holder_user.telegram_id}: {e}", exc_info=True)
                await context.bot.send_message(chat_id=ADMIN_ID, text=get_text("de", "error_sending_ticket_admin").format(reference_code=ticket.ticket_id_str, error=e))
                await context.bot.send_message(chat_id=ticket_holder_user.telegram_id, text=get_text(ticket_holder_user.language_code, "error_sending_ticket_user"))

        if issued_tickets_count > 0:
            # 5. ارسال پیام نهایی به کاربر
            await context.bot.send_message(
                chat_id=ticket_holder_user.telegram_id,
                text=get_text(ticket_holder_user.language_code, "tickets_sent_multiple").format(count=issued_tickets_count, event_name=ticket_event.name)
            )
            await context.bot.send_message(
                chat_id=ticket_holder_user.telegram_id,
                text=get_text(ticket_holder_user.language_code, "thank_you_message_user")
            )

            # 6. به‌روزرسانی پیام ادمین
            await query.edit_message_text(get_text("de", "payment_confirmed_admin").format(name=full_name, reference_code=all_pending_tickets[0].ticket_id_str if all_pending_tickets else 'N/A'))
        else:
            await query.edit_message_text(get_text("de", "error_sending_ticket_admin").format(reference_code=ticket_id_str_to_confirm, error="No tickets were successfully issued."))

        db.close()
        return


    elif query.data.startswith("set_lang_"):
        new_lang_code = query.data.split("_")[2]
        if new_lang_code in LANGUAGES:
            current_user.language_code = new_lang_code
            db.commit()
            await query.edit_message_text(get_text(new_lang_code, "language_changed"))

            keyboard = [
                [KeyboardButton(get_text(new_lang_code, "ticket_buy_button"))],
                [KeyboardButton(get_text(new_lang_code, "next_event_button")), KeyboardButton(get_text(new_lang_code, "past_events_button"))],
                [KeyboardButton(get_text(new_lang_code, "contact_button")), KeyboardButton(get_text(new_lang_code, "social_media_button"))],
                [KeyboardButton(get_text(new_lang_code, "language_select_button"))],
            ]
            await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(new_lang_code, "welcome_message"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(get_text(user_lang, "unrecognized_message"))
        db.close()
        return

    elif query.data == "check_subscription":
        is_subscribed = await is_member_of_channel(context.bot, current_user.telegram_id, TELEGRAM_CHANNEL_ID)

        if is_subscribed:
            await query.edit_message_text(get_text(user_lang, "thank_you_for_joining"))
            keyboard = [
                [KeyboardButton(get_text(user_lang, "ticket_buy_button"))],
                [KeyboardButton(get_text(user_lang, "next_event_button")), KeyboardButton(get_text(user_lang, "past_events_button"))],
                [KeyboardButton(get_text(user_lang, "contact_button")), KeyboardButton(get_text(user_lang, "social_media_button"))],
                [KeyboardButton(get_text(user_lang, "language_select_button"))],
            ]
            await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(user_lang, "welcome_message"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(get_text(user_lang, "not_subscribed_error"))
        db.close()
        return

    # 🆕 Callback-Handler zum Bestätigen des Löschens
    elif query.data == "confirm_clear_sales":
        if chat_id != ADMIN_ID:
            await query.edit_message_text(get_text("de", "not_authorized"))
            db.close()
            return

        try:
            # Löschen aller Tickets
            deleted_count = db.query(Ticket).delete()
            db.commit()

            # Aktualisierung der Nachricht im Admin-Chat
            await query.edit_message_text(
                get_text("de", "clear_sales_success").format(count=deleted_count),
                parse_mode='Markdown'
            )
            logging.info(f"Admin {chat_id} cleared all {deleted_count} ticket entries.")

        except Exception as e:
            logging.error(f"Error clearing all sales data: {e}", exc_info=True)
            await query.edit_message_text(
                get_text("de", "clear_sales_failure"),
                parse_mode='Markdown'
            )
        finally:
            db.close()
            return

    db.close()


# 🆕 تابع جدید برای ارسال لیست فروش به ادمین (نسخه بهبود یافته)
async def admin_sales_report(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.chat_id
    if chat_id != ADMIN_ID:
        return

    db: Session = next(get_db())

    all_tickets = db.query(Ticket).order_by(Ticket.issue_date.asc()).all()

    if not all_tickets:
        await context.bot.send_message(chat_id, get_text("de", "admin_no_sales_found"))
        db.close()
        return

    grouped_sales = defaultdict(lambda: {'tickets_count': 0, 'status': None, 'issue_date': None, 'event_price': 0, 'user': None, 'event': None})

    total_issued = 0
    total_pending = 0

    for ticket in all_tickets:
        key = (ticket.user_id, ticket.event_id, ticket.status)

        if grouped_sales[key]['tickets_count'] == 0:
            grouped_sales[key]['status'] = ticket.status
            grouped_sales[key]['issue_date'] = ticket.issue_date
            grouped_sales[key]['event_price'] = db.query(Event.price).filter(Event.id == ticket.event_id).scalar()
            grouped_sales[key]['user'] = db.query(User).filter(User.id == ticket.user_id).first()
            grouped_sales[key]['event'] = db.query(Event).filter(Event.id == ticket.event_id).first()

        grouped_sales[key]['tickets_count'] += 1

        if ticket.status == 'issued':
            total_issued += 1
        elif ticket.status == 'pending_payment':
            total_pending += 1


    final_grouped_data = list(grouped_sales.values())
    total_revenue = sum(data['tickets_count'] * data['event_price'] for data in final_grouped_data if data['status'] == 'issued')

    report_text = get_text("de", "admin_sales_report_title") + "\n\n"

    report_text += "<b>--- خلاصه فروش ---</b>\n"
    report_text += f"<b>کل بلیط‌های فروخته شده:</b> {total_issued}\n"
    report_text += f"<b>بلیط‌های در انتظار پرداخت:</b> {total_pending}\n"
    report_text += f"<b>کل درآمد (تأیید شده):</b> {total_revenue} EUR\n\n"
    report_text += "<b>--- جزئیات فروش (بر اساس رویداد و خریدار) ---</b>\n\n"

    index = 1

    final_grouped_data.sort(key=lambda x: x['issue_date'])

    for data in final_grouped_data:
        user = data['user']
        event = data['event']

        if user and event:
            status_text = get_text("de", "admin_sales_status_issued") if data['status'] == 'issued' else get_text("de", "admin_sales_status_pending")

            report_item = get_text("de", "admin_sales_item").format(
                index=index,
                name=f"{user.first_name} {user.last_name or ''}",
                username=user.username or 'N/A',
                event_name=event.name,
                amount=data['tickets_count'],
                status=status_text,
                date=data['issue_date'].strftime('%Y-%m-%d | %H:%M')
            )
            report_text += report_item + "\n"
            index += 1

    await context.bot.send_message(chat_id, report_text, parse_mode='HTML')
    db.close()


# 🆕 Admin-Befehl zum Löschen der Verkaufsdaten
async def admin_clear_sales(update: Update, context: CallbackContext):
    logging.info(f"Received /clearsales command from chat ID: {update.effective_chat.id}")

    chat_id = update.effective_chat.chat_id

    if chat_id != ADMIN_ID:
        await update.message.reply_text(get_text("de", "not_authorized"))
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("de", "clear_sales_confirm_button"), callback_data="confirm_clear_sales")],
    ])

    await update.message.reply_text(
        get_text("de", "clear_sales_prompt"),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# 🆕 Error Handler برای جلوگیری از کرش کردن ربات
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and notify the admin."""
    logging.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    # 🚨 اینجا می‌توانید یک پیام به ADMIN_ID ارسال کنید تا از خطا مطلع شوید، مثلا:
    # if update:
    #     await context.bot.send_message(chat_id=ADMIN_ID, text=f"خطای بحرانی در پردازش! Update: {update.update_id}\nError: {context.error}")

# 🧾 ساخت بلیت با QR که دقیقاً مربع سیاه سمت راست را می‌پوشاند
def create_ticket(name, ticket_id_str, event_name):

    qr_data = (
        f"KABOUK TICKET VALIDATION\n"
        f"Ticket ID: {ticket_id_str}\n"
        f"Holder Name: {name}\n"
        f"Event: {event_name}\n"
        f"Payment Method: Bank Transfer (Verwendungszweck)\n"
        f"Issue Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    qr = qrcode.make(qr_data)

    poster_template_path = "my_new_design.jpg"  

    if not os.path.exists(poster_template_path):
        logging.error(f"Error: Ticket template '{poster_template_path}' not found. Check file name and path.")
        raise FileNotFoundError(f"Ticket template '{poster_template_path}' not found. Cannot create ticket.")
    else:
        try:
            poster = Image.open(poster_template_path).convert("RGB")
            logging.info(f"Successfully loaded ticket template: {poster_template_path} with dimensions {poster.size}")
            print(f"Loaded poster size (width, height): {poster.size}")  
        except Exception as e:
            logging.error(f"Error opening or converting ticket template '{poster_template_path}': {e}")
            raise Exception(f"Failed to load ticket template image: {e}")

    poster_width, poster_height = poster.size

    black_area_start_x = 960      
    black_area_start_y = 100

    black_area_width = 300
    black_area_height = 300

    final_qr_width = max(1, black_area_width)
    final_qr_height = max(1, black_area_height)

    qr_image = qr.resize((final_qr_width, final_qr_height), Image.LANCZOS)
    logging.info(f"QR code resized to {final_qr_width}x{final_qr_height} pixels to precisely fit the black area.")

    poster.paste(qr_image, (int(black_area_start_x), int(black_area_start_y)))
    logging.info(f"QR code pasted at X:{int(black_area_start_x)}, Y:{int(black_area_start_y)}.")

    filename = f"ticket_{ticket_id_str}.pdf"
    temp_img_path = f"temp_ticket_{ticket_id_str}.jpg"
    try:
        poster.save(temp_img_path, quality=95)
        logging.info(f"Temporary ticket image saved to {temp_img_path}")
    except Exception as e:
        logging.error(f"Error saving temporary image '{temp_img_path}': {e}")
        raise Exception(f"Failed to save temporary image for PDF generation: {e}")

    pdf_width_mm = poster_width / 96 * 25.4 
    pdf_height_mm = poster_height / 96 * 25.4

    pdf = FPDF(unit="mm", format=(pdf_width_mm, pdf_height_mm)) 
    pdf.add_page()
    try:
        pdf.image(temp_img_path, x=0, y=0, w=pdf.w, h=pdf.h) 
        pdf.output(filename, "F")
        logging.info(f"PDF ticket generated: {filename}")
    except Exception as e:
        logging.error(f"Error generating PDF '{filename}': {e}")
        raise Exception(f"Failed to generate PDF ticket: {e}")
    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
            logging.info(f"Temporary image {temp_img_path} removed.")

    return filename

# 🟢 اجرای برنامه
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # --- ثبت Command Handlers (دستورات) - بالاترین اولویت ---
    app.add_handler(CommandHandler("start", start))

    # 🚨 دستورات ادمین با فیلتر صحیح
    app.add_handler(CommandHandler("sales", admin_sales_report, filters=filters.Chat(ADMIN_ID)))
    app.add_handler(CommandHandler("clearsales", admin_clear_sales, filters=filters.Chat(ADMIN_ID))) # ⬅️ اینجا فیلتر ادمین برگردانده شد و ثبت صحیح انجام شد

    # --- ثبت Callback Handler (دکمه‌های اینلاین) ---
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # --- ثبت Message Handlers (پیام‌های عادی، عکس و فایل) - پایین‌ترین اولویت ---
    # این باید بعد از CommandHandlers باشد.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND | filters.PHOTO | filters.Document.ALL, handle_message))

    # 🆕 ثبت Error Handler
    app.add_error_handler(error_handler)


    print("🤖 Der Bot läuft...")
    app.run_polling()