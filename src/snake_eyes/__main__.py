"""Command-line entry point for snake-eyes."""

from __future__ import annotations

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
    """Parse argv and either start the stdio server or print usage."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["--stdio"]:
        err = stderr if stderr is not None else sys.stderr
        err.write("snake-eyes --stdio\n")
        raise SystemExit(2)

    server = Server(
        stdin if stdin is not None else sys.stdin,
        stdout if stdout is not None else sys.stdout,
        stderr if stderr is not None else sys.stderr,
    )
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
