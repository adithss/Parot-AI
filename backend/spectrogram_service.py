import os
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import librosa
import librosa.display
from pathlib import Path

logger = logging.getLogger("spectrogram_service")

def create_spectrogram_image(audio_file_path: str, output_dir: str = "static/spectrograms") -> str:
    """
    Generate a static spectrogram image from an audio file.
    
    Args:
        audio_file_path: Path to the audio file
        output_dir: Directory to save the spectrogram image
        
    Returns:
        Relative path to the generated spectrogram image
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Load audio file
        logger.info(f"Loading audio file: {audio_file_path}")
        y, sr = librosa.load(audio_file_path, sr=None)
        
        # Generate spectrogram
        logger.info("Generating spectrogram...")
        D = librosa.stft(y, n_fft=2048, hop_length=512)
        S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        
        # Create custom colormap (plasma-like)
        colors = ['#0d0221', '#7e0075', '#fe6f2f', '#f9e94e']
        n_bins = 256
        cmap = LinearSegmentedColormap.from_list('plasma', colors, N=n_bins)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 4))
        
        # Plot spectrogram
        img = librosa.display.specshow(
            S_db,
            sr=sr,
            x_axis='time',
            y_axis='hz',
            ax=ax,
            cmap=cmap,
            vmin=-80,
            vmax=0
        )
        
        # Customize plot
        ax.set_title('Audio Spectrogram', fontsize=14, color='#06b6d4', fontweight='bold')
        ax.set_xlabel('Time (s)', fontsize=11, color='#9ca3af')
        ax.set_ylabel('Frequency (Hz)', fontsize=11, color='#9ca3af')
        
        # Set background color
        ax.set_facecolor('#0a0f1a')
        fig.patch.set_facecolor('#111827')
        
        # Customize tick colors
        ax.tick_params(colors='#9ca3af', which='both')
        for spine in ax.spines.values():
            spine.set_edgecolor('#374151')
            spine.set_linewidth(1.5)
        
        # Add colorbar
        cbar = fig.colorbar(img, ax=ax, format='%+2.0f dB')
        cbar.ax.tick_params(colors='#9ca3af')
        cbar.set_label('Amplitude (dB)', color='#9ca3af', fontsize=10)
        
        # Tight layout
        plt.tight_layout()
        
        # Generate unique filename based on input file
        input_filename = Path(audio_file_path).stem
        output_filename = f"spectrogram_{input_filename}.png"
        output_path = os.path.join(output_dir, output_filename)
        
        # Save figure
        logger.info(f"Saving spectrogram to: {output_path}")
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#111827')
        plt.close(fig)
        
        # Return relative path
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating spectrogram: {e}", exc_info=True)
        raise Exception(f"Failed to generate spectrogram: {e}")


def cleanup_old_spectrograms(output_dir: str = "static/spectrograms", max_age_hours: int = 24):
    """
    Clean up old spectrogram files.
    
    Args:
        output_dir: Directory containing spectrograms
        max_age_hours: Maximum age of files to keep in hours
    """
    try:
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        if not os.path.exists(output_dir):
            return
            
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    logger.info(f"Removed old spectrogram: {file_path}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up spectrograms: {e}")