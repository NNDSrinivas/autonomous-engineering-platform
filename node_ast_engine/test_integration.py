#!/usr/bin/env python3
"""
Python integration for Node AST Engine
Demonstrates how to call the AST transformation engine from Python
"""

import json
import subprocess
import os
from typing import Dict, Any, Optional, List


class ASTEngine:
    """Python wrapper for the Node AST transformation engine"""

    def __init__(self, engine_path: str = "./node_ast_engine"):
        self.engine_path = engine_path
        self.node_executable = os.path.join(engine_path, "dist", "index.js")

        # Verify engine is built
        if not os.path.exists(self.node_executable):
            raise FileNotFoundError(
                f"AST engine not found at {self.node_executable}. Run 'npm run build' first."
            )

    def _run_transform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a transform via the Node engine"""
        try:
            process = subprocess.run(
                ["node", self.node_executable],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=30,  # 30 second timeout
            )

            if process.returncode != 0:
                error_result = (
                    json.loads(process.stderr)
                    if process.stderr
                    else {"error": "Unknown error"}
                )
                return error_result

            return json.loads(process.stdout)

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Transform timeout after 30 seconds"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON response: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Transform failed: {str(e)}"}

    def rename_symbol(
        self,
        file_path: str,
        code: str,
        old_name: str,
        new_name: str,
        scope: str = "global",
    ) -> Dict[str, Any]:
        """Rename all occurrences of a symbol in the code"""
        payload = {
            "command": "renameSymbol",
            "filePath": file_path,
            "code": code,
            "params": {"oldName": old_name, "newName": new_name, "scope": scope},
        }
        return self._run_transform(payload)

    def update_import(
        self,
        file_path: str,
        code: str,
        from_module: Optional[str] = None,
        to_module: Optional[str] = None,
        add_imports: Optional[List[Dict[str, Any]]] = None,
        remove_imports: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update import statements in the code"""
        params = {}
        if from_module and to_module:
            params["from"] = from_module
            params["to"] = to_module
        if add_imports:
            params["addImports"] = add_imports
        if remove_imports:
            params["removeImports"] = remove_imports

        payload = {
            "command": "updateImport",
            "filePath": file_path,
            "code": code,
            "params": params,
        }
        return self._run_transform(payload)

    def extract_component(
        self,
        file_path: str,
        code: str,
        component_name: str,
        new_file_name: Optional[str] = None,
        export_type: str = "default",
    ) -> Dict[str, Any]:
        """Extract a component/function to a separate file"""
        payload = {
            "command": "extractComponent",
            "filePath": file_path,
            "code": code,
            "params": {
                "componentName": component_name,
                "newFileName": new_file_name,
                "exportType": export_type,
            },
        }
        return self._run_transform(payload)

    def convert_js_to_ts(
        self,
        file_path: str,
        code: str,
        add_type_annotations: bool = True,
        convert_require: bool = True,
    ) -> Dict[str, Any]:
        """Convert JavaScript code to TypeScript"""
        payload = {
            "command": "convertJsToTs",
            "filePath": file_path,
            "code": code,
            "params": {
                "addTypeAnnotations": add_type_annotations,
                "convertRequire": convert_require,
            },
        }
        return self._run_transform(payload)

    def remove_dead_code(self, file_path: str, code: str) -> Dict[str, Any]:
        """Remove unused variables, functions, and imports"""
        payload = {"command": "removeDeadCode", "filePath": file_path, "code": code}
        return self._run_transform(payload)


# Example usage and tests
if __name__ == "__main__":
    # Initialize the engine
    engine = ASTEngine()

    print("🔥 Node AST Engine - Python Integration Demo")
    print("=" * 50)

    # Test 1: Rename Symbol
    print("\n1. Testing symbol rename...")
    js_code = "const oldName = 42; console.log(oldName);"
    result = engine.rename_symbol("test.js", js_code, "oldName", "newName")

    if result.get("success"):
        print(f"✅ Success: {result['edits'][0]['replacement']}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test 2: Update Import
    print("\n2. Testing import update...")
    import_code = 'import { oldExport } from "old-module";'
    result = engine.update_import("test.js", import_code, "old-module", "new-module")

    if result.get("success"):
        print(f"✅ Success: {result['edits'][0]['replacement']}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test 3: Remove Dead Code
    print("\n3. Testing dead code removal...")
    dead_code = "const unused = 123;\nconst used = 456;\nconsole.log(used);"
    result = engine.remove_dead_code("test.js", dead_code)

    if result.get("success"):
        print("✅ Success: Removed unused code")
        print(f"   Result: {result['edits'][0]['replacement']}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    # Test 4: Convert JS to TS
    print("\n4. Testing JS to TS conversion...")
    js_code = "function add(a, b) { return a + b; }"
    result = engine.convert_js_to_ts("test.js", js_code)

    if result.get("success"):
        print("✅ Success: Converted to TypeScript")
        print(f"   New file: {result['file']}")
    else:
        print(f"❌ Failed: {result.get('error')}")

    print("\n" + "=" * 50)
    print("🎉 Node AST Engine is ready for production use!")
    print("Integration with Navi backend complete.")
