# 🎨 Frontend Integration Guide: NAVI Consent Mechanism

## Quick Start for Frontend Developers

### What You Need to Know

NAVI's self-healing engine can now handle ALL error types automatically, but some operations require user consent. Your job is to:
1. Display consent warnings to users
2. Collect yes/no responses
3. Pass the consent callback to NAVI
4. Handle awaiting-consent states

---

## 🔌 Integration Points

### Option 1: Real-Time Consent via Callback (Recommended)

**Backend Call:**
```python
async def get_user_consent_via_websocket(warning: str) -> bool:
    """Send consent request to frontend and wait for response"""
    consent_id = str(uuid.uuid4())
    
    # Send to frontend via WebSocket/SSE
    await send_to_frontend({
        "type": "consent_required",
        "consent_id": consent_id,
        "warning": warning,
        "timestamp": datetime.now().isoformat()
    })
    
    # Wait for user response (with timeout)
    response = await wait_for_consent_response(consent_id, timeout=300)  # 5 min
    return response == "yes"

# Use in NAVI execution
result = await brain.execute_action_with_recovery(
    action=action,
    context=context,
    consent_callback=get_user_consent_via_websocket,
)
```

**Frontend Handler (React/TypeScript example):**
```typescript
interface ConsentRequest {
    type: 'consent_required';
    consent_id: string;
    warning: string;
    timestamp: string;
}

// Listen for consent requests
useEffect(() => {
    const handleSSE = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'consent_required') {
            showConsentModal(data);
        }
    };
    
    eventSource.addEventListener('message', handleSSE);
    return () => eventSource.removeEventListener('message', handleSSE);
}, []);

// Show consent modal
function showConsentModal(request: ConsentRequest) {
    setConsentRequest(request);
    setShowModal(true);
}

// Handle user response
async function handleConsentResponse(consentId: string, approved: boolean) {
    await fetch(`/api/navi/consent/${consentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consent: approved })
    });
    setShowModal(false);
}
```

**Modal Component:**
```typescript
function ConsentModal({ request, onResponse }: ConsentModalProps) {
    const [userConfirmation, setUserConfirmation] = useState('');
    
    const isDangerous = request.warning.includes('🚨 CRITICAL');
    
    return (
        <Modal>
            <ModalHeader className={isDangerous ? 'critical' : 'warning'}>
                ⚠️ NAVI Requires Your Consent
            </ModalHeader>
            
            <ModalBody>
                <pre className="warning-message">{request.warning}</pre>
                
                {isDangerous && (
                    <Input
                        placeholder="Type 'yes' to confirm"
                        value={userConfirmation}
                        onChange={(e) => setUserConfirmation(e.target.value)}
                    />
                )}
            </ModalBody>
            
            <ModalFooter>
                {isDangerous ? (
                    <>
                        <Button
                            variant="danger"
                            disabled={userConfirmation.toLowerCase() !== 'yes'}
                            onClick={() => onResponse(request.consent_id, true)}
                        >
                            Proceed (Dangerous)
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={() => onResponse(request.consent_id, false)}
                        >
                            I'll Handle Manually
                        </Button>
                    </>
                ) : (
                    <>
                        <Button
                            variant="primary"
                            onClick={() => onResponse(request.consent_id, true)}
                        >
                            Yes, Proceed
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={() => onResponse(request.consent_id, false)}
                        >
                            No, Show Manual Steps
                        </Button>
                    </>
                )}
            </ModalFooter>
        </Modal>
    );
}
```

---

### Option 2: Check for Awaiting-Consent State

**Backend Response:**
```python
# When consent is needed but no callback provided
{
    "success": false,
    "awaiting_consent": true,
    "consent_details": {
        "action": "Kill process on port 8787",
        "danger_level": "warning",  # safe/caution/warning/critical
        "warning": "⚠️ WARNING: Process Termination...",
        "risks": [
            "Will terminate process using port 8787",
            "May interrupt running application or service",
            "Can be restarted after if needed"
        ],
        "affected_resources": ["Process on port 8787"]
    },
    "manual_steps": [
        "1. Check what's running: lsof -ti:8787",
        "2. Kill manually if needed: kill -9 $(lsof -ti:8787)",
        "3. Return to NAVI: 'I handled the port conflict, continue'"
    ],
    "message": "⚠️ Consent required for: Kill process on port 8787...",
    "error": "Port 8787 already in use"
}
```

**Frontend Handler:**
```typescript
async function executeWithNavi(action: NaviAction) {
    const response = await fetch('/api/navi/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action)
    });
    
    const result = await response.json();
    
    if (result.awaiting_consent) {
        // Show consent UI
        const userApproved = await showConsentDialog(result.consent_details);
        
        if (userApproved) {
            // Retry with consent granted
            return executeWithNavi({ ...action, consent_granted: true });
        } else {
            // Show manual steps
            showManualSteps(result.manual_steps);
            return result;
        }
    }
    
    return result;
}
```

---

## 🎨 UI/UX Guidelines

### Danger Level Styling

```css
.consent-modal.safe {
    border-left: 4px solid #10b981; /* Green */
}

.consent-modal.caution {
    border-left: 4px solid #f59e0b; /* Yellow/Orange */
}

.consent-modal.warning {
    border-left: 4px solid #f97316; /* Orange */
}

.consent-modal.critical {
    border-left: 4px solid #ef4444; /* Red */
    animation: pulse-danger 2s infinite;
}

@keyframes pulse-danger {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
    50% { box-shadow: 0 0 20px 10px rgba(239, 68, 68, 0); }
}
```

### Icon Mapping

```typescript
const DANGER_ICONS = {
    safe: '✅',
    caution: '⚙️',
    warning: '⚠️',
    critical: '🚨'
};

const DANGER_COLORS = {
    safe: 'green',
    caution: 'yellow',
    warning: 'orange',
    critical: 'red'
};
```

### Message Formatting

```typescript
function formatWarningMessage(warning: string): JSX.Element {
    // Parse the structured warning
    const lines = warning.split('\n');
    
    return (
        <div className="warning-container">
            <h3 className="warning-title">{lines[0]}</h3>
            <div className="warning-body">
                {lines.slice(1).map((line, i) => (
                    <p key={i}>{line}</p>
                ))}
            </div>
        </div>
    );
}
```

---

## 📱 Chat Interface Integration

For chat-based NAVI interactions:

```typescript
// When NAVI needs consent in chat
function handleNaviMessage(message: NaviMessage) {
    if (message.type === 'consent_request') {
        // Add consent prompt to chat
        addChatMessage({
            sender: 'navi',
            type: 'consent',
            content: message.warning,
            consentId: message.consent_id,
            dangerLevel: message.danger_level
        });
        
        // Show quick action buttons
        showQuickActions([
            { label: 'Yes, proceed', action: () => respondToConsent(message.consent_id, true) },
            { label: 'No, manual steps', action: () => respondToConsent(message.consent_id, false) }
        ]);
    }
}

// User can also type response
function handleUserInput(input: string) {
    if (awaitingConsent) {
        if (input.toLowerCase() === 'yes' || input.toLowerCase() === 'proceed') {
            respondToConsent(currentConsentId, true);
        } else if (input.toLowerCase() === 'no' || input.toLowerCase() === 'manual') {
            respondToConsent(currentConsentId, false);
        }
    }
}
```

---

## 🧪 Testing Checklist

- [ ] **Safe operations** execute immediately without prompting
- [ ] **Caution operations** show yellow warning with yes/no
- [ ] **Warning operations** show orange warning with clear risks
- [ ] **Critical operations** require explicit "yes" confirmation
- [ ] **Denied consent** shows manual steps clearly
- [ ] **Timeout handling** (if user doesn't respond in 5 minutes)
- [ ] **Multiple consent requests** queue properly
- [ ] **Consent history** is logged for audit
- [ ] **Mobile responsive** consent modals
- [ ] **Accessibility** (keyboard navigation, screen readers)

---

## 🎯 Example Scenarios

### Scenario 1: Port Conflict (Warning)
```
User: "Start the backend server"
NAVI: Detects port 8787 in use
Frontend: Shows modal
  ⚠️ WARNING: Process Termination
  
  Action: Kill process on port 8787
  Risk Level: WARNING
  
  This will kill the process running on port 8787.
  The process can be restarted if needed.
  
  [Yes, Proceed] [No, I'll Handle Manually]

User clicks "Yes, Proceed"
NAVI: Kills process, starts server
Frontend: "✅ Server started on port 8787"
```

### Scenario 2: Code Fix (Caution)
```
User: "Run the tests"
NAVI: Detects syntax error in test file
Frontend: Shows modal
  ⚙️ CAUTION: Automatic Code Modification
  
  Action: Fix syntax error using AI analysis
  Risk Level: CAUTION
  
  NAVI will use AI to modify your code automatically.
  A git commit is recommended before proceeding.
  
  [Yes, Proceed] [No, I'll Fix Manually]

User clicks "No, I'll Fix Manually"
Frontend: Shows manual steps
  1. Fix the code manually in your editor
  2. Save your changes
  3. Tell NAVI: 'Code fixed, continue'
```

### Scenario 3: File Deletion (Critical)
```
User: "Clean up the project"
NAVI: Wants to delete old_config.json
Frontend: Shows modal with red border, pulsing animation
  🚨 CRITICAL WARNING: Destructive Operation Detected!
  
  Action: Delete old_config.json
  Risk Level: CRITICAL - PERMANENT DATA LOSS
  
  This operation will PERMANENTLY DELETE data and CANNOT be undone.
  
  Type 'yes' to confirm: [________]
  
  [Proceed (Dangerous)] [I'll Handle Manually]

User types "yes" and clicks "Proceed (Dangerous)"
NAVI: Deletes file
Frontend: "⚠️ File deleted: old_config.json (PERMANENT)"
```

---

## 🔗 API Endpoints to Implement

```typescript
// POST /api/navi/consent/{consent_id}
// Body: { "consent": boolean }
// Response: { "acknowledged": true }

// GET /api/navi/consent/pending
// Response: Array of pending consent requests

// DELETE /api/navi/consent/{consent_id}
// Cancel a consent request (timeout or user dismissal)
```

---

## 📚 Resources

- Main implementation: `backend/services/navi_brain.py`
- Data structures: Lines 5780-5830 (DangerAssessment)
- Assessment logic: Lines 5832-6157 (assess_danger method)
- Consent workflow: Lines 6159-6283 (attempt_recovery with consent)
- Full documentation: `CONSENT_MECHANISM_COMPLETE.md`

---

**Questions?** Check the backend implementation or ask the team! 🚀
