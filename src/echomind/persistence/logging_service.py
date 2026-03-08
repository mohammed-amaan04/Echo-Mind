"""Database logging service — writes structured logs to system_logs."""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from echomind.db.models.system import SystemLog


def log_info(
    session: DbSession, module: str, message: str, metadata: dict | None = None
) -> None:
    session.add(SystemLog(level="INFO", message=message, module=module, metadata_json=metadata))


def log_warning(
    session: DbSession, module: str, message: str, metadata: dict | None = None
) -> None:
    session.add(
        SystemLog(level="WARNING", message=message, module=module, metadata_json=metadata)
    )


def log_error(
    session: DbSession, module: str, message: str, metadata: dict | None = None
) -> None:
    session.add(SystemLog(level="ERROR", message=message, module=module, metadata_json=metadata))
