/**
 * Extract Component Transform  
 * Extracts React components, functions, or classes into separate files
 */

import traverse from "@babel/traverse";
import * as t from "@babel/types";
const { parseCode } = require("../utils/parse");
const { emit } = require("../utils/emit");
const path = require("path");
import { TransformResponse } from "../types";

export async function extractComponent(
  filePath: string,
  code: string,
  params: {
    componentName: string;
    newFileName?: string;
    includeImports?: boolean;  // Include necessary imports in extracted file
    exportType?: 'default' | 'named';  // How to export the extracted component
  }
): Promise<TransformResponse> {

  const ast = parseCode(code);
  let extractedNodes: t.Node[] = [];
  let extractedImports: t.ImportDeclaration[] = [];
  let componentFound = false;
  
  // Collect all imports that might be needed
  const allImports: t.ImportDeclaration[] = [];
  
  traverse(ast, {
    ImportDeclaration(path) {
      allImports.push(path.node);
    }
  });

  // Find and extract the target component/function
  traverse(ast, {
    // Function declarations
    FunctionDeclaration(path) {
      if (path.node.id?.name === params.componentName) {
        extractedNodes.push(path.node);
        componentFound = true;
        path.remove();
      }
    },
    
    // Arrow function variables (const Component = () => {})
    VariableDeclaration(path) {
      path.node.declarations.forEach((decl, index) => {
        if (t.isIdentifier(decl.id) && decl.id.name === params.componentName) {
          if (t.isArrowFunctionExpression(decl.init) || t.isFunctionExpression(decl.init)) {
            extractedNodes.push(path.node);
            componentFound = true;
            path.remove();
          }
        }
      });
    },
    
    // Class declarations
    ClassDeclaration(path) {
      if (path.node.id?.name === params.componentName) {
        extractedNodes.push(path.node);
        componentFound = true;
        path.remove();
      }
    },
    
    // Export declarations
    ExportNamedDeclaration(path) {
      if (path.node.declaration) {
        if (t.isFunctionDeclaration(path.node.declaration) && 
            path.node.declaration.id?.name === params.componentName) {
          extractedNodes.push(path.node);
          componentFound = true;
          path.remove();
        } else if (t.isClassDeclaration(path.node.declaration) && 
                   path.node.declaration.id?.name === params.componentName) {
          extractedNodes.push(path.node);
          componentFound = true;
          path.remove();
        } else if (t.isVariableDeclaration(path.node.declaration)) {
          path.node.declaration.declarations.forEach(decl => {
            if (t.isIdentifier(decl.id) && decl.id.name === params.componentName) {
              extractedNodes.push(path.node);
              componentFound = true;
              path.remove();
            }
          });
        }
      }
    },
    
    ExportDefaultDeclaration(path) {
      if ((t.isFunctionDeclaration(path.node.declaration) && 
           path.node.declaration.id?.name === params.componentName) ||
          (t.isClassDeclaration(path.node.declaration) && 
           path.node.declaration.id?.name === params.componentName) ||
          (t.isIdentifier(path.node.declaration) && 
           path.node.declaration.name === params.componentName)) {
        extractedNodes.push(path.node);
        componentFound = true;
        path.remove();
      }
    }
  });

  if (!componentFound) {
    throw new Error(`Component '${params.componentName}' not found in the file`);
  }

  // Determine imports needed for extracted component
  if (params.includeImports !== false) {
    const usedImports = findUsedImports(extractedNodes, allImports);
    extractedImports = usedImports;
  }

  // Generate new file content
  const newFileContent = generateExtractedFile(
    extractedNodes,
    extractedImports,
    params.componentName,
    params.exportType || 'default'
  );

  // Generate new file name
  const newFileName = params.newFileName || generateFileName(params.componentName, filePath);

  // Add import to original file
  const importPath = getRelativeImportPath(filePath, newFileName);
  const newImport = generateImportStatement(params.componentName, importPath, params.exportType || 'default');
  
  // Add import at the top of the original file
  ast.program.body.unshift(newImport);

  const modifiedCode = emit(ast);

  return {
    success: true,
    file: filePath,
    newFile: newFileName,
    newFileContent,
    edits: [
      {
        start: 0,
        end: code.length,
        replacement: modifiedCode
      }
    ],
    metadata: {
      transformType: 'extractComponent',
      linesChanged: code.split('\n').length - modifiedCode.split('\n').length + newFileContent.split('\n').length,
      complexity: extractedNodes.length,
      timestamp: new Date().toISOString()
    }
  };
}

function findUsedImports(extractedNodes: t.Node[], allImports: t.ImportDeclaration[]): t.ImportDeclaration[] {
  const usedIdentifiers = new Set<string>();
  
  // Collect all identifiers used in extracted code
  extractedNodes.forEach(node => {
    traverse(t.file(t.program([node as t.Statement])), {
      Identifier(path) {
        if (path.isReferencedIdentifier()) {
          usedIdentifiers.add(path.node.name);
        }
      }
    });
  });

  // Find imports that provide these identifiers
  return allImports.filter(importNode => {
    return importNode.specifiers.some(spec => {
      if (t.isImportDefaultSpecifier(spec)) {
        return usedIdentifiers.has(spec.local.name);
      } else if (t.isImportSpecifier(spec)) {
        return usedIdentifiers.has(spec.local.name);
      } else if (t.isImportNamespaceSpecifier(spec)) {
        return usedIdentifiers.has(spec.local.name);
      }
      return false;
    });
  });
}

function generateExtractedFile(
  nodes: t.Node[],
  imports: t.ImportDeclaration[],
  componentName: string,
  exportType: 'default' | 'named'
): string {
  const statements: t.Statement[] = [];
  
  // Add imports
  statements.push(...imports);
  
  // Add extracted code
  statements.push(...(nodes as t.Statement[]));
  
  // Add export if not already exported
  const hasExport = nodes.some(node => 
    t.isExportNamedDeclaration(node) || t.isExportDefaultDeclaration(node)
  );
  
  if (!hasExport) {
    if (exportType === 'default') {
      statements.push(t.exportDefaultDeclaration(t.identifier(componentName)));
    } else {
      statements.push(t.exportNamedDeclaration(null, [
        t.exportSpecifier(t.identifier(componentName), t.identifier(componentName))
      ]));
    }
  }
  
  const program = t.program(statements);
  return emit(program);
}

function generateFileName(componentName: string, originalFilePath: string): string {
  const ext = path.extname(originalFilePath);
  const dir = path.dirname(originalFilePath);
  return path.join(dir, `${componentName}${ext}`);
}

function getRelativeImportPath(fromFile: string, toFile: string): string {
  const relativePath = path.relative(path.dirname(fromFile), toFile);
  // Remove extension and normalize path separators
  const withoutExt = relativePath.replace(/\.(tsx?|jsx?)$/, '');
  // Ensure relative imports start with ./
  return withoutExt.startsWith('.') ? withoutExt : `./${withoutExt}`;
}

function generateImportStatement(
  componentName: string, 
  importPath: string, 
  exportType: 'default' | 'named'
): t.ImportDeclaration {
  const specifiers = exportType === 'default' 
    ? [t.importDefaultSpecifier(t.identifier(componentName))]
    : [t.importSpecifier(t.identifier(componentName), t.identifier(componentName))];
    
  return t.importDeclaration(specifiers, t.stringLiteral(importPath));
}

module.exports = { extractComponent };
