"""
Migration script: Add existing project owners as ADMIN members in project_members.

Run after applying Alembic migration 002:
    python -m scripts.migrate_owners_to_members

This is a one-time migration. Safe to run multiple times (idempotent).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.membership import ProjectMember
from app.models.project import Project


def migrate():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        projects = db.query(Project).all()
        migrated = 0
        for project in projects:
            existing = db.query(ProjectMember).filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == project.user_id,
            ).first()
            if existing:
                continue

            member = ProjectMember(
                id=str(uuid.uuid4()),
                project_id=project.id,
                user_id=project.user_id,
                role="ADMIN",
                created_at=datetime.now(UTC),
            )
            db.add(member)
            migrated += 1

        db.commit()
        print(f"Migrated {migrated} project owners to ADMIN members.")
    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
