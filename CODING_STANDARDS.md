# Enterprise Multi-CRM Reference Architecture — Master Coding Standards

This document is the complete, authoritative specification of coding standards, architectural rules, and anti-pattern remediations across the **Enterprise Multi-CRM Reference Architecture** workspace.

Self-contained copies tailored to each subproject are also maintained directly inside each submodule repository and the nested `crm-infra/` repository:
- **[CrmApiCSharp/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md)** (Universal Standards + .NET 10 / C# 13, Dapper, SqlKata, HotChocolate GraphQL, Bruno)
- **[CrmApiKotlinSpringBoot/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md)** (Universal Standards + Kotlin 2.x, Spring Boot, Lightweight JDBC Data Mapper, Multi-Dialect SQL Compiler, GraphQL, JUnit 5, Bruno)
- **[CRMDatabaseMS/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md)** (Universal Standards + SQL Server 2022, SSDT DACPAC, T-SQL, Python, Bash)
- **[CRMDatabasePG/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md)** (Universal Standards + PostgreSQL 16, Flyway Migrations, PL/pgSQL, Python, Bash)
- **[crm-infra/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md)** (Universal Standards + Terraform / HCL, LocalStack for AWS & Azure, Docker Compose, Container Images, Bash)

The architectural rationale and authoritative sources behind these standards are recorded in the [Architecture Decision Records](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md) (ADR 13 covers the universal standards).

---

# Part I: Universal Coding Standards (All Projects & Languages)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Universal Standards Pillars                     │
├───────────────────┬───────────────────┬────────────────────────────────┤
│  Functional First │ Immutable Always  │ Explicit Side Effects          │
│  Maps over Loops  │ Records & Freezes │ Command/Query Segregation     │
├───────────────────┴──────┬────────────┴────────────────────────────────┤
│  Helper & Extension Fns  │ Zero Magic Numbers & Anti-Pattern Tolerance │
└──────────────────────────┴─────────────────────────────────────────────┘
```

## 1. Functional Logic Over Imperative Loops

Code across all languages (`C#`, `Kotlin`, `Python`, `SQL`, `Bash`, `HCL`, `JavaScript`) must favor declarative, functional transformations over state-mutating imperative loops.

### Rules:
1. **Choose Transformations (`map`, `filter`, `reduce`, LINQ, Kotlin collection pipelines, SQL projections, Terraform `for` expressions) Over Loops**:
   - Transform collections using pure declarative projections (`.Select()`, `.Where()`, `.Aggregate()`, `.map { }`, `.filter { }`, `.fold(...)`, `map()`, `filter()`, list comprehensions, SQL set-based `SELECT ... FROM ... JOIN`, HCL `{ for k, v in ... : k => v }` with `for_each`).
   - Do not allocate an empty collection, loop over input, and imperatively append elements (`.Add()`, `.add()`, `.append()`).
2. **Acceptable Exceptions for Loops**:
   - Loops (`for`, `foreach`, `while`) are permitted **only** when:
     - **Small datasets or performance-critical micro-benchmarks**: When allocations of delegate/enumerator closures on hot loops cause measured, unacceptable GC pressure (documented with benchmark data).
     - **Streaming large byte buffers / unbuffered streams**: Reading chunk-by-chunk from network or database streams (`while (await reader.ReadAsync(ct))` or `ResultSet.next()` wrapped in `generateSequence`).
     - **Early-exit break logic with complex state**: Where functional fold/recursion would significantly impair readability.
     - **Database batch maintenance**: Chunked batching (e.g. deleting 5,000 rows at a time in a `WHILE` loop to avoid locking the transaction log).
   - *Any exception loop must be documented with an inline comment explaining why a functional construct was rejected.*

### Good vs. Bad Comparison:

```csharp
// ❌ BAD: Imperative loop with mutable accumulator
var activeEmails = new List<string>();
foreach (var contact in contacts)
{
    if (contact.IsActive && !string.IsNullOrEmpty(contact.Email))
    {
        activeEmails.Add(contact.Email.ToLowerInvariant());
    }
}

// ✅ GOOD: Declarative functional pipeline
var activeEmails = contacts
    .Where(static c => c.IsActive && !string.IsNullOrWhiteSpace(c.Email))
    .Select(static c => c.Email!.ToLowerInvariant())
    .ToImmutableArray();
```

```kotlin
// ❌ BAD: Imperative Kotlin loop with mutable accumulator
val activeEmails = mutableListOf<String>()
for (contact in contacts) {
    if (contact.isActive && !contact.email.isNullOrBlank()) {
        activeEmails.add(contact.email.lowercase())
    }
}

// ✅ GOOD: Declarative Kotlin functional pipeline
val activeEmails = contacts
    .filter { it.isActive && !it.email.isNullOrBlank() }
    .map { it.email!!.lowercase() }
```

```python
# ❌ BAD: Imperative Python loop with manual mutation
results = []
for item in raw_records:
    if item["status"] == "active":
        results.append(item["id"])

# ✅ GOOD: Declarative comprehension / functional map
results = tuple(item["id"] for item in raw_records if item["status"] == "active")
```

```sql
-- ❌ BAD: Cursor / RBAR (Row-By-Agonizing-Row) processing
DECLARE contact_cursor CURSOR FOR SELECT Id, Email FROM Salesforce.Contact;
-- ... FETCH NEXT ... WHILE @@FETCH_STATUS = 0 ...

-- ✅ GOOD: Set-based declarative transformation
UPDATE Salesforce.Contact
SET Email = LOWER(Email)
WHERE Email IS NOT NULL AND IsDeleted = 0;
```

---

## 2. Immutability by Default

Data structures, domain entities, database records, and configuration payloads must remain deeply immutable once created.

### Rules:
1. **Immutable Data Contracts**:
   - Use C# `record` with `init` accessors, `readonly struct`, or readonly properties.
   - Use Kotlin `data class` with `val` properties and read-only `List<T>`, `Map<K, V>`, and `Set<T>`.
   - Use Python `@dataclass(frozen=True)`, `NamedTuple`, `tuple`, and `frozenset`.
   - Use Terraform `locals` for derived values, Bash `readonly` for constants, and content-hash tags on immutable container registries.
   - Collections in C# must be exposed as `IReadOnlyList<T>`, `IReadOnlyDictionary<TKey, TValue>`, `ImmutableArray<T>`, or `FrozenDictionary<TKey, TValue>`.
2. **Pure Functions**:
   - Methods should operate strictly on provided arguments and return new values without mutating input parameters.
   - Do not pass mutable collections into methods to be populated by the callee.
3. **Database Schema Immutability**:
   - In Flyway migrations (`CRMDatabasePG`), existing migration files (`V1`, `V2`, etc.) are **strictly immutable** once merged. Schema evolution occurs by appending new versioned migrations.
   - In SSDT (`CRMDatabaseMS`), table definitions represent declarative states; temporal history and audit fields (`CreatedDate`, `CreatedById`, `IsDeleted`) preserve historical immutability.

---

## 3. Explicit Demarcation of Side Effects

Side effects (mutating database state, making HTTP requests, writing to disk, mutating process environment, sending messages) must never be hidden inside innocent-looking getter methods, properties, or constructors.

### Rules:
1. **Command-Query Separation (CQS)**:
   - **Queries**: Pure, read-only, idempotent, and side-effect free. Can be called repeatedly with identical arguments without altering system state.
   - **Commands**: Explicitly alter state, perform I/O, or trigger mutations.
2. **Naming Conventions**:
   - **Pure Operations**: `Get...` / `get...`, `Calculate...` / `calculate...`, `Format...`, `Map...`, `To...` / `to...`, `Find...`, `Parse...` / `parse...`, `Resolve...` / `resolve...`.
   - **Side-Effecting Operations**: `Execute...` / `execute...`, `Create...`, `Update...`, `Delete...`, `Save...`, `Write...`, `Publish...`, `Apply...`, `Migrate...`, `Cleanup...`.
3. **Architecture Boundary (Functional Core, Imperative Shell)**:
   - Business calculations, validation rules, query AST composition, and data mappings must reside in pure functions without I/O dependencies.
   - I/O side effects (Dapper / JDBC database execution, HTTP response writing, process execution) reside strictly at the outer infrastructure and controller boundaries.
   - In Terraform, pure contract modules (`crm-catalog`, `crm-runtime-config`, `endpoint-address`) contain no resources; resources and `local-exec` provisioners live only in side-effecting modules. In Bash, mark functions with `# Pure query:` or `# Side effect:` comments.

---

## 4. Elimination of Magic Numbers & String Literals

Every numerical value, string identifier, timeout, limit, and status code must have explicit, well-named semantic context.

### Rules:
1. **No Raw Magic Numbers**:
   - Ban numeric literals in logic (e.g. `if (status == 404)`, `pageSize = 20`, `timeout = 30000`).
   - Replace with strongly-typed `enum`, `public const int` / `const val`, `public static readonly`, `StatusCodes.*` / `HttpStatus.*`, or strongly-typed options classes.
2. **No Magic Strings for Configuration or Providers**:
   - Use `DatabaseProvider` enum (`DatabaseProvider.Ms`, `DatabaseProvider.Pg`) and `DatabaseProviderExtensions` (`MsProviderCode` / `MS_PROVIDER_CODE`, `PgProviderCode` / `PG_PROVIDER_CODE`).
   - Use `nameof(...)` in C# when referencing symbols or parameter names.
3. **Database Constraints & Standard Limits**:
   - Define batch sizes, default page limits, and maximum limits in central configuration (`QueryOptions.DefaultPage` / `DEFAULT_PAGE`, `QueryOptions.DefaultPageSize` / `DEFAULT_PAGE_SIZE`, `QueryOptions.MaxPageSize` / `MAX_PAGE_SIZE`).
   - In SQL, use named variables for batch chunks (`DECLARE @BatchSize INT = 5000;`).
   - In Terraform and Bash, name ports, lengths, retries, and timeouts in `locals` / `readonly` constants (`container_http_port`, `password_length`, `MAX_ATTEMPTS`, `DEFAULT_LOCALSTACK_AWS_PORT`).

---

## 5. Eliminate Redundancy via Helper & Extension Functions

Duplicate or boilerplate logic across classes, controllers, repositories, or scripts must be consolidated into reusable helper functions—preferring **extension methods / functions** where the language supports them.

### Rules:
1. **Prefer Extension Functions for Fluent Pipelines (C# & Kotlin)**:
   - When transforming types, building queries, parsing request parameters, or mapping responses, define pure extension methods (`public static class ...Extensions` in C# or top-level `fun Receiver.action(...)` in Kotlin) rather than repeating logic or bloating base classes.
   - Examples: `provider.ToDatabaseProvider()` / `provider.toDatabaseProvider()`, `Request.Query.ToQueryOptions(...)` / `allParams.toQueryOptions(...)`, `query.ApplyFilters(...)` / `query.applyFilters(...)`, `entityTask.ToActionResultAsync()` / `entity.toResponseEntity()`.
2. **Consolidate Repeated Workflows in Scripts & Infrastructure (Python, Bash & Terraform)**:
   - Extract repeated CLI invocations (`psql`, `sqlcmd`, `terraform`, `docker compose`, health probes) into single-responsibility helper functions (`run_psql_query`, `run_sqlcmd_file`, `execute_suite`, `terraform_stack`, `compose`) and map them across inputs using functional composition.
   - Define *what* is deployed once in `crm-infra/terraform/modules/shared` and reuse it from every cloud stack instead of duplicating per provider.
3. **Keep Helpers Pure Where Possible**:
   - Separate pure data transformation helpers (e.g. parsing filter tokens, normalizing pagination bounds) from side-effecting execution helpers (e.g. opening a DB connection or writing an HTTP response).

---

## 6. Universal Anti-Pattern & Common Mistakes Catalog

1. **Shallow Immutability (Mutable Collections Inside Immutable Records / Data Classes)**:
   - *Violation*: Exposing `Dictionary<K, V>`, `List<T>`, `MutableMap<K, V>`, or `MutableList<T>` inside a `record` or `data class`, returning `.ToList()` from C# repositories, or defining `public static QueryOptions Default => new();` (allocating on every read).
   - *Remedy*: Use `IReadOnlyDictionary<K, V>`, `FrozenDictionary<K, V>`, `ImmutableArray<T>`, Kotlin read-only `List<T>` / `Map<K, V>`, and `public static readonly` / `val` fields.
2. **Culture-Sensitive Parsing & JavaBean Reflection Serialization Bugs**:
   - *Violation*: Calling `decimal.TryParse(val, out var d)` or `int.TryParse` in C# without `CultureInfo.InvariantCulture`, or using JavaBean reflection serializers on Kotlin `data class`es (which strip `is*` prefixes from properties like `isDeleted` -> `"deleted"`).
   - *Remedy*: Always pass `NumberStyles` and `CultureInfo.InvariantCulture` in C#, and use JetBrains `kotlinx.serialization` (`@Serializable` with `encodeDefaults = true`) in Kotlin for native compile-time serialization.
3. **Dead Code, Boolean Tautologies & Unused Injected Dependencies**:
   - *Violation*: Leaving `if (cond || true)` in startup pipelines or injecting unused `_logger` fields.
   - *Remedy*: Remove dead fields/parameters and use explicit configuration flags.
4. **Unsealed Concrete Leaf Classes**:
   - *Violation*: Leaving concrete C# controllers, services, repositories, and middleware unsealed (Kotlin classes are `final` by default).
   - *Remedy*: Mark all concrete C# leaf classes `sealed`.
5. **Primitive Obsession**:
   - *Violation*: Passing raw `"ms"` / `"pg"` strings across internal service boundaries.
   - *Remedy*: Parse into `DatabaseProvider` at the boundary via `provider.ToDatabaseProvider()` / `provider.toDatabaseProvider()`.
6. **Sync-over-Async & Unclosed Resources**:
   - *Violation*: Calling `.Result`, `.Wait()`, or `.GetAwaiter().GetResult()` in C#, or opening JDBC `Connection`/`PreparedStatement` without `.use { ... }` in Kotlin.
   - *Remedy*: Use `async`/`await` with `CancellationToken` in C# and `.use { ... }` in Kotlin.
7. **Silent Error Swallowing & 500 Information Disclosure**:
   - *Violation*: Empty `catch` blocks, ignoring shell exit codes, or leaking internal `exception.Message` on `500 Internal Server Error` in production.
   - *Remedy*: Sanitize `500` error details outside Development and enforce `set -euo pipefail` in Bash.
8. **Leaky SQL Abstractions & Injection Vulnerabilities**:
   - *Violation*: String interpolation in SQL queries or `psql` migration runner commands.
   - *Remedy*: Parameterized queries via Dapper / `JdbcDataMapper`, identifier whitelisting via `IsSafeSqlIdentifier()` / `isSafeSqlIdentifier()`, and `psql -v` bind variables (`:'var'`).
9. **Secrets in Plain Configuration & Mutable Artifacts**:
   - *Violation*: Passing connection strings through plain container `environment` maps or command-line flags, committing `.env` / `*.tfstate`, or deploying `:latest` application images.
   - *Remedy*: Platform secret stores (AWS Secrets Manager, Azure Container App secrets), `sensitive = true` Terraform values, git-ignored `.env` files with documented `.env.example` templates, and content-hash image tags.

---

# Part II: Subproject-Specific Standards Summary

## 7. CrmApiCSharp (.NET 10 / C# 13, Dapper, SqlKata, GraphQL, Bruno)
Full details in **[CrmApiCSharp/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/CODING_STANDARDS.md)** (rationale: [ADR 1](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-1-universal-coding-standards-functional-core-immutability-and-command-query-separation)–[ADR 13](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-13-polyglot-feature-parity-api-runtimes-c--kotlin-with-jetbrains-kotlinxserialization)):
- **Functional C# 13**: LINQ projections, switch expressions, and fluent extension methods (`ControllerResultExtensions`, `QueryFilteringExtensions`, `DatabaseProviderExtensions`).
- **Immutability**: `record` entities with `init` properties, `IReadOnlyDictionary` / `FrozenDictionary` filters, and `ImmutableArray<T>` repository results.
- **Explicit Side Effects**: CQS separation (`Get*Async` pure queries vs `Execute*Async` commands); I/O isolated in `BaseRepository.ExecuteWithOpenConnectionAsync` and `ExceptionHandlingMiddleware.WriteProblemResponseAsync`.

## 8. CrmApiKotlinSpringBoot (Kotlin 2.x, Spring Boot, JDBC Data Mapper, GraphQL, Bruno)
Full details in **[CrmApiKotlinSpringBoot/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/CODING_STANDARDS.md)** (rationale: [ADR 1](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-1-universal-coding-standards-functional-core-immutability-and-command-query-separation)–[ADR 13](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-13-polyglot-feature-parity-api-runtimes-c--kotlin-with-jetbrains-kotlinxserialization)):
- **Functional Kotlin 2.x**: Collection/sequence pipelines (`map`, `filter`, `fold`, `associate`), exhaustive `when` expressions, and top-level extension functions (`ControllerResultExtensions.kt`, `QueryFilteringExtensions.kt`, `DatabaseProviderExtensions.kt`).
- **Immutability**: `data class` entities with `val` properties, `@param:JsonProperty("is...") @get:JsonProperty("is...")` parity annotations, immutable `SqlQuery` AST, and read-only `List<T>` / `Map<K, V>`.
- **Explicit Side Effects**: Pure SQL compilation (`SqlCompilerFactory`) separated from JDBC resource management (`executeWithOpenConnection` and `.use { ... }`) and RFC 7807 `ExceptionHandlingAdvice.createProblemDetails`.

## 9. CRMDatabaseMS (SQL Server 2022, SSDT DACPAC, T-SQL)
Full details in **[CRMDatabaseMS/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md)** (rationale: [ADR 4](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-4-immutable-content-addressed-images-platform-secret-stores-and-one-shot-schema-migrators), [ADR 5](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-5-data-access-layer-via-dapper-and-sqlkata-micro-orm--query-object-over-heavy-orm), [ADR 7](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-7-division-of-responsibilities-application-database-encapsulation-vs-relational-invariants); [migration comparison](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/MIGRATION_STRATEGY_COMPARISON.md)):
- **Declarative DACPAC State**: `.sql` files define desired schema state compiled via `Microsoft.Build.Sql`.
- **Set-Based T-SQL**: Tally CTEs and window functions over cursors/loops.
- **Transactional Safety**: `SET NOCOUNT ON; SET XACT_ABORT ON;` and `THROW;` inside `BEGIN CATCH` across all stored procedures (`sp_CleanupAllCRMData`, `sp_SeedStandardData`, `sp_SimulateHeavyETLLoad`).

## 10. CRMDatabasePG (PostgreSQL 16, Flyway Migrations)
Full details in **[CRMDatabasePG/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md)** (rationale: [ADR 4](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-4-immutable-content-addressed-images-platform-secret-stores-and-one-shot-schema-migrators), [ADR 5](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-5-data-access-layer-via-dapper-and-sqlkata-micro-orm--query-object-over-heavy-orm), [ADR 7](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-7-division-of-responsibilities-application-database-encapsulation-vs-relational-invariants); [migration comparison](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/MIGRATION_STRATEGY_COMPARISON.md)):
- **Migration Immutability**: Merged `migrations/V1..V6__*.sql` files are strictly immutable.
- **Set Generators & Volatility**: Use `generate_series` over PL/pgSQL loops, `GENERATED BY DEFAULT AS IDENTITY` over legacy `SERIAL`, `TIMESTAMPTZ` over `TIMESTAMP`, and explicit `IMMUTABLE` / `STABLE` / `VOLATILE` markers.
- **Parameterized Tooling**: `psql -v` bind variables (`:'mig_version'`) in `migrate.py` and `migrate.sh`.

## 11. crm-infra/ (Terraform, LocalStack for AWS & Azure, Docker Compose, Bash)
Full details in **[crm-infra/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/crm-infra/CODING_STANDARDS.md)** (rationale: [ADR 2](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-2-cloud-agnostic-infrastructure-as-code-via-terraform-shared-contract-modules), [ADR 3](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-3-emulation-first-delivery-with-localstack-for-aws--azure-and-offline-terraform-tests), [ADR 4](file:///Users/cy/codes/localstack-reference-architecture/docs/architecture-decisions.md#adr-4-immutable-content-addressed-images-platform-secret-stores-and-one-shot-schema-migrators)):
- **Cloud Portability Contract**: `modules/shared` (pure `crm-catalog` / `crm-runtime-config`, provider-neutral `container-image` / `database-schema`) defines *what* is deployed; only `modules/aws` and `modules/azure` are provider-specific.
- **Terraform Style**: `terraform fmt`, `snake_case`, `for_each` over `count`, described/typed/validated variables, pinned provider versions, one workspace per permutation.
- **Emulation-First**: `localstack_enabled = true` by default with conditional endpoint overrides; LocalStack for AWS on `:4566` and LocalStack for Azure on `:4567`; dummy `test` credentials.
- **Secrets & Images**: `random_password` + `sensitive`, platform secret stores, non-root multi-stage images with content-hash tags, one-shot schema migrators.
- **Bash & Tests**: `set -euo pipefail`, `readonly` constants, shared `lib.sh`, idempotent `up.sh` / `down.sh`, offline `terraform test` with mocked providers.

---

## 12. Automated Pre-Commit Formatting & Import Cleanup

A multi-repo Git `pre-commit` hook is configured across the workspace root, all submodules (`CrmApiCSharp`, `CrmApiKotlinSpringBoot`, `CRMDatabaseMS`, `CRMDatabasePG`), and the nested `crm-infra/` repository to automatically format staged files, remove unused `using` / `import` statements, and re-stage changes before every commit:

- **Hook & Formatter Scripts**:
  - [`.githooks/pre-commit`](file:///Users/cy/codes/localstack-reference-architecture/.githooks/pre-commit): Intercepts staged files in the root repo, any submodule, or `crm-infra/`, runs the formatter, validates Python (`py_compile`) and Bash (`bash -n`) syntax, and re-stages (`git add`) modified files.
  - [`.githooks/clean_and_format.py`](file:///Users/cy/codes/localstack-reference-architecture/.githooks/clean_and_format.py): Runs default language formatters (`dotnet format`, `ktlint`, `ruff`, `shfmt`) alongside deterministic Roslyn `IDE0005` (`dotnet build --no-incremental`) unused-`using` removal/sorting for C#, Kotlin unused-`import` removal/sorting, and Python `ast` unused-`import` removal for Python. Immutable Flyway migration files (`migrations/V*.sql`) are protected from modification.
  - [`.editorconfig`](file:///Users/cy/codes/localstack-reference-architecture/.editorconfig), [`CrmApiCSharp/Directory.Build.props`](file:///Users/cy/codes/localstack-reference-architecture/CrmApiCSharp/Directory.Build.props), & [`CrmApiKotlinSpringBoot/.editorconfig`](file:///Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot/.editorconfig): Enforce code style, `IDE0005` (remove unnecessary usings), and standard formatting rules.
  - [`.pre-commit-config.yaml`](file:///Users/cy/codes/localstack-reference-architecture/.pre-commit-config.yaml): Standard configuration for teams using the `pre-commit` CLI framework.
- **Setup / Manual Execution**:
  ```bash
  # Install hooks across root, all submodules, and crm-infra
  ./.githooks/install-hooks.sh

  # Format and clean imports across all files on demand
  python3 .githooks/clean_and_format.py --all

  # Terraform formatting is not part of the hook; check it explicitly
  terraform fmt -check -recursive crm-infra/terraform
  ```
