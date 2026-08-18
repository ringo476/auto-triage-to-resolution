# Skill: Automated Code Patching & PR Generation

## Objective
Locate the source code causing a bug, apply a verified fix to the local file system, run sandbox tests, and generate a GitHub Pull Request summary.

## Execution Rules (Strict Sequence)
1. **Step 1 - Locate:** Use `search_codebase` or check the stack trace lines from the execution logs to find the failing file path.
2. **Step 2 - Inspect:** Use `read_file` to view the specific lines surrounding the failure. DO NOT guess the code structure without reading it first.
3. **Step 3 - Apply Patch:** Once you determine the fix, use the `write_file` tool to physically overwrite the broken file on the file system with your corrected code.
4. **Step 4 - Test Fix:** Use `execute_sandbox_script` to run the application or tests. Ensure the crash is resolved and the newly written file works. If it fails, use `write_file` to patch it again.
5. **Step 5 - Summarize:** Once the sandbox test passes, output a clear text summary of the exact changes you made. Do NOT request any more tools after this step.