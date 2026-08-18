# Skill: Bug Report Triage & Routing

## Objective
Analyze execution logs, stack traces, and API documentation to output a structured classification decision.

## Classification Rules
1. **`USER_ERROR`**: The payload sent by the user violated the API schema or client authentication parameters (e.g., missing required fields, 400 Bad Request, 401 Unauthorized).
2. **`AUTO_PR`**: The failure is caused by an unhandled application exception localized to backend code (e.g., `KeyError`, `IndexError`, `AttributeError`, unhandled 500 error in application code).
3. **`JIRA_TICKET`**: The failure is an infrastructure outage, connection pool exhaustion, database deadlock, or third-party service degradation.

## Constraints
You MUST return a JSON object adhering to the required schema containing `action` and `analysis`. Do NOT output conversational text.