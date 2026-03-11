# MCP CONTRACT SPECIFICATION

## SECTION 1 — MCP MANIFEST
The capability manifest is defined in `mcp-manifest.json` at the root of the repository. It provides machine-discoverable metadata, supported actions, and schema references.

## SECTION 2 — ACTION SCHEMA CONTRACTS
All actions MUST adhere to the JSON Schemas defined in the `/schemas/actions/` directory. Each action consists of a request schema and a response data schema.

## SECTION 3 — STANDARD RESPONSE ENVELOPE SCHEMA
Every response from the wrapper MUST be a JSON object validating against `schemas/response-envelope.schema.json`. 

Key fields:
- `status`: "success" or "error"
- `action`: The requested action name
- `data`: Action-specific result payload (nullable on error)
- `error`: Formal error object (nullable on success) including `type`, `code`, `message`, `retryable`, and `severity`
- `metadata`: Execution context (timestamp, execution time, authenticated status, request_id, wrapper_version, and protocol_version)

## SECTION 4 — ERROR TAXONOMY
Errors are classified into five stable types:
1. `authentication`: Failures related to identity or permissions.
2. `validation`: Input parameters failing schema constraints.
3. `execution`: Failures during the performance of the action logic.
4. `transport`: Failures in the communication layer.
5. `internal`: Unexpected wrapper failures.

New error codes MUST be added as additive changes to the `error_codes` array in the manifest. Removal or renaming of existing error codes is a breaking change.

## SECTION 5 — DISCOVERY & HANDSHAKE
Clients SHOULD discover capabilities by reading `mcp-manifest.json` or by executing the `MANIFEST` action.
Protocol compatibility MUST be verified using the `mcp-protocol-version` file or the `protocol_version` field in the manifest.

## SECTION 6 — DETERMINISTIC EXECUTION RULES
- **Statelessness**: The wrapper SHOULD be treated as stateless; however, authentication context is persisted via the Azure CLI's internal state.
- **Authentication**: Actions requiring `requires_auth: true` will fail with `AZ_NOT_AUTHENTICATED` if no active session exists.
- **Timeouts**: The wrapper does not enforce internal timeouts beyond the environment defaults. Clients SHOULD implement a 300s timeout for `QUERY` actions.
- **Output**: The wrapper MUST only output valid JSON to `stdout`. Any logging or debugging information MUST be directed to `stderr`.

## SECTION 7 — INSTALLATION & DEPENDENCY CONTRACT
The wrapper requires a Python 3.12+ environment with the Azure CLI (`az`) installed and accessible in the system PATH.
Failures to locate dependencies MUST be reported via the `AZ_CLI_NOT_FOUND` error code.

## SECTION 8 — VERSIONING STRATEGY
- **Semantic Versioning**: The wrapper version follows SemVer (MAJOR.MINOR.PATCH) as defined in the `mcp-wrapper-version` file.
- **Breaking Changes**: Increments MAJOR version. Examples: Removing an action, changing required parameters, changing the response envelope structure.
- **Non-breaking Changes**: Increments MINOR or PATCH version. Examples: Adding an action, adding optional parameters, adding error codes.

## SECTION 9 — MACHINE-READABLE EXAMPLES
Valid interaction examples are provided in the `/examples/` directory.

## SECTION 10 — MCP CONFORMANCE CHECKLIST
- [ ] Inputs are validated against action-specific request schemas.
- [ ] Responses are validated against the global response envelope schema.
- [ ] All error responses use stable error codes from the taxonomy.
- [ ] `stdout` contains zero non-JSON data.
- [ ] `MANIFEST` action returns the current state of `mcp-manifest.json`.
- [ ] Authentication status is accurately reported in the `metadata` block.
- [ ] Execution time is measured and reported in milliseconds.
