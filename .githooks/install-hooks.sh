#!/usr/bin/env bash
# ============================================================================
# Installs the pre-commit hook across the root repository and all submodules.
# ============================================================================
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly HOOK_SOURCE="${ROOT_DIR}/.githooks/pre-commit"
readonly FORMATTER_SCRIPT="${ROOT_DIR}/.githooks/clean_and_format.py"

chmod +x "${HOOK_SOURCE}" "${FORMATTER_SCRIPT}"

install_hook_target() {
    local target_dir="$1"
    if [ -d "${target_dir}" ]; then
        cp "${HOOK_SOURCE}" "${target_dir}/pre-commit"
        chmod +x "${target_dir}/pre-commit"
        echo "  [Installed] ${target_dir}/pre-commit"
    fi
}

echo "==> Installing pre-commit hooks across workspace and submodules..."
git -C "${ROOT_DIR}" config core.hooksPath .githooks
install_hook_target "${ROOT_DIR}/.git/hooks"

for submodule in CrmApi CRMDatabaseMS CRMDatabasePG; do
    install_hook_target "${ROOT_DIR}/.git/modules/${submodule}/hooks"
done

echo "==> Pre-commit hooks installed and active!"
