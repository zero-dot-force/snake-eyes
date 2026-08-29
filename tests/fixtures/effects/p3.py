"""P3 effects fixture: StdoutWrite (print), EnvVarMutation, ProcessExit (sys.exit)."""

import os
import sys


def say_hello() -> None:
    print("hello")  # StdoutWrite


def set_env() -> None:
    os.environ["X"] = "1"  # EnvVarMutation


def exit_process() -> None:
    sys.exit(0)  # ProcessExit + ErrorSignal
