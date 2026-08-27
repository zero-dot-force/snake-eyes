"""Command-line entry point for snake-eyes."""

from __future__ import annotations

import io
import sys
from typing import TextIO

from .server import Server


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Parse argv and either start the stdio server or print usage.

    With ``--stdio`` the JSON-RPC server runs on stdin/stdout until EOF,
    ``shutdown``, or a broken pipe (exit 0). Without it the usage line is
    written to stderr and the process exits 2.

    ``argv`` defaults to ``sys.argv[1:]``; the stream arguments default to
    the real ``sys`` streams and exist so tests can drive the entry point
    in-process. Text streams are reconfigured to UTF-8 (stdout with ``\n``
    newlines) so the protocol channel does not depend on the locale's
    default encoding.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["--stdio"]:
        err = stderr if stderr is not None else sys.stderr
        err.write("snake-eyes --stdio\n")
        raise SystemExit(2)

    in_stream = stdin if stdin is not None else sys.stdin
    out_stream = stdout if stdout is not None else sys.stdout
    err_stream = stderr if stderr is not None else sys.stderr
    if isinstance(in_stream, io.TextIOWrapper):
        in_stream.reconfigure(encoding="utf-8")
    if isinstance(out_stream, io.TextIOWrapper):
        out_stream.reconfigure(encoding="utf-8", newline="\n")
    server = Server(in_stream, out_stream, err_stream)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
