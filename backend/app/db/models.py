"""Schema. User data and personal catalogs carry user_id; ownerless catalog rows retain legacy data."""
from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        PrimaryKeyConstraint, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)          # stored lowercase
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(300))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(INET)
    success: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (Index("ix_login_attempts_username_at", "username", "at"),
                      Index("ix_login_attempts_ip_at", "ip", "at"),
                      Index("ix_login_attempts_at", "at"))


class CaptchaRedemption(Base):
    __tablename__ = "captcha_redemptions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class LoginProtectionSetting(Base):
    __tablename__ = "login_protection_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    policy: Mapped[dict] = mapped_column(JSONB)


class LoginBan(Base):
    __tablename__ = "login_bans"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(INET)
    username: Mapped[str] = mapped_column(String(64))
    failures: Mapped[int] = mapped_column(Integer)
    stage: Mapped[int] = mapped_column(Integer)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("ip", "username", name="uq_login_bans_identity"),)


# ---- private company catalog; ownerless rows preserve legacy shared data ----

class ReportType(Base):
    __tablename__ = "report_types"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_report_types_user_name"),
                      UniqueConstraint("id", "user_id", name="uq_report_types_id_user"))


class Project(Base):
    __tablename__ = "projects"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_projects_user_name"),
                      UniqueConstraint("id", "user_id", name="uq_projects_id_user"))


class Story(Base):
    __tablename__ = "stories"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        UniqueConstraint("id", "user_id", name="uq_stories_id_user"),
        ForeignKeyConstraint(["project_id", "user_id"], ["projects.id", "projects.user_id"],
                             name="fk_stories_project_owner"),
    )


# ---- per-user data ----

class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    budget_minutes: Mapped[float | None] = mapped_column(Float)
    budget_since: Mapped[date | None] = mapped_column(Date)
    report_type_id: Mapped[int | None] = mapped_column(ForeignKey("report_types.id", ondelete="SET NULL"))
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"))
    fill_weight: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        UniqueConstraint("id", "user_id", name="uq_tags_id_user"),
        ForeignKeyConstraint(["report_type_id", "user_id"], ["report_types.id", "report_types.user_id"],
                             name="fk_tags_report_type_owner"),
        ForeignKeyConstraint(["story_id", "user_id"], ["stories.id", "stories.user_id"],
                             name="fk_tags_story_owner"),
    )


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    jalali_year: Mapped[int] = mapped_column(Integer)
    jalali_month: Mapped[int] = mapped_column(Integer)
    jalali_day: Mapped[int] = mapped_column(Integer)
    gregorian_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(Text)
    start_time: Mapped[str | None] = mapped_column(String(5))      # "HH:MM"
    end_time: Mapped[str | None] = mapped_column(String(5))
    duration_minutes: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="running", server_default="running")
    accumulated_minutes: Mapped[float] = mapped_column(Float, default=0, server_default=text("0"))
    segment_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id"))
    entered_main_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    meeting_with: Mapped[str | None] = mapped_column(Text)
    meeting_minutes: Mapped[float | None] = mapped_column(Float)
    adjust_minutes: Mapped[float] = mapped_column(Float, default=0, server_default=text("0"))
    report_type_id: Mapped[int | None] = mapped_column(ForeignKey("report_types.id", ondelete="SET NULL"))
    outside_company: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    planned_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    fill_minutes: Mapped[float] = mapped_column(Float, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["report_type_id", "user_id"], ["report_types.id", "report_types.user_id"],
                             name="fk_tasks_report_type_owner"),
        ForeignKeyConstraint(["tag_id", "user_id"], ["tags.id", "tags.user_id"], name="fk_tasks_tag_owner"),
        CheckConstraint("status in ('running','paused','done')", name="ck_tasks_status"),
        Index("ix_tasks_user_gdate", "user_id", "gregorian_date"),
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_jalali", "user_id", "jalali_year", "jalali_month", "jalali_day"),
    )


class TaskSegment(Base):
    __tablename__ = "task_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class PlannedTask(Base):
    __tablename__ = "planned_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    jalali_year: Mapped[int] = mapped_column(Integer)
    jalali_month: Mapped[int] = mapped_column(Integer)
    jalali_day: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        Index("ix_planned_user_date", "user_id", "jalali_year", "jalali_month", "jalali_day"),
        ForeignKeyConstraint(["tag_id", "user_id"], ["tags.id", "tags.user_id"], name="fk_planned_tag_owner"),
    )


class PresenceSegment(Base):
    __tablename__ = "presence_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(String(10))
    __table_args__ = (Index("ix_presence_user_started", "user_id", "started_at"),)


class UserSetting(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)
    __table_args__ = (PrimaryKeyConstraint("user_id", "key"),)


class AuditLog(Base):
    """task_deleted / fill_rollback / tag_merge - what the desktop kept in deleted_tasks and settings logs."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
