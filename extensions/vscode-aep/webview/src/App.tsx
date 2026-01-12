import React, { useEffect } from "react";
import { WorkspaceProvider } from "./context/WorkspaceContext";
import { UIProvider, useUIState } from "./state/uiStore";
import { routeEventToUI } from "./state/eventRouter";
import { onMessage } from "./utils/vscodeApi";
import { CodeCompanionShell } from "./components/shell/CodeCompanionShell";
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
    <ErrorBoundary>
      <CodeCompanionShell />
    </ErrorBoundary>
  );
}

function App() {
  return (
    <UIProvider>
      <WorkspaceProvider>
        <AppContent />
      </WorkspaceProvider>
    </UIProvider>
  );
}

export default App;

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[NAVI] Webview render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full w-full items-center justify-center bg-slate-950 text-slate-100">
          <div className="max-w-lg rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-100">
            <div className="font-semibold">Webview render error</div>
            <div className="mt-2 text-red-200">
              {this.state.error?.message || "Unknown error"}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
