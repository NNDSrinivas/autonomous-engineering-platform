/**
 * Transform Runner - Dispatch system for all AST transformations
 * Handles command routing and response formatting
 */

const { renameSymbol } = require("./transforms/renameSymbol");
const { updateImport } = require("./transforms/updateImport");
const { extractComponent } = require("./transforms/extractComponent");
const { convertJsToTs } = require("./transforms/convertJsToTs");
const { removeDeadCode } = require("./transforms/removeDeadCode");

export interface TransformRequest {
  command: string;
  filePath: string;
  code: string;
  params?: any;
}

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

export async function runTransform(req: TransformRequest): Promise<TransformResponse> {
  const startTime = Date.now();
  
  try {
    let result: TransformResponse;
    
    switch (req.command) {
      case "renameSymbol":
        if (!req.params?.oldName || !req.params?.newName) {
          throw new Error("renameSymbol requires params.oldName and params.newName");
        }
        result = await renameSymbol(req.filePath, req.code, req.params);
        break;
        
      case "updateImport":
        if (!req.params?.from || !req.params?.to) {
          throw new Error("updateImport requires params.from and params.to");
        }
        result = await updateImport(req.filePath, req.code, req.params);
        break;
        
      case "extractComponent":
        if (!req.params?.componentName) {
          throw new Error("extractComponent requires params.componentName");
        }
        result = await extractComponent(req.filePath, req.code, req.params);
        break;
        
      case "convertJsToTs":
        result = await convertJsToTs(req.filePath, req.code, req.params || {});
        break;
        
      case "removeDeadCode":
        result = await removeDeadCode(req.filePath, req.code);
        break;
        
      default:
        throw new Error(`Unknown transform command: ${req.command}. Available commands: renameSymbol, updateImport, extractComponent, convertJsToTs, removeDeadCode`);
    }
    
    // Add metadata to successful responses
    const duration = Date.now() - startTime;
    result.success = true;
    result.metadata = {
      transformType: req.command,
      linesChanged: result.edits?.reduce((acc, edit) => {
        const oldLines = req.code.slice(edit.start, edit.end).split('\n').length;
        const newLines = edit.replacement.split('\n').length;
        return acc + Math.abs(newLines - oldLines);
      }, 0) || 0,
      complexity: calculateComplexity(req.code),
      timestamp: new Date().toISOString()
    };
    
    return result;
    
  } catch (error) {
    return {
      success: false,
      file: req.filePath,
      error: error instanceof Error ? error.message : String(error),
      metadata: {
        transformType: req.command,
        linesChanged: 0,
        complexity: 0,
        timestamp: new Date().toISOString()
      }
    };
  }
}

function calculateComplexity(code: string): number {
  // Simple complexity metric based on control structures
  const complexityPatterns = [
    /\bif\s*\(/g,
    /\bfor\s*\(/g,
    /\bwhile\s*\(/g,
    /\bswitch\s*\(/g,
    /\btry\s*\{/g,
    /\bcatch\s*\(/g,
    /\?\s*.*\s*:/g, // ternary
    /=>\s*{/g, // arrow functions with blocks
  ];
  
  return complexityPatterns.reduce((count, pattern) => {
    return count + (code.match(pattern) || []).length;
  }, 1); // Base complexity of 1
}

module.exports = { runTransform };