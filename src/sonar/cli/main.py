"""Top-level ``sonar`` Typer app — aggregates sub-commands.

The ``sonar`` entry point in ``pyproject.toml`` points here
(``sonar.cli.main:app``). Sub-apps register themselves via
``app.add_typer(...)`` so ``sonar --help`` lists everything available.

Week 7 Sprint G sub-commands:

- ``sonar status`` — cross-cycle country snapshot (single + matrix).
- ``sonar health`` — last-24h pipeline freshness + success counts.
- ``sonar retention`` — retention-policy + VACUUM helpers, dry-run
  default.

Additional sub-commands (backfill, replay, calibration harness)
register the same way in future sprints.
"""

from __future__ import annotations

import typer

from sonar.cli import health as health_cli, status as status_cli
from sonar.scripts import retention as retention_cli

app = typer.Typer(
    name="sonar",
    help="SONAR v2 operational CLI — status / health / retention / backfill.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(status_cli.app, name="status", help="Cross-cycle country status dashboard.")
app.add_typer(health_cli.app, name="health", help="Pipeline freshness + success snapshot.")
app.add_typer(retention_cli.app, name="retention", help="Retention policies + SQLite VACUUM.")


if __name__ == "__main__":  # pragma: no cover
    app()
