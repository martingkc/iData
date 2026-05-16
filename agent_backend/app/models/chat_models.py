from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    String,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from ..db import Base
from flask import current_app
import jwt
import time
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum


class UserType(Enum):
    ADMIN = "admin"
    BASE = "base"


class CandidateStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name = mapped_column(String(32), index=True, nullable=False)
    surname = mapped_column(String(32), index=True, nullable=False)
    password_hash = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_type = mapped_column(SAEnum(UserType), nullable=False, default=UserType.BASE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    authenticated = mapped_column(Boolean, default=False)

    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    google_tokens = relationship("UserGoogleToken", back_populates="user", cascade="all, delete-orphan")
    calendar_candidates = relationship("CalendarEventCandidate", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, name=None, surname=None, email=None, password=None, user_type: UserType = UserType.BASE, id=None):
        super().__init__()
        if id is not None:
            self.id = id
        if name is not None:
            self.name = name
        if surname is not None:
            self.surname = surname
        if email is not None:
            self.email = email
        if password is not None:
            self.hash_password(password)
        self.user_type = user_type

    @staticmethod
    def verify_auth_token(token):
        try:

            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            print("Token expired")
            return None
        except jwt.InvalidTokenError:
            print("Invalid token")
            return None

        # Note: This uses Flask-SQLAlchemy style query, prefer verify_auth_token_with_session
        from ..db import SessionLocal
        db = SessionLocal()
        try:
            return db.query(User).filter_by(email=data["email"]).first()
        finally:
            db.close()

    @staticmethod
    def verify_auth_token_with_session(token, db_session):
        """Verify token using provided SQLAlchemy session."""
        try:
            data = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            print("Token expired")
            return None
        except jwt.InvalidTokenError:
            print("Invalid token")
            return None

        return db_session.query(User).filter_by(email=data["email"]).first()

    def hash_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def refresh_available_tokens(self):
        if self.user_type == UserType.ADMIN.value:
            self.available_tokens = current_app.config["ADMIN_USER_TOKEN"]
        elif getattr(UserType, "PREMIUM", None) and self.user_type == UserType.PREMIUM.value:
            self.available_tokens = current_app.config["PREMIUM_USER_TOKEN"]
        else:
            self.available_tokens = current_app.config["BASE_USER_TOKEN"]

    def change_user_type(self, new_type: UserType):
        self.user_type = new_type
        self.refresh_available_tokens()

    def generate_auth_token(self, expires_in=3600):
        payload = {"email": self.email, "exp": time.time() + expires_in}
        return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

    def authenticate(self):
        self.authenticated = True
        db.session.commit()


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("thread_id", name="uq_chat_thread_id"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Internal ID used by LangGraph 
    thread_id: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship("User", back_populates="chats")
    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    chat_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String,  # "user" | "assistant" | "tool" | "system"
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    chat = relationship("Chat", back_populates="messages")


class UserGoogleToken(Base):
    """Stores per-user Google OAuth tokens for third-party integrations."""
    __tablename__ = "user_google_tokens"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    service: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default="google_calendar",
    )
    token_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="google_tokens")


class CalendarEventCandidate(Base):
    """Stores detected calendar event candidates from transcript analysis."""
    __tablename__ = "calendar_event_candidates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        SAEnum(CandidateStatus), nullable=False, default=CandidateStatus.PENDING
    )
    google_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="calendar_candidates")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "start_datetime": self.start_datetime.isoformat() if self.start_datetime else None,
            "end_datetime": self.end_datetime.isoformat() if self.end_datetime else None,
            "description": self.description,
            "location": self.location,
            "timezone": self.timezone,
            "source_excerpt": self.source_excerpt,
            "status": self.status.value,
            "google_event_id": self.google_event_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
