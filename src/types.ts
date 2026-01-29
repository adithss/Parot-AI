
export enum MeetingState {
  IDLE = 'IDLE',
  RECORDING = 'RECORDING',
  PROCESSING = 'PROCESSING',
  ANALYSIS_READY = 'ANALYSIS_READY',
  ERROR = 'ERROR',
}

// NEW: For speaker diarization
export interface SpeakerSegment {
  speaker: string;
  text: string;
}

// NEW: Structured transcript segment for UI
export interface TranscriptSegment {
    id: string;
    speaker: string;
    text: string;
    timestamp: string;
    colorId: number; // 0-3 for cycling colors
}

// NEW: For live session updates
export interface StreamUpdate {
    text: string;
    source: 'user' | 'model';
    isFinal: boolean;
}

// UPDATED: To include more detailed analysis based on the architecture
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
}

// NEW: For the context-aware chatbot feature
export interface ChatMessage {
    sender: 'user' | 'bot';
    text: string;
}

// NEW: For storing meetings with metadata for the history list
export interface AnalysisResultWithMeta {
  id: string;
  title: string;
  timestamp: string;
  result: AnalysisResult;
}