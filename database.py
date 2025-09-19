from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# 🚨 تنظیمات بهینه‌شده برای SQLite در محیط‌های تک فرآیندی مانند Replit
DATABASE_URL = "sqlite:///./tickets.db"
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    current_step = Column(String, default="start")
    selected_event_id = Column(Integer, ForeignKey('events.id'), nullable=True)
    language_code = Column(String, default="de")

    tickets = relationship("Ticket", back_populates="user")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    date = Column(DateTime)
    location = Column(String)
    description = Column(String)
    price = Column(Integer)
    is_active = Column(Boolean, default=True)
    is_past_event = Column(Boolean, default=False)
    poster_path = Column(String, nullable=True)

    tickets = relationship("Ticket", back_populates="event")

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id_str = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    issue_date = Column(DateTime, default=datetime.now)
    status = Column(String, default="pending_payment")

    user = relationship("User", back_populates="tickets")
    event = relationship("Event", back_populates="tickets")

# 🚨 تنظیم اتصال: check_same_thread=False برای جلوگیری از خطاهای threading
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# 🚨 استفاده از sessionmaker استاندارد
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()