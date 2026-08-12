"""
Pydantic v2 request/response schemas for UPSC Memory OS API.
"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr
from pydantic.alias_generators import to_camel

from models.enums import ErrorType

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------
class UserCreate(CamelModel):
    email: EmailStr
    password: str
    exam_date: date

class UserLogin(CamelModel):
    email: EmailStr
    password: str


class UserResponse(CamelModel):
    id: UUID
    email: EmailStr
    exam_date: date
    timezone: str
    onboarding_done: bool


class TokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class DocumentUploadResponse(CamelModel):
    document_id: UUID
    status: str


class DocumentResponse(CamelModel):
    id: UUID
    filename: str
    source_type: Optional[str] = None
    topic_category: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    chunk_count: int = 0
    ingestion_status: str = "pending"
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Ask / RAG
# ---------------------------------------------------------------------------
class AskRequest(CamelModel):
    question: str


class AskResponse(CamelModel):
    answer: str
    sources: List[dict] = Field(default_factory=list)
    query_type: str
    confidence: Optional[str] = None


# ---------------------------------------------------------------------------
# Flashcards / Quiz
# ---------------------------------------------------------------------------
class FlashcardResponse(CamelModel):
    id: UUID
    question: str
    answer: str
    card_type: Optional[str] = None
    difficulty: Optional[str] = None
    topic_type: Optional[str] = None


class QuizSessionRequest(CamelModel):
    size: int = 10
    topic_ids: Optional[List[UUID]] = None


class QuizAnswerRequest(CamelModel):
    session_id: UUID
    flashcard_id: UUID
    answer: str
    error_type: Optional[ErrorType] = None  # Self-reported: WHY did you get it wrong?
    time_spent_sec: Optional[int] = None


class QuizAnswerResponse(CamelModel):
    correct: bool
    score: float
    feedback: str
    error_type: Optional[str] = None
    # Sent to the frontend ONLY when the answer is wrong.
    # The UI renders these as tap-buttons: "Why did you get this wrong?"
    error_type_options: Optional[list[dict]] = Field(
        default=None,
        description="List of error type options for the frontend to display when answer is wrong",
    )


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------
class OnboardingExamDate(CamelModel):
    exam_date: date


class OnboardingSubjects(CamelModel):
    weak_subjects: List[str]


# ---------------------------------------------------------------------------
# Dashboard / Urgency
# ---------------------------------------------------------------------------
class UrgencyItem(CamelModel):
    topic_id: UUID
    topic_name: str
    topic_type: str
    urgency_score: float
    urgency_tier: str
    computed_at: Optional[str] = None


class DashboardResponse(CamelModel):
    items: List[UrgencyItem]
    critical: List[UrgencyItem] = Field(default_factory=list)
    stable: List[UrgencyItem] = Field(default_factory=list)
    days_remaining: int
    total_topics: int
