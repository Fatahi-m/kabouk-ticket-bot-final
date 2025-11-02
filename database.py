from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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
    surveys = relationship("Survey", back_populates="user")

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
    capacity = Column(Integer, nullable=True, default=None)
    # ⭐️ NEW: فیلدهای مربوط به VIP
    vip_price = Column(Integer, nullable=True)
    vip_description = Column(String, nullable=True)

    tickets = relationship("Ticket", back_populates="event")
    surveys = relationship("Survey", back_populates="event")
    discount_codes = relationship("DiscountCode", back_populates="event")

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id_str = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    issue_date = Column(DateTime, default=datetime.now)
    status = Column(String, default="pending_payment")
    # ⭐️ NEW: نوع بلیط (معمولی یا VIP)
    ticket_type = Column(String, default='regular') # 'regular' or 'vip'

    user = relationship("User", back_populates="tickets")
    event = relationship("Event", back_populates="tickets")

class Survey(Base):
    __tablename__ = 'surveys'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    event_id = Column(Integer, ForeignKey('events.id'))
    rating = Column(Integer, nullable=False)
    submission_date = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="surveys")
    event = relationship("Event", back_populates="surveys")

class DiscountCode(Base):
    __tablename__ = 'discount_codes'
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    discount_type = Column(String)
    value = Column(Float)
    max_uses = Column(Integer, default=1)
    uses_count = Column(Integer, default=0)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    event = relationship("Event", back_populates="discount_codes")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
