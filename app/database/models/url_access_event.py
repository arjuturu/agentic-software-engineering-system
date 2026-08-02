from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base


class UrlAccessEvent(Base):
    __tablename__ = "url_access_events"
    __table_args__ = (
        Index("ix_url_access_events_short_url_id", "short_url_id"),
        Index("ix_url_access_events_accessed_at", "accessed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    short_url_id: Mapped[str] = mapped_column(ForeignKey("short_urls.id"))
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    referrer: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)

    short_url: Mapped[ShortUrl] = relationship(back_populates="access_events")


from app.database.models.short_url import ShortUrl  # noqa: E402
