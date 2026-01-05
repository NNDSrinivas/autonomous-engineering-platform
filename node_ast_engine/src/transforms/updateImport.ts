/**
 * Update Import Transform
 * Updates import paths and import specifiers (from/to module renaming, named import changes)
 */

const traverse = require("@babel/traverse").default;
const t = require("@babel/types");
const { parseCode } = require("../utils/parse");
const { emit } = require("../utils/emit");
import { TransformResponse } from "../types";

export async function updateImport(
  filePath: string,
  code: string,
  params: {
    from?: string;        // Old module path
    to?: string;          // New module path  
    addImports?: Array<{  // Add new named imports
      name: string;
      alias?: string;
      isDefault?: boolean;
    }>;
    removeImports?: string[];  // Remove named imports by name
    updateImports?: Array<{    // Update existing imports
      oldName: string;
      newName: string;
      alias?: string;
    }>;
  }
): Promise<TransformResponse> {

  const ast = parseCode(code);
  let changeCount = 0;

  traverse(ast, {
    ImportDeclaration(path) {
      let modified = false;
      
      // Update module path
      if (params.from && params.to && path.node.source.value === params.from) {
        path.node.source = t.stringLiteral(params.to);
        changeCount++;
        modified = true;
      }
      
      // Only modify imports from the target module (or all if no from specified)
      const shouldModifyThisImport = !params.from || path.node.source.value === params.from || path.node.source.value === params.to;
      
      if (shouldModifyThisImport) {
        
        // Remove specified imports
        if (params.removeImports && params.removeImports.length > 0) {
          path.node.specifiers = path.node.specifiers.filter(spec => {
            if (t.isImportSpecifier(spec)) {
              const importName = t.isIdentifier(spec.imported) ? spec.imported.name : spec.imported.value;
              if (params.removeImports!.includes(importName)) {
                changeCount++;
                modified = true;
                return false;
              }
            } else if (t.isImportDefaultSpecifier(spec) && params.removeImports!.includes('default')) {
              changeCount++;
              modified = true;
              return false;
            }
            return true;
          });
        }
        
        // Update existing imports
        if (params.updateImports) {
          params.updateImports.forEach(update => {
            path.node.specifiers.forEach(spec => {
              if (t.isImportSpecifier(spec)) {
                const importName = t.isIdentifier(spec.imported) ? spec.imported.name : spec.imported.value;
                if (importName === update.oldName) {
                  spec.imported = t.identifier(update.newName);
                  if (update.alias) {
                    spec.local = t.identifier(update.alias);
                  }
                  changeCount++;
                  modified = true;
                }
              }
            });
          });
        }
        
        // Add new imports
        if (params.addImports) {
          params.addImports.forEach(newImport => {
            // Check if import already exists
            const exists = path.node.specifiers.some(spec => {
              if (newImport.isDefault && t.isImportDefaultSpecifier(spec)) {
                return true;
              }
              if (t.isImportSpecifier(spec)) {
                const importName = t.isIdentifier(spec.imported) ? spec.imported.name : spec.imported.value;
                return importName === newImport.name;
              }
              return false;
            });
            
            if (!exists) {
              if (newImport.isDefault) {
                const defaultSpec = t.importDefaultSpecifier(t.identifier(newImport.alias || newImport.name));
                path.node.specifiers.unshift(defaultSpec);
              } else {
                const importSpec = t.importSpecifier(
                  t.identifier(newImport.alias || newImport.name),
                  t.identifier(newImport.name)
                );
                path.node.specifiers.push(importSpec);
              }
              changeCount++;
              modified = true;
            }
          });
        }
        
        // Remove import declaration if no specifiers remain
        if (path.node.specifiers.length === 0) {
          path.remove();
          changeCount++;
          modified = true;
        }
      }
    }
  });
  
  // Add completely new import statements if needed
  if (params.addImports && params.to && !params.from) {
    const newImportSpecifiers: any[] = [];
    let defaultImport: any | null = null;
    
    params.addImports.forEach(imp => {
      if (imp.isDefault) {
        defaultImport = t.importDefaultSpecifier(t.identifier(imp.alias || imp.name));
      } else {
        newImportSpecifiers.push(
          t.importSpecifier(
            t.identifier(imp.alias || imp.name),
            t.identifier(imp.name)
          )
        );
      }
    });
    
    const specifiers = [
      ...(defaultImport ? [defaultImport] : []),
      ...newImportSpecifiers
    ];
    
    if (specifiers.length > 0) {
      const newImportDeclaration = t.importDeclaration(
        specifiers,
        t.stringLiteral(params.to)
      );
      
      // Add at the top of the file after other imports
      const program = ast.program;
      const lastImportIndex = program.body.findIndex(node => !t.isImportDeclaration(node));
      const insertIndex = lastImportIndex === -1 ? program.body.length : lastImportIndex;
      
      program.body.splice(insertIndex, 0, newImportDeclaration);
      changeCount++;
    }
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
      transformType: 'updateImport',
      linesChanged: Math.abs(newCode.split('\n').length - code.split('\n').length),
      complexity: changeCount,
      timestamp: new Date().toISOString()
    }
  };
}

module.exports = { updateImport };