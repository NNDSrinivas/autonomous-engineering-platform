"""
Agent Proposal API for VS Code Extension

Generates execution plans and step-by-step workflows from Jira issues.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.database.session import get_db
from sqlalchemy.orm import Session
from backend.api.routers.oauth_device import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Planning"])


class ProposedStep(BaseModel):
    id: str = Field(description="Unique step identifier")
    kind: str = Field(description="Step type: edit, run, or open")
    title: str = Field(description="Step title/summary")
    details: Optional[str] = Field(
        default=None, description="Detailed step description"
    )
    patch: Optional[str] = Field(
        default=None, description="Code diff/patch for edit steps"
    )
    command: Optional[str] = Field(
        default=None, description="Command to execute for run steps"
    )
    files: Optional[List[str]] = Field(
        default=None, description="Files affected by this step"
    )
    estimated_time: Optional[int] = Field(
        default=None, description="Estimated time in minutes"
    )


class ProposeRequest(BaseModel):
    issue_key: str = Field(description="Jira issue key to generate plan for")
    context: Optional[Dict[str, Any]] = Field(description="Additional context")


class ProposeResponse(BaseModel):
    issue_key: str = Field(description="Source Jira issue")
    plan_id: str = Field(description="Generated plan identifier")
    steps: List[ProposedStep] = Field(description="Proposed execution steps")
    summary: str = Field(description="Plan summary")
    estimated_total_time: Optional[int] = Field(
        description="Total estimated time in minutes"
    )


@router.post("/propose", response_model=List[ProposedStep])
async def propose_plan(
    request: ProposeRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Generate a step-by-step execution plan for a Jira issue.

    This endpoint analyzes the Jira issue and generates a concrete plan
    that can be executed step-by-step with user approval.
    """
    try:
        # Validate user authentication
        await get_current_user(authorization)

        issue_key = request.issue_key

        # For MVP, generate mock plans based on issue key
        if issue_key == "AEP-123":
            return [
                ProposedStep(
                    id="step-1",
                    kind="edit",
                    title="Add OAuth device flow types",
                    details="Create TypeScript interfaces for device code flow",
                    patch="""--- a/src/api/types.ts
+++ b/src/api/types.ts
@@ -1,2 +1,8 @@
 export type JiraIssue = { id: string; key: string; summary: string; status: string; url?: string };
 export type ProposedStep = { id: string; kind: 'edit'|'run'|'open'; title: string; details?: string; patch?: string };
+export type DeviceCodeStart = { 
+  device_code: string; 
+  user_code: string; 
+  verification_uri: string; 
+  verification_uri_complete?: string; 
+  interval: number 
+};""",
                    files=["src/api/types.ts"],
                    estimated_time=5,
                ),
                ProposedStep(
                    id="step-2",
                    kind="edit",
                    title="Implement authentication manager",
                    details="Create device code authentication flow in AuthManager",
                    patch="""--- a/src/auth/AuthManager.ts
+++ b/src/auth/AuthManager.ts
@@ -10,4 +10,20 @@ export class AuthManager {
   async authenticate(): Promise<boolean> {
-    // TODO: Implement OAuth flow
-    return false;
+    try {
+      const deviceFlow = await this.apiClient.startDeviceCode();
+      await vscode.env.openExternal(vscode.Uri.parse(deviceFlow.verification_uri));
+      
+      // Poll for completion
+      const token = await this.pollForToken(deviceFlow.device_code);
+      await this.storeToken(token);
+      return true;
+    } catch (error) {
+      vscode.window.showErrorMessage(`Authentication failed: ${error.message}`);
+      return false;
+    }
   }""",
                    files=["src/auth/AuthManager.ts"],
                    estimated_time=15,
                ),
                ProposedStep(
                    id="step-3",
                    kind="run",
                    title="Test OAuth flow",
                    details="Run extension and test device code authentication",
                    command="npm run compile && code --extensionDevelopmentPath=. --new-window",
                    estimated_time=10,
                ),
                ProposedStep(
                    id="step-4",
                    kind="edit",
                    title="Add error handling",
                    details="Implement robust error handling for authentication failures",
                    patch="""--- a/src/auth/AuthManager.ts
+++ b/src/auth/AuthManager.ts
@@ -25,0 +25,15 @@ export class AuthManager {
+  
+  private async handleAuthError(error: any): Promise<void> {
+    if (error.code === 'access_denied') {
+      vscode.window.showWarningMessage('Authentication was denied');
+    } else if (error.code === 'expired_token') {
+      vscode.window.showErrorMessage('Authentication timed out. Please try again.');
+    } else {
+      vscode.window.showErrorMessage(`Authentication failed: ${error.message}`);
+    }
+    
+    // Clear any stored partial state
+    await this.clearTokenStorage();
+  }""",
                    files=["src/auth/AuthManager.ts"],
                    estimated_time=8,
                ),
            ]

        elif issue_key == "AEP-124":
            return [
                ProposedStep(
                    id="step-1",
                    kind="edit",
                    title="Add morning brief types",
                    details="Define TypeScript interfaces for morning briefing data",
                    patch="""--- a/src/api/types.ts
+++ b/src/api/types.ts
@@ -4,0 +4,12 @@ export type DeviceCodeToken = { access_token: string; expires_in: number };
+export type MorningBriefData = {
+  greeting: string;
+  jiraTasks: JiraIssue[];
+  teamActivity: TeamActivity[];
+  suggestions: SmartSuggestion[];
+  meetings: UpcomingMeeting[];
+};
+
+export type TeamActivity = { user: string; action: string; timestamp: string; url?: string };
+export type SmartSuggestion = { id: string; title: string; description: string; priority: 'low'|'medium'|'high' };
+export type UpcomingMeeting = { title: string; time: string; attendees: string[]; url?: string };""",
                    files=["src/api/types.ts"],
                    estimated_time=5,
                ),
                ProposedStep(
                    id="step-2",
                    kind="edit",
                    title="Enhance agent panel UI",
                    details="Add enterprise intelligence widgets to morning briefing",
                    patch="""--- a/src/features/chatSidebar.ts
+++ b/src/features/chatSidebar.ts
@@ -30,5 +30,25 @@ export class ChatSidebarProvider implements vscode.WebviewViewProvider {
         <ul class="issues">
           ${issues.map(i=>`<li data-key="${i.key}"><b>${i.key}</b> – ${i.summary} <span class="st">${i.status}</span></li>`).join('')}
         </ul>
+        
+        <div class="team-activity">
+          <h3>Team Activity</h3>
+          <ul class="activity-feed">
+            <li><strong>Alice</strong> commented on AEP-120 <span class="time">2h ago</span></li>
+            <li><strong>Bob</strong> merged PR #45 <span class="time">4h ago</span></li>
+            <li><strong>Carol</strong> created AEP-126 <span class="time">6h ago</span></li>
+          </ul>
+        </div>
+        
+        <div class="suggestions">
+          <h3>Smart Suggestions</h3>
+          <div class="suggestion-card priority-high">
+            <strong>Review pending PRs</strong>
+            <p>You have 3 PRs waiting for review</p>
+          </div>
+          <div class="suggestion-card priority-medium">
+            <strong>Update documentation</strong>
+            <p>API changes need documentation updates</p>
+          </div>
+        </div>""",
                    files=["src/features/chatSidebar.ts"],
                    estimated_time=20,
                ),
                ProposedStep(
                    id="step-3",
                    kind="run",
                    title="Test enhanced briefing",
                    details="Verify new morning briefing features work correctly",
                    command="npm run compile && code --extensionDevelopmentPath=.",
                    estimated_time=10,
                ),
            ]

        else:
            # Generic plan for unknown issues
            return [
                ProposedStep(
                    id="step-1",
                    kind="open",
                    title="Analyze issue requirements",
                    details=f"Review and understand requirements for {issue_key}",
                    estimated_time=10,
                ),
                ProposedStep(
                    id="step-2",
                    kind="edit",
                    title="Implement solution",
                    details="Create initial implementation based on issue analysis",
                    patch="// TODO: Generate specific implementation",
                    estimated_time=30,
                ),
                ProposedStep(
                    id="step-3",
                    kind="run",
                    title="Test implementation",
                    details="Run tests and verify solution works correctly",
                    command="npm test",
                    estimated_time=15,
                ),
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to propose plan for {request.issue_key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate plan: {str(e)}"
        )


@router.get("/plans/{plan_id}", response_model=ProposeResponse)
async def get_plan(
    plan_id: str, authorization: str = Header(None), db: Session = Depends(get_db)
):
    """
    Get details of a previously generated plan.
    """
    try:
        await get_current_user(authorization)

        # For MVP, return mock plan data
        # In production, retrieve from database
        raise HTTPException(status_code=404, detail="Plan not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {str(e)}")
