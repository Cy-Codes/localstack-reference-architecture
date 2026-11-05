#!/usr/bin/env bash
# ============================================================================
# Master End-to-End Verification Pipeline (Local CI Equivalent)
# Verifies:
#   1. CRMDatabaseMS (DACPAC build + 18 SQL Server tests across Suites 1-3)
#   2. CRMDatabasePG (V1-V6 Migrations + 17 PostgreSQL tests across Suites 1-3)
#   3. CrmApi (.NET 10 build + 21 xUnit tests + 93 Bruno tests x 2 DB engines)
# ============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTNET_BIN="${DOTNET_BIN:-$(command -v dotnet || echo /Users/cy/.dotnet/dotnet)}"
DOCKER_BIN="${DOCKER_BIN:-$(command -v docker || echo /opt/homebrew/bin/docker)}"

echo "========================================================================"
echo " STEP 1: CRMDatabaseMS - Build DACPAC & Run SQL Server Test Suite"
echo "========================================================================"
"${DOTNET_BIN}" build "${ROOT_DIR}/CRMDatabaseMS/CRMDatabaseMS/CRMDatabaseMS.sqlproj" -c Release
"${DOCKER_BIN}" exec crm-database-ms /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P "CrmDev2026!Secure#Pass" -C -d CRMDatabaseMS -b \
  -i /app/tests/03_run_all_tests.sql

echo ""
echo "========================================================================"
echo " STEP 2: CRMDatabasePG - Verify Migrations & Run PostgreSQL Test Suite"
echo "========================================================================"
"${DOCKER_BIN}" exec crm_database_pg /workspace/migrate.sh
"${DOCKER_BIN}" exec crm_database_pg /workspace/tests/run_tests.sh

echo ""
echo "========================================================================"
echo " STEP 3: CrmApi - Build & Run xUnit Test Suites"
echo "========================================================================"
"${DOTNET_BIN}" test "${ROOT_DIR}/CrmApi/CrmApi.slnx"

echo ""
echo "========================================================================"
echo " STEP 4: CrmApi - Run Bruno E2E API Suite (Local-MsSql & Local-Postgres)"
echo "========================================================================"
"${DOTNET_BIN}" run --no-build --project "${ROOT_DIR}/CrmApi/src/Api" --urls http://localhost:5172 > /tmp/crmapi_pipeline.log 2>&1 &
API_PID=$!
trap 'kill ${API_PID} 2>/dev/null || true' EXIT

for i in {1..30}; do
  if curl -sf http://localhost:5172/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

"${ROOT_DIR}/CrmApi/bruno/run_tests.sh" Local-MsSql
"${ROOT_DIR}/CrmApi/bruno/run_tests.sh" Local-Postgres

echo ""
echo "========================================================================"
echo " ALL DATABASE, UNIT, AND END-TO-END API PIPELINES PASSED SUCCESSFULLY!"
echo "========================================================================"
