# database/crud.py - Complete CRUD operations for Parot AI with collaborative meeting support

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, and_
from typing import List, Optional
from datetime import datetime
from database import models, schemas

# ==================== USER OPERATIONS ====================

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

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Get user by username"""
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: str) -> Optional[models.User]:
    """Get user by ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def search_users(db: Session, query: str, limit: int = 10) -> List[models.User]:
    """Search users by username or email"""
    search_pattern = f"%{query}%"
    return db.query(models.User)\
        .filter(
            or_(
                models.User.username.ilike(search_pattern),
                models.User.email.ilike(search_pattern),
                models.User.full_name.ilike(search_pattern)
            )
        )\
        .limit(limit)\
        .all()

def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """Authenticate user - just check if password matches"""
    user = get_user_by_email(db, email)
    if not user or user.password_hash != password:  # Simple comparison
        return None
    return user

# ==================== MEETING OPERATIONS ====================

def create_meeting(db: Session, user_id: str, meeting: schemas.MeetingCreate):
    """Create a new meeting"""
    db_meeting = models.Meeting(
        title=meeting.title,
        description=meeting.description,
        user_id=user_id,
        host_user_id=user_id,
        is_collaborative=getattr(meeting, 'is_collaborative', False),
        is_live=getattr(meeting, 'is_live', False),
        status='live' if getattr(meeting, 'is_live', False) else 'pending',
        started_at=datetime.now() if getattr(meeting, 'is_live', False) else None
    )
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    
    # Add host as participant
    if db_meeting.is_collaborative:
        participant = models.MeetingParticipant(
            meeting_id=db_meeting.id,
            user_id=user_id,
            role='host',
            can_edit=True
        )
        db.add(participant)
        db.commit()
    
    return db_meeting

def get_meeting_by_id(db: Session, meeting_id: str) -> Optional[models.Meeting]:
    """Get meeting by ID"""
    return db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()

def get_user_meetings(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[models.Meeting]:
    """Get all meetings for a user (created by them OR where they're a participant)"""
    return db.query(models.Meeting)\
        .outerjoin(models.MeetingParticipant)\
        .filter(
            or_(
                models.Meeting.user_id == user_id,
                models.MeetingParticipant.user_id == user_id
            )
        )\
        .distinct()\
        .order_by(desc(models.Meeting.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_collaborative_meetings(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[models.Meeting]:
    """Get collaborative meetings where user is a participant"""
    return db.query(models.Meeting)\
        .join(models.MeetingParticipant)\
        .filter(
            and_(
                models.Meeting.is_collaborative == True,
                models.MeetingParticipant.user_id == user_id,
                models.MeetingParticipant.is_active == True
            )
        )\
        .order_by(desc(models.Meeting.created_at))\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_live_meetings(db: Session, user_id: str) -> List[models.Meeting]:
    """Get currently live meetings for a user"""
    return db.query(models.Meeting)\
        .outerjoin(models.MeetingParticipant)\
        .filter(
            and_(
                models.Meeting.is_live == True,
                or_(
                    models.Meeting.user_id == user_id,
                    models.MeetingParticipant.user_id == user_id
                )
            )
        )\
        .distinct()\
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

def start_meeting(db: Session, meeting_id: str) -> Optional[models.Meeting]:
    """Mark meeting as live"""
    db_meeting = get_meeting_by_id(db, meeting_id)
    if not db_meeting:
        return None
    
    db_meeting.is_live = True
    db_meeting.started_at = datetime.now()
    db_meeting.status = "live"
    
    db.commit()
    db.refresh(db_meeting)
    return db_meeting

def end_meeting(db: Session, meeting_id: str) -> Optional[models.Meeting]:
    """Mark meeting as ended"""
    db_meeting = get_meeting_by_id(db, meeting_id)
    if not db_meeting:
        return None
    
    db_meeting.is_live = False
    db_meeting.ended_at = datetime.now()
    db_meeting.status = "completed"
    
    db.commit()
    db.refresh(db_meeting)
    return db_meeting

# ==================== MEETING PARTICIPANT OPERATIONS ====================

def add_participant(
    db: Session, 
    meeting_id: str, 
    user_id: str, 
    role: str = "participant",
    can_edit: bool = False
) -> models.MeetingParticipant:
    """Add a participant to a meeting"""
    # Check if already exists
    existing = db.query(models.MeetingParticipant)\
        .filter(
            and_(
                models.MeetingParticipant.meeting_id == meeting_id,
                models.MeetingParticipant.user_id == user_id
            )
        )\
        .first()
    
    if existing:
        existing.is_active = True
        existing.role = role
        existing.can_edit = can_edit
        db.commit()
        db.refresh(existing)
        return existing
    
    db_participant = models.MeetingParticipant(
        meeting_id=meeting_id,
        user_id=user_id,
        role=role,
        can_edit=can_edit
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

def remove_participant(db: Session, meeting_id: str, user_id: str) -> bool:
    """Remove a participant from a meeting"""
    participant = db.query(models.MeetingParticipant)\
        .filter(
            and_(
                models.MeetingParticipant.meeting_id == meeting_id,
                models.MeetingParticipant.user_id == user_id
            )
        )\
        .first()
    
    if not participant:
        return False
    
    db.delete(participant)
    db.commit()
    return True

def get_meeting_participants(db: Session, meeting_id: str) -> List[models.MeetingParticipant]:
    """Get all participants for a meeting"""
    return db.query(models.MeetingParticipant)\
        .options(joinedload(models.MeetingParticipant.user))\
        .filter(
            and_(
                models.MeetingParticipant.meeting_id == meeting_id,
                models.MeetingParticipant.is_active == True
            )
        )\
        .all()

def update_participant_last_seen(db: Session, meeting_id: str, user_id: str) -> None:
    """Update last seen timestamp for a participant"""
    participant = db.query(models.MeetingParticipant)\
        .filter(
            and_(
                models.MeetingParticipant.meeting_id == meeting_id,
                models.MeetingParticipant.user_id == user_id
            )
        )\
        .first()
    
    if participant:
        participant.last_seen_at = datetime.now()
        db.commit()

def is_participant(db: Session, meeting_id: str, user_id: str) -> bool:
    """Check if user is a participant in a meeting"""
    participant = db.query(models.MeetingParticipant)\
        .filter(
            and_(
                models.MeetingParticipant.meeting_id == meeting_id,
                models.MeetingParticipant.user_id == user_id,
                models.MeetingParticipant.is_active == True
            )
        )\
        .first()
    
    return participant is not None

def is_host(db: Session, meeting_id: str, user_id: str) -> bool:
    """Check if user is the host of a meeting"""
    meeting = get_meeting_by_id(db, meeting_id)
    if not meeting:
        return False
    
    return meeting.host_user_id == user_id or meeting.user_id == user_id

# ==================== MEETING INVITATION OPERATIONS ====================

def create_invitation(
    db: Session,
    meeting_id: str,
    inviter_user_id: str,
    invitee_username: str
) -> Optional[models.MeetingInvitation]:
    """Create a meeting invitation"""
    # Find invitee by username
    invitee = get_user_by_username(db, invitee_username)
    if not invitee:
        return None
    
    # Check if invitation already exists
    existing = db.query(models.MeetingInvitation)\
        .filter(
            and_(
                models.MeetingInvitation.meeting_id == meeting_id,
                models.MeetingInvitation.invitee_user_id == invitee.id,
                models.MeetingInvitation.status == "pending"
            )
        )\
        .first()
    
    if existing:
        return existing
    
    db_invitation = models.MeetingInvitation(
        meeting_id=meeting_id,
        inviter_user_id=inviter_user_id,
        invitee_user_id=invitee.id,
        status="pending"
    )
    db.add(db_invitation)
    db.commit()
    db.refresh(db_invitation)
    return db_invitation

def get_user_invitations(db: Session, user_id: str, status: Optional[str] = None) -> List[models.MeetingInvitation]:
    """Get invitations for a user"""
    query = db.query(models.MeetingInvitation)\
        .options(
            joinedload(models.MeetingInvitation.inviter),
            joinedload(models.MeetingInvitation.meeting)
        )\
        .filter(models.MeetingInvitation.invitee_user_id == user_id)
    
    if status:
        query = query.filter(models.MeetingInvitation.status == status)
    
    return query.order_by(desc(models.MeetingInvitation.created_at)).all()

def respond_to_invitation(db: Session, invitation_id: str, status: str) -> Optional[models.MeetingInvitation]:
    """Respond to an invitation (accept/decline)"""
    invitation = db.query(models.MeetingInvitation)\
        .filter(models.MeetingInvitation.id == invitation_id)\
        .first()
    
    if not invitation or invitation.status != "pending":
        return None
    
    invitation.status = status
    invitation.responded_at = datetime.now()
    
    # If accepted, add as participant
    if status == "accepted":
        add_participant(
            db,
            meeting_id=invitation.meeting_id,
            user_id=invitation.invitee_user_id,
            role="participant"
        )
    
    db.commit()
    db.refresh(invitation)
    return invitation

# ==================== REALTIME TRANSCRIPT UPDATE OPERATIONS ====================

def add_realtime_update(db: Session, meeting_id: str, update: schemas.RealtimeUpdateCreate):
    """Add a real-time transcript update"""
    db_update = models.RealtimeTranscriptUpdate(
        meeting_id=meeting_id,
        speaker_label=update.speaker_label,
        text=update.text,
        timestamp_ms=update.timestamp_ms,
        sequence_number=update.sequence_number,
        is_final=update.is_final,
        created_at=datetime.now()
    )
    db.add(db_update)
    db.commit()
    db.refresh(db_update)
    return db_update

def create_realtime_update(db: Session, update: schemas.RealtimeTranscriptUpdateCreate) -> models.RealtimeTranscriptUpdate:
    """Create a realtime transcript update"""
    db_update = models.RealtimeTranscriptUpdate(**update.model_dump())
    db.add(db_update)
    db.commit()
    db.refresh(db_update)
    return db_update

def get_realtime_updates(
    db: Session, 
    meeting_id: str, 
    after_sequence: Optional[int] = None,
    limit: int = 100
) -> List[models.RealtimeTranscriptUpdate]:
    """Get realtime updates for a meeting"""
    query = db.query(models.RealtimeTranscriptUpdate)\
        .filter(models.RealtimeTranscriptUpdate.meeting_id == meeting_id)
    
    if after_sequence is not None:
        query = query.filter(models.RealtimeTranscriptUpdate.sequence_number > after_sequence)
    
    return query\
        .order_by(models.RealtimeTranscriptUpdate.sequence_number)\
        .limit(limit)\
        .all()

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
    meeting = db.query(models.Meeting)\
        .options(
            joinedload(models.Meeting.participants).joinedload(models.MeetingParticipant.user),
            joinedload(models.Meeting.transcripts),
            joinedload(models.Meeting.speakers),
            joinedload(models.Meeting.summary),
            joinedload(models.Meeting.sentiment_analysis),
            joinedload(models.Meeting.action_items),
            joinedload(models.Meeting.key_decisions),
            joinedload(models.Meeting.realtime_updates)
        )\
        .filter(models.Meeting.id == meeting_id)\
        .first()
    
    return meeting

def save_complete_meeting_data(
    db: Session,
    user_id: str,
    meeting_data: dict,
    analysis_data: dict,
    audio_file_path: str = None,
    spectrogram_url: str = None,
    is_collaborative: bool = False,
    meeting_id: str = None  # NEW: Support updating existing meetings
) -> models.Meeting:
    """
    Save complete meeting data with analysis
    If meeting_id is provided, update existing meeting instead of creating new
    """
    try:
        if meeting_id:
            # UPDATE EXISTING MEETING
            meeting = db.query(models.Meeting).filter(models.Meeting.id == meeting_id).first()
            if not meeting:
                raise Exception(f"Meeting {meeting_id} not found")
            
            # Update meeting fields
            meeting.status = "completed"
            meeting.spectrogram_url = spectrogram_url
            meeting.updated_at = datetime.now()
            if audio_file_path:
                meeting.audio_file_path = audio_file_path
            
            # Delete existing analysis data to replace it
            db.query(models.Transcript).filter(models.Transcript.meeting_id == meeting_id).delete()
            db.query(models.Speaker).filter(models.Speaker.meeting_id == meeting_id).delete()
            db.query(models.Summary).filter(models.Summary.meeting_id == meeting_id).delete()
            db.query(models.SentimentAnalysis).filter(models.SentimentAnalysis.meeting_id == meeting_id).delete()
            db.query(models.ActionItem).filter(models.ActionItem.meeting_id == meeting_id).delete()
            db.query(models.KeyDecision).filter(models.KeyDecision.meeting_id == meeting_id).delete()
            
            db.flush()  # Ensure deletions are committed before inserts
            
        else:
            # CREATE NEW MEETING
            meeting = models.Meeting(
                user_id=user_id,
                host_user_id=user_id if is_collaborative else None,
                title=meeting_data.get("title", f"Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                description=meeting_data.get("description"),
                audio_file_path=audio_file_path,
                spectrogram_url=spectrogram_url,
                duration=meeting_data.get("duration"),
                meeting_date=datetime.now(),
                is_collaborative=is_collaborative,
                status="completed"
            )
            db.add(meeting)
            db.flush()  # Get the meeting ID
            meeting_id = meeting.id
            
            # Add host as participant for collaborative meetings
            if is_collaborative:
                participant = models.MeetingParticipant(
                    meeting_id=meeting_id,
                    user_id=user_id,
                    role='host',
                    can_edit=True
                )
                db.add(participant)
        
        # Create speakers
        speakers_map = {}
        if "speakers" in analysis_data and analysis_data["speakers"]:
            for speaker_label in analysis_data["speakers"]:
                speaker = models.Speaker(
                    meeting_id=meeting_id,
                    speaker_label=speaker_label
                )
                db.add(speaker)
                db.flush()
                speakers_map[speaker_label] = speaker.id
        
        # Create transcripts
        if "diarizedTranscript" in analysis_data and analysis_data["diarizedTranscript"]:
            for idx, segment in enumerate(analysis_data["diarizedTranscript"]):
                speaker_label = segment.get("speaker", "Unknown")
                speaker_id = speakers_map.get(speaker_label)
                
                transcript = models.Transcript(
                    meeting_id=meeting_id,
                    speaker_id=speaker_id,
                    text=segment.get("text", ""),
                    sequence_number=idx
                )
                db.add(transcript)
        
        # Create summary
        if "summary" in analysis_data and analysis_data["summary"]:
            summary = models.Summary(
                meeting_id=meeting_id,
                summary_text=analysis_data["summary"],
                key_points=analysis_data.get("keyPoints"),
                topics=analysis_data.get("topics")
            )
            db.add(summary)
        
        # Create sentiment analysis
        if "sentiment" in analysis_data and analysis_data["sentiment"]:
            sentiment = analysis_data["sentiment"]
            sentiment_analysis = models.SentimentAnalysis(
                meeting_id=meeting_id,
                overall_sentiment=sentiment.get("overall", "Neutral"),
                highlights=sentiment.get("highlights", []),
                emotion_analysis=analysis_data.get("emotionAnalysis", [])
            )
            db.add(sentiment_analysis)
        
        # Create action items
        if "actionItems" in analysis_data and analysis_data["actionItems"]:
            for item in analysis_data["actionItems"]:
                if isinstance(item, str):
                    action_item = models.ActionItem(
                        meeting_id=meeting_id,
                        description=item
                    )
                    db.add(action_item)
        
        # Create key decisions
        if "keyDecisions" in analysis_data and analysis_data["keyDecisions"]:
            for decision in analysis_data["keyDecisions"]:
                if isinstance(decision, str):
                    key_decision = models.KeyDecision(
                        meeting_id=meeting_id,
                        decision=decision
                    )
                    db.add(key_decision)
        
        # Commit all changes
        db.commit()
        db.refresh(meeting)
        return meeting
        
    except Exception as e:
        db.rollback()
        raise e