/**
 * User Prompt Handler for NAVI Autonomous Agent
 *
 * Handles prompt_request events from the backend and displays VS Code
 * input dialogs to collect user responses.
 */

import * as vscode from "vscode";

export interface PromptOption {
  label: string;
  description?: string;
}

export interface PromptRequest {
  prompt_id: string;
  prompt_type: "text" | "select" | "multiselect" | "confirm";
  title: string;
  description?: string;
  placeholder?: string;
  default_value?: string;
  options?: PromptOption[];
  timeout_seconds?: number;
}

export interface PromptResponse {
  response?: string;
  cancelled: boolean;
}

export class PromptHandler {
  private backendUrl: string;
  private getAuthToken: () => Promise<string | undefined>;

  constructor(backendUrl: string, getAuthToken: () => Promise<string | undefined>) {
    this.backendUrl = backendUrl;
    this.getAuthToken = getAuthToken;
  }

  /**
   * Handle a prompt request from the backend
   */
  async handlePromptRequest(promptRequest: PromptRequest): Promise<void> {
    console.log(`[PromptHandler] Received prompt request: ${promptRequest.prompt_id}`, promptRequest);

    let response: PromptResponse;

    try {
      switch (promptRequest.prompt_type) {
        case "select":
          response = await this.handleSelectPrompt(promptRequest);
          break;
        case "multiselect":
          response = await this.handleMultiSelectPrompt(promptRequest);
          break;
        case "confirm":
          response = await this.handleConfirmPrompt(promptRequest);
          break;
        case "text":
        default:
          response = await this.handleTextPrompt(promptRequest);
          break;
      }
    } catch (error) {
      console.error(`[PromptHandler] Error handling prompt:`, error);
      response = { cancelled: true };
    }

    // Send response to backend
    await this.sendPromptResponse(promptRequest.prompt_id, response);
  }

  /**
   * Show text input dialog
   */
  private async handleTextPrompt(prompt: PromptRequest): Promise<PromptResponse> {
    const value = await vscode.window.showInputBox({
      title: prompt.title,
      prompt: prompt.description,
      placeHolder: prompt.placeholder,
      value: prompt.default_value,
      ignoreFocusOut: true, // Don't cancel when user clicks away
    });

    if (value === undefined) {
      // User cancelled (pressed Escape)
      return { cancelled: true };
    }

    return {
      response: value,
      cancelled: false,
    };
  }

  /**
   * Show quick pick dialog for select prompts
   */
  private async handleSelectPrompt(prompt: PromptRequest): Promise<PromptResponse> {
    if (!prompt.options || prompt.options.length === 0) {
      console.error("[PromptHandler] Select prompt has no options");
      return { cancelled: true };
    }

    const items = prompt.options.map((opt) => ({
      label: opt.label,
      description: opt.description,
    }));

    const selected = await vscode.window.showQuickPick(items, {
      title: prompt.title,
      placeHolder: prompt.description || "Select an option",
      canPickMany: false,
      ignoreFocusOut: true,
    });

    if (selected === undefined) {
      return { cancelled: true };
    }

    return {
      response: selected.label,
      cancelled: false,
    };
  }

  /**
   * Show multi-select quick pick dialog
   */
  private async handleMultiSelectPrompt(prompt: PromptRequest): Promise<PromptResponse> {
    if (!prompt.options || prompt.options.length === 0) {
      console.error("[PromptHandler] MultiSelect prompt has no options");
      return { cancelled: true };
    }

    const items = prompt.options.map((opt) => ({
      label: opt.label,
      description: opt.description,
    }));

    const selected = await vscode.window.showQuickPick(items, {
      title: prompt.title,
      placeHolder: prompt.description || "Select one or more options",
      canPickMany: true,
      ignoreFocusOut: true,
    });

    if (selected === undefined || selected.length === 0) {
      return { cancelled: true };
    }

    return {
      response: selected.map((item) => item.label).join(", "),
      cancelled: false,
    };
  }

  /**
   * Show confirmation dialog
   */
  private async handleConfirmPrompt(prompt: PromptRequest): Promise<PromptResponse> {
    const answer = await vscode.window.showInformationMessage(
      prompt.description || prompt.title,
      { modal: true },
      "Yes",
      "No"
    );

    if (answer === undefined) {
      return { cancelled: true };
    }

    return {
      response: answer,
      cancelled: false,
    };
  }

  /**
   * Send prompt response to backend
   */
  private async sendPromptResponse(
    promptId: string,
    response: PromptResponse
  ): Promise<void> {
    try {
      const token = await this.getAuthToken();
      if (!token) {
        console.error("[PromptHandler] No auth token available - cannot send prompt response");

        // Notify user about auth failure
        vscode.window.showErrorMessage(
          "Authentication failed. Unable to send response to NAVI. Please sign in again.",
          "Sign In"
        ).then(selection => {
          if (selection === "Sign In") {
            vscode.commands.executeCommand("aep.signIn");
          }
        });

        // NOTE: Cannot send cancellation without auth token.
        // The /api/navi/prompt/{promptId} endpoint requires authentication (Role.VIEWER).
        // Backend will timeout the prompt request after a reasonable period.
        return;
      }

      const url = `${this.backendUrl}/api/navi/prompt/${promptId}`;
      console.log(`[PromptHandler] Sending response to ${url}:`, response);

      const httpResponse = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(response),
      });

      if (!httpResponse.ok) {
        const error = await httpResponse.text();
        console.error(`[PromptHandler] Failed to send response: ${error}`);
      } else {
        console.log(`[PromptHandler] Response sent successfully for prompt ${promptId}`);
      }
    } catch (error) {
      console.error("[PromptHandler] Error sending prompt response:", error);
    }
  }
}
