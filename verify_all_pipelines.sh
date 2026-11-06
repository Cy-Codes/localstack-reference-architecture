#!/usr/bin/env bash
# ============================================================================
# Master End-to-End Verification Pipeline (Local CI Equivalent)
# Verifies:
#   1. CRMDatabaseMS (DACPAC build + 18 SQL Server tests across Suites 1-3)
#   2. CRMDatabasePG (V1-V6 Migrations + 17 PostgreSQL tests across Suites 1-3)
#   3. CrmApi (.NET 10 build + xUnit tests + 93 Bruno tests x 2 DB engines)
# ============================================================================
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DOTNET_BIN="${DOTNET_BIN:-$(command -v dotnet || echo /Users/cy/.dotnet/dotnet)}"
readonly DOCKER_BIN="${DOCKER_BIN:-$(command -v docker || echo /opt/homebrew/bin/docker)}"

readonly MS_CONTAINER_NAME="crm-database-ms"
readonly MS_DB_NAME="CRMDatabaseMS"
readonly MS_SA_PASSWORD="${MSSQL_SA_PASSWORD:-CrmDev2026!Secure#Pass}"
readonly PG_CONTAINER_NAME="crm_database_pg"

readonly API_PORT=5172
readonly API_BASE_URL="http://localhost:${API_PORT}"
readonly API_HEALTH_URL="${API_BASE_URL}/health"
readonly API_LOG_PATH="/tmp/crmapi_pipeline.log"
readonly MAX_HEALTH_RETRIES=30
readonly HEALTH_RETRY_SLEEP_SECONDS=1

readonly BRUNO_ENVIRONMENTS=("Local-MsSql" "Local-Postgres")

print_banner() {
    local message="$1"
    echo ""
    echo "========================================================================"
    echo " ${message}"
    echo "========================================================================"
}

wait_for_api_health() {
    for _ in $(seq 1 "${MAX_HEALTH_RETRIES}"); do
        if curl -sf "${API_HEALTH_URL}" >/dev/null 2>&1; then
            return 0
        fi
        sleep "${HEALTH_RETRY_SLEEP_SECONDS}"
    done
    echo "Error: CrmApi failed to become healthy at ${API_HEALTH_URL}" >&2
    return 1
}

run_bruno_suite() {
    local env_name="$1"
    "${ROOT_DIR}/CrmApi/bruno/run_tests.sh" "${env_name}"
}

print_banner "STEP 1: CRMDatabaseMS - Build DACPAC & Run SQL Server Test Suite"
"${DOTNET_BIN}" build "${ROOT_DIR}/CRMDatabaseMS/CRMDatabaseMS/CRMDatabaseMS.sqlproj" -c Release
"${DOCKER_BIN}" exec "${MS_CONTAINER_NAME}" /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "${MS_SA_PASSWORD}" -C -d "${MS_DB_NAME}" -b \
    -i /app/tests/03_run_all_tests.sql

print_banner "STEP 2: CRMDatabasePG - Verify Migrations & Run PostgreSQL Test Suite"
"${DOCKER_BIN}" exec "${PG_CONTAINER_NAME}" /workspace/migrate.sh
"${DOCKER_BIN}" exec "${PG_CONTAINER_NAME}" /workspace/tests/run_tests.sh

print_banner "STEP 3: CrmApi - Build & Run xUnit Test Suites"
"${DOTNET_BIN}" test "${ROOT_DIR}/CrmApi/CrmApi.slnx"

print_banner "STEP 4: CrmApi - Run Bruno E2E API Suite (Local-MsSql & Local-Postgres)"
"${DOTNET_BIN}" run --no-build --project "${ROOT_DIR}/CrmApi/src/Api" --urls "${API_BASE_URL}" > "${API_LOG_PATH}" 2>&1 &
API_PID=$!
trap 'kill "${API_PID}" 2>/dev/null || true' EXIT

wait_for_api_health

for env_name in "${BRUNO_ENVIRONMENTS[@]}"; do
    run_bruno_suite "${env_name}"
done

print_banner "ALL DATABASE, UNIT, AND END-TO-END API PIPELINES PASSED SUCCESSFULLY!"
