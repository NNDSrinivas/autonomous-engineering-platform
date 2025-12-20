/**
 * Convert JS to TS Transform
 * Converts JavaScript files to TypeScript with basic type annotations
 */

import traverse from "@babel/traverse";
import * as t from "@babel/types";
import { TransformResponse } from "../types";
const { parseCode } = require("../utils/parse");
const { emit } = require("../utils/emit");
const path = require("path");

export async function convertJsToTs(
  filePath: string,
  code: string,
  params: {
    addTypeAnnotations?: boolean;  // Add basic type annotations
    strictMode?: boolean;          // Use strict TypeScript options
    convertRequire?: boolean;      // Convert require() to import
    addInterfaces?: boolean;       // Generate interfaces for object types
  } = {}
): Promise<TransformResponse> {

  const ast = parseCode(code);
  let changeCount = 0;
  
  // Convert require() calls to import statements
  if (params.convertRequire !== false) {
    const newImports: t.ImportDeclaration[] = [];
    
    traverse(ast, {
      CallExpression(path) {
        if (t.isIdentifier(path.node.callee) && path.node.callee.name === 'require') {
          const arg = path.node.arguments[0];
          if (t.isStringLiteral(arg)) {
            // Handle different require patterns
            const parent = path.parent;
            
            if (t.isVariableDeclarator(parent) && t.isIdentifier(parent.id)) {
              // const module = require('module')
              const importDecl = t.importDeclaration(
                [t.importDefaultSpecifier(t.identifier(parent.id.name))],
                t.stringLiteral(arg.value)
              );
              newImports.push(importDecl);
              
              // Remove the variable declarator
              const varDecl = path.findParent(p => t.isVariableDeclaration(p.node));
              if (varDecl) {
                varDecl.remove();
                changeCount++;
              }
            } else if (t.isAssignmentExpression(parent) && t.isIdentifier(parent.left)) {
              // module = require('module')
              const importDecl = t.importDeclaration(
                [t.importDefaultSpecifier(t.identifier(parent.left.name))],
                t.stringLiteral(arg.value)
              );
              newImports.push(importDecl);
              
              const expressionStmt = path.findParent(p => t.isExpressionStatement(p.node));
              if (expressionStmt) {
                expressionStmt.remove();
                changeCount++;
              }
            }
          }
        }
      }
    });
    
    // Add new imports at the top
    if (newImports.length > 0) {
      ast.program.body.unshift(...newImports);
    }
  }

  // Add basic type annotations
  if (params.addTypeAnnotations) {
    traverse(ast, {
      FunctionDeclaration(path) {
        // Add return type annotation
        if (!path.node.returnType) {
          const returnType = inferReturnType(path.node);
          if (returnType) {
            path.node.returnType = t.tsTypeAnnotation(returnType);
            changeCount++;
          }
        }
        
        // Add parameter type annotations
        path.node.params.forEach((param, index) => {
          if (t.isIdentifier(param) && !param.typeAnnotation) {
            const paramType = inferParameterType(param, path.node, index);
            if (paramType) {
              param.typeAnnotation = t.tsTypeAnnotation(paramType);
              changeCount++;
            }
          }
        });
      },
      
      ArrowFunctionExpression(path) {
        // Add return type for arrow functions
        if (!path.node.returnType) {
          const returnType = inferReturnType(path.node);
          if (returnType) {
            path.node.returnType = t.tsTypeAnnotation(returnType);
            changeCount++;
          }
        }
      },
      
      VariableDeclarator(path) {
        // Add type annotations for variables
        if (t.isIdentifier(path.node.id) && !path.node.id.typeAnnotation && path.node.init) {
          const varType = inferVariableType(path.node.init);
          if (varType) {
            path.node.id.typeAnnotation = t.tsTypeAnnotation(varType);
            changeCount++;
          }
        }
      },
      
      ClassDeclaration(path) {
        // Add property type annotations
        path.node.body.body.forEach(member => {
          if (t.isClassProperty(member) && t.isIdentifier(member.key) && !member.typeAnnotation) {
            const propType = member.value ? inferVariableType(member.value) : t.tsAnyKeyword();
            if (propType) {
              member.typeAnnotation = t.tsTypeAnnotation(propType);
              changeCount++;
            }
          }
        });
      }
    });
  }

  // Convert module.exports to export statements
  traverse(ast, {
    AssignmentExpression(path) {
      if (t.isMemberExpression(path.node.left) &&
          t.isIdentifier(path.node.left.object) && path.node.left.object.name === 'module' &&
          t.isIdentifier(path.node.left.property) && path.node.left.property.name === 'exports') {
        
        // module.exports = something
        const exportDecl = t.exportDefaultDeclaration(path.node.right);
        const program = path.findParent(p => t.isProgram(p.node));
        if (program) {
          const stmt = path.findParent(p => t.isExpressionStatement(p.node));
          if (stmt) {
            stmt.replaceWith(exportDecl);
            changeCount++;
          }
        }
      } else if (t.isMemberExpression(path.node.left) &&
                 t.isMemberExpression(path.node.left.object) &&
                 t.isIdentifier(path.node.left.object.object) && path.node.left.object.object.name === 'module' &&
                 t.isIdentifier(path.node.left.object.property) && path.node.left.object.property.name === 'exports') {
        
        // module.exports.something = value
        if (t.isIdentifier(path.node.left.property)) {
          const exportDecl = t.exportNamedDeclaration(
            t.variableDeclaration('const', [
              t.variableDeclarator(path.node.left.property, path.node.right)
            ])
          );
          const stmt = path.findParent(p => t.isExpressionStatement(p.node));
          if (stmt) {
            stmt.replaceWith(exportDecl);
            changeCount++;
          }
        }
      }
    }
  });

  // Generate new file path with .ts/.tsx extension
  const originalExt = path.extname(filePath);
  const newExt = originalExt === '.jsx' ? '.tsx' : '.ts';
  const newFilePath = filePath.replace(/\.jsx?$/, newExt);

  const newCode = emit(ast);
  
  return {
    success: true,
    file: newFilePath,  // Return new TypeScript file path
    edits: [
      {
        start: 0,
        end: code.length,
        replacement: newCode
      }
    ],
    metadata: {
      transformType: 'convertJsToTs',
      linesChanged: Math.abs(newCode.split('\n').length - code.split('\n').length),
      complexity: changeCount,
      timestamp: new Date().toISOString()
    }
  };
}

// Helper functions for type inference
function inferReturnType(func: t.Function): t.TSType | null {
  if (!func.body || !t.isBlockStatement(func.body)) {
    return null;
  }
  
  // Look for return statements
  const returnStatements: t.ReturnStatement[] = [];
  traverse(t.file(t.program([func.body])), {
    ReturnStatement(path) {
      returnStatements.push(path.node);
    }
  });
  
  if (returnStatements.length === 0) {
    return t.tsVoidKeyword();
  }
  
  // Analyze return values
  const returnTypes = returnStatements.map(stmt => {
    if (!stmt.argument) return t.tsVoidKeyword();
    return inferExpressionType(stmt.argument);
  });
  
  // If all returns are the same type, use that
  const firstType = returnTypes[0];
  if (returnTypes.every(type => 
    (t.isTSStringKeyword(type) && t.isTSStringKeyword(firstType)) ||
    (t.isTSNumberKeyword(type) && t.isTSNumberKeyword(firstType)) ||
    (t.isTSBooleanKeyword(type) && t.isTSBooleanKeyword(firstType))
  )) {
    return firstType;
  }
  
  return t.tsUnionType(returnTypes);
}

function inferParameterType(param: t.Identifier, func: t.Function, index: number): t.TSType | null {
  // Basic inference based on parameter name
  const paramName = param.name.toLowerCase();
  
  if (paramName.includes('count') || paramName.includes('index') || paramName.includes('id')) {
    return t.tsNumberKeyword();
  }
  
  if (paramName.includes('name') || paramName.includes('title') || paramName.includes('text')) {
    return t.tsStringKeyword();
  }
  
  if (paramName.includes('is') || paramName.includes('has') || paramName.includes('can')) {
    return t.tsBooleanKeyword();
  }
  
  // Default to any for now
  return t.tsAnyKeyword();
}

function inferVariableType(init: t.Expression): t.TSType | null {
  return inferExpressionType(init);
}

function inferExpressionType(expr: t.Expression): t.TSType {
  if (t.isStringLiteral(expr)) {
    return t.tsStringKeyword();
  }
  
  if (t.isNumericLiteral(expr)) {
    return t.tsNumberKeyword();
  }
  
  if (t.isBooleanLiteral(expr)) {
    return t.tsBooleanKeyword();
  }
  
  if (t.isArrayExpression(expr)) {
    if (expr.elements.length > 0 && expr.elements[0]) {
      const elementType = inferExpressionType(expr.elements[0] as t.Expression);
      return t.tsArrayType(elementType);
    }
    return t.tsArrayType(t.tsAnyKeyword());
  }
  
  if (t.isObjectExpression(expr)) {
    return t.tsObjectKeyword();
  }
  
  if (t.isArrowFunctionExpression(expr) || t.isFunctionExpression(expr)) {
    return t.tsTypeReference(t.identifier('Function'));
  }
  
  return t.tsAnyKeyword();
}

module.exports = { convertJsToTs };
