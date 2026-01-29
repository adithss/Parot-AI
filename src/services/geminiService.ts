// API Base URL - update this to match your backend
const API_BASE_URL = "http://localhost:8000";

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

export const transcribeAudio = async (
  base64Audio: string,
  mimeType: string,
): Promise<string> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        audio_base64: base64Audio,
        mime_type: mimeType,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Transcription failed: ${response.statusText}`,
      );
    }

    const data = await response.json();

    if (!data.success || !data.transcript) {
      throw new Error("Invalid response from transcription service");
    }

    return data.transcript;
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
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        transcript: transcript,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Analysis failed: ${response.statusText}`,
      );
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
    // Prepare the context payload with meeting information
    const contextPayload = {
      transcript: formatTranscriptForContext(meetingResult.diarizedTranscript),
      summary: meetingResult.summary,
      sentiment: meetingResult.sentiment,
      emotionAnalysis: meetingResult.emotionAnalysis,
      actionItems: meetingResult.actionItems,
      keyDecisions: meetingResult.keyDecisions,
      question: question,
    };

    const response = await fetch(`${API_BASE_URL}/api/query-context`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(contextPayload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Query failed: ${response.statusText}`,
      );
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

/**
 * Translate content to a target language
 * This function is commented out in MeetingAnalysis.tsx but included here for completeness
 */
export const translateContent = async (
  result: any,
  targetLanguage: string,
): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/translate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        content: result,
        target_language: targetLanguage,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Translation failed: ${response.statusText}`,
      );
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
