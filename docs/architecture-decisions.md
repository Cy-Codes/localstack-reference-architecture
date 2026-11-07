# Architecture Decision Records (ADR) & Design Rationale

This document outlines the foundational technical decisions for the **CrmApiCSharp** (.NET 10 / C# 13) and **CrmApiKotlinSpringBoot** (Kotlin 2.x / Spring Boot) projects, serving relational replica data from **Microsoft SQL Server** (`CRMDatabaseMS`) and **PostgreSQL** (`CRMDatabasePG`) across Salesforce, HubSpot, and Microsoft Dynamics 365, together with the **`crm-infra/`** Terraform and LocalStack platform that deploys every **cloud × API runtime × database engine** permutation to local Docker, AWS, and Azure.

Every design choice is grounded in enterprise architectural patterns, authoritative industry specifications, and established literature from Martin Fowler, Microsoft Architecture Guides, JetBrains Kotlin, Spring Architecture, HashiCorp Terraform, LocalStack, and database/API consensus.

The decisions are enforced day-to-day through the workspace coding standards:
- **[Master Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/CODING_STANDARDS.md)** (universal principles — see [ADR 1](#adr-1-universal-coding-standards-functional-core-immutability-and-command-query-separation))
- **[CrmApiCSharp Standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md)** · **[CrmApiKotlinSpringBoot Standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md)** · **[CRMDatabaseMS Standards](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md)** · **[CRMDatabasePG Standards](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md)** · **[Infrastructure Standards](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md)**

### Implementation Matrix

| ADR | crm-infra/ (Terraform / LocalStack) | CRMDatabasePG (PostgreSQL 16 / Flyway) | CRMDatabaseMS (SQL Server 2022 / DACPAC) | CrmApiCSharp (.NET 10 / C# 13) | CrmApiKotlinSpringBoot (Kotlin 2.x / Spring Boot) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Coding Standards | [Infrastructure standards](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md) (Terraform, LocalStack, Bash) | [PG standards](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md) (PL/pgSQL, Python, Bash) | [MS standards](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md) (T-SQL, Python, Bash) | [C# standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md) (.NET 10, Dapper, SqlKata) | [Kotlin standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md) (Kotlin 2.x, Spring Boot) |
| 2–4. Platform | Terraform, LocalStack, images & migrators | PostgreSQL container, one-shot Flyway migrator | SQL Server container, one-shot SqlPackage deployer | Container image | Container image |
| 5. Data Access | Schema deployed by one-shot migrators | Migration-based: immutable `V{n}__` scripts applied in order | State-based: one `.sql` per object, delta computed at deploy time | Dapper + SqlKata | `JdbcDataMapper` + immutable `SqlQuery` AST |
| 6. Factories & Repositories | Identical connection strings via `crm-runtime-config` | Schema only; no app-side factory | Schema only; no app-side factory | `IDbConnectionFactory`, `ISqlKataCompilerFactory` | `IDbConnectionFactory`, `ISqlCompilerFactory` |
| 7. Application Database | Databases reachable only by API tasks and admin/migrator CIDRs | Constraints and PL/pgSQL functions enforce invariants | Constraints and stored procedures enforce invariants | API-owned domain logic | API-owned domain logic |
| 8. Provider Routing | Both engines wired into every API | Selected by `pg` provider segment | Selected by `ms` provider segment | `{provider:regex(^(ms\|pg)$)}` | `{provider:^(?:ms\|pg)$}` |
| 9. Layering | Shared contract modules vs. cloud modules | — | — | 4 projects (`Domain`, `Infrastructure`, `Application`, `Api`) | 4 packages (`domain`, `infrastructure`, `application`, `api`) |
| 10. GraphQL | Same `/graphql` route on every cloud | — | — | HotChocolate + `IDataLoader` | Lightweight `POST /graphql` endpoint with selection projection |
| 11. Problem Details | — | — | — | `ExceptionHandlingMiddleware` | `ExceptionHandlingAdvice` (`@RestControllerAdvice`) |
| 12. Pagination | — | — | — | `record QueryOptions` / `PagedResult<T>` | `data class QueryOptions` / `PagedResult<T>` |
| 13. Polyglot Parity | Both runtimes in one catalog | Same schema served to both runtimes | Same schema served to both runtimes | Reference implementation | Feature-parity implementation |
| 14. Command Endpoints & RBAC | [`dev-token.sh`](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/scripts/dev-token.sh) mints local role tokens | Constraints surface as `409` | Constraints surface as `409` | `*CommandsController`, `CrmRoles` policies, `ConflictException` | Spring Security URL rules, role converter, `ExceptionHandlingAdvice` |

---

## Table of Contents
- [ADR 1: Universal Coding Standards: Functional Core, Immutability, and Command-Query Separation](#adr-1-universal-coding-standards-functional-core-immutability-and-command-query-separation)
- [ADR 2: Cloud-Agnostic Infrastructure as Code via Terraform Shared Contract Modules](#adr-2-cloud-agnostic-infrastructure-as-code-via-terraform-shared-contract-modules)
- [ADR 3: Emulation-First Delivery with LocalStack for AWS & Azure and Offline Terraform Tests](#adr-3-emulation-first-delivery-with-localstack-for-aws--azure-and-offline-terraform-tests)
- [ADR 4: Immutable Content-Addressed Images, Platform Secret Stores, and One-Shot Schema Migrators](#adr-4-immutable-content-addressed-images-platform-secret-stores-and-one-shot-schema-migrators)
- [ADR 5: Data Access Layer via Dapper and SqlKata (Micro-ORM & Query Object over Heavy ORM)](#adr-5-data-access-layer-via-dapper-and-sqlkata-micro-orm--query-object-over-heavy-orm)
- [ADR 6: Repository and Abstract Factory Patterns for Multi-Engine Persistence](#adr-6-repository-and-abstract-factory-patterns-for-multi-engine-persistence)
- [ADR 7: Division of Responsibilities: Application Database Encapsulation vs. Relational Invariants](#adr-7-division-of-responsibilities-application-database-encapsulation-vs-relational-invariants)
- [ADR 8: Dynamic Multi-Provider Routing (`/api/{provider}/v1/...`)](#adr-8-dynamic-multi-provider-routing-apiproviderv1)
- [ADR 9: Clean Architecture Layering & Inversion of Control](#adr-9-clean-architecture-layering--inversion-of-control)
- [ADR 10: HotChocolate GraphQL Foundation with DataLoader Batching](#adr-10-hotchocolate-graphql-foundation-with-dataloader-batching)
- [ADR 11: Standardized Error Handling via RFC 7807 / RFC 9457 Problem Details](#adr-11-standardized-error-handling-via-rfc-7807--rfc-9457-problem-details)
- [ADR 12: Stateless Offset Pagination and Dynamic Filtering via Immutable Value Objects](#adr-12-stateless-offset-pagination-and-dynamic-filtering-via-immutable-value-objects)
- [ADR 13: Polyglot Feature-Parity API Runtimes (C# & Kotlin) with JetBrains `kotlinx.serialization`](#adr-13-polyglot-feature-parity-api-runtimes-c--kotlin-with-jetbrains-kotlinxserialization)
- [ADR 14: Command Endpoints (Create / Update / Delete) with Role-Based Authorization](#adr-14-command-endpoints-create--update--delete-with-role-based-authorization)

---

## ADR 1: Universal Coding Standards: Functional Core, Immutability, and Command-Query Separation

### Status
Accepted

### Context
The workspace spans C#, Kotlin, T-SQL, PL/pgSQL, Python, Bash, HCL, and YAML across five codebases (`CrmApiCSharp`, `CrmApiKotlinSpringBoot`, `CRMDatabaseMS`, `CRMDatabasePG`, `crm-infra/`). Without shared rules, each codebase evolves its own idioms, and the architectural guarantees above (immutable value objects, pure query compilation, isolated I/O, injection safety) erode one change at a time.

### Decision
Adopt one set of **universal coding standards**, specified in the [Master Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/CODING_STANDARDS.md) and restated self-contained in every codebase:

| Pillar | C# | Kotlin | SQL (T-SQL / PL/pgSQL) | Infrastructure (HCL / Bash) |
| :--- | :--- | :--- | :--- | :--- |
| **Functional over loops** | LINQ projections | `map` / `filter` / `fold` / `generateSequence` | Set-based queries, tally CTEs, `generate_series` | `for` expressions, `for_each`, `jq` pipelines |
| **Immutability** | `record` + `init`, `ImmutableArray<T>`, `FrozenDictionary` | `data class` + `val`, read-only `List` / `Map` | Immutable Flyway migrations, audit columns | `locals`, `readonly`, content-hash image tags |
| **Explicit side effects (CQS)** | `Get*` vs `Execute*` | `get*` / `to*` vs `execute*` / `open*` | Deterministic functions vs procedures with `XACT_ABORT` | Pure modules vs resource modules; `# Pure query` / `# Side effect` |
| **Zero magic numbers** | `const`, `StatusCodes.*` | `const val`, `HttpStatus.*` | `DECLARE @BatchSize` | Named `locals`, `readonly DEFAULT_*` |
| **Helpers & extensions** | `static class ...Extensions` | Top-level extension functions | Shared runner scripts | Shared modules, `lib.sh` |

Codebase-specific standards: [CrmApiCSharp](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md) · [CrmApiKotlinSpringBoot](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md) · [CRMDatabaseMS](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md) · [CRMDatabasePG](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md) · [crm-infra/](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md).

### Rationales & Authoritative Sources

1. **Command-Query Separation & Functional Core, Imperative Shell**:
   - Pure query construction (SqlKata / `SqlQuery`, `crm-catalog`, `crm-runtime-config`) is trivially testable; I/O is confined to thin, explicit boundaries.
   - *References*:
     - Martin Fowler: [CommandQuerySeparation](https://martinfowler.com/bliki/CommandQuerySeparation.html).
     - Gary Bernhardt: [Functional Core, Imperative Shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell).

2. **Immutability & Value Semantics**:
   - *References*:
     - Martin Fowler: [Value Object](https://martinfowler.com/bliki/ValueObject.html).
     - JetBrains: [Kotlin Collections Overview (read-only vs mutable)](https://kotlinlang.org/docs/collections-overview.html).

3. **Language-Specific Style Authorities**:
   - *References*:
     - Microsoft Learn: [C# Coding Conventions](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions).
     - JetBrains: [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html).
     - HashiCorp: [Terraform Style Guide](https://developer.hashicorp.com/terraform/language/style) & [`terraform fmt`](https://developer.hashicorp.com/terraform/cli/commands/fmt).
     - Google: [Shell Style Guide](https://google.github.io/styleguide/shellguide.html) & [ShellCheck](https://www.shellcheck.net/).

4. **Injection Safety by Construction**:
   - *References*:
     - OWASP Foundation: [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) — Parameterized queries and identifier whitelisting (`IsSafeSqlIdentifier()` / `isSafeSqlIdentifier()`), plus `psql -v` bind variables in migration runners.

5. **Design by Contract & Automated Quality Governance**:
   - Universal coding standards act as automated contracts across languages, enforced continuously via pre-commit hooks and static analysis tools.
   - *References*:
     - Bertrand Meyer: [Design by Contract](https://www.eiffel.com/values/design-by-contract/) & *Object-Oriented Software Construction* (Prentice Hall) — The foundational principle of Command-Query Separation (CQS) and invariant contracts.
     - Neal Ford, Mark Richards: *Software Architecture: The Hard Parts* (O'Reilly) — Automated fitness functions and code governance across polyglot systems.

### Outcomes

#### Strategic Architectural Advantages
- **Uniform Reviewability**: The same five pillars apply to every pull request regardless of language, making cross-codebase review and onboarding predictable.
- **Architecture Preserved in the Small**: Immutable value objects, pure compilers, and isolated I/O are enforced at the line level, not only in diagrams.

#### Architectural Guardrails & Governance
- **Automated Enforcement**: The workspace `pre-commit` hook ([`.githooks/pre-commit`](file:///Users/cy/codes/localstack-reference-architecture/.githooks/pre-commit)) formats staged files and removes unused `using` / `import` statements across the root repository, all submodules, and the nested `crm-infra/` repository. HCL formatting is enforced with `terraform fmt -check -recursive crm-infra/terraform`.
- **Documented Exceptions Only**: Imperative loops, `nonsensitive(...)`, or other deviations require an inline comment explaining why the standard construct was rejected.

---

## ADR 2: Cloud-Agnostic Infrastructure as Code via Terraform Shared Contract Modules

### Status
Accepted

### Context
The same workloads (2 API runtimes × 2 database engines) must deploy to local Docker, AWS, and Azure — and must be migratable between clouds without rewriting application configuration. Hand-built or per-cloud bespoke environments drift quickly ("snowflake servers"), and duplicating *what* is deployed across cloud-specific code guarantees divergence.

### Decision
Use **Terraform** with a strict split between **shared, cloud-agnostic contract modules** and **thin provider-specific modules**:
- `modules/shared/crm-catalog` — pure single source of truth for runtimes, engines, ports, health paths, and migrator platforms.
- `modules/shared/crm-runtime-config` — pure translation of database endpoints into each runtime's environment/secret contract (identical connection strings, different variable spelling).
- `modules/shared/container-image`, `modules/shared/database-schema`, `modules/shared/endpoint-address` — provider-neutral build, migration, and parsing helpers.
- `modules/aws/*` (VPC, RDS, ECS Fargate + ALB) and `modules/azure/*` (Container Apps, Azure SQL, PostgreSQL Flexible Server) — the only cloud-specific code.
- Root stacks `terraform/aws` and `terraform/azure` compose these modules; each permutation (`all`, `csharp-ms`, `csharp-pg`, `kotlin-ms`, `kotlin-pg`) runs in its own **Terraform workspace** with its own `permutations/*.tfvars`.

### Rationales & Authoritative Sources

1. **Infrastructure as Code & Elimination of Snowflakes**:
   - Declarative, version-controlled definitions make every environment reproducible and reviewable.
   - *References*:
     - Martin Fowler: [InfrastructureAsCode](https://martinfowler.com/bliki/InfrastructureAsCode.html) & [SnowflakeServer](https://martinfowler.com/bliki/SnowflakeServer.html).
     - Kief Morris: *Infrastructure as Code: Designing and Delivering Dynamic Systems for the Cloud Age* (O'Reilly, 3rd ed.) — [infrastructure-as-code.com](https://infrastructure-as-code.com/).

2. **Module Composition & Standard Module Structure**:
   - Small modules composed by thin root stacks keep provider details at the edges and the shared contract at the core.
   - *References*:
     - HashiCorp: [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition) & [Standard Module Structure](https://developer.hashicorp.com/terraform/language/modules/develop/structure).
     - HashiCorp: [Terraform Style Guide](https://developer.hashicorp.com/terraform/language/style).
     - AWS Prescriptive Guidance: [Best Practices for Using the Terraform AWS Provider](https://docs.aws.amazon.com/prescriptive-guidance/latest/terraform-aws-provider-best-practices/introduction.html).

3. **Configuration in the Environment & Dev/Prod Parity**:
   - A single environment contract per runtime, identical on every cloud, keeps images unchanged across environments.
   - *References*:
     - The Twelve-Factor App: [III. Config](https://12factor.net/config) & [X. Dev/Prod Parity](https://12factor.net/dev-prod-parity).

4. **Isolated, Side-by-Side Permutations**:
   - *References*:
     - HashiCorp: [Terraform Workspaces](https://developer.hashicorp.com/terraform/language/state/workspaces) — Multiple state instances of one configuration.
     - HashiCorp: [`for_each` Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each) & [`for` Expressions](https://developer.hashicorp.com/terraform/language/expressions/for) — Stable, key-addressed collections of runtimes and engines.

5. **Defense-in-Depth Cloud Network Security & TLS Enforcement**:
   - Real-world cloud infrastructure mandates placing compute tasks in private subnets behind load balancers with mandatory in-transit TLS encryption.
   - *References*:
     - Center for Internet Security: [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services) & [CIS Microsoft Azure Foundations Benchmark](https://www.cisecurity.org/benchmark/azure) — Network security, subnet isolation, and TLS requirements.
     - NIST: [SP 800-52 Rev. 2: Guidelines for the Selection, Configuration, and Use of TLS](https://csrc.nist.gov/publications/detail/sp/800-52/rev-2/final).

### Outcomes

#### Strategic Architectural Advantages
- **Cloud Migration by Re-Targeting**: Moving `kotlin-pg` from AWS to Azure is `./crm-infra/scripts/up.sh azure kotlin-pg` — no application or catalog change.
- **One Place to Add a Workload**: A new runtime or engine is a catalog entry plus its image; both clouds pick it up automatically.
- **Well-Architected Alignment on Both Clouds**: Managed compute (ECS Fargate / Container Apps) and managed databases (RDS / Azure SQL / PostgreSQL Flexible Server) map to the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html) and [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/) pillars.

#### Architectural Guardrails & Governance
- **No Cloud Logic in Shared Modules**: `modules/shared` must never contain `aws_*` or `azurerm_*` resources; enforced by review against the [Infrastructure Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md).
- **Validated Selectors**: `api_runtimes` and `database_engines` are validated sets; unknown values fail at `plan` time.
- **Edge TLS & Private Network Isolation**: Real cloud deployments on AWS and Azure must terminate TLS at the load balancer via ACM/Azure managed certificates and place container tasks in private subnets with NAT gateways rather than assigning public IPs.
- **Database TLS Verification**: Connection strings in real-cloud environments must mandate verified TLS encryption (`Encrypt=True;TrustServerCertificate=False` on SQL Server, `SSL Mode=VerifyFull` on PostgreSQL) to prevent unencrypted or spoofed database transport.

---

## ADR 3: Emulation-First Delivery with LocalStack for AWS & Azure and Offline Terraform Tests

### Status
Accepted

### Context
Validating cloud deployments against real AWS and Azure accounts is slow, costly, and requires credentials that should never live on developer machines or in CI by default. The team needs fast feedback that the *same* Terraform and the *same* images work on both clouds, plus a cheaper layer of tests that needs no emulator at all.

### Decision
Adopt an **emulation-first** workflow with a layered test strategy:
1. **Offline contract tests** — `terraform test` with `mock_provider` blocks and `override_module` for the host-side migrator verifies wiring, naming, permutation selection, the runtime configuration contract, and negative validation (`expect_failures`) with no Docker or emulator.
2. **Emulated clouds** — `crm-infra/compose.yaml` profiles run **LocalStack for AWS** (gateway `:4566`, service ports `4510-4559`) and **LocalStack for Azure** (gateway `:4567`, service ports `4610-4659`) side by side; Terraform providers switch endpoints only when `localstack_enabled = true` (the default).
3. **Local baseline** — the `local` profile runs both databases and both APIs as plain containers with no cloud layer.
4. **Smoke & E2E** — `crm-infra/scripts/smoke.sh` probes health and REST resources per permutation and optionally runs the Bruno suites.

Real-cloud deployment uses the identical code with `TF_VAR_localstack_enabled=false` and real credentials.

### Rationales & Authoritative Sources

1. **Test Pyramid for Infrastructure**:
   - Cheap, fast mocked plans/applies at the base; emulator deployments in the middle; Bruno E2E at the top.
   - *References*:
     - Martin Fowler: [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html).
     - HashiCorp: [Terraform Tests](https://developer.hashicorp.com/terraform/language/tests) & [Mocks and Overrides](https://developer.hashicorp.com/terraform/language/tests/mocking).
     - Microsoft Learn: [Testing Terraform Code (Best Practices)](https://learn.microsoft.com/en-us/azure/developer/terraform/best-practices-testing-overview).

2. **High-Fidelity Local Cloud Emulation**:
   - *References*:
     - LocalStack: [Terraform Integration](https://docs.localstack.cloud/aws/integrations/infrastructure-as-code/terraform/) — Provider endpoint overrides and `skip_*` flags.
     - LocalStack: [Configuration Reference](https://docs.localstack.cloud/aws/capabilities/config/configuration/) — `GATEWAY_LISTEN`, `EXTERNAL_SERVICE_PORTS_START/END`, `PERSISTENCE`.
     - LocalStack: [LocalStack for Azure](https://docs.localstack.cloud/azure/) & [Auth Tokens](https://docs.localstack.cloud/aws/getting-started/auth-token/).
     - The Twelve-Factor App: [X. Dev/Prod Parity](https://12factor.net/dev-prod-parity).

3. **Profiles & Health-Gated Startup**:
   - *References*:
     - Docker: [Using Profiles with Compose](https://docs.docker.com/compose/how-tos/profiles/) & [Compose Services Reference (`healthcheck`, `depends_on`)](https://docs.docker.com/reference/compose-file/services/).

4. **Continuous Delivery & Automated Pipeline Governance**:
   - Comprehensive CI pipelines validating root configurations, infrastructure modules, and application runtimes ensure rapid, defect-free release cycles.
   - *References*:
     - Jez Humble & David Farley: *Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation* (Addison-Wesley).
     - Michael Nygard: *Release It!* (Pragmatic Bookshelf) — Health checks and self-healing startup sequences.

### Outcomes

#### Strategic Architectural Advantages
- **Zero-Cost, Credential-Free Iteration**: All 12 permutations (3 targets × 2 runtimes × 2 engines) are exercisable on a laptop with dummy credentials (`test` / `test`).
- **Fast Feedback in CI**: Offline `terraform test` runs in seconds and catches contract regressions (e.g. secrets leaking into plain `environment`) before any container is built.
- **Concurrent Multi-Cloud Emulation**: Non-overlapping port ranges allow AWS and Azure stacks to run simultaneously for migration rehearsals.

#### Architectural Guardrails & Governance
- **Emulator ≠ Production**: Emulator behavior can differ from real services (e.g. TLS, IAM enforcement, quotas). Real-cloud runs remain necessary before production and must restrict network access first.
- **Auth Token Hygiene**: `LOCALSTACK_AUTH_TOKEN` lives only in the git-ignored `crm-infra/.env`; scripts fail fast when it is missing.
- **Pin Emulator Versions for Reproducibility**: `LOCALSTACK_AWS_IMAGE_TAG` / `LOCALSTACK_AZURE_IMAGE_TAG` default to `latest` for convenience; CI and shared demos should pin calendar versions.
- **Healthcheck Schema Gating & Connect Retries**: Container orchestration healthchecks must verify schema readiness (e.g. querying `schema_version` or seeded tables) rather than simple port connectivity (`SELECT 1`), and migrator scripts must implement bounded connection retry loops (e.g. `pg_isready` polling) to avoid startup race conditions.
- **Continuous Integration for Root & Infrastructure**: Automated CI pipelines must validate the root repository and `crm-infra/` via Terraform format, validation, offline tests, and cross-repo smoke tests.

---

## ADR 4: Immutable Content-Addressed Images, Platform Secret Stores, and One-Shot Schema Migrators

### Status
Accepted

### Context
Each sub-repository ships a `Dockerfile`. Those images must run unchanged on local Docker, ECS Fargate, and Azure Container Apps; roll out automatically when — and only when — source changes; never embed credentials; and deploy database schemas (DACPAC for SQL Server, versioned migrations for PostgreSQL) against managed endpoints that have no shell access.

### Decision
- **Immutable, content-addressed images**: `modules/shared/container-image` tags each image with a SHA-1 of its build context and pushes to registries with immutable tags (Amazon ECR `IMMUTABLE`, Azure Container Registry). Images are multi-stage and run as non-root users; all environment-specific settings arrive via environment variables documented in each repository's `.env.example`.
- **Platform secret stores**: connection strings are delivered only through AWS Secrets Manager (ECS task `secrets`) or Azure Container App secrets (`secret_name` references), never as plain environment values. Credentials are generated with `random_password` and marked `sensitive`.
- **One-shot schema migrators**: `modules/shared/database-schema` reuses each database repository image as an admin process (`CRMDatabaseMS/publish.sh` for DACPAC publish + seed; the `CRMDatabasePG` init entrypoint for `V1..Vn` migrations + seed), executed via `terraform_data` + `local-exec` and re-triggered only when the image, endpoint, or seed mode changes. API services `depends_on` schema deployment.

### Rationales & Authoritative Sources

1. **Immutable Infrastructure & Build/Release/Run Separation**:
   - *References*:
     - Martin Fowler: [ImmutableServer](https://martinfowler.com/bliki/ImmutableServer.html) & [PhoenixServer](https://martinfowler.com/bliki/PhoenixServer.html).
     - The Twelve-Factor App: [V. Build, Release, Run](https://12factor.net/build-release-run).
     - Open Container Initiative: [Image Annotations (`org.opencontainers.image.*`)](https://github.com/opencontainers/image-spec/blob/main/annotations.md).

2. **Secure, Minimal Container Images**:
   - *References*:
     - Docker: [Building Best Practices (multi-stage builds, non-root users)](https://docs.docker.com/build/building/best-practices/).
     - OWASP Foundation: [Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html).

3. **Secrets Never in Plain Configuration**:
   - *References*:
     - AWS: [Pass Sensitive Data to an Amazon ECS Container](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data-secrets.html).
     - Microsoft Learn: [Manage Secrets in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets).
     - HashiCorp: [Input Variables — Suppressing Values in CLI Output (`sensitive`)](https://developer.hashicorp.com/terraform/language/values/variables).
     - OWASP Foundation: [Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

4. **Schema Deployment as an Admin Process Owned by the Database Repository**:
   - Reusing the database repositories' own tooling keeps DACPAC and migration logic single-sourced (ADR 5, ADR 7) and makes schema deployment identical on emulators and real clouds.
   - *References*:
     - The Twelve-Factor App: [XII. Admin Processes](https://12factor.net/admin-processes).
     - Pramod Sadalage & Martin Fowler: [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html).
     - HashiCorp: [The `terraform_data` Managed Resource](https://developer.hashicorp.com/terraform/language/resources/terraform-data).

5. **IAM Policy Eventual Consistency & Resource Dependency Sequencing**:
   - Cloud resource provisioning must explicitly sequence IAM policy attachments to compute execution roles before launching tasks to prevent eventual consistency race conditions.
   - *References*:
     - AWS Documentation: [IAM Eventual Consistency & Error Handling](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_general.html#troubleshoot_general_eventual-consistency).
     - AWS Well-Architected Framework: [Reliability Pillar — Data Protection and Deletion Safeguards](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/data-protection.html).

### Outcomes

#### Strategic Architectural Advantages
- **Deterministic Rollouts**: Unchanged source produces the same tag and therefore no redeploy; changed source always produces a new, immutable tag.
- **One Image, Every Environment**: The exact artifact verified locally is the artifact running on ECS or Container Apps.
- **No Credentials in Images, Plans, or Command Lines**: Secrets flow from `random_password` → secret store → container, and migrator credentials travel through process environment only.

#### Architectural Guardrails & Governance
- **Host-Side Migrator Reachability & In-VPC Migration**: Because migrators run on the operator's Docker daemon, databases must be reachable from `database_admin_cidrs` / `database_firewall_rules`. Real-cloud deployments should transition migrator execution to in-VPC/in-VNet one-shot container jobs (ECS run-task / Container Apps job) and close public database ingress entirely.
- **IAM Policy Propagation & Dependency Ordering**: ECS services and task definitions must declare explicit `depends_on` relationships on execution role policies (e.g. `read_secrets`) to eliminate startup failures caused by IAM eventual consistency.
- **Data Protection & Deletion Safeguards**: Managed database modules must expose `deletion_protection` (defaulting to `true` in production) and `skip_final_snapshot` (defaulting to `false`) to prevent accidental data loss.
- **Zero Fallback Password Leakage**: Fallback development passwords in local compose and Dockerfile files must never be inherited by real-cloud infrastructure or automated deployment pipelines.
- **Documented Sensitivity Exceptions**: The migrator unwraps sensitive values with `nonsensitive(...)` solely so Terraform streams migrator logs; any further use of `nonsensitive` requires an inline justification.
- **Platform Constraints**: The SQL Server migrator image is `linux/amd64`-only (`migrator_platform` in `crm-catalog`); API images target `var.image_platform` and must be `linux/amd64` for real Azure Container Apps.

---

## ADR 5: Data Access Layer via Dapper and SqlKata (Micro-ORM & Query Object over Heavy ORM)

### Status
Accepted

### Context
The application queries 37 relational tables across 3 distinct enterprise CRM schemas (`Salesforce`, `HubSpot`, `Dynamics365`) hosted concurrently on both Microsoft SQL Server (`CRMDatabaseMS`) and PostgreSQL (`CRMDatabasePG`). Database schemas are maintained independently via declarative SSDT DACPAC projects and Flyway SQL migrations respectively.

We needed a data access strategy that:
1. Emits native, parameterized SQL for two different SQL dialects without maintaining duplicate SQL strings.
2. Achieves near-zero CPU and memory allocation overhead for high-concurrency read queries.
3. Completely decouples application code from database schema migrations and change-tracking state machines.

### Decision
Use **SqlKata** as an object-oriented query builder and **Dapper** as the execution and object-mapping micro-ORM, eschewing heavyweight full-featured ORMs like Entity Framework Core or NHibernate.

**Kotlin counterpart (`CrmApiKotlinSpringBoot`)**: Apply the identical patterns without JPA/Hibernate. An immutable, sealed query AST (`SqlQuery`, `WhereClause.EqualsClause` / `LikeClause` / `InSubQueryClause`, `OrderByClause`) is compiled by pure dialect compilers (`SqlServerCompiler`, `PostgresCompiler`) into a `CompiledSqlQuery`, and the lightweight `JdbcDataMapper` object binds parameters through JDBC `PreparedStatement` and maps `ResultSet` rows directly into immutable `data class` primary constructors.

### Rationales & Authoritative Sources

1. **Object-Relational Impedance Mismatch & Micro-ORM Philosophy**:
   - Heavyweight ORMs introduce substantial runtime overhead (identity maps, change trackers, proxy generators, and state machines) that add no value for high-performance read-only projections.
   - *References*:
     - Martin Fowler: [OrmHate](https://martinfowler.com/bliki/OrmHate.html) — Explains the impedance mismatch and warns against treating relational databases merely as object dumps: *"The primary solution is to realize that ORMs are about mapping between objects and database... the key is to use them for what they are good at and not expect them to hide the database completely."*
     - Martin Fowler: [Data Mapper Pattern](https://martinfowler.com/eaaCatalog/dataMapper.html) (*Patterns of Enterprise Application Architecture* [P of EAA]) — Dapper functions as a streamlined Data Mapper, separating in-memory C# representations from database schemas without leaking persistence concerns into entities.

2. **Query Object Pattern for Multi-Dialect SQL Compilation**:
   - Rather than interpolating SQL strings or duplicating queries per engine, queries are composed as programmatic trees that compile to dialect-specific SQL (T-SQL brackets `[Salesforce].[Account]` with `OFFSET...FETCH NEXT` vs. ANSI quotes `"salesforce"."account"` with `LIMIT...OFFSET`).
   - *References*:
     - Martin Fowler: [Query Object Pattern](https://martinfowler.com/eaaCatalog/queryObject.html) (*P of EAA*) — *"A Query Object is an interpreter, that is, a structure of objects that can form itself into a SQL query. You can create this query by referring to classes and fields rather than tables and columns."*
     - SqlKata Official Documentation: [SqlKata Documentation & Architecture](https://sqlkata.com/docs) & [SqlKata GitHub Repository](https://github.com/sqlkata/querybuilder).

3. **Zero Change-Tracking Overhead & Maximum Execution Throughput**:
   - Dapper executes directly on native `DbCommand` and `DbDataReader` streams with runtime-emitted dynamic MSIL (`DynamicMethod`), yielding deserialization speeds within single-digit percentage points of handwritten ADO.NET.
   - *References*:
     - Dapper Micro-ORM: [Dapper Benchmarks & Documentation](https://github.com/DapperLib/Dapper#benchmarks).
     - Oracle: [JDBC Tutorial: Using Prepared Statements](https://docs.oracle.com/javase/tutorial/jdbc/basics/prepared.html) — The JVM foundation used by `JdbcDataMapper` for parameterized, pre-compiled execution.

4. **Kotlin Immutable Query AST & Deterministic Resource Disposal**:
   - Kotlin's sealed interfaces and `data class`es model the query tree as an exhaustive, immutable value; compilation is a pure `fold` over clauses, while JDBC `Connection` / `PreparedStatement` / `ResultSet` lifetimes are bounded by `.use { ... }`, and rows are streamed with `generateSequence { if (rs.next()) ... }`.
   - *References*:
     - JetBrains: [Kotlin Sealed Classes and Interfaces](https://kotlinlang.org/docs/sealed-classes.html) — Exhaustive `when` over closed type hierarchies (`WhereClause`).
     - JetBrains: [Kotlin Data Classes](https://kotlinlang.org/docs/data-classes.html) & [Sequences](https://kotlinlang.org/docs/sequences.html).
     - JetBrains: [`kotlin.use` (AutoCloseable)](https://kotlinlang.org/api/core/kotlin-stdlib/kotlin/use.html) — Deterministic disposal of JDBC resources.

5. **Decoupling Application from Database Schema Governance**:
   - Schemas are governed in dedicated database projects (`CRMDatabaseMS` via DACPAC and `CRMDatabasePG` via Flyway). Tying the API to EF Core migrations (or Hibernate `ddl-auto`) would create dual-state synchronization debt and violate single-source-of-truth principles.
   - *References*:
     - Pramod Sadalage & Martin Fowler: [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html) — Outlines why database migrations must be independently versioned and automated alongside application deployments rather than generated implicitly.
     - Martin Fowler: [Database Migration Pattern](https://martinfowler.com/patterns/database-migration.html).

6. **Concurrent Migration Serialization & Advisory Locking**:
   - Preventing race conditions during parallel CI/CD runs or multi-instance provisioning requires explicit distributed mutex acquisition at the database engine level.
   - *References*:
     - PostgreSQL Global Development Group: [PostgreSQL Explicit Locking & Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS) — Application-defined mutual exclusion locks (`pg_advisory_lock`).
     - Microsoft Learn: [sp_getapplock (Transact-SQL)](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-getapplock-transact-sql) — Application-level resource locking in SQL Server.
     - PostgreSQL Global Development Group: [psql Documentation: Variables and Interpolation](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES) — Using stdin streaming vs `-c` execution for `:'variable'` syntax.

### Outcomes

#### Strategic Architectural Advantages
- **Hardware Efficiency & Zero Allocation Overhead**: By bypassing EF Core's change-tracker, snapshot buffers, and dynamic proxy generation, Dapper streams rows directly from `DbDataReader` into records, achieving near-zero GC pressure and raw ADO.NET throughput under high concurrent load.
- **Deterministic Multi-Dialect Query Generation**: SqlKata query trees compile cleanly to engine-specific SQL (T-SQL bracketed schemas with `OFFSET...FETCH` vs PostgreSQL quoted identifiers with `LIMIT...OFFSET`) from a single query definition, eliminating dialect drift and duplicated query logic.
- **SQL Injection Immunity by Construction**: SqlKata binds query parameters as strictly typed named parameters (`@p0`, `@p1`), preventing injection attacks without relying on manual parameter sanitization. The Kotlin compilers emit the same `@pN` placeholders, which `JdbcDataMapper.toJdbcSql` rewrites into positional JDBC `?` bindings.
- **Complete Decoupling from Database Migration Lifecycle**: Eliminates the "dual-state synchronization debt" where EF Core model snapshots drift from actual database DDL. Database schemas remain independently version-controlled and governed via DACPAC (`CRMDatabaseMS`) and Flyway (`CRMDatabasePG`).

#### Architectural Guardrails & Governance
- **Explicit Graph Mapping over Magic Lazy Loading**: Deep hierarchical object graphs (e.g. Accounts with multiple Contact and Opportunity collections) require explicit mapping queries or DataLoader batching rather than ORM navigation properties. This deliberate trade-off trades implicit, uncontrolled queries for explicit, predictable performance.
- **Automated Schema Verification in CI**: To guard against column name drift between database schemas and Dapper models, automated integration tests and database schema verification suites execute on every pull request, ensuring model fidelity without requiring heavy ORM metadata scaffolding.
- **Hand-Rolled Compiler Scope Discipline (Kotlin)**: The Kotlin `SqlQuery` AST intentionally supports only the clauses the API needs (equality, `LIKE`, `IN (subquery)`, ordering, pagination). New clause types must be added as new sealed `WhereClause` variants with matching `SqlCompilerTests` for both dialects, never as raw SQL fragments.
- **Migration Script Execution & Variable Interpolation**: CLI migrators must pass SQL via standard input (e.g. `psql -v ...` with piped input as in `migrate.sh`) rather than `-c` flags, as PostgreSQL `psql` does not interpolate `:'variable'` expressions in command-line strings.
- **Concurrent Migration & Seed Serialization**: Migration runners must acquire mutual-exclusion locks (such as `pg_advisory_lock` in PostgreSQL and `sp_getapplock` within SQL Server seed/ETL procedures) and execute DDL and `schema_version` history recordings inside single transactions to prevent race conditions during concurrent CI or infrastructure provisioning runs.

---

## ADR 6: Repository and Abstract Factory Patterns for Multi-Engine Persistence

### Status
Accepted

### Context
The application must instantiate either `Microsoft.Data.SqlClient.SqlConnection` or `Npgsql.NpgsqlConnection`, and pair it with either `SqlServerCompiler` or `PostgresCompiler`, transparently at runtime per request based on the `{provider}` token.

### Decision
Implement the **Abstract Factory Pattern** (`IDbConnectionFactory`, `ISqlKataCompilerFactory`) injected into a **Repository Pattern** (`BaseRepository`, `SalesforceRepository`, `HubSpotRepository`, `Dynamics365Repository`).

**Kotlin counterpart**: `DbConnectionFactory` (implementing `IDbConnectionFactory`) parses the **same ADO.NET-style connection strings** consumed by the C# API (`ConnectionStrings.CRMDatabaseMS` / `ConnectionStrings.CRMDatabasePG`, bound from `CONNECTIONSTRINGS_CRMDATABASE{MS,PG}` via Spring relaxed binding) into JDBC URLs, and `SqlCompilerFactory` (implementing `ISqlCompilerFactory`) returns singleton `SqlServerCompiler` / `PostgresCompiler` instances. Repositories (`BaseRepository`, `SalesforceRepository`, ...) mirror the C# hierarchy one-for-one.

### Rationales & Authoritative Sources

1. **Repository Pattern for Decoupled Data Access**:
   - Repositories mediate between the domain and data mapping layers, acting like in-memory domain object collections and hiding SQL dialects from business logic.
   - *References*:
     - Martin Fowler: [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html) (*P of EAA*) — *"Mediates between the domain and data mapping layers using a collection-like interface for accessing domain objects."*
     - Martin Fowler: [Gateway Pattern](https://martinfowler.com/eaaCatalog/gateway.html) (*P of EAA*) — Encapsulating access to an external system or resource.

2. **Abstract Factory Pattern for Connection & Compiler Creation**:
   - Centralizes the creation of vendor-specific ADO.NET connection objects and query compilers without hardcoding connection constructors into repositories.
   - *References*:
     - Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides: *Design Patterns: Elements of Reusable Object-Oriented Software* (GoF) — Abstract Factory Pattern.
     - Microsoft Learn: [Framework Design Guidelines: Factory Patterns](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/).

3. **SQL Injection Defense-in-Depth**:
   - Dynamic sorting columns and filter keys are validated against strict alphanumeric regex (`^[a-zA-Z0-9_.]+$`), while all query values are passed as parameterized bindings (`@p0`, `@p1`) to Dapper.
   - Kotlin applies the identical whitelist via `String.isSafeSqlIdentifier()` (`SAFE_IDENTIFIER_REGEX`) in `QueryFilteringExtensions.kt`.
   - *References*:
     - OWASP Foundation: [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

4. **Single Connection-String Contract Across Runtimes**:
   - Both runtimes accept the identical connection string per engine so that infrastructure (ADR 2) never branches on the API language.
   - *References*:
     - Spring Boot Documentation: [Externalized Configuration & Relaxed Binding](https://docs.spring.io/spring-boot/reference/features/external-config.html).
     - The Twelve-Factor App: [III. Config](https://12factor.net/config) — Store configuration in the environment.

5. **Connection Pooling, Timeouts, and Circuit Resilience (Michael Nygard & HikariCP)**:
   - High-throughput database access mandates pooled connection reuse with explicit timeouts to prevent cascading connection starvation under load.
   - *References*:
     - Michael Nygard: *Release It! Design and Deploy Production-Ready Software* (Pragmatic Bookshelf) — Patterns for Stability: Connection Pools, Timeouts, and Fail Fast.
     - Brett Wooldridge: [HikariCP: High-Performance JDBC Connection Pool](https://github.com/brettwooldridge/HikariCP).
     - Microsoft Learn: [Options Validation in ASP.NET Core (`ValidateOnStart`)](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/configuration/options#options-validation).
     - Spring Boot Documentation: [Validated Configuration Properties](https://docs.spring.io/spring-boot/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.validation).
     - Polly: [Polly .NET Transient Fault Handling Library](https://github.com/App-vNext/Polly) & Spring: [Spring Retry Documentation](https://github.com/spring-projects/spring-retry).

### Outcomes

#### Strategic Architectural Advantages
- **Encapsulated Connection Lifecycle Management**: The `IDbConnectionFactory` encapsulates connection string resolution, database credentials, and engine instantiation (`SqlConnection` vs `NpgsqlConnection`) behind a unified factory, guaranteeing proper async disposal (`await using`) and preventing connection pool exhaustion.
- **Compile-Time Singleton Efficiency**: `ISqlKataCompilerFactory` maintains singleton, thread-safe instances of `SqlServerCompiler` and `PostgresCompiler`, avoiding unnecessary object allocations on high-frequency query paths.
- **Defense-in-Depth Injection Prevention**: Column identifiers and sorting keys are strictly validated against compiled regular expressions (`SafeIdentifierRegex`), while all user-supplied filter values are bound as parameterized variables.

#### Architectural Guardrails & Governance
- **Connection Pooling & Transient Fault Governance**: Direct ADO.NET connection creation relies on connection pooling configured within connection strings. Production environments must configure transient connection retry policies (e.g. `EnableRetryOnFailure` or Polly execution policies) within the factory implementation.
- **JVM Connection Pooling & Lifecycle (Kotlin)**: The Kotlin `DbConnectionFactory` must be backed by a high-performance connection pool (HikariCP `DataSource`) rather than raw `java.sql.DriverManager.getConnection`. Connection and statement timeouts (`connectionTimeout`, `loginTimeout`, `statement.queryTimeout`) must be explicitly configured to prevent stalled queries from starving request threads.
- **Credential & JDBC URL Contract Fidelity**: Connection string parsers must accurately honor credentials supplied in raw `jdbc:` URLs and environment variables without reverting to hardcoded development defaults.
- **Fail-Fast Startup Configuration Validation**: Database connection strings and mandatory operational settings must be validated during application startup (`ValidateOnStart` in .NET, `@ConfigurationProperties` + `@Validated` in Spring Boot) rather than failing lazily on the first inbound request.
- **Repository Granularity**: Generic query execution is centralized in `BaseRepository`, while domain-specific entity queries reside in dedicated CRM repositories (`SalesforceRepository`, etc.), preventing god-object anti-patterns.

---

## ADR 7: Division of Responsibilities: Application Database Encapsulation vs. Relational Invariants

### Status
Accepted

### Context
In enterprise architectures, legacy paradigms frequently advocate for the "Database as Application Platform" model—attempting to embed domain validation, multi-entity business workflows, calculations, and orchestration inside database stored procedures, triggers, and proprietary vendor scripts under the premise that the database must be independently intelligent.

This creates severe architectural liabilities:
1. **The Integration Database Anti-Pattern**: Allowing external systems or ad-hoc tools direct read/write access to tables bypasses application security, business validation, and audit telemetry.
2. **The Dual-Maintenance Trap**: Fragmenting business logic between application code (C#) and procedural SQL (T-SQL, PL/pgSQL) guarantees logic duplication, subtle synchronization bugs, and vendor lock-in.
3. **Severe CI/CD Bottlenecks**: Procedural database logic cannot execute in-memory unit tests in milliseconds, forcing brittle and slow database-spinning integration pipelines.

### Decision
Adopt an **Encapsulated Application Database model with API-First domain governance**:

- **API / Application Layer (Sole Domain Authority)**:
  - The API is the **canonical, non-bypassable entry point** for all business rules, domain entities, validation logic, state machine transitions, pagination, security, and audit telemetry.
  - Test suites follow the **Test Pyramid**: rich suites of unit, component, and contract tests execute in-memory in milliseconds without database provisioning overhead.
- **Database Layer (Storage & Relational Invariants)**:
  - Strictly encapsulated as a private **Application Database** (backing service). Direct external access to tables is denied.
  - Dedicated strictly to what relational engines are uniquely optimized for: **ACID persistence, physical storage indexing, query optimization, and relational structural invariants** (declarative primary keys, foreign keys, unique constraints, check constraints, and cascading integrity).

### Rationales & Authoritative Sources

1. **Application Database vs. Integration Database Pattern (Martin Fowler)**:
   - Modern service architecture strictly rejects the *Integration Database* anti-pattern (where multiple applications or ad-hoc clients share access to raw tables), replacing it with the *Application Database* pattern where only a single application service controls the database schema and access.
   - *References*:
     - Martin Fowler: [Application Database](https://martinfowler.com/bliki/ApplicationDatabase.html) — *"In an Application Database, all access to the database is done through a single application. This means the application completely controls the database schema... You can easily change the database schema as long as you keep the application's external interfaces stable."*
     - Martin Fowler: [Integration Database](https://martinfowler.com/bliki/IntegrationDatabase.html) — Details how shared database integrations paralyze schema evolution and introduce uncontrolled coupling across teams.

2. **Domain Logic in Application Code vs. SQL Stored Procedures (Martin Fowler & Uncle Bob)**:
   - Placing domain workflows in stored procedures destroys portability, testability, and refactoring safety. An object-oriented or functional application tier provides strong type safety, modern IDE tooling, automated refactoring, and package management that procedural SQL lacks.
   - *References*:
     - Martin Fowler: [Domain Logic and SQL](https://martinfowler.com/articles/dblogic.html) — Thoroughly analyzes the trade-offs of domain logic in application code vs. stored procedures, explaining why enterprise architectures consolidate business logic in code for long-term maintainability.
     - Robert C. Martin: [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) — *"The database is a detail... The business rules should not know about the database."*

3. **Smart Endpoints and Dumb Pipes (Martin Fowler & Twelve-Factor)**:
   - Business intelligence, validation, and workflow state belong in cohesive application services, while persistence and transport infrastructure remain decoupled backing services.
   - *References*:
     - Martin Fowler: [Smart Endpoints and Dumb Pipes](https://martinfowler.com/articles/microservices.html#SmartEndpointsAndDumbPipes) — Foundational distributed systems and microservice principle.
     - The Twelve-Factor App: [Stateless Processes & Backing Services](https://12factor.net/) — Stateless application processes scale horizontally at low cost, treating databases as attached resources.

4. **The Test Pyramid & Fast Developer Feedback (Martin Fowler)**:
   - Fast, reliable CI/CD pipelines depend on running thousands of in-memory domain tests in seconds (`dotnet test`, `./gradlew test`). Moving business logic into the database makes in-memory testing impossible and creates flaky, slow CI builds.
   - *References*:
     - Martin Fowler: [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html).
     - Martin Fowler: [Microservice Testing](https://martinfowler.com/articles/microservice-testing/).

5. **Cloud Infrastructure Economics: Horizontal vs. Vertical Scaling (AWS Well-Architected)**:
   - Stateless API containers scale out horizontally on low-cost commodity compute or Kubernetes pods. In contrast, relational database compute is the most expensive and vertically constrained resource in the enterprise (often incurring steep per-core database licensing). Squandering database CPU cycles on procedural business calculations creates an expensive, unscalable infrastructure bottleneck.
   - *References*:
     - AWS: [AWS Well-Architected Framework: Performance Efficiency & Reliability](https://aws.amazon.com/architecture/well-architected/).

6. **Relational Integrity Invariants & Codd's Relational Foundation**:
   - Relational database management systems are engineered to enforce mathematical integrity constraints at the storage tier, ensuring data consistency that application tiers cannot guarantee under concurrent access.
   - *References*:
     - Edgar F. Codd: *A Relational Model of Data for Large Shared Data Banks* (Communications of the ACM, 1970) — Formal foundations of entity integrity, referential integrity, and relational keys.
     - C.J. Date: *An Introduction to Database Systems* (Addison-Wesley, 8th ed.) — Declarative integrity constraints vs procedural application checks.

7. **Optimistic Concurrency Control & Idempotent Mutations**:
   - Preventing lost updates and race conditions on write operations requires version tokens and standardized conditional requests.
   - *References*:
     - Martin Fowler: [Optimistic Offline Lock](https://martinfowler.com/eaaCatalog/optimisticOfflineLock.html) (*P of EAA*).
     - IETF RFC 9110: [HTTP Semantics — Conditional Requests (`ETag`, `If-Match`)](https://datatracker.ietf.org/doc/html/rfc9110#section-13.1.1).
     - IETF: [The Idempotency-Key HTTP Header Field](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header).

### Outcomes

#### Strategic Architectural Advantages
- **Single Source of Truth**: 100% of domain rules, calculations, and validations reside in version-controlled application services (C# in `CrmApiCSharp`, Kotlin in `CrmApiKotlinSpringBoot`) with full IDE and compiler assistance, eliminating the dual-maintenance trap between application code and procedural SQL.
- **True Engine Portability**: The same business logic operates concurrently against both Microsoft SQL Server and PostgreSQL without maintaining twin procedural codebases in T-SQL and PL/pgSQL.
- **Sub-Second CI/CD Execution**: Automated test suites validate the domain model in seconds during pull requests without provisioning database instances.
- **Compute Optimization**: Database CPU/IOPS are preserved exclusively for indexing, query plan execution, and ACID transactions—delivering maximum relational throughput.
- **Non-Bypassable Security & Audit Boundary**: Centralizing access through the API guarantees that all operations enforce authentication, authorization, input validation, and structured telemetry.

#### Architectural Guardrails & Governance
- **Strict Encapsulation (No Direct DB Write Access)**: Direct write access to relational storage from reporting tools, third-party consumers, or ad-hoc scripts is explicitly denied. All mutations must route through API domain services.
- **Structural Invariants at the Storage Tier**: The database layer is not passive; it rigorously enforces declarative relational invariants (primary keys, foreign keys, unique constraints, NOT NULL constraints, check constraints, and ACID transactions), guaranteeing that no invalid or orphaned data can ever be persisted under any operational circumstance.
- **Network-Level Encapsulation in Deployed Environments**: In `crm-infra/`, database security groups and firewall rules admit only the API tasks plus explicitly configured admin/migrator ranges (`database_admin_cidrs` on AWS, `database_firewall_rules` on Azure). These ranges default to open for emulator convenience and must be restricted to private subnets/VNets and known IPs before any real-cloud deployment (see ADR 4).
- **Concurrency & Write Guardrails**: When write paths are introduced, entities must enforce unique constraints on business keys (preventing check-then-insert races), utilize optimistic concurrency tokens (`rowversion` on SQL Server, `xmin` on PostgreSQL) with HTTP `ETag` / `If-Match` validation, and require client `Idempotency-Key` headers on POST endpoints. The first write paths shipped in [ADR 14](#adr-14-command-endpoints-create--update--delete-with-role-based-authorization) rely on the unique/foreign-key constraints (surfaced as `409`) but **defer** `ETag` / `If-Match` and `Idempotency-Key`; that gap is a tracked exception, not the target state.

---

## ADR 8: Dynamic Multi-Provider Routing (`/api/{provider}/v1/...`)

### Status
Accepted

### Context
Clients must be able to interrogate either database engine (`ms` for Microsoft SQL Server, `pg` for PostgreSQL) dynamically across any CRM entity using standard RESTful conventions, enabling live benchmarking, verification, and migration without deploying separate APIs.

### Decision
Adopt route templates parameterized by the provider token constrained by regex:
```http
/api/{provider:regex(^(ms|pg)$)}/v1/{crm}/{resource}     # CrmApiCSharp (ASP.NET Core)
/api/{provider:^(?:ms|pg)$}/v1/{crm}/{resource}         # CrmApiKotlinSpringBoot (Spring Web MVC)
```

### Rationales & Authoritative Sources

1. **Branch By Abstraction & Strangler Fig Architectural Patterns**:
   - Exposing both database engines under identical URL structures allows parallel running, A/B validation, and seamless progressive transitions from one database engine to another without breaking client contracts.
   - *References*:
     - Martin Fowler: [Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — *"Branch by Abstraction is a technique for making a large-scale change to a software system in gradual steps... allowing you to release your software with the new implementation running in parallel with the old one."*
     - Martin Fowler: [Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html) — Intercepting and routing calls to alternate backends behind a unified façade.

2. **Richardson Maturity Model & Microsoft REST API Guidelines**:
   - Routes model resources as predictable nouns, use HTTP verbs appropriately (`GET`), support explicit versioning (`v1`), and enforce provider constraints at the routing tier with standard HTTP 404 responses for invalid providers.
   - *References*:
     - Martin Fowler: [Richardson Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html) — Steps to the glory of REST: Level 1 (Resources), Level 2 (HTTP Verbs), and uniform resource addressing.
     - Microsoft: [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines) — Sections 5.1 (URL Path format), 7.2 (Versioning), and 9 (Collections).
     - Microsoft Learn: [Routing in ASP.NET Core & Route Constraints](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/routing).
     - Spring Framework Documentation: [Spring Web MVC URI Patterns](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-requestmapping.html) — Regex-constrained URI variables (`/api/{provider:^(?:ms|pg)$}/v1/...`) used by the Kotlin controllers.

3. **Liveness vs. Readiness Health Probes in Distributed Systems**:
   - Separating liveness (process vitality) from readiness (dependent storage and schema availability) prevents routing traffic during database restarts or migration initialization windows.
   - *References*:
     - Brendan Burns, Joe Beda, Kelsey Hightower: *Kubernetes: Up and Running* (O'Reilly) & Kubernetes Documentation: [Pod Lifecycle: Container Probes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes).
     - Spring Boot Documentation: [Liveness and Readiness Probes](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html#actuator.endpoints.kubernetes-probes).
     - Microsoft Learn: [Health Checks in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/host-and-deploy/health-checks).

### Outcomes

#### Strategic Architectural Advantages
- **Risk-Free Dual-Engine Verification (Branch By Abstraction)**: Running SQL Server (`ms`) and PostgreSQL (`pg`) simultaneously behind an identical URI surface enables direct performance benchmarking, functional verification, and continuous parity checking across engines without deploying or maintaining separate API instances.
- **Transparent Strangler Fig Migration**: Downstream consumers can gradually migrate from legacy SQL Server instances to cloud-native PostgreSQL by toggling a single path parameter or header, enabling phased zero-downtime database transitions without breaking client contracts.
- **Declarative Route Guardrails**: Utilizing regex constraints (`{provider:regex(^(ms|pg)$)}`) ensures invalid database provider tokens are rejected at the routing gateway with standard HTTP 404 responses before executing any application or database code.

#### Architectural Guardrails & Governance
- **Encapsulated Provider Context Propagation**: Every controller endpoint and query service accepts and propagates the `DatabaseProvider` discriminator to resolve the correct connection factory and compiler. This routing logic is strictly encapsulated via `BaseCrmController` and `IDbConnectionFactory` in both runtimes (`provider.ToDatabaseProvider()` / `provider.toDatabaseProvider()`), preventing provider-specific leaks into domain contracts.
- **Strict Schema Parity Enforcement**: Both SQL Server and PostgreSQL database instances must strictly conform to identical entity definitions and column types, enforced via automated database schema assertion test suites (`CRMDatabaseMS/Tests/01_Schema_Structure_Tests.sql`, `CRMDatabasePG/tests/01_schema_structure_tests.sql`).
- **Liveness vs. Readiness Health Probes**: Generic `/health` endpoints report liveness only (application process up); load balancers, orchestrators, and gateway routers must target database-verified readiness endpoints (`/health/ms` and `/health/pg` or schema readiness sentinels) to prevent routing production traffic during database restarts or schema initialization.

---

## ADR 9: Clean Architecture Layering & Inversion of Control

### Status
Accepted

### Context
The solution must separate pure domain representations from database mechanics, query building, application orchestration, and external transport protocols (REST and GraphQL).

### Decision
Structure the solution into 4 strictly decoupled layers with inward-facing dependencies:
- **`Domain`**: Pure C# record definitions, pagination envelopes (`PagedResult<T>`), and query options (`QueryOptions`). Zero external package dependencies.
- **`Infrastructure`**: Database connection factories (`IDbConnectionFactory`), SqlKata compiler factories (`ISqlKataCompilerFactory`), and CRM repositories executing Dapper queries.
- **`Application`**: Query services (`ISalesforceQueryService`, `IHubSpotQueryService`, `IDynamics365QueryService`), filter orchestrators, and child collection loaders.
- **`Api`**: ASP.NET Core controllers, route dispatching, middleware, OpenAPI / Swagger specifications, and HotChocolate GraphQL endpoints.

**Kotlin counterpart**: The same four layers are expressed as packages under `codes.cy.crmapi` (`domain`, `infrastructure`, `application`, `api`) in a single Gradle module, wired exclusively through Spring primary-constructor injection of `private val` interface dependencies (`ISalesforceQueryService`, `ISalesforceRepository`, `IDbConnectionFactory`, `ISqlCompilerFactory`).

### Rationales & Authoritative Sources

1. **Separation of Concerns & Presentation-Domain-Data Layering**:
   - Isolating domain contracts from infrastructure mechanics ensures business entities remain unaffected by database changes, driver upgrades, or transport migrations.
   - *References*:
     - Martin Fowler: [PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html) — *"One of the most common ways to modularize an information system is to divide it into three broad layers: presentation, domain, and data source."*
     - Martin Fowler: [Separated Interface](https://martinfowler.com/eaaCatalog/separatedInterface.html) (*P of EAA*) — Interfaces (`ISalesforceQueryService`, `ISalesforceRepository`) are owned by consumer layers, inverting runtime dependencies.
     - Robert C. Martin: [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) — The Dependency Rule: Source code dependencies can only point inward.
     - Microsoft Learn: [Common Web Application Architectures](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures).

2. **Inversion of Control (IoC) & Transport Independence**:
   - Both REST controllers (`SalesforceController`) and HotChocolate GraphQL resolvers (`Query`) consume the exact same `Application` query services via dependency injection, eliminating duplicated query logic.
   - *References*:
     - Martin Fowler: [Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html) — Principles of decoupling service configuration from resolution.
     - Microsoft Learn: [Dependency injection in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/dependency-injection).
     - Spring Framework Documentation: [Dependency Injection (Constructor-based)](https://docs.spring.io/spring-framework/reference/core/beans/dependencies/factory-collaborators.html) — Constructor injection with immutable `private val` collaborators in the Kotlin runtime.
     - Spring Framework Documentation: [Kotlin Support](https://docs.spring.io/spring-framework/reference/languages/kotlin.html) — Final-by-default classes opened by `kotlin("plugin.spring")`, null-safety via `-Xjsr305=strict`.

3. **Automated Architectural Fitness Functions & Boundary Testing**:
   - Enforcing package boundaries and dependency rules automatically in continuous integration prevents architectural erosion over time.
   - *References*:
     - Neal Ford, Rebecca Parsons, Patrick Kua: *Building Evolutionary Architectures* (O'Reilly) — Architectural fitness functions for automated dependency validation.
     - ArchUnit: [ArchUnit User Guide](https://www.archunit.org/userguide/html/000_Index.html) & LemonAppDev: [Konsist Documentation](https://lemonappdev.github.io/konsist/) — Declarative architecture assertion tools for JVM and Kotlin codebases.

4. **Perimeter Authentication and Zero Trust Edge Exposure**:
   - APIs deployed to cloud environments must terminate identity at the edge boundary and enforce authorization before routing to application services.
   - *References*:
     - NIST: [SP 800-207: Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final).
     - OWASP Foundation: [API Security Top 10](https://owasp.org/www-project-api-security/) — API1: Broken Object Level Authorization & API2: Broken Authentication.
     - Spring Security Reference: [Spring Security Architecture](https://docs.spring.io/spring-security/reference/index.html).

### Outcomes

#### Strategic Architectural Advantages
- **Transport Protocol Independence**: REST controllers and GraphQL resolvers function merely as lightweight transport adapters; 100% of business querying, filtering, and pagination rules live in shared Application services, completely eliminating protocol-specific logic duplication.
- **Inversion of Control & High Testability**: Inward-pointing dependencies and separated interfaces allow every application service to be unit-tested in isolation in milliseconds with mock repositories, freeing test suites from database dependencies.
- **Long-Term Maintainability & Domain Protection**: Domain records and contracts have zero third-party dependencies (no ASP.NET Core, no Dapper, no database drivers), protecting the core CRM model from external framework churn or breaking library upgrades.

#### Architectural Guardrails & Governance
- **Strict Layer Boundary Enforcement**: Developers must resist leaking infrastructure concerns (e.g. `SqlConnection`, raw SQL strings) or transport concerns (e.g. `HttpContext`, HTTP status codes) into the `Domain` or `Application` layers. In C# this is enforced via compile-time project reference boundaries.
- **Package-Level Boundaries in Kotlin**: Because the Kotlin layers share one Gradle module, boundaries are enforced by code review and the [CrmApiKotlinSpringBoot Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md) rather than the compiler. The `domain` package may depend only on the Kotlin standard library and `kotlinx.serialization` annotations; automated architecture test suites (e.g. ArchUnit or Konsist) or multi-module Gradle subprojects are required to prevent illegal layer imports.
- **Separated Interface Governance**: Every repository and query service is governed by an explicit interface (`ISalesforceQueryService`, `ISalesforceRepository`), ensuring that implementations remain interchangeable and fully mockable during testing.
- **Authentication & Authorization Perimeter**: Real-cloud edge deployments must introduce non-bypassable authentication and authorization middleware (e.g. ASP.NET Core JWT/OAuth2 authentication and Spring Security) before routing public ingress through load balancers or API gateways. Role rules for mutations are defined in [ADR 14](#adr-14-command-endpoints-create--update--delete-with-role-based-authorization).

---

## ADR 10: HotChocolate GraphQL Foundation with DataLoader Batching

### Status
Accepted

### Context
In addition to REST endpoints, clients require a flexible query interface capable of selecting specific fields and navigating related entities (e.g. Accounts with Contacts, Opportunities with LineItems) without suffering from the $N+1$ query problem.

### Decision
Implement **HotChocolate GraphQL** utilizing the `IDataLoader` pattern for batching child entity queries over Dapper and SqlKata.

**Kotlin counterpart**: Expose a lightweight `POST /graphql` endpoint (`GraphqlController`) that resolves a fixed catalog of root operations (`salesforceAccounts`, `salesforceAccountById`, `hubSpotCompanies`, `dynamics365Contacts`, ...) through the `Query` resolver and projects only the requested selection-set fields into a `kotlinx.serialization` `JsonObject`. The Kotlin schema deliberately exposes **flat root fields only** (no nested child navigation), so no N+1 fan-out can occur; nested navigation is reached through the REST child routes (e.g. `/accounts/{id}/contacts`).

### Rationales & Authoritative Sources

1. **Mitigating the N+1 Query Problem in Relational Queries**:
   - In naïve GraphQL implementations, resolving child relationships for a list of $N$ parent records results in 1 initial query plus $N$ individual child queries ($N+1$).
   - HotChocolate DataLoaders collect foreign keys across resolver executions within a request turn and dispatch a single parameterized `WHERE id IN (@id1, @id2, ...)` batch query through SqlKata and Dapper.
   - *References*:
     - Martin Fowler: [Lazy Load / N+1 Problem](https://martinfowler.com/eaaCatalog/lazyLoad.html) (*P of EAA*) — Trade-offs of loading on demand versus eager batching.
     - Lee Byron: [GraphQL DataLoader Specification](https://github.com/graphql/dataloader) — Foundational pattern for batching and caching asynchronous requests in GraphQL execution engines.
     - ChilliCream: [HotChocolate DataLoaders Documentation](https://chillicream.com/docs/hotchocolate/v13/fetching-data/dataloader).

2. **Official GraphQL Specification Alignment**:
   - Supports declarative field selection, strongly typed schemas, and standard execution semantics.
   - *References*:
     - GraphQL Foundation: [Official GraphQL Specification](https://spec.graphql.org/).
     - Martin Fowler: [Data Transfer Object (DTO)](https://martinfowler.com/eaaCatalog/dataTransferObject.html) — Client-driven field projection in the Kotlin `GraphqlController`.

3. **Escalation Path for Nested GraphQL on the JVM**:
   - Should the Kotlin schema grow nested child fields, it must adopt a specification-compliant engine with batching rather than extending regex parsing.
   - *References*:
     - Spring for GraphQL: [Annotated Controllers & `@BatchMapping`](https://docs.spring.io/spring-graphql/reference/controllers.html) — DataLoader-backed batch resolution on Spring.
     - GraphQL Java: [java-dataloader](https://github.com/graphql-java/java-dataloader) — JVM port of the DataLoader batching pattern.

4. **Query Depth & Complexity Protection (Denial of Service Prevention)**:
   - Client-driven nested queries can be weaponized into cyclic or combinatorial database exhaustion attacks without static depth and complexity limits.
   - *References*:
     - OWASP Foundation: [GraphQL Cheat Sheet: Denial of Service Prevention](https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html#denial-of-service).
     - ChilliCream: [HotChocolate Security: Execution Depth and Operation Complexity](https://chillicream.com/docs/hotchocolate/v13/security).

### Outcomes

#### Strategic Architectural Advantages
- **Bounded Query Execution ($O(1)$ Batching)**: The `IDataLoader` pattern guarantees that child entity lookups (e.g. Contacts for 50 Accounts) are batched into a single parameterized SQL query (`WHERE "AccountId" IN (...)`) per relationship level, completely eliminating the catastrophic $N+1$ query problem that plagues unoptimized GraphQL and ORM implementations.
- **Client-Driven Payload Optimization**: Clients select exactly the fields and relationship depths they require, drastically reducing network payload size and mobile data consumption without writing tailored REST view endpoints.
- **Unified Data Access Engine**: GraphQL resolvers do not execute independent SQL queries; they route through the same `Application` query services and Dapper repositories as REST, maintaining single-source-of-truth semantics.

#### Architectural Guardrails & Governance
- **Schema Type Governance**: Code-first GraphQL schema definitions (`SalesforceAccountType`, `SalesforceContactType`) must be explicitly declared and maintained to expose child navigation fields and link DataLoaders cleanly.
- **Query Complexity Protection**: While field selection is client-driven, production deployments must enforce HotChocolate query depth and complexity limits (`AddMaxExecutionDepth`, `AddMaxAllowedPagingBounds`) to guard the database against maliciously nested or recursive GraphQL requests.
- **Kotlin Operation Catalog Governance**: The Kotlin endpoint currently recognizes operations listed in `GraphqlController.OPERATION_REGEX` and rejects everything else with a GraphQL `errors` payload (HTTP 400). Adding an operation requires updating the resolver, the regex catalog, `GraphQLEndpointTests`, and the Bruno `04-GraphQL` collection together, keeping parity with the C# schema.
- **Specification-Compliant Kotlin GraphQL Engine**: Regex-based operation matching is limited to flat queries without support for nested selections, fragments, variables, or aliases. Upgrading to a spec-compliant GraphQL framework (Spring for GraphQL / Apollo Kotlin / GraphQL Java with DataLoader) is required before exposing nested child navigation on the JVM runtime.

---

## ADR 11: Standardized Error Handling via RFC 7807 / RFC 9457 Problem Details

### Status
Accepted

### Context
When exceptions occur (e.g. invalid database provider, bad filter parameter, missing entity, database timeout), the API must return standardized, machine-readable HTTP error payloads without leaking internal server stack traces or database connection details.

### Decision
Implement custom ASP.NET Core middleware (`ExceptionHandlingMiddleware`) returning standard **`ProblemDetails`** payloads with `Content-Type: application/problem+json` compliant with RFC 7807 and RFC 9457.

**Kotlin counterpart**: A global `@RestControllerAdvice` (`ExceptionHandlingAdvice`) whose pure companion function `createProblemDetails` maps exceptions to a `@Serializable` `ProblemDetailsPayload` (`IllegalArgumentException` / type-mismatch / unreadable body → 400, `NoSuchElementException` / `NoResourceFoundException` / `NoHandlerFoundException` → 404, otherwise 500), served as `application/problem+json`. `500` details are masked with `GENERIC_INTERNAL_ERROR_DETAIL` unless a `dev` / `development` profile is active.

### Rationales & Authoritative Sources

1. **RFC 7807 / RFC 9457 Standardized Problem Details**:
   - Defines a standardized JSON schema for HTTP API errors (`status`, `title`, `detail`, `instance`), eliminating custom ad-hoc error formats across endpoints.
   - *References*:
     - IETF RFC 7807: [Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807).
     - IETF RFC 9457: [Problem Details for HTTP APIs (Updated RFC)](https://datatracker.ietf.org/doc/html/rfc9457).
     - Microsoft Learn: [Handle errors in ASP.NET Core web APIs](https://learn.microsoft.com/en-us/aspnet/core/web-api/handle-errors).
     - Spring Framework Documentation: [Error Responses (RFC 9457) in Spring Web MVC](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html) & [Controller Advice](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-advice.html).

2. **Notification Pattern & Safe Fault Handling**:
   - Translates domain exceptions (`ArgumentException` $\rightarrow$ 400 Bad Request, `KeyNotFoundException` $\rightarrow$ 404 Not Found, unhandled $\rightarrow$ 500 Internal Server Error) while logging complete diagnostic context securely to `ILogger`.
   - *References*:
     - Martin Fowler: [Notification Pattern](https://martinfowler.com/articles/replaceThrowWithNotification.html) — Collecting errors and communicating status cleanly to consumers.

### Outcomes

#### Strategic Architectural Advantages
- **RFC-Standardized Machine-Readable Contracts**: Emitting `application/problem+json` envelopes adhering to RFC 7807 and RFC 9457 provides client SDKs and automated test runners (Bruno) with deterministic error structures (`status`, `title`, `detail`, `instance`), eliminating unpredictable string parsing.
- **Zero Information Leakage (Security Hardening)**: Production error responses systematically strip database connection strings, server hostnames, table schemas, and internal CLR stack traces, mitigating information disclosure vulnerabilities (OWASP API3:2023).
- **Centralized Diagnostic Observability**: All unhandled exceptions and error states are intercepted at the middleware boundary, logging structured telemetry with correlation IDs to `ILogger` before the response is serialized.

#### Architectural Guardrails & Governance
- **Exception Taxonomy Maintenance**: As new domain failure scenarios emerge, the middleware's exception mapping pattern must be intentionally updated to map domain exceptions to appropriate HTTP status codes (e.g. 400 for bad filters, 404 for missing resources, 409 for conflicts, 500 for unhandled infrastructure failures).
- **Consistent Client Expectation**: API consumers must be configured to inspect standard `ProblemDetails` payloads rather than expecting raw text or vendor-specific error structures.

---

## ADR 12: Stateless Offset Pagination and Dynamic Filtering via Immutable Value Objects

### Status
Accepted

### Context
Querying 37 enterprise CRM entities requires uniform, stateless handling of pagination (`page`, `pageSize`), multi-column sorting (`sortBy`, `sortDirection`), and arbitrary field filtering (`{field}={value}`) across both SQL dialects.

### Decision
Model query parameters as an immutable `QueryOptions` record and return responses wrapped in an immutable `PagedResult<T>` envelope containing metadata (`Items`, `TotalCount`, `Page`, `PageSize`, `TotalPages`, `HasPreviousPage`, `HasNextPage`).

**Kotlin counterpart**: `QueryOptions` and `PagedResult<T>` are `data class`es with `val` properties only (`PagedResult<T>` is `@Serializable` for compile-time JSON encoding); limits are `const val` companion constants (`DEFAULT_PAGE = 1`, `DEFAULT_PAGE_SIZE = 20`, `MAX_PAGE_SIZE = 100`) and normalization is exposed as pure computed properties (`normalizedPage`, `normalizedPageSize`). Query parameters are parsed at the boundary by the `Map<String, String>.toQueryOptions(...)` extension function.

### Rationales & Authoritative Sources

1. **Value Object Pattern**:
   - Query options and paged responses are immutable value objects defined by their attributes rather than identity, guaranteeing thread safety and eliminating mutation bugs across layers.
   - *References*:
     - Martin Fowler: [Value Object](https://martinfowler.com/bliki/ValueObject.html) — Immutable objects compared by value rather than identity.
     - Martin Fowler: [Data Transfer Object (DTO)](https://martinfowler.com/eaaCatalog/dataTransferObject.html) (*P of EAA*) — Packaging data between processes to reduce round-trips.
     - JetBrains: [Kotlin Data Classes](https://kotlinlang.org/docs/data-classes.html) & [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html) — `val`-only value types and read-only collection interfaces.

2. **Microsoft REST API Guidelines on Collections & Pagination**:
   - Adheres to standard pagination patterns using `page` and `pageSize` (defaulting to 20, capped at 100), accompanied by total item counts and page calculation.
   - *References*:
     - Microsoft: [Microsoft REST API Guidelines Section 9 (Collections)](https://github.com/microsoft/api-guidelines#9-collections).

3. **Defensive Arithmetic & Integer Overflow Prevention (CWE-190)**:
   - Paging arithmetic (`(page - 1) * pageSize`) must be guarded against 32-bit signed integer overflow to prevent negative database offsets and unexpected query behavior.
   - *References*:
     - MITRE: [CWE-190: Integer Overflow or Wraparound](https://cwe.mitre.org/data/definitions/190.html).
     - SEI CERT: [Java Coding Standard: NUM00-J Detect or prevent integer overflow](https://wiki.sei.cmu.edu/confluence/display/java/NUM00-J.+Detect+or+prevent+integer+overflow).
     - Markus Winand: *SQL Performance Explained* & [Use The Index, Luke! Pagination](https://use-the-index-luke.com/sql/partial-results/fetch-next-page) — Offset pagination mechanics and performance bounds.

### Outcomes

#### Strategic Architectural Advantages
- **Predictable, Uniform Client Experience**: All 37 entity endpoints across Salesforce, HubSpot, and Dynamics 365 adhere to an identical query protocol (`page`, `pageSize`, `sortBy`, `sortDirection`, `{filterKey}={filterVal}`), dramatically simplifying client SDK implementation and API documentation.
- **Immutable Value Objects & Thread Safety**: Modeling query parameters as immutable records (`QueryOptions`) and responses as envelopes (`PagedResult<T>`) eliminates state mutation bugs across asynchronous request execution pipelines.
- **Stateless Horizontal Scalability**: Zero server-side session state or cursors are maintained in memory; each query request is completely self-contained, allowing API containers to scale horizontally behind round-robin load balancers without sticky sessions.

#### Architectural Guardrails & Governance
- **Bounded Page Sizes to Guard Against Database Exhaustion**: The `BaseRepository` hard-caps `pageSize` to a maximum of 100 records (defaulting to 20), preventing malicious or poorly designed client queries from attempting to load millions of records into memory at once. Both runtimes must keep these limits identical (`QueryOptions.MaxPageSize` / `QueryOptions.MAX_PAGE_SIZE`).
- **Paging Arithmetic & Integer Overflow Guards**: Paging offset calculations (`(page - 1) * pageSize`) must be validated against 32-bit integer overflow; requests specifying out-of-range `page` numbers must be rejected with HTTP 400 Bad Request rather than wrapping to negative offsets and triggering database query errors.
- **Unbounded Relationship Collection Guards**: Repository child collection loaders must enforce explicit `LIMIT` / `TOP` caps or pagination bounds rather than buffering unbounded child entity sets into memory.
- **Deep-Offset Query Latency**: While offset pagination (`OFFSET...FETCH` / `LIMIT...OFFSET`) is optimal and expected for standard CRM interactive navigation (pages 1 through 100), extremely deep offsets (e.g. page 10,000+) incur database scan costs. For massive bulk export scenarios, dedicated bulk ETL procedures or keyset pagination patterns should be introduced as a complementary pattern.

---

## ADR 13: Polyglot Feature-Parity API Runtimes (C# & Kotlin) with JetBrains `kotlinx.serialization`

### Status
Accepted

### Context
The reference architecture must demonstrate that its patterns (ADRs 5–12) are language-agnostic and must let teams compare the .NET and JVM ecosystems under identical workloads. A second runtime is only valuable if it is a **true drop-in replacement**: same routes, same query protocol, same JSON field names, same error envelopes, and the same configuration contract. Kotlin introduces two specific serialization risks: JavaBean-style reflection serializers rename `is*` boolean properties (`isDeleted` → `deleted`), and omitting default-valued properties would make Kotlin payloads diverge field-for-field from the C# API.

### Decision
Maintain **`CrmApiKotlinSpringBoot`** (Kotlin 2.x, Spring Boot, JDK 25 toolchain) as a feature-parity counterpart of **`CrmApiCSharp`**:
- **Identical public contract**: all 37 entities, the `/api/{provider}/v1/{crm}/{resource}` routes, `POST /graphql`, `/health`, pagination/filter parameters, and RFC 9457 error envelopes.
- **Compile-time JSON via JetBrains `kotlinx.serialization`**: domain models are `@Serializable` `data class`es, served through Spring's `KotlinSerializationJsonHttpMessageConverter` configured with `Json { encodeDefaults = true; ignoreUnknownKeys = true; explicitNulls = true }`, preserving `is*` property names without reflection.
- **Shared verification**: both runtimes run the same Bruno collection layout (93 requests × `Local-MsSql` / `Local-Postgres`) and are wired into the same `crm-infra/` workload catalog (`csharp`, `kotlin`), so every permutation is tested identically.

### Rationales & Authoritative Sources

1. **Contract Parity over Implementation Parity**:
   - Consumers depend on the HTTP contract, not the language. Running the same contract tests against both implementations proves interchangeability and allows Branch-By-Abstraction swaps at the runtime level, exactly as ADR 7 does at the database level.
   - *References*:
     - Martin Fowler: [ContractTest](https://martinfowler.com/bliki/ContractTest.html) — Verifying that a service honors the contract its consumers rely on.
     - Martin Fowler: [Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html).

2. **Idiomatic, Immutable Kotlin on Spring**:
   - Kotlin's final-by-default classes, `val` properties, null-safety, extension functions, and `data class`es map directly onto the workspace immutability and helper-function standards (ADR 1).
   - *References*:
     - JetBrains: [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html), [Null Safety](https://kotlinlang.org/docs/null-safety.html), and [Extensions](https://kotlinlang.org/docs/extensions.html).
     - Spring Boot Documentation: [Kotlin Support](https://docs.spring.io/spring-boot/reference/features/kotlin.html).
     - Spring Framework Documentation: [Kotlin](https://docs.spring.io/spring-framework/reference/languages/kotlin.html).

3. **Compile-Time Serialization over Reflection**:
   - `kotlinx.serialization` generates serializers at compile time through the `org.jetbrains.kotlin.plugin.serialization` compiler plugin, avoiding reflection cost and JavaBean property-name mangling.
   - *References*:
     - JetBrains: [Kotlin Serialization](https://kotlinlang.org/docs/serialization.html) & [Kotlin Serialization Guide](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/serialization-guide.md).

4. **Reproducible Builds & Dependency Isolation**:
   - Builds must declare dependencies deterministically so that offline compilation (`--offline`) remains fully functional and reproducible.
   - *References*:
     - The Twelve-Factor App: [II. Dependencies](https://12factor.net/dependencies) — Explicitly declare and isolate dependencies.
     - Gradle User Manual: [Declaring Dependencies & Managing Transitive Dependencies](https://docs.gradle.org/current/userguide/declaring_dependencies.html).

### Outcomes

#### Strategic Architectural Advantages
- **Language-Agnostic Proof of the Architecture**: Every ADR is demonstrated twice, in two ecosystems, against two database engines — a 2 × 2 matrix exercised by the same test suites.
- **Byte-Compatible JSON Contracts**: `encodeDefaults = true` and native `is*` naming keep Kotlin responses field-for-field identical to the C# API, so Bruno assertions are shared without runtime-specific branches.
- **Runtime Portability in Infrastructure**: Because both images honor the same port (`8080`), health path (`/health`), and connection-string contract, `crm-infra/` deploys either runtime by catalog key alone (ADR 2).

#### Architectural Guardrails & Governance
- **Parity Changes Ship Together**: Any new entity, route, filter, or error mapping must land in both runtimes and in both Bruno collections in the same change set; divergence is treated as a defect.
- **Serializer Configuration Is Frozen**: Disabling `encodeDefaults`, switching to Jackson, or adding JavaBean-style DTOs is prohibited by the [CrmApiKotlinSpringBoot Coding Standards](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md).
- **Offline Build Dependency Integrity**: JDBC driver dependencies in `build.gradle.kts` must be declared unconditionally so that `--offline` Gradle builds retain required database drivers at runtime.
- **Configuration Hygiene & Dead Config Removal**: Unused configuration sections (e.g. `crm.databases.*` in `application.yml`) must be removed or reconciled to prevent configuration drift with `ConnectionStrings.*`.

---

## ADR 14: Command Endpoints (Create / Update / Delete) with Role-Based Authorization

### Status
Accepted (first pass: core entities; remaining tables and hardening items are tracked in the guardrails below)

### Context
Both APIs were read-only. Introducing mutations requires (1) side-effecting code that is clearly separated from the pure query path (ADR 1), (2) one authorization model that behaves identically in C# and Kotlin (ADR 13), and (3) a way to protect writes without making public reads harder to use. The previous perimeter was a single on/off switch (`Authentication:Enabled` / `crm.security.auth-enabled`) that either protected everything or nothing, with no notion of roles.

### Decision
- **Commands are separate from queries.** Each CRM gets dedicated command services (`I{Crm}CommandService`) and controllers (`{Crm}CommandsController`) in C#, and the equivalent in Kotlin. Repository mutation methods are named `Execute*` / `execute*`; reads stay `Get*` / `get*`. Writes go through generic `ExecuteInsert/Update/Delete` primitives that accept only whitelisted identifiers and parameterized values (SqlKata in C#; in Kotlin the immutable `SqlCommand.Insert/Update/Delete` AST compiled by the same dialect compilers — a separate type from `SqlQuery`, a documented deviation from the ADR 5 "new sealed variants" guardrail; ADR 5).
- **First-pass entities**: Salesforce `accounts`, `contacts`, `opportunities`; HubSpot `companies`, `contacts`, `deals`; Dynamics 365 `accounts`, `contacts`, `opportunities`, on both `ms` and `pg`.
- **Verbs and semantics**: `POST` → `201` + `Location` + persisted entity; `PUT` → full replace of writable fields (`200`, or `404`); `DELETE` → hard delete (`204`, or `404`). Foreign-key / unique-key violations map to `409 Conflict` Problem Details (ADR 11).
- **Roles** (JWT `roles` claim): *anonymous* = read-only; `user` = create + update; `admin` = create + update + delete. Every `GET`, `/health`, `/graphql`, and Swagger/actuator stay public; mutations are **always** protected and no configuration switch can open them. The legacy global toggle was removed.
- **Server-owned columns**: identifiers (`ICrmIdGenerator` / id generator), audit timestamps (`TimeProvider` / `Clock`), generated columns, and derived values (`fullname`) are never accepted from clients. JWT subjects do not map to CRM users, so the record's `ownerId` doubles as creator/modifier on audit columns until identity mapping exists.
- **Tokens for local use**: [`crm-infra/scripts/dev-token.sh`](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/scripts/dev-token.sh) mints HS256 tokens with the shared development secret. A real identity provider is a tracked follow-up.

### Rationales & Authoritative Sources

1. **Command-Query Separation**:
   - Mutating operations are explicit, named commands; queries remain side-effect free.
   - *References*:
     - Martin Fowler: [CommandQuerySeparation](https://martinfowler.com/bliki/CommandQuerySeparation.html).
     - Bertrand Meyer: *Object-Oriented Software Construction* (Prentice Hall).

2. **Function-Level Authorization Enforced Centrally**:
   - Declarative role policies on the command endpoints (ASP.NET Core authorization policies; Spring Security request matchers) make "who may mutate" reviewable in one place and prevent forgotten checks.
   - *References*:
     - OWASP Foundation: [API Security Top 10](https://owasp.org/www-project-api-security/) — API5: Broken Function Level Authorization & API2: Broken Authentication.
     - Microsoft Learn: [Role-based authorization in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/roles) & [Policy-based authorization](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/policies).
     - Spring Security Reference: [Authorize HTTP Requests](https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html) & [OAuth2 Resource Server JWT](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html).
     - IETF: [RFC 7519 JSON Web Token](https://datatracker.ietf.org/doc/html/rfc7519) & [RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750).

3. **Standard HTTP Method Semantics**:
   - `PUT` replaces the target representation idempotently, `DELETE` is idempotent, `POST` creates and returns `201` with `Location`.
   - *References*:
     - IETF RFC 9110: [HTTP Semantics — Methods](https://datatracker.ietf.org/doc/html/rfc9110#section-9).

4. **Constraints as the Last Line of Defense**:
   - Relational invariants (ADR 7) reject orphaning deletes and duplicate keys; the API translates the engine-specific error codes (SQL Server 547/2627/2601, PostgreSQL `23503`/`23505`) into one portable `409`.
   - *References*:
     - PostgreSQL: [Error Codes (Class 23 — Integrity Constraint Violation)](https://www.postgresql.org/docs/current/errcodes-appendix.html).
     - Microsoft Learn: [Database Engine Errors](https://learn.microsoft.com/en-us/sql/relational-databases/errors-events/database-engine-events-and-errors).
     - IETF RFC 9110: [409 Conflict](https://datatracker.ietf.org/doc/html/rfc9110#name-409-conflict).

### Outcomes

#### Strategic Architectural Advantages
- **Safe Public Reads, Locked Writes**: Consumers keep zero-friction `GET` access while every state change requires a verified identity and role.
- **One Contract, Two Runtimes**: Identical routes, status codes, and role matrix in C# and Kotlin (ADR 13). Known parity gaps (Bruno layout, JWT issuer/audience validation, role-claim case sensitivity, input length validation) are tracked in `local/ISSUES.md`.
- **Injection-Safe Writes**: Column names are whitelisted identifiers and all values are bound parameters, so request bodies can never alter SQL structure.

#### Architectural Guardrails & Governance
- **Mutations Are Never Anonymous**: Any new `POST` / `PUT` / `DELETE` route must carry the write or delete policy; tests assert `401` (no token), `403` (wrong role), and success per role.
- **Dev Signing Key Is Not a Secret**: The shared HS256 key in `appsettings.json` / `application.yml` is for emulation only and must be replaced (ideally by an RS256 identity provider) before any real-cloud deployment.
- **Tracked Exceptions** (see `local/TODO.md`): optimistic concurrency (`ETag` / `If-Match`) and `Idempotency-Key` required by ADR 7 are not yet implemented; mutations for the remaining ~28 tables; mapping JWT subjects to CRM users for audit columns; GraphQL mutations; real IdP.
- **Parity Changes Ship Together**: Any new command endpoint lands in both runtimes and both Bruno collections in the same change set (ADR 13).
