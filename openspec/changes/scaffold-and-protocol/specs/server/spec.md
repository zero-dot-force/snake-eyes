## ADDED Requirements

### Requirement: Line-delimited stdio transport
The system SHALL read one JSON object per line from stdin and write one JSON object per line to stdout, flushing after every response. The system SHALL NOT use LSP Content-Length headers. Trailing `\r` on request lines SHALL be stripped so Windows `\r\n` line endings are accepted. A write failure (e.g. `BrokenPipeError` when Gaze closes the pipe) SHALL be treated as clean teardown — exit 0 without a traceback to stdout.

#### Scenario: One response per request line
- **WHEN** a single request line is written to stdin
- **THEN** exactly one response line is written to stdout and flushed

#### Scenario: CRLF line endings accepted
- **WHEN** a request line terminated with `\r\n` is written
- **THEN** exactly one response line is written, identical to a `\n`-terminated request

#### Scenario: Write failure is clean teardown
- **WHEN** a response is written to a stdout whose `write` raises `BrokenPipeError`
- **THEN** the process exits with code 0 and no traceback is written to stdout

### Requirement: Sequential processing
The system SHALL process requests sequentially, one at a time, and SHALL NOT pipeline or process requests concurrently.

#### Scenario: Multiple requests handled in order
- **WHEN** two valid request lines are written
- **THEN** two responses are produced in the same order as the requests

### Requirement: Empty line and EOF handling
The system SHALL ignore empty and whitespace-only lines. On stdin EOF without a prior `shutdown`, the system SHALL exit 0 without writing a response. Signal-based termination (SIGTERM/SIGINT) falls back to default Python behavior; no deterministic teardown is required for a Gaze-managed subprocess.

#### Scenario: Empty line ignored
- **WHEN** an empty line is written between requests
- **THEN** no response is produced for the empty line

#### Scenario: EOF exits cleanly
- **WHEN** stdin is closed without a `shutdown` request
- **THEN** the process exits with code 0 and writes no response

### Requirement: Parse error handling
The system SHALL respond to malformed JSON with a parse error (`-32700`) using `id` of `null`, and SHALL remain alive to process subsequent requests. Input that fails to decode as UTF-8 text, and JSON whose nesting exceeds the interpreter's recursion limit, SHALL likewise yield `-32700` with `id` of `null` while the server remains alive.

#### Scenario: Malformed JSON yields parse error
- **WHEN** a line containing invalid JSON (e.g. `{not json`) is written
- **THEN** a `-32700` error with `id: null` is written and the process remains alive for a subsequent valid request

### Requirement: Invalid request handling
The system SHALL respond with `-32600` when a line is valid JSON but is not an object, is missing `jsonrpc` or `method`, or has a `jsonrpc` value other than `"2.0"`. The error SHALL use the request `id` if present, otherwise `null`. A line exceeding the 16 MiB size bound SHALL be rejected with `-32600` and `id` of `null` without being parsed, and the server SHALL remain alive.

#### Scenario: Missing method field
- **WHEN** a JSON object without a `method` field is written
- **THEN** a `-32600` error is written using the request `id` if present, otherwise `null`

#### Scenario: Missing jsonrpc field
- **WHEN** a JSON object without a `jsonrpc` field is written
- **THEN** a `-32600` error is written using the request `id` if present, otherwise `null`

#### Scenario: Non-object request
- **WHEN** a line that is valid JSON but not an object (e.g. a JSON array) is written
- **THEN** a `-32600` error is written using the request `id` if present, otherwise `null`

#### Scenario: Wrong jsonrpc version
- **WHEN** a request with `jsonrpc` present but not equal to `"2.0"` is written
- **THEN** a `-32600` error is written using the request `id` if present, otherwise `null`

### Requirement: Method not found
The system SHALL respond to an unknown method with `-32601` and message `Method not found: <method>`. The echoed method name SHALL be truncated to 64 characters.

#### Scenario: Unknown method
- **WHEN** a request with an unrecognized method name is written
- **THEN** a `-32601` error with message `Method not found: <method>` is written

### Requirement: Injectable dispatch table
The system SHALL accept an injectable dispatch table (mapping of method name to handler callable) via the `Server` constructor, defaulting to the built-in `initialize`/`shutdown` table. Tests SHALL be able to register a handler — including a raising handler — to exercise dispatch and error paths through stdin/stdout without altering the built-in method set.

#### Scenario: Raising handler registered via injected dispatch
- **WHEN** a handler that raises is registered through the injected dispatch table and a request for that method is written
- **THEN** the `-32603` internal-error response is produced through the normal stdin/stdout loop

### Requirement: Internal error handling
When a handler raises an exception, the system SHALL respond with `-32603` and the exception message. Tracebacks SHALL NOT be written to stdout; they MAY be written to stderr.

#### Scenario: Handler exception yields internal error
- **WHEN** a handler registered via the injected dispatch table raises
- **THEN** a `-32603` error with the exception message is written to stdout and no traceback is written to stdout

### Requirement: initialize dispatch and idempotency
The system SHALL dispatch `initialize` and MAY be called more than once; a second `initialize` SHALL be answered with a valid result without error.

#### Scenario: Repeated initialize succeeds
- **WHEN** `initialize` is sent twice
- **THEN** both requests receive a valid result response

#### Scenario: initialize with invalid params
- **WHEN** an `initialize` request lacks a string `root_path` in `params`
- **THEN** a `-32602` invalid params error is returned

### Requirement: shutdown exits the process
The system SHALL answer `shutdown` with a success result `{}` and then terminate the process with exit code 0.

#### Scenario: shutdown terminates with success
- **WHEN** a `shutdown` request is processed
- **THEN** a success response with result `{}` is written and the process exits with code 0

### Requirement: Dispatch table scope
The system SHALL register only `initialize` and `shutdown` in this change. Any other method SHALL return `-32601`. The dispatch table SHALL be overridable via the `Server` constructor for testing (see `Injectable dispatch table`).

#### Scenario: Reserved methods are not implemented
- **WHEN** a request for `analyze`, `complexity`, `coverage`, `discover`, `test_mapping`, `classify_signals`, or `analyze/stream` is written
- **THEN** the system responds with `-32601`
