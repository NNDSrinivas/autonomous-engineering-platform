import { Dispatch } from "react";
import { UIAction } from "./uiStore";

type CommandBuffer = {
  stdout: string;
  stderr: string;
  command?: string;
  cwd?: string;
  meta?: any;
};

const commandBuffers = new Map<string, CommandBuffer>();
let lastAssistantMessage: { text: string; at: number } | null = null;

function shouldSkipDuplicateAssistantMessage(content: string) {
  const trimmed = content.trim();
  if (!trimmed) {
    return true;
  }

  const now = Date.now();
  if (lastAssistantMessage && lastAssistantMessage.text === trimmed && now - lastAssistantMessage.at < 1500) {
    return true;
  }

  lastAssistantMessage = { text: trimmed, at: now };
  return false;
}

function getChangePlan(event: any) {
  return event?.changePlan ?? event?.plan ?? event?.data?.changePlan ?? event?.data?.plan ?? event?.data;
}

function getDiffs(event: any) {
  return event?.codeChanges ?? event?.diffs ?? event?.data?.codeChanges ?? event?.data?.diffs ?? event?.data;
}

function getValidationResult(event: any) {
  return event?.validationResult ?? event?.result ?? event?.data?.validationResult ?? event?.data?.result ?? event?.data;
}

function getApplyResult(event: any) {
  return event?.applyResult ?? event?.result ?? event?.data?.applyResult ?? event?.data;
}

function startWorkflow(dispatch: Dispatch<UIAction>) {
  dispatch({ type: "START_WORKFLOW" });
}

function stepActive(dispatch: Dispatch<UIAction>, step: string) {
  dispatch({ type: "STEP_ACTIVE", step });
}

function stepComplete(dispatch: Dispatch<UIAction>, step: string) {
  dispatch({ type: "STEP_COMPLETE", step });
}

function stepFail(dispatch: Dispatch<UIAction>, step: string) {
  dispatch({ type: "STEP_FAIL", step });
}

export function routeEventToUI(event: any, dispatch: Dispatch<UIAction>) {
  switch (event.type) {
    case "navi.workflow.started":
      startWorkflow(dispatch);
      break;

    case "navi.workflow.step":
      if (event.status === "active") stepActive(dispatch, event.step);
      if (event.status === "completed") stepComplete(dispatch, event.step);
      if (event.status === "failed") stepFail(dispatch, event.step);
      break;

    case "navi.approval.required":
      dispatch({ type: "REQUEST_APPROVAL" });
      break;

    case "navi.workflow.completed":
      dispatch({ type: "RESET" });
      break;

    case "navi.workflow.failed":
      stepFail(dispatch, event.step || "unknown");
      break;

    case "navi.assistant.message":
      if (!shouldSkipDuplicateAssistantMessage(String(event.content || ""))) {
        dispatch({ type: "ADD_ASSISTANT_MESSAGE", content: event.content });
      }
      break;

    case "botMessage":
      if (!shouldSkipDuplicateAssistantMessage(String(event.text || event.content || ""))) {
        dispatch({ type: "ADD_ASSISTANT_MESSAGE", content: event.text || event.content || "" });
      }
      break;

    case "error":
      dispatch({
        type: "ADD_ASSISTANT_MESSAGE",
        content: event.text || event.content || "⚠️ An unexpected error occurred.",
        messageType: "error",
        error: event.text || event.content
      });
      dispatch({ type: "SET_THINKING", thinking: false });
      break;

    case "navi.assistant.thinking":
      dispatch({ type: "SET_THINKING", thinking: !!event.thinking });
      break;

    case "botThinking":
      dispatch({ type: "SET_THINKING", thinking: !!event.value });
      break;

    case "navi.assistant.plan": {
      dispatch({
        type: "ADD_PLAN",
        plan: event.plan,
        reasoning: event.reasoning,
        session_id: event.session_id
      });
      dispatch({ type: "SET_THINKING", thinking: false });
      break;
    }

    case "navi.assistant.conversation":
      dispatch({
        type: "ADD_CONVERSATION",
        content: event.content,
        conversationType: event.conversationType,
        suggestions: event.suggestions
      });
      break;

    case "navi.readonly.context": {
      const files = Array.isArray(event.files) ? event.files : [];
      dispatch({ type: "CLEAR_WORKFLOW" });
      if (files.length > 0) {
        dispatch({
          type: "ADD_ARTIFACT_MESSAGE",
          artifact: {
            kind: "context",
            title: "Read-only context",
            data: {
              files,
              summary: event.summary
            }
          }
        });
      }
      break;
    }

    case "navi.tool.approval":
      dispatch({
        type: "REQUEST_TOOL_APPROVAL",
        tool_request: event.tool_request,
        session_id: event.session_id
      });
      break;

    case "navi.assistant.error":
      dispatch({
        type: "ADD_ASSISTANT_MESSAGE",
        content: event.content,
        messageType: "error",
        error: event.error
      });
      break;

    case "addAttachment":
      if (event.attachment) {
        dispatch({ type: "ADD_ATTACHMENT", attachment: event.attachment });
      }
      break;

    case "removeAttachment":
      if (event.attachmentKey) {
        dispatch({ type: "REMOVE_ATTACHMENT", attachmentKey: event.attachmentKey });
      }
      break;

    case "clearAttachments":
      dispatch({ type: "CLEAR_ATTACHMENTS" });
      break;

    case "resetChat":
      dispatch({ type: "CLEAR_MESSAGES" });
      lastAssistantMessage = null;
      break;

    case "navi.changePlan.generated": {
      const changePlan = getChangePlan(event);
      if (changePlan) {
        dispatch({
          type: "ADD_ARTIFACT_MESSAGE",
          artifact: {
            kind: "changePlan",
            title: changePlan.goal ? `Plan: ${changePlan.goal}` : "Plan generated",
            data: changePlan
          }
        });
      }
      startWorkflow(dispatch);
      stepComplete(dispatch, "scan");
      stepComplete(dispatch, "plan");
      stepActive(dispatch, "diff");
      break;
    }

    case "navi.diffs.generated": {
      const codeChanges = getDiffs(event);
      if (codeChanges) {
        dispatch({
          type: "ADD_ARTIFACT_MESSAGE",
          artifact: {
            kind: "diffs",
            title: "Diffs generated",
            data: { codeChanges }
          }
        });
      }
      startWorkflow(dispatch);
      stepComplete(dispatch, "diff");
      stepActive(dispatch, "validate");
      break;
    }

    case "navi.validation.result": {
      const validationResult = getValidationResult(event);
      if (validationResult) {
        dispatch({
          type: "ADD_ARTIFACT_MESSAGE",
          artifact: {
            kind: "validation",
            title: "Validation result",
            data: validationResult
          }
        });
      }
      startWorkflow(dispatch);
      if (validationResult?.status === "FAILED" || validationResult?.canProceed === false) {
        stepFail(dispatch, "validate");
      } else {
        stepComplete(dispatch, "validate");
        stepActive(dispatch, "apply");
      }
      break;
    }

    case "navi.changes.applied": {
      const applyResult = getApplyResult(event);
      if (applyResult) {
        dispatch({
          type: "ADD_ARTIFACT_MESSAGE",
          artifact: {
            kind: "apply",
            title: "Changes applied",
            data: applyResult
          }
        });
      }
      startWorkflow(dispatch);
      stepComplete(dispatch, "apply");
      stepActive(dispatch, "pr");
      break;
    }

    case "navi.pr.branch.created": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "pr",
          title: "Branch created",
          data: { stage: "branch", ...event.branchResult, ...event }
        }
      });
      startWorkflow(dispatch);
      stepActive(dispatch, "pr");
      break;
    }

    case "navi.pr.commit.created": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "pr",
          title: "Commit created",
          data: { stage: "commit", ...event.commitResult, ...event }
        }
      });
      startWorkflow(dispatch);
      stepActive(dispatch, "pr");
      break;
    }

    case "navi.pr.created": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "pr",
          title: "Pull request created",
          data: { stage: "pr", ...event.prResult, ...event }
        }
      });
      startWorkflow(dispatch);
      stepComplete(dispatch, "pr");
      stepActive(dispatch, "ci");
      break;
    }

    case "navi.pr.monitoring.started": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "ci",
          title: "CI monitoring started",
          data: { stage: "monitoring", ...event }
        }
      });
      startWorkflow(dispatch);
      stepActive(dispatch, "ci");
      break;
    }

    case "navi.pr.ci.updated": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "ci",
          title: "CI update",
          data: { stage: "update", ...event }
        }
      });
      startWorkflow(dispatch);
      stepActive(dispatch, "ci");
      if (event.conclusion === "failure" || event.state === "failure") {
        stepFail(dispatch, "ci");
      }
      break;
    }

    case "navi.pr.completed": {
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "ci",
          title: "CI completed",
          data: { stage: "completed", ...event }
        }
      });
      startWorkflow(dispatch);
      if (event.conclusion === "failure" || event.state === "failure") {
        stepFail(dispatch, "ci");
      } else {
        stepComplete(dispatch, "ci");
      }
      break;
    }

    case "command.start": {
      const commandId = String(event.commandId || "");
      if (commandId) {
        commandBuffers.set(commandId, {
          stdout: "",
          stderr: "",
          command: event.command,
          cwd: event.cwd,
          meta: event.meta
        });
      }
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "command",
          title: "Command started",
          data: {
            status: "running",
            commandId,
            command: event.command,
            cwd: event.cwd,
            meta: event.meta
          }
        }
      });
      break;
    }

    case "command.output": {
      const commandId = String(event.commandId || "");
      if (!commandId) break;
      const buffer = commandBuffers.get(commandId) || {
        stdout: "",
        stderr: "",
        command: event.command,
        cwd: event.cwd,
        meta: event.meta
      };
      if (event.stream === "stderr") {
        buffer.stderr = `${buffer.stderr}${event.text || ""}`;
      } else {
        buffer.stdout = `${buffer.stdout}${event.text || ""}`;
      }
      commandBuffers.set(commandId, buffer);
      break;
    }

    case "command.error": {
      const commandId = String(event.commandId || "");
      const buffer = commandBuffers.get(commandId);
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "command",
          title: "Command failed",
          data: {
            status: "error",
            commandId,
            command: buffer?.command,
            cwd: buffer?.cwd,
            stdout: buffer?.stdout,
            stderr: buffer?.stderr,
            error: event.error
          }
        }
      });
      if (commandId) {
        commandBuffers.delete(commandId);
      }
      break;
    }

    case "command.done": {
      const commandId = String(event.commandId || "");
      const buffer = commandBuffers.get(commandId);
      dispatch({
        type: "ADD_ARTIFACT_MESSAGE",
        artifact: {
          kind: "command",
          title: "Command finished",
          data: {
            status: "done",
            commandId,
            command: buffer?.command,
            cwd: buffer?.cwd,
            stdout: buffer?.stdout,
            stderr: buffer?.stderr,
            exitCode: event.exitCode,
            durationMs: event.durationMs
          }
        }
      });
      if (commandId) {
        commandBuffers.delete(commandId);
      }
      break;
    }

    default:
      break;
  }
}
