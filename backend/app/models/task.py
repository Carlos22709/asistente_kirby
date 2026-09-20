"""Modelo persistente de una tarea administrada por el agente secretario."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from .gmail_thread_reference import GmailThreadReference


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=10), default=TaskPriority.medium
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.pending,
        server_default=TaskStatus.pending.name,
        index=True,
        nullable=False,
    )
    source_gmail_thread_ref_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "gmail_thread_references.id",
            name="fk_tasks_source_gmail_thread_ref",
            ondelete="SET NULL",
        ),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source_gmail_thread_ref: Mapped["GmailThreadReference | None"] = relationship(
        back_populates="tasks",
        lazy="joined",
    )

    @property
    def source_gmail_thread_id(self) -> str | None:
        """Expone el identificador externo sin convertir Gmail en fuente local."""

        if self.source_gmail_thread_ref is None:
            return None
        return self.source_gmail_thread_ref.gmail_thread_id
