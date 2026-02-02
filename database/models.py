from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base


class PostType(enum.Enum):
    FAIR = "fair"  # Честный слот
    RANDOM = "random"  # Случайный слот


class PostStatus(enum.Enum):
    PENDING = "pending"  # Ожидает модерации
    APPROVED = "approved"  # Одобрен
    DELETED = "deleted"  # Удален
    MODERATION = "moderation"  # На модерации (есть жалобы)
    REJECTED = "rejected"  # Отклонен админом (требует замены)


class SanctionType(enum.Enum):
    WARNING = "warning"  # Предупреждение
    DAY_BAN = "day_ban"  # Блок на 1 день
    SESSION_BAN = "session_ban"  # Блок на сессию
    ACCOUNT_BAN = "account_ban"  # Блок аккаунта


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    channel_link = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    inactive_days_count = Column(Integer, default=0, nullable=False)
    
    # Статистика
    posts_count = Column(Integer, default=0, nullable=False)
    views_received = Column(Integer, default=0, nullable=False)
    likes_received = Column(Integer, default=0, nullable=False)
    subscribers_gained = Column(Integer, default=0, nullable=False)
    
    # Связи
    posts = relationship("Post", back_populates="author")
    complaints = relationship("Complaint", back_populates="complainer")
    sanctions = relationship("Sanction", back_populates="user")
    viewed_posts = relationship("PostView", back_populates="viewer")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    
    # Связи
    posts = relationship("Post", back_populates="task")
    sessions = relationship("Session", back_populates="task")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    content_submission_deadline = Column(DateTime, nullable=False)
    distribution_completed = Column(Boolean, default=False, nullable=False)
    
    # Связи
    task = relationship("Task", back_populates="sessions")
    posts = relationship("Post", back_populates="session")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    
    post_type = Column(SQLEnum(PostType, native_enum=False), nullable=True)  # None = еще не распределен
    status = Column(SQLEnum(PostStatus, native_enum=False), default=PostStatus.PENDING, nullable=False)
    
    media_file_id = Column(String(500), nullable=False)  # Telegram file_id
    media_type = Column(String(50), nullable=False)  # 'photo' or 'video'
    file_path = Column(String(1000), nullable=True)  # Локальный путь к файлу
    
    complaints_count = Column(Integer, default=0, nullable=False)
    views_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    author = relationship("User", back_populates="posts")
    task = relationship("Task", back_populates="posts")
    session = relationship("Session", back_populates="posts")
    complaints = relationship("Complaint", back_populates="post")
    views = relationship("PostView", back_populates="post")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    complainer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    post = relationship("Post", back_populates="complaints")
    complainer = relationship("User", back_populates="complaints")


class PostView(Base):
    __tablename__ = "post_views"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    viewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    liked = Column(Boolean, default=False, nullable=False)
    subscribed = Column(Boolean, default=False, nullable=False)
    viewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связи
    post = relationship("Post", back_populates="views")
    viewer = relationship("User", back_populates="viewed_posts")


class Sanction(Base):
    __tablename__ = "sanctions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sanction_type = Column(SQLEnum(SanctionType, native_enum=False), nullable=False)
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # None = постоянный бан
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="sanctions")

