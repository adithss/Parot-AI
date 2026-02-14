// API Base URL - update this to match your backend
export const API_BASE_URL = "http://localhost:8000";
// ============================================================================
// AUTHENTICATION HELPERS
// ============================================================================

/**
 * Get authentication token from localStorage
 */
const getAuthToken = (): string | null => {
  return localStorage.getItem("parotAuthToken");
};

/**
 * Get authentication headers for API requests
 */
const getAuthHeaders = (): HeadersInit => {
  const token = getAuthToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return headers;
};

/**
 * Handle API errors and check for authentication issues
 */
const handleApiError = async (response: Response) => {
  if (response.status === 401) {
    // Unauthorized - clear token and redirect to login
    localStorage.removeItem("parotAuthToken");
    localStorage.removeItem("parotUser");
    window.location.href = "/"; // Redirect to landing page
    throw new Error("Session expired. Please login again.");
  }

  const error = await response
    .json()
    .catch(() => ({ detail: "Unknown error" }));
  throw new Error(error.detail || `Request failed: ${response.statusText}`);
};

// ============================================================================
// RECORDING FUNCTIONS
// ============================================================================

let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];

export const startRecording = async (): Promise<void> => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.start();
  } catch (error) {
    console.error("Error starting recording:", error);
    throw new Error("Failed to access microphone. Please check permissions.");
  }
};

export const stopRecording = async (): Promise<{
  base64: string;
  mimeType: string;
}> => {
  return new Promise((resolve, reject) => {
    if (!mediaRecorder) {
      reject(new Error("No active recording found"));
      return;
    }

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, {
        type: mediaRecorder!.mimeType,
      });
      const reader = new FileReader();

      reader.onloadend = () => {
        const base64String = (reader.result as string).split(",")[1];
        resolve({
          base64: base64String,
          mimeType: audioBlob.type,
        });
      };

      reader.onerror = () => {
        reject(new Error("Failed to convert audio to base64"));
      };

      reader.readAsDataURL(audioBlob);

      // Stop all tracks
      if (mediaRecorder?.stream) {
        mediaRecorder.stream.getTracks().forEach((track) => track.stop());
      }
    };

    mediaRecorder.stop();
  });
};

// ============================================================================
// TRANSCRIPTION & ANALYSIS FUNCTIONS (WITH AUTHENTICATION)
// ============================================================================

export const transcribeAudio = async (
  base64Audio: string,
  mimeType: string,
): Promise<{
  transcript: string;
  spectrogramUrl?: string;
  meetingId?: string;
}> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        audio_base64: base64Audio,
        mime_type: mimeType,
      }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.transcript) {
      throw new Error("Invalid response from transcription service");
    }

    return {
      transcript: data.transcript,
      spectrogramUrl: data.spectrogramUrl,
      meetingId: data.meetingId,
    };
  } catch (error) {
    console.error("Transcription error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to transcribe audio. Please try again.");
  }
};

export const analyzeTranscript = async (transcript: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        transcript: transcript,
      }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.analysis) {
      throw new Error("Invalid response from analysis service");
    }

    return data.analysis;
  } catch (error) {
    console.error("Analysis error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to analyze transcript. Please try again.");
  }
};

// ============================================================================
// MEETING CONTEXT QUERY (WITH AUTHENTICATION)
// ============================================================================

/**
 * Query the meeting context with a follow-up question
 * This function sends the meeting analysis and user question to the backend
 * to get contextual answers about the meeting
 */
export const queryMeetingContext = async (
  meetingResult: any,
  question: string,
): Promise<string> => {
  try {
    // Format transcript - handle both array and string formats
    let transcriptText = "";
    if (Array.isArray(meetingResult.diarizedTranscript)) {
      transcriptText = formatTranscriptForContext(
        meetingResult.diarizedTranscript,
      );
    } else if (typeof meetingResult.diarizedTranscript === "string") {
      transcriptText = meetingResult.diarizedTranscript;
    }

    // Prepare the context payload with meeting information
    const contextPayload = {
      transcript: transcriptText,
      summary: meetingResult.summary,
      sentiment: meetingResult.sentiment,
      emotionAnalysis: meetingResult.emotionAnalysis,
      actionItems: meetingResult.actionItems,
      keyDecisions: meetingResult.keyDecisions,
      question: question,
    };

    const response = await fetch(`${API_BASE_URL}/api/query-context`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(contextPayload),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.answer) {
      throw new Error("Invalid response from query service");
    }

    return data.answer;
  } catch (error) {
    console.error("Query context error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to query meeting context. Please try again.");
  }
};

/**
 * Helper function to format the diarized transcript into a readable string
 */
const formatTranscriptForContext = (
  diarizedTranscript: Array<{ speaker: string; text: string }>,
): string => {
  if (!diarizedTranscript || diarizedTranscript.length === 0) {
    return "";
  }

  return diarizedTranscript
    .map((segment) => `${segment.speaker}: ${segment.text}`)
    .join("\n\n");
};

// ============================================================================
// TRANSLATION FUNCTIONS (WITH AUTHENTICATION)
// ============================================================================

/**
 * Map language names to language codes
 */
const getLanguageCode = (language: string): string => {
  const languageMap: { [key: string]: string } = {
    english: "en",
    spanish: "es",
    french: "fr",
    german: "de",
    italian: "it",
    portuguese: "pt",
    russian: "ru",
    chinese: "zh",
    japanese: "ja",
    arabic: "ar",
    hindi: "hi",
    korean: "ko",
    dutch: "nl",
    polish: "pl",
    turkish: "tr",
    malayalam: "ml",
  };

  // Convert to lowercase for matching
  const lowerLang = language.toLowerCase();

  // If it's already a code (2 letters), return as-is
  if (language.length === 2) {
    return language.toLowerCase();
  }

  // Otherwise, look up the code
  return languageMap[lowerLang] || language;
};

/**
 * Translate content to a target language
 */
export const translateContent = async (
  result: any,
  targetLanguage: string,
): Promise<any> => {
  try {
    // Convert language name to code (e.g., "French" -> "fr")
    const targetLanguageCode = getLanguageCode(targetLanguage);

    // Prepare content to translate
    const contentToTranslate = {
      summary: result.summary,
      actionItems: result.actionItems,
      keyDecisions: result.keyDecisions,
      diarizedTranscript: result.diarizedTranscript,
      sentiment: result.sentiment,
      emotionAnalysis: result.emotionAnalysis,
    };

    const response = await fetch(`${API_BASE_URL}/api/translate`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        content: contentToTranslate,
        target_language: targetLanguageCode,
        source_language: "en", // Always translate from English
      }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.translated_content) {
      throw new Error("Invalid response from translation service");
    }

    return data.translated_content;
  } catch (error) {
    console.error("Translation error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to translate content. Please try again.");
  }
};

// ============================================================================
// REALTIME PROCESSING (WITH AUTHENTICATION)
// ============================================================================

/**
 * Process complete real-time audio after large transcription is ready
 * This sends the recorded audio to backend for diarization and analysis
 */
export const processRealtimeComplete = async (
  audioBlob: Blob,
): Promise<any> => {
  try {
    // Convert blob to base64
    const base64Audio = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = (reader.result as string).split(",")[1];
        resolve(base64String);
      };
      reader.onerror = () => {
        reject(new Error("Failed to convert audio to base64"));
      };
      reader.readAsDataURL(audioBlob);
    });

    const response = await fetch(
      `${API_BASE_URL}/api/process-realtime-complete`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          audio_base64: base64Audio,
          mime_type: audioBlob.type,
        }),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.analysis) {
      throw new Error("Invalid response from processing service");
    }

    return {
      ...data.analysis,
      spectrogramUrl: data.spectrogramUrl,
      meetingId: data.meetingId, // ✅ Return meeting ID from database
    };
  } catch (error) {
    console.error("Real-time complete processing error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to process real-time audio. Please try again.");
  }
};

// ============================================================================
// MEETING API FUNCTIONS (DATABASE-BACKED)
// ============================================================================

/**
 * Get all meetings for the authenticated user from the database
 */
export const getUserMeetings = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Error fetching meetings:", error);
    throw error;
  }
};

/**
 * Get a specific meeting by ID with complete analysis data
 */
export const getMeetingById = async (meetingId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings/${meetingId}`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Error fetching meeting:", error);
    throw error;
  }
};

/**
 * Delete a meeting
 */
export const deleteMeeting = async (meetingId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings/${meetingId}`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Error deleting meeting:", error);
    throw error;
  }
};

/**
 * Check backend health
 */
export const checkBackendHealth = async (): Promise<boolean> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    return false;
  }
};

// ============================================================================
// AUTH FUNCTIONS
// ============================================================================

/**
 * User signup
 */
export const signup = async (userData: {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Signup failed" }));
      throw new Error(error.detail || "Signup failed");
    }

    return response.json();
  } catch (error) {
    console.error("Signup error:", error);
    throw error;
  }
};

/**
 * User login
 */
export const login = async (credentials: {
  email: string;
  password: string;
}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Login failed" }));
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();

    // Store token in localStorage
    if (data.access_token) {
      localStorage.setItem("parotAuthToken", data.access_token);
      localStorage.setItem("parotUser", JSON.stringify(data.user));
    }

    return data;
  } catch (error) {
    console.error("Login error:", error);
    throw error;
  }
};

/**
 * User logout
 */
export const logout = () => {
  localStorage.removeItem("parotAuthToken");
  localStorage.removeItem("parotUser");
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = (): boolean => {
  return !!getAuthToken();
};

/**
 * Get current user data
 */
export const getCurrentUser = () => {
  const userStr = localStorage.getItem("parotUser");
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
};

// ============================================================================
// COLLABORATIVE MEETING FUNCTIONS
// ============================================================================

/**
 * Create a new collaborative meeting
 */
export const createCollaborativeMeeting = async (meetingData: {
  title: string;
  description?: string;
}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        ...meetingData,
        is_collaborative: true,
        is_live: true,
      }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Create collaborative meeting error:", error);
    throw error;
  }
};

/**
 * Search for users by username or email
 */
export const searchUsers = async (query: string, limit: number = 10) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/users/search?q=${encodeURIComponent(query)}&limit=${limit}`,
      {
        method: "GET",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Search users error:", error);
    throw error;
  }
};

/**
 * Invite a user to a meeting
 */
export const inviteUserToMeeting = async (
  meetingId: string,
  username: string,
) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/invite`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          meeting_id: meetingId,
          invitee_username: username,
        }),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Invite user error:", error);
    throw error;
  }
};

/**
 * Invite multiple users to a meeting
 */
export const inviteMultipleUsers = async (
  meetingId: string,
  usernames: string[],
) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/invite-multiple`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          usernames,
        }),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Invite multiple users error:", error);
    throw error;
  }
};

/**
 * Get user's invitations
 */
export const getMyInvitations = async (status?: string) => {
  try {
    const url = status
      ? `${API_BASE_URL}/api/invitations?status=${status}`
      : `${API_BASE_URL}/api/invitations`;

    const response = await fetch(url, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Get invitations error:", error);
    throw error;
  }
};

/**
 * Respond to a meeting invitation
 */
export const respondToInvitation = async (
  invitationId: string,
  status: "accepted" | "declined",
) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/invitations/${invitationId}/respond`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ status }),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Respond to invitation error:", error);
    throw error;
  }
};

/**
 * Get meeting participants
 */
export const getMeetingParticipants = async (meetingId: string) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/participants`,
      {
        method: "GET",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Get participants error:", error);
    throw error;
  }
};

/**
 * Remove a participant from a meeting
 */
export const removeParticipant = async (meetingId: string, userId: string) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/participants/${userId}`,
      {
        method: "DELETE",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Remove participant error:", error);
    throw error;
  }
};

/**
 * Start a collaborative meeting (mark as live)
 */
export const startMeeting = async (meetingId: string) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/start`,
      {
        method: "POST",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Start meeting error:", error);
    throw error;
  }
};

/**
 * End a collaborative meeting
 */
export const endMeeting = async (meetingId: string) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/end`,
      {
        method: "POST",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("End meeting error:", error);
    throw error;
  }
};

/**
 * Get live meetings
 */
export const getLiveMeetings = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings/live`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Get live meetings error:", error);
    throw error;
  }
};

/**
 * Get collaborative meetings
 */
export const getCollaborativeMeetings = async (
  skip: number = 0,
  limit: number = 100,
) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/collaborative?skip=${skip}&limit=${limit}`,
      {
        method: "GET",
        headers: getAuthHeaders(),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Get collaborative meetings error:", error);
    throw error;
  }
};

/**
 * Add a real-time transcript update
 */
export const addRealtimeUpdate = async (
  meetingId: string,
  update: {
    speaker_label?: string;
    text: string;
    timestamp_ms: number;
    sequence_number: number;
    is_final: boolean;
  },
) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/meetings/${meetingId}/realtime-updates`,
      {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          meeting_id: meetingId,
          ...update,
        }),
      },
    );

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Add realtime update error:", error);
    throw error;
  }
};

/**
 * Get real-time transcript updates
 */
export const getRealtimeUpdates = async (
  meetingId: string,
  afterSequence?: number,
  limit: number = 100,
) => {
  try {
    let url = `${API_BASE_URL}/api/meetings/${meetingId}/realtime-updates?limit=${limit}`;
    if (afterSequence !== undefined) {
      url += `&after_sequence=${afterSequence}`;
    }

    const response = await fetch(url, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    return response.json();
  } catch (error) {
    console.error("Get realtime updates error:", error);
    throw error;
  }
};

/**
 * Process real-time audio with collaboration support
 */
export const processRealtimeCompleteWithCollaboration = async (
  audioBlob: Blob,
  isCollaborative: boolean = false,
  meetingId?: string,
): Promise<any> => {
  try {
    // Convert blob to base64
    const base64Audio = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = (reader.result as string).split(",")[1];
        resolve(base64String);
      };
      reader.onerror = () => {
        reject(new Error("Failed to convert audio to base64"));
      };
      reader.readAsDataURL(audioBlob);
    });

    let url = `${API_BASE_URL}/api/process-realtime-complete?is_collaborative=${isCollaborative}`;
    if (meetingId) {
      url += `&meeting_id=${meetingId}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        audio_base64: base64Audio,
        mime_type: audioBlob.type,
      }),
    });

    if (!response.ok) {
      await handleApiError(response);
    }

    const data = await response.json();

    if (!data.success || !data.analysis) {
      throw new Error("Invalid response from processing service");
    }

    return {
      ...data.analysis,
      spectrogramUrl: data.spectrogramUrl,
      meetingId: data.meetingId,
    };
  } catch (error) {
    console.error("Real-time complete processing error:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to process real-time audio. Please try again.");
  }
};

// ============================================================================
// POLLING UTILITY FOR REAL-TIME UPDATES
// ============================================================================

/**
 * Poll for new real-time updates
 * Returns a cleanup function to stop polling
 */
export const pollRealtimeUpdates = (
  meetingId: string,
  onUpdate: (updates: any[]) => void,
  intervalMs: number = 2000,
): (() => void) => {
  let lastSequence = -1;
  let isPolling = true;

  const poll = async () => {
    if (!isPolling) return;

    try {
      const updates = await getRealtimeUpdates(meetingId, lastSequence);

      if (updates && updates.length > 0) {
        onUpdate(updates);
        lastSequence = Math.max(...updates.map((u: any) => u.sequence_number));
      }
    } catch (error) {
      console.error("Polling error:", error);
    }

    if (isPolling) {
      setTimeout(poll, intervalMs);
    }
  };

  // Start polling
  poll();

  // Return cleanup function
  return () => {
    isPolling = false;
  };
};
// ============================================================================
// REAL-TIME STREAMING TRANSCRIPTION (NEW)
// ============================================================================

/**
 * Connect to streaming transcription endpoint (for HOST)
 * This establishes a WebSocket connection to stream audio and receive live transcriptions
 *
 * @param meetingId - The collaborative meeting ID
 * @param onTranscription - Callback when transcription is received
 * @returns WebSocket instance
 */
export const connectStreamingTranscription = (
  meetingId: string,
  onTranscription: (text: string, isFinal: boolean, source?: string) => void,
): WebSocket => {
  const wsUrl = `ws://localhost:8000/ws/meetings/${meetingId}/stream`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("✅ Connected to streaming transcription endpoint");
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);

      if (message.type === "stream_ready") {
        console.log("🎙️ Stream ready - you can start speaking");
      } else if (message.type === "transcription_echo") {
        // Host receives their own transcription
        const { text, is_final, source } = message.data;
        if (text && text.trim()) {
          onTranscription(text, is_final, source);
        }
      } else if (message.type === "stream_stopped") {
        console.log("🛑 Stream stopped successfully");
      } else if (message.type === "error") {
        console.error("❌ Stream error:", message.message);
      }
    } catch (error) {
      console.error("Error parsing streaming message:", error);
    }
  };

  ws.onerror = (error) => {
    console.error("❌ Streaming WebSocket error:", error);
  };

  ws.onclose = () => {
    console.log("🔌 Streaming WebSocket closed");
  };

  return ws;
};

/**
 * Send audio chunk through streaming WebSocket
 * @param ws - The WebSocket connection
 * @param audioChunk - PCM16 audio data (ArrayBuffer or Int16Array)
 */
export const sendAudioChunk = (
  ws: WebSocket,
  audioChunk: ArrayBuffer | Int16Array,
): void => {
  if (ws.readyState === WebSocket.OPEN) {
    // Convert to ArrayBuffer if it's Int16Array
    const buffer =
      audioChunk instanceof Int16Array ? audioChunk.buffer : audioChunk;

    ws.send(buffer);
  } else {
    console.warn("WebSocket not open, cannot send audio chunk");
  }
};

/**
 * Send control message through streaming WebSocket
 * @param ws - The WebSocket connection
 * @param message - Control message object
 */
export const sendStreamingMessage = (ws: WebSocket, message: any): void => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  }
};

/**
 * Stop streaming session
 * @param ws - The WebSocket connection to close
 */
export const stopStreaming = (ws: WebSocket): void => {
  if (ws.readyState === WebSocket.OPEN) {
    // Send stop signal
    ws.send(JSON.stringify({ type: "stop" }));

    // Wait a bit for graceful close, then force close
    setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    }, 500);
  }
};

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  // Recording
  startRecording,
  stopRecording,

  // Processing
  transcribeAudio,
  analyzeTranscript,
  processRealtimeComplete,

  // Context & Translation
  queryMeetingContext,
  translateContent,

  // Meetings (Database-backed)
  getUserMeetings,
  getMeetingById,
  deleteMeeting,

  // Auth
  signup,
  login,
  logout,
  isAuthenticated,
  getCurrentUser,

  // Health
  checkBackendHealth,

  // Collaboration
  createCollaborativeMeeting,
  searchUsers,
  inviteUserToMeeting,
  inviteMultipleUsers,
  getMyInvitations,
  respondToInvitation,
  getMeetingParticipants,
  removeParticipant,
  startMeeting,
  endMeeting,
  getLiveMeetings,
  getCollaborativeMeetings,
  addRealtimeUpdate,
  getRealtimeUpdates,
  processRealtimeCompleteWithCollaboration,
  pollRealtimeUpdates,

  // Streaming Transcription (NEW)
  connectStreamingTranscription,
  sendAudioChunk,
  sendStreamingMessage,
  stopStreaming,
};
