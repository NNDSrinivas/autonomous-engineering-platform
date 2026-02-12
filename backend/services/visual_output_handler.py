"""
Visual Output Handler for NAVI Autonomous Agent

Handles post-processing of visual outputs (animations, videos, images):
- Detects frame sequences from command outputs
- Compiles frames into videos/GIFs
- Opens/displays visual results for users
- Provides clear feedback about generated outputs
"""

import os
import re
import glob
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class VisualOutputHandler:
    """Handles detection and processing of visual outputs from agent tasks."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def detect_frame_sequence(self, output: str, created_files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Detect if the output indicates frame generation for animation.

        Returns dict with frame info if detected, None otherwise.
        """
        # Pattern 1: "Frame saved" messages
        frame_saved_pattern = r"Frame\s+(?:saved|written|created)"
        if re.search(frame_saved_pattern, output, re.IGNORECASE):
            # Look for image files in created files or workspace
            image_patterns = ["*.png", "*.jpg", "*.jpeg", "*.bmp"]
            frames = []

            for pattern in image_patterns:
                frames.extend(glob.glob(os.path.join(self.workspace_path, pattern)))
                frames.extend(glob.glob(os.path.join(self.workspace_path, "**", pattern), recursive=True))

            if len(frames) > 3:  # Need at least a few frames for animation
                return {
                    "type": "frame_sequence",
                    "frames": sorted(frames),
                    "count": len(frames),
                    "detected_from": "frame_saved_messages"
                }

        # Pattern 2: Numbered frame files (frame_001.png, etc.)
        numbered_frames = glob.glob(os.path.join(self.workspace_path, "**/frame_*.png"), recursive=True)
        numbered_frames.extend(glob.glob(os.path.join(self.workspace_path, "**/frame*.png"), recursive=True))

        if len(numbered_frames) > 3:
            return {
                "type": "frame_sequence",
                "frames": sorted(numbered_frames),
                "count": len(numbered_frames),
                "detected_from": "numbered_frame_files"
            }

        # Pattern 3: Canvas/animation keywords in output
        animation_keywords = ["animation", "canvas", "frames", "video", "render"]
        if any(keyword in output.lower() for keyword in animation_keywords):
            # Check for any image files created
            image_files = []
            for ext in [".png", ".jpg", ".jpeg", ".gif"]:
                image_files.extend([f for f in created_files if f.endswith(ext)])

            if len(image_files) > 3:
                return {
                    "type": "frame_sequence",
                    "frames": [os.path.join(self.workspace_path, f) for f in image_files],
                    "count": len(image_files),
                    "detected_from": "animation_keywords"
                }

        return None

    async def compile_to_video(self, frames: List[str], output_path: str, fps: int = 30) -> Dict[str, Any]:
        """
        Compile image frames into a video using ffmpeg.

        Args:
            frames: List of frame file paths
            output_path: Path for output video
            fps: Frames per second

        Returns:
            Dict with success status and output path
        """
        try:
            # Check if ffmpeg is available
            result = subprocess.run(
                ["which", "ffmpeg"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.warning("ffmpeg not found, falling back to GIF")
                return await self.compile_to_gif(frames, output_path.replace(".mp4", ".gif"))

            # Create a temporary file list for ffmpeg
            list_file = os.path.join(os.path.dirname(output_path), "frame_list.txt")
            with open(list_file, "w") as f:
                for frame in sorted(frames):
                    # Use relative paths if possible
                    f.write(f"file '{os.path.abspath(frame)}'\n")

            # Run ffmpeg to create video
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-r", str(fps),
                "-pix_fmt", "yuv420p",
                "-y",  # Overwrite output
                output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Clean up temp file
            if os.path.exists(list_file):
                os.remove(list_file)

            if result.returncode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": "video/mp4",
                    "size_mb": round(size_mb, 2),
                    "fps": fps,
                    "frame_count": len(frames)
                }
            else:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr[:500]
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Video compilation timed out after 60s"
            }
        except Exception as e:
            logger.error(f"Error compiling video: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def compile_to_gif(self, frames: List[str], output_path: str, fps: int = 10) -> Dict[str, Any]:
        """
        Compile frames into animated GIF (fallback if ffmpeg not available).
        """
        try:
            # Try using ImageMagick convert
            cmd = [
                "convert",
                "-delay", str(int(100/fps)),  # Delay in 1/100ths of a second
                "-loop", "0",  # Infinite loop
            ] + sorted(frames) + [output_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": "image/gif",
                    "size_mb": round(size_mb, 2),
                    "fps": fps,
                    "frame_count": len(frames)
                }
            else:
                return {
                    "success": False,
                    "error": "GIF compilation failed (ImageMagick not available?)"
                }

        except Exception as e:
            logger.error(f"Error compiling GIF: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def open_file(self, file_path: str) -> Dict[str, Any]:
        """
        Open a file with the default system application.

        Args:
            file_path: Path to file to open

        Returns:
            Dict with success status
        """
        try:
            # Use 'open' on macOS, 'xdg-open' on Linux, 'start' on Windows
            if os.path.exists("/usr/bin/open"):  # macOS
                cmd = ["open", file_path]
            elif os.path.exists("/usr/bin/xdg-open"):  # Linux
                cmd = ["xdg-open", file_path]
            else:  # Windows or fallback
                logger.warning("Cannot determine how to open files on this system")
                return {
                    "success": False,
                    "error": "File opening not supported on this system"
                }

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            return {
                "success": result.returncode == 0,
                "opened": file_path,
                "error": result.stderr if result.returncode != 0 else None
            }

        except Exception as e:
            logger.error(f"Error opening file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def process_visual_output(
        self,
        output: str,
        created_files: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Main entry point: detect and process visual outputs.

        Args:
            output: Command/tool output text
            created_files: List of files created during execution

        Returns:
            Dict with processing results, or None if no visual output detected
        """
        # Detect frame sequence
        frame_info = self.detect_frame_sequence(output, created_files)

        if not frame_info:
            return None

        logger.info(f"[VisualOutputHandler] Detected {frame_info['count']} frames")

        # Compile to video/GIF
        output_name = "animation_output.mp4"
        output_path = os.path.join(self.workspace_path, output_name)

        compilation_result = await self.compile_to_video(
            frame_info["frames"],
            output_path
        )

        if not compilation_result["success"]:
            # Try GIF as fallback
            output_name = "animation_output.gif"
            output_path = os.path.join(self.workspace_path, output_name)
            compilation_result = await self.compile_to_gif(
                frame_info["frames"],
                output_path
            )

        if compilation_result["success"]:
            # Try to open the file
            open_result = await self.open_file(output_path)

            return {
                "detected": True,
                "frame_count": frame_info["count"],
                "compiled": True,
                "output_file": output_path,
                "format": compilation_result["format"],
                "size_mb": compilation_result["size_mb"],
                "opened": open_result.get("success", False),
                "message": self._generate_success_message(compilation_result, open_result)
            }
        else:
            return {
                "detected": True,
                "frame_count": frame_info["count"],
                "compiled": False,
                "error": compilation_result.get("error"),
                "message": f"Detected {frame_info['count']} frames but failed to compile animation: {compilation_result.get('error')}"
            }

    def _generate_success_message(self, compilation: Dict[str, Any], open_result: Dict[str, Any]) -> str:
        """Generate a user-friendly success message."""
        format_name = "video" if "mp4" in compilation["format"] else "animated GIF"

        msg = f"✅ Created {format_name} from {compilation['frame_count']} frames\n"
        msg += f"📁 Output: {compilation['output_path']}\n"
        msg += f"📊 Size: {compilation['size_mb']} MB\n"

        if open_result.get("success"):
            msg += "🎬 Animation opened in default viewer"
        else:
            msg += "⚠️ Animation created but could not be opened automatically. Please open the file manually."

        return msg
