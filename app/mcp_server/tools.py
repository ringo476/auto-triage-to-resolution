import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize the server
mcp = FastMCP("SentinelOps_Sandbox")

# Define the root directory to prevent the LLM from escaping the project folder
PROJECT_ROOT = Path("/app/workspace").resolve()

@mcp.tool()
def read_file(file_path: str) -> str:
    """Reads the contents of a specific file in the codebase."""
    target = (PROJECT_ROOT / file_path).resolve()
    
    if not str(target).startswith(str(PROJECT_ROOT)):
        return "Error: Access denied. Cannot read outside project root."
        
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e!s}"

@mcp.tool()
def search_codebase(keyword: str) -> str:
    """Searches the entire codebase for a specific keyword or function name."""
    try:
        # Use grep to find occurrences, ignoring hidden directories like .git
        result = subprocess.run(
            ["grep", "-rnw", str(PROJECT_ROOT), "-e", keyword, "--exclude-dir=.git"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout if result.stdout else "No matches found."
    except subprocess.TimeoutExpired:
        return "Error: Search timed out."
    except Exception as e:
        return f"Error executing search: {e!s}"

@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """Overwrites a file with new code to apply a patch."""
    target = (PROJECT_ROOT / file_path).resolve()
    
    if not str(target).startswith(str(PROJECT_ROOT)):
        return "Error: Access denied. Cannot write outside project root."
        
    try:
        target.write_text(content, encoding="utf-8")
        return f"Successfully updated {file_path}"
    except Exception as e:
        return f"Error writing file: {e!s}"

@mcp.tool()
def run_sandbox_script(script_name: str, args: str = "") -> str:
    """Executes a Python script in the sandbox to verify if the code fix worked."""
    target = (PROJECT_ROOT / script_name).resolve()
    
    if not str(target).startswith(str(PROJECT_ROOT)):
        return "Error: Access denied."
        
    try:
        # Execute the script as a subprocess
        cmd = ["python3", str(target)]
        if args:
            cmd.extend(args.split())
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        output = f"Return Code: {result.returncode}\n"
        output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
            
        return output
    except subprocess.TimeoutExpired:
        return "Error: Script execution timed out."
    except Exception as e:
        return f"Error executing script: {e!s}"