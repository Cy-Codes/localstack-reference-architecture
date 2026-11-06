# Enterprise Multi-CRM Reference Architecture — Master Coding Standards

This document is the complete, authoritative specification of coding standards, architectural rules, and anti-pattern remediations across the **Enterprise Multi-CRM Reference Architecture** workspace.

Self-contained copies tailored to each subproject are also maintained directly inside each submodule repository:
- **[CrmApi/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/CODING_STANDARDS.md)** (Universal Standards + .NET 10 / C# 13, Dapper, SqlKata, HotChocolate GraphQL, Bruno)
- **[CRMDatabaseMS/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md)** (Universal Standards + SQL Server 2022, SSDT DACPAC, T-SQL, Python, Bash)
- **[CRMDatabasePG/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md)** (Universal Standards + PostgreSQL 16, Flyway Migrations, PL/pgSQL, Python, Bash)

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

Code across all languages (`C#`, `Python`, `SQL`, `Bash`, `JavaScript`) must favor declarative, functional transformations over state-mutating imperative loops.

### Rules:
1. **Choose Transformations (`map`, `filter`, `reduce`, LINQ, SQL projections) Over Loops**:
   - Transform collections using pure declarative projections (`.Select()`, `.Where()`, `.Aggregate()`, `map()`, `filter()`, list comprehensions, SQL set-based `SELECT ... FROM ... JOIN`).
   - Do not allocate an empty collection, loop over input, and imperatively append elements (`.Add()`, `.append()`).
2. **Acceptable Exceptions for Loops**:
   - Loops (`for`, `foreach`, `while`) are permitted **only** when:
     - **Small datasets or performance-critical micro-benchmarks**: When allocations of delegate/enumerator closures on hot loops cause measured, unacceptable GC pressure (documented with benchmark data).
     - **Streaming large byte buffers / unbuffered streams**: Reading chunk-by-chunk from network or database streams (`while (await reader.ReadAsync(ct))`).
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
   - Use Python `@dataclass(frozen=True)`, `NamedTuple`, `tuple`, and `frozenset`.
   - Collections must be exposed as `IReadOnlyList<T>`, `IReadOnlyDictionary<TKey, TValue>`, `ImmutableArray<T>`, or `FrozenDictionary<TKey, TValue>`.
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
   - **Pure Operations**: `Get...`, `Calculate...`, `Format...`, `Map...`, `To...`, `Find...`, `Parse...`, `Resolve...`.
   - **Side-Effecting Operations**: `Execute...`, `Create...`, `Update...`, `Delete...`, `Save...`, `Write...`, `Publish...`, `Apply...`, `Migrate...`, `Cleanup...`.
3. **Architecture Boundary (Functional Core, Imperative Shell)**:
   - Business calculations, validation rules, query AST composition, and data mappings must reside in pure functions without I/O dependencies.
   - I/O side effects (Dapper database execution, HTTP response writing, process execution) reside strictly at the outer infrastructure and controller boundaries.

---

## 4. Elimination of Magic Numbers & String Literals

Every numerical value, string identifier, timeout, limit, and status code must have explicit, well-named semantic context.

### Rules:
1. **No Raw Magic Numbers**:
   - Ban numeric literals in logic (e.g. `if (status == 404)`, `pageSize = 20`, `timeout = 30000`).
   - Replace with strongly-typed `enum`, `public const int`, `public static readonly`, `StatusCodes.*`, or strongly-typed options classes.
2. **No Magic Strings for Configuration or Providers**:
   - Use `DatabaseProvider` enum (`DatabaseProvider.Ms`, `DatabaseProvider.Pg`) and `DatabaseProviderExtensions` (`MsProviderCode`, `PgProviderCode`).
   - Use `nameof(...)` in C# when referencing symbols or parameter names.
3. **Database Constraints & Standard Limits**:
   - Define batch sizes, default page limits, and maximum limits in central configuration (`QueryOptions.DefaultPage`, `QueryOptions.DefaultPageSize`, `QueryOptions.MaxPageSize`).
   - In SQL, use named variables for batch chunks (`DECLARE @BatchSize INT = 5000;`).

---

## 5. Eliminate Redundancy via Helper & Extension Functions

Duplicate or boilerplate logic across classes, controllers, repositories, or scripts must be consolidated into reusable helper functions—preferring **extension methods** where the language supports them.

### Rules:
1. **Prefer Extension Functions for Fluent Pipelines (C#)**:
   - When transforming types, building queries, parsing request parameters, or mapping responses, define pure `static` extension methods (`public static class ...Extensions`) rather than repeating logic or bloating base classes.
   - Examples: `provider.ToDatabaseProvider()`, `Request.Query.ToQueryOptions(...)`, `query.ApplyFilters(...)`, `query.ApplySorting(...)`, `entityTask.ToActionResultAsync()`.
2. **Consolidate Repeated Workflows in Scripts (Python & Bash)**:
   - Extract repeated CLI invocations (`psql`, `sqlcmd`, health probes) into single-responsibility helper functions (`run_psql_query`, `run_sqlcmd_file`, `execute_suite`) and map them across inputs using functional composition.
3. **Keep Helpers Pure Where Possible**:
   - Separate pure data transformation helpers (e.g. parsing filter tokens, normalizing pagination bounds) from side-effecting execution helpers (e.g. opening a DB connection or writing an HTTP response).

---

## 6. Universal Anti-Pattern & Common Mistakes Catalog

1. **Shallow Immutability (Mutable Collections Inside Immutable Records)**:
   - *Violation*: Exposing `Dictionary<K, V>` or `List<T>` inside a `record`, returning `.ToList()` from repositories, or defining `public static QueryOptions Default => new();` (allocating on every read).
   - *Remedy*: Use `IReadOnlyDictionary<K, V>`, `FrozenDictionary<K, V>`, `ImmutableArray<T>`, and `public static readonly` fields.
2. **Culture-Sensitive Parsing & Formatting Bugs**:
   - *Violation*: Calling `decimal.TryParse(val, out var d)`, `int.TryParse`, or `.ToString()` without `CultureInfo.InvariantCulture`.
   - *Remedy*: Always pass `NumberStyles` and `CultureInfo.InvariantCulture`.
3. **Dead Code, Boolean Tautologies & Unused Injected Dependencies**:
   - *Violation*: Leaving `if (cond || true)` in startup pipelines or injecting unused `_logger` fields.
   - *Remedy*: Remove dead fields/parameters and use explicit configuration flags.
4. **Unsealed Concrete Leaf Classes**:
   - *Violation*: Leaving concrete controllers, services, repositories, and middleware unsealed.
   - *Remedy*: Mark all concrete leaf classes `sealed`.
5. **Primitive Obsession**:
   - *Violation*: Passing raw `"ms"` / `"pg"` strings across internal service boundaries.
   - *Remedy*: Parse into `DatabaseProvider` at the boundary via `provider.ToDatabaseProvider()`.
6. **Sync-over-Async & Thread Blocking**:
   - *Violation*: Calling `.Result`, `.Wait()`, or `.GetAwaiter().GetResult()`.
   - *Remedy*: Use `async`/`await` with `CancellationToken` throughout the call stack.
7. **Silent Error Swallowing & 500 Information Disclosure**:
   - *Violation*: Empty `catch` blocks, ignoring shell exit codes, or leaking internal `exception.Message` on `500 Internal Server Error` in production.
   - *Remedy*: Sanitize `500` error details outside Development and enforce `set -euo pipefail` in Bash.
8. **Leaky SQL Abstractions & Injection Vulnerabilities**:
   - *Violation*: String interpolation in SQL queries or `psql` migration runner commands.
   - *Remedy*: Parameterized queries via Dapper, identifier whitelisting via `IsSafeSqlIdentifier()`, and `psql -v` bind variables (`:'var'`).

---

# Part II: Subproject-Specific Standards Summary

## 7. CrmApi (.NET 10 / C# 13, Dapper, SqlKata, GraphQL, Bruno)
Full details in **[CrmApi/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/CODING_STANDARDS.md)**:
- **Functional C# 13**: LINQ projections, switch expressions, and fluent extension methods (`ControllerResultExtensions`, `QueryFilteringExtensions`, `DatabaseProviderExtensions`).
- **Immutability**: `record` entities with `init` properties, `IReadOnlyDictionary` / `FrozenDictionary` filters, and `ImmutableArray<T>` repository results.
- **Explicit Side Effects**: CQS separation (`Get*Async` pure queries vs `Execute*Async` commands); I/O isolated in `BaseRepository.ExecuteWithOpenConnectionAsync` and `ExceptionHandlingMiddleware.WriteProblemResponseAsync`.

## 8. CRMDatabaseMS (SQL Server 2022, SSDT DACPAC, T-SQL)
Full details in **[CRMDatabaseMS/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/CODING_STANDARDS.md)**:
- **Declarative DACPAC State**: `.sql` files define desired schema state compiled via `Microsoft.Build.Sql`.
- **Set-Based T-SQL**: Tally CTEs and window functions over cursors/loops.
- **Transactional Safety**: `SET NOCOUNT ON; SET XACT_ABORT ON;` and `THROW;` inside `BEGIN CATCH` across all stored procedures (`sp_CleanupAllCRMData`, `sp_SeedStandardData`, `sp_SimulateHeavyETLLoad`).

## 9. CRMDatabasePG (PostgreSQL 16, Flyway Migrations)
Full details in **[CRMDatabasePG/CODING_STANDARDS.md](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/CODING_STANDARDS.md)**:
- **Migration Immutability**: Merged `migrations/V1..V6__*.sql` files are strictly immutable.
- **Set Generators & Volatility**: Use `generate_series` over PL/pgSQL loops, `GENERATED BY DEFAULT AS IDENTITY` over legacy `SERIAL`, `TIMESTAMPTZ` over `TIMESTAMP`, and explicit `IMMUTABLE` / `STABLE` / `VOLATILE` markers.
- **Parameterized Tooling**: `psql -v` bind variables (`:'mig_version'`) in `migrate.py` and `migrate.sh`.

---

## 10. Automated Pre-Commit Formatting & Import Cleanup

A multi-repo Git `pre-commit` hook is configured across the workspace root and all submodules (`CrmApi`, `CRMDatabaseMS`, `CRMDatabasePG`) to automatically format staged files, remove unused `using` / `import` statements, and re-stage changes before every commit:

- **Hook & Formatter Scripts**:
  - [`.githooks/pre-commit`](file:///Users/cy/codes/localstack-reference-architecture/.githooks/pre-commit): Intercepts staged files in the root repo or any submodule, runs the formatter, validates Python (`py_compile`) and Bash (`bash -n`) syntax, and re-stages (`git add`) modified files.
  - [`.githooks/clean_and_format.py`](file:///Users/cy/codes/localstack-reference-architecture/.githooks/clean_and_format.py): Runs default language formatters (`dotnet format`, `ruff`, `shfmt`) alongside deterministic Roslyn `IDE0005` (`dotnet build --no-incremental`) unused-`using` removal/sorting for C# and Python `ast` unused-`import` removal for Python. Immutable Flyway migration files (`migrations/V*.sql`) are protected from modification.
  - [`.editorconfig`](file:///Users/cy/codes/localstack-reference-architecture/.editorconfig) & [`CrmApi/Directory.Build.props`](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/Directory.Build.props): Enable `EnforceCodeStyleInBuild`, `IDE0005` (remove unnecessary usings), and `dotnet_sort_system_directives_first = true`.
  - [`.pre-commit-config.yaml`](file:///Users/cy/codes/localstack-reference-architecture/.pre-commit-config.yaml): Standard configuration for teams using the `pre-commit` CLI framework.
- **Setup / Manual Execution**:
  ```bash
  # Install hooks across root and all submodules
  ./.githooks/install-hooks.sh

  # Format and clean imports across all files on demand
  python3 .githooks/clean_and_format.py --all
  ```
