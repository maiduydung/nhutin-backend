# AI Instance Governance Rules
### These RULES must be followed at all times.

This document defines mandatory operating principles for all AI instances. It ensures consistent behaviour, robust execution, and secure collaboration across tasks and services.

⸻

## Code Quality Standards

- All scripts must implement structured error handling with specific failure modes.
- Every function must include a concise, purpose-driven docstring.
- Sripts must verify preconditions before executing critical or irreversible operations.
- Long-running operations must implement timeout and cancellation mechanisms.
- File and path operations must verify existence and permissions before granting access.
- For function apps, only write to /tmp because thats the only place Azure allows writing to.
- All files must have a main() function to test run them easily from the project root, for example: python -m services.health_monitor
- For API calls and I/O processes, always prioritize async.
- Prioritize OOP, use classes and methods for readability.
- No files should be longer than 200 lines, if a file is that long, you must cut it into multiple classes and put in separate files.

⸻

## Documentation Protocols

- Keep documentation simple, easy to understand.
- Only update documentations to /docs directory or CHANGELOG.md and README.md in the project root.
- Documentation must be synchronised with code changes—no outdated references.
- Markdown files must use consistent heading hierarchies and section formats.
- Code snippets in documentation must be executable, tested, and reflect real use cases.
- Each doc must clearly outline: purpose, usage, parameters, and examples.
- Technical terms must be explained inline or linked to a canonical definition.

## Process Execution Requirements

- Agents must log all actions with appropriate severity (INFO, WARNING, ERROR, etc.).
- Any failed task must include a clear, human-readable error report.
- Agents must respect system resource limits, especially memory and CPU usage and funtion app timeouts.
- Long-running tasks must expose progress indicators or checkpoints.
- Retry logic must include exponential backoff and failure limits.
