import React, { useEffect, useRef, useCallback, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type SpectrogramMode = "live" | "file";

interface SpectrogramProps {
  /** Pass a live MediaStream (microphone) for real-time mode */
  stream?: MediaStream | null;
  /** Pass an audio File/Blob for file-analysis mode */
  audioFile?: File | Blob | null;
  /** Whether the live stream is actively recording */
  isRecording?: boolean;
  /** Height of the canvas in px (default 160) */
  height?: number;
  /** FFT size – must be power of 2 between 32–32768 (default 2048) */
  fftSize?: number;
  /** Label shown above the spectrogram */
  label?: string;
  /** Colour palette preset */
  colorScheme?: "plasma" | "viridis" | "inferno" | "cyan";
}

// ─── Colour maps ─────────────────────────────────────────────────────────────
// Each map: 256 stops → [r, g, b] for amplitude 0 (silence) → 255 (loud)

function getColor(
  intensity: number, // 0–255
  scheme: NonNullable<SpectrogramProps["colorScheme"]>,
): [number, number, number] {
  const t = intensity / 255;

  switch (scheme) {
    case "plasma": {
      // Purple → orange → yellow
      const r = Math.round(255 * Math.min(1, t * 2.0));
      const g = Math.round(255 * Math.max(0, t * 2.0 - 0.5));
      const b = Math.round(255 * Math.max(0, 1 - t * 2.2));
      return [r, g, b];
    }
    case "viridis": {
      // Dark purple → teal → yellow-green
      const r = Math.round(255 * (0.267 + 0.5 * t + 0.3 * t * t));
      const g = Math.round(255 * (0.005 + 1.1 * t - 0.4 * t * t));
      const b = Math.round(255 * (0.329 + 0.1 * t - 0.45 * t * t));
      return [
        Math.min(255, Math.max(0, r)),
        Math.min(255, Math.max(0, g)),
        Math.min(255, Math.max(0, b)),
      ];
    }
    case "inferno": {
      // Black → purple → orange → white
      const r = Math.round(255 * Math.min(1, t * 2.3 - 0.2));
      const g = Math.round(255 * Math.max(0, t * 1.8 - 0.7));
      const b = Math.round(255 * (t < 0.5 ? t * 1.2 : 1.2 - t * 1.2));
      return [
        Math.min(255, Math.max(0, r)),
        Math.min(255, Math.max(0, g)),
        Math.min(255, Math.max(0, b)),
      ];
    }
    case "cyan":
    default: {
      // Dark navy → cyan → white (matches the app's existing palette)
      const r = Math.round(255 * Math.max(0, t * 2 - 1));
      const g = Math.round(255 * Math.min(1, t * 1.6));
      const b = Math.round(255 * Math.min(1, t + 0.1));
      return [
        Math.min(255, Math.max(0, r)),
        Math.min(255, Math.max(0, g)),
        Math.min(255, Math.max(0, b)),
      ];
    }
  }
}

// ─── Frequency-band labels (approximate for 44.1 kHz / FFT 2048) ─────────────

const FREQ_LABELS = [
  { label: "20Hz", pct: 0 },
  { label: "500Hz", pct: 0.22 },
  { label: "2kHz", pct: 0.45 },
  { label: "8kHz", pct: 0.7 },
  { label: "20kHz", pct: 1 },
];

// ─── Component ────────────────────────────────────────────────────────────────

const Spectrogram: React.FC<SpectrogramProps> = ({
  stream = null,
  audioFile = null,
  isRecording = false,
  height = 160,
  fftSize = 2048,
  label = "Spectrogram",
  colorScheme = "cyan",
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // AudioContext refs
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<
    MediaStreamAudioSourceNode | AudioBufferSourceNode | null
  >(null);
  const rafRef = useRef<number | null>(null);

  // Rolling image buffer (we draw columns left-to-right and scroll)
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);

  const [canvasWidth, setCanvasWidth] = useState(600);
  const [isReady, setIsReady] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [peakDb, setPeakDb] = useState<number>(-60);

  // ── Observe container width ────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setCanvasWidth(Math.floor(entry.contentRect.width));
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── Create offscreen buffer when canvas size changes ───────────────────────
  useEffect(() => {
    const offscreen = document.createElement("canvas");
    offscreen.width = canvasWidth;
    offscreen.height = height;
    const ctx = offscreen.getContext("2d")!;
    ctx.fillStyle = "#0a0f1a";
    ctx.fillRect(0, 0, canvasWidth, height);
    offscreenRef.current = offscreen;
  }, [canvasWidth, height]);

  // ── Draw loop ─────────────────────────────────────────────────────────────
  const drawFrame = useCallback(() => {
    const analyser = analyserRef.current;
    const canvas = canvasRef.current;
    const offscreen = offscreenRef.current;
    if (!analyser || !canvas || !offscreen) return;

    const binCount = analyser.frequencyBinCount; // fftSize / 2
    const dataArray = new Uint8Array(binCount);
    analyser.getByteFrequencyData(dataArray);

    const w = canvas.width;
    const h = canvas.height;

    // Scroll offscreen one pixel to the left
    const offCtx = offscreen.getContext("2d")!;
    offCtx.drawImage(offscreen, -1, 0);

    // Draw new column at the rightmost pixel
    // Map frequency bins (linear) to canvas rows (log-ish scale gives more room to bass)
    const colX = w - 1;
    for (let row = 0; row < h; row++) {
      // row 0 → top → high frequency, row h-1 → bottom → low frequency
      const normY = 1 - row / h; // 0 (low) → 1 (high)
      // Log scale mapping
      const logY = Math.pow(normY, 1.5);
      const binIndex = Math.floor(logY * (binCount - 1));
      const intensity = dataArray[binIndex];
      const [r, g, b] = getColor(intensity, colorScheme);

      offCtx.fillStyle = `rgb(${r},${g},${b})`;
      offCtx.fillRect(colX, row, 1, 1);
    }

    // Copy offscreen to visible canvas
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(offscreen, 0, 0);

    // Draw axis labels overlay
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, 0, 52, h);
    ctx.font = "10px monospace";
    ctx.fillStyle = "#8be0f4";
    for (const { label: lbl, pct } of FREQ_LABELS) {
      // pct 0 = low freq (bottom), pct 1 = high (top)
      const y = h - pct * h;
      ctx.fillText(lbl, 2, Math.max(10, Math.min(h - 2, y)));
    }

    // Peak dB meter
    const maxBin = Math.max(...Array.from(dataArray));
    const db = 20 * Math.log10((maxBin + 1) / 256);
    setPeakDb(Math.round(db));

    rafRef.current = requestAnimationFrame(drawFrame);
  }, [colorScheme, height]);

  // ── Tear down audio graph ─────────────────────────────────────────────────
  const teardown = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch (_) {}
      sourceRef.current = null;
    }
    if (analyserRef.current) {
      try {
        analyserRef.current.disconnect();
      } catch (_) {}
      analyserRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setIsReady(false);
  }, []);

  // ── LIVE STREAM mode ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!stream || !isRecording) {
      if (!stream && !audioFile) teardown();
      return;
    }

    teardown();
    setErrorMsg(null);

    try {
      const ctx = new AudioContext({ sampleRate: 16000 });
      const analyser = ctx.createAnalyser();
      analyser.fftSize = fftSize;
      analyser.smoothingTimeConstant = 0.8;
      analyser.minDecibels = -90;
      analyser.maxDecibels = -10;

      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      sourceRef.current = source;

      setIsReady(true);
      rafRef.current = requestAnimationFrame(drawFrame);
    } catch (err) {
      setErrorMsg("Failed to initialise audio analyser.");
    }

    return () => teardown();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream, isRecording, fftSize]);

  // ── FILE mode ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!audioFile) return;

    teardown();
    setErrorMsg(null);
    setIsReady(false);

    let cancelled = false;

    (async () => {
      try {
        const arrayBuffer = await (audioFile as File).arrayBuffer();
        if (cancelled) return;

        const ctx = new AudioContext();
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
        if (cancelled) {
          ctx.close();
          return;
        }

        const analyser = ctx.createAnalyser();
        analyser.fftSize = fftSize;
        analyser.smoothingTimeConstant = 0.75;
        analyser.minDecibels = -90;
        analyser.maxDecibels = -10;

        const bufferSource = ctx.createBufferSource();
        bufferSource.buffer = audioBuffer;
        bufferSource.connect(analyser);
        analyser.connect(ctx.destination);

        audioCtxRef.current = ctx;
        analyserRef.current = analyser;
        sourceRef.current = bufferSource;

        bufferSource.start(0);
        setIsReady(true);
        rafRef.current = requestAnimationFrame(drawFrame);

        bufferSource.onended = () => {
          if (rafRef.current) cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        };
      } catch (err) {
        if (!cancelled) setErrorMsg("Could not decode audio for spectrogram.");
      }
    })();

    return () => {
      cancelled = true;
      teardown();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioFile, fftSize]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl overflow-hidden border border-gray-700 bg-gray-900 shadow-inner"
      style={{ position: "relative" }}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700">
        <span className="text-xs font-mono font-semibold text-cyan-400 tracking-widest uppercase">
          {label}
        </span>
        <div className="flex items-center gap-3">
          {isReady && (
            <span
              className="text-xs font-mono"
              style={{
                color:
                  peakDb > -6
                    ? "#f87171"
                    : peakDb > -20
                      ? "#fbbf24"
                      : "#34d399",
              }}
            >
              {peakDb} dB
            </span>
          )}
          {/* Colour-scale legend */}
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-gray-500 font-mono">quiet</span>
            <div
              className="w-20 h-2 rounded"
              style={{
                background:
                  colorScheme === "cyan"
                    ? "linear-gradient(to right, #0a0f1a, #06b6d4, #ffffff)"
                    : colorScheme === "plasma"
                      ? "linear-gradient(to right, #0d0221, #7e0075, #fe6f2f, #f9e94e)"
                      : colorScheme === "viridis"
                        ? "linear-gradient(to right, #440154, #31688e, #35b779, #fde725)"
                        : "linear-gradient(to right, #000004, #b63679, #fc8961, #fcfdbf)",
              }}
            />
            <span className="text-[10px] text-gray-500 font-mono">loud</span>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div style={{ position: "relative", height }}>
        <canvas
          ref={canvasRef}
          width={canvasWidth}
          height={height}
          style={{ display: "block", width: "100%", height }}
        />

        {/* Idle / loading overlay */}
        {!isReady && !errorMsg && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center gap-2"
            style={{ background: "#0a0f1a" }}
          >
            <svg
              className="w-8 h-8 text-gray-600"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path d="M3 12h1m16 0h1M12 3v1m0 16v1M5.64 5.64l.71.71M17.66 17.66l.71.71M5.64 18.36l.71-.71M17.66 6.34l.71-.71" />
            </svg>
            <p className="text-xs text-gray-600 font-mono">
              {audioFile ? "Decoding audio…" : "Awaiting audio signal"}
            </p>
          </div>
        )}

        {/* Error overlay */}
        {errorMsg && (
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{ background: "#0a0f1a" }}
          >
            <p className="text-xs text-red-400 font-mono px-4 text-center">
              {errorMsg}
            </p>
          </div>
        )}

        {/* Axis label: Time → */}
        <div className="absolute bottom-1 right-2 text-[10px] text-gray-600 font-mono pointer-events-none">
          time →
        </div>
      </div>

      {/* Bottom axis bar */}
      <div className="flex justify-between items-center px-3 py-1 bg-gray-800/60 border-t border-gray-700">
        <span className="text-[10px] text-gray-500 font-mono">← older</span>
        <span className="text-[10px] text-gray-500 font-mono">
          {colorScheme === "cyan"
            ? "Cyan"
            : colorScheme === "plasma"
              ? "Plasma"
              : colorScheme === "viridis"
                ? "Viridis"
                : "Inferno"}{" "}
          scale &nbsp;·&nbsp; Y = frequency (pitch) &nbsp;·&nbsp; colour =
          amplitude
        </span>
        <span className="text-[10px] text-gray-500 font-mono">now →</span>
      </div>
    </div>
  );
};

export default Spectrogram;
