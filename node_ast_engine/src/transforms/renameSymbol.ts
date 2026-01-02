/**
 * Rename Symbol Transform
 * Renames all occurrences of a symbol (variable, function, class, etc.) throughout the code
 */

const traverse = require("@babel/traverse").default;
const t = require("@babel/types");
const { parseCode } = require("../utils/parse");
const { emit } = require("../utils/emit");
import { TransformResponse } from "../types";

export async function renameSymbol(
  filePath: string,
  code: string,
  params: { oldName: string; newName: string; scope?: 'global' | 'local' }
): Promise<TransformResponse> {
  
  if (!params.oldName || !params.newName) {
    throw new Error("Both oldName and newName are required for renameSymbol transform");
  }
  
  if (params.oldName === params.newName) {
    return {
      success: true,
      file: filePath,
      edits: [] // No changes needed
    };
  }

  const ast = parseCode(code);
  let changeCount = 0;
  const scope = params.scope || 'global';
  
  // Track binding scopes to avoid renaming shadowed variables
  const bindingScopes = new Map<string, Set<string>>();

  traverse(ast, {
    Program(path) {
      // Initialize global scope
      bindingScopes.set('global', new Set());
    },
    
    Scope(path) {
      // Track all bindings in this scope
      const scopeBindings = new Set<string>();
      Object.keys(path.scope.bindings).forEach(binding => {
        scopeBindings.add(binding);
      });
      bindingScopes.set(path.scope.uid.toString(), scopeBindings);
    },

    Identifier(path) {
      if (path.node.name === params.oldName) {
        
        // Check if this is a binding (declaration) or reference
        const isBinding = path.isBindingIdentifier();
        const isReference = path.isReferencedIdentifier();
        
        // For local scope, only rename if it's in the same lexical scope
        if (scope === 'local') {
          const binding = path.scope.getBinding(params.oldName);
          if (!binding) return; // Not in scope
        }
        
        // Special cases to avoid renaming
        if (path.isObjectProperty() && (path as any).node === (path as any).parent.key && !(path as any).parent.computed) {
          // Don't rename object property keys unless computed
          return;
        }
        
        if (path.isMemberExpression() && (path as any).node === (path as any).parent.property && !(path as any).parent.computed) {
          // Don't rename member expression properties unless computed  
          return;
        }
        
        // Perform the rename
        path.node.name = params.newName;
        changeCount++;
      }
    },
    
    // Handle specific node types that might contain the symbol
    FunctionDeclaration(path) {
      if (path.node.id && path.node.id.name === params.oldName) {
        path.node.id.name = params.newName;
        changeCount++;
      }
    },
    
    ClassDeclaration(path) {
      if (path.node.id && path.node.id.name === params.oldName) {
        path.node.id.name = params.newName;
        changeCount++;
      }
    },
    
    VariableDeclarator(path) {
      if (t.isIdentifier(path.node.id) && path.node.id.name === params.oldName) {
        path.node.id.name = params.newName;
        changeCount++;
      }
    },
    
    ImportSpecifier(path) {
      if (path.node.local.name === params.oldName) {
        path.node.local.name = params.newName;
        changeCount++;
      }
      if (path.node.imported && t.isIdentifier(path.node.imported) && path.node.imported.name === params.oldName) {
        path.node.imported.name = params.newName;
        changeCount++;
      }
    },
    
    ExportSpecifier(path) {
      if (path.node.local.name === params.oldName) {
        path.node.local.name = params.newName;
        changeCount++;
      }
      if (t.isIdentifier(path.node.exported) && path.node.exported.name === params.oldName) {
        path.node.exported.name = params.newName;
        changeCount++;
      }
    }
  });

  const newCode = emit(ast);
  
  return {
    success: true,
    file: filePath,
    edits: [
      {
        start: 0,
        end: code.length,
        replacement: newCode
      }
    ],
    metadata: {
      transformType: 'renameSymbol',
      linesChanged: Math.abs(newCode.split('\n').length - code.split('\n').length),
      complexity: changeCount,
      timestamp: new Date().toISOString()
    }
  };
}

module.exports = { renameSymbol };