/**
 * Code Generation Utility
 * Handles converting AST back to source code with proper formatting
 */

const generate = require("@babel/generator").default;

export interface EmitOptions {
  retainLines?: boolean;
  compact?: boolean;
  comments?: boolean;
  minified?: boolean;
  sourceMaps?: boolean;
  sourceMapTarget?: string;
  sourceRoot?: string;
  sourceFileName?: string;
}

export function emit(node: Node, options: EmitOptions = {}): string {
  try {
    const result = generate(node, {
      retainLines: options.retainLines !== false, // Default true to preserve line numbers
      compact: options.compact || false,
      comments: options.comments !== false, // Default true to preserve comments
      minified: options.minified || false,
      sourceMaps: options.sourceMaps || false,
      
      // Preserve existing formatting where possible
      decoratorsBeforeExport: true
    });
    
    return result.code;
  } catch (generateError) {
    throw new Error(`Failed to generate code: ${generateError instanceof Error ? generateError.message : String(generateError)}`);
  }
}

export function emitWithSourceMap(node: Node, options: EmitOptions = {}) {
  try {
    return generate(node, {
      ...options,
      sourceMaps: true,
      retainLines: options.retainLines !== false,
      comments: options.comments !== false
    });
  } catch (generateError) {
    throw new Error(`Failed to generate code with source map: ${generateError instanceof Error ? generateError.message : String(generateError)}`);
  }
}

/**
 * Format code with consistent styling
 */
export function formatCode(code: string, options: {
  indentSize?: number;
  semicolons?: boolean;
  singleQuotes?: boolean;
} = {}): string {
  // Basic formatting - in production you might want to integrate Prettier
  let formatted = code;
  
  // Normalize line endings
  formatted = formatted.replace(/\r\n/g, '\n');
  
  // Remove trailing whitespace
  formatted = formatted.replace(/[ \t]+$/gm, '');
  
  // Ensure consistent indentation
  if (options.indentSize) {
    const lines = formatted.split('\n');
    let indentLevel = 0;
    const indentStr = ' '.repeat(options.indentSize);
    
    formatted = lines.map(line => {
      const trimmed = line.trim();
      if (!trimmed) return '';
      
      // Adjust indent level
      if (trimmed.includes('}')) indentLevel--;
      const result = indentStr.repeat(Math.max(0, indentLevel)) + trimmed;
      if (trimmed.includes('{') && !trimmed.includes('}')) indentLevel++;
      
      return result;
    }).join('\n');
  }
  
  return formatted;
}

module.exports = { emit, emitWithSourceMap, formatCode };