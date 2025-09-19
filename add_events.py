# -*- coding: utf-8 -*-
from datetime import datetime
from database import SessionLocal, Event, init_db
import os

POSTER_DIR = "posters"
if not os.path.exists(POSTER_DIR):
    os.makedirs(POSTER_DIR)
    print(f"Created directory: {POSTER_DIR}")

def add_new_event(name, date_str, time_str, location, price, is_active=True, poster_filename=None, description_de="", description_fa="", description_ckb=""):
    db = SessionLocal()
    try:
        full_date_str = f"{date_str} {time_str}"
        event_datetime = datetime.strptime(full_date_str, '%Y-%m-%d %H:%M')

        existing_event = db.query(Event).filter(Event.name == name).first()

        # ذخیره توضیحات به صورت چند زبانه (UTF-8 Compatible)
        localized_description = f"de:{description_de}|fa:{description_fa}|ckb:{description_ckb}"

        poster_path = None
        if poster_filename:
            poster_path = os.path.join(POSTER_DIR, poster_filename)
            if not os.path.exists(poster_path):
                print(f"WARNING: Poster file '{poster_path}' not found. Event will be added without poster.")
                poster_path = None

        if existing_event:
            print(f"Event '{name}' already exists. Updating its details.")
            existing_event.date = event_datetime
            existing_event.location = location
            existing_event.description = localized_description
            existing_event.price = price
            existing_event.is_active = is_active
            existing_event.poster_path = poster_path
        else:
            new_event = Event(
                name=name,
                date=event_datetime,
                location=location,
                description=localized_description,
                price=price,
                is_active=is_active,
                is_past_event=False,
                poster_path=poster_path
            )
            db.add(new_event)
            print(f"New event '{name}' added successfully.")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error adding/updating event '{name}': {e}")
    finally:
        db.close()

def set_event_as_past(event_name):
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.name == event_name).first()
        if event:
            event.is_past_event = True
            event.is_active = False
            db.commit()
            print(f"Event '{event_name}' marked as past.")
        else:
            print(f"Event '{event_name}' not found.")
    except Exception as e:
        db.rollback()
        print(f"Error setting event '{event_name}' as past: {e}")
    finally:
        db.close()

def list_all_events():
    db = SessionLocal()
    try:
        events = db.query(Event).all()
        if not events:
            print("No events found in the database.")
            return

        print("\n--- All Events in Database ---")
        for event in events:
            status = "Active" if event.is_active else "Inactive"
            past_status = "Past" if event.is_past_event else "Upcoming/Active"

            desc_parts = event.description.split('|')
            desc_dict = {}
            for part in desc_parts:
                if ':' in part:
                    lang, text = part.split(':', 1)
                    desc_dict[lang] = text

            print(f"ID: {event.id}, Name: {event.name}, Date: {event.date.strftime('%Y-%m-%d %H:%M')}, "
                  f"Location: {event.location}, Price: {event.price}, "
                  f"Status: {status}, Past: {past_status}, Poster: {event.poster_path}")
            print(f"  Description (DE): {desc_dict.get('de', 'N/A')}")
            print(f"  Description (FA): {desc_dict.get('fa', 'N/A')}")
            print(f"  Description (CKB): {desc_dict.get('ckb', 'N/A')}")
        print("----------------------------\n")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Adding/Updating example events...")

    # ✅ رویدادهای آینده (برای دکمه "رویدادهای آینده" و "خرید تیکت")
    add_new_event(
        name="Kabouk presents: Muxtar Fatahi",
        date_str="2025-08-30",
        time_str="19:30",
        location="Berlin, KulturMarktHalle",
        price=10,
        is_active=True,
        poster_filename="kabouk_summer_festival.jpg",

        # 🚨 اصلاح متون فارسی و کوردی برای اطمینان از خوانایی و صحت
        description_de="Ein unvergesslicher Abend mit der Kabuk Band in der KULTURMARKTHALLE Berlin. Sichern Sie sich jetzt Tickets für dieses einzigartige Konzert und erleben Sie eine Mischung aus traditioneller und moderner kurdischer Musik.",
        description_fa="یک شب فراموش‌نشدنی با کابوک باند در کولتور مارکت هاله‌ برلین. همین حالا بلیط خود را برای این کنسرت بی‌نظیر تهیه کنید و ترکیبی از موسیقی سنتی و مدرن کردی را تجربه کنید.",
        description_ckb="شەوێکی لەبیرنەکراو لەگەڵ گرووپی موسیقای کابووک لە هۆڵی کولتوور مارکت هالە بەرلین. ئێستا بلیتەکەت دابین بکە بۆ ئەم کۆنسێرتە ناوازەیە و تێکەڵەیەک لە مۆسیقای فۆلکلۆر و مۆدێرنی کوردی ئەزموون بکە."
    )

    # ✅ رویدادهای گذشته (برای دکمه "رویدادهای گذشته")
    add_new_event(
        name="New Year's Eve Party 2024",
        date_str="2024-12-31",
        time_str="21:00",
        location="Berlin, Event Location X",
        price=40,
        is_active=False,
        poster_filename="new_year_2024.jpg",
        description_de="Unsere legendäre Silvesterparty! Ein Rückblick auf eine großartige Nacht.",
        description_fa="جشن شب سال نو ما! مروری بر یک شب عالی.",
        description_ckb="ئاهەنگی شەوی سەری ساڵی نوێ! گەڕانەوەیەک بۆ شەوێکی نایاب."
    )
    set_event_as_past("New Year's Eve Party 2024")

    list_all_events()
    print("Event setup complete.")