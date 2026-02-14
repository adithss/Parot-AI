from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==================== USER SCHEMAS ====================

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

class UserSearchResult(BaseModel):
    """Search result for finding users to invite"""
    id: str
    username: str
    full_name: Optional[str] = None
    email: str
    
    class Config:
        from_attributes = True

# ==================== MEETING SCHEMAS ====================

class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None

class MeetingCreate(MeetingBase):
    user_id: str
    audio_file_path: Optional[str] = None
    spectrogram_url: Optional[str] = None
    duration: Optional[int] = None
    is_collaborative: Optional[bool] = False
    host_user_id: Optional[str] = None

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_live: Optional[bool] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class MeetingResponse(MeetingBase):
    id: str
    user_id: str
    host_user_id: Optional[str]
    audio_file_path: Optional[str]
    spectrogram_url: Optional[str]
    duration: Optional[int]
    status: str
    is_collaborative: bool
    is_live: bool
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ==================== MEETING PARTICIPANT SCHEMAS ====================

class MeetingParticipantBase(BaseModel):
    role: str = "participant"
    can_edit: bool = False

class MeetingParticipantCreate(MeetingParticipantBase):
    meeting_id: str
    user_id: str

class MeetingParticipantResponse(MeetingParticipantBase):
    id: str
    meeting_id: str
    user_id: str
    joined_at: datetime
    last_seen_at: Optional[datetime]
    is_active: bool
    user: Optional[UserSearchResult] = None  # Include user details
    
    class Config:
        from_attributes = True

# ==================== MEETING INVITATION SCHEMAS ====================

class MeetingInvitationBase(BaseModel):
    pass

class MeetingInvitationCreate(BaseModel):
    meeting_id: str
    invitee_username: str  # Username to invite

class MeetingInvitationResponse(BaseModel):
    id: str
    meeting_id: str
    inviter_user_id: str
    invitee_user_id: str
    status: str
    created_at: datetime
    responded_at: Optional[datetime]
    inviter: Optional[UserSearchResult] = None
    invitee: Optional[UserSearchResult] = None
    meeting: Optional[MeetingResponse] = None
    
    class Config:
        from_attributes = True

class InvitationResponseRequest(BaseModel):
    status: str  # "accepted" or "declined"

# ==================== REALTIME TRANSCRIPT UPDATE SCHEMAS ====================

class RealtimeTranscriptUpdateBase(BaseModel):
    speaker_label: Optional[str] = None
    text: str
    timestamp_ms: int
    sequence_number: int
    is_final: bool = False

class RealtimeTranscriptUpdateCreate(RealtimeTranscriptUpdateBase):
    meeting_id: str

class RealtimeTranscriptUpdateResponse(RealtimeTranscriptUpdateBase):
    id: str
    meeting_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== TRANSCRIPT SCHEMAS ====================

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

# ==================== SPEAKER SCHEMAS ====================

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

# ==================== SUMMARY SCHEMAS ====================
class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    is_collaborative: bool = False
    is_live: bool = False
class SummaryBase(BaseModel):
    summary_text: str
    key_points: Optional[List[Dict[str, Any]]] = None
    topics: Optional[List[str]] = None

class RealtimeUpdateCreate(BaseModel):
    speaker_label: Optional[str] = None
    text: str
    timestamp_ms: int
    sequence_number: int
    is_final: bool = False

class SummaryCreate(SummaryBase):
    meeting_id: str

class SummaryResponse(SummaryBase):
    id: str
    meeting_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# ==================== SENTIMENT ANALYSIS SCHEMAS ====================

class SentimentAnalysisBase(BaseModel):
    overall_sentiment: str  # "Positive", "Negative", "Neutral"
    highlights: Optional[List[str]] = None
    emotion_analysis: Optional[List[Dict[str, str]]] = None

class SentimentAnalysisCreate(SentimentAnalysisBase):
    meeting_id: str

class SentimentAnalysisResponse(SentimentAnalysisBase):
    id: str
    meeting_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== ACTION ITEM SCHEMAS ====================

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

# ==================== KEY DECISION SCHEMAS ====================

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

# ==================== COMPLETE MEETING RESPONSE ====================

class CompleteMeetingResponse(MeetingResponse):
    transcripts: List[TranscriptResponse] = []
    speakers: List[SpeakerResponse] = []
    summary: Optional[SummaryResponse] = None
    sentiment_analysis: Optional[SentimentAnalysisResponse] = None
    action_items: List[ActionItemResponse] = []
    key_decisions: List[KeyDecisionResponse] = []
    participants: List[MeetingParticipantResponse] = []
    realtime_updates: List[RealtimeTranscriptUpdateResponse] = []
    
    class Config:
        from_attributes = True

# ==================== ADDITIONAL REQUEST SCHEMAS ====================

class AddParticipantsRequest(BaseModel):
    """Request to add multiple participants to a meeting"""
    usernames: List[str]

class RemoveParticipantRequest(BaseModel):
    """Request to remove a participant from a meeting"""
    user_id: str