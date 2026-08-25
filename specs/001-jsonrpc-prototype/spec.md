# Feature Specification: JSON-RPC Prototype

**Feature Branch**: `001-jsonrpc-prototype`

**Created**: 2026-05-17

**Status**: Draft

**Input**: Set up the Python project (pyproject.toml, uv, basic package structure) and build a prototype JSON-RPC server with at least the initialize, discover, and analyze methods working against real Python code. This validates the protocol design with real data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Project Setup and Developer Onboarding (Priority: P1)

A developer clones the snake-eyes repository, runs a single install command, and has a working development environment with all dependencies installed, tests passing, and the `snake-eyes` command available. The project follows standard Python packaging conventions.

**Why this priority**: Without project scaffolding, no development or testing can happen. This is the prerequisite for every other story.

**Independent Test**: Can be tested by running the install command in a fresh clone and verifying the entry point command starts without errors.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository, **When** the developer runs the install command, **Then** all dependencies are installed without errors.
2. **Given** dependencies are installed, **When** the developer runs the test suite, **Then** all tests pass.
3. **Given** dependencies are installed, **When** the developer runs `snake-eyes --stdio`, **Then** the analyzer starts and waits for input on stdin.

---

### User Story 2 - Analyzer Handshake (Priority: P1)

Gaze spawns `snake-eyes --stdio` as a subprocess. It sends an `initialize` request with the project root path. Snake Eyes responds with its name, version, supported language, and a list of capabilities (which protocol methods it supports). Gaze uses this to determine what analysis it can request from this analyzer.

**Why this priority**: Without the handshake, no other protocol interaction is possible. This is the foundation of the two-process system.

**Independent Test**: Can be tested by piping a single request to stdin and verifying the response on stdout. No Python source code analysis needed.

**Acceptance Scenarios**:

1. **Given** snake-eyes is started in stdio mode, **When** Gaze sends an initialize request with a project root path, **Then** snake-eyes responds with its name, version, language identifier, and list of supported capabilities.
2. **Given** snake-eyes is running, **When** Gaze sends a request for an unsupported method, **Then** snake-eyes responds with a standard method-not-found error.
3. **Given** snake-eyes is running, **When** Gaze sends malformed input, **Then** snake-eyes responds with a standard parse error without crashing.

---

### User Story 3 - File Discovery (Priority: P1)

Gaze sends a `discover` request with a project root. Snake Eyes walks the file system, identifies Python source files and test files (using standard naming and directory conventions), and returns categorized file lists. This tells Gaze what to analyze.

**Why this priority**: Without file discovery, Gaze cannot know which files to send for analysis. This is a prerequisite for the analyze method.

**Independent Test**: Can be tested by pointing discover at a known directory structure with Python files and verifying the source/test classification is correct.

**Acceptance Scenarios**:

1. **Given** a project with source files and test files following standard conventions, **When** Gaze sends a discover request, **Then** snake-eyes returns separate lists of source files and test files.
2. **Given** a project with no Python files, **When** Gaze sends a discover request, **Then** snake-eyes returns empty file lists without errors.
3. **Given** a project with virtual environments, cache directories, and version control directories, **When** Gaze sends a discover request, **Then** those directories are excluded from results.

---

### User Story 4 - Side Effect Detection (Priority: P1)

Gaze sends an `analyze` request with a list of Python files. Snake Eyes parses each file and detects P0-tier side effects for every function and method: return values, raised exceptions, self-attribute mutations, and mutable argument mutations. It returns a structured list of functions with their detected effects using the universal taxonomy types.

**Why this priority**: Side effect detection is the core value proposition. This is the analysis that feeds Gaze's scoring engine.

**Independent Test**: Can be tested by analyzing Python files with known side effect patterns and verifying each effect is detected with the correct type, tier, and source location.

**Acceptance Scenarios**:

1. **Given** a file with a function that returns a value, **When** analyzed, **Then** the function reports a ReturnValue effect at P0 tier with the correct line number.
2. **Given** a file with a function that raises an exception, **When** analyzed, **Then** the function reports an ErrorSignal effect at P0 tier.
3. **Given** a class method that assigns to a self attribute, **When** analyzed, **Then** the function reports a ReceiverMutation effect at P0 tier with the target attribute identified.
4. **Given** a function that mutates a parameter (calling append, update, or similar on a passed argument), **When** analyzed, **Then** the function reports an ArgumentMutation effect at P0 tier with the target parameter identified.
5. **Given** a function with no observable side effects, **When** analyzed, **Then** the function reports zero effects.

---

### User Story 5 - Clean Shutdown (Priority: P2)

Gaze sends a `shutdown` request. Snake Eyes responds with acknowledgment and exits cleanly. This enables well-behaved subprocess lifecycle management.

**Why this priority**: Necessary for proper process lifecycle but not functionally complex.

**Independent Test**: Can be tested by sending a shutdown request and verifying the process terminates with a success exit code.

**Acceptance Scenarios**:

1. **Given** snake-eyes is running, **When** Gaze sends a shutdown request, **Then** snake-eyes responds with acknowledgment and the process exits with code 0.
2. **Given** snake-eyes is running, **When** stdin closes unexpectedly, **Then** snake-eyes exits cleanly with code 0.

---

### Edge Cases

- What happens when `analyze` receives a file path that does not exist? The response includes an error entry for that file; remaining files are still analyzed.
- What happens when a Python file has syntax errors? The file is skipped with a parse error reported in the response; other files continue to be analyzed.
- What happens when `discover` is called with a root path that does not exist? A protocol error is returned with the path identified in the message.
- How does the server handle multiple requests? Requests are processed sequentially (one at a time) since stdin/stdout is a serial transport. Each request is fully processed before the next is read.
- What happens when a function has both return values and raised exceptions? Both effects are reported independently in the function's effect list.
- What happens with nested functions or closures? Each function definition at any nesting level is analyzed independently. Inner functions are reported as separate entries.
- What happens with decorated functions? The function is analyzed as-is; decorator effects are deferred to future P2 analysis.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Snake Eyes MUST accept a `--stdio` flag that starts a server reading requests from stdin and writing responses to stdout.
- **FR-002**: All requests and responses MUST conform to the JSON-RPC 2.0 specification, including version field, request id matching, and standard error codes.
- **FR-003**: The server MUST implement the `initialize` method, returning the analyzer's name, version, language, and list of supported capabilities.
- **FR-004**: The server MUST implement the `discover` method, returning categorized lists of source files and test files found under the given root path.
- **FR-005**: The server MUST implement the `analyze` method, detecting P0-tier side effects (ReturnValue, ErrorSignal, ReceiverMutation, ArgumentMutation) for every function and method in the given files.
- **FR-006**: The server MUST implement the `shutdown` method, cleanly terminating the process after responding.
- **FR-007**: File discovery MUST exclude common non-source directories: virtual environments, cache directories, version control directories, and build output directories.
- **FR-008**: Test file detection MUST recognize standard conventions: files named with test prefixes or suffixes, and files within directories named for testing.
- **FR-009**: When a file cannot be parsed due to syntax errors, the analyzer MUST report the error and continue analyzing remaining files.
- **FR-010**: The project MUST use standard Python packaging with all dependencies declared, installable with a single command.
- **FR-011**: The project MUST include a test suite that exercises all protocol methods and all P0 effect detection scenarios.
- **FR-012**: Side effect types MUST use the universal taxonomy names defined by the Gaze project (ReturnValue, ErrorSignal, ReceiverMutation, ArgumentMutation for P0).

### Key Entities

- **Function**: A detected Python function or method. Attributes: name, file path, start line, end line, visibility (public or private based on naming convention), list of detected effects, whether it is a test function, whether it is a generator.
- **Effect**: A detected side effect. Attributes: universal taxonomy type, priority tier, source line number, optional target identifier (e.g., attribute name or parameter name).
- **SourceFile**: A discovered Python file. Attributes: file path relative to project root, classification as source or test.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete lifecycle (initialize, discover, analyze, shutdown) completes successfully against a real Python project without errors.
- **SC-002**: All four P0 effect types are correctly detected in purpose-built test fixtures with zero false negatives.
- **SC-003**: File discovery correctly separates source files from test files in a standard project layout.
- **SC-004**: The server handles all error conditions (malformed input, missing files, syntax errors) without crashing.
- **SC-005**: The project installs and all tests pass from a fresh clone with a single install command.
- **SC-006**: Protocol responses are valid JSON-RPC 2.0, verifiable by automated conformance tests.

## Assumptions

- The target runtime is Python 3.11 or later.
- This prototype targets P0 effects only; P1 and P2 effects are deferred to future specifications.
- Name resolution and type inference libraries are declared as dependencies but not used in this prototype; pure structural analysis is sufficient for P0 detection.
- Complexity calculation and coverage parsing are deferred to future specifications.
- The protocol design is exploratory; it will be formalized as a Gaze specification once validated by this prototype.
- The `test_mapping` and `classify_signals` methods are not implemented in this prototype.
- The analyzer is intended to be invoked by Gaze, not by end users directly. The `--stdio` flag is the only user-facing interface.
