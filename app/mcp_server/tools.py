import ast
import subprocess
import tempfile
import textwrap
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize the server
mcp = FastMCP("SentinelOps_Sandbox")

# Define the root directory to prevent the LLM from escaping the project folder
PROJECT_ROOT = Path("/app/workspace").resolve()


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: list_project_files
# Gives the LLM a structural map of the codebase before it starts digging.
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def list_project_files(subdir: str = "") -> str:
    """
    Returns a tree of all Python files in the project (or a subdirectory).
    Use this first to understand the structure before reading specific files.
    Args:
        subdir: Optional subdirectory to list, relative to project root (e.g. 'app/api').
    """
    target = (PROJECT_ROOT / subdir).resolve() if subdir else PROJECT_ROOT

    if not target.is_relative_to(PROJECT_ROOT):
        return "Error: Access denied. Cannot list outside project root."

    py_files = sorted(target.rglob("*.py"))
    if not py_files:
        return "No Python files found."

    lines = []
    for f in py_files:
        relative = f.relative_to(PROJECT_ROOT)
        lines.append(str(relative))

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: find_definition
# Semantic AST-based lookup — finds the EXACT source of a function or class.
# This replaces grep and eliminates the noise problem entirely.
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def find_definition(symbol_name: str) -> str:
    """
    Finds and returns the exact source code of a function or class definition
    by name. Searches the entire project using Python's AST parser.
    Use this instead of searching for keywords — it finds definitions precisely.
    Args:
        symbol_name: The exact function or class name to find (e.g. 'create_pull_request').
    """
    results = []

    for py_file in PROJECT_ROOT.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name != symbol_name:
                continue

            # Extract the source lines for this node
            start = node.lineno - 1
            end = node.end_lineno
            definition_src = "\n".join(source_lines[start:end])
            relative_path = py_file.relative_to(PROJECT_ROOT)
            results.append(
                f"### Found in: {relative_path} (lines {node.lineno}–{node.end_lineno})\n"
                f"```python\n{definition_src}\n```"
            )

    if not results:
        return f"No definition found for '{symbol_name}' in the project."

    return "\n\n".join(results)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3: read_file (unchanged — still useful for reading full files)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def read_file(file_path: str) -> str:
    """
    Reads the full contents of a specific file in the codebase.
    Use find_definition first if you only need one function.
    Args:
        file_path: Path to the file, relative to project root (e.g. 'app/api/webhooks.py').
    """
    target = (PROJECT_ROOT / file_path).resolve()

    if not target.is_relative_to(PROJECT_ROOT):
        return "Error: Access denied. Cannot read outside project root."

    try:
        return target.read_text(encoding="utf-8")
    except OSError as e:
        return f"Error reading file: {e!s}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4: apply_patch
# Surgically replaces a specific function in a file rather than overwriting
# the whole file — dramatically reduces risk of corrupting surrounding code.
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def apply_patch(file_path: str, function_name: str, new_function_source: str) -> str:
    """
    Surgically replaces a single function inside a file with new source code.
    PREFER this over write_file — it is safer because it only touches the
    function that needs to be fixed and leaves everything else unchanged.
    Args:
        file_path: Path to the file to patch, relative to project root.
        function_name: The exact name of the function to replace.
        new_function_source: The complete new source code for the function.
    """
    target = (PROJECT_ROOT / file_path).resolve()

    if not target.is_relative_to(PROJECT_ROOT):
        return "Error: Access denied. Cannot write outside project root."

    try:
        source = target.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except OSError as e:
        return f"Error reading file: {e!s}"
    except SyntaxError as e:
        return f"Syntax error in existing file, cannot parse: {e!s}"

    source_lines = source.splitlines(keepends=True)

    # Find the target function node
    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target_node = node
            break

    if not target_node:
        return f"Error: Function '{function_name}' not found in {file_path}."

    # Detect the indentation level of the original function
    original_first_line = source_lines[target_node.lineno - 1]
    indent = len(original_first_line) - len(original_first_line.lstrip())
    indent_str = " " * indent

    # Re-indent the new source to match
    dedented = textwrap.dedent(new_function_source)
    reindented_lines = [
        (indent_str + line if line.strip() else line)
        for line in dedented.splitlines(keepends=True)
    ]
    if reindented_lines and not reindented_lines[-1].endswith("\n"):
        reindented_lines[-1] += "\n"

    # Splice: lines before + new function + lines after
    start = target_node.lineno - 1
    end = target_node.end_lineno
    new_source_lines = source_lines[:start] + reindented_lines + source_lines[end:]
    new_source = "".join(new_source_lines)

    # Validate the patched result parses cleanly before saving
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return f"Error: The patched code has a syntax error and was NOT saved: {e!s}"

    target.write_text(new_source, encoding="utf-8")
    return f"Successfully patched '{function_name}' in {file_path}."


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5: write_file (kept as fallback for new files)
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """
    Overwrites an entire file with new content. Use apply_patch to fix a
    specific function. Only use this tool to CREATE a brand new file.
    Args:
        file_path: Path to the file, relative to project root.
        content: The complete content to write.
    """
    target = (PROJECT_ROOT / file_path).resolve()

    if not target.is_relative_to(PROJECT_ROOT):
        return "Error: Access denied. Cannot write outside project root."

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote new file: {file_path}"
    except OSError as e:
        return f"Error writing file: {e!s}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6: run_python_code
# Runs an INLINE code snippet the LLM writes on the fly — much more flexible
# than run_sandbox_script which required a named file on disk.
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def run_python_code(code: str, timeout: int = 30) -> str:
    """
    Executes an inline Python code snippet in the sandbox and returns stdout/stderr.
    Use this to reproduce a bug, verify a fix works, or run a quick test.
    The code runs with the project root as the working directory.
    Args:
        code: Valid Python source code to execute.
        timeout: Maximum seconds to allow before killing the process (default: 30).
    """
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            dir=str(PROJECT_ROOT),
            encoding="utf-8",
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            check=False,
        )

        output = f"Return Code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"

        return output

    except subprocess.TimeoutExpired:
        return f"Error: Script timed out after {timeout} seconds. Check for infinite loops."
    except OSError as e:
        return f"Error running code: {e!s}"
    finally:
        # Always clean up the temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001, S110
            pass