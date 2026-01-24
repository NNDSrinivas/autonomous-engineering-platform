/**
 * Action Marker Parser
 * 
 * Parses LLM-generated action markers from text.
 * Extends existing ActionRegistry with marker-based action parsing.
 */

import * as path from 'path';

export interface ParsedAction {
    type: 'CREATE_FILE' | 'EDIT_FILE' | 'RUN_COMMAND' | 'DELETE_FILE' | 'MOVE_FILE';
    params: Record<string, string>;
    rawMarker: string;
    lineNumber: number;
}

export interface ParsedActionPlan {
    actions: ParsedAction[];
    rawText: string;
    errors: string[];
}

/**
 * Parses action markers from LLM output for integration with ActionRegistry
 */
export class ActionMarkerParser {
    private static readonly MARKER_PATTERNS = {
        CREATE_FILE: /\[\[CREATE_FILE:\s*([^\]]+)\]\]\s*```(?:\w+)?\n([\s\S]*?)```/g,
        EDIT_FILE: /\[\[EDIT_FILE:\s*([^\]]+)\]\]\s*```(?:\w+)?\n([\s\S]*?)```/g,
        RUN_COMMAND: /\[\[RUN_COMMAND:\s*([^\]]+)\]\]/g,
        DELETE_FILE: /\[\[DELETE_FILE:\s*([^\]]+)\]\]/g,
        MOVE_FILE: /\[\[MOVE_FILE:\s*from=([^,\]]+),\s*to=([^\]]+)\]\]/g,
    };

    /**
     * Parse LLM output containing action markers
     */
    parse(text: string): ParsedActionPlan {
        const actions: ParsedAction[] = [];
        const errors: string[] = [];
        const lines = text.split('\n');

        // Parse CREATE_FILE markers
        let match;
        while ((match = ActionMarkerParser.MARKER_PATTERNS.CREATE_FILE.exec(text)) !== null) {
            const filePath = match[1].trim();
            const content = match[2];
            const lineNumber = this.getLineNumber(text, match.index);

            if (!filePath) {
                errors.push(`Invalid CREATE_FILE marker at line ${lineNumber}: missing file path`);
                continue;
            }

            actions.push({
                type: 'CREATE_FILE',
                params: { path: filePath, content },
                rawMarker: match[0],
                lineNumber,
            });
        }

        // Reset regex
        ActionMarkerParser.MARKER_PATTERNS.CREATE_FILE.lastIndex = 0;

        // Parse EDIT_FILE markers
        while ((match = ActionMarkerParser.MARKER_PATTERNS.EDIT_FILE.exec(text)) !== null) {
            const filePath = match[1].trim();
            const content = match[2];
            const lineNumber = this.getLineNumber(text, match.index);

            if (!filePath) {
                errors.push(`Invalid EDIT_FILE marker at line ${lineNumber}: missing file path`);
                continue;
            }

            actions.push({
                type: 'EDIT_FILE',
                params: { path: filePath, content },
                rawMarker: match[0],
                lineNumber,
            });
        }

        ActionMarkerParser.MARKER_PATTERNS.EDIT_FILE.lastIndex = 0;

        // Parse RUN_COMMAND markers
        while ((match = ActionMarkerParser.MARKER_PATTERNS.RUN_COMMAND.exec(text)) !== null) {
            const command = match[1].trim();
            const lineNumber = this.getLineNumber(text, match.index);

            if (!command) {
                errors.push(`Invalid RUN_COMMAND marker at line ${lineNumber}: missing command`);
                continue;
            }

            actions.push({
                type: 'RUN_COMMAND',
                params: { command },
                rawMarker: match[0],
                lineNumber,
            });
        }

        ActionMarkerParser.MARKER_PATTERNS.RUN_COMMAND.lastIndex = 0;

        // Parse DELETE_FILE markers
        while ((match = ActionMarkerParser.MARKER_PATTERNS.DELETE_FILE.exec(text)) !== null) {
            const filePath = match[1].trim();
            const lineNumber = this.getLineNumber(text, match.index);

            if (!filePath) {
                errors.push(`Invalid DELETE_FILE marker at line ${lineNumber}: missing file path`);
                continue;
            }

            actions.push({
                type: 'DELETE_FILE',
                params: { path: filePath },
                rawMarker: match[0],
                lineNumber,
            });
        }

        ActionMarkerParser.MARKER_PATTERNS.DELETE_FILE.lastIndex = 0;

        // Parse MOVE_FILE markers
        while ((match = ActionMarkerParser.MARKER_PATTERNS.MOVE_FILE.exec(text)) !== null) {
            const fromPath = match[1].trim();
            const toPath = match[2].trim();
            const lineNumber = this.getLineNumber(text, match.index);

            if (!fromPath || !toPath) {
                errors.push(`Invalid MOVE_FILE marker at line ${lineNumber}: missing paths`);
                continue;
            }

            actions.push({
                type: 'MOVE_FILE',
                params: { from: fromPath, to: toPath },
                rawMarker: match[0],
                lineNumber,
            });
        }

        ActionMarkerParser.MARKER_PATTERNS.MOVE_FILE.lastIndex = 0;

        return {
            actions,
            rawText: text,
            errors,
        };
    }

    /**
     * Convert parsed actions to ActionRegistry format
     */
    toActionRegistryFormat(parsed: ParsedActionPlan): any[] {
        return parsed.actions.map(action => {
            switch (action.type) {
                case 'CREATE_FILE':
                    return {
                        type: 'createFile',
                        path: action.params.path,
                        content: action.params.content,
                    };

                case 'EDIT_FILE':
                    return {
                        type: 'editFile',
                        path: action.params.path,
                        edits: [{
                            oldCode: '',
                            newCode: action.params.content,
                        }],
                    };

                case 'RUN_COMMAND':
                    return {
                        type: 'runCommand',
                        command: action.params.command,
                    };

                case 'DELETE_FILE':
                    return {
                        type: 'deleteFile',
                        path: action.params.path,
                    };

                case 'MOVE_FILE':
                    return {
                        type: 'moveFile',
                        from: action.params.from,
                        to: action.params.to,
                    };

                default:
                    return null;
            }
        }).filter(Boolean);
    }

    private getLineNumber(text: string, index: number): number {
        return text.substring(0, index).split('\n').length;
    }
}
