"""
Comprehensive tests for the multi-language debugger.

Tests error parsing for 15+ programming languages including:
- Runtime errors
- Compiler errors
- Linter outputs
- Test failures
- Build system errors
- Memory issues
"""

import pytest


class TestPythonParsing:
    """Test Python error parsing."""

    @pytest.mark.asyncio
    async def test_python_runtime_error(self):
        """Test Python traceback parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        traceback = """
Traceback (most recent call last):
  File "/app/main.py", line 10, in main
    result = process_data(data)
  File "/app/processor.py", line 25, in process_data
    return data["key"]
KeyError: 'key'
"""

        errors = ComprehensiveDebugger._parse_python_error(traceback, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.language == "python"
        assert error.error_type == "KeyError"
        assert len(error.stack_trace) >= 2
        assert len(error.suggestions) >= 1

    @pytest.mark.asyncio
    async def test_python_syntax_error(self):
        """Test Python syntax error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
  File "test.py", line 5
    print("hello"
               ^
SyntaxError: unexpected EOF while parsing
"""

        errors = ComprehensiveDebugger._parse_python_error(output, ".")

        assert len(errors) >= 1
        assert any(e.error_type == "SyntaxError" for e in errors)

    @pytest.mark.asyncio
    async def test_pytest_output(self):
        """Test pytest failure parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
FAILED tests/test_app.py::test_login - AssertionError: expected True
FAILED tests/test_app.py::test_signup - ValueError: invalid email
"""

        errors = ComprehensiveDebugger._parse_pytest_output(output, ".")

        assert len(errors) >= 2
        assert all(e.category.value == "test" for e in errors)

    @pytest.mark.asyncio
    async def test_mypy_output(self):
        """Test mypy output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
app.py:10: error: Incompatible types in assignment (expression has type "str", variable has type "int")
app.py:15:5: error: Function is missing a return type annotation
app.py:20: warning: Unused variable "x"
"""

        errors = ComprehensiveDebugger._parse_mypy_output(output, ".")

        assert len(errors) >= 2
        assert all(e.category.value == "type" for e in errors)

    @pytest.mark.asyncio
    async def test_pylint_output(self):
        """Test pylint output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
app.py:10:0: E0001: Syntax error in type comment (syntax-error)
app.py:15:4: W0611: Unused import os (unused-import)
app.py:20:0: C0114: Missing module docstring (missing-module-docstring)
"""

        errors = ComprehensiveDebugger._parse_pylint_output(output, ".")

        assert len(errors) >= 3
        assert any(e.severity == "error" for e in errors)
        assert any(e.severity == "warning" for e in errors)


class TestJavaScriptParsing:
    """Test JavaScript/TypeScript error parsing."""

    @pytest.mark.asyncio
    async def test_javascript_runtime_error(self):
        """Test JavaScript error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
TypeError: Cannot read property 'map' of undefined
    at processItems (/app/utils.js:15:20)
    at main (/app/index.js:42:10)
    at Object.<anonymous> (/app/index.js:50:1)
"""

        errors = ComprehensiveDebugger._parse_javascript_error(output, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.language == "javascript"
        assert error.error_type == "TypeError"
        assert len(error.stack_trace) >= 2

    @pytest.mark.asyncio
    async def test_typescript_compiler_error(self):
        """Test TypeScript compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
src/app.ts(10,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/app.ts(15,10): error TS2339: Property 'foo' does not exist on type 'Bar'.
src/utils.ts(5,1): warning TS6133: 'x' is declared but its value is never read.
"""

        errors = ComprehensiveDebugger._parse_typescript_error(output, ".")

        assert len(errors) >= 3
        assert all(e.language == "typescript" for e in errors)
        assert any(e.error_code == "TS2322" for e in errors)

    @pytest.mark.asyncio
    async def test_eslint_output(self):
        """Test ESLint output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
/app/src/app.js
  10:5   error  'foo' is not defined          no-undef
  15:10  warning  Unexpected console statement  no-console

/app/src/utils.js
  5:1  error  Missing semicolon  semi
"""

        errors = ComprehensiveDebugger._parse_eslint_output(output, ".")

        assert len(errors) >= 3
        assert any(e.error_code == "no-undef" for e in errors)

    @pytest.mark.asyncio
    async def test_jest_output(self):
        """Test Jest test output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
● Login Component › should render login form

  expect(received).toBe(expected)

  Expected: true
  Received: false
"""

        errors = ComprehensiveDebugger._parse_jest_output(output, ".")

        assert len(errors) >= 1
        assert errors[0].category.value == "test"


class TestGoParsing:
    """Test Go error parsing."""

    @pytest.mark.asyncio
    async def test_go_panic(self):
        """Test Go panic parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.processData(0xc0000b4000, 0x3, 0x3, 0x5)
        /app/main.go:25 +0x123
main.main()
        /app/main.go:15 +0x45
"""

        errors = ComprehensiveDebugger._parse_go_error(output, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.language == "go"
        assert error.error_type == "panic"
        assert "index out of range" in error.message
        assert len(error.stack_trace) >= 1

    @pytest.mark.asyncio
    async def test_go_compiler_error(self):
        """Test Go compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
./main.go:10:5: undefined: foo
./main.go:15:10: cannot use "hello" (type string) as type int
./utils.go:5:1: imported and not used: "fmt"
"""

        errors = ComprehensiveDebugger._parse_go_compiler_error(output, ".")

        assert len(errors) >= 3
        assert all(e.language == "go" for e in errors)
        assert all(e.category.value == "compile" for e in errors)

    @pytest.mark.asyncio
    async def test_go_test_output(self):
        """Test go test output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
--- FAIL: TestProcessData (0.01s)
    main_test.go:15: expected 10, got 5
--- FAIL: TestValidate (0.02s)
    validate_test.go:20: validation failed
"""

        errors = ComprehensiveDebugger._parse_go_test_output(output, ".")

        assert len(errors) >= 2
        assert all(e.category.value == "test" for e in errors)


class TestRustParsing:
    """Test Rust error parsing."""

    @pytest.mark.asyncio
    async def test_rust_panic(self):
        """Test Rust panic parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
thread 'main' panicked at 'called `Option::unwrap()` on a `None` value', src/main.rs:10:5
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
"""

        errors = ComprehensiveDebugger._parse_rust_error(output, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.language == "rust"
        assert "unwrap" in error.message
        assert error.file_path == "src/main.rs"

    @pytest.mark.asyncio
    async def test_rustc_error(self):
        """Test Rust compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
error[E0382]: borrow of moved value: `x`
  --> src/main.rs:5:10
   |
3  |     let x = String::new();
   |         - move occurs because `x` has type `String`
4  |     let y = x;
   |             - value moved here
5  |     println!("{}", x);
   |                    ^ value borrowed here after move
"""

        errors = ComprehensiveDebugger._parse_rustc_error(output, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.error_code == "E0382"

    @pytest.mark.asyncio
    async def test_cargo_test_output(self):
        """Test cargo test output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
running 3 tests
test tests::test_add ... ok
test tests::test_sub ... FAILED
test tests::test_mul ... FAILED

failures:
    tests::test_sub
    tests::test_mul
"""

        errors = ComprehensiveDebugger._parse_cargo_test_output(output, ".")

        assert len(errors) >= 2
        assert all(e.category.value == "test" for e in errors)


class TestJavaParsing:
    """Test Java/Kotlin error parsing."""

    @pytest.mark.asyncio
    async def test_java_exception(self):
        """Test Java exception parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.UserService.getUser(UserService.java:42)
    at com.example.Controller.handleRequest(Controller.java:28)
    at org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:897)
Caused by: java.lang.IllegalStateException: Database connection not initialized
    at com.example.Database.connect(Database.java:15)
"""

        errors = ComprehensiveDebugger._parse_java_error(output, ".")

        assert len(errors) >= 1
        error = errors[0]
        assert error.language == "java"
        assert "NullPointerException" in error.error_type
        assert len(error.stack_trace) >= 3
        assert len(error.related_errors) >= 1

    @pytest.mark.asyncio
    async def test_javac_error(self):
        """Test javac compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
App.java:10: error: cannot find symbol
        foo.bar();
           ^
  symbol:   method bar()
  location: variable foo of type Foo
App.java:15: warning: [deprecation] oldMethod() in Utils has been deprecated
"""

        errors = ComprehensiveDebugger._parse_javac_error(output, ".")

        assert len(errors) >= 1
        assert any(e.severity == "error" for e in errors)

    @pytest.mark.asyncio
    async def test_maven_error(self):
        """Test Maven build error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
[ERROR] /project/src/main/java/App.java:[10,5] cannot find symbol
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:3.8.1:compile
"""

        errors = ComprehensiveDebugger._parse_maven_error(output, ".")

        assert len(errors) >= 1
        assert all(e.category.value == "build" for e in errors)


class TestCCppParsing:
    """Test C/C++ error parsing."""

    @pytest.mark.asyncio
    async def test_segfault(self):
        """Test segmentation fault detection."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
Segmentation fault (core dumped)
"""

        errors = ComprehensiveDebugger._parse_c_cpp_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].error_type == "SegmentationFault"
        assert len(errors[0].suggestions) >= 1

    @pytest.mark.asyncio
    async def test_gcc_error(self):
        """Test GCC compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
main.c:10:5: error: implicit declaration of function 'foo'
main.c:15:10: warning: unused variable 'x' [-Wunused-variable]
main.cpp:20:8: error: 'Bar' was not declared in this scope
"""

        errors = ComprehensiveDebugger._parse_gcc_clang_error(output, ".")

        assert len(errors) >= 3
        assert any(e.language == "c" for e in errors)
        assert any(e.language == "cpp" for e in errors)

    @pytest.mark.asyncio
    async def test_valgrind_output(self):
        """Test Valgrind output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
==12345== 40 bytes in 1 blocks are definitely lost in loss record 1 of 1
==12345==    at 0x4C2FB0F: malloc (in /usr/lib/valgrind/vgpreload_memcheck-amd64-linux.so)
==12345==    by 0x108681: main (main.c:10)
==12345== Invalid read of size 4
==12345==    at 0x108690: process (utils.c:15)
"""

        errors = ComprehensiveDebugger._parse_valgrind_output(output, ".")

        assert len(errors) >= 2
        assert any(e.error_type == "MemoryLeak" for e in errors)
        assert any(e.error_type == "InvalidRead" for e in errors)

    @pytest.mark.asyncio
    async def test_asan_output(self):
        """Test AddressSanitizer output parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000014
"""

        errors = ComprehensiveDebugger._parse_sanitizer_output(output, ".")

        assert len(errors) >= 1
        assert "heap-buffer-overflow" in errors[0].error_type


class TestOtherLanguages:
    """Test other language parsers."""

    @pytest.mark.asyncio
    async def test_ruby_error(self):
        """Test Ruby exception parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
NoMethodError: undefined method `name' for nil:NilClass
    from /app/models/user.rb:15:in `display_name'
    from /app/controllers/users_controller.rb:28:in `show'
"""

        errors = ComprehensiveDebugger._parse_ruby_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "ruby"
        assert "NoMethodError" in errors[0].error_type

    @pytest.mark.asyncio
    async def test_php_error(self):
        """Test PHP error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
Fatal error: Uncaught TypeError: count(): Argument #1 must be countable in /var/www/app/src/UserService.php on line 45

Stack trace:
#0 /var/www/app/src/UserService.php(45): count(NULL)
#1 /var/www/app/src/Controller.php(28): UserService->getUsers()
"""

        errors = ComprehensiveDebugger._parse_php_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "php"
        assert errors[0].line == 45

    @pytest.mark.asyncio
    async def test_csharp_exception(self):
        """Test C# exception parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
System.NullReferenceException: Object reference not set to an instance of an object.
   at MyApp.Services.UserService.GetUser(Int32 id) in C:\\Projects\\MyApp\\Services\\UserService.cs:line 45
   at MyApp.Controllers.UserController.Get(Int32 id) in C:\\Projects\\MyApp\\Controllers\\UserController.cs:line 22
"""

        errors = ComprehensiveDebugger._parse_csharp_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "csharp"
        assert "NullReferenceException" in errors[0].error_type

    @pytest.mark.asyncio
    async def test_swift_error(self):
        """Test Swift error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
Fatal error: Unexpectedly found nil while unwrapping an Optional value
"""

        errors = ComprehensiveDebugger._parse_swift_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "swift"

    @pytest.mark.asyncio
    async def test_scala_error(self):
        """Test Scala compiler error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
App.scala:10: error: type mismatch;
 found   : String
 required: Int
"""

        errors = ComprehensiveDebugger._parse_scala_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "scala"

    @pytest.mark.asyncio
    async def test_elixir_error(self):
        """Test Elixir error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
** (CompileError) lib/app.ex:10: undefined function foo/1
"""

        errors = ComprehensiveDebugger._parse_elixir_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "elixir"

    @pytest.mark.asyncio
    async def test_haskell_error(self):
        """Test Haskell/GHC error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
Main.hs:10:5: error:
    • Variable not in scope: foo :: Int -> Int
"""

        errors = ComprehensiveDebugger._parse_haskell_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "haskell"

    @pytest.mark.asyncio
    async def test_dart_error(self):
        """Test Dart analyzer error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
lib/main.dart:10:5 • The argument type 'String' can't be assigned to the parameter type 'int' • argument_type_not_assignable
"""

        errors = ComprehensiveDebugger._parse_dart_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "dart"


class TestBuildSystemParsing:
    """Test build system error parsing."""

    @pytest.mark.asyncio
    async def test_npm_error(self):
        """Test npm error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /app/package.json
npm ERR! errno -2
npm ERR! enoent ENOENT: no such file or directory
"""

        errors = ComprehensiveDebugger._parse_npm_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].category.value == "build"

    @pytest.mark.asyncio
    async def test_pip_error(self):
        """Test pip error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
ERROR: Could not find a version that satisfies the requirement nonexistent-package
ERROR: No matching distribution found for nonexistent-package
"""

        errors = ComprehensiveDebugger._parse_pip_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "python"

    @pytest.mark.asyncio
    async def test_cargo_error(self):
        """Test Cargo build error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
error[E0433]: failed to resolve: use of undeclared crate or module `foo`
error: aborting due to previous error
"""

        errors = ComprehensiveDebugger._parse_cargo_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].language == "rust"

    @pytest.mark.asyncio
    async def test_cmake_error(self):
        """Test CMake error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
CMake Error at CMakeLists.txt:10 (find_package):
  Could not find a package configuration file provided by "Boost"
"""

        errors = ComprehensiveDebugger._parse_cmake_error(output, ".")

        assert len(errors) >= 1
        assert errors[0].category.value == "build"

    @pytest.mark.asyncio
    async def test_make_error(self):
        """Test Make error parsing."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        output = """
make: *** [Makefile:10: build] Error 2
"""

        errors = ComprehensiveDebugger._parse_make_error(output, ".")

        assert len(errors) >= 1
        assert "build" in errors[0].message


class TestComprehensiveAnalysis:
    """Test comprehensive error analysis."""

    @pytest.mark.asyncio
    async def test_full_analysis(self):
        """Test full comprehensive analysis."""
        from backend.services.comprehensive_debugger import analyze_errors

        error_output = """
Traceback (most recent call last):
  File "app.py", line 10, in main
    result = process()
TypeError: process() missing 1 required argument
"""

        result = await analyze_errors(error_output, ".")

        assert result["success"]
        assert len(result["errors"]) >= 1
        assert "summary" in result
        assert "suggested_commands" in result

    @pytest.mark.asyncio
    async def test_integration_with_project_analyzer(self):
        """Test integration with ProjectAnalyzer."""
        from backend.services.navi_brain import ProjectAnalyzer

        error_output = """
TypeError: Cannot read property 'length' of undefined
    at processItems (/app/utils.js:15:20)
"""

        result = await ProjectAnalyzer.analyze_error_comprehensive(".", error_output)

        assert isinstance(result, dict)
        if result.get("success"):
            assert "errors" in result or "warnings" in result


class TestAutoFixes:
    """Test auto-fix generation."""

    @pytest.mark.asyncio
    async def test_python_import_fix(self):
        """Test Python import error auto-fix."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        error = {
            "language": "python",
            "error_type": "ModuleNotFoundError",
            "message": "No module named 'requests'",
        }

        fix = ComprehensiveDebugger._get_auto_fix(error, ".")

        assert fix is not None
        assert "pip install" in fix.get("command", "")
        assert "requests" in fix.get("command", "")

    @pytest.mark.asyncio
    async def test_npm_install_fix(self):
        """Test JavaScript module install auto-fix."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger

        error = {
            "language": "javascript",
            "error_type": "ModuleNotFoundError",
            "message": "Cannot find module 'lodash'",
        }

        fix = ComprehensiveDebugger._get_auto_fix(error, ".")

        assert fix is not None
        assert "npm install" in fix.get("command", "")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("COMPREHENSIVE DEBUGGER TEST SUITE")
    print("=" * 60)

    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
