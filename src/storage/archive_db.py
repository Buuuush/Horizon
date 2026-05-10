"""SQLite archive database for stored articles.

Provides the ``ArchivedArticle`` ORM model and helper functions for
creating the table and accessing a session.
"""

from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    JSON,
    create_engine,
    inspect,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class ArchivedArticle(Base):
    """SQLAlchemy model for an archived article.

    Columns correspond to the fields described in the CLAUDE.md plan.
    """

    __tablename__ = "articles"

    id = Column(String, primary_key=True)  # e.g. "rss:12345"
    title = Column(String, index=True)
    url = Column(String)
    source_type = Column(String, index=True)  # rss, hn, reddit
    source_name = Column(String)
    ai_score = Column(Float, index=True)
    tags = Column(JSON)  # list of strings
    summary = Column(String)  # first 500 chars of ai_summary
    whats_new = Column(String)
    why_it_matters = Column(String)
    background = Column(String)
    published_at = Column(DateTime, index=True)
    fetched_at = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)
    run_date = Column(String, index=True)  # YYYY-MM-DD
    profile_name = Column(String, index=True)

# ---------------------------------------------------------------------------
# Engine / Session utilities
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    """Return the path to the SQLite file (data/archive.db)."""
    return Path("data") / "archive.db"

def get_engine(echo: bool = False):
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=echo, future=True)

def get_session(echo: bool = False):
    """Create a new SQLAlchemy session.

    The caller is responsible for closing the session.
    """
    engine = get_engine(echo=echo)
    # Create tables if they do not exist
    if not inspect(engine).has_table(ArchivedArticle.__tablename__):
        Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return Session()