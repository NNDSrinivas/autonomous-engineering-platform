/**
 * Code Parser Utility
 * Handles parsing of JavaScript/TypeScript code with all modern syntax support
 */

const { parse } = require("@babel/parser");

export interface ParseOptions {
  sourceType?: "script" | "module";
  allowImportExportEverywhere?: boolean;
  allowReturnOutsideFunction?: boolean;
  ranges?: boolean;
  tokens?: boolean;
}

export function parseCode(code: string, options: ParseOptions = {}): File {
  try {
    return parse(code, {
      sourceType: options.sourceType || "module",
      allowImportExportEverywhere: options.allowImportExportEverywhere || false,
      allowReturnOutsideFunction: options.allowReturnOutsideFunction || false,
      ranges: options.ranges || false,
      tokens: options.tokens || false,
      plugins: [
        // JavaScript/TypeScript features
        "jsx",
        "typescript", 
        ["decorators", { "decoratorsBeforeExport": true }],
        "classProperties",
        "classPrivateProperties",
        "classPrivateMethods",
        
        // Modern JavaScript features
        "optionalChaining",
        "nullishCoalescingOperator",
        "optionalCatchBinding", 
        "numericSeparator",
        "bigInt",
        "dynamicImport",
        "importMeta",
        "topLevelAwait",
        
        // Proposed features (commonly used)
        "functionBind",
        "partialApplication",
        
        // React/JSX extensions  
        "jsx"
      ]
    });
  } catch (parseError) {
    // Try parsing without TypeScript if it fails
    if (parseError instanceof Error && parseError.message.includes('typescript')) {
      try {
        return parse(code, {
          ...options,
          sourceType: options.sourceType || "module",
          plugins: [
            "jsx",
            ["decorators", { "decoratorsBeforeExport": true }], 
            "classProperties",
            "optionalChaining",
            "nullishCoalescingOperator",
            "dynamicImport",
            "bigInt"
          ]
        });
      } catch (fallbackError) {
        throw new Error(`Failed to parse code: ${fallbackError instanceof Error ? fallbackError.message : String(fallbackError)}`);
      }
    }
    
    throw new Error(`Failed to parse code: ${parseError instanceof Error ? parseError.message : String(parseError)}`);
  }
}

export function isTypeScriptFile(filePath: string): boolean {
  return /\.tsx?$/.test(filePath);
}

export function isJSXFile(filePath: string): boolean {
  return /\.(jsx|tsx)$/.test(filePath);
}

export function getLanguageFromPath(filePath: string): 'javascript' | 'typescript' | 'jsx' | 'tsx' {
  if (filePath.endsWith('.tsx')) return 'tsx';
  if (filePath.endsWith('.ts')) return 'typescript';
  if (filePath.endsWith('.jsx')) return 'jsx';
  return 'javascript';
}

module.exports = { parseCode, isTypeScriptFile, isJSXFile, getLanguageFromPath };