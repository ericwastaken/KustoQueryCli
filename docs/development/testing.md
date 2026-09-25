# Testing

Run commands from the repository root in the activated development environment.

## Automated regressions and protocol smoke test

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/integration/mcp_smoke.py
```

Automated regressions live under `tests/unit/`. Package markers permit recursive
unittest discovery. The integration smoke test exercises a real stdio session,
tool discovery, introspection, and errors without live login or queries. It uses
temporary Azure state and checks modern/legacy sessions where supported by the
installed client SDK.

An explicit server command can follow the smoke-test script name:

```bash
python tests/integration/mcp_smoke.py docker run --rm -i '<existing-image>' python mcp-stdio-server.py
```

Replace the image placeholder first. Launcher and unit tests do not need a real
Azure account. The scripts under `tests/manual/` are live integration helpers;
inspect their arguments and auth/query side effects before using them.

## Shared CI checks

The authoritative matrix is
[scripts/release-matrix.json](../../scripts/release-matrix.json). Local preparation
and [.github/workflows/test.yml](../../.github/workflows/test.yml) use the same
[scripts/release_checks.py](../../scripts/release_checks.py) runner:

```bash
python scripts/release_checks.py metadata
python scripts/release_checks.py python --python-version 3.12
python scripts/release_checks.py python --python-version 3.13
python scripts/release_checks.py docker --platform linux/amd64
python scripts/release_checks.py docker --platform linux/arm64
```

Select suites relevant to a change; validate all matrix rows for a release. The
runner creates isolated dependency environments, builds local images, checks
resolved dependencies, and tests modern and legacy clients. It writes logs under
`.release/`. Missing runtimes or failed checks must be reported, not silently
skipped. Runtime overrides and platform prerequisites are in
[docs/development/releases.md](releases.md).

For documentation-only changes, check relative links, examples, and consistency
with code. A full Docker build is unnecessary. For entry-point or package moves,
verify historical root launchers and imports in addition to package-level tests.
