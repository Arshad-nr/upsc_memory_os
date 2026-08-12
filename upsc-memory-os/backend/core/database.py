"""
SQLAlchemy async engine, session factory, and ORM models for UPSC Memory OS.
Uses asyncpg with Supabase PostgreSQL.
"""

import uuid
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from core.config import settings

# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0
    }
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="Asia/Kolkata")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)

    # relationships
    documents: Mapped[List["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    study_sessions: Mapped[List["StudySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    revision_events: Mapped[List["RevisionEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    flashcards: Mapped[List["Flashcard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    topic_profiles: Mapped[List["UserTopicProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    urgency_cache_entries: Mapped[List["UrgencyCache"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String)
    topic_category: Mapped[Optional[str]] = mapped_column(String)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[str] = mapped_column(String, default="pending")
    file_path: Mapped[Optional[str]] = mapped_column(String)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('newspaper','coaching_notes','handwritten','official_report')",
            name="ck_documents_source_type",
        ),
        CheckConstraint(
            "ingestion_status IN ('pending','processing','complete','failed')",
            name="ck_documents_ingestion_status",
        ),
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    superseding_flashcards: Mapped[List["Flashcard"]] = relationship(
        back_populates="superseded_by_document",
        foreign_keys="[Flashcard.superseded_by_doc]",
    )


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------
class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_content: Mapped[Optional[str]] = mapped_column(Text)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer)
    qdrant_id: Mapped[Optional[str]] = mapped_column(String)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    topic_type: Mapped[Optional[str]] = mapped_column(String)
    topic_name: Mapped[Optional[str]] = mapped_column(String)
    section_header: Mapped[Optional[str]] = mapped_column(String)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )

    # relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")#many to one relationship, many chunks belong to one document
    user: Mapped["User"] = relationship(back_populates="chunks")
    flashcards: Mapped[List["Flashcard"]] = relationship(
        back_populates="chunk"
    )#one to many relationship, one chunk can have many flashcards, but each flashcard belongs to only one chunk

# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------
class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    topic_type: Mapped[str] = mapped_column(String, nullable=False)
    syllabus_area: Mapped[Optional[str]] = mapped_column(String)

    __table_args__ = (
        CheckConstraint(
            "topic_type IN ("
            "'current_affairs','government_schemes','reports_indices',"
            "'history','art_and_culture','geography','society',"
            "'polity','governance_social_justice','international_relations',"
            "'economy','agriculture','environment','science_tech',"
            "'internal_security','disaster_management',"
            "'ethics','essay','csat',"
            "'static_syllabus')",
            name="ck_topics_topic_type",
        ),
    )

    # relationships
    revision_events: Mapped[List["RevisionEvent"]] = relationship(
        back_populates="topic"
    )
    flashcards: Mapped[List["Flashcard"]] = relationship(
        back_populates="topic"
    )
    urgency_cache_entries: Mapped[List["UrgencyCache"]] = relationship(
        back_populates="topic"
    )


# ---------------------------------------------------------------------------
# Topic Relationships
# ---------------------------------------------------------------------------
class TopicRelationship(Base):
    __tablename__ = "topic_relationships"

    topic_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True
    )
    topic_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True
    )
    relationship_type: Mapped[Optional[str]] = mapped_column(
        "relationship", String
    )
    strength: Mapped[Optional[float]] = mapped_column(Float)
    source: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "relationship IN ('parent_child','sibling','application')",
            name="ck_topicrel_relationship",
        ),
        CheckConstraint(
            "source IN ('manual','llm_extracted','behavioral')",
            name="ck_topicrel_source",
        ),
    )

    # relationships
    topic_a_rel: Mapped["Topic"] = relationship(foreign_keys=[topic_a])
    topic_b_rel: Mapped["Topic"] = relationship(foreign_keys=[topic_b])


# ---------------------------------------------------------------------------
# Study Sessions
# ---------------------------------------------------------------------------
class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)
    item_count: Mapped[int] = mapped_column(Integer, default=0)

    # relationships
    user: Mapped["User"] = relationship(back_populates="study_sessions")
    revision_events: Mapped[List["RevisionEvent"]] = relationship(
        back_populates="session"
    )


# ---------------------------------------------------------------------------
# Revision Events
# ---------------------------------------------------------------------------
class RevisionEvent(Base):
    __tablename__ = "revision_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id")
    )
    flashcard_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    revised_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )
    accuracy_score: Mapped[Optional[float]] = mapped_column(Float)
    error_type: Mapped[Optional[str]] = mapped_column(String)
    time_spent_sec: Mapped[Optional[int]] = mapped_column(Integer)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_sessions.id")
    )
    session_quality: Mapped[Optional[float]] = mapped_column(Float)
    was_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(
            "error_type IN ('complete_blank','confused_similar','partial_recall','careless_mistake','correct')",
            name="ck_revevents_error_type",
        ),
        Index("idx_rev_user_topic", "user_id", "topic_id"),
        Index("idx_rev_revised_at", "revised_at", postgresql_ops={"revised_at": "DESC"}),
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="revision_events")
    topic: Mapped[Optional["Topic"]] = relationship(back_populates="revision_events")
    session: Mapped[Optional["StudySession"]] = relationship(
        back_populates="revision_events"
    )


# ---------------------------------------------------------------------------
# User Topic Profiles
# ---------------------------------------------------------------------------
class UserTopicProfile(Base):
    __tablename__ = "user_topic_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_type: Mapped[str] = mapped_column(String, primary_key=True)
    decay_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    importance_weight: Mapped[float] = mapped_column(Float, default=0.5)
    last_updated: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="topic_profiles")


# ---------------------------------------------------------------------------
# Topic Type Stats
# ---------------------------------------------------------------------------
class TopicTypeStat(Base):
    __tablename__ = "topic_type_stats"

    topic_type: Mapped[str] = mapped_column(String, primary_key=True)
    decay_constant: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[str] = mapped_column(String, default="low")
    last_updated: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------
class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id")
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    card_type: Mapped[Optional[str]] = mapped_column(String)
    llm_difficulty: Mapped[str] = mapped_column(String, default="medium")
    global_wrong_rate: Mapped[Optional[float]] = mapped_column(Float)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    deprecation_reason: Mapped[Optional[str]] = mapped_column(Text)
    superseded_by_doc: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )#superseded_by_doc is a foreign key to documents.id, meaning if this flashcard is deprecated because the source document was updated and re-ingested, we can link to the new document that supersedes it. This allows us to trace back the reason for deprecation and also potentially show the user the updated content when they encounter a deprecated flashcard.
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )
    last_shown_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint(
            "card_type IN ('flashcard','mcq')",
            name="ck_flashcards_card_type",
        ),
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="flashcards")
    chunk: Mapped[Optional["Chunk"]] = relationship(back_populates="flashcards")
    topic: Mapped[Optional["Topic"]] = relationship(back_populates="flashcards")
    superseded_by_document: Mapped[Optional["Document"]] = relationship(
        back_populates="superseding_flashcards",
        foreign_keys=[superseded_by_doc],
    )


# ---------------------------------------------------------------------------
# Urgency Cache
# ---------------------------------------------------------------------------
class UrgencyCache(Base):
    __tablename__ = "urgency_cache"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id"),
        primary_key=True,
    )
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False)
    urgency_tier: Mapped[Optional[str]] = mapped_column(String)
    computed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "urgency_tier IN ('CRITICAL','HIGH','MEDIUM','STABLE')",
            name="ck_urgencycache_tier",
        ),
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="urgency_cache_entries")#backpopulates is two way urgency_cache_entries.user will give the user object for this cache entry, and user.urgency_cache_entries will give list of cache entries for that user
    topic: Mapped["Topic"] = relationship(back_populates="urgency_cache_entries")
