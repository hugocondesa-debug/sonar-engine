"""L2 ERP external-reference overlay (Sprint 3.1).

Adjacent to the computed ``erp_canonical`` (Sprint 3); spec
``overlays/erp-daily.md`` §11 separation of concerns ("compute, don't
consume") preserved — canonical stays computed, this namespace ships
editorial / benchmarking external snapshots.

Sprint 3.1 backs Damodaran monthly US (start of month, 2008-09 onwards).
The ``source`` column is extensible: future writers can register
Bloomberg, GS Research, or Reuters consensus rows alongside Damodaran
without touching the table schema.
"""

from __future__ import annotations

from sonar.overlays.erp_external.damodaran import build_damodaran_external_row

__all__ = ["build_damodaran_external_row"]
