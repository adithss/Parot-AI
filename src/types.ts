// types_updated.ts - Updated TypeScript types for multi-user meeting collaboration

export enum MeetingState {
  IDLE = "IDLE",
  RECORDING = "RECORDING",
  PROCESSING = "PROCESSING",
  ANALYSIS_READY = "ANALYSIS_READY",
  ERROR = "ERROR",
}

// Speaker diarization
export interface SpeakerSegment {
  speaker: string;
  text: string;
}

// Structured transcript segment for UI
export interface TranscriptSegment {
  id: string;
  speaker: string;
  text: string;
  timestamp: string;
  colorId: number;
}

// Live session updates
export interface StreamUpdate {
  text: string;
  source: "user" | "model";
  isFinal: boolean;
}

// Analysis result
export interface AnalysisResult {
  summary: string;
  sentiment: {
    overall: string;
    highlights: string[];
  };
  emotionAnalysis: {
    emotion: string;
    reasoning: string;
  }[];
  actionItems: string[];
  keyDecisions: string[];
  diarizedTranscript: SpeakerSegment[];
  spectrogramUrl?: string;
}

// Context-aware chatbot
export interface ChatMessage {
  sender: "user" | "bot";
  text: string;
}

// ==================== NEW: MULTI-USER COLLABORATION TYPES ====================

// User information
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
}

// Meeting participant
export interface MeetingParticipant {
  id: string;
  meeting_id: string;
  user_id: string;
  role: "host" | "participant" | "viewer";
  can_edit: boolean;
  joined_at: string;
  last_seen_at?: string;
  is_active: boolean;
  user?: User;
}

// Meeting invitation
export interface MeetingInvitation {
  id: string;
  meeting_id: string;
  inviter_user_id: string;
  invitee_user_id: string;
  status: "pending" | "accepted" | "declined" | "cancelled";
  created_at: string;
  responded_at?: string;
  inviter?: User;
  invitee?: User;
  meeting?: AnalysisResultWithMeta;
}

// Real-time transcript update
export interface RealtimeTranscriptUpdate {
  id: string;
  meeting_id: string;
  speaker_label?: string;
  text: string;
  timestamp_ms: number;
  sequence_number: number;
  is_final: boolean;
  created_at: string;
}

// Meeting with metadata (extended)
export interface AnalysisResultWithMeta {
  id: string;
  title: string;
  created_at: string;
  user_id: string;
  host_user_id?: string;
  audio_file_path?: string;
  spectrogram_url?: string;
  duration?: number;
  status: string;
  is_collaborative: boolean;
  is_live: boolean;
  started_at?: string;
  ended_at?: string;
  participants?: MeetingParticipant[];
}

// Complete meeting data
export interface CompleteMeeting extends AnalysisResultWithMeta {
  transcripts: any[];
  speakers: any[];
  summary?: {
    id: string;
    summary_text: string;
    key_points?: any;
    topics?: string[];
  };
  sentiment_analysis?: {
    overall_sentiment: string;
    highlights: string[];
    emotion_analysis: any[];
  };
  action_items: Array<{
    id: string;
    description: string;
    created_at: string;
  }>;
  key_decisions: Array<{
    id: string;
    decision: string;
    created_at: string;
  }>;
  realtime_updates?: RealtimeTranscriptUpdate[];
}

// Request types
export interface InviteUserRequest {
  invitee_username: string;
}

export interface InviteMultipleUsersRequest {
  usernames: string[];
}

export interface RespondToInvitationRequest {
  status: "accepted" | "declined";
}

export interface AddRealtimeUpdateRequest {
  speaker_label?: string;
  text: string;
  timestamp_ms: number;
  sequence_number: number;
  is_final: boolean;
}

// UI State for collaborative meetings
export interface CollaborativeMeetingState {
  meetingId: string;
  isHost: boolean;
  participants: MeetingParticipant[];
  realtimeUpdates: RealtimeTranscriptUpdate[];
  lastSequence: number;
}
