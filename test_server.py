#!/usr/bin/env python3
"""
Simple test server to verify connectors marketplace functionality
"""

import os
import sys
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

# Set up logging to see all requests
logging.basicConfig(level=logging.INFO)

# Import our connector schemas and services
from backend.schemas.connectors import ConnectorStatus, JiraConnectorRequest, SlackConnectorRequest, ConnectorConnectResponse
from backend.services.connectors import get_connector_status_for_user, save_jira_connection, save_slack_connection

app = FastAPI(title="Test Connectors Server")

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"🔍 Request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"📤 Response: {response.status_code}")
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

# NAVI endpoints that the extension expects
@app.get("/api/navi/chat")
async def navi_chat():
    return {"status": "navi_endpoint_available", "message": "Chat endpoint placeholder"}

@app.post("/api/navi/chat") 
async def navi_chat_post():
    return {"response": "Test response from NAVI chat"}

@app.get("/api/navi/jira-tasks")
async def navi_jira_tasks():
    return {"tasks": [{"key": "TEST-1", "summary": "Sample Jira task"}]}

@app.get("/api/navi/task-brief")
async def navi_task_brief():
    return {"brief": "Task brief placeholder"}

# Additional endpoints that might be needed
@app.get("/api/navi/search")
async def navi_search():
    return {"results": []}

@app.post("/api/navi/search") 
async def navi_search_post():
    return {"results": []}

@app.get("/api/connectors/marketplace/status", response_model=List[ConnectorStatus])
async def get_marketplace_status(user_id: Optional[str] = None):
    """Get connector status for the marketplace UI."""
    # For testing, use a default user if none provided
    if not user_id:
        user_id = "test_user"
    
    return get_connector_status_for_user(user_id)

@app.post("/api/connectors/jira/connect", response_model=ConnectorConnectResponse)
async def connect_jira(request: JiraConnectorRequest, user_id: Optional[str] = None):
    """Connect to Jira for the specified user."""
    # For testing, use a default user if none provided
    if not user_id:
        user_id = "test_user"
    
    # Extract fields from request and save connection
    save_jira_connection(user_id, str(request.base_url), request.email, request.api_token)
    
    # Return success response
    return ConnectorConnectResponse(ok=True, connector_id="jira")

@app.post("/api/connectors/slack/connect", response_model=ConnectorConnectResponse)
async def connect_slack(request: SlackConnectorRequest, user_id: Optional[str] = None):
    """Connect to Slack for the specified user."""
    # For testing, use a default user if none provided
    if not user_id:
        user_id = "test_user"
    
    # Extract fields from request and save connection
    save_slack_connection(user_id, request.bot_token)
    
    # Return success response
    return ConnectorConnectResponse(ok=True, connector_id="slack")

@app.get("/api/autonomous/coding")
async def autonomous_coding():
    return {"status": "available"}

# Catch-all for any other /api requests (MUST BE LAST)
@app.api_route("/api/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_api(full_path: str):
    print(f"🚨 Unhandled API request: /api/{full_path}")
    return {"message": f"Endpoint /api/{full_path} available in test mode", "status": "ok"}

if __name__ == "__main__":
    print("🚀 Starting test connectors server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)