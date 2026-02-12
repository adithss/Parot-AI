import React, { useState, useEffect, useRef } from "react";
import {
  MeetingState,
  AnalysisResult,
  AnalysisResultWithMeta,
  SpeakerSegment,
} from "./types";
import {
  analyzeTranscript,
  transcribeAudio,
  processRealtimeComplete,
  logout,
  isAuthenticated,
  getUserMeetings,
  getMeetingById, // ← NEW
  deleteMeeting,
} from "./services/geminiService";
import {
  MicIcon,
  StopCircleIcon,
  FileUpIcon,
  LoaderIcon,
  HistoryIcon,
  Trash2Icon,
  LogOutIcon,
  ParotLogo,
} from "./components/icons";
import {
  Copy,
  Download,
  Trash2,
  Zap,
  Wifi,
  WifiOff,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  MicOff,
} from "lucide-react";
// import apiService from "./services/apiService";
import MeetingAnalysis from "./components/MeetingAnalysis";
import LandingPage from "./components/LandingPage";
import SignupPage from "./components/SignupPage";
import LoginPage from "./components/LoginPage";
import Spectrogram from "./components/Spectrogram";

type AppView = "landing" | "signup" | "login" | "dashboard" | "realtime";

const COLAB_URL = "https://unnarrowly-unrevered-griffin.ngrok-free.dev";

// Constants for real-time recording
const SAMPLE_RATE = 16000;
const FRAME_DURATION_MS = 100;
const FRAME_SIZE = Math.floor((SAMPLE_RATE * FRAME_DURATION_MS) / 1000);

interface TranscriptSegment {
  text: string;
  timestamp: number;
  type: "tiny" | "medium" | "large";
  id: string;
}

interface MeetingFromDB {
  id: string;
  title: string;
  created_at: string;
  user_id: string;
  audio_file_path?: string;
  spectrogram_url?: string;
  duration?: number;
  status: string;
}
const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>("landing");
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [meetingState, setMeetingState] = useState<MeetingState>(
    MeetingState.IDLE,
  );
  const [error, setError] = useState<string | null>(null);

  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisResult | null>(
    null,
  );
  const [activeAudioFile, setActiveAudioFile] = useState<File | Blob | null>(
    null,
  );
  const [meetingHistory, setMeetingHistory] = useState<MeetingFromDB[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [currentMeetingId, setCurrentMeetingId] = useState<string | null>(null);

  // Real-time recording states
  const [deepgramText, setDeepgramText] = useState("");
  const [mediumTranscript, setMediumTranscript] = useState("");
  const [largeText, setLargeText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isProcessingLarge, setIsProcessingLarge] = useState(false);
  const [realtimeError, setRealtimeError] = useState("");
  const [success, setSuccess] = useState("");
  const [backendStatus, setBackendStatus] = useState<
    "checking" | "connected" | "disconnected"
  >("checking");
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [stats, setStats] = useState({
    tiny: 0,
    medium: 0,
    large: 0,
  });

  // Refs for real-time recording
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const durationIntervalRef = useRef<number | null>(null);
  const sessionStartTimeRef = useRef<number>(0);
  const cumulativeMediumRef = useRef<string>("");
  const recordedAudioChunksRef = useRef<Blob[]>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  useEffect(() => {
    const token = localStorage.getItem("parotAuthToken");
    if (token) {
      setIsAuthenticated(true);
      setCurrentView("dashboard");
    }
  }, []);
  useEffect(() => {
    checkBackendHealth();
    const healthInterval = setInterval(checkBackendHealth, 30000);

    return () => {
      clearInterval(healthInterval);
      cleanup();
    };
  }, []);

  // Separate useEffect for loading meetings
  useEffect(() => {
    const loadMeetingsFromDB = async () => {
      if (!isAuthenticated) return;

      try {
        setIsLoadingHistory(true);
        const meetings = await getUserMeetings();
        setMeetingHistory(meetings);
      } catch (error) {
        console.error("Failed to load meetings:", error);
        setError("Failed to load meeting history");
      } finally {
        setIsLoadingHistory(false);
      }
    };

    if (isAuthenticated && currentView === "dashboard") {
      loadMeetingsFromDB();
    }
  }, [isAuthenticated, currentView]);

  const checkBackendHealth = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${COLAB_URL}/health`, {
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        setBackendStatus("connected");
      } else {
        setBackendStatus("disconnected");
      }
    } catch (err) {
      setBackendStatus("disconnected");
    }
  };

  const cleanup = () => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    if (workletNodeRef.current) {
      try {
        workletNodeRef.current.disconnect();
        workletNodeRef.current.port.postMessage({ command: "stop" });
      } catch (e) {}
      workletNodeRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      try {
        audioContextRef.current.close();
      } catch (e) {}
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {}
    }
  };

  const closeWebSocket = () => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {}
      wsRef.current = null;
    }
  };

  const refreshMeetingHistory = async () => {
    if (!isAuthenticated) return;

    try {
      const meetings = await getUserMeetings();
      setMeetingHistory(meetings);
    } catch (error) {
      console.error("Failed to refresh meeting history:", error);
    }
  };

  const deleteFromHistory = async (idToDelete: string) => {
    try {
      await deleteMeeting(idToDelete);
      // Refresh the list after deletion
      await refreshMeetingHistory();

      // If the deleted meeting was currently open, close it
      if (activeAnalysis && idToDelete === currentMeetingId) {
        handleCloseAnalysis();
      }
    } catch (error) {
      console.error("Failed to delete meeting:", error);
      setError("Failed to delete meeting");
    }
  };

  const handleSelectHistory = async (meetingId: string) => {
    try {
      setMeetingState(MeetingState.PROCESSING);
      setError(null);
      setCurrentMeetingId(meetingId);
      // Fetch complete meeting data from database
      const meetingData = await getMeetingById(meetingId);

      // Convert database format to AnalysisResult format
      const analysis: AnalysisResult = {
        summary: meetingData.summary?.summary_text || "No summary available",
        sentiment: {
          overall:
            meetingData.sentiment_analysis?.overall_sentiment || "Neutral",
          highlights: meetingData.sentiment_analysis?.highlights || [],
        },
        emotionAnalysis: meetingData.sentiment_analysis?.emotion_analysis || [],
        actionItems:
          meetingData.action_items?.map((item: any) => item.description) || [],
        keyDecisions:
          meetingData.key_decisions?.map((kd: any) => kd.decision) || [],
        diarizedTranscript:
          meetingData.transcripts?.map((t: any) => ({
            speaker: t.speaker?.speaker_label || "Unknown",
            text: t.text,
          })) || [],
        spectrogramUrl: meetingData.spectrogram_url,
      };

      setActiveAnalysis(analysis);
      setMeetingState(MeetingState.ANALYSIS_READY);
    } catch (error) {
      console.error("Failed to load meeting:", error);
      setError("Failed to load meeting details");
      setMeetingState(MeetingState.ERROR);
    }
  };

  const handleCloseAnalysis = () => {
    setActiveAnalysis(null);
    setActiveAudioFile(null);
    setCurrentMeetingId(null); // ← ADD THIS LINE

    setMeetingState(MeetingState.IDLE);
    setError(null);
  };

  const handleLogout = () => {
    logout();
    setIsAuthenticated(false);
    setCurrentView("landing");
  };

  // Helper function to parse transcript into segments
  const parseTranscriptToSegments = (
    transcript: string | SpeakerSegment[],
  ): SpeakerSegment[] => {
    // ✅ If backend already sent diarized array
    if (Array.isArray(transcript)) {
      return transcript;
    }

    // ✅ If transcript is string → parse speakers
    const segments: SpeakerSegment[] = [];
    const lines = transcript.split("\n\n");

    lines.forEach((line) => {
      const match = line.match(/^(.+?):\s*(.+)$/s);
      if (match) {
        segments.push({
          speaker: match[1].trim(),
          text: match[2].trim(),
        });
      }
    });

    // ✅ Fallback if no speakers found
    return segments.length > 0
      ? segments
      : [{ speaker: "Unknown", text: transcript }];
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (!event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];

    // Store file so MeetingAnalysis can show spectrogram
    setActiveAudioFile(file);

    setMeetingState(MeetingState.PROCESSING);
    setError(null);

    try {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onloadend = async () => {
        try {
          const base64String = (reader.result as string).split(",")[1];
          const mimeType = file.type;

          const transcriptionData = await transcribeAudio(
            base64String,
            mimeType,
          );
          const transcript = transcriptionData.transcript;

          const analysisResult = await analyzeTranscript(transcript);

          const parsedTranscript = parseTranscriptToSegments(
            analysisResult.diarizedTranscript || transcript || "",
          );

          const finalResult: AnalysisResult = {
            summary: analysisResult.summary || "No summary available.",
            sentiment: analysisResult.sentiment || {
              overall: "Neutral",
              highlights: [],
            },
            emotionAnalysis: analysisResult.emotionAnalysis || [],
            actionItems: analysisResult.actionItems || [],
            keyDecisions: analysisResult.keyDecisions || [],
            diarizedTranscript: parsedTranscript,
            spectrogramUrl: transcriptionData.spectrogramUrl,
          };

          setActiveAnalysis(finalResult);
          // Meeting is already saved to DB by backend - just refresh the list
          await refreshMeetingHistory();
          setMeetingState(MeetingState.ANALYSIS_READY);
        } catch (err) {
          console.error("Processing error:", err);
          setError(
            err instanceof Error
              ? err.message
              : "An unexpected error occurred during processing.",
          );
          setMeetingState(MeetingState.ERROR);
        }
      };

      reader.onerror = () => {
        setError("Failed to read the audio file.");
        setMeetingState(MeetingState.ERROR);
      };
    } catch (err) {
      console.error("Upload error:", err);
      setError(
        err instanceof Error ? err.message : "Failed to upload the audio file.",
      );
      setMeetingState(MeetingState.ERROR);
    }
  };

  const handleStartRealtimeMeeting = () => {
    setCurrentView("realtime");
    setDeepgramText("");
    setMediumTranscript("");
    setLargeText("");
    setRealtimeError("");
    setSuccess("");
    setRecordingDuration(0);
    setStats({ tiny: 0, medium: 0, large: 0 });
    cumulativeMediumRef.current = "";
    recordedAudioChunksRef.current = [];
  };

  const handleBackFromRealtime = () => {
    if (isListening) {
      stopListening();
    }
    setCurrentView("dashboard");
  };

  // const startListening = async () => {
  //   try {
  //     setRealtimeError("");
  //     setSuccess("");

  //     // Initialize MediaRecorder for saving audio
  //     const stream = await navigator.mediaDevices.getUserMedia({
  //       audio: {
  //         channelCount: 1,
  //         sampleRate: 16000,
  //         echoCancellation: true,
  //         noiseSuppression: true,
  //         autoGainControl: true,
  //       },
  //     });
  //     streamRef.current = stream;

  //     // recordedAudioChunksRef.current = [];
  //     // const mediaRecorder = new MediaRecorder(stream);
  //     // mediaRecorderRef.current = mediaRecorder;

  //     // mediaRecorder.ondataavailable = (event) => {
  //     //   if (event.data.size > 0) {
  //     //     recordedAudioChunksRef.current.push(event.data);
  //     //   }
  //     // };

  //     // mediaRecorder.start(100); // Collect data every 100ms

  //     // Initialize WebSocket for real-time transcription
  //     const ws = new WebSocket(
  //       `${COLAB_URL.replace("https://", "wss://").replace("http://", "ws://")}/api/stream`,
  //     );
  //     wsRef.current = ws;

  //     ws.onopen = async () => {
  //       console.log("WebSocket connected");
  //       setIsListening(true);
  //       sessionStartTimeRef.current = Date.now();

  //       durationIntervalRef.current = window.setInterval(() => {
  //         setRecordingDuration(
  //           Math.floor((Date.now() - sessionStartTimeRef.current) / 1000),
  //         );
  //       }, 1000);

  //       const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
  //       audioContextRef.current = audioContext;

  //       await audioContext.audioWorklet.addModule("/audio-processor.js");

  //       const source = audioContext.createMediaStreamSource(stream);
  //       const workletNode = new AudioWorkletNode(
  //         audioContext,
  //         "audio-processor",
  //       );
  //       workletNodeRef.current = workletNode;

  //       workletNode.port.onmessage = (event) => {
  //         const { audioData, isSpeaking: speaking } = event.data;
  //         setIsSpeaking(speaking);

  //         if (
  //           audioData &&
  //           ws.readyState === WebSocket.OPEN &&
  //           audioData.byteLength > 0
  //         ) {
  //           console.log("Audio frame size:", audioData.byteLength); // debug

  //           const int16Array = new Int16Array(audioData);
  //           ws.send(int16Array.buffer);
  //         }
  //       };

  //       source.connect(workletNode);
  //       workletNode.connect(audioContext.destination);
  //     };

  //     ws.onmessage = (event) => {
  //       try {
  //         const data = JSON.parse(event.data);

  //         if (data.type === "deepgram_transcript") {
  //           setDeepgramText(data.text);
  //           setStats((prev) => ({ ...prev, tiny: prev.tiny + 1 }));
  //         } else if (data.type === "medium_delta") {
  //           const newCumulative = data.text;
  //           cumulativeMediumRef.current = newCumulative;
  //           setMediumTranscript(newCumulative);
  //           setStats((prev) => ({ ...prev, medium: prev.medium + 1 }));
  //         } else if (data.type === "large_result") {
  //           setLargeText(data.text);
  //           setIsProcessingLarge(false);
  //           setStats((prev) => ({ ...prev, large: prev.large + 1 }));

  //           // Process for analysis when large model finishes
  //         } else if (data.type === "error") {
  //           setRealtimeError(data.message || "Transcription error");
  //         }
  //       } catch (e) {
  //         console.error("Error parsing WebSocket message:", e);
  //       }
  //     };

  //     ws.onerror = (error) => {
  //       console.error("WebSocket error:", error);
  //       setRealtimeError("Connection error. Please check backend.");
  //       stopListening();
  //     };

  //     ws.onclose = () => {
  //       console.log("WebSocket closed");
  //     };
  //   } catch (err) {
  //     console.error("Error starting recording:", err);
  //     setRealtimeError(
  //       "Failed to access microphone. Please check permissions.",
  //     );
  //     setIsListening(false);
  //   }
  // };
  // COMPLETE FIX FOR YOUR INTEGRATED APP.TSX
  // Replace your entire startListening() function with this one

  const startListening = async () => {
    try {
      setRealtimeError("");
      setSuccess("");

      // Initialize MediaRecorder for saving audio
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      // Initialize MediaRecorder to save audio for later processing
      recordedAudioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedAudioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(100); // Collect data every 100ms
      // Initialize WebSocket for real-time transcription
      const ws = new WebSocket(
        `${COLAB_URL.replace("https://", "wss://").replace("http://", "ws://")}/api/stream`,
      );
      wsRef.current = ws;

      ws.onopen = async () => {
        console.log("WebSocket connected");
        setIsListening(true);
        sessionStartTimeRef.current = Date.now();

        durationIntervalRef.current = window.setInterval(() => {
          setRecordingDuration(
            Math.floor((Date.now() - sessionStartTimeRef.current) / 1000),
          );
        }, 1000);

        const audioContext = new AudioContext({ sampleRate: 16000 });
        audioContextRef.current = audioContext;

        // ============ FIX: Create AudioWorklet code inline ============
        const workletCode = `
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 1600; // 100ms at 16kHz
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
    this.silenceThreshold = 0.01;
    this.isActive = true;

    this.port.onmessage = (e) => {
      if (e.data.command === 'stop') {
        this.isActive = false;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0] || !this.isActive) return this.isActive;

    const inputData = input[0];
    let maxAmplitude = 0;

    for (let i = 0; i < inputData.length; i++) {
      this.buffer[this.bufferIndex++] = inputData[i];
      maxAmplitude = Math.max(maxAmplitude, Math.abs(inputData[i]));

      if (this.bufferIndex >= this.bufferSize) {
        // Convert to PCM16
        const pcm16 = new Int16Array(this.bufferSize);
        for (let j = 0; j < this.bufferSize; j++) {
          const s = Math.max(-1, Math.min(1, this.buffer[j]));
          pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        const isSpeaking = maxAmplitude > this.silenceThreshold;

        this.port.postMessage({
          audioData: pcm16.buffer,
          isSpeaking: isSpeaking
        }, [pcm16.buffer]);

        this.bufferIndex = 0;
        this.buffer = new Float32Array(this.bufferSize);
        maxAmplitude = 0;
      }
    }

    return this.isActive;
  }
}

registerProcessor('audio-processor', AudioProcessor);
`;

        const blob = new Blob([workletCode], {
          type: "application/javascript",
        });
        const workletUrl = URL.createObjectURL(blob);

        await audioContext.audioWorklet.addModule(workletUrl);
        URL.revokeObjectURL(workletUrl);
        // ============ END FIX ============

        const source = audioContext.createMediaStreamSource(stream);
        const workletNode = new AudioWorkletNode(
          audioContext,
          "audio-processor",
        );
        workletNodeRef.current = workletNode;

        workletNode.port.onmessage = (event) => {
          const { audioData, isSpeaking: speaking } = event.data;
          setIsSpeaking(speaking);

          if (
            audioData &&
            ws.readyState === WebSocket.OPEN &&
            audioData.byteLength > 0
          ) {
            // Send as ArrayBuffer (PCM16 format)
            ws.send(audioData);
          }
        };

        source.connect(workletNode);
        workletNode.connect(audioContext.destination);
      };

      // ============ FIX: Change "tiny_result" to "deepgram_transcript" ============
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "deepgram_transcript") {
            // ALWAYS update Deepgram text (don't let Medium block it)
            setDeepgramText(data.text);
            setStats((prev) => ({ ...prev, tiny: prev.tiny + 1 }));
          } else if (data.type === "medium_delta") {
            const newDelta = data.text.trim();
            if (newDelta) {
              const newCumulative = cumulativeMediumRef.current
                ? `${cumulativeMediumRef.current} ${newDelta}`
                : newDelta;

              cumulativeMediumRef.current = newCumulative;
              setMediumTranscript(newCumulative);
              setStats((prev) => ({ ...prev, medium: prev.medium + 1 }));

              // DON'T clear Deepgram here - let it keep showing real-time text
              // setDeepgramText("");  // ← REMOVE THIS LINE
            }
          } else if (data.type === "large_result") {
            setLargeText(data.text);
            setIsProcessingLarge(false);
            setStats((prev) => ({ ...prev, large: prev.large + 1 }));

            setMediumTranscript("");
            setDeepgramText("");
            cumulativeMediumRef.current = "";

            if (wsRef.current && (wsRef.current as any).__fallbackTimeout) {
              clearTimeout((wsRef.current as any).__fallbackTimeout);
            }

            setTimeout(() => {
              closeWebSocket();
            }, 500);

            if (recordedAudioChunksRef.current.length > 0) {
              try {
                setMeetingState(MeetingState.PROCESSING);

                const audioBlob = new Blob(recordedAudioChunksRef.current, {
                  type: "audio/wav",
                });

                processRealtimeComplete(audioBlob)
                  .then(async (analysisResult) => {
                    console.log(
                      "✅ Analysis complete, navigating to results...",
                    );
                    setActiveAnalysis(analysisResult);
                    setActiveAudioFile(audioBlob);

                    // Refresh meeting history from database
                    await refreshMeetingHistory();

                    // Navigate to dashboard view and show analysis
                    setCurrentView("dashboard");
                    setMeetingState(MeetingState.ANALYSIS_READY);
                    setSuccess("Meeting analysis complete!");
                    recordedAudioChunksRef.current = [];
                  })
                  .catch((err) => {
                    console.error("Error processing complete analysis:", err);
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Failed to process meeting analysis",
                    );
                    setCurrentView("dashboard");
                    setMeetingState(MeetingState.ERROR);
                  });
              } catch (err) {
                console.error("Error creating audio blob:", err);
                setError("Failed to prepare audio for analysis");
                setMeetingState(MeetingState.ERROR);
              }
            }
          } else if (data.type === "error") {
            setRealtimeError(data.message || "Transcription error");
          } else if (data.type === "pong") {
            // Keep-alive
          }
        } catch (e) {
          console.error("Error parsing WebSocket message:", e);
        }
      };
      // ============ END FIX ============

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        if (isListening) {
          setRealtimeError("Connection error. Please check backend.");
          stopListening();
        }
      };

      ws.onclose = (event) => {
        console.log("WebSocket closed:", event.code, event.reason);

        // If closed while recording → error
        if (isListening && !isProcessingLarge) {
          setRealtimeError("Connection lost during recording.");
          stopListening();
        }
      };
    } catch (err) {
      console.error("Error starting recording:", err);
      setRealtimeError(
        "Failed to access microphone. Please check permissions.",
      );
      setIsListening(false);
    }
  };
  const stopListening = async () => {
    setIsListening(false);
    setIsProcessingLarge(true);

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      } catch (e) {
        console.error("Error sending stop message:", e);
      }
    }

    const fallbackTimeout = setTimeout(() => {
      closeWebSocket();
    }, 20000);

    (wsRef.current as any).__fallbackTimeout = fallbackTimeout;

    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }

    if (workletNodeRef.current) {
      try {
        workletNodeRef.current.disconnect();
        workletNodeRef.current.port.postMessage({ command: "stop" });
      } catch (e) {}
      workletNodeRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      try {
        await audioContextRef.current.close();
      } catch (e) {}
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };
  // const processRecordedAudio = async () => {
  //   try {
  //     // Use the large text that was already transcribed in real-time
  //     const finalTranscript = largeText || mediumTranscript || deepgramText;

  //     if (!finalTranscript || finalTranscript.trim().length === 0) {
  //       setRealtimeError("No transcript available for analysis");
  //       setIsProcessingLarge(false);
  //       return;
  //     }

  //     // Show processing state
  //     setCurrentView("dashboard");
  //     setMeetingState(MeetingState.PROCESSING);
  //     setError(null);

  //     // Analyze the transcript that was already generated
  //     const analysisResult = await analyzeTranscript(finalTranscript);

  //     // Parse diarized transcript
  //     const parsedTranscript = parseTranscriptToSegments(
  //       analysisResult.diarizedTranscript || finalTranscript || "",
  //     );

  //     // Create final result
  //     const finalResult: AnalysisResult = {
  //       summary: analysisResult.summary || "No summary available.",
  //       sentiment: analysisResult.sentiment || {
  //         overall: "Neutral",
  //         highlights: [],
  //       },
  //       emotionAnalysis: analysisResult.emotionAnalysis || [],
  //       actionItems: analysisResult.actionItems || [],
  //       keyDecisions: analysisResult.keyDecisions || [],
  //       diarizedTranscript: parsedTranscript,
  //     };

  //     // Set active analysis and save to history
  //     setActiveAnalysis(finalResult);
  //     // Meeting is already saved to DB by backend - just refresh
  //     await refreshMeetingHistory();
  //     setMeetingState(MeetingState.ANALYSIS_READY);
  //     setIsProcessingLarge(false);
  //   } catch (err) {
  //     console.error("Processing error:", err);
  //     setError(
  //       err instanceof Error
  //         ? err.message
  //         : "An unexpected error occurred during processing.",
  //     );
  //     setMeetingState(MeetingState.ERROR);
  //     setIsProcessingLarge(false);
  //   }
  // };

  // const processRecordedAudio = async () => {
  //   try {
  //     if (recordedAudioChunksRef.current.length === 0) {
  //       setRealtimeError("No audio data recorded");
  //       setIsProcessingLarge(false);
  //       return;
  //     }

  //     // Create blob from recorded chunks
  //     const audioBlob = new Blob(recordedAudioChunksRef.current, {
  //       type: mediaRecorderRef.current?.mimeType || "audio/webm",
  //     });

  //     // Convert to base64
  //     const reader = new FileReader();
  //     reader.readAsDataURL(audioBlob);

  //     reader.onloadend = async () => {
  //       try {
  //         const base64String = (reader.result as string).split(",")[1];
  //         const mimeType = audioBlob.type;

  //         // Show processing state
  //         setCurrentView("dashboard");
  //         setMeetingState(MeetingState.PROCESSING);
  //         setError(null);

  //         // Transcribe audio
  //         const transcript = await transcribeAudio(base64String, mimeType);

  //         // Analyze transcript
  //         const analysisResult = await analyzeTranscript(transcript);

  //         // Parse diarized transcript
  //         const parsedTranscript = parseTranscriptToSegments(
  //           analysisResult.diarizedTranscript || transcript,
  //         );

  //         // Create final result
  //         const finalResult: AnalysisResult = {
  //           summary: analysisResult.summary || "No summary available.",
  //           sentiment: analysisResult.sentiment || {
  //             overall: "Neutral",
  //             highlights: [],
  //           },
  //           emotionAnalysis: analysisResult.emotionAnalysis || [],
  //           actionItems: analysisResult.actionItems || [],
  //           keyDecisions: analysisResult.keyDecisions || [],
  //           diarizedTranscript: parsedTranscript,
  //         };

  //         // Set active analysis and save to history
  //         setActiveAnalysis(finalResult);
  //         saveMeetingToHistory(finalResult);
  //         setMeetingState(MeetingState.ANALYSIS_READY);
  //         setIsProcessingLarge(false);
  //       } catch (err) {
  //         console.error("Processing error:", err);
  //         setError(
  //           err instanceof Error
  //             ? err.message
  //             : "An unexpected error occurred during processing.",
  //         );
  //         setMeetingState(MeetingState.ERROR);
  //         setIsProcessingLarge(false);
  //       }
  //     };

  //     reader.onerror = () => {
  //       setError("Failed to process the recorded audio.");
  //       setMeetingState(MeetingState.ERROR);
  //       setIsProcessingLarge(false);
  //     };
  //   } catch (err) {
  //     console.error("Recording processing error:", err);
  //     setError(
  //       err instanceof Error ? err.message : "Failed to process the recording.",
  //     );
  //     setMeetingState(MeetingState.ERROR);
  //     setIsProcessingLarge(false);
  //   }
  // };

  const copyToClipboard = () => {
    const textToCopy = largeText || mediumTranscript || deepgramText;
    navigator.clipboard.writeText(textToCopy);
    setSuccess("Copied to clipboard!");
    setTimeout(() => setSuccess(""), 3000);
  };

  const downloadTranscript = () => {
    const textToDownload = largeText || mediumTranscript || deepgramText;
    const blob = new Blob([textToDownload], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript_${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setSuccess("Transcript downloaded!");
    setTimeout(() => setSuccess(""), 3000);
  };

  const clearTranscript = () => {
    setDeepgramText("");
    setMediumTranscript("");
    setLargeText("");
    cumulativeMediumRef.current = "";
    setStats({ tiny: 0, medium: 0, large: 0 });
    setSuccess("Transcript cleared!");
    setTimeout(() => setSuccess(""), 3000);
  };

  const formatDuration = (seconds: number): string => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const renderRealtimePage = () => {
    const hasTranscript = !!(deepgramText || mediumTranscript || largeText);

    return (
      <div className="min-h-screen bg-gray-900 text-white flex flex-col">
        <header className="bg-gray-800 border-b border-gray-700 p-4">
          <div className="container mx-auto flex items-center justify-between">
            <button
              onClick={handleBackFromRealtime}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
              <span>Back to Dashboard</span>
            </button>

            <div className="flex items-center gap-3">
              <ParotLogo className="w-8 h-8" />
              <span className="text-xl font-bold">parot</span>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                {backendStatus === "connected" ? (
                  <>
                    <Wifi size={18} className="text-green-400" />
                    <span className="text-green-400">Connected</span>
                  </>
                ) : backendStatus === "disconnected" ? (
                  <>
                    <WifiOff size={18} className="text-red-400" />
                    <span className="text-red-400">Disconnected</span>
                  </>
                ) : (
                  <>
                    <LoaderIcon className="w-4 h-4 animate-spin text-yellow-400" />
                    <span className="text-yellow-400">Checking...</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        <div className="flex-1 container mx-auto p-4 flex flex-col">
          <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full">
            {(realtimeError || success) && (
              <div className="mb-4">
                {realtimeError && (
                  <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg flex items-center gap-2">
                    <AlertCircle size={20} />
                    <span>{realtimeError}</span>
                  </div>
                )}
                {success && (
                  <div className="bg-green-900/50 border border-green-700 text-green-200 px-4 py-3 rounded-lg flex items-center gap-2">
                    <CheckCircle2 size={20} />
                    <span>{success}</span>
                  </div>
                )}
              </div>
            )}

            <div className="bg-gray-800 rounded-lg p-6 mb-4 flex flex-col items-center">
              <div className="mb-6 text-center">
                <div className="text-5xl font-mono font-bold text-cyan-400 mb-2">
                  {formatDuration(recordingDuration)}
                </div>
                <div className="text-sm text-gray-400">
                  {isListening ? "Recording..." : "Ready to record"}
                </div>
              </div>

              <div className="flex gap-4 mb-6">
                <button
                  onClick={isListening ? stopListening : startListening}
                  disabled={isProcessingLarge}
                  className={`flex items-center justify-center gap-3 px-8 py-4 rounded-full font-bold text-lg transition-all shadow-lg ${
                    isListening
                      ? "bg-red-600 hover:bg-red-700"
                      : "bg-cyan-600 hover:bg-cyan-700"
                  } ${isProcessingLarge ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {isProcessingLarge ? (
                    <>
                      <LoaderIcon className="w-6 h-6 animate-spin" />
                      Processing...
                    </>
                  ) : isListening ? (
                    <>
                      <StopCircleIcon className="w-6 h-6" />
                      Stop Recording
                    </>
                  ) : (
                    <>
                      <MicIcon className="w-6 h-6" />
                      Start Recording
                    </>
                  )}
                </button>
              </div>

              {isListening && (
                <div className="flex items-center gap-3 text-sm">
                  <div
                    className={`w-3 h-3 rounded-full ${isSpeaking ? "bg-green-400 animate-pulse" : "bg-gray-600"}`}
                  />
                  <span className="text-gray-400">
                    {isSpeaking ? "Detecting speech..." : "Listening..."}
                  </span>
                </div>
              )}

              {/* ── Live Spectrogram ─────────────────────────────────── */}
              <div className="w-full mt-5">
                <Spectrogram
                  stream={streamRef.current}
                  isRecording={isListening}
                  label="Live Spectrogram"
                  colorScheme="cyan"
                  height={140}
                  fftSize={2048}
                />
              </div>

              <div className="flex gap-6 text-xs text-gray-500 mt-4">
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-cyan-400" />
                  <span>Tiny: {stats.tiny}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-blue-400" />
                  <span>Medium: {stats.medium}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-purple-400" />
                  <span>Large: {stats.large}</span>
                </div>
              </div>
            </div>

            <div className="flex-1 bg-gray-800 rounded-lg p-6 overflow-y-auto">
              {hasTranscript ? (
                <div className="space-y-4">
                  <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {isProcessingLarge && (
                      <span className="inline-flex items-center gap-2 text-purple-400 mb-2">
                        <LoaderIcon className="w-4 h-4 animate-spin" />
                        Final polish in progress...
                      </span>
                    )}
                    {largeText ? (
                      <>
                        <span className="text-purple-400 font-semibold">
                          [Final - Large Model]
                        </span>
                        <br />
                        {largeText}
                      </>
                    ) : (
                      <>
                        {/* Show Medium (refined) first */}
                        {mediumTranscript && (
                          <>
                            <span className="text-blue-400 font-semibold">
                              [Refined]
                            </span>{" "}
                            <span className="text-blue-400 font-medium">
                              {mediumTranscript}
                            </span>
                          </>
                        )}

                        {/* Show Deepgram (real-time) after Medium */}
                        {deepgramText && (
                          <>
                            {mediumTranscript && " "}
                            <span className="text-cyan-400 font-semibold">
                              {mediumTranscript
                                ? "[Live]"
                                : "[Live - Deepgram]"}
                            </span>{" "}
                            <span className="text-cyan-400 italic">
                              {deepgramText}
                            </span>
                            {isListening && (
                              <span className="inline-block w-2 h-4 bg-cyan-400 ml-1 animate-pulse" />
                            )}
                          </>
                        )}

                        {/* Fallback if nothing is showing */}
                        {!mediumTranscript && !deepgramText && isListening && (
                          <span className="text-gray-500">Listening...</span>
                        )}
                      </>
                    )}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500 text-center py-8">
                  <MicIcon className="mb-2 w-12 h-12" />
                  <p>Your transcription will appear here in realtime</p>
                  <p className="text-sm mt-2">
                    Ultra-fast: Deepgram • Refined: Medium • Final: Large
                  </p>
                </div>
              )}
            </div>

            {hasTranscript && (
              <div className="flex gap-2 mb-4">
                <button
                  onClick={copyToClipboard}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors font-medium"
                >
                  <Copy size={18} />
                  Copy
                </button>
                <button
                  onClick={downloadTranscript}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors font-medium"
                >
                  <Download size={18} />
                  Download
                </button>
                <button
                  onClick={clearTranscript}
                  className="flex items-center justify-center gap-2 px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            )}

            <div className="text-center text-sm text-gray-500 space-y-1">
              <p>⚡ Deepgram: Ultra-fast real-time (200-400ms latency)</p>
              <p>🔄 Medium: Whisper cumulative refinements every 5s</p>
              <p>🎯 Large: Whisper final high-quality polish</p>
              {backendStatus === "disconnected" && (
                <p className="text-orange-400 font-medium">
                  ⚠️ Backend offline - check connection
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderContent = () => {
    switch (meetingState) {
      case MeetingState.PROCESSING:
        return (
          <div className="flex flex-col items-center justify-center h-full text-center w-full max-w-md">
            <LoaderIcon className="w-16 h-16 text-cyan-400 animate-spin mb-6" />
            <h2 className="text-2xl font-bold mb-4 text-cyan-300">
              Processing Your Meeting...
            </h2>
            <p className="text-gray-400">
              Transcribing audio, identifying speakers, and analyzing content.
              <br />
              This may take a moment. Please wait.
            </p>
          </div>
        );
      case MeetingState.ANALYSIS_READY:
        return (
          activeAnalysis && (
            <MeetingAnalysis
              result={activeAnalysis}
              onReset={handleCloseAnalysis}
              audioFile={activeAudioFile}
            />
          )
        );
      case MeetingState.ERROR:
        return (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <h2 className="text-2xl font-bold text-red-500 mb-4">
              An Error Occurred
            </h2>
            <p className="text-gray-300 bg-red-900/50 p-4 rounded-lg border border-red-700 max-w-2xl">
              {error}
            </p>
            <button
              onClick={handleCloseAnalysis}
              className="mt-6 px-6 py-2 bg-cyan-600 text-white font-semibold rounded-full hover:bg-cyan-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        );
      case MeetingState.IDLE:
      default:
        return (
          <div className="flex flex-col items-center justify-center h-full w-full text-center">
            <div className="mb-12">
              <ParotLogo className="w-24 h-24 mx-auto mb-4" />
              <h1 className="text-5xl md:text-6xl font-extrabold mb-4 tracking-tight">
                parot
              </h1>
              <p className="text-lg text-gray-400 mb-8 max-w-2xl">
                Capture, understand, and act on your meetings like never before.
                Get transcriptions with speaker identification, summaries, and
                sentiment analysis.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  onClick={handleStartRealtimeMeeting}
                  className="flex items-center justify-center px-8 py-4 bg-cyan-600 text-white font-bold rounded-full hover:bg-cyan-700 transition-transform hover:scale-105 shadow-lg"
                >
                  <MicIcon className="w-6 h-6 mr-2" />
                  Start New Meeting
                </button>
                <label
                  htmlFor="audio-upload"
                  className="flex items-center justify-center px-8 py-4 bg-gray-700 text-white font-bold rounded-full hover:bg-gray-600 transition-transform hover:scale-105 shadow-lg cursor-pointer"
                >
                  <FileUpIcon className="w-6 h-6 mr-2" />
                  Analyze Audio File
                </label>
                <input
                  id="audio-upload"
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </div>
            </div>

            <div className="w-full max-w-4xl pt-8 border-t border-gray-700">
              <h2 className="flex items-center justify-center text-2xl font-bold text-cyan-300 mb-4">
                <HistoryIcon className="w-7 h-7 mr-3" />
                Meeting History
              </h2>
              {isLoadingHistory ? (
                <div className="flex items-center justify-center py-8">
                  <LoaderIcon className="w-8 h-8 animate-spin text-cyan-400" />
                  <span className="ml-3 text-gray-400">
                    Loading meetings...
                  </span>
                </div>
              ) : meetingHistory.length > 0 ? (
                <div className="space-y-3 max-h-60 overflow-y-auto pr-2">
                  {meetingHistory.map((meeting) => (
                    <div
                      key={meeting.id}
                      className="flex items-center justify-between bg-gray-800/50 p-3 rounded-lg border border-gray-700 hover:bg-gray-800 transition-colors"
                    >
                      <button
                        onClick={() => handleSelectHistory(meeting.id)}
                        className="flex-grow text-left"
                      >
                        <p className="font-semibold text-white">
                          {meeting.title}
                        </p>
                        <p className="text-sm text-gray-400">
                          {new Date(meeting.created_at).toLocaleString()}
                        </p>
                        {meeting.status && (
                          <p className="text-xs text-gray-500 mt-1">
                            Status: {meeting.status}
                          </p>
                        )}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteFromHistory(meeting.id);
                        }}
                        className="p-2 text-gray-500 hover:text-red-500 hover:bg-gray-700 rounded-full transition-colors"
                        title="Delete meeting"
                      >
                        <Trash2Icon className="w-5 h-5" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">
                  No past meetings found. Start a new session to see your
                  history here.
                </p>
              )}
            </div>
          </div>
        );
    }
  };

  if (currentView === "landing") {
    return (
      <LandingPage onNavigate={(view) => setCurrentView(view as AppView)} />
    );
  }

  if (currentView === "signup") {
    return (
      <SignupPage
        onSignupSuccess={() => setCurrentView("login")}
        onNavigateToLogin={() => setCurrentView("login")}
      />
    );
  }

  if (currentView === "login") {
    return (
      <LoginPage
        onLoginSuccess={(userData) => {
          setIsAuthenticated(true);
          setCurrentView("dashboard");
        }}
        onNavigateToSignup={() => setCurrentView("signup")}
      />
    );
  }

  if (currentView === "realtime") {
    return renderRealtimePage();
  }

  return (
    <main className="min-h-screen bg-gray-900 text-white p-4 sm:p-8">
      <div className="container mx-auto max-w-7xl">
        <header className="flex items-center justify-between mb-12">
          <div className="flex items-center gap-3">
            <ParotLogo className="w-10 h-10" />
            <span className="text-3xl font-bold tracking-tight text-white">
              parot
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center text-gray-400 hover:text-white transition-colors"
          >
            <LogOutIcon className="w-5 h-5 mr-2" />
            Log Out
          </button>
        </header>
        <div className="bg-gray-800/20 backdrop-blur-sm rounded-2xl shadow-2xl border border-gray-700/50 min-h-[75vh] p-4 sm:p-8 flex items-center justify-center">
          {renderContent()}
        </div>
        <footer className="text-center mt-8 text-gray-500 text-sm"></footer>
      </div>
    </main>
  );
};

export default App;
