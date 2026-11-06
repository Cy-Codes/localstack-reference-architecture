---
name: air-format-compliance
description: "Strict formatting specifications for Air agentic development environment: file URIs (air-file://, air-folder://), commit schemes, markdown table layout, and subagent invocation rules."
metadata:
    namespace: environment
---
# Air Format Compliance & Runtime Conventions

This skill provides explicit formatting instructions and URI scheme construction rules required for all interactions within the Air environment on host `nmtkpi7uqs88prg7f8tn`.

## 1. File & Folder URI Scheme Rules

All file and directory references must use formatted markdown links with appropriate scheme targets and base names:

### File References (`air-file://`)
- **Structure**: `[<basename>](air-file://nmtkpi7uqs88prg7f8tn/<absolute-path>?type=file&root=%252F)`
- **Snippet / Line Offsets**: Include `linesData` with 0-indexed ranges and lines when referring to specific lines.
- **Rules**:
  - The link text inside `[ ]` MUST only be the file's base name (e.g., `README.md`).
  - NEVER use backticks around the link text or around the link itself.
  - Spaces in paths must be percent-encoded as `%20`.

### Folder References (`air-folder://`)
- **Structure**: `[<basename>](air-folder://nmtkpi7uqs88prg7f8tn/<absolute-path>?type=folder&root=%252F)`

---

## 2. Table Formatting Requirements

Markdown tables must ALWAYS be preceded and followed by a blank white line:

```markdown
Here is the summary table:

| Subsystem | Status |
| :--- | :--- |
| Database | Ready |
| API | Ready |

Following text continues here.
```

---

## 3. Subagent Execution Rules

- **Foreground Execution**: Always pass `waitForResult: true` when calling subagents to ensure execution completes before response generation.
- Subagents running in the background do not persist across session turns.

---

## 4. Commit Suggestions

When requested to suggest a commit message, invoke `mcp__Air__suggest_commit_message` with the proposed message formatted per repository conventions.
