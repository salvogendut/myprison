#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
topdir="${RPM_TOPDIR:-"${repo_root}/build/rpm"}"

cd "${repo_root}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required" >&2
    exit 1
fi

if ! python3 -c "import build" >/dev/null 2>&1; then
    echo "python3-build is required; install it with your package manager or pip" >&2
    exit 1
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "rpmbuild is required; install rpm-build and pyproject-rpm-macros" >&2
    exit 1
fi

rm -rf dist "${topdir}"
mkdir -p "${topdir}/BUILD" "${topdir}/BUILDROOT" "${topdir}/RPMS" "${topdir}/SOURCES" "${topdir}/SPECS" "${topdir}/SRPMS"

python3 -m build --sdist --wheel

rpmbuild -ba packaging/myprison.spec \
    --define "_topdir ${topdir}" \
    --define "_sourcedir ${repo_root}/dist"

echo
echo "RPM artifacts:"
find "${topdir}/RPMS" "${topdir}/SRPMS" -type f -name '*.rpm' -print
