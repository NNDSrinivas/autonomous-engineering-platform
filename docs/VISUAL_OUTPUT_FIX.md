# Visual Output Handler - NAVI Agent Improvement

## Problem

NAVI's autonomous agent generates visual outputs (animation frames, images) but fails to:
1. Compile frames into videos/GIFs
2. Display the results to users
3. Provide clear feedback about what was created

## Solution

Added `VisualOutputHandler` service that:
- **Detects** frame sequences from command outputs and file creation
- **Compiles** frames into videos (MP4) or animated GIFs
- **Opens** the output file in the default viewer
- **Reports** clear success messages with file paths and sizes

## Files Created

### 1. `/backend/services/visual_output_handler.py`
New service module that handles all visual output post-processing.

**Key Features:**
- `detect_frame_sequence()` - Detects when frames/animations are created
- `compile_to_video()` - Uses ffmpeg to create MP4 videos
- `compile_to_gif()` - Fallback to animated GIF if ffmpeg unavailable
- `open_file()` - Opens output in system default viewer
- `process_visual_output()` - Main entry point for post-processing

## Integration Points

### Option A: Automatic Post-Processing (Recommended)

Add to `autonomous_agent.py` after `run_command` tool execution:

```python
# After command execution completes successfully
if result.get("success"):
    try:
        from backend.services.visual_output_handler import VisualOutputHandler

        visual_handler = VisualOutputHandler(self.workspace_path)
        visual_result = await visual_handler.process_visual_output(
            output=result.get("output", ""),
            created_files=context.files_created
        )

        if visual_result and visual_result.get("compiled"):
            # Enhance the result with visual output info
            result["visual_output"] = visual_result
            result["output"] = f"{result.get('output', '')}\\n\\n{visual_result['message']}"
            logger.info(f"[AutonomousAgent] ✅ Processed visual output: {visual_result['output_file']}")
    except Exception as e:
        logger.warning(f"Visual output processing failed (non-critical): {e}")
```

**Where to add this:**
- In `_execute_tool()` method
- After `run_command` tool completes
- Before returning the result

### Option B: Manual Tool

Add a new tool `compile_animation` that users can explicitly call:

```python
elif tool_name == "compile_animation":
    from backend.services.visual_output_handler import VisualOutputHandler

    handler = VisualOutputHandler(self.workspace_path)
    visual_result = await handler.process_visual_output(
        output="",
        created_files=context.files_created
    )

    if visual_result:
        return visual_result
    else:
        return {
            "success": False,
            "error": "No animation frames detected"
        }
```

## Dependencies

**Required:**
- Python 3.8+
- `Pillow` - Python library for GIF creation (automatically installed via pip)

**Optional (for enhanced functionality):**
- `ffmpeg` - For MP4 video compilation (falls back to GIF if not available)

**Install Python dependencies:**
```bash
pip install Pillow>=10.0.0
# Already included in requirements.txt
```

**Optional - Install ffmpeg for MP4 support:**
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg

# Not required - system will automatically use GIF if ffmpeg is missing
```

## Example Usage

### Before Fix:
```
User: "Create a futuristic animation"
NAVI: "Created frames: frame_001.png, frame_002.png, ..."
```
**Issues:** No video, no display, no clear output

### After Fix:
```
User: "Create a futuristic animation"
NAVI: "Created frames: frame_001.png, frame_002.png, ...

✅ Created video from 30 frames
📁 Output: /path/to/animation_output.mp4
📊 Size: 2.5 MB
🎬 Animation opened in default viewer"
```
**Result:** Video created, displayed, clear feedback!

## Testing

Test the fix with animation generation:

```bash
# 1. Test frame detection
python -c "
from backend.services.visual_output_handler import VisualOutputHandler
handler = VisualOutputHandler('/path/to/workspace')
result = handler.detect_frame_sequence('Frame saved', [])
print(result)
"

# 2. Test video compilation (requires frames)
# Create test frames first, then:
python -c "
import asyncio
from backend.services.visual_output_handler import VisualOutputHandler

async def test():
    handler = VisualOutputHandler('/path/to/workspace')
    result = await handler.compile_to_video(
        frames=['/path/frame_001.png', '/path/frame_002.png'],
        output_path='/path/test_output.mp4'
    )
    print(result)

asyncio.run(test())
"
```

## Limitations & Future Improvements

**Current Limitations:**
1. Requires `ffmpeg` or `ImageMagick` installed
2. Only detects common frame naming patterns
3. Fixed FPS settings (30fps for video, 10fps for GIF)

**Future Improvements:**
1. Add configurable FPS settings
2. Support more frame naming patterns
3. Add frame extraction from video
4. Support HTML5 canvas animation export
5. Add preview thumbnails in NAVI UI
6. Integrate with VSCode webview for inline preview

## Commit & Deployment

```bash
# Add the new file
git add backend/services/visual_output_handler.py

# Integration changes (after adding to autonomous_agent.py)
git add backend/services/autonomous_agent.py

# Commit
git commit -m "feat: Add visual output handler for animation compilation

- Detect frame sequences from command outputs
- Compile frames into videos/GIFs
- Auto-open results in default viewer
- Provide clear feedback about generated outputs

Fixes NAVI failing to show animation videos to users"

# Push
git push origin your-branch
```

## Rollback Plan

If issues occur:
```bash
# Remove the integration from autonomous_agent.py
# The module is standalone and won't affect existing functionality
# Remove the file:
rm backend/services/visual_output_handler.py
```

---

**Status:** ✅ Module created, ready for integration
**Next Step:** Add integration code to `autonomous_agent.py`
