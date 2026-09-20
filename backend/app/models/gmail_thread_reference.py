"""Referencia mínima a un hilo cuyo contenido permanece en Gmail."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .task import Task


class GmailThreadReference(Base):
    __tablename__ = "gmail_thread_references"
    __table_args__ = (
        Index(
            "ix_gmail_thread_references_thread_id",
            "gmail_thread_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="source_gmail_thread_ref",
        passive_deletes=True,
    )
