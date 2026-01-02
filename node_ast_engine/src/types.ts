// Common types for the AST engine
export interface TransformResponse {
  success: boolean;
  file: string;
  edits?: Array<{
    start: number;
    end: number;
    replacement: string;
  }>;
  newFile?: string;
  newFileContent?: string;
  removedFiles?: string[];
  metadata?: {
    transformType: string;
    linesChanged: number;
    complexity: number;
    timestamp: string;
  };
  error?: string;
}