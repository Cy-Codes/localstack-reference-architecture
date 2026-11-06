---
name: multi-repo-navigator
description: "Rules and practices for navigating the multi-repository workspace across CRMDatabaseMS, CRMDatabasePG, CrmApiCSharp, and CrmApiKotlinSpringBoot while preventing workspace file pollution and enforcing clean git hygiene."
metadata:
    namespace: workspace
---
# Multi-Repository Workspace Navigation & Hygiene

This skill ensures streamlined context switching across sub-repositories in the workspace, preventing cross-module pollution, directory confusion, and unwanted IDE metadata commits.

## 1. Multi-Repository Boundaries

The workspace hosts multiple independent modules:
- `CRMDatabaseMS`: SQL Server SSDT DACPAC project (`Microsoft.Build.Sql`).
- `CRMDatabasePG`: PostgreSQL Flyway migrations (`V1..V6`).
- `CrmApiCSharp`: .NET 10 / C# 13 Web API and HotChocolate GraphQL service.
- `CrmApiKotlinSpringBoot`: Kotlin 2.x / Spring Boot Web API and GraphQL service.

### Execution Context Protocol
Always execute subproject operations within the respective directory context:
```bash
# Good: Target directory explicitly
cd /Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS && dotnet build

# Good: Run in subshell to avoid changing global working directory
(cd /Users/cy/codes/localstack-reference-architecture/CrmApiCSharp && dotnet test CrmApiCSharp.slnx)
(cd /Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot && ./gradlew test)
```

---

## 2. Preventing IDE & Workspace File Pollution

JetBrains IDEs discover and attach project roots dynamically.
- **NEVER** generate, commit, or edit workspace files (e.g., `workspace.xml`, `.idea/`, `.vscode/`, `.code-workspace`).
- Avoid adding root-level solution or workspace aggregators unless specifically requested.

---

## 3. Git Hygiene & Submodule Isolation

Before committing or inspecting changes, ensure the repository boundary is isolated:
```bash
# Verify submodule git status independently
git -C /Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS status
git -C /Users/cy/codes/localstack-reference-architecture/CRMDatabasePG status
git -C /Users/cy/codes/localstack-reference-architecture/CrmApiCSharp status
git -C /Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot status
```

---

## 4. Master Pipeline Verification

Run the top-level verification script to validate end-to-end multi-repository integrity:
```bash
/Users/cy/codes/localstack-reference-architecture/verify_all_pipelines.sh
```
