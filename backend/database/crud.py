from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from database import models, schemas

# ==================== USER OPERATIONS - SIMPLE VERSION ====================

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user - NO PASSWORD HASHING, just store it"""
    db_user = models.User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        password_hash=user.password  # Just store password as-is
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email"""
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[models.User]:
    """Get user by ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """Authenticate user - just check if password matches"""
    user = get_user_by_email(db, email)
    if not user or user.password_hash != password:  # Simple comparison
        return None
    return user

# ==================== MEETING OPERATIONS ====================

def create_meeting(db: Session, meeting: schemas.MeetingCreate) -> models.Meeting:
    """Create a new meeting"""
    db_meeting = models.Meeting(**meeting.model_dump())
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    return db_meeting

def get_meeting_by_id(db: Session, meeting_id: str) -> Optional[models.Meeting]:
    """Get meeting by ID"""
    return db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()

def get_user_meetings(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[models.Meeting]:
    """Get all meetings for a user"""
    return db.query(models.Meeting)\
        .filter(models.Meeting.user_id == user_id)\
        .order_by(desc(models.Meeting.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()

def update_meeting(db: Session, meeting_id: str, meeting_update: schemas.MeetingUpdate) -> Optional[models.Meeting]:
    """Update meeting details"""
    db_meeting = get_meeting_by_id(db, meeting_id)
    if not db_meeting:
        return None
    
    update_data = meeting_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_meeting, field, value)
    
    db.commit()
    db.refresh(db_meeting)
    return db_meeting

def delete_meeting(db: Session, meeting_id: str) -> bool:
    """Delete a meeting and all related data"""
    db_meeting = get_meeting_by_id(db, meeting_id)
    if not db_meeting:
        return False
    
    db.delete(db_meeting)
    db.commit()
    return True

# ==================== TRANSCRIPT OPERATIONS ====================

def create_transcript(db: Session, transcript: schemas.TranscriptCreate) -> models.Transcript:
    """Create a transcript segment"""
    db_transcript = models.Transcript(**transcript.model_dump())
    db.add(db_transcript)
    db.commit()
    db.refresh(db_transcript)
    return db_transcript

def create_transcripts_bulk(db: Session, transcripts: List[schemas.TranscriptCreate]) -> List[models.Transcript]:
    """Create multiple transcript segments at once"""
    db_transcripts = [models.Transcript(**t.model_dump()) for t in transcripts]
    db.add_all(db_transcripts)
    db.commit()
    for t in db_transcripts:
        db.refresh(t)
    return db_transcripts

def get_meeting_transcripts(db: Session, meeting_id: str) -> List[models.Transcript]:
    """Get all transcripts for a meeting"""
    return db.query(models.Transcript)\
        .filter(models.Transcript.meeting_id == meeting_id)\
        .order_by(models.Transcript.sequence_number)\
        .all()

# ==================== SPEAKER OPERATIONS ====================

def create_speaker(db: Session, speaker: schemas.SpeakerCreate) -> models.Speaker:
    """Create a speaker"""
    db_speaker = models.Speaker(**speaker.model_dump())
    db.add(db_speaker)
    db.commit()
    db.refresh(db_speaker)
    return db_speaker

def get_meeting_speakers(db: Session, meeting_id: str) -> List[models.Speaker]:
    """Get all speakers for a meeting"""
    return db.query(models.Speaker)\
        .filter(models.Speaker.meeting_id == meeting_id)\
        .all()

def get_speaker_by_label(db: Session, meeting_id: str, speaker_label: str) -> Optional[models.Speaker]:
    """Get speaker by label in a specific meeting"""
    return db.query(models.Speaker)\
        .filter(models.Speaker.meeting_id == meeting_id, models.Speaker.speaker_label == speaker_label)\
        .first()

# ==================== SUMMARY OPERATIONS ====================

def create_summary(db: Session, summary: schemas.SummaryCreate) -> models.Summary:
    """Create a meeting summary"""
    db_summary = models.Summary(**summary.model_dump())
    db.add(db_summary)
    db.commit()
    db.refresh(db_summary)
    return db_summary

def get_meeting_summary(db: Session, meeting_id: str) -> Optional[models.Summary]:
    """Get summary for a meeting"""
    return db.query(models.Summary)\
        .filter(models.Summary.meeting_id == meeting_id)\
        .first()

def update_summary(db: Session, meeting_id: str, summary_update: schemas.SummaryBase) -> Optional[models.Summary]:
    """Update meeting summary"""
    db_summary = get_meeting_summary(db, meeting_id)
    if not db_summary:
        return None
    
    update_data = summary_update.model_dump()
    for field, value in update_data.items():
        setattr(db_summary, field, value)
    
    db.commit()
    db.refresh(db_summary)
    return db_summary

# ==================== SENTIMENT ANALYSIS OPERATIONS ====================

def create_sentiment_analysis(db: Session, sentiment: schemas.SentimentAnalysisCreate) -> models.SentimentAnalysis:
    """Create sentiment analysis for a meeting"""
    db_sentiment = models.SentimentAnalysis(**sentiment.model_dump())
    db.add(db_sentiment)
    db.commit()
    db.refresh(db_sentiment)
    return db_sentiment

def get_meeting_sentiment(db: Session, meeting_id: str) -> Optional[models.SentimentAnalysis]:
    """Get sentiment analysis for a meeting"""
    return db.query(models.SentimentAnalysis)\
        .filter(models.SentimentAnalysis.meeting_id == meeting_id)\
        .first()

# ==================== ACTION ITEM OPERATIONS ====================

def create_action_item(db: Session, action_item: schemas.ActionItemCreate) -> models.ActionItem:
    """Create an action item"""
    db_action_item = models.ActionItem(**action_item.model_dump())
    db.add(db_action_item)
    db.commit()
    db.refresh(db_action_item)
    return db_action_item

def create_action_items_bulk(db: Session, action_items: List[schemas.ActionItemCreate]) -> List[models.ActionItem]:
    """Create multiple action items at once"""
    db_action_items = [models.ActionItem(**ai.model_dump()) for ai in action_items]
    db.add_all(db_action_items)
    db.commit()
    for ai in db_action_items:
        db.refresh(ai)
    return db_action_items

def get_meeting_action_items(db: Session, meeting_id: str) -> List[models.ActionItem]:
    """Get all action items for a meeting"""
    return db.query(models.ActionItem)\
        .filter(models.ActionItem.meeting_id == meeting_id)\
        .order_by(models.ActionItem.created_at)\
        .all()

# ==================== KEY DECISION OPERATIONS ====================

def create_key_decision(db: Session, key_decision: schemas.KeyDecisionCreate) -> models.KeyDecision:
    """Create a key decision"""
    db_key_decision = models.KeyDecision(**key_decision.model_dump())
    db.add(db_key_decision)
    db.commit()
    db.refresh(db_key_decision)
    return db_key_decision

def create_key_decisions_bulk(db: Session, key_decisions: List[schemas.KeyDecisionCreate]) -> List[models.KeyDecision]:
    """Create multiple key decisions at once"""
    db_key_decisions = [models.KeyDecision(**kd.model_dump()) for kd in key_decisions]
    db.add_all(db_key_decisions)
    db.commit()
    for kd in db_key_decisions:
        db.refresh(kd)
    return db_key_decisions

def get_meeting_key_decisions(db: Session, meeting_id: str) -> List[models.KeyDecision]:
    """Get all key decisions for a meeting"""
    return db.query(models.KeyDecision)\
        .filter(models.KeyDecision.meeting_id == meeting_id)\
        .order_by(models.KeyDecision.created_at)\
        .all()

# ==================== COMPLETE MEETING DATA ====================

def get_complete_meeting(db: Session, meeting_id: str) -> Optional[models.Meeting]:
    """Get meeting with all related data"""
    meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
    if not meeting:
        return None
    return meeting

def save_complete_meeting_data(
    db: Session,
    user_id: str,
    meeting_data: dict,
    analysis_data: dict,
    audio_file_path: str = None,
    spectrogram_url: str = None
) -> models.Meeting:
    """Save complete meeting data"""
    # Create meeting
    meeting = create_meeting(db, schemas.MeetingCreate(
        user_id=user_id,
        title=meeting_data.get("title", f"Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        description=meeting_data.get("description"),
        audio_file_path=audio_file_path,
        spectrogram_url=spectrogram_url,
        duration=meeting_data.get("duration"),
        meeting_date=datetime.now()
    ))
    
    # Create speakers
    speakers_map = {}
    if "speakers" in analysis_data:
        for speaker_label in analysis_data["speakers"]:
            speaker = create_speaker(db, schemas.SpeakerCreate(
                meeting_id=meeting.id,
                speaker_label=speaker_label
            ))
            speakers_map[speaker_label] = speaker.id
    
    # Create transcripts
    if "diarizedTranscript" in analysis_data:
        transcripts = []
        for idx, segment in enumerate(analysis_data["diarizedTranscript"]):
            speaker_label = segment.get("speaker", "Unknown")
            speaker_id = speakers_map.get(speaker_label)
            
            transcripts.append(schemas.TranscriptCreate(
                meeting_id=meeting.id,
                speaker_id=speaker_id,
                text=segment["text"],
                sequence_number=idx
            ))
        if transcripts:
            create_transcripts_bulk(db, transcripts)
    
    # Create summary
    if "summary" in analysis_data and analysis_data["summary"]:
        create_summary(db, schemas.SummaryCreate(
            meeting_id=meeting.id,
            summary_text=analysis_data["summary"],
            key_points=analysis_data.get("keyPoints"),
            topics=analysis_data.get("topics")
        ))
    
    # Create sentiment analysis
    if "sentiment" in analysis_data:
        sentiment = analysis_data["sentiment"]
        create_sentiment_analysis(db, schemas.SentimentAnalysisCreate(
            meeting_id=meeting.id,
            overall_sentiment=sentiment.get("overall", "Neutral"),
            highlights=sentiment.get("highlights", []),
            emotion_analysis=analysis_data.get("emotionAnalysis", [])
        ))
    
    # Create action items
    if "actionItems" in analysis_data and analysis_data["actionItems"]:
        action_items = []
        for item in analysis_data["actionItems"]:
            action_items.append(schemas.ActionItemCreate(
                meeting_id=meeting.id,
                description=item
            ))
        if action_items:
            create_action_items_bulk(db, action_items)
    
    # Create key decisions
    if "keyDecisions" in analysis_data and analysis_data["keyDecisions"]:
        key_decisions = []
        for decision in analysis_data["keyDecisions"]:
            key_decisions.append(schemas.KeyDecisionCreate(
                meeting_id=meeting.id,
                decision=decision
            ))
        if key_decisions:
            create_key_decisions_bulk(db, key_decisions)
    
    return meeting