# Agent Guidelines & Context for LocalStack Reference Architecture

Welcome to the **LocalStack Reference Architecture** workspace. This repository / workspace is designed to house and demonstrate reference architectures, cloud-native emulation patterns, and local development workflows using LocalStack across multi-repo and multi-service systems.

---

## 1. Multi-Repository & Workspace Structure

- **Multi-Repo Workspace**: Multiple independent repositories and services may reside within this workspace.
- **No JetBrains Workspace Files Needed**: JetBrains IntelliJ IDEA natively discovers multiple Git roots and attaches project modules automatically.
  - **Do NOT** generate, require, or commit workspace files (such as `workspace.xml`, `.idea` project state, or `.code-workspace` files) for JetBrains to play nice with multiple repositories.
  - Let JetBrains detect directory roots and modules dynamically.
- **Repository Boundaries**:
  - Always verify whether an operation applies to the root workspace or an individual nested repository (`cd <sub-repo>` or run commands in the respective `Cwd`).
  - Check `git status` within the specific repository context to prevent cross-repo pollution.

---

## 2. Core Operating Principles

- **Plan Before Execution**: For non-trivial modifications or architectural decisions, present a concise plan outlining affected components before making changes.
- **Coding Standards Compliance**: All code written or modified must adhere strictly to the project's [Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/CODING_STANDARDS.md):
  - **Functional Logic Over Loops**: Choose declarative transformations/maps over imperative loops (except benchmarked hot paths, streaming I/O, or batch log maintenance).
  - **Immutable Data by Default**: Use `record` with `init`, `data class` with `val`, `IReadOnlyList`, `ImmutableArray`, `IReadOnlyDictionary`, `FrozenDictionary`, `readonly struct`, or `@dataclass(frozen=True)`.
  - **Explicit Side Effects**: Demarcate mutating commands vs pure queries; isolate side effects to system boundaries.
  - **Zero Magic Numbers**: Use strongly typed constants, enums, or configuration options.
  - **Helper & Extension Functions**: Consolidate redundant logic into reusable helper functions, preferring static/top-level extension methods where supported.
  - **Submodule Standards**: Comply with language/engine-specific standards in [CrmApiCSharp](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md), [CrmApiKotlinSpringBoot](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md), [CRMDatabaseMS](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md), [CRMDatabasePG](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md), and [crm-infra](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md) (Terraform, LocalStack, Docker Compose, Bash).
  - **Architecture Decisions**: Consult the [Architecture Decision Records](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md) before changing patterns covered there, and update the relevant ADR when a decision changes.
- **Minimal & Focused Diffs**: Keep code changes scoped strictly to the task at hand. Avoid unnecessary reformatting or unrelated refactoring.
- **Preserve Documentation Integrity**: Preserve existing comments, docstrings, and documentation unless specifically instructed or directly affected by changes.
- **Safety First**: Never commit or log actual AWS secrets, production credentials, API keys, or certificates.

---

## 3. LocalStack & Cloud Emulation Guidelines

- **Mock Endpoints**: Always configure AWS clients (AWS SDK, Terraform AWS provider, CDK, CLI) to point to the LocalStack endpoint:
  - Host machine: `http://localhost:4566` (or `http://127.0.0.1:4566`)
  - Inside Docker containers/networks: `http://localstack:4566`
- **Dummy Credentials**: Always use standard dummy credentials for local emulation:
  - `AWS_ACCESS_KEY_ID=test`
  - `AWS_SECRET_ACCESS_KEY=test`
  - `AWS_DEFAULT_REGION=us-east-1` (or the project-configured default region)
- **Infrastructure as Code (IaC)**:
  - Structure IaC (Terraform, CDK, CloudFormation, SAM) modularly under dedicated directories (`crm-infra/` or `iac/`).
  - Ensure templates are compatible with LocalStack community or pro features as required.
- **Idempotency & Clean Lifecycle**:
  - Scripts and test fixtures creating AWS resources (S3, SQS, DynamoDB, SNS, EventBridge, Lambda, etc.) must be idempotent or provide clean setup/teardown mechanics.

---

## 4. Development, Testing, and Verification

- **Local Verification**: Verify code and infrastructure changes against running LocalStack instances where feasible.
- **Clean Git Hygiene**:
  - Keep working directories clean.
  - Never commit temporary logs, caches, build artifacts, or IDE-specific state (`.idea/`, `.vscode/`, `.DS_Store`).
  - Follow conventional commits where applicable (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
- **Agent Scratchpads**: Use the `scratch/` directory or temporary folders for one-off debugging scripts or exploratory artifacts; do not commit them.

---

## 5. Communication & Output Style

- Be concise and direct in explanations.
- Reference modified files and symbols with clickable markdown file links (`[filename](file:///absolute/path/to/file)`).
- When introducing new services or infrastructure components, provide clear run instructions or quick verification commands (e.g., `awslocal` or `curl`).
