import React, { useEffect } from "react";
import { UIProvider, useUIState } from "./state/uiStore";
import { routeEventToUI } from "./state/eventRouter";
import { onMessage } from "./utils/vscodeApi";
import { PanelContainer } from "./components/layout/PanelContainer";
import { HeaderBar } from "./components/layout/HeaderBar";
import { ComposerBar } from "./components/layout/ComposerBar";
import { ActionCard } from "./components/actions/ActionCard";
import { WorkflowTimeline } from "./components/workflow/WorkflowTimeline";
import { AgentWorkflowPanel } from "./components/workflow/AgentWorkflowPanel";
import ChatArea from "./components/chat/ChatArea";
import "./globals.css";

/**
 * Phase 4.0.5 - UI Parity with Copilot/Cline Standards
 * 
 * Critical UI fixes for production readiness:
 * ✅ Message state management with proper chat flow
 * ✅ No phantom workflows on simple user input
 * ✅ Proper mode/model selector placement
 * ✅ Clean single header design
 * ✅ User message display immediate feedback
 * 
 * Addressing user feedback for trust and parity.
 */
function AppContent() {
  const { dispatch } = useUIState();

  useEffect(() => {
    const unsubscribe = onMessage((event) => {
      routeEventToUI(event, dispatch);
    });
    return unsubscribe;
  }, [dispatch]);

  return (
    <PanelContainer>
      <HeaderBar />
      
      {/* Agent workflow panel (only visible when agent is active) */}
      <AgentWorkflowPanel />
      
      <ChatArea />
        
      {/* State-driven workflow components */}
      <WorkflowTimeline />
      <ActionCard />

      <ComposerBar />
    </PanelContainer>
  );
}function App() {
  return (
    <UIProvider>
      <AppContent />
    </UIProvider>
  );
}

export default App;
