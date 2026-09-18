"""Cleaning, with a report of what was changed and why.

A cleaning step that silently drops rows is how a dashboard ends up 8% short
without anyone noticing. Every rule here counts what it touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

COUNTRY_MAP = {
    "pakistan": "Pakistan", "pk": "Pakistan",
    "united arab emirates": "United Arab Emirates", "uae": "United Arab Emirates",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "saudi arabia": "Saudi Arabia", "ksa": "Saudi Arabia",
}


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    duplicates_removed: int = 0
    bad_dates: int = 0
    bad_prices: int = 0
    missing_customers: int = 0
    returns: int = 0
    countries_normalised: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"{self.rows_in:,} rows in, {self.rows_out:,} out",
            f"  {self.duplicates_removed:,} exact duplicates removed",
            f"  {self.bad_dates:,} rows with an unparseable date dropped",
            f"  {self.bad_prices:,} rows with no price dropped",
            f"  {self.missing_customers:,} rows without a customer id kept as 'guest'",
            f"  {self.returns:,} returns kept as negative quantities",
            f"  {self.countries_normalised:,} country spellings normalised",
        ]
        return "\n".join(lines + [f"  {note}" for note in self.notes])


def _to_number(series: pd.Series) -> pd.Series:
    """'Rs 9,800' -> 9800.0, '' -> NaN."""
    return pd.to_numeric(
        series.astype(str).str.replace(r"[^\d.\-]", "", regex=True).replace("", None),
        errors="coerce",
    )


ISO_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")
DAY_FIRST_FORMATS = ("%d/%m/%Y %H:%M", "%d/%m/%Y")


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse each known format explicitly.

    Letting pandas infer per row is what turns 03/04/2026 into 4 March for some
    rows and 3 April for others. The export uses two formats, so both are named
    and tried in order; anything else becomes NaT and is counted as a bad date.
    """
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    text = series.astype(str).str.strip()
    for fmt in (*ISO_FORMATS, *DAY_FIRST_FORMATS):
        missing = out.isna()
        if not missing.any():
            break
        out.loc[missing] = pd.to_datetime(text[missing], format=fmt, errors="coerce")
    return out


def clean_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    report = CleaningReport(rows_in=len(df))
    df = df.copy()

    before = len(df)
    df = df.drop_duplicates()
    report.duplicates_removed = before - len(df)

    df["order_date"] = _parse_dates(df["order_date"])
    report.bad_dates = int(df["order_date"].isna().sum())
    df = df[df["order_date"].notna()]

    df["unit_price"] = _to_number(df["unit_price"])
    report.bad_prices = int(df["unit_price"].isna().sum())
    df = df[df["unit_price"].notna()]

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    report.returns = int((df["quantity"] < 0).sum())

    report.missing_customers = int(df["customer_id"].isna().sum())
    df["customer_id"] = df["customer_id"].fillna("guest")

    original_countries = df["country"].copy()
    df["country"] = df["country"].astype(str).str.strip().str.lower().map(COUNTRY_MAP).fillna(df["country"])
    report.countries_normalised = int((original_countries != df["country"]).sum())

    df["channel"] = df["channel"].astype(str).str.strip().str.lower()
    df["discount_percent"] = pd.to_numeric(df["discount_percent"], errors="coerce").fillna(0)

    df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount_percent"] / 100)).round(2)
    df["month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["is_return"] = df["quantity"] < 0

    report.rows_out = len(df)
    if report.rows_out < report.rows_in * 0.8:
        report.notes.append("WARNING: more than a fifth of the rows were dropped — check the export")
    return df.reset_index(drop=True), report
