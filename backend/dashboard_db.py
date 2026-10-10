import sqlite3
import json
from pathlib import Path
from datetime import datetime


# Chemins du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FOLDER = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_FOLDER / "studyagent.db"


def get_connection():
    """Ouvre une connexion à la base SQLite."""
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """Crée les tables si elles n'existent pas encore."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'success',
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()


def log_event(
    event_type,
    detail="",
    metadata=None,
    status="success"
):
    """Enregistre une activité de StudyAgent."""

    if metadata is None:
        metadata = {}

    created_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO events (
                event_type,
                detail,
                metadata,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_type,
                detail,
                json.dumps(metadata, ensure_ascii=False),
                status,
                created_at
            )
        )

        connection.commit()


def get_dashboard_stats():
    """Calcule les statistiques à partir de l'historique."""

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT event_type, status, metadata
            FROM events
        """).fetchall()

    stats = {
        "pdf_uploaded": 0,
        "pages_processed": 0,
        "summaries_generated": 0,
        "document_questions": 0,
        "quizzes_generated": 0,
        "chat_messages": 0,
        "successful_operations": 0,
        "failed_operations": 0,
        "total_operations": len(rows)
    }

    for row in rows:
        event_type = row["event_type"]
        status = row["status"]

        try:
            metadata = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            metadata = {}

        if status == "success":
            stats["successful_operations"] += 1
        else:
            stats["failed_operations"] += 1

        if event_type == "pdf_uploaded" and status == "success":
            stats["pdf_uploaded"] += 1
            stats["pages_processed"] += int(
                metadata.get("pages", 0)
            )

        elif event_type == "summary" and status == "success":
            stats["summaries_generated"] += 1

        elif event_type == "document_question" and status == "success":
            stats["document_questions"] += 1

        elif event_type == "quiz" and status == "success":
            stats["quizzes_generated"] += 1

        elif event_type == "chat" and status == "success":
            stats["chat_messages"] += 1

    return stats


def get_recent_events(limit=15):
    """Retourne les activités les plus récentes."""

    limit = max(1, min(int(limit), 100))

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, detail, status, created_at
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [dict(row) for row in rows]


def get_dashboard_data():
    """Retourne toutes les données nécessaires au dashboard."""

    return {
        "stats": get_dashboard_stats(),
        "recent_events": get_recent_events()
    }


# Création automatique des tables au premier import
initialize_database()