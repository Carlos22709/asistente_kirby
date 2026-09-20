"""Administra referencias locales sin copiar el contenido alojado en Gmail."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.gmail_thread_reference import GmailThreadReference
from ..models.task import Task


def get_or_create_gmail_thread_reference(
    db: Session, gmail_thread_id: str
) -> GmailThreadReference:
    normalized_id = gmail_thread_id.strip()
    reference = db.scalar(
        select(GmailThreadReference).where(
            GmailThreadReference.gmail_thread_id == normalized_id
        )
    )
    if reference is not None:
        return reference

    reference = GmailThreadReference(gmail_thread_id=normalized_id)
    db.add(reference)
    db.flush()
    return reference


def set_task_gmail_thread_reference(
    db: Session, task: Task, gmail_thread_id: str | None
) -> None:
    if gmail_thread_id is None:
        task.source_gmail_thread_ref = None
        return
    task.source_gmail_thread_ref = get_or_create_gmail_thread_reference(
        db, gmail_thread_id
    )
