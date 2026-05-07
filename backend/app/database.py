import os

from dotenv import load_dotenv

from datetime import datetime, timezone
from collections.abc import Generator

from sqlalchemy import (
    create_engine,
    String,
    DateTime,
    Text,
    ForeignKey
)

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base,
    Mapped,
    mapped_column,
    relationship,
    Session
)

load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./research_papers.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()


class Paper(Base):

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="processing",
        nullable=False
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    lines: Mapped[list["LineMap"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan"
    )

    result: Mapped["Result"] = relationship(
        back_populates="paper",
        uselist=False,
        cascade="all, delete-orphan"
    )

class LineMap(Base):

    __tablename__ = "line_map"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"),
        index=True,
        nullable=False
    )

    page_number: Mapped[int] = mapped_column(
        nullable=False
    )

    line_number: Mapped[int] = mapped_column(
        nullable=False
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    paper: Mapped["Paper"] = relationship(
        back_populates="lines"
    )

class Result(Base):

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"),
        unique=True,
        nullable=False,
        index=True
    )

    claims_json: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    
    paper: Mapped["Paper"] = relationship(
        back_populates="result"
    )

def create_tables():

    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()