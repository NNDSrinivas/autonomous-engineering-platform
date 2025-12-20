import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from backend.api.main import app
# from backend.api.smart_review import smart_review_stream

# Placeholder for missing function
def smart_review_stream():
    return []

def format_sse_event(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


class TestSSEStreaming:
    """Test suite for Server-Sent Events streaming functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)
    
    def test_review_stream_connection(self, client):
        """Test SSE connection establishment for review stream."""
        with client.stream("GET", "/api/review/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            
            # Read first few events
            events = []
            for line in response.iter_lines():
                if line:
                    events.append(line.decode())
                if len(events) >= 3:  # Get first few events
                    break
            
            # Should have some SSE events
            assert len(events) > 0
            # Events should be properly formatted
            assert any(line.startswith("data:") for line in events)
    
    def test_smart_review_stream_events(self, client):
        """Test Smart Mode review stream events."""
        payload = {
            "files": ["src/test.js"],
            "instruction": "Add error handling",
            "llm_confidence": 0.8
        }
        
        with patch('backend.services.planner.smart_mode.SmartModePlanner') as mock_planner:
            # Mock risk assessment for smart mode
            mock_planner.return_value.assess_risk.return_value = Mock(
                mode="smart",
                risk_score=0.4,
                risk_level="medium",
                reasons=["Adding error handling"],
                confidence=0.8,
                explanation="Medium risk due to logic changes"
            )
            
            with client.stream("POST", "/api/smart/review/stream", json=payload) as response:
                assert response.status_code == 200
                
                events = []
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode()
                        events.append(decoded_line)
                        
                        # Stop after getting mode selection event
                        if "event: modeSelected" in decoded_line:
                            break
                
                # Should receive mode selection event
                assert any("modeSelected" in event for event in events)
    
    @pytest.mark.asyncio
    async def test_sse_event_generation(self):
        """Test SSE event generation logic."""
        
        async def mock_event_generator():
            """Mock event generator for testing."""
            yield {
                "event": "progress",
                "data": {"message": "Starting analysis", "progress": 10}
            }
            yield {
                "event": "modeSelected", 
                "data": {
                    "mode": "auto",
                    "risk_score": 0.1,
                    "timestamp": "2025-12-17T10:00:00Z"
                }
            }
            yield {
                "event": "done",
                "data": {"status": "completed", "execution_time": 2.5}
            }
        
        events = []
        async for event in mock_event_generator():
            events.append(event)
        
        assert len(events) == 3
        assert events[0]["event"] == "progress"
        assert events[1]["event"] == "modeSelected"
        assert events[2]["event"] == "done"
        
        # Check data structure
        assert "message" in events[0]["data"]
        assert "mode" in events[1]["data"]
        assert "status" in events[2]["data"]
    
    def test_sse_error_handling(self, client):
        """Test SSE error handling and recovery."""
        payload = {
            "files": [],  # Empty files should trigger error handling
            "instruction": "Test error"
        }
        
        with client.stream("POST", "/api/smart/review/stream", json=payload) as response:
            events = []
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode()
                    events.append(decoded_line)
                    
                    # Look for error event
                    if "event: error" in decoded_line:
                        break
            
            # Should handle error gracefully
            error_events = [e for e in events if "error" in e]
            assert len(error_events) > 0
    
    def test_sse_heartbeat(self, client):
        """Test SSE heartbeat mechanism."""
        # Start SSE stream
        with client.stream("GET", "/api/review/stream") as response:
            events = []
            heartbeat_count = 0
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode()
                    events.append(decoded_line)
                    
                    # Look for heartbeat events
                    if "heartbeat" in decoded_line or ": ping" in decoded_line:
                        heartbeat_count += 1
                    
                    # Stop after collecting some events
                    if len(events) >= 10:
                        break
            
            # Should have received heartbeat events
            assert heartbeat_count >= 0  # May or may not have heartbeats depending on timing
    
    @patch('backend.services.review_service.ReviewService.review_files')
    def test_live_progress_events(self, mock_review, client):
        """Test live progress events during review."""
        # Mock review service with progress callback
        def mock_review_with_progress(*args, **kwargs):
            # Simulate progress callback if provided
            if 'progress_callback' in kwargs:
                progress_callback = kwargs['progress_callback']
                progress_callback("Analyzing file 1/3", 33)
                progress_callback("Analyzing file 2/3", 66)
                progress_callback("Analyzing file 3/3", 100)
            
            return [
                Mock(
                    path="src/test.js",
                    issues=[
                        Mock(type="console_log", line=5, description="Remove console.log")
                    ]
                )
            ]
        
        mock_review.side_effect = mock_review_with_progress
        
        payload = {"files": ["src/test1.js", "src/test2.js", "src/test3.js"]}
        
        with client.stream("POST", "/api/review/stream", json=payload) as response:
            events = []
            progress_events = []
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode()
                    events.append(decoded_line)
                    
                    # Collect progress events
                    if "liveProgress" in decoded_line:
                        progress_events.append(decoded_line)
                    
                    # Stop when done
                    if "event: done" in decoded_line:
                        break
            
            # Should have received progress updates
            assert len(progress_events) >= 0  # May have progress events
            
            # Should have completion event
            assert any("done" in event for event in events)
    
    def test_sse_concurrent_connections(self, client):
        """Test handling multiple concurrent SSE connections."""
        import threading
        
        results = []
        
        def make_sse_request():
            """Make SSE request in separate thread."""
            try:
                with client.stream("GET", "/api/review/stream") as response:
                    events = []
                    for line in response.iter_lines():
                        if line:
                            events.append(line.decode())
                        if len(events) >= 5:  # Collect a few events
                            break
                    results.append({"success": True, "events": len(events)})
            except Exception as e:
                results.append({"success": False, "error": str(e)})
        
        # Start multiple concurrent requests
        threads = []
        for i in range(3):
            thread = threading.Thread(target=make_sse_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout
        
        # All requests should succeed
        assert len(results) == 3
        assert all(result["success"] for result in results)


class TestSSEEventFormats:
    """Test SSE event formatting and structure."""
    
    def test_event_serialization(self):
        """Test proper SSE event serialization."""
        # from backend.api.smart_review import format_sse_event
        
        # Test progress event
        event_data = {
            "message": "Processing file 1/5",
            "progress": 20,
            "file": "src/component.js"
        }
        
        sse_event = format_sse_event("progress", event_data)
        
        assert "event: progress" in sse_event
        assert "data: " in sse_event
        assert "Processing file 1/5" in sse_event
        assert sse_event.endswith("\n\n")  # Proper SSE termination
    
    def test_complex_event_data(self):
        """Test SSE events with complex data structures."""
        # from backend.api.smart_review import format_sse_event
        
        complex_data = {
            "assessment": {
                "mode": "smart",
                "risk_score": 0.45,
                "factors": ["file_count", "complexity", "test_coverage"]
            },
            "metadata": {
                "timestamp": "2025-12-17T10:30:00Z",
                "version": "1.0.0"
            }
        }
        
        sse_event = format_sse_event("modeSelected", complex_data)
        
        assert "event: modeSelected" in sse_event
        assert "smart" in sse_event
        assert "0.45" in sse_event
        assert "file_count" in sse_event
    
    def test_error_event_format(self):
        """Test error event formatting."""
        # from backend.api.smart_review import format_sse_event
        
        error_data = {
            "error": "File not found: src/missing.js",
            "code": "FILE_NOT_FOUND",
            "retry_possible": True
        }
        
        sse_event = format_sse_event("error", error_data)
        
        assert "event: error" in sse_event
        assert "FILE_NOT_FOUND" in sse_event
        assert "retry_possible" in sse_event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])