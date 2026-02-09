import React, { useState, useEffect } from "react";
import {
  MeetingState,
  AnalysisResult,
  AnalysisResultWithMeta,
  SpeakerSegment,
} from "./types";
import {
  analyzeTranscript,
  startRecording,
  stopRecording,
  transcribeAudio,
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
import MeetingAnalysis from "./components/MeetingAnalysis";
import LandingPage from "./components/LandingPage";
import SignupPage from "./components/SignupPage";
import LoginPage from "./components/LoginPage";

type AppView = "landing" | "signup" | "login" | "dashboard";

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>("dashboard");
  const [meetingState, setMeetingState] = useState<MeetingState>(
    MeetingState.IDLE,
  );
  const [error, setError] = useState<string | null>(null);

  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisResult | null>(
    null,
  );
  const [meetingHistory, setMeetingHistory] = useState<
    AnalysisResultWithMeta[]
  >([]);

  useEffect(() => {
    try {
      const storedHistory = localStorage.getItem("meetingHistory");
      if (storedHistory) {
        setMeetingHistory(JSON.parse(storedHistory));
      }
    } catch (e) {
      console.error("Failed to load meeting history from localStorage", e);
    }
  }, []);

  const saveMeetingToHistory = (result: AnalysisResult) => {
    const newMeeting: AnalysisResultWithMeta = {
      id: Date.now().toString(),
      title: `Meeting - ${new Date().toLocaleString()}`,
      timestamp: new Date().toISOString(),
      result: result,
    };
    setMeetingHistory((prev) => {
      const updatedHistory = [newMeeting, ...prev];
      localStorage.setItem("meetingHistory", JSON.stringify(updatedHistory));
      return updatedHistory;
    });
    return newMeeting;
  };

  const deleteFromHistory = (idToDelete: string) => {
    setMeetingHistory((prev) => {
      const updatedHistory = prev.filter((item) => item.id !== idToDelete);
      localStorage.setItem("meetingHistory", JSON.stringify(updatedHistory));
      return updatedHistory;
    });
  };

  const handleSelectHistory = (analysis: AnalysisResult) => {
    setActiveAnalysis(analysis);
    setMeetingState(MeetingState.ANALYSIS_READY);
  };

  const handleCloseAnalysis = () => {
    setActiveAnalysis(null);
    setMeetingState(MeetingState.IDLE);
    setError(null);
  };

  // Helper function to parse transcript into segments
  const parseTranscriptToSegments = (transcript: string): SpeakerSegment[] => {
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

    return segments.length > 0
      ? segments
      : [{ speaker: "Unknown", text: transcript }];
  };

  const startMeeting = async () => {
    setMeetingState(MeetingState.RECORDING);
    setError(null);

    try {
      await startRecording();
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unknown error occurred.";
      setError(`Failed to start recording: ${errorMessage}`);
      setMeetingState(MeetingState.ERROR);
    }
  };

  const stopMeeting = async () => {
    setMeetingState(MeetingState.PROCESSING);

    try {
      // 1. Get the recorded audio
      const { base64, mimeType } = await stopRecording();

      // 2. Transcribe and diarize the audio
      const transcript = await transcribeAudio(base64, mimeType);

      if (!transcript.trim()) {
        setError(
          "No transcription generated. Please ensure your microphone was working and you spoke clearly.",
        );
        setMeetingState(MeetingState.ERROR);
        return;
      }

      // 3. Analyze the transcript
      const analysisResult = await analyzeTranscript(transcript);

      // Parse the transcript to extract diarized segments
      const diarizedTranscript = parseTranscriptToSegments(transcript);

      // Create the full result object by merging analysis with transcript
      const result: AnalysisResult = {
        summary: analysisResult.summary || "No summary available",
        sentiment: analysisResult.sentiment || {
          overall: "Neutral",
          highlights: [],
        },
        emotionAnalysis: analysisResult.emotionAnalysis || [],
        actionItems: analysisResult.actionItems || [],
        keyDecisions: analysisResult.keyDecisions || [],
        diarizedTranscript:
          analysisResult.diarizedTranscript || diarizedTranscript,
      };

      saveMeetingToHistory(result);
      setActiveAnalysis(result);
      setMeetingState(MeetingState.ANALYSIS_READY);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "An unknown error occurred during processing.";
      setError(`Processing failed: ${errorMessage}`);
      setMeetingState(MeetingState.ERROR);
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    if (!event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];

    setMeetingState(MeetingState.PROCESSING);
    setError(null);

    try {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = async (e) => {
        const resultStr = e.target?.result as string;
        if (!resultStr) return;

        // Safety check to ensure resultStr format is valid before splitting
        if (!resultStr.includes(",")) {
          setError("Invalid file format.");
          setMeetingState(MeetingState.ERROR);
          return;
        }

        const base64Audio = resultStr.split(",")[1];

        // Transcribe and diarize
        const transcript = await transcribeAudio(base64Audio, file.type);

        if (!transcript.trim()) {
          setError(
            "No transcription generated. Please ensure the audio file contains speech.",
          );
          setMeetingState(MeetingState.ERROR);
          return;
        }

        // Analyze
        const analysisResult = await analyzeTranscript(transcript);

        // Parse the transcript to extract diarized segments
        const diarizedTranscript = parseTranscriptToSegments(transcript);

        // Create the full result object
        const result: AnalysisResult = {
          summary: analysisResult.summary || "No summary available",
          sentiment: analysisResult.sentiment || {
            overall: "Neutral",
            highlights: [],
          },
          emotionAnalysis: analysisResult.emotionAnalysis || [],
          actionItems: analysisResult.actionItems || [],
          keyDecisions: analysisResult.keyDecisions || [],
          diarizedTranscript:
            analysisResult.diarizedTranscript || diarizedTranscript,
        };

        saveMeetingToHistory(result);
        setActiveAnalysis(result);
        setMeetingState(MeetingState.ANALYSIS_READY);
      };
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "An unknown error occurred during file processing.";
      setError(`File processing failed: ${errorMessage}`);
      setMeetingState(MeetingState.ERROR);
    }
  };

  const handleLogout = () => {
    setCurrentView("landing");
    handleCloseAnalysis();
  };

  const renderContent = () => {
    switch (meetingState) {
      case MeetingState.RECORDING:
        return (
          <div className="flex flex-col items-center justify-center h-full text-center w-full max-w-5xl">
            <h2 className="text-3xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 animate-pulse">
              Meeting in Progress...
            </h2>

            {/* Recording Indicator UI */}
            <div className="w-full h-[500px] bg-gray-900/90 rounded-2xl p-6 flex flex-col items-center justify-center border border-gray-700 mb-8 shadow-2xl relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent to-cyan-900/20 pointer-events-none"></div>

              {/* Visualizer / Animation */}
              <div className="flex items-center justify-center gap-3 mb-8 h-20">
                {[1, 2, 3, 4, 5, 6, 7].map((i) => (
                  <div
                    key={i}
                    className="w-3 bg-cyan-500 rounded-full animate-pulse"
                    style={{
                      height: `${Math.random() * 40 + 20}px`,
                      animationDuration: `${0.6 + Math.random() * 0.4}s`,
                    }}
                  ></div>
                ))}
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                Recording in Progress
              </h3>
              <p className="text-gray-400 max-w-lg">
                Audio is being recorded securely. <br />
                The full transcript with speaker identification and AI analysis
                will be generated automatically when you end the meeting.
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-red-400 bg-red-900/20 px-4 py-2 rounded-full border border-red-900/50 animate-pulse">
                <div className="w-2 h-2 rounded-full bg-red-500"></div>
                <span className="text-sm font-semibold uppercase tracking-widest">
                  Recording
                </span>
              </div>
              <button
                onClick={stopMeeting}
                className="flex items-center justify-center px-8 py-3 bg-red-600 text-white font-bold text-lg rounded-full hover:bg-red-700 transition-all hover:scale-105 shadow-xl hover:shadow-red-900/30"
              >
                <StopCircleIcon className="w-6 h-6 mr-2" />
                End Meeting
              </button>
            </div>
          </div>
        );
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
                  onClick={startMeeting}
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
              {meetingHistory.length > 0 ? (
                <div className="space-y-3 max-h-60 overflow-y-auto pr-2">
                  {meetingHistory.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between bg-gray-800/50 p-3 rounded-lg border border-gray-700 hover:bg-gray-800 transition-colors"
                    >
                      <button
                        onClick={() => handleSelectHistory(item.result)}
                        className="flex-grow text-left"
                      >
                        <p className="font-semibold text-white">{item.title}</p>
                        <p className="text-sm text-gray-400">
                          {new Date(item.timestamp).toLocaleString()}
                        </p>
                      </button>
                      <button
                        onClick={() => deleteFromHistory(item.id)}
                        className="p-2 text-gray-500 hover:text-red-500 hover:bg-gray-700 rounded-full transition-colors"
                        title="Delete entry"
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
        onSignupSuccess={() => setCurrentView("dashboard")}
        onNavigateToLogin={() => setCurrentView("login")}
      />
    );
  }

  if (currentView === "login") {
    return (
      <LoginPage
        onLoginSuccess={() => setCurrentView("dashboard")}
        onNavigateToSignup={() => setCurrentView("signup")}
      />
    );
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
