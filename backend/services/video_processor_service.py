"""
Video Processor Service - Extract frames and transcribe audio from videos

Provides:
1. Frame extraction using ffmpeg at configurable intervals
2. Audio transcription using OpenAI Whisper API
3. Integration with vision service for frame analysis
4. Combined video understanding for NAVI

This enables NAVI to understand video content by:
- Extracting key frames at intervals (e.g., every 5 seconds)
- Transcribing any spoken audio
- Analyzing frames with vision models
- Combining into a coherent video summary
"""

import os
import tempfile
import asyncio
import subprocess
import base64
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import httpx
import structlog
from dotenv import load_dotenv

# Load .env file to ensure API keys are available in os.environ
load_dotenv()

logger = structlog.get_logger(__name__)


def _get_command_env() -> dict:
    """
    Get environment for command execution with nvm compatibility fixes.
    Removes npm_config_prefix which conflicts with nvm.
    """
    env = os.environ.copy()
    env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
    env["SHELL"] = env.get("SHELL", "/bin/bash")
    return env


# ============================================================
# CONFIGURATION
# ============================================================

# Frame extraction settings
DEFAULT_FRAME_INTERVAL = 5  # seconds between frames
MAX_FRAMES = 20  # Maximum frames to extract
FRAME_FORMAT = "jpg"
FRAME_QUALITY = 85  # JPEG quality (1-100)

# Supported video formats
SUPPORTED_VIDEO_FORMATS = {
    ".mp4",
    ".webm",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
    ".wmv",
    ".flv",
}

# Audio extraction settings
AUDIO_FORMAT = "mp3"
AUDIO_BITRATE = "64k"  # Lower bitrate for transcription (saves tokens)


# ============================================================
# DATA CLASSES
# ============================================================


@dataclass
class ExtractedFrame:
    """A single extracted video frame"""

    timestamp: float  # seconds from start
    base64_data: str  # base64-encoded image
    description: Optional[str] = None  # Vision model description


@dataclass
class VideoTranscription:
    """Transcribed audio from video"""

    full_text: str
    segments: List[Dict[str, Any]] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0


@dataclass
class VideoAnalysis:
    """Complete analysis of a video file"""

    duration: float
    frame_count: int
    frames: List[ExtractedFrame] = field(default_factory=list)
    transcription: Optional[VideoTranscription] = None
    summary: str = ""
    key_moments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration": self.duration,
            "frame_count": self.frame_count,
            "frames": [
                {
                    "timestamp": f.timestamp,
                    "description": f.description,
                    "has_image": bool(f.base64_data),
                }
                for f in self.frames
            ],
            "transcription": (
                {
                    "text": (
                        self.transcription.full_text if self.transcription else None
                    ),
                    "segments": (
                        self.transcription.segments if self.transcription else []
                    ),
                    "language": (
                        self.transcription.language if self.transcription else None
                    ),
                }
                if self.transcription
                else None
            ),
            "summary": self.summary,
            "key_moments": self.key_moments,
            "metadata": self.metadata,
        }

    def to_context_string(self) -> str:
        """Convert to a string that can be used as LLM context"""
        parts = [
            "=== VIDEO ANALYSIS ===",
            f"\n**Duration**: {self.duration:.1f} seconds",
            f"**Frames Analyzed**: {self.frame_count}",
        ]

        if self.summary:
            parts.append(f"\n**Summary**: {self.summary}")

        if self.transcription and self.transcription.full_text:
            parts.append(
                f"\n**Audio Transcription**:\n{self.transcription.full_text[:2000]}"
            )
            if len(self.transcription.full_text) > 2000:
                parts.append("... (truncated)")

        if self.key_moments:
            parts.append("\n**Key Moments**:")
            for moment in self.key_moments:
                ts = moment.get("timestamp", 0)
                desc = moment.get("description", "")
                parts.append(f"  - {ts:.1f}s: {desc}")

        if self.frames:
            parts.append("\n**Frame Descriptions**:")
            for frame in self.frames[:10]:  # Limit to first 10
                if frame.description:
                    parts.append(f"  - {frame.timestamp:.1f}s: {frame.description}")

        parts.append("\n=== END VIDEO ANALYSIS ===")
        return "\n".join(parts)


# ============================================================
# FFMPEG UTILITIES
# ============================================================


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
            env=_get_command_env(),
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def check_ffprobe_available() -> bool:
    """Check if ffprobe is available"""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=5,
            env=_get_command_env(),
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


async def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe"""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=_get_command_env(),
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to get video duration: {e}")
    return 0.0


async def get_video_metadata(video_path: str) -> Dict[str, Any]:
    """Get video metadata using ffprobe"""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=_get_command_env(),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            format_info = data.get("format", {})
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {},
            )
            audio_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
                {},
            )
            return {
                "duration": float(format_info.get("duration", 0)),
                "size_bytes": int(format_info.get("size", 0)),
                "format": format_info.get("format_name", ""),
                "video": {
                    "codec": video_stream.get("codec_name", ""),
                    "width": video_stream.get("width", 0),
                    "height": video_stream.get("height", 0),
                    "fps": (
                        eval(video_stream.get("r_frame_rate", "0/1"))
                        if "/" in video_stream.get("r_frame_rate", "")
                        else 0
                    ),
                },
                "audio": (
                    {
                        "codec": audio_stream.get("codec_name", ""),
                        "channels": audio_stream.get("channels", 0),
                        "sample_rate": audio_stream.get("sample_rate", ""),
                    }
                    if audio_stream
                    else None
                ),
            }
    except Exception as e:
        logger.warning(f"Failed to get video metadata: {e}")
    return {}


# ============================================================
# FRAME EXTRACTION
# ============================================================


async def extract_frames(
    video_path: str,
    output_dir: str,
    interval: float = DEFAULT_FRAME_INTERVAL,
    max_frames: int = MAX_FRAMES,
) -> List[Tuple[float, str]]:
    """
    Extract frames from video at regular intervals.

    Args:
        video_path: Path to video file
        output_dir: Directory to save frames
        interval: Seconds between frames
        max_frames: Maximum frames to extract

    Returns:
        List of (timestamp, frame_path) tuples
    """
    if not check_ffmpeg_available():
        raise RuntimeError("ffmpeg is not available. Please install ffmpeg.")

    duration = await get_video_duration(video_path)
    if duration <= 0:
        logger.warning("Could not determine video duration")
        duration = 300  # Assume 5 minutes max

    # Calculate frame timestamps
    timestamps = []
    t = 0.0
    while t < duration and len(timestamps) < max_frames:
        timestamps.append(t)
        t += interval

    # Extract frames in parallel batches
    frames: List[Tuple[float, str]] = []

    for i, ts in enumerate(timestamps):
        frame_path = os.path.join(output_dir, f"frame_{i:04d}.{FRAME_FORMAT}")

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-ss",
                    str(ts),
                    "-i",
                    video_path,
                    "-vframes",
                    "1",
                    "-q:v",
                    str(int((100 - FRAME_QUALITY) / 10) + 1),  # ffmpeg quality scale
                    "-y",  # Overwrite
                    frame_path,
                ],
                capture_output=True,
                timeout=30,
                env=_get_command_env(),
            )

            if result.returncode == 0 and os.path.exists(frame_path):
                frames.append((ts, frame_path))
                logger.debug(f"Extracted frame at {ts}s")
            else:
                logger.warning(
                    f"Failed to extract frame at {ts}s: {result.stderr.decode()[:200]}"
                )

        except Exception as e:
            logger.warning(f"Error extracting frame at {ts}s: {e}")

    return frames


def frame_to_base64(frame_path: str) -> str:
    """Convert frame image to base64"""
    with open(frame_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# AUDIO EXTRACTION & TRANSCRIPTION
# ============================================================


async def extract_audio(video_path: str, output_path: str) -> bool:
    """
    Extract audio track from video.

    Args:
        video_path: Path to video file
        output_path: Path for output audio file

    Returns:
        True if successful
    """
    if not check_ffmpeg_available():
        raise RuntimeError("ffmpeg is not available")

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",  # No video
                "-acodec",
                "libmp3lame",
                "-ab",
                AUDIO_BITRATE,
                "-ar",
                "16000",  # 16kHz for Whisper
                "-ac",
                "1",  # Mono
                "-y",
                output_path,
            ],
            capture_output=True,
            timeout=120,
            env=_get_command_env(),
        )
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.warning(f"Failed to extract audio: {e}")
        return False


async def transcribe_audio_whisper(
    audio_path: str,
    api_key: Optional[str] = None,
) -> Optional[VideoTranscription]:
    """
    Transcribe audio using OpenAI Whisper API.

    Args:
        audio_path: Path to audio file
        api_key: OpenAI API key (uses env var if not provided)

    Returns:
        Transcription result or None if failed
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("No OpenAI API key available for transcription")
        return None

    try:
        async with httpx.AsyncClient() as client:
            with open(audio_path, "rb") as audio_file:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={
                        "file": (os.path.basename(audio_path), audio_file, "audio/mpeg")
                    },
                    data={
                        "model": "whisper-1",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                    },
                    timeout=300,  # 5 minute timeout for long videos
                )

            if response.status_code == 200:
                data = response.json()
                return VideoTranscription(
                    full_text=data.get("text", ""),
                    segments=data.get("segments", []),
                    language=data.get("language", "en"),
                    duration=data.get("duration", 0.0),
                )
            else:
                logger.error(
                    f"Whisper API error: {response.status_code} - {response.text[:200]}"
                )

    except Exception as e:
        logger.error(f"Transcription failed: {e}")

    return None


# ============================================================
# FRAME ANALYSIS WITH VISION
# ============================================================


async def analyze_frames_with_vision(
    frames: List[ExtractedFrame],
    api_key: Optional[str] = None,
    provider: str = "anthropic",
) -> List[ExtractedFrame]:
    """
    Analyze extracted frames using vision model.

    Args:
        frames: List of extracted frames with base64 data
        api_key: API key for vision provider
        provider: Vision provider (anthropic, openai, google)

    Returns:
        Frames with descriptions added
    """
    from backend.services.vision_service import VisionClient, VisionProvider

    provider_enum = VisionProvider(provider.lower())

    # Get API key from env if not provided
    if not api_key:
        env_keys = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        api_key = os.environ.get(env_keys.get(provider, "ANTHROPIC_API_KEY"))

    if not api_key:
        logger.warning(f"No API key for vision provider {provider}")
        return frames

    prompt = """Briefly describe what's happening in this video frame.
Focus on:
- Main subjects/actions
- Important UI elements (if it's a screen recording)
- Text visible on screen
- Any changes from what might have been shown before

Keep the description concise (1-2 sentences)."""

    analyzed_frames = []

    # Analyze frames (can parallelize if needed)
    for frame in frames:
        try:
            description = await VisionClient.analyze_image(
                frame.base64_data,
                prompt,
                provider=provider_enum,
                timeout=30,
            )
            frame.description = description.strip()
        except Exception as e:
            logger.warning(f"Failed to analyze frame at {frame.timestamp}s: {e}")
            frame.description = None

        analyzed_frames.append(frame)

    return analyzed_frames


# ============================================================
# VIDEO PROCESSOR
# ============================================================


class VideoProcessor:
    """Main video processing service"""

    @classmethod
    async def process_video(
        cls,
        video_path: str,
        frame_interval: float = DEFAULT_FRAME_INTERVAL,
        max_frames: int = MAX_FRAMES,
        transcribe: bool = True,
        analyze_frames: bool = True,
        vision_provider: str = "anthropic",
    ) -> VideoAnalysis:
        """
        Process a video file and extract all relevant information.

        Args:
            video_path: Path to video file
            frame_interval: Seconds between frame extractions
            max_frames: Maximum frames to extract
            transcribe: Whether to transcribe audio
            analyze_frames: Whether to analyze frames with vision model
            vision_provider: Provider for frame analysis

        Returns:
            Complete video analysis
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        ext = Path(video_path).suffix.lower()
        if ext not in SUPPORTED_VIDEO_FORMATS:
            raise ValueError(f"Unsupported video format: {ext}")

        if not check_ffmpeg_available():
            raise RuntimeError(
                "ffmpeg is not available. Please install ffmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg\n"
                "  Windows: Download from https://ffmpeg.org/download.html"
            )

        logger.info(f"Processing video: {video_path}")

        # Get metadata
        metadata = await get_video_metadata(video_path)
        duration = metadata.get("duration", 0)

        # Create temp directory for processing
        temp_dir = tempfile.mkdtemp(prefix="video_process_")

        try:
            # Extract frames
            logger.info(
                f"Extracting frames (interval: {frame_interval}s, max: {max_frames})"
            )
            frame_paths = await extract_frames(
                video_path,
                temp_dir,
                interval=frame_interval,
                max_frames=max_frames,
            )

            # Convert frames to ExtractedFrame objects
            frames = []
            for ts, path in frame_paths:
                try:
                    b64 = frame_to_base64(path)
                    frames.append(ExtractedFrame(timestamp=ts, base64_data=b64))
                except Exception as e:
                    logger.warning(f"Failed to encode frame at {ts}s: {e}")

            logger.info(f"Extracted {len(frames)} frames")

            # Transcribe audio if requested
            transcription = None
            if transcribe and metadata.get("audio"):
                logger.info("Extracting and transcribing audio...")
                audio_path = os.path.join(temp_dir, f"audio.{AUDIO_FORMAT}")
                if await extract_audio(video_path, audio_path):
                    transcription = await transcribe_audio_whisper(audio_path)
                    if transcription:
                        logger.info(
                            f"Transcription complete: {len(transcription.full_text)} chars"
                        )

            # Analyze frames with vision if requested
            if analyze_frames and frames:
                logger.info(f"Analyzing {len(frames)} frames with vision model...")
                frames = await analyze_frames_with_vision(
                    frames,
                    provider=vision_provider,
                )

            # Generate summary
            summary = cls._generate_summary(frames, transcription, duration)

            # Identify key moments
            key_moments = cls._identify_key_moments(frames, transcription)

            return VideoAnalysis(
                duration=duration,
                frame_count=len(frames),
                frames=frames,
                transcription=transcription,
                summary=summary,
                key_moments=key_moments,
                metadata=metadata,
            )

        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")

    @classmethod
    def _generate_summary(
        cls,
        frames: List[ExtractedFrame],
        transcription: Optional[VideoTranscription],
        duration: float,
    ) -> str:
        """Generate a brief summary of the video content"""
        parts = [f"Video duration: {duration:.1f} seconds."]

        # Add frame-based summary
        descriptions = [f.description for f in frames if f.description]
        if descriptions:
            unique_descriptions = list(dict.fromkeys(descriptions))[:5]
            parts.append("Visual content shows: " + "; ".join(unique_descriptions))

        # Add transcription summary
        if transcription and transcription.full_text:
            text = transcription.full_text
            # Take first 500 chars as preview
            preview = text[:500] + "..." if len(text) > 500 else text
            parts.append(f"Audio contains: {preview}")

        return " ".join(parts)

    @classmethod
    def _identify_key_moments(
        cls,
        frames: List[ExtractedFrame],
        transcription: Optional[VideoTranscription],
    ) -> List[Dict[str, Any]]:
        """Identify key moments in the video"""
        moments = []

        # Add frame-based moments
        for frame in frames:
            if frame.description:
                moments.append(
                    {
                        "timestamp": frame.timestamp,
                        "type": "visual",
                        "description": frame.description,
                    }
                )

        # Add transcription-based moments
        if transcription and transcription.segments:
            for segment in transcription.segments:
                if segment.get("text", "").strip():
                    moments.append(
                        {
                            "timestamp": segment.get("start", 0),
                            "type": "audio",
                            "description": segment.get("text", "").strip()[:200],
                        }
                    )

        # Sort by timestamp and deduplicate
        moments.sort(key=lambda x: x["timestamp"])

        # Take most relevant moments
        return moments[:20]


# ============================================================
# PUBLIC API
# ============================================================


async def process_video(
    video_path: str,
    frame_interval: float = DEFAULT_FRAME_INTERVAL,
    max_frames: int = MAX_FRAMES,
    transcribe: bool = True,
    analyze_frames: bool = True,
    vision_provider: str = "anthropic",
) -> Dict[str, Any]:
    """
    Process a video file and extract frames + transcription.

    Args:
        video_path: Path to video file
        frame_interval: Seconds between frames
        max_frames: Maximum frames to extract
        transcribe: Whether to transcribe audio
        analyze_frames: Whether to analyze frames with vision
        vision_provider: Vision provider for frame analysis

    Returns:
        Video analysis results
    """
    analysis = await VideoProcessor.process_video(
        video_path,
        frame_interval=frame_interval,
        max_frames=max_frames,
        transcribe=transcribe,
        analyze_frames=analyze_frames,
        vision_provider=vision_provider,
    )
    return analysis.to_dict()


async def process_video_for_chat(
    video_path: str,
    frame_interval: float = 10,  # Larger interval for chat (less detail)
    max_frames: int = 10,
) -> Tuple[str, List[str]]:
    """
    Process a video for use in chat context.

    Returns:
        Tuple of (context_string, list_of_frame_base64_images)
    """
    analysis = await VideoProcessor.process_video(
        video_path,
        frame_interval=frame_interval,
        max_frames=max_frames,
        transcribe=True,
        analyze_frames=False,  # Skip expensive vision analysis
    )

    context = analysis.to_context_string()

    # Return first few frames for vision context
    frame_images = [f.base64_data for f in analysis.frames[:5] if f.base64_data]

    return context, frame_images


def get_video_context_for_llm(analysis: VideoAnalysis) -> str:
    """
    Convert video analysis to context string for LLM prompts.

    This is what NAVI injects into its prompts when videos are provided.
    """
    return analysis.to_context_string()


# Quick check function
def is_video_processing_available() -> Tuple[bool, str]:
    """Check if video processing is available"""
    if not check_ffmpeg_available():
        return False, "ffmpeg is not installed"
    if not check_ffprobe_available():
        return False, "ffprobe is not installed"
    return True, "Video processing is available"
