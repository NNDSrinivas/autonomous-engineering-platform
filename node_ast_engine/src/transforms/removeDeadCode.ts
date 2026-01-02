/**
 * Remove Dead Code Transform
 * Removes unused variables, functions, imports, and other dead code
 */

import traverse from "@babel/traverse";
import * as t from "@babel/types";
import { TransformResponse } from "../types";
const { parseCode } = require("../utils/parse");
const { emit } = require("../utils/emit");

export async function removeDeadCode(
  filePath: string,
  code: string
): Promise<TransformResponse> {

  const ast = parseCode(code);
  let changeCount = 0;
  
  // Track all bindings and their references
  const allBindings = new Map<string, {
    binding: any;
    referenced: boolean;
    path: any;
  }>();

  // First pass: collect all bindings
  traverse(ast, {
    Program(path) {
      Object.keys(path.scope.bindings).forEach(name => {
        const binding = path.scope.bindings[name];
        allBindings.set(name, {
          binding,
          referenced: binding.referenced,
          path: binding.path
        });
      });
    },
    
    Function(path) {
      Object.keys(path.scope.bindings).forEach(name => {
        const binding = path.scope.bindings[name];
        if (!allBindings.has(name)) {  // Don't override global bindings
          allBindings.set(name, {
            binding,
            referenced: binding.referenced,
            path: binding.path
          });
        }
      });
    },
    
    BlockStatement(path) {
      Object.keys(path.scope.bindings).forEach(name => {
        const binding = path.scope.bindings[name];
        if (!allBindings.has(name)) {
          allBindings.set(name, {
            binding,
            referenced: binding.referenced,
            path: binding.path
          });
        }
      });
    }
  });

  // Second pass: remove unused code
  traverse(ast, {
    // Remove unused function declarations
    FunctionDeclaration(path) {
      const name = path.node.id?.name;
      if (name) {
        const bindingInfo = allBindings.get(name);
        if (bindingInfo && !bindingInfo.referenced && !isExported(path)) {
          // Check if it's a convention-based unused function (starts with _)
          if (name.startsWith('_') || !bindingInfo.binding.referenced) {
            path.remove();
            changeCount++;
          }
        }
      }
    },

    // Remove unused variable declarations
    VariableDeclaration(path) {
      let hasUsedDeclarators = false;
      
      path.node.declarations = path.node.declarations.filter(declarator => {
        if (t.isIdentifier(declarator.id)) {
          const name = declarator.id.name;
          const bindingInfo = allBindings.get(name);
          
          if (bindingInfo && !bindingInfo.referenced && !name.startsWith('_')) {
            // Keep if it has side effects in the initializer
            if (declarator.init && hasSideEffects(declarator.init)) {
              hasUsedDeclarators = true;
              return true;
            }
            
            changeCount++;
            return false;  // Remove this declarator
          }
        }
        
        hasUsedDeclarators = true;
        return true;  // Keep this declarator
      });
      
      // Remove entire variable declaration if no declarators left
      if (path.node.declarations.length === 0) {
        path.remove();
      } else if (!hasUsedDeclarators) {
        path.remove();
      }
    },

    // Remove unused import specifiers
    ImportDeclaration(path) {
      const originalSpecifiers = path.node.specifiers.length;
      
      path.node.specifiers = path.node.specifiers.filter(specifier => {
        let localName: string;
        
        if (t.isImportDefaultSpecifier(specifier)) {
          localName = specifier.local.name;
        } else if (t.isImportSpecifier(specifier)) {
          localName = specifier.local.name;
        } else if (t.isImportNamespaceSpecifier(specifier)) {
          localName = specifier.local.name;
        } else {
          return true;
        }
        
        const bindingInfo = allBindings.get(localName);
        if (bindingInfo && !bindingInfo.referenced) {
          changeCount++;
          return false;  // Remove this import specifier
        }
        
        return true;  // Keep this import specifier
      });
      
      // Remove entire import declaration if no specifiers left
      if (path.node.specifiers.length === 0) {
        // Check if it's a side-effect import (no specifiers originally)
        if (originalSpecifiers > 0) {
          path.remove();
          changeCount++;
        }
      }
    },

    // Remove unused class declarations
    ClassDeclaration(path) {
      const name = path.node.id?.name;
      if (name) {
        const bindingInfo = allBindings.get(name);
        if (bindingInfo && !bindingInfo.referenced && !isExported(path)) {
          path.remove();
          changeCount++;
        }
      }
    },

    // Remove unused class methods
    ClassMethod(path) {
      if (path.node.kind === 'method' && t.isIdentifier(path.node.key)) {
        const methodName = path.node.key.name;
        
        // Remove methods that start with underscore (convention for unused)
        if (methodName.startsWith('_') && !isUsedInClass(path, methodName)) {
          path.remove();
          changeCount++;
        }
      }
    },

    // Remove unreachable code after return/throw
    ReturnStatement(path) {
      removeUnreachableAfter(path);
    },
    
    ThrowStatement(path) {
      removeUnreachableAfter(path);
    },

    // Remove empty blocks
    BlockStatement(path) {
      if (path.node.body.length === 0 && !isRequiredEmptyBlock(path)) {
        // Don't remove function bodies or required blocks
        const parent = path.parent;
        if (!t.isFunction(parent) && !t.isCatchClause(parent)) {
          path.remove();
          changeCount++;
        }
      }
    },

    // Remove unused parameters (mark with _ prefix for now)
    "FunctionDeclaration|FunctionExpression|ArrowFunctionExpression"(path) {
      markUnusedParameters(path);
    }
  });

  // Helper function to remove unreachable statements
  function removeUnreachableAfter(path: any) {
    const parent = path.parent;
    if (t.isBlockStatement(parent)) {
      const statements = parent.body;
      const currentIndex = statements.indexOf(path.node);
      
      if (currentIndex !== -1 && currentIndex < statements.length - 1) {
        // Remove all statements after this one
        const unreachableCount = statements.length - currentIndex - 1;
        statements.splice(currentIndex + 1);
        changeCount += unreachableCount;
      }
    }
  }

  // Helper function to mark unused parameters
  function markUnusedParameters(path: any) {
    if (!path.node.params) return;
    
    path.node.params.forEach((param: t.Node, index: number) => {
      if (t.isIdentifier(param)) {
        const binding = path.scope.getBinding(param.name);
        if (binding && !binding.referenced && !param.name.startsWith('_')) {
          // Don't remove parameters, just mark them as potentially unused
          // param.name = `_${param.name}`;  // Uncomment if you want to rename them
          // changeCount++;
        }
      }
    });
  }

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
      transformType: 'removeDeadCode',
      linesChanged: code.split('\n').length - newCode.split('\n').length,
      complexity: changeCount,
      timestamp: new Date().toISOString()
    }
  };
}

// Helper functions
function isExported(path: any): boolean {
  const program = path.findParent((p: any) => t.isProgram(p.node));
  if (!program) return false;
  
  const name = path.node.id?.name;
  if (!name) return false;
  
  // Check for export statements
  return program.node.body.some((stmt: t.Statement) => {
    if (t.isExportNamedDeclaration(stmt)) {
      if (stmt.declaration === path.node) return true;
      
      if (stmt.specifiers) {
        return stmt.specifiers.some(spec => 
          t.isExportSpecifier(spec) && 
          t.isIdentifier(spec.local) && 
          spec.local.name === name
        );
      }
    }
    
    if (t.isExportDefaultDeclaration(stmt)) {
      return stmt.declaration === path.node || 
             (t.isIdentifier(stmt.declaration) && stmt.declaration.name === name);
    }
    
    return false;
  });
}

function hasSideEffects(node: t.Expression): boolean {
  // Check for expressions that might have side effects
  if (t.isCallExpression(node)) return true;
  if (t.isNewExpression(node)) return true;
  if (t.isAssignmentExpression(node)) return true;
  if (t.isUpdateExpression(node)) return true;
  
  // Check for member expressions that might have getters
  if (t.isMemberExpression(node)) {
    return hasSideEffects(node.object as t.Expression);
  }
  
  // Arrays and objects with side effects in their elements
  if (t.isArrayExpression(node)) {
    return node.elements.some(el => el && hasSideEffects(el as t.Expression));
  }
  
  if (t.isObjectExpression(node)) {
    return node.properties.some(prop => {
      if (t.isObjectProperty(prop)) {
        return hasSideEffects(prop.value as t.Expression);
      }
      return false;
    });
  }
  
  return false;
}

function isUsedInClass(methodPath: any, methodName: string): boolean {
  const classPath = methodPath.findParent((p: any) => t.isClassDeclaration(p.node));
  if (!classPath) return false;
  
  let isUsed = false;
  
  traverse(classPath.node, {
    MemberExpression(path) {
      if (t.isIdentifier(path.node.property) && path.node.property.name === methodName) {
        isUsed = true;
        path.stop();
      }
    },
    
    CallExpression(path) {
      if (t.isMemberExpression(path.node.callee) && 
          t.isIdentifier(path.node.callee.property) && 
          path.node.callee.property.name === methodName) {
        isUsed = true;
        path.stop();
      }
    }
  });
  
  return isUsed;
}

function isRequiredEmptyBlock(path: any): boolean {
  const parent = path.parent;
  
  // Required empty blocks
  if (t.isCatchClause(parent)) return true;
  if (t.isTryStatement(parent) && parent.finalizer === path.node) return true;
  if (t.isIfStatement(parent)) return true;
  if (t.isWhileStatement(parent)) return true;
  if (t.isForStatement(parent)) return true;
  
  return false;
}
