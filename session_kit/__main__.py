"""Typer app — registers all `sk <subcommand>` entrypoints.

New subcommands (e.g., park-finalize, index) plug in here as the migration
proceeds. Shared flags like --json belong on each subcommand for now; promote
to an app-level callback only when more than one subcommand actually needs
the same flag.
"""
from __future__ import annotations

import typer

from . import checkin as checkin_cmd
from . import park_finalize as park_finalize_cmd
from . import write_artifact as write_artifact_cmd

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="session-kit CLI — backing implementation for the session-kit skill family.",
)

app.command(name="checkin", help=checkin_cmd.command.__doc__)(checkin_cmd.command)
app.command(name="write-artifact", help=write_artifact_cmd.command.__doc__)(
    write_artifact_cmd.command
)
app.command(name="park-finalize", help=park_finalize_cmd.command.__doc__)(
    park_finalize_cmd.command
)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
