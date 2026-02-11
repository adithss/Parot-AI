import React, { useState, useEffect, useRef } from "react";
import { AnalysisResult, ChatMessage } from "./types";
import {
  queryMeetingContext,
  translateContent,
  API_BASE_URL,
} from "../services/geminiService";
import {
  BotMessageSquareIcon,
  FileTextIcon,
  SmileIcon,
  ListTodoIcon,
  GavelIcon,
  BrainCircuitIcon,
  LanguagesIcon,
  LoaderIcon,
  MessageCircleQuestionIcon,
  DownloadIcon,
  CalendarPlusIcon,
} from "./icons";
import Spectrogram from "./Spectrogram";
import SpectrogramImage from "./SpectrogramImage";

interface MeetingAnalysisProps {
  result: AnalysisResult;
  onReset: () => void;
  /** Optional: original audio file so the spectrogram can replay it */
  audioFile?: File | Blob | null;
}

const MeetingAnalysis: React.FC<MeetingAnalysisProps> = ({
  result,
  onReset,
  audioFile = null,
}) => {
  const [showTranscript, setShowTranscript] = useState(false);
  const [currentResult, setCurrentResult] = useState<AnalysisResult>(result);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationError, setTranslationError] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState("original");
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  // State for the chatbot
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatting, setIsChatting] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to the bottom of the chat on new message
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  useEffect(() => {
    setCurrentResult(result);
    setSelectedLanguage("original");
    setTranslationError(null);
    setIsTranslating(false);
    setChatMessages([]); // Reset chat when a new result is loaded
  }, [result]);

  const handleTranslate = async (targetLanguage: string) => {
    if (targetLanguage === "original") {
      setCurrentResult(result);
      setSelectedLanguage("original");
      setTranslationError(null);
      return;
    }

    setSelectedLanguage(targetLanguage);
    setIsTranslating(true);
    setTranslationError(null);
    try {
      const translatedResult = await translateContent(result, targetLanguage);
      setCurrentResult(translatedResult);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unknown error occurred.";
      setTranslationError(`Translation failed: ${errorMessage}`);
    } finally {
      setIsTranslating(false);
    }
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const question = chatInput.trim();
    if (!question || isChatting) return;

    const newUserMessage: ChatMessage = { sender: "user", text: question };
    setChatMessages((prev) => [...prev, newUserMessage]);
    setChatInput("");
    setIsChatting(true);

    try {
      const answer = await queryMeetingContext(result, question);
      const newBotMessage: ChatMessage = { sender: "bot", text: answer };
      setChatMessages((prev) => [...prev, newBotMessage]);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unknown error occurred.";
      const errorBotMessage: ChatMessage = {
        sender: "bot",
        text: `Sorry, I encountered an error: ${errorMessage}`,
      };
      setChatMessages((prev) => [...prev, errorBotMessage]);
    } finally {
      setIsChatting(false);
    }
  };

  const handleDownloadReport = async () => {
    setIsGeneratingPdf(true);
    const {
      summary,
      sentiment,
      emotionAnalysis,
      keyDecisions,
      actionItems,
      diarizedTranscript,
    } = currentResult;

    // Create a container to hold the PDF content off-screen to prevent UI flicker
    // nesting ensures html2canvas captures the child element correctly starting at 0,0 relative to container
    const container = document.createElement("div");
    Object.assign(container.style, {
      position: "fixed",
      left: "-10000px",
      top: "0",
      zIndex: "-1000",
    });
    document.body.appendChild(container);

    // Create the actual content element
    const element = document.createElement("div");
    Object.assign(element.style, {
      width: "800px", // Fixed width for A4 consistency
      backgroundColor: "#ffffff",
      color: "#000000",
      padding: "40px",
      fontFamily: "Arial, Helvetica, sans-serif",
    });

    // Construct the HTML content (clean, light mode, black text)
    element.innerHTML = `
      <div style="font-family: Arial, Helvetica, sans-serif; color: #000000; -webkit-print-color-adjust: exact;">
        <div style="border-bottom: 2px solid #0891b2; padding-bottom: 20px; margin-bottom: 30px;">
          <h1 style="color: #0891b2; font-size: 28px; font-weight: 800; margin: 0;">Meeting Intelligence Report</h1>
          <p style="color: #4b5563; margin-top: 8px; font-size: 14px;"><strong>Generated on:</strong> ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()}</p>
        </div>

        <div style="margin-bottom: 30px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Executive Summary</h2>
          <div style="line-height: 1.6; color: #1f2937; white-space: pre-wrap; font-size: 14px;">
            ${
              summary
                ? summary.replace(/\n/g, "<br/>")
                : "No summary available."
            }
          </div>
        </div>

        <div style="margin-bottom: 30px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Sentiment Analysis</h2>
          <p style="margin-bottom: 8px; color: #1f2937;"><strong>Overall Sentiment:</strong> <span style="background: #f3f4f6; padding: 2px 8px; border-radius: 4px; color: #000;">${
            sentiment.overall
          }</span></p>
          <ul style="list-style-type: disc; margin-left: 20px; color: #1f2937;">
            ${sentiment.highlights
              .map((h) => `<li style="margin-bottom: 4px;">"${h}"</li>`)
              .join("")}
          </ul>
        </div>

        <div style="margin-bottom: 30px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Emotion Analysis</h2>
          <ul style="list-style-type: none; padding: 0;">
            ${emotionAnalysis
              .map(
                (e) => `
              <li style="margin-bottom: 12px; background: #f9fafb; padding: 10px; border-radius: 6px; border: 1px solid #e5e7eb;">
                <strong style="color: #0891b2;">${e.emotion}:</strong> <span style="color: #374151;">${e.reasoning}</span>
              </li>
            `,
              )
              .join("")}
          </ul>
        </div>

        <div style="margin-bottom: 30px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Key Decisions</h2>
          <ul style="list-style-type: disc; margin-left: 20px; color: #1f2937;">
            ${
              keyDecisions.length > 0
                ? keyDecisions
                    .map((d) => `<li style="margin-bottom: 6px;">${d}</li>`)
                    .join("")
                : "<li>None</li>"
            }
          </ul>
        </div>

        <div style="margin-bottom: 30px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Action Items</h2>
          <ol style="margin-left: 20px; color: #1f2937;">
            ${
              actionItems.length > 0
                ? actionItems
                    .map(
                      (item) =>
                        `<li style="margin-bottom: 8px; padding-left: 5px;">${item}</li>`,
                    )
                    .join("")
                : "<li>None</li>"
            }
          </ol>
        </div>

        ${
          currentResult.spectrogramUrl
            ? `
        <div style="margin-bottom: 30px; page-break-inside: avoid;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 12px; border-left: 4px solid #0891b2; padding-left: 10px;">Audio Spectrogram</h2>
          <img src="${API_BASE_URL}${currentResult.spectrogramUrl}" alt="Audio Spectrogram" style="width: 100%; max-width: 720px; height: auto; border-radius: 8px; background: #111827; border: 1px solid #e5e7eb;" crossorigin="anonymous" />
          <p style="text-align: center; color: #6b7280; font-size: 11px; margin-top: 8px;">
            Y-axis = Frequency (Hz) &nbsp;·&nbsp; X-axis = Time (s) &nbsp;·&nbsp; Color = Amplitude (dB)
          </p>
        </div>
        `
            : ""
        }

        <div style="margin-top: 40px; border-top: 1px solid #e5e7eb; padding-top: 20px;">
          <h2 style="font-size: 20px; font-weight: 700; color: #111827; margin-bottom: 16px;">Full Transcript</h2>
          <div style="font-size: 13px; color: #4b5563;">
            ${diarizedTranscript
              .map(
                (segment) => `
              <div style="margin-bottom: 12px; page-break-inside: avoid;">
                <span style="font-weight: 700; color: #0e7490; display: block; margin-bottom: 2px;">${segment.speaker}</span>
                <span style="display: block; line-height: 1.5; white-space: pre-wrap;">${segment.text}</span>
              </div>
            `,
              )
              .join("")}
          </div>
        </div>
      </div>
    `;
    container.appendChild(element);

    // If there's a spectrogram, preload it before generating PDF
    if (currentResult.spectrogramUrl) {
      try {
        const spectrogramImg = element.querySelector(
          'img[alt="Audio Spectrogram"]',
        ) as HTMLImageElement;
        if (spectrogramImg) {
          await new Promise((resolve, reject) => {
            spectrogramImg.onload = resolve;
            spectrogramImg.onerror = reject;
            // Trigger load if not already loaded
            if (!spectrogramImg.complete) {
              spectrogramImg.src = spectrogramImg.src;
            } else {
              resolve(null);
            }
          });
        }
      } catch (err) {
        console.warn("Failed to preload spectrogram image:", err);
      }
    }

    // Delay to allow DOM rendering and layout calculation
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const w = window as any;
    if (w.html2pdf) {
      const opt = {
        margin: [0.5, 0.5, 0.5, 0.5], // Top, Left, Bottom, Right
        filename: `Parot-Report-${new Date().toISOString().slice(0, 10)}.pdf`,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          letterRendering: true,
          scrollY: 0,
        },
        jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
      };

      try {
        await w.html2pdf().set(opt).from(element).save();
      } catch (err) {
        console.error("PDF generation failed:", err);
        alert("Failed to generate PDF. Check console for details.");
      } finally {
        if (document.body.contains(container)) {
          document.body.removeChild(container);
        }
        setIsGeneratingPdf(false);
      }
    } else {
      alert("PDF generation library is not loaded. Please refresh the page.");
      if (document.body.contains(container)) {
        document.body.removeChild(container);
      }
      setIsGeneratingPdf(false);
    }
  };

  const handleAddToCalendar = (actionItemText: string) => {
    const title = encodeURIComponent(actionItemText);
    const details = encodeURIComponent(
      "Action item from Gemini Meeting Intelligence report.",
    );

    // Creates a link to a full-day event for today. The user can adjust the time.
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const url = `https://www.google.com/calendar/render?action=TEMPLATE&text=${title}&details=${details}&dates=${today}/${today}`;

    window.open(url, "_blank", "noopener,noreferrer");
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment.toLowerCase()) {
      case "positive":
        return "text-green-400 border-green-400 bg-green-900/50";
      case "negative":
        return "text-red-400 border-red-400 bg-red-900/50";
      case "neutral":
        return "text-yellow-400 border-yellow-400 bg-yellow-900/50";
      default:
        return "text-gray-400 border-gray-400 bg-gray-900/50";
    }
  };

  const analysisToDisplay = currentResult;

  return (
    <div className="w-full text-left animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-center mb-6">
        <h2 className="text-3xl font-bold text-cyan-300">Meeting Insights</h2>

        <div className="flex items-center gap-4 mt-4 sm:mt-0 relative">
          <div className="flex items-center gap-2">
            <LanguagesIcon className="w-6 h-6 text-gray-400" />
            <select
              value={selectedLanguage}
              onChange={(e) => handleTranslate(e.target.value)}
              disabled={isTranslating}
              className="bg-gray-700 border border-gray-600 rounded-md pl-3 pr-8 py-1.5 text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none appearance-none"
            >
              <option value="original">Original</option>
              <option value="Spanish">Spanish</option>
              <option value="French">French</option>
              <option value="German">German</option>
              <option value="Japanese">Japanese</option>
              <option value="Chinese">Chinese</option>
              <option value="Hindi">Hindi</option>
              <option value="Tamil">Tamil</option>
              <option value="Bengali">Bengali</option>
              <option value="Marathi">Marathi</option>
              <option value="Telugu">Telugu</option>
              <option value="Malayalam">Malayalam</option>
            </select>
            {isTranslating && (
              <LoaderIcon className="w-5 h-5 animate-spin absolute right-2 top-1/2 -translate-y-1/2 text-cyan-400 pointer-events-none" />
            )}
          </div>

          <button
            onClick={handleDownloadReport}
            disabled={isGeneratingPdf}
            className="flex items-center px-4 py-1.5 bg-gray-700 text-white font-semibold rounded-md hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Download full report as PDF"
          >
            {isGeneratingPdf ? (
              <LoaderIcon className="w-5 h-5 mr-2 animate-spin" />
            ) : (
              <DownloadIcon className="w-5 h-5 mr-2" />
            )}
            {isGeneratingPdf ? "Exporting..." : "Export"}
          </button>
        </div>
      </div>

      {translationError && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 p-3 rounded-lg mb-4 text-center">
          {translationError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Summary Card (takes more space) */}
        <div className="bg-gray-800/60 p-6 rounded-lg border border-gray-700 lg:col-span-1">
          <h3 className="flex items-center text-xl font-semibold mb-3 text-cyan-400">
            <BotMessageSquareIcon className="w-6 h-6 mr-3" />
            AI Summary
          </h3>
          <p className="text-gray-300 whitespace-pre-wrap">
            {analysisToDisplay.summary}
          </p>
        </div>

        {/* Analysis Column */}
        <div className="flex flex-col gap-6 lg:col-span-1">
          <div className="bg-gray-800/60 p-6 rounded-lg border border-gray-700">
            <h3 className="flex items-center text-xl font-semibold mb-3 text-cyan-400">
              <SmileIcon className="w-6 h-6 mr-3" />
              Sentiment
            </h3>
            <span
              className={`px-3 py-1 text-sm font-bold rounded-full ${getSentimentColor(
                analysisToDisplay.sentiment.overall,
              )}`}
            >
              {analysisToDisplay.sentiment.overall}
            </span>
            {analysisToDisplay.sentiment.highlights &&
              analysisToDisplay.sentiment.highlights.length > 0 && (
                <ul className="list-disc list-inside mt-3 text-gray-400 space-y-1 text-sm">
                  {analysisToDisplay.sentiment.highlights.map((item, index) => (
                    <li key={index}>"{item}"</li>
                  ))}
                </ul>
              )}
          </div>
          <div className="bg-gray-800/60 p-6 rounded-lg border border-gray-700">
            <h3 className="flex items-center text-xl font-semibold mb-3 text-cyan-400">
              <BrainCircuitIcon className="w-6 h-6 mr-3" />
              Emotion Analysis
            </h3>
            {analysisToDisplay.emotionAnalysis &&
            analysisToDisplay.emotionAnalysis.length > 0 ? (
              <div className="space-y-2">
                {analysisToDisplay.emotionAnalysis.map((item, index) => (
                  <div key={index}>
                    <p className="font-semibold text-gray-200">
                      {item.emotion}:{" "}
                      <span className="text-gray-400 font-normal">
                        {item.reasoning}
                      </span>
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">No specific emotions detected.</p>
            )}
          </div>
        </div>

        {/* Outcomes Column */}
        <div className="flex flex-col gap-6 lg:col-span-1">
          <div className="bg-gray-800/60 p-6 rounded-lg border border-gray-700">
            <h3 className="flex items-center text-xl font-semibold mb-3 text-cyan-400">
              <GavelIcon className="w-6 h-6 mr-3" />
              Key Decisions
            </h3>
            {analysisToDisplay.keyDecisions &&
            analysisToDisplay.keyDecisions.length > 0 ? (
              <ul className="list-disc list-inside text-gray-300 space-y-1">
                {analysisToDisplay.keyDecisions.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-400">No key decisions were identified.</p>
            )}
          </div>
          <div className="bg-gray-800/60 p-6 rounded-lg border border-gray-700">
            <h3 className="flex items-center text-xl font-semibold mb-3 text-cyan-400">
              <ListTodoIcon className="w-6 h-6 mr-3" />
              Action Items
            </h3>
            {analysisToDisplay.actionItems &&
            analysisToDisplay.actionItems.length > 0 ? (
              <div className="space-y-2">
                {analysisToDisplay.actionItems.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="text-gray-300 flex-1">
                      {index + 1}. {item}
                    </span>
                    <button
                      onClick={() => handleAddToCalendar(item)}
                      className="p-1.5 text-gray-400 hover:text-cyan-400 hover:bg-gray-700 rounded-full transition-colors"
                      title="Add to Google Calendar"
                    >
                      <CalendarPlusIcon className="w-5 h-5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">No action items were identified.</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Spectrogram Section ─────────────────────────────────────────── */}
      {result.spectrogramUrl && (
        <div className="mb-8">
          <h3 className="flex items-center text-lg font-semibold mb-3 text-cyan-400">
            <svg
              className="w-5 h-5 mr-2"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M2 12h1m18 0h1M6.5 7.5l-1-1M18.5 7.5l1-1M6.5 16.5l-1 1M18.5 16.5l1 1M12 4v1m0 14v1" />
              <circle cx="12" cy="12" r="4" />
            </svg>
            Audio Spectrogram
          </h3>
          <SpectrogramImage
            imageUrl={`${API_BASE_URL}${result.spectrogramUrl}`}
            label="Frequency · Time · Amplitude"
          />
        </div>
      )}

      {/* Transcript Section */}
      <div className="mb-8">
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          className="flex items-center text-lg font-semibold text-cyan-400 hover:text-cyan-300 transition-colors"
        >
          <FileTextIcon className="w-5 h-5 mr-2" />
          {showTranscript ? "Hide" : "Show"} Full Transcript
        </button>
        {showTranscript && (
          <div className="mt-4 p-4 bg-gray-900/70 rounded-lg border border-gray-700 max-h-72 overflow-y-auto">
            <div className="space-y-4">
              {analysisToDisplay.diarizedTranscript.length > 0 ? (
                analysisToDisplay.diarizedTranscript.map((segment, index) => (
                  <div key={index} className="flex flex-col items-start">
                    <span className="px-2 py-1 text-xs font-bold text-cyan-200 bg-cyan-900/50 rounded-md mb-1">
                      {segment.speaker}
                    </span>
                    <p className="text-gray-300">{segment.text}</p>
                  </div>
                ))
              ) : (
                <p className="text-gray-400">
                  Transcript is empty or could not be diarized.
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Context-Aware Chatbot Section */}
      <div className="mt-8 pt-6 border-t border-gray-700">
        <h3 className="flex items-center text-xl font-semibold mb-4 text-cyan-400">
          <MessageCircleQuestionIcon className="w-6 h-6 mr-3" />
          Ask a Follow-up Question
        </h3>
        <div className="bg-gray-900/70 rounded-lg border border-gray-700 max-h-80 flex flex-col">
          <div
            ref={chatContainerRef}
            className="flex-grow p-4 space-y-4 overflow-y-auto"
          >
            {chatMessages.map((msg, index) => (
              <div
                key={index}
                className={`flex items-end gap-2 ${
                  msg.sender === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.sender === "bot" && (
                  <BotMessageSquareIcon className="w-8 h-8 text-cyan-400 flex-shrink-0" />
                )}
                <div
                  className={`max-w-xl px-4 py-2 rounded-lg ${
                    msg.sender === "user"
                      ? "bg-cyan-800 text-white"
                      : "bg-gray-700 text-gray-200"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                </div>
              </div>
            ))}
            {isChatting && (
              <div className="flex items-end gap-2 justify-start">
                <BotMessageSquareIcon className="w-8 h-8 text-cyan-400 flex-shrink-0" />
                <div className="max-w-xl px-4 py-2 rounded-lg bg-gray-700 text-gray-200">
                  <LoaderIcon className="w-5 h-5 animate-spin" />
                </div>
              </div>
            )}
          </div>
          <form
            onSubmit={handleChatSubmit}
            className="p-4 border-t border-gray-700 flex items-center gap-2"
          >
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="e.g., Who is responsible for the Q3 budget?"
              className="flex-grow bg-gray-800 border border-gray-600 rounded-full py-2 px-4 text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              disabled={isChatting}
            />
            <button
              type="submit"
              className="bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-2 px-4 rounded-full disabled:bg-gray-600"
              disabled={isChatting || !chatInput}
            >
              Send
            </button>
          </form>
        </div>
      </div>

      <div className="text-center mt-12">
        <button
          onClick={onReset}
          className="px-8 py-3 bg-gray-700 text-white font-bold rounded-full hover:bg-gray-600 transition-transform hover:scale-105 shadow-lg"
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
};

export default MeetingAnalysis;
