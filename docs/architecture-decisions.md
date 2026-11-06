# Architecture Decision Records (ADR) & Design Rationale

This document outlines the foundational technical decisions for the **CrmApiCSharp** (.NET 10 / C# 13) and **CrmApiKotlinSpringBoot** (Kotlin 2.x / Spring Boot) projects, serving relational replica data from **Microsoft SQL Server** (`CRMDatabaseMS`) and **PostgreSQL** (`CRMDatabasePG`) across Salesforce, HubSpot, and Microsoft Dynamics 365.

Every design choice is grounded in enterprise architectural patterns, authoritative industry specifications, and established literature from Martin Fowler, Microsoft Architecture Guides, and database/API consensus.

---

## Table of Contents
- [ADR 1: Data Access Layer via Dapper and SqlKata (Micro-ORM & Query Object over Heavy ORM)](#adr-1-data-access-layer-via-dapper-and-sqlkata-micro-orm--query-object-over-heavy-orm)
- [ADR 2: Dynamic Multi-Provider Routing (`/api/{provider}/v1/...`)](#adr-2-dynamic-multi-provider-routing-apiproviderv1)
- [ADR 3: Clean Architecture Layering & Inversion of Control](#adr-3-clean-architecture-layering--inversion-of-control)
- [ADR 4: HotChocolate GraphQL Foundation with DataLoader Batching](#adr-4-hotchocolate-graphql-foundation-with-dataloader-batching)
- [ADR 5: Repository and Abstract Factory Patterns for Multi-Engine Persistence](#adr-5-repository-and-abstract-factory-patterns-for-multi-engine-persistence)
- [ADR 6: Standardized Error Handling via RFC 7807 / RFC 9457 Problem Details](#adr-6-standardized-error-handling-via-rfc-7807--rfc-9457-problem-details)
- [ADR 7: Stateless Offset Pagination and Dynamic Filtering via Immutable Value Objects](#adr-7-stateless-offset-pagination-and-dynamic-filtering-via-immutable-value-objects)
- [ADR 8: Division of Responsibilities: Application Database Encapsulation vs. Relational Invariants](#adr-8-division-of-responsibilities-application-database-encapsulation-vs-relational-invariants)

---

## ADR 1: Data Access Layer via Dapper and SqlKata (Micro-ORM & Query Object over Heavy ORM)

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

4. **Decoupling Application from Database Schema Governance**:
   - Schemas are governed in dedicated database projects (`CRMDatabaseMS` via DACPAC and `CRMDatabasePG` via Flyway). Tying the API to EF Core migrations would create dual-state synchronization debt and violate single-source-of-truth principles.
   - *References*:
     - Pramod Sadalage & Martin Fowler: [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html) — Outlines why database migrations must be independently versioned and automated alongside application deployments rather than generated implicitly.
     - Martin Fowler: [Database Migration Pattern](https://martinfowler.com/patterns/database-migration.html).

### Outcomes

#### Strategic Architectural Advantages
- **Hardware Efficiency & Zero Allocation Overhead**: By bypassing EF Core's change-tracker, snapshot buffers, and dynamic proxy generation, Dapper streams rows directly from `DbDataReader` into records, achieving near-zero GC pressure and raw ADO.NET throughput under high concurrent load.
- **Deterministic Multi-Dialect Query Generation**: SqlKata query trees compile cleanly to engine-specific SQL (T-SQL bracketed schemas with `OFFSET...FETCH` vs PostgreSQL quoted identifiers with `LIMIT...OFFSET`) from a single query definition, eliminating dialect drift and duplicated query logic.
- **SQL Injection Immunity by Construction**: SqlKata binds query parameters as strictly typed named parameters (`@p0`, `@p1`), preventing injection attacks without relying on manual parameter sanitization.
- **Complete Decoupling from Database Migration Lifecycle**: Eliminates the "dual-state synchronization debt" where EF Core model snapshots drift from actual database DDL. Database schemas remain independently version-controlled and governed via DACPAC (`CRMDatabaseMS`) and Flyway (`CRMDatabasePG`).

#### Architectural Guardrails & Governance
- **Explicit Graph Mapping over Magic Lazy Loading**: Deep hierarchical object graphs (e.g. Accounts with multiple Contact and Opportunity collections) require explicit mapping queries or DataLoader batching rather than ORM navigation properties. This deliberate trade-off trades implicit, uncontrolled queries for explicit, predictable performance.
- **Automated Schema Verification in CI**: To guard against column name drift between database schemas and Dapper models, automated integration tests and database schema verification suites execute on every pull request, ensuring model fidelity without requiring heavy ORM metadata scaffolding.

---

## ADR 2: Dynamic Multi-Provider Routing (`/api/{provider}/v1/...`)

### Status
Accepted

### Context
Clients must be able to interrogate either database engine (`ms` for Microsoft SQL Server, `pg` for PostgreSQL) dynamically across any CRM entity using standard RESTful conventions, enabling live benchmarking, verification, and migration without deploying separate APIs.

### Decision
Adopt route templates parameterized by the provider token constrained by regex:
```http
/api/{provider:regex(^(ms|pg)$)}/v1/{crm}/{resource}
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

### Outcomes

#### Strategic Architectural Advantages
- **Risk-Free Dual-Engine Verification (Branch By Abstraction)**: Running SQL Server (`ms`) and PostgreSQL (`pg`) simultaneously behind an identical URI surface enables direct performance benchmarking, functional verification, and continuous parity checking across engines without deploying or maintaining separate API instances.
- **Transparent Strangler Fig Migration**: Downstream consumers can gradually migrate from legacy SQL Server instances to cloud-native PostgreSQL by toggling a single path parameter or header, enabling phased zero-downtime database transitions without breaking client contracts.
- **Declarative Route Guardrails**: Utilizing regex constraints (`{provider:regex(^(ms|pg)$)}`) ensures invalid database provider tokens are rejected at the routing gateway with standard HTTP 404 responses before executing any application or database code.

#### Architectural Guardrails & Governance
- **Encapsulated Provider Context Propagation**: Every controller endpoint and query service accepts and propagates the `DatabaseProvider` discriminator to resolve the correct connection factory and compiler. This routing logic is strictly encapsulated via `BaseCrmController` and `IDbConnectionFactory`, preventing provider-specific leaks into domain contracts.
- **Strict Schema Parity Enforcement**: Both SQL Server and PostgreSQL database instances must strictly conform to identical entity definitions and column types, enforced via automated database schema assertion test suites (`tests/01_schema_structure_tests.sql`).

---

## ADR 3: Clean Architecture Layering & Inversion of Control

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

### Outcomes

#### Strategic Architectural Advantages
- **Transport Protocol Independence**: REST controllers and GraphQL resolvers function merely as lightweight transport adapters; 100% of business querying, filtering, and pagination rules live in shared Application services, completely eliminating protocol-specific logic duplication.
- **Inversion of Control & High Testability**: Inward-pointing dependencies and separated interfaces allow every application service to be unit-tested in isolation in milliseconds with mock repositories, freeing test suites from database dependencies.
- **Long-Term Maintainability & Domain Protection**: Domain records and contracts have zero third-party dependencies (no ASP.NET Core, no Dapper, no database drivers), protecting the core CRM model from external framework churn or breaking library upgrades.

#### Architectural Guardrails & Governance
- **Strict Layer Boundary Enforcement**: Developers must resist leaking infrastructure concerns (e.g. `SqlConnection`, raw SQL strings) or transport concerns (e.g. `HttpContext`, HTTP status codes) into the `Domain` or `Application` layers. This is enforced via compile-time project reference boundaries.
- **Separated Interface Governance**: Every repository and query service is governed by an explicit interface (`ISalesforceQueryService`, `ISalesforceRepository`), ensuring that implementations remain interchangeable and fully mockable during testing.

---

## ADR 4: HotChocolate GraphQL Foundation with DataLoader Batching

### Status
Accepted

### Context
In addition to REST endpoints, clients require a flexible query interface capable of selecting specific fields and navigating related entities (e.g. Accounts with Contacts, Opportunities with LineItems) without suffering from the $N+1$ query problem.

### Decision
Implement **HotChocolate GraphQL** utilizing the `IDataLoader` pattern for batching child entity queries over Dapper and SqlKata.

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

### Outcomes

#### Strategic Architectural Advantages
- **Bounded Query Execution ($O(1)$ Batching)**: The `IDataLoader` pattern guarantees that child entity lookups (e.g. Contacts for 50 Accounts) are batched into a single parameterized SQL query (`WHERE "AccountId" IN (...)`) per relationship level, completely eliminating the catastrophic $N+1$ query problem that plagues unoptimized GraphQL and ORM implementations.
- **Client-Driven Payload Optimization**: Clients select exactly the fields and relationship depths they require, drastically reducing network payload size and mobile data consumption without writing tailored REST view endpoints.
- **Unified Data Access Engine**: GraphQL resolvers do not execute independent SQL queries; they route through the same `Application` query services and Dapper repositories as REST, maintaining single-source-of-truth semantics.

#### Architectural Guardrails & Governance
- **Schema Type Governance**: Code-first GraphQL schema definitions (`SalesforceAccountType`, `SalesforceContactType`) must be explicitly declared and maintained to expose child navigation fields and link DataLoaders cleanly.
- **Query Complexity Protection**: While field selection is client-driven, production deployments must enforce HotChocolate query depth and complexity limits (`AddMaxExecutionDepth`, `AddMaxAllowedPagingBounds`) to guard the database against maliciously nested or recursive GraphQL requests.

---

## ADR 5: Repository and Abstract Factory Patterns for Multi-Engine Persistence

### Status
Accepted

### Context
The application must instantiate either `Microsoft.Data.SqlClient.SqlConnection` or `Npgsql.NpgsqlConnection`, and pair it with either `SqlServerCompiler` or `PostgresCompiler`, transparently at runtime per request based on the `{provider}` token.

### Decision
Implement the **Abstract Factory Pattern** (`IDbConnectionFactory`, `ISqlKataCompilerFactory`) injected into a **Repository Pattern** (`BaseRepository`, `SalesforceRepository`, `HubSpotRepository`, `Dynamics365Repository`).

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
   - *References*:
     - OWASP Foundation: [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

### Outcomes

#### Strategic Architectural Advantages
- **Encapsulated Connection Lifecycle Management**: The `IDbConnectionFactory` encapsulates connection string resolution, database credentials, and engine instantiation (`SqlConnection` vs `NpgsqlConnection`) behind a unified factory, guaranteeing proper async disposal (`await using`) and preventing connection pool exhaustion.
- **Compile-Time Singleton Efficiency**: `ISqlKataCompilerFactory` maintains singleton, thread-safe instances of `SqlServerCompiler` and `PostgresCompiler`, avoiding unnecessary object allocations on high-frequency query paths.
- **Defense-in-Depth Injection Prevention**: Column identifiers and sorting keys are strictly validated against compiled regular expressions (`SafeIdentifierRegex`), while all user-supplied filter values are bound as parameterized variables.

#### Architectural Guardrails & Governance
- **Connection Pooling & Transient Fault Governance**: Direct ADO.NET connection creation relies on connection pooling configured within connection strings. Production environments must configure transient connection retry policies (e.g. `EnableRetryOnFailure` or Polly execution policies) within the factory implementation.
- **Repository Granularity**: Generic query execution is centralized in `BaseRepository`, while domain-specific entity queries reside in dedicated CRM repositories (`SalesforceRepository`, etc.), preventing god-object anti-patterns.

---

## ADR 6: Standardized Error Handling via RFC 7807 / RFC 9457 Problem Details

### Status
Accepted

### Context
When exceptions occur (e.g. invalid database provider, bad filter parameter, missing entity, database timeout), the API must return standardized, machine-readable HTTP error payloads without leaking internal server stack traces or database connection details.

### Decision
Implement custom ASP.NET Core middleware (`ExceptionHandlingMiddleware`) returning standard **`ProblemDetails`** payloads with `Content-Type: application/problem+json` compliant with RFC 7807 and RFC 9457.

### Rationales & Authoritative Sources

1. **RFC 7807 / RFC 9457 Standardized Problem Details**:
   - Defines a standardized JSON schema for HTTP API errors (`status`, `title`, `detail`, `instance`), eliminating custom ad-hoc error formats across endpoints.
   - *References*:
     - IETF RFC 7807: [Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807).
     - IETF RFC 9457: [Problem Details for HTTP APIs (Updated RFC)](https://datatracker.ietf.org/doc/html/rfc9457).
     - Microsoft Learn: [Handle errors in ASP.NET Core web APIs](https://learn.microsoft.com/en-us/aspnet/core/web-api/handle-errors).

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

## ADR 7: Stateless Offset Pagination and Dynamic Filtering via Immutable Value Objects

### Status
Accepted

### Context
Querying 37 enterprise CRM entities requires uniform, stateless handling of pagination (`page`, `pageSize`), multi-column sorting (`sortBy`, `sortDirection`), and arbitrary field filtering (`{field}={value}`) across both SQL dialects.

### Decision
Model query parameters as an immutable `QueryOptions` record and return responses wrapped in an immutable `PagedResult<T>` envelope containing metadata (`Items`, `TotalCount`, `Page`, `PageSize`, `TotalPages`, `HasPreviousPage`, `HasNextPage`).

### Rationales & Authoritative Sources

1. **Value Object Pattern**:
   - Query options and paged responses are immutable value objects defined by their attributes rather than identity, guaranteeing thread safety and eliminating mutation bugs across layers.
   - *References*:
     - Martin Fowler: [Value Object](https://martinfowler.com/bliki/ValueObject.html) — Immutable objects compared by value rather than identity.
     - Martin Fowler: [Data Transfer Object (DTO)](https://martinfowler.com/eaaCatalog/dataTransferObject.html) (*P of EAA*) — Packaging data between processes to reduce round-trips.

2. **Microsoft REST API Guidelines on Collections & Pagination**:
   - Adheres to standard pagination patterns using `page` and `pageSize` (defaulting to 20, capped at 100), accompanied by total item counts and page calculation.
   - *References*:
     - Microsoft: [Microsoft REST API Guidelines Section 9 (Collections)](https://github.com/microsoft/api-guidelines#9-collections).

### Outcomes

#### Strategic Architectural Advantages
- **Predictable, Uniform Client Experience**: All 37 entity endpoints across Salesforce, HubSpot, and Dynamics 365 adhere to an identical query protocol (`page`, `pageSize`, `sortBy`, `sortDirection`, `{filterKey}={filterVal}`), dramatically simplifying client SDK implementation and API documentation.
- **Immutable Value Objects & Thread Safety**: Modeling query parameters as immutable records (`QueryOptions`) and responses as envelopes (`PagedResult<T>`) eliminates state mutation bugs across asynchronous request execution pipelines.
- **Stateless Horizontal Scalability**: Zero server-side session state or cursors are maintained in memory; each query request is completely self-contained, allowing API containers to scale horizontally behind round-robin load balancers without sticky sessions.

#### Architectural Guardrails & Governance
- **Bounded Page Sizes to Guard Against Database Exhaustion**: The `BaseRepository` hard-caps `pageSize` to a maximum of 100 records (defaulting to 20), preventing malicious or poorly designed client queries from attempting to load millions of records into memory at once.
- **Deep-Offset Query Latency**: While offset pagination (`OFFSET...FETCH` / `LIMIT...OFFSET`) is optimal and expected for standard CRM interactive navigation (pages 1 through 100), extremely deep offsets (e.g. page 10,000+) incur database scan costs. For massive bulk export scenarios, dedicated bulk ETL procedures or keyset pagination patterns should be introduced as a complementary pattern.

---

## ADR 8: Division of Responsibilities: Application Database Encapsulation vs. Relational Invariants

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
   - Fast, reliable CI/CD pipelines depend on running thousands of in-memory domain tests in seconds (`dotnet test`). Moving business logic into the database makes in-memory testing impossible and creates flaky, slow CI builds.
   - *References*:
     - Martin Fowler: [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html).
     - Martin Fowler: [Microservice Testing](https://martinfowler.com/articles/microservice-testing/).

5. **Cloud Infrastructure Economics: Horizontal vs. Vertical Scaling (AWS Well-Architected)**:
   - Stateless API containers scale out horizontally on low-cost commodity compute or Kubernetes pods. In contrast, relational database compute is the most expensive and vertically constrained resource in the enterprise (often incurring steep per-core database licensing). Squandering database CPU cycles on procedural business calculations creates an expensive, unscalable infrastructure bottleneck.
   - *References*:
     - AWS: [AWS Well-Architected Framework: Performance Efficiency & Reliability](https://aws.amazon.com/architecture/well-architected/).

### Outcomes

#### Strategic Architectural Advantages
- **Single Source of Truth**: 100% of domain rules, calculations, and validations reside in version-controlled C# domain services with full IDE and compiler assistance, eliminating the dual-maintenance trap.
- **True Engine Portability**: The same business logic operates concurrently against both Microsoft SQL Server and PostgreSQL without maintaining twin procedural codebases in T-SQL and PL/pgSQL.
- **Sub-Second CI/CD Execution**: Automated test suites validate the domain model in seconds during pull requests without provisioning database instances.
- **Compute Optimization**: Database CPU/IOPS are preserved exclusively for indexing, query plan execution, and ACID transactions—delivering maximum relational throughput.
- **Non-Bypassable Security & Audit Boundary**: Centralizing access through the API guarantees that all operations enforce authentication, authorization, input validation, and structured telemetry.

#### Architectural Guardrails & Governance
- **Strict Encapsulation (No Direct DB Write Access)**: Direct write access to relational storage from reporting tools, third-party consumers, or ad-hoc scripts is explicitly denied. All mutations must route through API domain services.
- **Structural Invariants at the Storage Tier**: The database layer is not passive; it rigorously enforces declarative relational invariants (primary keys, foreign keys, unique constraints, NOT NULL constraints, check constraints, and ACID transactions), guaranteeing that no invalid or orphaned data can ever be persisted under any operational circumstance.
