"""Sales analysis: clean, aggregate, segment, report."""

from .analysis import cohort_retention, monthly_summary, rfm_segments, top_products
from .clean import CleaningReport, clean_orders

__all__ = ["CleaningReport", "clean_orders", "cohort_retention", "monthly_summary",
           "rfm_segments", "top_products"]
__version__ = "1.0.0"
