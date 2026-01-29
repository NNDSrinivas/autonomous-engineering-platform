"""
Media Processing API Router

Handles video processing and other media operations for NAVI.
"""

import os
import tempfile
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
import structlog

from backend.services.video_processor_service import (
    process_video_for_chat,
    is_video_processing_available,
    SUPPORTED_VIDEO_FORMATS,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================


class VideoProcessRequest(BaseModel):
    """Request to process a video file"""

    video_path: str = Field(..., description="Path to video file on disk")
    frame_interval: float = Field(default=5.0, description="Seconds between frames")
    max_frames: int = Field(default=20, description="Maximum frames to extract")
    transcribe: bool = Field(default=True, description="Whether to transcribe audio")
    analyze_frames: bool = Field(
        default=True, description="Whether to analyze frames with vision"
    )
    vision_provider: str = Field(default="anthropic", description="Vision provider")


class VideoProcessResponse(BaseModel):
    """Response from video processing"""

    success: bool
    duration: float
    frame_count: int
    has_transcription: bool
    summary: str
    context_string: str  # For injection into LLM prompts
    analysis: dict  # Full analysis data


class VideoChatRequest(BaseModel):
    """Request to process video for chat context"""

    video_path: str
    frame_interval: float = 10.0
    max_frames: int = 10


class VideoChatResponse(BaseModel):
    """Response with video context for chat"""

    success: bool
    context: str  # Text context for LLM
    frame_images: list[str]  # Base64-encoded frames for vision
    error: Optional[str] = None


class VideoCapabilityResponse(BaseModel):
    """Response for video capability check"""

    available: bool
    message: str
    supported_formats: list[str]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/video/capabilities")
async def check_video_capabilities() -> VideoCapabilityResponse:
    """Check if video processing is available"""
    available, message = is_video_processing_available()
    return VideoCapabilityResponse(
        available=available,
        message=message,
        supported_formats=list(SUPPORTED_VIDEO_FORMATS),
    )


@router.post("/video/process")
async def process_video_endpoint(request: VideoProcessRequest) -> VideoProcessResponse:
    """
    Process a video file and extract frames + transcription.

    This is the full processing endpoint that extracts frames,
    transcribes audio, and optionally analyzes frames with vision.
    """
    try:
        # Check if video processing is available
        available, msg = is_video_processing_available()
        if not available:
            raise HTTPException(status_code=503, detail=msg)

        # Check if file exists
        if not os.path.exists(request.video_path):
            raise HTTPException(
                status_code=404, detail=f"Video file not found: {request.video_path}"
            )

        # Process video
        from backend.services.video_processor_service import VideoProcessor

        analysis = await VideoProcessor.process_video(
            video_path=request.video_path,
            frame_interval=request.frame_interval,
            max_frames=request.max_frames,
            transcribe=request.transcribe,
            analyze_frames=request.analyze_frames,
            vision_provider=request.vision_provider,
        )

        return VideoProcessResponse(
            success=True,
            duration=analysis.duration,
            frame_count=analysis.frame_count,
            has_transcription=analysis.transcription is not None,
            summary=analysis.summary,
            context_string=analysis.to_context_string(),
            analysis=analysis.to_dict(),
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Video processing failed: {str(e)}"
        )


@router.post("/video/process-for-chat")
async def process_video_for_chat_endpoint(
    request: VideoChatRequest,
) -> VideoChatResponse:
    """
    Process a video for use in chat context.

    This is a lighter-weight endpoint that extracts frames and
    transcription without expensive vision analysis, suitable for
    injecting video context into chat.
    """
    try:
        available, msg = is_video_processing_available()
        if not available:
            return VideoChatResponse(
                success=False,
                context="",
                frame_images=[],
                error=msg,
            )

        if not os.path.exists(request.video_path):
            return VideoChatResponse(
                success=False,
                context="",
                frame_images=[],
                error=f"Video file not found: {request.video_path}",
            )

        context, frame_images = await process_video_for_chat(
            video_path=request.video_path,
            frame_interval=request.frame_interval,
            max_frames=request.max_frames,
        )

        return VideoChatResponse(
            success=True,
            context=context,
            frame_images=frame_images,
        )

    except Exception as e:
        logger.error(f"Video chat processing error: {e}")
        return VideoChatResponse(
            success=False,
            context="",
            frame_images=[],
            error=str(e),
        )


@router.post("/video/upload-and-process")
async def upload_and_process_video(
    file: UploadFile = File(...),
    frame_interval: float = Form(default=5.0),
    max_frames: int = Form(default=20),
    transcribe: bool = Form(default=True),
) -> VideoProcessResponse:
    """
    Upload a video file and process it.

    This endpoint accepts video uploads directly rather than
    requiring a file path on disk.
    """
    try:
        available, msg = is_video_processing_available()
        if not available:
            raise HTTPException(status_code=503, detail=msg)

        # Validate file type
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in SUPPORTED_VIDEO_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported video format: {ext}. Supported: {SUPPORTED_VIDEO_FORMATS}",
            )

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Process the uploaded video
            from backend.services.video_processor_service import VideoProcessor

            analysis = await VideoProcessor.process_video(
                video_path=temp_path,
                frame_interval=frame_interval,
                max_frames=max_frames,
                transcribe=transcribe,
                analyze_frames=False,  # Skip expensive vision for uploads
            )

            return VideoProcessResponse(
                success=True,
                duration=analysis.duration,
                frame_count=analysis.frame_count,
                has_transcription=analysis.transcription is not None,
                summary=analysis.summary,
                context_string=analysis.to_context_string(),
                analysis=analysis.to_dict(),
            )

        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video upload processing error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Video processing failed: {str(e)}"
        )
