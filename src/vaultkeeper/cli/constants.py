"""CLI execution exit codes and global presentation constants."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standard process exit codes for CLI commands."""

    SUCCESS = 0
    ERROR = 1
    ISSUES_FOUND = 2


EXIT_SUCCESS = ExitCode.SUCCESS
EXIT_ERROR = ExitCode.ERROR
EXIT_ISSUES_FOUND = ExitCode.ISSUES_FOUND
