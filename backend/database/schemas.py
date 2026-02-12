from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Meeting Schemas
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None

class MeetingCreate(MeetingBase):
    user_id: str
    audio_file_path: Optional[str] = None
    spectrogram_url: Optional[str] = None
    duration: Optional[int] = None

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class MeetingResponse(MeetingBase):
    id: str
    user_id: str
    audio_file_path: Optional[str]
    spectrogram_url: Optional[str]
    duration: Optional[int]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Transcript Schemas
class TranscriptBase(BaseModel):
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    confidence: Optional[float] = None

class TranscriptCreate(TranscriptBase):
    meeting_id: str
    speaker_id: Optional[str] = None
    sequence_number: Optional[int] = None

class TranscriptResponse(TranscriptBase):
    id: str
    meeting_id: str
    speaker_id: Optional[str]
    sequence_number: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Speaker Schemas
class SpeakerBase(BaseModel):
    speaker_label: str
    speaker_name: Optional[str] = None

class SpeakerCreate(SpeakerBase):
    meeting_id: str
    total_speaking_time: Optional[float] = None
    segment_count: Optional[int] = 0

class SpeakerResponse(SpeakerBase):
    id: str
    meeting_id: str
    total_speaking_time: Optional[float]
    segment_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Summary Schemas
class SummaryBase(BaseModel):
    summary_text: str
    key_points: Optional[List[Dict[str, Any]]] = None
    topics: Optional[List[str]] = None

class SummaryCreate(SummaryBase):
    meeting_id: str

class SummaryResponse(SummaryBase):
    id: str
    meeting_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Sentiment Analysis Schemas
class SentimentAnalysisBase(BaseModel):
    overall_sentiment: str  # "Positive", "Negative", "Neutral"
    highlights: Optional[List[str]] = None
    emotion_analysis: Optional[List[Dict[str, str]]] = None  # [{"emotion": str, "reasoning": str}]

class SentimentAnalysisCreate(SentimentAnalysisBase):
    meeting_id: str

class SentimentAnalysisResponse(SentimentAnalysisBase):
    id: str
    meeting_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Action Item Schemas
class ActionItemBase(BaseModel):
    description: str

class ActionItemCreate(ActionItemBase):
    meeting_id: str

class ActionItemResponse(ActionItemBase):
    id: str
    meeting_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Key Decision Schemas
class KeyDecisionBase(BaseModel):
    decision: str

class KeyDecisionCreate(KeyDecisionBase):
    meeting_id: str

class KeyDecisionResponse(KeyDecisionBase):
    id: str
    meeting_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Complete Meeting Response (with all related data)
class CompleteMeetingResponse(MeetingResponse):
    transcripts: List[TranscriptResponse] = []
    speakers: List[SpeakerResponse] = []
    summary: Optional[SummaryResponse] = None
    sentiment_analysis: Optional[SentimentAnalysisResponse] = None
    action_items: List[ActionItemResponse] = []
    key_decisions: List[KeyDecisionResponse] = []
    
    class Config:
        from_attributes = True