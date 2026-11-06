---
name: database-verification
description: "Procedures and scripts for building and verifying the dual-lifecycle database systems: SSDT DACPAC (Microsoft.Build.Sql) on SQL Server and Flyway migrations (V1..V6) on PostgreSQL."
metadata:
    namespace: database
---
# Database Verification & Dual-Lifecycle Management

This skill provides direct operational workflows for verifying and maintaining the declarative SQL Server (`CRMDatabaseMS`) and imperative PostgreSQL (`CRMDatabasePG`) database systems.

## 1. CRMDatabaseMS (SQL Server / SSDT DACPAC)

### Build DACPAC
Build the declarative schema project with the `Microsoft.Build.Sql` SDK:
```bash
cd /Users/cy/codes/localstack-reference-architecture/CRMDatabaseMS
dotnet build /p:NetCoreBuild=true
```

### Deploy & Verify SQL Server Schema
Execute schema deployment and run the 18 verification tests across Suites 1–3:
```bash
# Deploy DACPAC
sqlcmd -S localhost -U sa -P 'YourStrong!Pass' -d master -Q "IF DB_ID('CRMDatabaseMS') IS NULL CREATE DATABASE CRMDatabaseMS"
sqlpackage /Action:Publish /SourceFile:bin/Debug/CRMDatabaseMS.dacpac /TargetConnectionString:"Server=localhost;Database=CRMDatabaseMS;User Id=sa;Password=YourStrong!Pass;TrustServerCertificate=True;"

# Run verification test suite
sqlcmd -S localhost -d CRMDatabaseMS -U sa -P 'YourStrong!Pass' -i Tests/04_Run_All_Tests.sql
```

---

## 2. CRMDatabasePG (PostgreSQL / Flyway Migrations)

### Apply Migrations & Run Test Suite
Apply versioned migrations `V1__init_schemas.sql` through `V6__indexes_and_optimizations.sql` and execute the 17 verification tests:
```bash
cd /Users/cy/codes/localstack-reference-architecture/CRMDatabasePG

# Run PostgreSQL test pipeline
./tests/run_tests.sh
```

---

## 3. CrmApiCSharp & CrmApiKotlinSpringBoot Integration & Bruno API Testing

### Run CrmApiCSharp xUnit Tests
```bash
cd /Users/cy/codes/localstack-reference-architecture/CrmApiCSharp
dotnet test CrmApiCSharp.slnx --logger "console;verbosity=normal"
```

### Run CrmApiKotlinSpringBoot JUnit 5 Tests
```bash
cd /Users/cy/codes/localstack-reference-architecture/CrmApiKotlinSpringBoot
./gradlew test
```

### Run Automated Bruno E2E Test Collection
Execute all 93 REST & GraphQL requests against both providers:
```bash
# From CrmApiCSharp/bruno or CrmApiKotlinSpringBoot/bruno
bru run --env Local-MsSql
bru run --env Local-Postgres
```
