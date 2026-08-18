# Skill: Bug Reproduction & Diagnostics

## Objective
Your goal is to reproduce the user-reported bug by executing commands against the staging environment and capturing the resulting stack trace or execution logs.

## Tool Selection Rules
1. **Analyze Available Tools:** Review your available FastMCP tools. 
2. **Prefer Pre-defined Tools:** If a specialized tool exists for your task (e.g., `seed_test_user`), use it directly.
3. **Fallback to Custom Code:** If no tool exists for your specific need (e.g., sending concurrent requests, hitting a specific endpoint), write a complete, self-contained Python script using standard libraries (like `requests` or `aiohttp`) and pass it to the `execute_sandbox_script` tool.

## Execution Constraints
- Always print the output of your operations so they are captured in the logs.
- If you encounter an error, stop and evaluate the output. Do not guess the root cause.
- Once you have successfully captured the stack trace or reproduced the failure, stop calling tools and provide a final summary.