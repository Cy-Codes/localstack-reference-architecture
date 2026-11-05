# Enterprise Multi-CRM Reference Architecture

An enterprise-grade reference architecture modeling and serving the **top 3 CRM data models** across two leading relational database engines with an accompanying high-throughput .NET 10 Web API and GraphQL service:

- **Salesforce** (Sales Cloud & Platform Data Model — 15 Tables)
- **HubSpot** (CRM Object & Association Model — 11 Tables)
- **Microsoft Dynamics 365** (Dataverse / Common Data Model — 11 Tables)

Totaling **37 enterprise relational tables** deployed across:
1. **[CRMDatabaseMS](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/README.md)**: Microsoft SQL Server 2022 utilizing a **declarative, state-based DACPAC lifecycle** (`Microsoft.Build.Sql` SDK).
2. **[CRMDatabasePG](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/README.md)**: PostgreSQL 16 utilizing an **imperative, migration-based version control lifecycle** (Flyway-compatible `V1..V6` migrations).
3. **[CrmApi](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/README.md)**: Unified .NET 10 Web API providing high-throughput REST and HotChocolate GraphQL endpoints over Dapper and SqlKata.

Detailed architectural decisions are cataloged in the [Architecture Decision Records (ADR)](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/docs/architecture-decisions.md) and the in-depth [Migration Strategy Comparison](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/MIGRATION_STRATEGY_COMPARISON.md).

---

## 🏛️ Architectural Highlights & Authoritative Sources

Every technical design choice across this reference architecture is grounded in authoritative industry specifications, established architectural patterns, and foundational literature from Martin Fowler and Microsoft Architecture:

### 1. State-Based vs. Migration-Based Database Lifecycles
- **Design Choice**: Provide direct architectural counterparts for the two major database engineering paradigms (SSDT DACPAC declarative state vs. Flyway imperative versioned migrations) managing identical 37-table schemas.
- **Authoritative References**:
  - Pramod Sadalage & Martin Fowler: [Evolutionary Database Design](https://martinfowler.com/articles/evodb.html) — Foundational principles for version-controlled database schemas and continuous integration.
  - Martin Fowler: [Database Migration Pattern](https://martinfowler.com/patterns/database-migration.html) — Pattern catalog for ordered, transactional transition scripts.
  - Microsoft Learn: [SqlPackage & DACFx Architecture](https://learn.microsoft.com/en-us/sql/tools/sqlpackage/sqlpackage) & [SQL Database Projects](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-projects-overview) — Declarative schema models and compilation.
  - Redgate Simple Talk: [State-Based vs. Migration-Based Database Development](https://www.red-gate.com/simple-talk/devops/database-devops/state-based-vs-migration-based-database-development/).

### 2. High-Throughput Micro-ORM & Query Object Patterns
- **Design Choice**: Use **Dapper** directly over `DbDataReader` streams for minimal allocations and **SqlKata** for compiling unified object queries into engine-specific dialects (`SqlServerCompiler` vs `PostgresCompiler`).
- **Authoritative References**:
  - Martin Fowler: [OrmHate](https://martinfowler.com/bliki/OrmHate.html) — Object-relational impedance mismatch and the benefits of lightweight data mapping.
  - Martin Fowler: [Data Mapper Pattern](https://martinfowler.com/eaaCatalog/dataMapper.html) (*Patterns of Enterprise Application Architecture* [P of EAA]) — Decoupling memory objects from relational schemas.
  - Martin Fowler: [Query Object Pattern](https://martinfowler.com/eaaCatalog/queryObject.html) (*P of EAA*) — Representing queries as composable interpreter trees.
  - Dapper Micro-ORM: [Benchmarks & Documentation](https://github.com/DapperLib/Dapper#benchmarks).
  - SqlKata: [Documentation & Query Builder](https://sqlkata.com/docs).

### 3. Dynamic Multi-Provider Routing & Facade Abstraction
- **Design Choice**: Parameterized URL routing (`/api/{provider:regex(^(ms|pg)$)}/v1/{crm}/{resource}`) enabling runtime database selection, side-by-side benchmarking, and zero-downtime database migration.
- **Authoritative References**:
  - Martin Fowler: [Branch By Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — Running dual implementations in parallel behind a common interface.
  - Martin Fowler: [Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html) — Seamless migration through routing facades.
  - Martin Fowler: [Richardson Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html) — Resource URIs and standard HTTP methods.
  - Microsoft: [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines).

### 4. Clean Architecture Layering & Inversion of Control
- **Design Choice**: Decoupled 4-tier structure (`Domain`, `Infrastructure`, `Application`, `Api`) with inward dependency flow, enabling transport independence (REST and GraphQL reuse the same application services).
- **Authoritative References**:
  - Martin Fowler: [PresentationDomainDataLayering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html) — Separating presentation, domain, and data source concerns.
  - Martin Fowler: [Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html) — Decoupled service assembly.
  - Martin Fowler: [Separated Interface](https://martinfowler.com/eaaCatalog/separatedInterface.html) (*P of EAA*).
  - Microsoft Learn: [Common Web Application Architectures](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures).
  - Robert C. Martin: [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html).

### 5. Solving the N+1 Problem with GraphQL DataLoaders
- **Design Choice**: HotChocolate GraphQL integration with `IDataLoader` batching, converting $N$ individual relationship queries into a single parameterized `WHERE id IN (...)` round-trip.
- **Authoritative References**:
  - Martin Fowler: [Lazy Load / N+1 Problem](https://martinfowler.com/eaaCatalog/lazyLoad.html) (*P of EAA*).
  - Lee Byron: [GraphQL DataLoader Pattern](https://github.com/graphql/dataloader).
  - ChilliCream: [HotChocolate DataLoaders Documentation](https://chillicream.com/docs/hotchocolate/v13/fetching-data/dataloader).
  - GraphQL Foundation: [GraphQL Specification](https://spec.graphql.org/).

### 6. Standardized Error Handling via Problem Details
- **Design Choice**: Centralized middleware emitting RFC 7807 / RFC 9457 compliant `application/problem+json` envelopes.
- **Authoritative References**:
  - IETF: [RFC 7807: Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807) & [RFC 9457](https://datatracker.ietf.org/doc/html/rfc9457).
  - Microsoft Learn: [Handle errors in ASP.NET Core web APIs](https://learn.microsoft.com/en-us/aspnet/core/web-api/handle-errors).
  - Martin Fowler: [Notification Pattern](https://martinfowler.com/articles/replaceThrowWithNotification.html).

### 7. Application Database Encapsulation & Domain Ownership
- **Design Choice**: Business logic, multi-entity validation, and test automation reside exclusively in the API layer, treating the database as an encapsulated Application Database and reserving database CPU for indexed data access and structural constraints.
- **Authoritative References**:
  - Martin Fowler: [Application Database](https://martinfowler.com/bliki/ApplicationDatabase.html) & [Integration Database](https://martinfowler.com/bliki/IntegrationDatabase.html) — Encapsulating data access behind a single service boundary and eliminating shared database coupling.
  - Martin Fowler: [Domain Logic and SQL](https://martinfowler.com/articles/dblogic.html) — Engineering trade-offs of domain logic in application code vs. stored procedures.
  - Martin Fowler: [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html) & [Microservice Testing](https://martinfowler.com/articles/microservice-testing/).
  - Martin Fowler: [Smart Endpoints and Dumb Pipes](https://martinfowler.com/articles/microservices.html#SmartEndpointsAndDumbPipes).
  - The Twelve-Factor App: [Stateless Processes & Backing Services](https://12factor.net/).
  - AWS: [AWS Well-Architected Framework: Performance Efficiency & Reliability](https://aws.amazon.com/architecture/well-architected/).

---

## 📁 Repository Overview

| Subproject | Description | Technologies |
| :--- | :--- | :--- |
| **[CRMDatabaseMS](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS/README.md)** | State-based declarative CRM database | Microsoft SQL Server 2022, SSDT, `Microsoft.Build.Sql`, DACPAC, `sqlcmd` |
| **[CRMDatabasePG](file:///Users/cy/codes/localstack-reference-architecture/CRMDatabasePG/README.md)** | Migration-based imperative CRM database | PostgreSQL 16 Alpine, Flyway SQL Migrations (`V1..V6`), `psql` |
| **[CrmApi](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/README.md)** | High-performance multi-provider CRM Web API | .NET 10, C# 13, Dapper, SqlKata, HotChocolate GraphQL, Bruno |
| **[CrmApi Bruno](file:///Users/cy/codes/localstack-reference-architecture/CrmApi/bruno/README.md)** | Git-native automated API test collection | Bruno CLI (`bru`), 93 automated endpoint tests per provider |

---

## 🚀 One-Command Verification Pipeline

Run the master end-to-end verification pipeline, validating all database migrations, DACPAC builds, SQL Server tests, PostgreSQL tests, xUnit tests, and Bruno API test suites:

```bash
./verify_all_pipelines.sh
```

### What the Pipeline Validates:
1. **CRMDatabaseMS**: Builds `CRMDatabaseMS.dacpac` with the `Microsoft.Build.Sql` SDK and runs 18 SQL Server verification tests across Suites 1–3 (`03_run_all_tests.sql`).
2. **CRMDatabasePG**: Applies migrations `V1__init_schemas.sql` through `V6__indexes_and_optimizations.sql` and executes 17 PostgreSQL verification tests across Suites 1–3 (`tests/run_tests.sh`).
3. **CrmApi Unit & Integration Tests**: Runs 21 xUnit tests covering SqlKata compilation, provider mapping, and WebApplicationFactory integration endpoints.
4. **Bruno E2E Test Suite**: Spins up `CrmApi` and runs all 93 automated REST and GraphQL requests against both **Microsoft SQL Server** (`Local-MsSql`) and **PostgreSQL** (`Local-Postgres`).
