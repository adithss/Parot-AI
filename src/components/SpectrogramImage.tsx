import React from "react";

interface SpectrogramImageProps {
  /** URL to the spectrogram image */
  imageUrl: string;
  /** Label shown above the spectrogram */
  label?: string;
  /** Alt text for the image */
  alt?: string;
}

const SpectrogramImage: React.FC<SpectrogramImageProps> = ({
  imageUrl,
  label = "Audio Spectrogram",
  alt = "Audio frequency spectrogram visualization",
}) => {
  return (
    <div className="w-full rounded-xl overflow-hidden border border-gray-700 bg-gray-900 shadow-inner">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700">
        <span className="text-xs font-mono font-semibold text-cyan-400 tracking-widest uppercase">
          {label}
        </span>
      </div>

      {/* Image Container */}
      <div className="p-4 bg-gray-900">
        <img
          src={imageUrl}
          alt={alt}
          className="w-full h-auto rounded-lg"
          style={{ backgroundColor: "#111827" }}
        />
      </div>

      {/* Footer info */}
      <div className="flex justify-center items-center px-3 py-1.5 bg-gray-800/60 border-t border-gray-700">
        <span className="text-[10px] text-gray-500 font-mono">
          Y = frequency (pitch) &nbsp;·&nbsp; X = time &nbsp;·&nbsp; color =
          amplitude (loudness)
        </span>
      </div>
    </div>
  );
};

export default SpectrogramImage;
