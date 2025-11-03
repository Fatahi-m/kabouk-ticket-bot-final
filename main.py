import logging
import qrcode
import datetime as dt
import csv, io
import asyncio
from PIL import Image
from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackContext,
    MessageHandler, filters, CallbackQueryHandler,
    ConversationHandler
)
from uuid import uuid4
from datetime import datetime, time
from sqlalchemy.orm import Session
from sqlalchemy import func
# فرض می‌کنیم database.py در جای درست قرار دارد
from database import init_db, get_db, User, Event, Ticket, Survey, DiscountCode
import os


# 🔧 تنظیمات اولیه
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "922402042"))

# ⭐️ NEW: لیست شناسه‌های تلگرام مسئولین چک-این بلیط
# می‌توانید شناسه‌های بیشتری را با کاما جدا کنید
CHECKIN_STAFF_IDS = {ADMIN_ID, 922402042} # آی‌دی ادمین و یک آی‌دی نمونه

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
    {"name": "🌐 Website", "url": "https://www.kaboukevent.com"},
    {"name": "📨 Telegram Admin", "url": "https://t.me/Fetahi_M"},
]

# 🌍 دایرکتوری زبان‌ها (Language Packs)
# ⭐️⭐️ استفاده از رشته‌های چندخطی برای حفظ قالب‌بندی و رفع هشدارهای IDE ⭐️⭐️
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
        "go_to_main_menu": "🏠 Zurück zum Hauptmenü", # ⭐️ NEW
        "back_button": "⬅️ Zurück", # ⭐️ NEW: Back button for purchase steps

        # --- UX Improvements ---
        "my_tickets_button": "🎟️ Meine Tickets",
        "help_button": "❓ Hilfe",
        "my_tickets_title": "Deine gekauften Tickets:",
        "my_tickets_none": "Du hast noch keine Tickets gekauft.",
        "help_text": """*Hilfe & Anleitung*

Willkommen beim Kabouk-Ticket-Bot! Hier ist eine kurze Anleitung:

1. *🎫 Ticket kaufen*: Wähle diese Option, um die Liste der aktuellen Events zu sehen und Tickets zu kaufen.
2. *🎶 Nächstes Event*: Zeigt dir Details zu unseren kommenden Events.
3. *🗓️ Vergangene Events*: Wirf einen Blick auf unsere vergangenen Konzerte.
4. *🎟️ Meine Tickets*: Hier findest du alle deine gekauften Tickets erneut.
5. *🌐 Sprache ändern*: Wähle zwischen Deutsch, Persisch und Kurdisch.
6. *📱 Kontakt / 📢 Social Media*: Kontaktiere uns oder folge uns auf unseren Kanälen.

Bei Problemen wende dich bitte an den Support über den *Kontakt*-Button.""",

        # --- Automation ---
        "event_reminder_message": "🔔 *Erinnerung!*\n\nDein Event '{event_name}' findet morgen statt!\n\nWir freuen uns auf dich!",
        "post_event_survey_message": "Wir hoffen, du hattest eine tolle Zeit bei '{event_name}'!\n\nWie würdest du das Event bewerten?",
        "survey_thanks": "Vielen Dank für dein Feedback!",
        "survey_already_voted": "Du hast dieses Event bereits bewertet. Danke!",
        "survey_rating_1": "⭐️",
        "bot_feedback_prompt": "Wie zufrieden bist du mit dem Kabouk Ticket Bot Service?",
        "stop_bot_warning": "⚠️ *Achtung!* ⚠️\n\nWenn du den Bot stoppst oder den Chatverlauf löschst, werden deine Daten, einschließlich gekaufter Tickets und Treuestatus, dauerhaft gelöscht. Du verlierst den Anspruch auf zukünftige Treuerabatte.\n\nBist du sicher, dass du fortfahren möchtest?",
        "survey_rating_2": "⭐️⭐️",
        "survey_rating_3": "⭐️⭐️⭐️",
        "survey_rating_4": "⭐️⭐️⭐️⭐️",
        "survey_rating_5": "⭐️⭐️⭐️⭐️⭐️",

        "no_events_available": "Aktuell sind keine Events zum Kauf verfügbar.",
        "event_sold_out": "Dieses Event ist leider ausverkauft!",
        "event_caption_format": "*{name}*\n🗓️ Datum: {date}\n📍 Ort: {location}\n⏰ Uhrzeit: {time} Uhr\n💰 Preis: {price} EUR\n\n*{description}*",
        "event_caption_no_poster": "(Kein Poster verfügbar)",
        # --- Discount Code ---
        "ask_discount_code": "Hast du einen Rabattcode?",
        "yes": "Ja",
        "no": "Nein",
        "loyalty_discount_applied": "🎉 Als treuer Kunde erhältst du 10% Rabatt auf diesen Kauf!",
        "ask_ticket_type": "Welchen Ticket-Typ möchtest du?",
        "enter_discount_code": "Bitte gib deinen Rabattcode ein:",
        "discount_invalid": "❌ Ungültiger oder abgelaufener Rabattcode.",
        "discount_applied": "✅ Rabattcode '{code}' angewendet!",
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
        "ticket_purchase_summary": """✅ Du möchtest {amount} Ticket(s) für '{event_name}' kaufen.\nGesamtpreis: {total_price} EUR.

Bitte überweise den Betrag an die folgende Bankverbindung:

*Bankname:  N26*
*Kontoinhaber: Mukhtar Fatahi*
*IBAN: DE66100110012264463335*
*BIC: NTSBDEB1XXX*

<b>WICHTIG:</b> Bitte gib den Code <code>{reference_code}</code> als Verwendungszweck an.

Nach der Überweisung sende uns bitte <b>die Quittung (Foto/PDF) oder den genauen Verwendungszweck-Text</b> zurück.

---
<b>WICHTIGER HINWEIS ZUM TICKETVERSAND:</b>

* Sofortige Ticketzustellung: Bitte nutze die <b>Echtzeitüberweisung (Instant Transfer)</b>. Deine Tickets werden sofort nach Bestätigung versendet.
* Standard-Überweisung: Die Gutschrift des Betrags dauert in der Regel 1–2 Werktage. Der Ticketversand erfolgt erst nach Gutschrift und Prüfung durch den Admin.""",
        "unrecognized_message": "Entschuldigung, ich habe dich nicht verstanden. Bitte nutze die Tasten oder starte mit /start.",
        "start_bot_prompt": "Bitte starte den Bot mit /start.",
        "language_select_prompt": "🌐 Bitte wähle deine Sprache:",
        "language_changed": "Sprache wurde auf Deutsch geändert.",

        "admin_sales_report_title": "--- Verkaufsbericht ---",
        "admin_no_sales_found": "Es wurden noch keine Tickets verkauft oder es gibt keine offenen Anfragen.",
        "admin_sales_item": "<b>{index}. Käufer:</b> {name} (@{username})\n<b>Event:</b> {event_name}\n<b>Anzahl Tickets:</b> {amount}\n<b>Status:</b> {status}\n<b>Datum:</b> {date}",
        "admin_sales_status_pending": "Ausstehende Zahlung ⏳",
        "admin_sales_status_issued": "Bezahlt ✅",

        "payment_proof_received": "✅ Dokument/Text als Zahlungsnachweis erhalten. Wird zur Prüfung an Admin gesendet.",
        "payment_proof_forwarded": "👆 مدرک واریزی کاربر در پیام بالاست.",

        # --- Admin Event Management ---
        "admin_addevent_start": "Ein neues Event wird hinzugefügt. Bitte gib den Namen des Events ein:",
        "admin_addevent_name_received": "OK. Name ist '{name}'. Bitte gib das Datum und die Uhrzeit ein (Format: YYYY-MM-DD HH:MM):",
        "admin_addevent_datetime_received": "OK. Datum ist '{date}'. Bitte gib den Ort des Events ein:",
        "admin_addevent_location_received": "OK. Ort ist '{location}'. Bitte gib den Preis in EUR ein (nur die Zahl):",
        "admin_addevent_price_received": "OK. Preis ist {price} EUR. Bitte gib die mehrsprachige Beschreibung ein:\nFormat: `de:Text|fa:Text|ckb:Text`",
        "admin_addevent_description_received": "OK. Beschreibung erhalten. Bitte lade jetzt das Event-Poster hoch.",
        "admin_addevent_poster_received": "Poster erhalten. Soll das Event sofort aktiv sein? (ja/nein)",
        "admin_addevent_success": "✅ Event '{name}' wurde erfolgreich erstellt und gespeichert!",
        "admin_addevent_cancel": "Vorgang zum Hinzufügen eines Events wurde abgebrochen.",
        "admin_invalid_date": "Ungültiges Datumsformat. Bitte benutze YYYY-MM-DD HH:MM.",
        "admin_invalid_price": "Ungültiger Preis. Bitte gib eine Zahl ein.",
        "admin_invalid_yes_no": "Ungültige Eingabe. Bitte antworte mit 'ja' oder 'nein'.",

        # --- Admin Menu ---
        "admin_menu_title": "⚙️ Admin-Menü ⚙️\nWas möchtest du tun?",
        "admin_menu_add_event": "➕ Event hinzufügen",
        "admin_menu_edit_event": "✏️ Event bearbeiten",
        "admin_menu_archive_event": "🗂️ Event archivieren/löschen",
        "admin_menu_export_csv": "📄 Verkäufe exportieren (CSV)",
        "admin_menu_survey_report": "📊 Umfragebericht",
        "admin_menu_sales_report": "📊 Verkaufsbericht",

        # --- Admin Edit Event ---
        "admin_editevent_select": "Welches Event möchtest du bearbeiten?",
        "admin_editevent_no_events": "Keine Events zum Bearbeiten gefunden.",
        "admin_editevent_selected": "Du bearbeitest '{name}'. Was möchtest du ändern?",
        "admin_editevent_ask_new_value": "Bitte gib den neuen Wert für '{field}' ein.",
        "admin_editevent_ask_new_poster": "Bitte lade das neue Poster hoch.",
        "admin_editevent_updated": "✅ Feld '{field}' für Event '{name}' wurde aktualisiert.",
        "admin_editevent_done": "Bearbeitung abgeschlossen. Du kehrst zum Admin-Menü zurück.",
        "admin_editevent_cancel": "Bearbeitung abgebrochen.",

        # --- Admin Archive/Delete Event ---
        "admin_archive_select": "Welches Event möchtest du verwalten?",
        "admin_archive_menu": "Aktion für '{name}':",
        "admin_archive_button": "Archivieren (zu Vergangene verschieben)",
        "admin_delete_button": "Löschen",
        "admin_archive_success": "✅ Event '{name}' wurde archiviert.",
        "admin_delete_confirm": "Bist du sicher, dass du '{name}' DAUERHAFT löschen möchtest? Alle zugehörigen Tickets werden ebenfalls gelöscht. Dies kann nicht rückgängig gemacht werden.",
        "admin_delete_success": "🗑️ Event '{name}' wurde endgültig gelöscht.",

        # --- Admin Discount Codes ---
        "admin_menu_discounts": "🎟️ Rabattcodes verwalten",
        "admin_discounts_menu_title": "Rabattcode-Verwaltung",
        "admin_discounts_create": "Neu erstellen",
        "admin_discounts_view": "Alle anzeigen",
        "admin_discounts_delete": "Löschen",
        "admin_discounts_ask_code": "Gib den neuen Code ein (z.B. SOMMER20):",
        "admin_discounts_ask_type": "Wähle den Rabatt-Typ:",
        "admin_discounts_ask_value": "Gib den Wert ein (z.B. '10' für 10% oder '5' für 5 EUR):",
        "admin_discounts_ask_max_uses": "Wie oft kann der Code verwendet werden?",
        "admin_discounts_view_title": "--- Bestehende Rabattcodes ---",
        "admin_discounts_view_item": "<b>Code:</b> <code>{code}</code>\n<b>Typ:</b> {type}\n<b>Wert:</b> {value}\n<b>Verwendet:</b> {uses}/{max_uses}\n<b>Aktiv:</b> {active}\n",
        "admin_discounts_none": "Keine Rabattcodes gefunden.",
        "admin_discounts_delete_prompt": "Welchen Code möchtest du löschen? Bitte sende den Code-Namen.",
        "admin_discounts_success": "✅ Rabattcode '{code}' wurde erstellt.",
        "admin_addevent_ask_vip": "Hat dieses Event einen VIP-Bereich? (ja/nein)",
        "admin_addevent_ask_vip_price": "OK. Bitte gib den VIP-Preis in EUR ein:",
        "admin_addevent_ask_vip_description": "OK. VIP-Preis ist {price} EUR. Bitte gib die mehrsprachige VIP-Beschreibung ein (Format: de:Text|fa:Text):",

        # --- Admin Event Capacity ---
        "admin_addevent_capacity_received": "OK. Kapazität ist {capacity}. Bitte gib die mehrsprachige Beschreibung ein:\nFormat: `de:Text|fa:Text|ckb:Text`",
        "admin_addevent_ask_capacity": "OK. Preis ist {price} EUR. Bitte gib die Kapazität des Events an (Zahl, oder '0' für unbegrenzt):",        "admin_addevent_ask_desc_de": "OK. Kapazität ist {capacity}. Bitte gib die deutsche Beschreibung ein:",
        "admin_addevent_ask_desc_fa": "OK. Bitte gib die persische Beschreibung ein:",
        "admin_addevent_ask_desc_ckb": "OK. Bitte gib die kurdische Beschreibung ein:",

        # --- Check-in System ---
        "checkin_start": "✅ Check-in Modus aktiviert.\nBitte scanne den QR-Code des Tickets oder sende die Ticket-ID.",
        "checkin_cancel": "Check-in Modus deaktiviert.",
        "checkin_invalid_id": "❌ Ungültige Ticket-ID.",
        "checkin_not_found": "❌ Ticket nicht gefunden.",
        "checkin_not_issued": "❌ Ticket ungültig (Status: {status}).\nInhaber: {name}\nEvent: {event}",
        "checkin_already_used": "❌ Ticket bereits verwendet!\nEingecheckt am: {date}\nInhaber: {name}\nEvent: {event}",
        "checkin_success": "✅ Ticket gültig! Willkommen!\nInhaber: {name}\nEvent: {event}",
        "checkin_wrong_event": "❌ Ticket ist für ein anderes Event!\nTicket für: {ticket_event}\nAktuelles Event: {current_event}",
        "checkin_select_event": "Für welches Event möchtest du Tickets einchecken?",

        # --- Admin Survey Report ---
        "admin_survey_report_title": "--- Umfrageergebnisse ---",
        "admin_survey_export_csv": "📄 Umfrageergebnisse exportieren (CSV)",
        "admin_survey_report_item": "<b>{event_name}</b>:\n- Durchschnittliche Bewertung: {avg_rating:.1f} / 5 ⭐ ({vote_count} Stimmen)\n",
        "admin_survey_no_surveys": "Es wurden noch keine Umfragen beantwortet.",

        # --- Admin Broadcast ---
        "admin_menu_broadcast": "📣 Broadcast an alle",
        "admin_broadcast_start": "Bitte sende die Nachricht, die du an alle Benutzer senden möchtest. Du kannst Text, Fotos, Videos usw. senden.",
        "admin_broadcast_confirm": "Soll diese Nachricht wirklich an alle Benutzer gesendet werden?",
        "admin_broadcast_sending": "⏳ Sende Broadcast... Dies kann eine Weile dauern.",
        "admin_broadcast_success_report": "✅ Broadcast abgeschlossen.\nGesendet an: {success_count} Benutzer.\nFehlgeschlagen für: {failed_count} Benutzer.",
        "admin_broadcast_failed_users_list": "Liste der Benutzer, die den Bot blockiert haben.",
        "admin_broadcast_cancelled": "Broadcast abgebrochen.",
    },
    "fa": {
        "welcome_message": "به *ربات بلیط کابوک* خوش آمدید!",
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
        "go_to_main_menu": "🏠 بازگشت به منوی اصلی", # ⭐️ NEW
        "back_button": "⬅️ بازگشت", # ⭐️ NEW: Back button for purchase steps

        # --- UX Improvements ---
        "my_tickets_button": "🎟️ بلیط‌های من",
        "help_button": "❓ راهنما",
        "my_tickets_title": "بلیط‌های خریداری شده شما:",
        "my_tickets_none": "شما هنوز هیچ بلیطی خریداری نکرده‌اید.",
        "help_text": """*راهنما*

به ربات فروش بلیط کابوک خوش آمدید! راهنمای سریع:

1. *🎫 خرید بلیط*: لیست رویدادهای فعال را ببینید و بلیط بخرید.
2. *🎶 رویدادهای آینده*: جزئیات رویدادهای بعدی ما را مشاهده کنید.
3. *🗓️ رویدادهای گذشته*: نگاهی به کنسرت‌های قبلی ما بیندازید.
4. *🎟️ بلیط‌های من*: تمام بلیط‌های خریداری شده خود را دوباره اینجا پیدا کنید.
5. *🌐 تغییر زبان*: بین زبان‌های فارسی، آلمانی و کردی انتخاب کنید.
6. *📱 تماس با ما / 📢 شبکه‌های اجتماعی*: با ما در تماس باشید یا ما را دنبال کنید.

در صورت بروز مشکل، از طریق دکمه *تماس با ما* به پشتیبانی پیام دهید.""",

        # --- Automation ---
        "event_reminder_message": "🔔 *یادآوری!*\n\nرویداد '{event_name}' شما فردا برگزار می‌شود!\n\nمشتاق دیدار شما هستیم!",
        "post_event_survey_message": "امیدواریم در رویداد '{event_name}' به شما خوش گذشته باشد!\n\nبه این رویداد چه امتیازی می‌دهید؟",
        "survey_thanks": "از بازخورد شما متشکریم!",
        "survey_already_voted": "شما قبلاً به این رویداد امتیاز داده‌اید. متشکریم!",
        "survey_rating_1": "⭐️",
        "bot_feedback_prompt": "از خدمات ربات بلیط کابوک چقدر رضایت دارید؟",
        "stop_bot_warning": "⚠️ *توجه!* ⚠️\n\nبا توقف ربات یا پاک کردن تاریخچه، اطلاعات شما شامل بلیط‌های خریداری شده و وضعیت وفاداری برای همیشه حذف خواهد شد و دیگر شامل تخفیف‌های وفاداری نخواهید شد.\n\nآیا برای ادامه مطمئن هستید؟",
        "survey_rating_2": "⭐️⭐️",
        "survey_rating_3": "⭐️⭐️⭐️",
        "survey_rating_4": "⭐️⭐️⭐️⭐️",
        "survey_rating_5": "⭐️⭐️⭐️⭐️⭐️",

        "no_events_available": "در حال حاضر هیچ رویدادی برای خرید بلیط موجود نیست.",
        "event_sold_out": "متاسفانه ظرفیت این رویداد تکمیل شده است!",
        "event_caption_format": "*{name}*\n🗓️ تاریخ: {date}\n📍 مکان: {location}\n⏰ ساعت: {time} \n💰 قیمت: {price} یورو\n\n*{description}*",
        "event_caption_no_poster": "(پوستر موجود نیست)",
        # --- Discount Code ---
        "ask_discount_code": "آیا کد تخفیف دارید؟",
        "yes": "بله",
        "no": "خیر",
        "loyalty_discount_applied": "🎉 به عنوان یک مشتری وفادار، شما ۱۰٪ تخفیف برای این خرید دریافت می‌کنید!",
        "ask_ticket_type": "کدام نوع بلیط را می‌خواهید؟",
        "enter_discount_code": "لطفاً کد تخفیف خود را وارد کنید:",
        "discount_invalid": "❌ کد تخفیف نامعتبر یا منقضی شده است.",
        "discount_applied": "✅ کد تخفیف '{code}' اعمال شد!",
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
        "ticket_purchase_summary": """✅ شما می‌خواهید {amount} بلیط برای '{event_name}' بخرید.
مبلغ کل: {total_price} یورو.

لطفاً مبلغ را به حساب بانکی زیر واریز کنید:

*N26 : بانک شما*
*صاحب حساب: Mukhtar Fatahi *
*شماره شبا: DE66100110012264463335*
*سوییفت کد: NTSBDEB1XXX*

<b>توجه:</b> لطفاً کد <code>{reference_code}</code> را به عنوان هدف واریز (Verwendungszweck) وارد نمایید.

پس از واریز، <b>عکس رسید (مانند PDF) یا کد مرجع را برای ما ارسال کنید.</b>

---
<b>تذکر مهم در مورد ارسال بلیط:</b>

* برای دریافت *آنی* بلیط، لطفاً از گزینه <b>واریز آنی (Instant Transfer)</b> استفاده کنید. بلیط‌های شما بلافاصله پس از تأیید ارسال می‌شوند.
* در صورت استفاده از واریز عادی، واریز مبلغ معمولاً ۱ تا ۲ روز کاری طول می‌کشد. ارسال بلیط تنها پس از دریافت مبلغ و بررسی دستی توسط ادمین امکان‌پذیر است.""",
        "unrecognized_message": "متاسفم، متوجه نشدم. لطفاً از دکمه‌ها استفاده کنید یا با /start شروع کنید.",
        "start_bot_prompt": "لطفاً ربات را با /start شروع کنید.",
        "language_select_prompt": "🌐 لطفاً زبان خود را انتخاب کنید:",
        "language_changed": "زبان به فارسی تغییر یافت.",

        "admin_sales_report_title": "--- گزارش فروش بلیط ---",
        "admin_no_sales_found": "هنوز هیچ بلیطی فروخته نشده یا درخواست باز وجود ندارد.",
        "admin_sales_item": "<b>{index}. خریدار:</b> {name} (@{username})\n<b>رویداد:</b> {event_name}\n<b>تعداد بلیط:</b> {amount}\n<b>وضعیت:</b> {status}\n<b>تاریخ:</b> {date}",
        "admin_sales_status_pending": "در انتظار پرداخت ⏳",
        "admin_sales_status_issued": "پرداخت شده ✅",

        "payment_proof_received": "✅ مدرک پرداخت (عکس/فایل) دریافت شد. در حال ارسال برای بررسی ادمین...",
        "payment_proof_forwarded": "👆 بەڵگەی پارەدانی کڕیار لە پەیامی سەرەوەدایە.",
    },
    "fa": {
        "welcome_message": "به *ربات بلیط کابوک* خوش آمدید!",
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
        "go_to_main_menu": "🏠 بازگشت به منوی اصلی", # ⭐️ NEW
        "back_button": "⬅️ بازگشت", # ⭐️ NEW: Back button for purchase steps

        # --- UX Improvements ---
        "my_tickets_button": "🎟️ بلیط‌های من",
        "help_button": "❓ راهنما",
        "my_tickets_title": "بلیط‌های خریداری شده شما:",
        "my_tickets_none": "شما هنوز هیچ بلیطی خریداری نکرده‌اید.",
        "help_text": """*راهنما*

به ربات فروش بلیط کابوک خوش آمدید! راهنمای سریع:

1. *🎫 خرید بلیط*: لیست رویدادهای فعال را ببینید و بلیط بخرید.
2. *🎶 رویدادهای آینده*: جزئیات رویدادهای بعدی ما را مشاهده کنید.
3. *🗓️ رویدادهای گذشته*: نگاهی به کنسرت‌های قبلی ما بیندازید.
4. *🎟️ بلیط‌های من*: تمام بلیط‌های خریداری شده خود را دوباره اینجا پیدا کنید.
5. *🌐 تغییر زبان*: بین زبان‌های فارسی، آلمانی و کردی انتخاب کنید.
6. *📱 تماس با ما / 📢 شبکه‌های اجتماعی*: با ما در تماس باشید یا ما را دنبال کنید.

در صورت بروز مشکل، از طریق دکمه *تماس با ما* به پشتیبانی پیام دهید.""",

        # --- Automation ---
        "event_reminder_message": "🔔 *یادآوری!*\n\nرویداد '{event_name}' شما فردا برگزار می‌شود!\n\nمشتاق دیدار شما هستیم!",
        "post_event_survey_message": "امیدواریم در رویداد '{event_name}' به شما خوش گذشته باشد!\n\nبه این رویداد چه امتیازی می‌دهید؟",
        "survey_thanks": "از بازخورد شما متشکریم!",
        "survey_already_voted": "شما قبلاً به این رویداد امتیاز داده‌اید. متشکریم!",
        "survey_rating_1": "⭐️",
        "bot_feedback_prompt": "از خدمات ربات بلیط کابوک چقدر رضایت دارید؟",
        "stop_bot_warning": "⚠️ *توجه!* ⚠️\n\nبا توقف ربات یا پاک کردن تاریخچه، اطلاعات شما شامل بلیط‌های خریداری شده و وضعیت وفاداری برای همیشه حذف خواهد شد و دیگر شامل تخفیف‌های وفاداری نخواهید شد.\n\nآیا برای ادامه مطمئن هستید؟",
        "survey_rating_2": "⭐️⭐️",
        "survey_rating_3": "⭐️⭐️⭐️",
        "survey_rating_4": "⭐️⭐️⭐️⭐️",
        "survey_rating_5": "⭐️⭐️⭐️⭐️⭐️",

        "no_events_available": "در حال حاضر هیچ رویدادی برای خرید بلیط موجود نیست.",
        "event_sold_out": "متاسفانه ظرفیت این رویداد تکمیل شده است!",
        "event_caption_format": "*{name}*\n🗓️ تاریخ: {date}\n📍 مکان: {location}\n⏰ ساعت: {time} \n💰 قیمت: {price} یورو\n\n*{description}*",
        "event_caption_no_poster": "(پوستر موجود نیست)",
        # --- Discount Code ---
        "ask_discount_code": "آیا کد تخفیف دارید؟",
        "yes": "بله",
        "no": "خیر",
        "loyalty_discount_applied": "🎉 به عنوان یک مشتری وفادار، شما ۱۰٪ تخفیف برای این خرید دریافت می‌کنید!",
        "ask_ticket_type": "کدام نوع بلیط را می‌خواهید؟",
        "enter_discount_code": "لطفاً کد تخفیف خود را وارد کنید:",
        "discount_invalid": "❌ کد تخفیف نامعتبر یا منقضی شده است.",
        "discount_applied": "✅ کد تخفیف '{code}' اعمال شد!",
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
        "ticket_purchase_summary": """✅ شما می‌خواهید {amount} بلیط برای '{event_name}' بخرید.
مبلغ کل: {total_price} یورو.

لطفاً مبلغ را به حساب بانکی زیر واریز کنید:

*نام بانک: N26 *
*صاحب حساب: Mukhtar Fatahi*
*شماره شبا: DE66100110012264463335*
*سوییفت کد: NTSBDEB1XXX*

<b>توجه:</b> لطفاً کد <code>{reference_code}</code> را به عنوان هدف واریز (Verwendungszweck) وارد نمایید.

پس از واریز، <b>عکس رسید (مانند PDF) یا کد مرجع را برای ما ارسال کنید.</b>

---
<b>تذکر مهم در مورد ارسال بلیط:</b>

* برای دریافت *آنی* بلیط، لطفاً از گزینه <b>واریز آنی (Instant Transfer)</b> استفاده کنید. بلیط‌های شما بلافاصله پس از تأیید ارسال می‌شوند.
* در صورت استفاده از واریز عادی، واریز مبلغ معمولاً ۱ تا ۲ روز کاری طول می‌کشد. ارسال بلیط تنها پس از دریافت مبلغ و بررسی دستی توسط ادمین امکان‌پذیر است.""",
        "unrecognized_message": "متاسفم، متوجه نشدم. لطفاً از دکمه‌ها استفاده کنید یا با /start شروع کنید.",
        "start_bot_prompt": "لطفاً ربات را با /start شروع کنید.",
        "language_select_prompt": "🌐 لطفاً زبان خود را انتخاب کنید:",
        "language_changed": "زبان به فارسی تغییر یافت.",

        "admin_sales_report_title": "--- گزارش فروش بلیط ---",
        "admin_no_sales_found": "هنوز هیچ بلیطی فروخته نشده یا درخواست باز وجود ندارد.",
        "admin_sales_item": "<b>{index}. خریدار:</b> {name} (@{username})\n<b>رویداد:</b> {event_name}\n<b>تعداد بلیط:</b> {amount}\n<b>وضعیت:</b> {status}\n<b>تاریخ:</b> {date}",
        "admin_sales_status_pending": "در انتظار پرداخت ⏳",
        "admin_sales_status_issued": "پرداخت شده ✅",

        "payment_proof_received": "✅ مدرک پرداخت (عکس/فایل) دریافت شد. در حال ارسال برای بررسی ادمین...",
        "payment_proof_forwarded": "👆 مدرک واریزی کاربر در پیام بالاست.",

        # --- Admin Event Management ---
        "admin_addevent_start": "در حال افزودن رویداد جدید. لطفاً نام رویداد را وارد کنید:",
        "admin_addevent_name_received": "نام '{name}' ثبت شد. لطفاً تاریخ و زمان را وارد کنید (فرمت: YYYY-MM-DD HH:MM):",
        "admin_addevent_datetime_received": "تاریخ '{date}' ثبت شد. لطفاً مکان رویداد را وارد کنید:",
        "admin_addevent_location_received": "مکان '{location}' ثبت شد. لطفاً قیمت را به یورو وارد کنید (فقط عدد):",
        "admin_addevent_price_received": "قیمت {price} یورو ثبت شد. لطفاً توضیحات چندزبانه را وارد کنید:\nفرمت: `de:Text|fa:Text|ckb:Text`",
        "admin_addevent_description_received": "توضیحات دریافت شد. لطفاً پوستر رویداد را آپلود کنید.",
        "admin_addevent_poster_received": "پوستر دریافت شد. آیا رویداد بلافاصله فعال شود؟ (بله/خیر)",
        "admin_addevent_success": "✅ رویداد '{name}' با موفقیت ایجاد و ذخیره شد!",
        "admin_addevent_cancel": "عملیات افزودن رویداد لغو شد.",
        "admin_invalid_date": "فرمت تاریخ نامعتبر است. لطفاً از YYYY-MM-DD HH:MM استفاده کنید.",
        "admin_invalid_price": "قیمت نامعتبر است. لطفاً یک عدد وارد کنید.",
        "admin_invalid_yes_no": "ورودی نامعتبر است. لطفاً با 'بله' یا 'خیر' پاسخ دهید.",

        # --- Admin Menu ---
        "admin_menu_title": "⚙️ منوی ادمین ⚙️\nچه کاری می‌خواهید انجام دهید؟",
        "admin_menu_add_event": "➕ افزودن رویداد",
        "admin_menu_edit_event": "✏️ ویرایش رویداد",
        "admin_menu_archive_event": "🗂️ آرشیو/حذف رویداد",
        "admin_menu_export_csv": "📄 خروجی CSV فروش",
        "admin_menu_survey_report": "📊 گزارش نظرسنجی",
        "admin_menu_sales_report": "📊 گزارش فروش",

        # --- Admin Edit Event ---
        "admin_editevent_select": "کدام رویداد را می‌خواهید ویرایش کنید؟",
        "admin_editevent_no_events": "هیچ رویدادی برای ویرایش یافت نشد.",
        "admin_editevent_selected": "در حال ویرایش '{name}'. چه چیزی را می‌خواهید تغییر دهید؟",
        "admin_editevent_ask_new_value": "لطفاً مقدار جدید برای '{field}' را وارد کنید.",
        "admin_editevent_ask_new_poster": "لطفاً پوستر جدید را آپلود کنید.",
        "admin_editevent_updated": "✅ فیلد '{field}' برای رویداد '{name}' به‌روزرسانی شد.",
        "admin_editevent_done": "ویرایش به پایان رسید. در حال بازگشت به منوی ادمین.",
        "admin_editevent_cancel": "ویرایش لغو شد.",

        # --- Admin Archive/Delete Event ---
        "admin_archive_select": "کدام رویداد را می‌خواهید مدیریت کنید؟",
        "admin_archive_menu": "عملیات برای '{name}':",
        "admin_archive_button": "آرشیو کردن (انتقال به گذشته)",
        "admin_delete_button": "حذف کردن",
        "admin_archive_success": "✅ رویداد '{name}' آرشیو شد.",
        "admin_delete_confirm": "آیا مطمئن هستید که می‌خواهید '{name}' را برای همیشه حذف کنید؟ تمام بلیط‌های مرتبط نیز حذف خواهند شد. این عمل قابل بازگشت نیست.",
        "admin_delete_success": "🗑️ رویداد '{name}' برای همیشه حذف شد.",

        # --- Admin Discount Codes ---
        "admin_menu_discounts": "🎟️ مدیریت کدهای تخفیف",
        "admin_discounts_menu_title": "مدیریت کدهای تخفیف",
        "admin_discounts_create": "ایجاد جدید",
        "admin_discounts_view": "مشاهده همه",
        "admin_discounts_delete": "حذف کردن",
        "admin_discounts_ask_code": "کد جدید را وارد کنید (مثال: SUMMER20):",
        "admin_discounts_ask_type": "نوع تخفیف را انتخاب کنید:",
        "admin_discounts_ask_value": "مقدار را وارد کنید (مثال: '10' برای ۱۰٪ یا '5' برای ۵ یورو):",
        "admin_discounts_ask_max_uses": "این کد چند بار قابل استفاده است؟",
        "admin_discounts_view_title": "--- کدهای تخفیف موجود ---",
        "admin_discounts_view_item": "<b>کد:</b> <code>{code}</code>\n<b>نوع:</b> {type}\n<b>مقدار:</b> {value}\n<b>استفاده شده:</b> {uses}/{max_uses}\n<b>فعال:</b> {active}\n",
        "admin_discounts_none": "هیچ کد تخفیفی یافت نشد.",
        "admin_discounts_delete_prompt": "کدام کد را می‌خواهید حذف کنید؟ لطفاً نام کد را ارسال کنید.",
        "admin_discounts_success": "✅ کد تخفیف '{code}' ایجاد شد.",
        "admin_addevent_ask_vip": "آیا این رویداد بخش VIP دارد؟ (بله/خیر)",
        "admin_addevent_ask_vip_price": "بسیار خب. لطفاً قیمت VIP را به یورو وارد کنید:",
        "admin_addevent_ask_vip_description": "بسیار خب. قیمت VIP {price} یورو است. لطفاً توضیحات چندزبانه VIP را وارد کنید (فرمت: de:Text|fa:Text):",

        # --- Admin Event Capacity ---
        "admin_addevent_capacity_received": "بسیار خب. ظرفیت {capacity} است. لطفاً توضیحات چندزبانه را وارد کنید:\nفرمت: `de:Text|fa:Text|ckb:Text`",
        "admin_addevent_ask_capacity": "بسیار خب. قیمت {price} یورو است. لطفاً ظرفیت رویداد را مشخص کنید (عدد، یا '0' برای نامحدود):",
        "admin_addevent_ask_desc_de": "بسیار خب. ظرفیت {capacity} است. لطفاً توضیحات آلمانی را وارد کنید:",
        "admin_addevent_ask_desc_fa": "بسیار خب. لطفاً توضیحات فارسی را وارد کنید:",
        "admin_addevent_ask_desc_ckb": "بسیار خب. لطفاً توضیحات کردی را وارد کنید:",

        # --- Check-in System ---
        "checkin_start": "✅ حالت چک-این فعال شد.\nلطفاً QR کد بلیط را اسکن کنید یا شناسه بلیط را ارسال کنید.",
        "checkin_cancel": "حالت چک-این غیرفعال شد.",
        "checkin_invalid_id": "❌ شناسه بلیط نامعتبر است.",
        "checkin_not_found": "❌ بلیط یافت نشد.",
        "checkin_not_issued": "❌ بلیط نامعتبر است (وضعیت: {status}).\nصاحب بلیط: {name}\nرویداد: {event}",
        "checkin_already_used": "❌ این بلیط قبلاً استفاده شده است!\nتاریخ چک-این: {date}\nصاحب بلیط: {name}\nرویداد: {event}",
        "checkin_success": "✅ بلیط معتبر است! خوش آمدید!\nصاحب بلیط: {name}\nرویداد: {event}",
        "checkin_wrong_event": "❌ این بلیط برای رویداد دیگری است!\nبلیط برای: {ticket_event}\nرویداد فعلی: {current_event}",
        "checkin_select_event": "برای کدام رویداد می‌خواهید بلیط‌ها را چک کنید؟",

        # --- Admin Survey Report ---
        "admin_survey_report_title": "--- نتایج نظرسنجی ---",
        "admin_survey_export_csv": "📄 خروجی CSV نظرسنجی‌ها",
        "admin_survey_report_item": "<b>{event_name}</b>:\n- میانگین امتیاز: {avg_rating:.1f} / 5 ⭐ ({vote_count} رأی)\n",
        "admin_survey_no_surveys": "هنوز هیچ نظرسنجی پاسخ داده نشده است.",

        # --- Admin Broadcast ---
        "admin_menu_broadcast": "📣 ارسال پیام همگانی",
        "admin_broadcast_start": "لطفاً پیامی که می‌خواهید به تمام کاربران ارسال شود را بفرستید. می‌توانید متن، عکس، ویدیو و... ارسال کنید.",
        "admin_broadcast_confirm": "آیا این پیام به تمام کاربران ارسال شود؟",
        "admin_broadcast_sending": "⏳ در حال ارسال پیام همگانی... این ممکن است کمی طول بکشد.",
        "admin_broadcast_success_report": "✅ ارسال پیام همگانی تمام شد.\nارسال موفق: {success_count} کاربر.\nارسال ناموفق: {failed_count} کاربر.",
        "admin_broadcast_failed_users_list": "لیست کاربرانی که ربات را بلاک کرده‌اند.",
        "admin_broadcast_cancelled": "ارسال پیام همگانی لغو شد.",
    },
    "ckb": { # کوردی سورانی (CKB)
        "welcome_message": "بەخێربێن بۆ *بۆتی بلیتەکانی کابوک*!",
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
        "go_to_main_menu": "🏠 گەڕانەوە بۆ لیستی سەرەکی", # ⭐️ NEW
        "back_button": "⬅️ گەڕانەوە", # ⭐️ NEW: Back button for purchase steps

        # --- UX Improvements ---
        "my_tickets_button": "🎟️ بلیتەکانم",
        "help_button": "❓ ڕێنمایی",
        "my_tickets_title": "بلیتە کڕدراوەکانت:",
        "my_tickets_none": "تۆ هێشتا هیچ بلیتێکت نەکڕیوە.",
        "help_text": """*یارمەتی و ڕێنمایی*

بەخێربێیت بۆ بۆتی بلیتەکانی کابوک! ئەمە ڕێنماییەکی خێرایە:

1. *🎫 کڕینی بلیت*: ئەمە هەڵبژێرە بۆ بینینی لیستی بۆنە چالاکەکان و کڕینی بلیت.
2. *🎶 بۆنە داهاتووەکان*: وردەکاری بۆنە داهاتووەکانمان ببینە.
3. *🗓️ بۆنە کۆنەکان*: سەیرێکی کۆنسێرتە ڕابردووەکانمان بکە.
4. *🎟️ بلیتەکانم*: لێرەدا دەتوانیت هەموو بلیتە کڕدراوەکانت بدۆزیتەوە.
5. *🌐 گۆڕینی زمان*: لە نێوان زمانەکانی کوردی، ئەڵمانی و فارسیدا هەڵبژێرە.
6. *📱 پەیوەندی / 📢 سۆشیال میدیا*: پەیوەندیمان پێوە بکە یان لە کەناڵەکانماندا فۆڵۆمان بکە.

ئەگەر کێشەیەکت هەبوو، تکایە لە ڕێگەی دوگمەی *پەیوەندی*یەوە پەیوەندی بە پشتیوانییەوە بکە.""",

        # --- Automation ---
        "event_reminder_message": "🔔 *بیرخستنەوە!*\n\nبۆنەکەت '{event_name}' سبەی بەڕێوەدەچێت!\n\nبەخۆشحاڵییەوە چاوەڕێتانین!",
        "post_event_survey_message": "هیوادارین کاتێکی خۆشت لە بۆنەی '{event_name}' بەسەر بردبێت!\n\nچەند ئەستێرە بەم بۆنەیە دەدەیت؟",
        "survey_thanks": "سوپاس بۆ پێداچوونەوەکەت!",
        "survey_already_voted": "تۆ پێشتر دەنگت بەم بۆنەیە داوە. سوپاس!",
        "survey_rating_1": "⭐️",
        "bot_feedback_prompt": "چەند لە خزمەتگوزاریی بۆتی بلیتەکانی کابوک ڕازیت؟",
        "stop_bot_warning": "⚠️ *ئاگاداری!* ⚠️\n\nبە ڕاگرتنی بۆت یان سڕینەوەی مێژوو، زانیارییەکانت لەوانە بلیتە کڕدراوەکان و دۆخی وەفادارییت بۆ هەمیشە دەسڕدرێتەوە و چیتر داشکاندنی وەفاداریت نابێت.\n\nدڵنیایت لە بەردەوامبوون؟",
        "survey_rating_2": "⭐️⭐️",
        "survey_rating_3": "⭐️⭐️⭐️",
        "survey_rating_4": "⭐️⭐️⭐️⭐️",
        "survey_rating_5": "⭐️⭐️⭐️⭐️⭐️",

        "no_events_available": "لە ئێستادا هیچ بۆنەیەک بۆ کڕین بەردەست نییە.",
        "event_sold_out": "بەداخەوە، توانای ئەم بۆنەیە پڕ بووەتەوە!",
        "event_caption_format": "*{name}*\n🗓️ ڕێکەوت: {date}\n📍 شوێن: {location}\n⏰ کات: {time}\n💰 نرخ: {price} یۆرۆ\n\n*{description}*",
        "event_caption_no_poster": "(پۆستەر نییە)",
        # --- Discount Code ---
        "ask_discount_code": "کۆدی داشکاندنت هەیە؟",
        "yes": "بەڵێ",
        "no": "نەخێر",
        "loyalty_discount_applied": "🎉 وەک کڕیارێکی بەوەفا، ١٠٪ داشکاندن بۆ ئەم کڕینە وەردەگریت!",
        "ask_ticket_type": "کام جۆر بلیتت دەوێت؟",
        "enter_discount_code": "تکایە کۆدی داشکاندنەکەت بنووسە:",
        "discount_invalid": "❌ کۆدی داشکاندنی نادروست یان بەسەرچوو.",
        "discount_applied": "✅ کۆدی داشکاندنی '{code}' جێبەجێ کرا!",
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
        "payment_request_admin": "💰 داواکاری پارەدانی نوێ بۆ بلیت:\nناو: {name}\nناوی بەکارهێنەر: @{username}\nناسنامەی بەکارهێنەر: {user_id}\nبۆنە: {event_name}\n<b>مەبەستی پارەدان/کۆدی ئاماژە:</b> {reference_code}\n\n<b>{notes}</b>",
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
        "ticket_purchase_summary": """✅ تۆ دەتەوێت {amount} بلیت بۆ '{event_name}' بکڕیت.
نرخی گشتی: {total_price} یۆرۆ.

لطفاً مبلغ را به حساب بانکی زیر واریز کنید:

*N26 : بانکی تۆ*
*صاحب حساب:  Mukhtar Fatahi*
*شماره شبا: DE66100110012264463335*
*سوییفت کد: NTSBDEB1XXX*

<b>توجه:</b> لطفاً کد <code>{reference_code}</code> وەکو مەبەستی پارەدان (Verwendungszweck) وارد نمایید.

پس از واریز، <b>عکس رسید (مانند PDF) یا کد مرجع را برای ما ارسال کنید.</b>

---
<b>تێبینی گرنگ سەبارەت بە ناردنی بلیت:</b>

* بۆ وەرگرتنی *دەستبەجێ*ی بلیت، تکایە لە گواستنەوەی <b>دەستبەجێ (Instant Transfer)</b> بەکاربهێنە. بلیتەکانت ڕاستەوخۆ دوای پشتڕاستکردنەوە دەنێردرێن.
* لە ئەگەری بەکارهێنانی گواستنەوەی ئاسایی، وەرگرتنی پارەکە بەزۆری ١-٢ ڕۆژی کارکردن دەخایەنێت. بلیتەکان تەنها دوای وەرگرتنی پارە و پشکنینی دەستی لەلایەن ئەدمینەوە دەتوانرێن بنێردرێن.""",

        "admin_sales_report_title": "--- ڕاپۆرتی فرۆش ---",
        "admin_no_sales_found": "تا ئێستا هیچ بلیتێک نەفرۆشراوە یان داواکارییەکی کراوە نییە.",
        "admin_sales_item": "<b>{index}. کڕیار:</b> {name} (@{username})\n<b>بۆنە:</b> {event_name}\n<b>ژمارەی بلیت:</b> {amount}\n<b>دۆخ:</b> {status}\n<b>ڕێکەوت:</b> {date}",
        "admin_sales_status_pending": "چاوەڕوانیی پارەدان ⏳",
        "admin_sales_status_issued": "پارە دراوە ✅",

        "payment_proof_received": "✅ مدرک پرداخت (عکس/فایل) دریافت شد. در حال ارسال برای بررسی ادمین...",
        "payment_proof_forwarded": "👆 بەڵگەی پارەدانی کڕیار لە پەیامی سەرەوەدایە.",

        # --- Admin (Kurdish) ---
        "admin_sales_report_title": "--- ڕاپۆرتی فرۆشتن ---",
        "admin_no_sales_found": "هێشتا هیچ بلیتێک نەفرۆشراوە یان داواکاری کراوە نییە.",
        "admin_sales_item": "<b>{index}. کڕیار:</b> {name} (@{username})\n<b>بۆنە:</b> {event_name}\n<b>ژمارەی بلیت:</b> {amount}\n<b>دۆخ:</b> {status}\n<b>ڕێکەوت:</b> {date}",
        "admin_sales_status_pending": "چاوەڕوانی پارەدان ⏳",
        "admin_sales_status_issued": "پارە دراوە ✅",
        "admin_addevent_start": "زیادکردنی بۆنەیەکی نوێ. تکایە ناوی بۆنەکە بنووسە:",
        "admin_addevent_name_received": "ناو '{name}' تۆمارکرا. تکایە ڕێکەوت و کات بنووسە (فۆرمات: YYYY-MM-DD HH:MM):",
        "admin_addevent_datetime_received": "ڕێکەوت '{date}' تۆمارکرا. تکایە شوێنی بۆنەکە بنووسە:",
        "admin_addevent_location_received": "شوێن '{location}' تۆمارکرا. تکایە نرخ بە یۆرۆ بنووسە (تەنها ژمارە):",
        "admin_addevent_price_received": "نرخ {price} یۆرۆ تۆمارکرا. تکایە وەسفی فرەزمان بنووسە:\nفۆرمات: `de:Text|fa:Text|ckb:Text`",
        "admin_addevent_description_received": "وەسف وەرگیرا. تکایە ئێستا پۆستەری بۆنەکە باربکە.",
        "admin_addevent_poster_received": "پۆستەر وەرگیرا. ئایا بۆنەکە دەستبەجێ چالاک بکرێت؟ (بەڵێ/نەخێر)",
        "admin_addevent_success": "✅ بۆنەی '{name}' بە سەرکەوتوویی دروستکرا و پاشەکەوت کرا!",
        "admin_addevent_cancel": "کرداری زیادکردنی بۆنە هەڵوەشایەوە.",
        "admin_invalid_date": "فۆرماتی ڕێکەوتی نادروست. تکایە YYYY-MM-DD HH:MM بەکاربهێنە.",
        "admin_invalid_price": "نرخی نادروست. تکایە ژمارەیەک بنووسە.",
        "admin_invalid_yes_no": "نووسراوی نادروست. تکایە بە 'بەڵێ' یان 'نەخێر' وەڵام بدەوە.",
        "admin_menu_title": "⚙️ لیستی ئەدمین ⚙️\nدەتەوێت چی بکەیت؟",
        "admin_menu_add_event": "➕ زیادکردنی بۆنە",
        "admin_menu_edit_event": "✏️ دەستکاریکردنی بۆنە",
        "admin_menu_archive_event": "🗂️ ئەرشیڤ/سڕینەوەی بۆنە",
        "admin_menu_export_csv": "📄 هەناردەکردنی فرۆش (CSV)",
        "admin_menu_survey_report": "📊 ڕاپۆرتی ڕاپرسی",
        "admin_menu_sales_report": "📊 ڕاپۆرتی فرۆشتن",
        "admin_editevent_select": "کام بۆنە دەتەوێت دەستکاری بکەیت؟",
        "admin_editevent_no_events": "هیچ بۆنەیەک بۆ دەستکاریکردن نەدۆزرایەوە.",
        "admin_editevent_selected": "تۆ لە حالەتی دەستکاریکردنی '{name}'. دەتەوێت چی بگۆڕیت؟",
        "admin_editevent_ask_new_value": "تکایە بەهای نوێ بۆ '{field}' بنووسە.",
        "admin_editevent_ask_new_poster": "تکایە پۆستەری نوێ باربکە.",
        "admin_editevent_updated": "✅ فیلدی '{field}' بۆ بۆنەی '{name}' نوێکرایەوە.",
        "admin_editevent_done": "دەستکاریکردن تەواو بوو. دەگەڕێیتەوە بۆ لیستی ئەدمین.",
        "admin_editevent_cancel": "دەستکاریکردن هەڵوەشایەوە.",
        "admin_archive_select": "کام بۆنە دەتەوێت بەڕێوەی ببەیت؟",
        "admin_archive_menu": "کردار بۆ '{name}':",
        "admin_archive_button": "ئەرشیڤکردن (گواستنەوە بۆ ڕابردوو)",
        "admin_delete_button": "سڕینەوە",
        "admin_archive_success": "✅ بۆنەی '{name}' ئەرشیڤ کرا.",
        "admin_delete_confirm": "دڵنیایت دەتەوێت '{name}' بۆ هەمیشە بسڕیتەوە؟ هەموو بلیتە پەیوەندیدارەکانیش دەسڕدرێنەوە. ئەم کردارە ناتوانرێت بگەڕێندرێتەوە.",
        "admin_delete_success": "🗑️ بۆنەی '{name}' بۆ هەمیشە سڕایەوە.",
        "admin_menu_discounts": "🎟️ بەڕێوەبردنی کۆدی داشکاندن",
        "admin_discounts_menu_title": "بەڕێوەبردنی کۆدی داشکاندن",
        "admin_discounts_create": "دروستکردنی نوێ",
        "admin_discounts_view": "بینینی هەموو",
        "admin_discounts_delete": "سڕینەوە",
        "admin_discounts_ask_code": "کۆدی نوێ بنووسە (بۆ نموونە: SUMMER20):",
        "admin_discounts_ask_type": "جۆری داشکاندن هەڵبژێرە:",
        "admin_discounts_ask_value": "بەهاکەی بنووسە (بۆ نموونە: '10' بۆ ١٠٪ یان '5' بۆ ٥ یۆرۆ):",
        "admin_discounts_ask_max_uses": "ئەم کۆدە چەند جار دەتوانرێت بەکاربهێنرێت؟",
        "admin_discounts_view_title": "--- کۆدە داشکاندنە بەردەستەکان ---",
        "admin_discounts_view_item": "<b>کۆد:</b> <code>{code}</code>\n<b>جۆر:</b> {type}\n<b>بەها:</b> {value}\n<b>بەکارهێنراو:</b> {uses}/{max_uses}\n<b>چالاک:</b> {active}\n",
        "admin_discounts_none": "هیچ کۆدێکی داشکاندن نەدۆزرایەوە.",
        "admin_discounts_delete_prompt": "کام کۆد دەتەوێت بسڕیتەوە؟ تکایە ناوی کۆدەکە بنێرە.",
        "admin_discounts_success": "✅ کۆدی داشکاندنی '{code}' دروستکرا.",
        "admin_addevent_ask_vip": "ئایا ئەم بۆنەیە بەشی VIPی هەیە؟ (بەڵێ/نەخێر)",
        "admin_addevent_ask_vip_price": "باشە. تکایە نرخی VIP بە یۆرۆ بنووسە:",
        "admin_addevent_ask_vip_description": "باشە. نرخی VIP {price} یۆرۆیە. تکایە وەسفی فرەزمانی VIP بنووسە (فۆرمات: de:Text|fa:Text):",
        "admin_addevent_ask_desc_de": "باشە. توانای {capacity}ـە. تکایە وەسفی ئەڵمانی بنووسە:",
        "admin_addevent_ask_desc_fa": "باشە. تکایە وەسفی فارسی بنووسە:",
        "admin_addevent_ask_desc_ckb": "باشە. تکایە وەسفی کوردی بنووسە:",
        "checkin_start": "✅ دۆخی چێک-ین چالاک کرا.\nتکایە کیو-ئاڕ کۆدی بلیتەکە سکان بکە یان ناسنامەی بلیتەکە بنێرە.",
        "checkin_cancel": "دۆخی چێک-ین ناچالاک کرا.",
        "checkin_invalid_id": "❌ ناسنامەی بلیت نادروستە.",
        "checkin_not_found": "❌ بلیت نەدۆزرایەوە.",
        "checkin_not_issued": "❌ بلیت نادروستە (دۆخ: {status}).\nخاوەن: {name}\nبۆنە: {event}",
        "checkin_already_used": "❌ ئەم بلیتە پێشتر بەکارهێنراوە!\nچێک-ین کراوە لە: {date}\nخاوەن: {name}\nبۆنە: {event}",
        "checkin_success": "✅ بلیت دروستە! بەخێربێیت!\nخاوەن: {name}\nبۆنە: {event}",
        "checkin_wrong_event": "❌ بلیت بۆ بۆنەیەکی ترە!\nبلیت بۆ: {ticket_event}\nبۆنەی ئێستا: {current_event}",
        "checkin_select_event": "بۆ کام بۆنە دەتەوێت بلیتەکان چێک بکەیت؟",
        "admin_survey_report_title": "--- ئەنجامی ڕاپرسییەکان ---",
        "admin_survey_export_csv": "📄 هەناردەکردنی ئەنجامی ڕاپرسییەکان (CSV)",
        "admin_survey_report_item": "<b>{event_name}</b>:\n- تێکڕای هەڵسەنگاندن: {avg_rating:.1f} / 5 ⭐ ({vote_count} دەنگ)\n",
        "admin_survey_no_surveys": "هێشتا هیچ ڕاپرسییەک وەڵام نەدراوەتەوە.",
        "admin_menu_broadcast": "📣 ناردنی پەیامی گشتی",
        "admin_broadcast_start": "تکایە ئەو پەیامە بنێرە کە دەتەوێت بۆ هەموو بەکارهێنەرانی بنێریت. دەتوانیت دەق، وێنە، ڤیدیۆ و هتد بنێریت.",
        "admin_broadcast_confirm": "ئایا ئەم پەیامە بەڕاستی بۆ هەموو بەکارهێنەران بنێردرێت؟",
        "admin_broadcast_sending": "⏳ لە حالەتی ناردنی پەیامی گشتی... ئەمە لەوانەیە کەمێک بخایەنێت.",
        "admin_broadcast_success_report": "✅ ناردنی پەیامی گشتی تەواو بوو.\nنێردرا بۆ: {success_count} بەکارهێنەر.\nشکستی هێنا بۆ: {failed_count} بەکارهێنەر.",
        "admin_broadcast_failed_users_list": "لیستی ئەو بەکارهێنەرانەی کە بۆتەکەیان بلۆک کردووە.",
        "admin_broadcast_cancelled": "ناردنی پەیامی گشتی هەڵوەشایەوە.",
    }
}


# 🆕 تابع برای Escape کردن کاراکترهای خاص Markdown
def escape_markdown_v2(text: str) -> str:
    """Helper function to escape telegram markup symbols."""
    # ⭐️ اصلاح قطعی برای رفع خطاهای سینتکسی IDE با استفاده از لیست استاندارد ⭐️
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    return ''.join('\\' + char if char in escape_chars else char for char in text)


# ➡️ تابع کمکی برای دریافت متن بر اساس زبان کاربر
def get_text(user_language_code, key):
    # Ensure user_language_code is a string key
    if user_language_code not in LANGUAGES:
        user_language_code = "de" # Fallback to German if language code is not recognized

    # First try to get the text for the specific user_language_code
    # If not found, try to get from the default language ("de")
    return LANGUAGES.get(user_language_code, LANGUAGES["de"]).get(key, LANGUAGES["de"][key])

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
    # 🚨 اصلاح: دسترسی مستقیم به کاربر موثر (effective_user) برای پایداری
    user_telegram_id = update.effective_user.id
    user = db.query(User).filter(User.telegram_id == user_telegram_id).first()

    if not user:
        user = User(
            telegram_id=user_telegram_id,
            first_name=update.message.from_user.first_name or "",
            last_name=update.message.from_user.last_name or "",
            username=update.message.from_user.username,
            current_step="start",
            language_code=update.message.from_user.language_code if update.message.from_user.language_code in LANGUAGES else "de"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    user.current_step = "start"
    user.selected_event_id = None
    db.commit()

    user_lang = user.language_code

    # ⭐️⭐️⭐️ 1. ارسال پیام خوشامدگویی با پوستر ⭐️⭐️⭐️
    # پیام خوشامدگویی اصلی (ساده شده برای عدم تکرار)
    welcome_caption = f"""
    به ربات رسمی بلیط کابوک خوش آمدید!

    ما همراه مطمئن شما برای تجربه رویدادها و کنسرت‌های فراموش نشدنی در اروپا هستیم. از طریق ربات ما، می‌توانید بلیط‌های مورد نظر خود را به سرعت و با اطمینان تهیه کنید.

    برای اطلاعات بیشتر، از وب‌سایت ما بازدید کنید:
    🌐 www.kaboukevent.com

    {get_text(user_lang, 'language_select_prompt')}
    """

    welcome_poster_path = "Kabouk_poster.jpg" # اسم فایل پوستر خوشامدگویی

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
        # ارسال عکس خوشامدگویی
        if os.path.exists(welcome_poster_path):
            try:
                with open(welcome_poster_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=user_telegram_id,
                        photo=photo,
                        caption=welcome_caption,
                        parse_mode='HTML'
                    )
            except Exception as e:
                logging.error(f"Error sending welcome photo: {e}")
                await context.bot.send_message(user_telegram_id, welcome_caption, parse_mode='HTML')
        else:
            await context.bot.send_message(user_telegram_id, welcome_caption, parse_mode='HTML')

        # ⭐️⭐️⭐️ 2. نمایش دکمه‌های اصلی و دکمه‌های زبان در Reply Keyboard ⭐️⭐️⭐️

        # دکمه‌های اصلی
        main_keyboard = [
            [KeyboardButton(get_text(user_lang, "ticket_buy_button"))],
            [KeyboardButton(get_text(user_lang, "next_event_button")), KeyboardButton(get_text(user_lang, "past_events_button"))],
            [KeyboardButton(get_text(user_lang, "my_tickets_button")), KeyboardButton(get_text(user_lang, "help_button"))],
            [KeyboardButton(get_text(user_lang, "contact_button")), KeyboardButton(get_text(user_lang, "social_media_button"))],
            [KeyboardButton("فارسی"), KeyboardButton("Deutsch"), KeyboardButton("کوردی")],
            [KeyboardButton(get_text(user_lang, "go_to_main_menu"))]
        ]

        # حذف پیام تکراری آلمانی (این پیام به دلیل send_photo بالای welcome_caption در همان زمان ایجاد شده بود)
        # و فقط یک بار کل منو را ارسال می‌کنیم.

        # ارسال دکمه‌های Reply Keyboard
        await context.bot.send_message(
            chat_id=user_telegram_id,
            text="لطفاً انتخاب کنید:", # پیام نهایی برای نمایش منو
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True),
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

    # 🚨🚨🚨 هندلر برای دکمه‌های زبان در Reply Keyboard 🚨🚨🚨
    if text == "Deutsch":
        await handle_language_change(update, context, db, 'de')
        db.close()
        return
    elif text == "فارسی":
        await handle_language_change(update, context, db, 'fa')
        db.close()
        return
    elif text == "کوردی":
        await handle_language_change(update, context, db, 'ckb')
        db.close()
        return

    # ⭐️ NEW: هندلر برای دکمه بازگشت به خانه (برای همه زبان‌ها)
    # این بلوک باید قبل از بلوک ادمین باشد تا همیشه کار کند.
    if text in [LANGUAGES['de']['go_to_main_menu'],
                 LANGUAGES['fa']['go_to_main_menu'],
                 LANGUAGES['ckb']['go_to_main_menu']]:
        await start(update, context)
        db.close()
        return

    # --- Admin Menu Button Handlers ---
    if chat_id == ADMIN_ID:
        if text == get_text(user_lang, "admin_menu_add_event"):
            await addevent_start(update, context)
            return ConversationHandler.END # End any previous conversation
        elif text == get_text(user_lang, "admin_menu_sales_report"):
            await admin_sales_report(update, context)
            return
        # ⭐️ NEW: Handle Edit Event button
        elif text == get_text(user_lang, "admin_menu_edit_event"):
            await editevent_start(update, context)
            return
        # ⭐️ NEW: Handle Archive/Delete Event button
        elif text == get_text(user_lang, "admin_menu_archive_event"):
            await archive_start(update, context)
            return
        # ⭐️ NEW: Handle Broadcast button
        elif text == get_text(user_lang, "admin_menu_broadcast"):
            await broadcast_start(update, context)
            return
        # ⭐️ NEW: Handle Export CSV button
        elif text == get_text(user_lang, "admin_menu_export_csv"):
            await export_sales_csv(update, context)
            return
        # ⭐️ NEW: Handle Survey Report button
        elif text == get_text(user_lang, "admin_menu_survey_report"):
            await admin_survey_report(update, context)
            return
        # ⭐️ NEW: Handle Survey Export button
        elif text == get_text(user_lang, "admin_survey_export_csv"):
            await export_surveys_csv(update, context)
            return
        # ⭐️ NEW: Handle Discount Codes button
        elif text == get_text(user_lang, "admin_menu_discounts"):
            await discounts_menu(update, context)
            return
        # ⭐️ NEW: Handle discount deletion step
        elif user.current_step == "deleting_discount_code":
            await discount_delete_confirm(update, context, db)
            db.close() # Close session after operation
            return

    # ⭐️⭐️⭐️ NEW: هندلر برای دکمه "بازگشت" در مراحل خرید ⭐️⭐️⭐️
    elif text == get_text(user_lang, "back_button"):
        current_step = user.current_step

        # بازگشت از وارد کردن نام خانوادگی به نام کوچک
        if current_step == "entering_nachname":
            user.current_step = "entering_vorname"
            db.commit()
            await update.message.reply_text(
                get_text(user_lang, "enter_vorname_prompt"),
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "back_button"))]], resize_keyboard=True)
            )

        # بازگشت از وارد کردن تعداد به نام خانوادگی
        elif current_step == "entering_anzahl":
            user.current_step = "entering_nachname"
            db.commit()
            await update.message.reply_text(
                get_text(user_lang, "enter_nachname_prompt"),
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "back_button"))]], resize_keyboard=True)
            )

        # بازگشت از وارد کردن نام کوچک به لیست رویدادها
        elif current_step == "entering_vorname":
            user.current_step = "start" # Reset state
            db.commit()
            await start(update, context) # بازگشت کامل به منوی اصلی

        db.close()
        return


    # 🚨🚨🚨 منطق اصلی پردازش پیام (بالاترین اولویت) 🚨🚨🚨

    if user.current_step == "entering_vorname":
        user.first_name = text
        user.current_step = "entering_nachname"
        db.commit()
        await update.message.reply_text(
            get_text(user_lang, "enter_nachname_prompt"),
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "back_button"))]], resize_keyboard=True)
        )
        db.close()
        return

    elif user.current_step == "entering_nachname":
        user.last_name = text
        user.current_step = "entering_anzahl"
        db.commit()
        await update.message.reply_text(
            get_text(user_lang, "enter_anzahl_prompt"),
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "back_button"))]], resize_keyboard=True)
        )
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
            for _ in range(anzahl):
                ticket_id_str = str(uuid4())
                new_ticket = Ticket(
                    ticket_id_str=ticket_id_str,
                    user_id=user.id,
                    event_id=selected_event.id,
                    status="pending_payment"
                )
                db.add(new_ticket)
            db.commit()

            # گرفتن کد مرجع از اولین بلیطی که ثبت شده (برای نمایش به کاربر)
            first_pending_ticket = db.query(Ticket).filter(
                Ticket.user_id == user.id,
                Ticket.event_id == selected_event.id,
                Ticket.status == "pending_payment"
            ).order_by(Ticket.issue_date.asc()).first()

            reference_code = first_pending_ticket.ticket_id_str if first_pending_ticket else "N/A"

            # 🚨🚨🚨 فراخوانی صحیح متن زمانبندی و کد مرجع 🚨🚨🚨
            summary_text = get_text(user_lang, "ticket_purchase_summary").format(
                amount=anzahl,
                event_name=selected_event.name,
                total_price=anzahl * selected_event.price,
                reference_code=reference_code # 🚨 ارسال کد مرجع به متن خلاصه
            )

            await update.message.reply_text(
                summary_text, parse_mode='HTML',
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "go_to_main_menu"))]], resize_keyboard=True)
            ) # 🚨 استفاده از HTML
            user.current_step = "waiting_for_payment"
            db.commit()

            # ⭐️ NEW: Ask for discount code
            keyboard = [[KeyboardButton(get_text(user_lang, "yes")), KeyboardButton(get_text(user_lang, "no"))]]
            await update.message.reply_text(
                get_text(user_lang, "ask_discount_code"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            )
            user.current_step = "entering_discount_code_choice"
            db.commit()

        except ValueError:
            await update.message.reply_text(get_text(user_lang, "invalid_amount"))
        finally:
            db.close()
        return

    # 🚨🚨🚨 منطق دریافت مدرک پرداخت (عکس، فایل، متن) 🚨🚨🚨
    # ⭐️ NEW: Handle discount code steps
    elif user.current_step == "entering_discount_code_choice":
        if text == get_text(user_lang, "yes"):
            user.current_step = "entering_discount_code"
            db.commit()
            await update.message.reply_text(
                get_text(user_lang, "enter_discount_code"),
                reply_markup=ReplyKeyboardRemove()
            )
        else: # No discount code
            # Finalize purchase without discount
            await finalize_purchase_summary(update, context, user, db)
        db.close()
        return

    elif user.current_step == "entering_discount_code":
        code_text = text.strip().upper()

        # Validate code
        discount_code = db.query(DiscountCode).filter(
            DiscountCode.code == code_text,
            DiscountCode.is_active == True
        ).first()

        valid = False
        if discount_code:
            if discount_code.uses_count < discount_code.max_uses:
                # Check if it's a general code or for the specific event
                if discount_code.event_id is None or discount_code.event_id == user.selected_event_id:
                    valid = True

        if valid:
            await update.message.reply_text(get_text(user_lang, "discount_applied").format(code=code_text))
            # Store applied code in context for final summary
            context.user_data['applied_discount_code_id'] = discount_code.id
            await finalize_purchase_summary(update, context, user, db, discount_code)
        else:
            await update.message.reply_text(get_text(user_lang, "discount_invalid"))
            # Give user another chance or proceed without discount
            await finalize_purchase_summary(update, context, user, db)

        db.close()
        return

    elif user.current_step == "waiting_for_payment":

        latest_pending_ticket = db.query(Ticket).filter(
            Ticket.user_id == user.id,
            Ticket.status == "pending_payment"
        ).order_by(Ticket.issue_date.desc()).first()

        if not latest_pending_ticket:
            await update.message.reply_text(get_text(user_lang, "no_pending_payment"))
            db.close()
            return

        event = db.query(Event).filter(Event.id == latest_pending_ticket.event_id).first()
        reference_code = latest_pending_ticket.ticket_id_str

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
            user.current_step = "payment-sent"
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

            user.current_step = "payment-sent"
            db.commit()

        else:
            await update.message.reply_text(get_text(user_lang, "unrecognized_message"))

        db.close()
        return

    # --- C. پردازش دکمه‌های اصلی منو ---
    elif text == get_text(user_lang, "ticket_buy_button"):
        # ⭐️ NEW: فراخوانی تابع صفحه‌بندی برای رویدادهای فعال
        await list_events_paginated(update, context, event_type='active')
        db.close()
        return

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
        # ⭐️ NEW: فراخوانی تابع صفحه‌بندی برای رویدادهای گذشته
        await list_events_paginated(update, context, event_type='past')
        db.close()
        return

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
        # این دکمه دیگر در منو اصلی نیست، اما اگر به صورت متنی فرستاده شود، منو زبان را نشان می‌دهد
        language_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="set_lang_de")],
            [InlineKeyboardButton("فارسی 🇮🇷", callback_data="set_lang_fa")],
            [InlineKeyboardButton("کوردی 🇮🇶", callback_data="set_lang_ckb")],
        ])
        await update.message.reply_text(get_text(user_lang, "language_select_prompt"), reply_markup=language_keyboard)
        user.current_step = "select_language"
        db.commit()

    # ⭐️ NEW: هندلر برای دکمه بازگشت
    elif text == get_text(user_lang, "go_to_main_menu"):
        await start(update, context)
        db.close()
        return

    # --- D. پردازش پیام‌های خارج از نوبت (اگر متن بود) ---
    elif user.current_step == "waiting_for_payment":

        latest_pending_ticket = db.query(Ticket).filter(
            Ticket.user_id == user.id,
            Ticket.status == "pending_payment"
        ).order_by(Ticket.issue_date.desc()).first()

        if not latest_pending_ticket:
            await update.message.reply_text(get_text(user_lang, "no_pending_payment"))
            db.close()
            return

        event = db.query(Event).filter(Event.id == latest_pending_ticket.event_id).first()
        reference_code = latest_pending_ticket.ticket_id_str

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
            user.current_step = "payment-sent"
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

            user.current_step = "payment-sent"
            db.commit()

        else:
            await update.message.reply_text(get_text(user_lang, "unrecognized_message"))

        db.close()
        return

    # --- C. پردازش دکمه‌های اصلی منو ---
    elif update.message.text and update.message.text.lower() == get_text(user_lang, "payment_received_text").lower():
        # اگر کاربر پیام قدیمی را تایپ کرد
        await update.message.reply_text("لطفاً به جای تایپ کردن، عکس رسید یا کد مرجع را برای ما ارسال کنید تا پرداخت شما تأیید شود.")

    else:
        await update.message.reply_text(get_text(user_lang, "unrecognized_message"))

    db.close()

# 🆕 --- تابع کمکی برای نهایی کردن خلاصه خرید ---
async def finalize_purchase_summary(update: Update, context: CallbackContext, user: User, db: Session, discount_code: DiscountCode = None):
    """محاسبه قیمت نهایی با/بدون تخفیف و نمایش خلاصه."""

    # We need to find out how many tickets the user is buying.
    # This is a bit tricky as we don't have the number directly.
    # Let's assume the last message in the 'entering_anzahl' step was the number.
    # This is not robust. A better way is to save 'anzahl' in user_data.
    # For now, let's just proceed and calculate based on pending tickets.

    pending_tickets = db.query(Ticket).filter(
        Ticket.user_id == user.id,
        Ticket.status == 'pending_payment',
        Ticket.event_id == user.selected_event_id
    ).all()

    anzahl = len(pending_tickets)
    if anzahl == 0:
        await update.message.reply_text(get_text(user.language_code, "problem_reselect_event"))
        return

    selected_event = db.query(Event).filter(Event.id == user.selected_event_id).first()
    original_price = anzahl * selected_event.price
    final_price = original_price
    discount_text = ""

    if discount_code:
        if discount_code.discount_type == 'percentage':
            discount_amount = (discount_code.value / 100) * original_price
            final_price = original_price - discount_amount
            discount_text = f"\nتخفیف ({discount_code.value}%): -{discount_amount:.2f} EUR"
        elif discount_code.discount_type == 'fixed':
            discount_amount = discount_code.value
            final_price = original_price - discount_amount
            discount_text = f"\nتخفیف: -{discount_amount:.2f} EUR"

        final_price = max(0, final_price) # Price can't be negative
        discount_code.uses_count += 1 # Increment usage
        db.commit()

    summary_text = get_text(user.language_code, "ticket_purchase_summary").format(
        amount=anzahl,
        event_name=selected_event.name,
        total_price=f"{final_price:.2f}", # Use final price
        reference_code=pending_tickets[0].ticket_id_str
    )
    # Add discount info to summary
    summary_text = summary_text.replace(f"Gesamtpreis: {final_price:.2f} EUR.", f"Preis: {original_price:.2f} EUR{discount_text}\n<b>Gesamtpreis: {final_price:.2f} EUR</b>.")

    await update.message.reply_text(summary_text, parse_mode='HTML', reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user.language_code, "go_to_main_menu"))]], resize_keyboard=True))
    user.current_step = "waiting_for_payment"
    db.commit()

# 🆕 --- سیستم صفحه‌بندی (Pagination) ---
EVENTS_PER_PAGE = 3 # تعداد رویداد در هر صفحه

async def list_events_paginated(update: Update, context: CallbackContext, event_type: str = 'active', page: int = 1):
    """لیست رویدادها را به صورت صفحه‌بندی شده نمایش می‌دهد."""
    db: Session = next(get_db())
    chat_id = update.effective_chat.id
    user = db.query(User).filter(User.telegram_id == chat_id).first()
    user_lang = user.language_code if user else 'de'

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        parts = query.data.split('_')
        event_type = parts[2]
        page = int(parts[3])

    if event_type == 'active':
        query_filter = (Event.is_active == True, Event.is_past_event == False)
        order_by = Event.date.asc()
    else: # 'past'
        query_filter = (Event.is_past_event == True,)
        order_by = Event.date.desc()

    total_events = db.query(Event).filter(*query_filter).count()
    if total_events == 0:
        message_key = "no_events_available" if event_type == 'active' else "no_past_events"
        await context.bot.send_message(chat_id, get_text(user_lang, message_key))
        return

    offset = (page - 1) * EVENTS_PER_PAGE
    events_to_show = db.query(Event).filter(*query_filter).order_by(order_by).limit(EVENTS_PER_PAGE).offset(offset).all()

    # ارسال پیام عنوان فقط برای صفحه اول
    if page == 1 and not update.callback_query:
        title_key = "upcoming_events_title" if event_type == 'active' else "past_events_title"
        await context.bot.send_message(chat_id, get_text(user_lang, title_key), parse_mode='Markdown')

    # ⭐️ FIX: The actual logic to display events was missing.
    for event in events_to_show:
        event_date_str = event.date.strftime('%d.%m.%Y')
        event_time_str = event.date.strftime('%H:%M')
        localized_description = escape_markdown_v2(get_localized_description(event.description, user_lang))

        if event_type == 'active':
            caption = get_text(user_lang, "event_caption_format").format(
                name=event.name, date=event_date_str, location=event.location,
                time=event_time_str, price=event.price, description=localized_description
            )
            # Add buy button only for active events
            keyboard = [[InlineKeyboardButton(get_text(user_lang, "buy_ticket_button_text"), callback_data=f"buy_ticket_for_{event.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else: # 'past'
            caption = get_text(user_lang, "event_caption_past").format(
                name=event.name, date=event_date_str, location=event.location,
                description=localized_description
            )
            reply_markup = None # No button for past events

        if event.poster_path and os.path.exists(event.poster_path):
            try:
                with open(event.poster_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id, photo=photo, caption=caption,
                        parse_mode='Markdown', reply_markup=reply_markup
                    )
            except Exception as e:
                logging.error(f"Error sending photo for event {event.name}: {e}")
                await context.bot.send_message(chat_id, f"{get_text(user_lang, 'error_loading_poster')}\n{caption}", parse_mode='Markdown', reply_markup=reply_markup)
        else:
            no_poster_key = "event_caption_no_poster" if event_type == 'active' else "no_poster_past_event"
            caption += f"\n\n{get_text(user_lang, no_poster_key)}"
            await context.bot.send_message(chat_id, caption, parse_mode='Markdown', reply_markup=reply_markup)


    # ساخت دکمه‌های صفحه‌بندی
    total_pages = (total_events + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"list_events_{event_type}_{page-1}"))
    if page < total_pages:
        pagination_buttons.append(InlineKeyboardButton(f"بعدی ▶️", callback_data=f"list_events_{event_type}_{page+1}"))

    if pagination_buttons:
        reply_markup = InlineKeyboardMarkup([pagination_buttons])
        # اگر از callback query آمده‌ایم، پیام جدید می‌فرستیم، در غیر این صورت به پیام قبلی اضافه می‌کنیم
        # For simplicity, we always send a new message for pagination controls.
        await context.bot.send_message(chat_id, f"صفحه {page} از {total_pages}", reply_markup=reply_markup)

    if event_type == 'active':
        user.current_step = "select_event"
        db.commit()

    db.close()


# 🆕 --- قابلیت‌های جدید برای کاربر ---
async def my_tickets(update: Update, context: CallbackContext):
    """نمایش بلیط‌های خریداری شده کاربر."""
    chat_id = update.effective_chat.id
    db: Session = next(get_db())
    user = db.query(User).filter(User.telegram_id == chat_id).first()
    user_lang = user.language_code if user else 'de'

    issued_tickets = db.query(Ticket).filter(Ticket.user_id == user.id, Ticket.status == 'issued').all()

    if not issued_tickets:
        await update.message.reply_text(get_text(user_lang, "my_tickets_none"))
    else:
        await update.message.reply_text(get_text(user_lang, "my_tickets_title"))
        for ticket in issued_tickets:
            event = db.query(Event).filter(Event.id == ticket.event_id).first()
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            pdf_path = create_ticket(full_name, ticket.ticket_id_str, event.name)
            with open(pdf_path, 'rb') as pdf_file:
                await context.bot.send_document(chat_id=chat_id, document=pdf_file)
            os.remove(pdf_path)
    db.close()

async def show_help(update: Update, context: CallbackContext):
    """نمایش پیام راهنما."""
    chat_id = update.effective_chat.id
    db: Session = next(get_db())
    user = db.query(User).filter(User.telegram_id == chat_id).first()
    user_lang = user.language_code if user else 'de'
    db.close()
    await update.message.reply_text(get_text(user_lang, "help_text"), parse_mode='Markdown')

# 🆕 تابع کمکی برای تغییر زبان (استفاده شده در handle_message)
async def handle_language_change(update: Update, context: CallbackContext, db: Session, new_lang_code: str):
    chat_id = update.effective_chat.id
    user = db.query(User).filter(User.telegram_id == chat_id).first()

    if user and new_lang_code in LANGUAGES:
        user.language_code = new_lang_code
        db.commit()

        # ⭐️ FIX: Always show the user menu after changing language, even for admins.
        await context.bot.send_message(chat_id, get_text(new_lang_code, "language_changed"),
                                       reply_markup=get_main_keyboard(new_lang_code))


# 🆕 تابع کمکی برای نمایش منوی اصلی (پس از تغییر زبان یا بازگشت)
async def start_main_menu(update: Update, context: CallbackContext):
    db: Session = next(get_db())
    user_telegram_id = update.effective_user.id
    user = db.query(User).filter(User.telegram_id == user_telegram_id).first()
    user_lang = user.language_code if user else 'fa'

    await context.bot.send_message(
        chat_id=user_telegram_id,
        text=get_text(user_lang, "welcome_message") + "\n\nلطفاً انتخاب کنید:",
        reply_markup=get_main_keyboard(user_lang),
        parse_mode='Markdown'
    )

    if user:
        user.current_step = "start"
        db.commit()
    db.close()

# 🆕 تابع کمکی برای ساخت کیبورد اصلی
def get_main_keyboard(lang_code: str) -> ReplyKeyboardMarkup:
    """Builds the main reply keyboard based on the user's language."""
    keyboard = [
        [KeyboardButton(get_text(lang_code, "ticket_buy_button"))],
        [KeyboardButton(get_text(lang_code, "next_event_button")), KeyboardButton(get_text(lang_code, "past_events_button"))],
        [KeyboardButton(get_text(lang_code, "my_tickets_button")), KeyboardButton(get_text(lang_code, "help_button"))],
        [KeyboardButton(get_text(lang_code, "contact_button")), KeyboardButton(get_text(lang_code, "social_media_button"))],
        # 🚨 دکمه‌های زبان در ردیف آخر
        [KeyboardButton("فارسی"), KeyboardButton("Deutsch"), KeyboardButton("کوردی")],
        [KeyboardButton(get_text(lang_code, "go_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


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
        logging.info(f"New user/admin {chat_id} added to DB during callback.")

    user_lang = current_user.language_code

    # ⭐️ NEW: Handle Edit Event callbacks
    if query.data.startswith("edit_event_"):
        await editevent_select_event(update, context)
        return
    elif query.data.startswith("edit_field_"):
        await editevent_select_field(update, context)
        return
    elif query.data == "edit_done":
        await editevent_done(update, context)
        return
    elif query.data == "edit_back_to_list":
        await editevent_start(update, context, is_callback=True)
        return

    # ⭐️ NEW: Handle Archive/Delete callbacks
    elif query.data.startswith("archive_select_"):
        await archive_menu(update, context)
        return

    # ⭐️ NEW: Handle Pagination callbacks
    elif query.data.startswith("list_events_"):
        await list_events_paginated(update, context)
        return
    elif query.data.startswith("archive_action_"):
        await archive_action(update, context)
        return
    elif query.data == "archive_back_to_list":
        await archive_start(update, context, is_callback=True)

    # ⭐️ NEW: Handle Survey callbacks
    elif query.data.startswith("survey_"):
        parts = query.data.split("_")
        event_id = int(parts[1])
        rating = int(parts[2])

        user_lang = current_user.language_code if current_user else 'de'

        # ⭐️ NEW: Save the rating to the database
        # Check if the user has already voted for this event
        existing_survey = db.query(Survey).filter(
            Survey.user_id == current_user.id,
            Survey.event_id == event_id
        ).first()

        if existing_survey:
            await query.edit_message_text(get_text(user_lang, "survey_already_voted"))
        else:
            # اگر کاربر قبلا رای نداده بود، رای جدید را ثبت کن
            new_survey = Survey(
                user_id=current_user.id,
                event_id=event_id,
                rating=rating
            )
            db.add(new_survey)
            db.commit()
            logging.info(f"User {current_user.id} gave event {event_id} a rating of {rating} stars.")
            await query.edit_message_text(get_text(user_lang, "survey_thanks"))
        return

    # ⭐️ NEW: Handle discount management callbacks
    elif query.data == "discount_create":
        return await discount_create_start(update, context)
    elif query.data == "discount_view":
        await discount_view_all(update, context)
        return
    elif query.data == "discount_delete":
        await discount_delete_start(update, context)
        return
    # ⭐️ NEW: Handle bot feedback
    elif query.data.startswith("bot_feedback_"):
        await bot_feedback_handler(update, context)
        return

    if query.data.startswith("buy_ticket_for_"):
        event_id = int(query.data.split("_")[3])
        context.user_data['selected_event_id'] = event_id
        selected_event = db.query(Event).filter(Event.id == event_id).first()

        if selected_event:
            # ⭐️ NEW: Check for VIP option
            if selected_event.vip_price:
                keyboard = [
                    [InlineKeyboardButton(f"معمولی ({selected_event.price} EUR)", callback_data=f"buy_type_regular_{event_id}")],
                    [InlineKeyboardButton(f"VIP ({selected_event.vip_price} EUR)", callback_data=f"buy_type_vip_{event_id}")]
                ]
                await query.edit_message_text(
                    get_text(user_lang, "ask_ticket_type"),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # No VIP, proceed as normal
                context.user_data['ticket_type'] = 'regular'
                await start_purchase_flow(update, context, current_user, db)
        else:
            await query.edit_message_text(get_text(user_lang, "event_not_found_restart"))
        db.close()
        return

    # ⭐️ NEW: Handle ticket type selection
    elif query.data.startswith("buy_type_"):
        parts = query.data.split("_")
        ticket_type = parts[2]
        event_id = int(parts[3])
        context.user_data['ticket_type'] = ticket_type
        context.user_data['selected_event_id'] = event_id

        selected_event = db.query(Event).filter(Event.id == event_id).first()
        if selected_event:
            await start_purchase_flow(update, context, current_user, db)

        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(user_lang, "event_not_found_restart")
            )
        db.close()
        return

    elif query.data.startswith("confirm_"):
        if chat_id != ADMIN_ID:
            await query.edit_message_text(get_text(user_lang, "not_authorized"))
            db.close()
            return

        ticket_id_str_to_confirm = query.data.split("_")[1]

        sample_ticket = db.query(Ticket).filter(
            Ticket.ticket_id_str == ticket_id_str_to_confirm,
            Ticket.status == "pending_payment"
        ).first()

        if not sample_ticket:
            await query.edit_message_text(get_text(user_lang, "ticket_not_pending"))
            db.close()
            return

        ticket_holder_user = db.query(User).filter(User.id == sample_ticket.user_id).first()
        ticket_event = db.query(Event).filter(Event.id == sample_ticket.event_id).first()

        if not ticket_holder_user or not ticket_event:
            logging.error(f"Critical error: User or Event not found for ticket {sample_ticket.ticket_id_str}.")
            await query.edit_message_text(get_text(user_lang, "error_user_event_not_found"))
            db.close()
            return

        all_pending_tickets = db.query(Ticket).filter(
            Ticket.user_id == ticket_holder_user.id,
            Ticket.event_id == ticket_event.id,
            Ticket.status == "pending_payment"
        ).all()

        if not all_pending_tickets:
            await query.edit_message_text(get_text(user_lang, "ticket_not_pending"))
            db.close()
            return

        issued_tickets_count = 0
        full_name = ""
        for ticket in all_pending_tickets:
            try:
                full_name = f"{ticket_holder_user.first_name} {ticket_holder_user.last_name or ''}".strip()
                pdf_path = create_ticket(full_name, ticket.ticket_id_str, ticket_event.name)

                await context.bot.send_document(
                    chat_id=ticket_holder_user.telegram_id,
                    document=open(pdf_path, "rb"),
                    caption=get_text(ticket_holder_user.language_code, "payment_confirmed_ticket_sent_user").format(event_name=ticket_event.name)
                )

                ticket.status = "issued"
                db.commit()
                os.remove(pdf_path)
                issued_tickets_count += 1

                logging.info(f"Ticket {ticket.ticket_id_str} issued to {ticket_holder_user.telegram_id}")

            except Exception as e:
                logging.error(f"Error issuing ticket {ticket.ticket_id_str} for user {ticket_holder_user.telegram_id}: {e}", exc_info=True)
                # ✅ اصلاح برای رفع KeyError: reference_code
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=get_text("de", "error_sending_ticket_admin").format(reference_code=ticket.ticket_id_str, error=e),
                    parse_mode='HTML'
                )
                await context.bot.send_message(chat_id=ticket_holder_user.telegram_id, text=get_text(ticket_holder_user.language_code, "error_sending_ticket_user"))

        if issued_tickets_count > 0:
            await context.bot.send_message(
                chat_id=ticket_holder_user.telegram_id,
                text=get_text(ticket_holder_user.language_code, "tickets_sent_multiple").format(count=issued_tickets_count, event_name=ticket_event.name)
            )
            await context.bot.send_message(
                chat_id=ticket_holder_user.telegram_id,
                text=get_text(ticket_holder_user.language_code, "thank_you_message_user")
            )

            # ✅ اصلاح برای رفع KeyError: reference_code در پیام تأیید نهایی
            await query.edit_message_text(get_text("de", "payment_confirmed_admin").format(name=full_name, reference_code=all_pending_tickets[0].ticket_id_str if all_pending_tickets else 'N/A'))
        else:
            await query.edit_message_text(get_text("de", "error_sending_ticket_admin").format(reference_code='N/A', error="No tickets were successfully issued."))

        db.close()

    elif query.data.startswith("set_lang_"):
        # 🚨 دکمه‌های زبان از Inline به Reply Keyboard منتقل شدند، اما این هندلر برای سازگاری باقی می‌ماند
        new_lang_code = query.data.split("_")[2]
        await handle_language_change(update.callback_query, context, db, new_lang_code)

    elif query.data == "check_subscription":
        is_subscribed = await is_member_of_channel(context.bot, current_user.telegram_id, TELEGRAM_CHANNEL_ID)

        if is_subscribed:
            await query.edit_message_text(get_text(user_lang, "thank_you_for_joining"))
            await start_main_menu(update, context)
        else:
            await query.edit_message_text(get_text(user_lang, "not_subscribed_error"))
        db.close()

    # ⭐️ NEW: Send a feedback survey about the bot itself
    if issued_tickets_count > 0:
        user_lang = ticket_holder_user.language_code
        feedback_keyboard = [[
            InlineKeyboardButton("⭐️", callback_data="bot_feedback_1"),
            InlineKeyboardButton("⭐️⭐️", callback_data="bot_feedback_2"),
            InlineKeyboardButton("⭐️⭐️⭐️", callback_data="bot_feedback_3"),
            InlineKeyboardButton("⭐️⭐️⭐️⭐️", callback_data="bot_feedback_4"),
            InlineKeyboardButton("⭐️⭐️⭐️⭐️⭐️", callback_data="bot_feedback_5"),
        ]]
        await context.bot.send_message(chat_id=ticket_holder_user.telegram_id,
                                       text=get_text(user_lang, "bot_feedback_prompt"),
                                       reply_markup=InlineKeyboardMarkup(feedback_keyboard))

async def bot_feedback_handler(update: Update, context: CallbackContext):
    """Handles the feedback rating for the bot itself."""
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split("_")[2])
    logging.info(f"Bot feedback received from user {query.from_user.id}: {rating} stars.")

    # For now, just thank the user. This could be saved to a separate table or log file.
    await query.edit_message_text(get_text(query.from_user.language_code, "survey_thanks"))


# 🆕 تابع جدید برای ارسال لیست فروش به ادمین (نسخه بهبود یافته و نهایی)
async def admin_sales_report(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id != ADMIN_ID:
        return

    db: Session = next(get_db())

    all_tickets = db.query(Ticket).order_by(Ticket.issue_date.asc()).all()

    if not all_tickets:
        await context.bot.send_message(chat_id, get_text("de", "admin_no_sales_found"))
        db.close()
        return

    sales_data = {}
    total_issued = 0
    total_pending = 0

    for ticket in all_tickets:
        # کلید گروه‌بندی: (شناسه کاربر، شناسه رویداد، وضعیت پرداخت)
        key = (ticket.user_id, ticket.event_id, ticket.status) # 🚨 از وضعیت هم برای اطمینان استفاده می‌کنیم

        # 🚨 دریافت قیمت رویداد
        event_data = db.query(Event.price).filter(Event.id == ticket.event_id).first()
        event_price = event_data[0] if event_data else 0

        if key not in sales_data:
            sales_data[key] = {
                'tickets_count': 0,
                'status': ticket.status,
                'issue_date': ticket.issue_date,
                'event_price': event_price,
                'user_id': ticket.user_id, # 🚨 اضافه کردن user_id
                'event_id': ticket.event_id # 🚨 اضافه کردن event_id
            }
        sales_data[key]['tickets_count'] += 1

        if ticket.status == 'issued':
            total_issued += 1
        elif ticket.status == 'pending_payment':
            total_pending += 1

    total_revenue = sum(data['tickets_count'] * data['event_price'] for data in sales_data.values() if data['status'] == 'issued')

    report_text = get_text("de", "admin_sales_report_title") + "\n\n"

    report_text += "<b>--- خلاصه فروش ---</b>\n"
    report_text += f"<b>کل بلیط‌های فروخته شده:</b> {total_issued}\n"
    report_text += f"<b>بلیط‌های در انتظار پرداخت:</b> {total_pending}\n"
    report_text += f"<b>کل درآمد (تأیید شده):</b> {total_revenue} EUR\n\n"
    report_text += "<b>--- جزئیات فروش (بر اساس رویداد و خریدار) ---</b>\n\n"

    index = 1
    events_in_report = {}

    # 🚨 گروه‌بندی داده‌ها بر اساس نام رویداد برای نمایش نهایی
    for data in sales_data.values():
        event_name = db.query(Event.name).filter(Event.id == data['event_id']).scalar()
        if event_name not in events_in_report:
            events_in_report[event_name] = []
        events_in_report[event_name].append(data)

    for event_name, transactions in events_in_report.items():
        # 🚨 اینجا از event_name استفاده می‌کنیم که قبلاً بازیابی شده
        report_text += f"<u><b>🎤 {event_name}</b></u>\n"

        transactions.sort(key=lambda x: x['issue_date'])

        for data in transactions:
            user = db.query(User).filter(User.id == data['user_id']).first()

            if user:
                status_text = get_text("de", "admin_sales_status_issued") if data['status'] == 'issued' else get_text("de", "admin_sales_status_pending")
                total_amount = data['tickets_count'] * data['event_price']

                report_item = get_text("de", "admin_sales_item").format(
                    index=index,
                    name=f"{user.first_name} {user.last_name or ''}",
                    username=user.username or 'N/A',
                    event_name=event_name, # 🚨 استفاده از event_name
                    amount=data['tickets_count'],
                    status=status_text,
                    date=data['issue_date'].strftime('%Y-%m-%d | %H:%M')
                )
                report_text += report_item + "\n\n"
                index += 1

    await context.bot.send_message(chat_id, report_text, parse_mode='HTML')
    db.close()

# 🧾 ساخت بلیت با QR که دقیقاً مربع سیاه سمت راست را می‌پوشاند
def create_ticket(name, ticket_id_str, event_name):

    # 🆕 ساخت محتوای QR Code با جزئیات کامل و خوانا
    qr_data = (
        f"KABOUK TICKET VALIDATION\n"
        f"Ticket ID: {ticket_id_str}\n"
        f"Holder Name: {name}\n"
        f"Event: {event_name}\n"
        f"Payment Method: Bank Transfer (Verwendungszweck)\n"
        f"Issue Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    qr = qrcode.make(qr_data)

    poster_template_path = "ticket_template_kabouk.jpg"

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

    # ابعاد دقیق شما: 2000x647 پیکسل
    # ناحیه خالی سمت راست تقریباً از X=1280 شروع می‌شود.

    # ⭐️⭐️⭐️ تنظیمات نهایی QR کد برای ابعاد 2000x647 (بزرگتر و مرکزی) ⭐️⭐️⭐️

    # ابعاد QR کد (اندازه بزرگ 420x420)
    final_qr_width = 420
    final_qr_height = 420

    # مختصات شروع (X, Y) برای مرکزیت در ناحیه خالی
    # X: تنظیم نهایی برای 50 پیکسل بیشتر به راست و مرکزیت با سایز 420
    new_start_x = 1500
    # Y: محاسبه مجدد برای مرکزیت با ارتفاع 420 پیکسل
    new_start_y = 114

    # برای تنظیم، فقط عدد new_start_x یا new_start_y را تغییر دهید.
    # برای راست تر شدن: new_start_x را افزایش دهید.
    # برای پایین تر آمدن: new_start_y را افزایش دهید.

    # ⭐️⭐️⭐️ پایان تنظیمات ⭐️⭐️⭐️

    # اطمینان از اینکه از مرز تصویر خارج نشویم
    new_start_x = max(0, min(new_start_x, poster_width - final_qr_width))
    new_start_y = max(0, min(new_start_y, poster_height - final_qr_height))

    qr_image = qr.resize((final_qr_width, final_qr_height), Image.LANCZOS)
    logging.info(f"QR code resized to {final_qr_width}x{final_qr_height} pixels to precisely fit the intended area.")

    poster.paste(qr_image, (int(new_start_x), int(new_start_y)))
    logging.info(f"QR code pasted at X:{int(new_start_x)}, Y:{int(new_start_y)}.")

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

# 🆕 --- مدیریت رویداد توسط ادمین (ConversationHandler) ---

# مراحل مکالمه
NAME, DATE, LOCATION, PRICE, CAPACITY, DESC_DE, DESC_FA, DESC_CKB, POSTER, IS_ACTIVE, VIP_CHOICE, VIP_PRICE, VIP_DESCRIPTION = range(13)

async def addevent_start(update: Update, context: CallbackContext):
    """شروع فرآیند افزودن رویداد جدید."""
    chat_id = update.effective_chat.id
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == chat_id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()

    if chat_id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text(get_text(admin_lang, "admin_addevent_start"))
    return NAME

async def addevent_name(update: Update, context: CallbackContext):
    """دریافت نام رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['name'] = update.message.text
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_name_received").format(name=update.message.text))
    return DATE

async def addevent_date(update: Update, context: CallbackContext):
    """دریافت تاریخ و زمان رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    try:
        event_date = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        context.user_data['date'] = event_date
        await update.message.reply_text(get_text(admin_lang, "admin_addevent_datetime_received").format(date=update.message.text))
        return LOCATION
    except ValueError:
        await update.message.reply_text(get_text(admin_lang, "admin_invalid_date"))
        return DATE

async def addevent_location(update: Update, context: CallbackContext):
    """دریافت مکان رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['location'] = update.message.text
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_location_received").format(location=update.message.text))
    return PRICE

async def addevent_price(update: Update, context: CallbackContext):
    """دریافت قیمت رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    try:
        price = float(update.message.text)
        context.user_data['price'] = price
        await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_capacity").format(price=price))
        return CAPACITY
    except ValueError:
        await update.message.reply_text(get_text(admin_lang, "admin_invalid_price"))
        return PRICE

async def addevent_capacity(update: Update, context: CallbackContext):
    """دریافت ظرفیت رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    try:
        capacity = int(update.message.text)
        context.user_data['capacity'] = capacity if capacity > 0 else None
        await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_desc_de").format(capacity=capacity))
        return DESC_DE
    except ValueError:
        await update.message.reply_text("Bitte eine gültige Zahl eingeben.")
        return CAPACITY

async def addevent_get_desc_de(update: Update, context: CallbackContext):
    """دریافت توضیحات آلمانی."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['desc_de'] = update.message.text
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_desc_fa"))
    return DESC_FA

async def addevent_get_desc_fa(update: Update, context: CallbackContext):
    """دریافت توضیحات فارسی."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['desc_fa'] = update.message.text
    await update.message.reply_text(get_text("de", "admin_addevent_ask_desc_ckb"))
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_desc_ckb"))
    return DESC_CKB

async def addevent_get_desc_ckb(update: Update, context: CallbackContext):
    """دریافت توضیحات کردی و رفتن به مرحله بعد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['desc_ckb'] = update.message.text
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_vip"))
    return VIP_CHOICE

async def addevent_vip_choice(update: Update, context: CallbackContext):
    """بررسی وجود بخش VIP."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    if update.message.text.lower() == 'ja':
        await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_vip_price"))
        return VIP_PRICE
    else:
        context.user_data['vip_price'] = None
        context.user_data['vip_description'] = None
        await update.message.reply_text(get_text(admin_lang, "admin_addevent_description_received")) # Re-using this text
        return POSTER

async def addevent_vip_price(update: Update, context: CallbackContext):
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['vip_price'] = int(update.message.text)
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_ask_vip_description").format(price=context.user_data['vip_price']))
    return VIP_DESCRIPTION

async def addevent_vip_description(update: Update, context: CallbackContext):
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    context.user_data['vip_description'] = update.message.text
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_description_received")) # Re-using this text
    return POSTER

async def addevent_poster(update: Update, context: CallbackContext):
    """دریافت و ذخیره پوستر رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    photo_file = await update.message.photo[-1].get_file()
    poster_filename = f"event_{uuid4()}.jpg"
    await photo_file.download_to_drive(poster_filename)
    context.user_data['poster_path'] = poster_filename
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_poster_received"))
    return IS_ACTIVE

async def addevent_is_active(update: Update, context: CallbackContext):
    """پرسش در مورد فعال بودن رویداد و ذخیره نهایی."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    text = update.message.text.lower()
    if text not in ['ja', 'nein']:
        await update.message.reply_text(get_text(admin_lang, "admin_invalid_yes_no"))
        return IS_ACTIVE

    context.user_data['is_active'] = (text == 'ja')

    # ⭐️ NEW: Combine descriptions
    desc_de = context.user_data.get('desc_de', '')
    desc_fa = context.user_data.get('desc_fa', '')
    desc_ckb = context.user_data.get('desc_ckb', '')
    full_description = f"de:{desc_de}|fa:{desc_fa}|ckb:{desc_ckb}"

    # ذخیره رویداد در دیتابیس
    db: Session = next(get_db())
    new_event = Event(
        name=context.user_data['name'],
        date=context.user_data['date'],
        location=context.user_data['location'],
        price=context.user_data['price'],
        capacity=context.user_data.get('capacity'),
        description=full_description,
        vip_price=context.user_data.get('vip_price'),
        vip_description=context.user_data.get('vip_description'),
        poster_path=context.user_data['poster_path'],
        is_active=context.user_data['is_active'],
        is_past_event=False # By default, new events are not past events
    )
    db.add(new_event)
    db.commit()
    db.close()

    await update.message.reply_text(get_text(admin_lang, "admin_addevent_success").format(name=context.user_data['name']))
    context.user_data.clear()
    return ConversationHandler.END

async def addevent_cancel(update: Update, context: CallbackContext):
    """لغو فرآیند افزودن رویداد."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    await update.message.reply_text(get_text(admin_lang, "admin_addevent_cancel"))
    context.user_data.clear()
    return ConversationHandler.END

async def conversation_fallback(update: Update, context: CallbackContext):
    """A generic fallback to end any conversation and return to the main menu."""
    await start(update, context)
    return ConversationHandler.END

# 🆕 --- ویرایش رویداد توسط ادمین ---
EDIT_SELECT_FIELD, EDIT_GET_VALUE = range(13, 15)

async def editevent_start(update: Update, context: CallbackContext, is_callback: bool = False):
    """مرحله ۱: نمایش لیست رویدادها برای ویرایش."""
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    events = db.query(Event).order_by(Event.date.desc()).all()
    db.close()

    if not events:
        await update.message.reply_text(get_text("de", "admin_editevent_no_events"))
        await update.message.reply_text(get_text(admin_lang, "admin_editevent_no_events"))
        return ConversationHandler.END

    keyboard = []
    for event in events:
        status_emoji = "✅" if event.is_active else "❌"
        keyboard.append([InlineKeyboardButton(f"{status_emoji} {event.name}", callback_data=f"edit_event_{event.id}")])

    # Add a cancel button
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="edit_cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = get_text("de", "admin_editevent_select")
    if is_callback:
        query = update.callback_query
        await query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

    return EDIT_SELECT_FIELD

async def editevent_select_event(update: Update, context: CallbackContext):
    """مرحله ۲: نمایش فیلدهای قابل ویرایش برای رویداد انتخاب شده."""
    query = update.callback_query
    event_id = int(query.data.split("_")[2])
    await query.answer()
    context.user_data['edit_event_id'] = event_id

    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    event = db.query(Event).filter(Event.id == event_id).first()
    db.close()

    if not event:
        await query.edit_message_text("Event not found.")
        return ConversationHandler.END

    text = get_text("de", "admin_editevent_selected").format(name=event.name)
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="edit_field_name"), InlineKeyboardButton("Date (YYYY-MM-DD HH:MM)", callback_data="edit_field_date")],
        [InlineKeyboardButton("Location", callback_data="edit_field_location"), InlineKeyboardButton("Price", callback_data="edit_field_price")],
        [InlineKeyboardButton("Capacity", callback_data="edit_field_capacity"), InlineKeyboardButton("VIP Price", callback_data="edit_field_vip_price")],
        [InlineKeyboardButton("VIP Description", callback_data="edit_field_vip_description"), InlineKeyboardButton("Poster", callback_data="edit_field_poster")],
        [InlineKeyboardButton("Description", callback_data="edit_field_description")],
        [InlineKeyboardButton("Status (Active/Inactive)", callback_data="edit_field_is_active")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="edit_back_to_list"), InlineKeyboardButton("✅ Done", callback_data="edit_done")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_SELECT_FIELD

async def editevent_select_field(update: Update, context: CallbackContext):
    """مرحله ۳: پرسیدن مقدار جدید برای فیلد انتخاب شده."""
    query = update.callback_query
    await query.answer()
    field_to_edit = query.data.split("_")[2]
    context.user_data['editing_field'] = field_to_edit

    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()

    if field_to_edit == 'poster':
        await query.message.reply_text(get_text("de", "admin_editevent_ask_new_poster"))
        await query.message.reply_text(get_text(admin_lang, "admin_editevent_ask_new_poster"))
    else:
        await query.message.reply_text(get_text("de", "admin_editevent_ask_new_value").format(field=field_to_edit))
        await query.message.reply_text(get_text(admin_lang, "admin_editevent_ask_new_value").format(field=field_to_edit))

    return EDIT_GET_VALUE

async def editevent_get_value(update: Update, context: CallbackContext):
    """مرحله ۴: دریافت مقدار جدید و آپدیت دیتابیس."""
    event_id = context.user_data.get('edit_event_id')
    field = context.user_data.get('editing_field')
    chat_id = update.effective_chat.id
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == chat_id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        await update.message.reply_text("Error: Event not found. Cancelling edit.")
        db.close()
        return ConversationHandler.END

    try:
        if update.message.photo and field == 'poster':
            photo_file = await update.message.photo[-1].get_file()
            poster_filename = f"event_{uuid4()}.jpg"
            await photo_file.download_to_drive(poster_filename)
            # Optionally delete old poster
            if event.poster_path and os.path.exists(event.poster_path):
                os.remove(event.poster_path)
            event.poster_path = poster_filename
        else:
            new_value = update.message.text
            if field == 'name': event.name = new_value
            elif field == 'date': event.date = datetime.strptime(new_value, '%Y-%m-%d %H:%M')
            elif field == 'location': event.location = new_value
            elif field == 'price': event.price = float(new_value)
            elif field == 'capacity': event.capacity = int(new_value) if int(new_value) > 0 else None
            elif field == 'vip_price': event.vip_price = int(new_value) if int(new_value) > 0 else None
            elif field == 'vip_description': event.vip_description = new_value
            elif field == 'description': event.description = new_value
            elif field == 'is_active': event.is_active = new_value.lower() in ['ja', 'yes', 'true', '1']

        db.commit()
        await update.message.reply_text(get_text("de", "admin_editevent_updated").format(field=field, name=event.name))
        await update.message.reply_text(get_text(admin_lang, "admin_editevent_updated").format(field=field, name=event.name))

    except Exception as e:
        await update.message.reply_text(f"Invalid value or error: {e}. Please try again.")

    finally:
        db.close()

    # Go back to field selection
    # We need to re-trigger the message with a fake update object
    fake_query_data = f"edit_event_{event_id}"
    update.callback_query = lambda: None # Create a dummy object
    update.callback_query.data = fake_query_data
    return await editevent_select_event(update, context)
    # FIX: Correctly return to the field selection menu
    # Create a new "fake" update object to re-trigger the previous step
    from unittest.mock import Mock
    mock_callback_query = Mock()
    mock_callback_query.data = f"edit_event_{event_id}"
    mock_callback_query.message = update.message
    mock_callback_query.from_user = update.effective_user
    mock_update = Mock(callback_query=mock_callback_query)

    await editevent_select_event(mock_update, context)
    return EDIT_SELECT_FIELD

async def editevent_done(update: Update, context: CallbackContext):
    """پایان ویرایش و بازگشت به منوی ادمین."""
    query = update.callback_query
    await query.edit_message_text(get_text("de", "admin_editevent_done"))
    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()
    await query.edit_message_text(get_text(admin_lang, "admin_editevent_done"))
    context.user_data.clear()
    await admin_menu(query, context) # Show admin menu again
    return ConversationHandler.END


# 🆕 --- آرشیو و حذف رویداد توسط ادمین ---
async def archive_start(update: Update, context: CallbackContext, is_callback: bool = False):
    """نمایش لیست رویدادها برای آرشیو/حذف."""
    db: Session = next(get_db())
    events = db.query(Event).order_by(Event.date.desc()).all()
    db.close()

    if not events:
        await update.message.reply_text(get_text("de", "admin_editevent_no_events"))
        return

    keyboard = [[InlineKeyboardButton(f"{'✅' if e.is_active else '❌'} {e.name}", callback_data=f"archive_select_{e.id}")] for e in events]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = get_text("de", "admin_archive_select")
    if is_callback:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def archive_menu(update: Update, context: CallbackContext):
    """نمایش گزینه‌های آرشیو یا حذف برای رویداد انتخاب شده."""
    query = update.callback_query
    event_id = int(query.data.split("_")[2])
    db: Session = next(get_db())
    event = db.query(Event).filter(Event.id == event_id).first()
    db.close()

    if not event:
        await query.edit_message_text("Event not found.")
        return

    keyboard = [
        [InlineKeyboardButton(get_text("de", "admin_archive_button"), callback_data=f"archive_action_archive_{event_id}")],
        [InlineKeyboardButton(get_text("de", "admin_delete_button"), callback_data=f"archive_action_delete_{event_id}")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="archive_back_to_list")]
    ]
    await query.edit_message_text(get_text("de", "admin_archive_menu").format(name=event.name), reply_markup=InlineKeyboardMarkup(keyboard))

async def archive_action(update: Update, context: CallbackContext):
    """انجام عمل آرشیو یا حذف."""
    query = update.callback_query
    parts = query.data.split("_")
    action, event_id = parts[2], int(parts[3])

    db: Session = next(get_db())
    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        await query.edit_message_text("Event not found.")
        db.close()
        return

    if action == "archive":
        event.is_active = False
        event.is_past_event = True
        db.commit()
        await query.edit_message_text(get_text("de", "admin_archive_success").format(name=event.name))
    elif action == "delete":
        # مرحله اول حذف: درخواست تایید
        keyboard = [[InlineKeyboardButton("YES, DELETE", callback_data=f"archive_action_confirmdelete_{event_id}"), InlineKeyboardButton("CANCEL", callback_data=f"archive_select_{event_id}")]]
        await query.edit_message_text(get_text("de", "admin_delete_confirm").format(name=event.name), reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "confirmdelete":
        # مرحله دوم: حذف نهایی
        db.query(Ticket).filter(Ticket.event_id == event_id).delete()
        db.delete(event)
        db.commit()
        await query.edit_message_text(get_text("de", "admin_delete_success").format(name=event.name))

    db.close()
    await admin_menu(query, context) # بازگشت به منوی ادمین

# 🆕 --- تابع کمکی برای شروع فرآیند خرید پس از انتخاب نوع بلیط ---
async def start_purchase_flow(update: Update, context: CallbackContext, user: User, db: Session):
    """Starts the name/number input flow after event/type is selected."""
    user_lang = user.language_code
    event_id = context.user_data.get('selected_event_id')
    event = db.query(Event).filter(Event.id == event_id).first()

    # ⭐️ NEW: Loyalty Discount Check
    # Count distinct events the user has bought tickets for
    purchased_events_count = db.query(func.count(func.distinct(Ticket.event_id))).filter(
        Ticket.user_id == user.id,
        Ticket.status.in_(['issued', 'checked_in'])
    ).scalar()

    if purchased_events_count >= 5:
        context.user_data['loyalty_discount'] = True
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=get_text(user_lang, "loyalty_discount_applied")
        )

    user.selected_event_id = event_id
    user.current_step = "entering_vorname"
    db.commit()

    await context.bot.send_message(
        chat_id=user.telegram_id,
        text=get_text(user_lang, "event_selected_prompt_vorname").format(event_name=event.name),
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(get_text(user_lang, "back_button"))]], resize_keyboard=True)
    )

# 🆕 --- گزارش نظرسنجی برای ادمین ---
async def admin_survey_report(update: Update, context: CallbackContext):
    """گزارشی از میانگین امتیازات رویدادها را برای ادمین ارسال می‌کند."""
    from sqlalchemy import func

    chat_id = update.effective_chat.id
    if chat_id != ADMIN_ID:
        return

    db: Session = next(get_db())

    # کوئری برای محاسبه میانگین امتیاز و تعداد آرا برای هر رویداد
    survey_stats = db.query(
        Event.name,
        func.avg(Survey.rating),
        func.count(Survey.id)
    ).join(Survey, Event.id == Survey.event_id).group_by(Event.name).order_by(func.avg(Survey.rating).desc()).all()

    if not survey_stats:
        await update.message.reply_text(get_text("de", "admin_survey_no_surveys"))
        db.close()
        return

    report_text = get_text("de", "admin_survey_report_title") + "\n\n"
    for event_name, avg_rating, vote_count in survey_stats:
        report_text += get_text("de", "admin_survey_report_item").format(event_name=event_name, avg_rating=avg_rating, vote_count=vote_count)

    await update.message.reply_text(report_text, parse_mode='HTML')
    db.close()

# 🆕 --- مدیریت کدهای تخفیف ---
DISCOUNT_CODE, DISCOUNT_TYPE, DISCOUNT_VALUE, DISCOUNT_USES = range(15, 19)

async def discounts_menu(update: Update, context: CallbackContext):
    """نمایش منوی مدیریت کدهای تخفیف."""
    keyboard = [
        [InlineKeyboardButton(get_text("de", "admin_discounts_create"), callback_data="discount_create")],
        [InlineKeyboardButton(get_text("de", "admin_discounts_view"), callback_data="discount_view")],
        [InlineKeyboardButton(get_text("de", "admin_discounts_delete"), callback_data="discount_delete")],
    ]
    await update.message.reply_text(get_text("de", "admin_discounts_menu_title"), reply_markup=InlineKeyboardMarkup(keyboard))

async def discount_create_start(update: Update, context: CallbackContext):
    """شروع فرآیند ساخت کد تخفیف."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(get_text("de", "admin_discounts_ask_code"))
    return DISCOUNT_CODE

async def discount_get_code(update: Update, context: CallbackContext):
    context.user_data['discount_code'] = update.message.text.strip().upper()
    keyboard = [[InlineKeyboardButton("درصدی (%)", callback_data="discount_type_percentage"),
                 InlineKeyboardButton("مبلغ ثابت (€)", callback_data="discount_type_fixed")]]
    await update.message.reply_text(get_text("de", "admin_discounts_ask_type"), reply_markup=InlineKeyboardMarkup(keyboard))
    return DISCOUNT_TYPE

async def discount_get_type(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data['discount_type'] = query.data.split('_')[2]
    await query.message.reply_text(get_text("de", "admin_discounts_ask_value"))
    return DISCOUNT_VALUE

async def discount_get_value(update: Update, context: CallbackContext):
    context.user_data['discount_value'] = float(update.message.text)
    await update.message.reply_text(get_text("de", "admin_discounts_ask_max_uses"))
    return DISCOUNT_USES

async def discount_get_uses_and_save(update: Update, context: CallbackContext):
    context.user_data['discount_max_uses'] = int(update.message.text)

    db: Session = next(get_db())
    new_code = DiscountCode(
        code=context.user_data['discount_code'],
        discount_type=context.user_data['discount_type'],
        value=context.user_data['discount_value'],
        max_uses=context.user_data['discount_max_uses'],
    )
    db.add(new_code)
    db.commit()
    db.close()

    await update.message.reply_text(get_text("de", "admin_discounts_success").format(code=new_code.code))
    context.user_data.clear()
    return ConversationHandler.END

async def discount_cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("عملیات ساخت کد تخفیف لغو شد.")
    context.user_data.clear()
    return ConversationHandler.END

async def discount_view_all(update: Update, context: CallbackContext):
    """نمایش تمام کدهای تخفیف موجود."""
    query = update.callback_query
    await query.answer()
    db: Session = next(get_db())
    codes = db.query(DiscountCode).all()
    db.close()

    if not codes:
        await query.message.reply_text(get_text("de", "admin_discounts_none"))
        return

    report = get_text("de", "admin_discounts_view_title") + "\n\n"
    for code in codes:
        value_str = f"{code.value}%" if code.discount_type == 'percentage' else f"{code.value} EUR"
        report += get_text("de", "admin_discounts_view_item").format(
            code=code.code,
            type=code.discount_type,
            value=value_str,
            uses=code.uses_count,
            max_uses=code.max_uses,
            active="✅" if code.is_active else "❌"
        )
    await query.message.reply_text(report, parse_mode='HTML')

async def discount_delete_start(update: Update, context: CallbackContext):
    """شروع فرآیند حذف کد تخفیف."""
    query = update.callback_query
    await query.answer()
    db: Session = next(get_db())
    user = db.query(User).filter(User.telegram_id == query.from_user.id).first()
    user.current_step = "deleting_discount_code"
    db.commit()

    admin_lang = user.language_code if user else 'de'
    await query.message.reply_text(get_text(admin_lang, "admin_discounts_delete_prompt"))
    db.close() # Close session after commit

async def discount_delete_confirm(update: Update, context: CallbackContext, db: Session):
    """حذف کد تخفیف پس از دریافت نام آن."""
    user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    admin_lang = user.language_code if user else 'de'
    code_to_delete = update.message.text.strip().upper()
    db.query(DiscountCode).filter(DiscountCode.code == code_to_delete).delete()
    db.commit()
    await update.message.reply_text(f"Code '{code_to_delete}' has been deleted.")
    user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    user.current_step = "start"
    db.commit()

# 🆕 --- خروجی CSV از نظرسنجی‌ها ---
async def export_surveys_csv(update: Update, context: CallbackContext):
    """ایجاد و ارسال فایل CSV از نتایج نظرسنجی."""
    from sqlalchemy import func
    if update.effective_chat.id != ADMIN_ID:
        return

    db: Session = next(get_db())
    survey_data = db.query(
        Event.name,
        User.first_name,
        User.last_name,
        Survey.rating,
        Survey.submission_date
    ).join(Survey, Event.id == Survey.event_id).join(User, User.id == Survey.user_id).order_by(Event.name, Survey.submission_date).all()

    if not survey_data:
        await update.message.reply_text(get_text("de", "admin_survey_no_surveys"))
        db.close()
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Event Name', 'User Name', 'Rating (1-5)', 'Submission Date'])

    for event_name, first_name, last_name, rating, date in survey_data:
        writer.writerow([event_name, f"{first_name} {last_name or ''}", rating, date.strftime('%Y-%m-%d %H:%M')])

    output.seek(0)
    await context.bot.send_document(chat_id=ADMIN_ID, document=io.BytesIO(output.getvalue().encode('utf-8')), filename=f"kabouk_survey_details_{datetime.now().strftime('%Y-%m-%d')}.csv")
    db.close()

# 🆕 --- خروجی CSV از فروش ---
async def export_sales_csv(update: Update, context: CallbackContext):
    """ایجاد و ارسال فایل CSV از گزارش فروش."""
    chat_id = update.effective_chat.id
    if chat_id != ADMIN_ID:
        return

    db: Session = next(get_db())
    all_tickets = db.query(Ticket).join(User).join(Event).order_by(Ticket.issue_date).all()

    if not all_tickets:
        await update.message.reply_text(get_text("de", "admin_no_sales_found"))
        db.close()
        return

    output = io.StringIO()
    writer = csv.writer(output)

    # نوشتن هدر فایل
    header = ['Ticket ID', 'Event Name', 'Buyer Name', 'Buyer Username', 'Status', 'Price (EUR)', 'Issue Date']
    writer.writerow(header)

    for ticket in all_tickets:
        row = [
            ticket.ticket_id_str,
            ticket.event.name,
            f"{ticket.user.first_name} {ticket.user.last_name or ''}",
            f"@{ticket.user.username}" if ticket.user.username else "N/A",
            ticket.status,
            ticket.event.price,
            ticket.issue_date.strftime('%Y-%m-%d %H:%M:%S')
        ]
        writer.writerow(row)

    output.seek(0)
    await context.bot.send_document(
        chat_id=ADMIN_ID,
        document=io.BytesIO(output.getvalue().encode('utf-8')),
        filename=f"kabouk_sales_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
    )
    db.close()

# 🆕 --- ارسال پیام همگانی (Broadcast) ---
BROADCAST_GET_MESSAGE, BROADCAST_CONFIRM = range(9, 11)

async def broadcast_start(update: Update, context: CallbackContext):
    """شروع فرآیند ارسال پیام همگانی."""
    await update.message.reply_text(get_text("de", "admin_broadcast_start"))
    return BROADCAST_GET_MESSAGE

async def broadcast_get_message(update: Update, context: CallbackContext):
    """دریافت پیام برای ارسال و درخواست تایید."""
    context.user_data['broadcast_message_id'] = update.message.message_id
    context.user_data['broadcast_chat_id'] = update.message.chat_id

    keyboard = [[InlineKeyboardButton("✅ Ja, senden", callback_data="broadcast_confirm_yes"),
                 InlineKeyboardButton("❌ Nein, abbrechen", callback_data="broadcast_confirm_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(get_text("de", "admin_broadcast_confirm"), reply_markup=reply_markup)
    return BROADCAST_CONFIRM

async def broadcast_confirm(update: Update, context: CallbackContext):
    """تایید و ارسال نهایی پیام همگانی."""
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast_confirm_no":
        await query.edit_message_text(get_text("de", "admin_broadcast_cancelled"))
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(get_text("de", "admin_broadcast_sending"))

    db: Session = next(get_db())
    users = db.query(User).all()
    db.close()

    message_id = context.user_data['broadcast_message_id']
    from_chat_id = context.user_data['broadcast_chat_id']

    success_count = 0
    failed_count = 0
    failed_users = [] # ⭐️ اصلاح ۱: لیست کاربران ناموفق را اینجا تعریف می‌کنیم

    for user in users:
        try:
            await context.bot.copy_message(chat_id=user.telegram_id, from_chat_id=from_chat_id, message_id=message_id)
            success_count += 1
            await asyncio.sleep(0.1) # برای جلوگیری از محدودیت‌های تلگرام
        except Exception as e:
            logging.warning(f"Failed to send broadcast to {user.telegram_id}: {e}")
            failed_count += 1
            failed_users.append(user.telegram_id) # ⭐️ اصلاح ۲: شناسه کاربر ناموفق را به لیست اضافه می‌کنیم

    context.user_data.clear()

    # ارسال گزارش نهایی
    final_report = get_text("de", "admin_broadcast_success_report").format(success_count=success_count, failed_count=failed_count)
    await context.bot.send_message(chat_id=ADMIN_ID, text=final_report)

    # ارسال لیست کاربران ناموفق در یک فایل
    if failed_users:
        failed_users_str = "\n".join(map(str, failed_users))
        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=io.BytesIO(failed_users_str.encode('utf-8')),
            filename="broadcast_failed_users.txt",
            caption=get_text("de", "admin_broadcast_failed_users_list")
        )

    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: CallbackContext):
    """لغو فرآیند ارسال پیام همگانی."""
    await update.message.reply_text(get_text("de", "admin_broadcast_cancelled"))
    context.user_data.clear()
    return ConversationHandler.END

# 🆕 --- منوی ادمین ---
async def admin_menu(update: Update, context: CallbackContext):
    """نمایش منوی اصلی ادمین."""
    chat_id = update.effective_chat.id if hasattr(update, 'effective_chat') else update.message.chat_id
    if chat_id != ADMIN_ID:
        return

    db: Session = next(get_db())
    admin_user = db.query(User).filter(User.telegram_id == chat_id).first()
    admin_lang = admin_user.language_code if admin_user else 'de'
    db.close()

    admin_keyboard = [
        [KeyboardButton(get_text(admin_lang, "admin_menu_add_event")), KeyboardButton(get_text(admin_lang, "admin_menu_edit_event"))],
        [KeyboardButton(get_text(admin_lang, "admin_menu_archive_event")), KeyboardButton(get_text(admin_lang, "admin_menu_discounts"))],
        [KeyboardButton(get_text(admin_lang, "admin_menu_sales_report")), KeyboardButton(get_text(admin_lang, "admin_menu_survey_report"))],
        [KeyboardButton(get_text(admin_lang, "admin_menu_export_csv")), KeyboardButton(get_text(admin_lang, "admin_survey_export_csv"))],
        [KeyboardButton(get_text(admin_lang, "admin_menu_broadcast"))],
        [KeyboardButton(get_text(admin_lang, "go_to_main_menu"))] # دکمه بازگشت به منوی کاربری
    ]
    reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
    await update.message.reply_text(get_text(admin_lang, "admin_menu_title"), reply_markup=reply_markup)

# 🆕 --- دستور توقف ربات با هشدار ---
async def stop_command(update: Update, context: CallbackContext):
    """Handles the /stop command with a warning."""
    user_lang = 'de'
    db: Session = next(get_db())
    user = db.query(User).filter(User.telegram_id == update.effective_chat.id).first()
    if user:
        user_lang = user.language_code
    db.close()
    await update.message.reply_text(get_text(user_lang, "stop_bot_warning"), parse_mode='Markdown')

# 🆕 --- سیستم چک-این بلیط ---
CHECKIN_SELECT_EVENT, CHECKIN_SCAN_TICKET = range(11, 13)

async def checkin_start(update: Update, context: CallbackContext):
    """شروع فرآیند چک-این: انتخاب رویداد."""
    if update.effective_user.id not in CHECKIN_STAFF_IDS:
        return ConversationHandler.END

    db: Session = next(get_db())
    # فقط رویدادهای فعال و نزدیک را نشان بده
    today = dt.date.today()
    active_events = db.query(Event).filter(
        Event.is_active == True,
        Event.date >= datetime.combine(today - dt.timedelta(days=1), time.min) # از دیروز به بعد
    ).order_by(Event.date.desc()).all()
    db.close()

    if not active_events:
        await update.message.reply_text("Keine aktiven Events für den Check-in gefunden.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(event.name, callback_data=f"checkin_event_{event.id}")] for event in active_events]
    await update.message.reply_text(get_text("de", "checkin_select_event"), reply_markup=InlineKeyboardMarkup(keyboard))
    return CHECKIN_SELECT_EVENT

async def checkin_event_selected(update: Update, context: CallbackContext):
    """رویداد برای چک-این انتخاب شد. حالا منتظر اسکن بلیط هستیم."""
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split("_")[2])
    context.user_data['checkin_event_id'] = event_id

    db: Session = next(get_db())
    event = db.query(Event).filter(Event.id == event_id).first()
    db.close()

    await query.edit_message_text(f"Check-in für '{event.name}' aktiviert. Scanne jetzt Tickets.")
    return CHECKIN_SCAN_TICKET

async def checkin_scan_ticket(update: Update, context: CallbackContext):
    """پردازش بلیط اسکن شده."""
    ticket_id = update.message.text.strip()
    event_id = context.user_data['checkin_event_id']
    db: Session = next(get_db())

    # استخراج ticket_id از متن کامل QR Code
    if "Ticket ID:" in ticket_id:
        try:
            ticket_id = ticket_id.split("Ticket ID:")[1].split("\n")[0].strip()
        except IndexError:
            await update.message.reply_text(get_text("de", "checkin_invalid_id"))
            db.close()
            return CHECKIN_SCAN_TICKET

    ticket = db.query(Ticket).filter(Ticket.ticket_id_str == ticket_id).first()

    if not ticket:
        await update.message.reply_text(get_text("de", "checkin_not_found"))
    elif ticket.event_id != event_id:
        await update.message.reply_text(get_text("de", "checkin_wrong_event").format(ticket_event=ticket.event.name, current_event=db.query(Event.name).filter(Event.id == event_id).scalar()))
    elif ticket.status == 'checked_in':
        await update.message.reply_text(get_text("de", "checkin_already_used").format(date=ticket.issue_date.strftime('%Y-%m-%d %H:%M'), name=ticket.user.first_name, event=ticket.event.name))
    elif ticket.status != 'issued':
        await update.message.reply_text(get_text("de", "checkin_not_issued").format(status=ticket.status, name=ticket.user.first_name, event=ticket.event.name))
    else: # بلیط معتبر است
        ticket.status = 'checked_in'
        ticket.issue_date = datetime.now() # زمان چک-این را ثبت می‌کنیم
        db.commit()
        await update.message.reply_text(get_text("de", "checkin_success").format(name=ticket.user.first_name, event=ticket.event.name))

    db.close()
    return CHECKIN_SCAN_TICKET

async def checkin_cancel(update: Update, context: CallbackContext):
    """لغو حالت چک-این."""
    await update.message.reply_text(get_text("de", "checkin_cancel"))
    context.user_data.clear()
    return ConversationHandler.END

# 🆕 --- وظایف زمان‌بندی شده (Scheduled Jobs) ---
async def auto_archive_events(context: CallbackContext):
    """
    رویدادهایی که تاریخشان گذشته است را به صورت خودکار آرشیو می‌کند.
    """
    db: Session = next(get_db())
    now = datetime.now()

    # پیدا کردن رویدادهای فعال که تاریخشان گذشته است
    expired_events = db.query(Event).filter(
        Event.is_past_event == False,
        Event.date < now
    ).all()

    if expired_events:
        logging.info(f"Found {len(expired_events)} expired events to archive.")
        for event in expired_events:
            event.is_active = False
            event.is_past_event = True
        db.commit()
        logging.info("Successfully archived expired events.")
    else:
        logging.info("No expired events to archive today.")

    db.close()

async def send_event_reminders(context: CallbackContext):
    """
    یک روز قبل از رویداد، برای شرکت‌کنندگان پیام یادآوری ارسال می‌کند.
    """
    db: Session = next(get_db())
    tomorrow = dt.date.today() + dt.timedelta(days=1)

    # پیدا کردن رویدادهایی که فردا برگزار می‌شوند
    events_tomorrow = db.query(Event).filter(
        Event.date >= datetime.combine(tomorrow, time.min),
        Event.date <= datetime.combine(tomorrow, time.max)
    ).all()

    if not events_tomorrow:
        logging.info("No events scheduled for tomorrow. No reminders to send.")
        db.close()
        return

    for event in events_tomorrow:
        logging.info(f"Sending reminders for event: {event.name}")
        tickets = db.query(Ticket).filter(Ticket.event_id == event.id, Ticket.status == 'issued').all()
        for ticket in tickets:
            try:
                user_lang = ticket.user.language_code
                reminder_text = get_text(user_lang, "event_reminder_message").format(event_name=event.name)
                await context.bot.send_message(chat_id=ticket.user.telegram_id, text=reminder_text, parse_mode='Markdown')
                await asyncio.sleep(0.1) # جلوگیری از محدودیت تلگرام
            except Exception as e:
                logging.warning(f"Failed to send reminder to user {ticket.user.telegram_id} for event {event.id}: {e}")
    db.close()

async def send_post_event_surveys(context: CallbackContext):
    """
    یک روز پس از رویداد، برای شرکت‌کنندگان نظرسنجی ارسال می‌کند.
    """
    db: Session = next(get_db())
    yesterday = dt.date.today() - dt.timedelta(days=1)

    # پیدا کردن رویدادهایی که دیروز تمام شده‌اند
    events_yesterday = db.query(Event).filter(
        Event.date >= datetime.combine(yesterday, time.min),
        Event.date <= datetime.combine(yesterday, time.max)
    ).all()

    if not events_yesterday:
        logging.info("No events ended yesterday. No surveys to send.")
        db.close()
        return

    for event in events_yesterday:
        logging.info(f"Sending surveys for event: {event.name}")
        tickets = db.query(Ticket).filter(Ticket.event_id == event.id, Ticket.status == 'issued').all()
        for ticket in tickets:
            try:
                user_lang = ticket.user.language_code
                survey_text = get_text(user_lang, "post_event_survey_message").format(event_name=event.name)
                keyboard = [[InlineKeyboardButton(get_text(user_lang, f"survey_rating_{i}"), callback_data=f"survey_{event.id}_{i}") for i in range(1, 6)]]
                await context.bot.send_message(chat_id=ticket.user.telegram_id, text=survey_text, reply_markup=InlineKeyboardMarkup(keyboard))
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.warning(f"Failed to send survey to user {ticket.user.telegram_id} for event {event.id}: {e}")
    db.close()

# 🟢 اجرای برنامه
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # ⭐️ NEW: زمان‌بندی وظایف خودکار
    job_queue = app.job_queue
    # اجرای آرشیو خودکار هر شب ساعت 00:05
    job_queue.run_daily(auto_archive_events, time=time(0, 5))
    # اجرای ارسال یادآوری هر روز ساعت 9:00 صبح
    job_queue.run_daily(send_event_reminders, time=time(9, 0))
    # اجرای ارسال نظرسنجی هر روز ساعت 12:00 ظهر
    job_queue.run_daily(send_post_event_surveys, time=time(12, 0))

    # --- Handler برای افزودن رویداد ---
    add_event_regex = (
        f'^({get_text("de", "admin_menu_add_event")}|'
        f'{get_text("fa", "admin_menu_add_event")}|'
        f'{get_text("ckb", "admin_menu_add_event")})$'
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('addevent', addevent_start, filters=filters.Chat(ADMIN_ID)),
            MessageHandler(filters.Regex(add_event_regex) & filters.Chat(ADMIN_ID), addevent_start),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_name)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_date)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_location)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_price)],
            CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_capacity)],
            DESC_DE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_get_desc_de)],
            DESC_FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_get_desc_fa)],
            DESC_CKB: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_get_desc_ckb)],
            VIP_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_vip_choice)],
            VIP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_vip_price)],
            VIP_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_vip_description)],
            POSTER: [MessageHandler(filters.PHOTO, addevent_poster)],
            IS_ACTIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_is_active)],
        },
        fallbacks=[
            CommandHandler('cancel', addevent_cancel),
            CommandHandler('start', conversation_fallback),
            MessageHandler(filters.Regex(f'^({get_text("de", "go_to_main_menu")}|{get_text("fa", "go_to_main_menu")}|{get_text("ckb", "go_to_main_menu")})$'), conversation_fallback)
        ],
        per_message=False,
        allow_reentry=True
    )

    # --- Handler for editing events ---
    edit_event_regex = (
        f'^({get_text("de", "admin_menu_edit_event")}|'
        f'{get_text("fa", "admin_menu_edit_event")}|'
        f'{get_text("ckb", "admin_menu_edit_event")})$'
    )

    edit_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('editevent', editevent_start, filters=filters.Chat(ADMIN_ID)),
            MessageHandler(filters.Regex(edit_event_regex) & filters.Chat(ADMIN_ID), editevent_start)
        ],
        states={
            EDIT_SELECT_FIELD: [CallbackQueryHandler(editevent_select_event, pattern='^edit_event_'),
                                CallbackQueryHandler(editevent_select_field, pattern='^edit_field_'),
                                CallbackQueryHandler(editevent_start, pattern='^edit_back_to_list$')],
            EDIT_GET_VALUE: [MessageHandler(filters.TEXT | filters.PHOTO, editevent_get_value)],
        },
        fallbacks=[
            CallbackQueryHandler(editevent_done, pattern='^edit_done$'),
            CallbackQueryHandler(addevent_cancel, pattern='^edit_cancel$'), # Using addevent_cancel as it's generic
            CommandHandler('cancel', addevent_cancel),
            CommandHandler('start', conversation_fallback),
            MessageHandler(filters.Regex(f'^({get_text("de", "go_to_main_menu")}|{get_text("fa", "go_to_main_menu")}|{get_text("ckb", "go_to_main_menu")})$'), conversation_fallback)
        ],
        per_message=False,
        allow_reentry=True
    )

    # --- Handler for broadcasting ---
    broadcast_regex = (
        f'^({get_text("de", "admin_menu_broadcast")}|'
        f'{get_text("fa", "admin_menu_broadcast")}|'
        f'{get_text("ckb", "admin_menu_broadcast")})$'
    )

    broadcast_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('broadcast', broadcast_start, filters=filters.Chat(ADMIN_ID)),
            MessageHandler(filters.Regex(broadcast_regex) & filters.Chat(ADMIN_ID), broadcast_start)
        ],
        states={
            BROADCAST_GET_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_get_message)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm, pattern='^broadcast_confirm_')],
        },
        fallbacks=[
            CommandHandler('cancel', broadcast_cancel),
            CommandHandler('start', conversation_fallback),
            MessageHandler(filters.Regex(f'^({get_text("de", "go_to_main_menu")}|{get_text("fa", "go_to_main_menu")}|{get_text("ckb", "go_to_main_menu")})$'), conversation_fallback)
        ],
        allow_reentry=True
    )

    # --- Handler for Check-in ---
    checkin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('checkin', checkin_start, filters=filters.Chat(CHECKIN_STAFF_IDS))],
        states={
            CHECKIN_SELECT_EVENT: [CallbackQueryHandler(checkin_event_selected, pattern='^checkin_event_')],
            CHECKIN_SCAN_TICKET: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkin_scan_ticket)],
        },
        fallbacks=[
            CommandHandler('cancel', checkin_cancel),
            CommandHandler('start', conversation_fallback),
            MessageHandler(filters.Regex(f'^({get_text("de", "go_to_main_menu")}|{get_text("fa", "go_to_main_menu")}|{get_text("ckb", "go_to_main_menu")})$'), conversation_fallback)
        ],
        allow_reentry=True
    )

    # --- Handler for Discount Codes ---
    discount_create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(discount_create_start, pattern='^discount_create$')],
        states={
            DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_get_code)],
            DISCOUNT_TYPE: [CallbackQueryHandler(discount_get_type, pattern='^discount_type_')],
            DISCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_get_value)],
            DISCOUNT_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_get_uses_and_save)],
        },
        fallbacks=[
            CommandHandler('cancel', discount_cancel),
            CommandHandler('start', conversation_fallback),
            MessageHandler(filters.Regex(f'^({get_text("de", "go_to_main_menu")}|{get_text("fa", "go_to_main_menu")}|{get_text("ckb", "go_to_main_menu")})$'), conversation_fallback)
        ],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(edit_conv_handler)
    app.add_handler(broadcast_conv_handler)
    app.add_handler(checkin_conv_handler)
    app.add_handler(discount_create_conv)
    app.add_handler(CommandHandler("start", start))

    # ⭐️ NEW: Regex for admin menu buttons to support all languages
    admin_buttons_regex = (
        f'^{get_text("de", "admin_menu_discounts")}$|'
        f'^{get_text("fa", "admin_menu_discounts")}$|'
        f'^{get_text("ckb", "admin_menu_discounts")}$'
    )

    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(MessageHandler(filters.Regex(f'^{get_text("fa", "help_button")}$|^{get_text("de", "help_button")}$|^{get_text("ckb", "help_button")}$'), show_help))
    app.add_handler(MessageHandler(filters.Regex(f'^{get_text("fa", "my_tickets_button")}$|^{get_text("de", "my_tickets_button")}$|^{get_text("ckb", "my_tickets_button")}$'), my_tickets))

    app.add_handler(CommandHandler("admin", admin_menu, filters=filters.Chat(ADMIN_ID)))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.Regex(admin_buttons_regex), discounts_menu))
    app.add_handler(CommandHandler("sales", admin_sales_report, filters=filters.Chat(ADMIN_ID)))
    app.add_handler(CommandHandler("surveys", admin_survey_report, filters=filters.Chat(ADMIN_ID)))
    # 🚨 MessageHandler باید بعد از ConversationHandler باشد تا تداخل نکند
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND | filters.PHOTO | filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    print("🤖 Der Bot läuft...")
    app.run_polling()