"""The analysis: what sold, who buys again, and when the year is busy."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, orders, customers and average order value by month."""
    sales = df[~df.is_return]
    monthly = sales.groupby("month").agg(
        revenue=("revenue", "sum"),
        orders=("order_id", "nunique"),
        units=("quantity", "sum"),
        customers=("customer_id", "nunique"),
    )
    returns = df[df.is_return].groupby("month")["revenue"].sum().abs()
    monthly["returns"] = returns.reindex(monthly.index).fillna(0)
    monthly["net_revenue"] = monthly["revenue"] - monthly["returns"]
    monthly["average_order_value"] = (monthly["revenue"] / monthly["orders"]).round(2)
    monthly["growth_percent"] = (monthly["net_revenue"].pct_change() * 100).round(1)
    return monthly.round(2)


def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    sales = df[~df.is_return]
    grouped = sales.groupby(["sku", "product", "category"]).agg(
        units=("quantity", "sum"), revenue=("revenue", "sum"), orders=("order_id", "nunique"),
    )
    returned = df[df.is_return].groupby("sku")["quantity"].sum().abs()
    grouped["returned_units"] = returned.reindex(grouped.index.get_level_values("sku")).fillna(0).values
    grouped["return_rate_percent"] = (
        100 * grouped["returned_units"] / (grouped["units"] + grouped["returned_units"])
    ).round(1)
    grouped["revenue_share_percent"] = (100 * grouped["revenue"] / grouped["revenue"].sum()).round(1)
    return grouped.sort_values("revenue", ascending=False).head(n).round(2)


def cohort_retention(df: pd.DataFrame, months: int = 6) -> pd.DataFrame:
    """Share of each signup month's customers who bought again N months later.

    Guests are excluded: rows with no customer id cannot be followed over time,
    and counting them as one giant customer is how retention charts start lying.
    """
    sales = df[(~df.is_return) & (df.customer_id != "guest")].copy()
    first = sales.groupby("customer_id")["month"].min().rename("cohort")
    sales = sales.join(first, on="customer_id")
    sales["offset"] = (
        (sales["month"].dt.year - sales["cohort"].dt.year) * 12
        + (sales["month"].dt.month - sales["cohort"].dt.month)
    )
    counts = sales.groupby(["cohort", "offset"])["customer_id"].nunique().unstack(fill_value=0)
    sizes = counts[0].replace(0, np.nan)
    retention = counts.div(sizes, axis=0).mul(100).round(1)
    return retention.iloc[:, : months + 1]


def rfm_segments(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Recency, frequency and monetary scores, and a plain-English segment."""
    sales = df[(~df.is_return) & (df.customer_id != "guest")]
    as_of = as_of or sales["order_date"].max()
    rfm = sales.groupby("customer_id").agg(
        last_order=("order_date", "max"),
        frequency=("order_id", "nunique"),
        monetary=("revenue", "sum"),
    )
    rfm["recency_days"] = (as_of - rfm["last_order"]).dt.days
    # Quartile scores; duplicates="drop" because a small shop can have ties.
    rfm["r_score"] = pd.qcut(rfm["recency_days"], 4, labels=[4, 3, 2, 1], duplicates="drop").astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)

    def label(row) -> str:
        r, f, m = row.r_score, row.f_score, row.m_score
        if r >= 3 and f >= 3 and m >= 3:
            return "champions"
        if r >= 3 and f >= 3:
            return "loyal"
        if r >= 3 and f <= 2:
            return "new or occasional"
        if r <= 2 and f >= 3 and m >= 3:
            return "at risk (valuable)"
        if r == 1 and f <= 2:
            return "lost"
        return "needs attention"

    rfm["segment"] = rfm.apply(label, axis=1)
    return rfm.sort_values("monetary", ascending=False).round(2)


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    summary = rfm.groupby("segment").agg(
        customers=("monetary", "size"),
        revenue=("monetary", "sum"),
        average_orders=("frequency", "mean"),
        average_recency_days=("recency_days", "mean"),
    )
    summary["revenue_share_percent"] = (100 * summary["revenue"] / summary["revenue"].sum()).round(1)
    return summary.sort_values("revenue", ascending=False).round(1)


def seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue by month of the year and by weekday, indexed to the average."""
    sales = df[~df.is_return].copy()
    sales["month_name"] = sales["order_date"].dt.strftime("%b")
    sales["month_number"] = sales["order_date"].dt.month
    sales["weekday"] = sales["order_date"].dt.day_name()
    by_month = sales.groupby(["month_number", "month_name"])["revenue"].sum()
    by_month = by_month.reset_index().set_index("month_name")["revenue"]
    index = (100 * by_month / by_month.mean()).round(1)
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday = sales.groupby("weekday")["revenue"].sum().reindex(weekday_order)
    return pd.DataFrame({
        "revenue": by_month.round(0),
        "index_vs_average": index,
    }).join(pd.DataFrame({"weekday_revenue": by_weekday.round(0)}), how="outer")


def channel_country(df: pd.DataFrame) -> pd.DataFrame:
    sales = df[~df.is_return]
    pivot = sales.pivot_table(index="country", columns="channel", values="revenue",
                              aggfunc="sum", fill_value=0)
    pivot["total"] = pivot.sum(axis=1)
    return pivot.sort_values("total", ascending=False).round(0)
