/**
 * User Prompt Handler for NAVI Autonomous Agent
 *
 * Handles prompt_request events from the backend and displays VS Code
 * input dialogs to collect user responses.
 */

import * as vscode from "vscode";

export interface PromptOption {
  value: string;
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
  response?: string | boolean | string[];
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

    // Map options to QuickPickItems, storing value for later retrieval
    const items = prompt.options.map((opt) => ({
      label: opt.label,
      description: opt.description,
      value: opt.value, // Store value for returning to backend
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
      response: selected.value, // Return value, not label
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

    // Map options to QuickPickItems, storing value for later retrieval
    const items = prompt.options.map((opt) => ({
      label: opt.label,
      description: opt.description,
      value: opt.value, // Store value for returning to backend
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
      response: selected.map((item) => item.value), // Return array of values, not joined string
      cancelled: false,
    };
  }

  /**
   * Show confirmation dialog
   */
  private async handleConfirmPrompt(prompt: PromptRequest): Promise<PromptResponse> {
    // If options are provided, use them; otherwise default to Yes/No
    if (prompt.options && prompt.options.length > 0) {
      // Map options to QuickPickItems for custom confirm options
      const items = prompt.options.map((opt) => ({
        label: opt.label,
        description: opt.description,
        value: opt.value,
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
        response: selected.value,
        cancelled: false,
      };
    }

    // Default Yes/No confirmation
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
      response: answer === "Yes", // Return boolean for default confirm
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
        vscode.window.showErrorMessage(
          "Failed to send your response to NAVI due to a server error. The agent may time out. Please try again."
        );
      } else {
        console.log(`[PromptHandler] Response sent successfully for prompt ${promptId}`);
      }
    } catch (error) {
      console.error("[PromptHandler] Error sending prompt response:", error);
      vscode.window.showErrorMessage(
        "An error occurred while sending your response to NAVI. The agent may time out. Please check your connection and try again."
      );
    }
  }
}
