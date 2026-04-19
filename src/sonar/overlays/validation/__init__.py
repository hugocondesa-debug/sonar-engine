"""L2 overlay validation hooks (cross-validation against published curves)."""

from sonar.overlays.validation.fed_gsw import (
    FED_GSW_XVAL_THRESHOLD_BPS,
    GSWReference,
    compare_to_gsw,
    parse_feds200628_csv,
)

__all__ = [
    "FED_GSW_XVAL_THRESHOLD_BPS",
    "GSWReference",
    "compare_to_gsw",
    "parse_feds200628_csv",
]
