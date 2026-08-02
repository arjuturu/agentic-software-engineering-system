from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class ShortUrl(Base):
    __tablename__ = "short_urls"
    __table_args__ = (CheckConstraint("click_count >= 0", name="click_count_nonnegative"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    short_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    original_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    source_type: Mapped[str] = mapped_column(String(30), default="MANUAL")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    access_events: Mapped[list[UrlAccessEvent]] = relationship(
        back_populates="short_url", cascade="all, delete-orphan"
    )


from app.database.models.url_access_event import UrlAccessEvent  # noqa: E402
