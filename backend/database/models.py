from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Boolean, JSON, ARRAY, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    hosted_meetings = relationship("Meeting", foreign_keys="Meeting.host_user_id", back_populates="host")
    meetings = relationship("Meeting", foreign_keys="Meeting.user_id", back_populates="user", cascade="all, delete-orphan")
    meeting_participants = relationship("MeetingParticipant", back_populates="user", cascade="all, delete-orphan")
    sent_invitations = relationship("MeetingInvitation", foreign_keys="MeetingInvitation.inviter_user_id", back_populates="inviter")
    received_invitations = relationship("MeetingInvitation", foreign_keys="MeetingInvitation.invitee_user_id", back_populates="invitee")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    host_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    audio_file_path = Column(String(500))
    spectrogram_url = Column(String(500))
    duration = Column(Integer)  # Duration in seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    meeting_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="completed")  # pending, processing, completed, failed, live
    
    # New fields for collaborative meetings
    is_collaborative = Column(Boolean, default=False)
    is_live = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="meetings")
    host = relationship("User", foreign_keys=[host_user_id], back_populates="hosted_meetings")
    transcripts = relationship("Transcript", back_populates="meeting", cascade="all, delete-orphan")
    speakers = relationship("Speaker", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    sentiment_analysis = relationship("SentimentAnalysis", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    key_decisions = relationship("KeyDecision", back_populates="meeting", cascade="all, delete-orphan")
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")
    invitations = relationship("MeetingInvitation", back_populates="meeting", cascade="all, delete-orphan")
    realtime_updates = relationship("RealtimeTranscriptUpdate", back_populates="meeting", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Meeting(id={self.id}, title={self.title})>"


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="participant")  # host, participant, viewer
    can_edit = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User", back_populates="meeting_participants")
    
    def __repr__(self):
        return f"<MeetingParticipant(meeting_id={self.meeting_id}, user_id={self.user_id}, role={self.role})>"


class MeetingInvitation(Base):
    __tablename__ = "meeting_invitations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    inviter_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invitee_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # pending, accepted, declined, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True))
    
    # Relationships
    meeting = relationship("Meeting", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[inviter_user_id], back_populates="sent_invitations")
    invitee = relationship("User", foreign_keys=[invitee_user_id], back_populates="received_invitations")
    
    def __repr__(self):
        return f"<MeetingInvitation(id={self.id}, status={self.status})>"


class RealtimeTranscriptUpdate(Base):
    __tablename__ = "realtime_transcript_updates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    speaker_label = Column(String(100))
    text = Column(Text, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)  # Milliseconds since meeting start
    sequence_number = Column(Integer, nullable=False)
    is_final = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="realtime_updates")
    
    def __repr__(self):
        return f"<RealtimeTranscriptUpdate(meeting_id={self.meeting_id}, seq={self.sequence_number})>"


class Transcript(Base):
    __tablename__ = "transcripts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    speaker_id = Column(String, ForeignKey("speakers.id", ondelete="SET NULL"))
    text = Column(Text, nullable=False)
    start_time = Column(Float)  # Start time in seconds
    end_time = Column(Float)    # End time in seconds
    confidence = Column(Float)  # Transcription confidence score
    sequence_number = Column(Integer)  # Order of transcript segments
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="transcripts")
    speaker = relationship("Speaker")
    
    def __repr__(self):
        return f"<Transcript(id={self.id}, meeting_id={self.meeting_id})>"


class Speaker(Base):
    __tablename__ = "speakers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    speaker_label = Column(String(100), nullable=False)  # "Speaker 1", "Speaker 2", etc.
    speaker_name = Column(String(255))  # Optional custom name
    total_speaking_time = Column(Float)  # Total speaking time in seconds
    segment_count = Column(Integer, default=0)  # Number of times this speaker spoke
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="speakers")
    
    def __repr__(self):
        return f"<Speaker(id={self.id}, label={self.speaker_label})>"


class Summary(Base):
    __tablename__ = "summaries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary_text = Column(Text, nullable=False)
    key_points = Column(JSON)  # Array of key points
    topics = Column(ARRAY(String))  # Array of main topics discussed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="summary")
    
    def __repr__(self):
        return f"<Summary(id={self.id}, meeting_id={self.meeting_id})>"


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True)
    overall_sentiment = Column(String(50))  # Positive, Negative, Neutral
    highlights = Column(ARRAY(String))  # Array of highlight strings
    emotion_analysis = Column(JSON)  # Array of {emotion: string, reasoning: string}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="sentiment_analysis")
    
    def __repr__(self):
        return f"<SentimentAnalysis(id={self.id}, overall={self.overall_sentiment})>"


class ActionItem(Base):
    __tablename__ = "action_items"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=False)  # The action item text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="action_items")
    
    def __repr__(self):
        return f"<ActionItem(id={self.id}, description={self.description[:50]})>"


class KeyDecision(Base):
    __tablename__ = "key_decisions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    decision = Column(Text, nullable=False)  # The key decision text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    meeting = relationship("Meeting", back_populates="key_decisions")
    
    def __repr__(self):
        return f"<KeyDecision(id={self.id}, decision={self.decision[:50]})>"