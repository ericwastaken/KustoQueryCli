# Development setup

Clone the repository and work from its root. Inspect `git status` before editing
and preserve unrelated work, scratch files, caches, and credentials.

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Python 3.12 is the baseline. The authoritative test combinations are in
[scripts/release-matrix.json](../../scripts/release-matrix.json), including the
additional Python runtime, current MCP SDK, legacy clients, and Docker platforms.
On Apple Silicon, prefer native ARM interpreters. On Windows CMD, use the virtual
environment's `Scripts` activation script.

Install Azure CLI separately for native authenticated use. Mocked regressions and
the automated stdio smoke test do not require a live Azure account. Docker includes
Azure CLI. Live-query helpers require your own authorized account and target.

Choose the guide for your change:

- [Architecture](architecture.md): entry points, shared services, contracts.
- [Python](python.md): CLI, MCP, action handlers, and regression coverage.
- [Containers](containers.md): build context, image selection, launchers.
- [Testing](testing.md): automated checks and manual integration boundaries.
- [Releases](../../RELEASING.md): requested version preparation and validation.

The root launchers are supported entry points. The project runs from a checkout;
no package publishing or editable-install step is required for development.
