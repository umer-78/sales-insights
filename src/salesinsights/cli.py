"""sales: clean an orders export and report on it."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from . import analysis, charts
from .clean import clean_orders
from .generate import write as write_sample
from .report import build_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "orders.csv"
DEFAULT_REPORTS = ROOT / "reports"


def money(value: float) -> str:
    if abs(value) >= 1e6:
        return f"Rs {value / 1e6:.2f}M"
    return f"Rs {value:,.0f}"


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"{path} not found — run `sales sample` first.", file=sys.stderr)
        raise SystemExit(2)
    raw = pd.read_csv(path)
    clean, report = clean_orders(raw)
    print(report.summary(), file=sys.stderr)
    return clean


def main(argv: list[str] | None = None) -> int:
    """Entry point. Wraps the real work so that piping into `head` — which closes
    the pipe early — ends quietly instead of printing a BrokenPipeError."""
    try:
        return _run(argv)
    except BrokenPipeError:
        # The reader went away. Point stdout at the void so the interpreter's
        # own flush on exit does not raise the same error again.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


def _run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sales", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="write a messy sample orders file")
    s.add_argument("-o", "--output", type=Path, default=DEFAULT_DATA)
    s.add_argument("-n", "--rows", type=int, default=6000)

    c = sub.add_parser("clean", help="clean a file and save the tidy version")
    c.add_argument("-d", "--data", type=Path, default=DEFAULT_DATA)
    c.add_argument("-o", "--output", type=Path, default=ROOT / "data" / "orders-clean.csv")

    for name, helptext in (("summary", "headline numbers and monthly trend"),
                           ("products", "best sellers and return rates"),
                           ("cohorts", "repeat purchase rate by signup month"),
                           ("segments", "RFM customer segments"),
                           ("seasonality", "month-of-year and weekday patterns")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("-d", "--data", type=Path, default=DEFAULT_DATA)

    r = sub.add_parser("report", help="build the HTML report with charts")
    r.add_argument("-d", "--data", type=Path, default=DEFAULT_DATA)
    r.add_argument("-o", "--output", type=Path, default=DEFAULT_REPORTS / "sales-report.html")

    args = ap.parse_args(argv)

    if args.cmd == "sample":
        path = write_sample(args.output, args.rows)
        print(f"wrote {args.rows:,} rows (with realistic mess) to {path}")
        return 0

    df = load(args.data)

    if args.cmd == "clean":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False)
        print(f"\nwrote {len(df):,} clean rows to {args.output}")
        return 0

    if args.cmd == "summary":
        monthly = analysis.monthly_summary(df)
        total = monthly["net_revenue"].sum()
        print(f"\n{len(df):,} rows, {df.order_id.nunique():,} orders, "
              f"{df.customer_id.nunique():,} customers")
        print(f"net revenue {money(total)} over {len(monthly)} months "
              f"(average {money(total / len(monthly))} a month)")
        print(f"\n{'month':<10} {'net revenue':>14} {'orders':>8} {'customers':>10} {'AOV':>10} {'growth':>8}")
        for month, row in monthly.tail(12).iterrows():
            growth = "" if pd.isna(row.growth_percent) else f"{row.growth_percent:+.1f}%"
            print(f"{month:%Y-%m}    {money(row.net_revenue):>14} {row.orders:>8.0f} "
                  f"{row.customers:>10.0f} {money(row.average_order_value):>10} {growth:>8}")
        return 0

    if args.cmd == "products":
        products = analysis.top_products(df)
        print(f"\n{'product':<26} {'units':>7} {'revenue':>12} {'share':>7} {'returns':>8}")
        for (_, name, _), row in products.iterrows():
            print(f"{name[:26]:<26} {row.units:>7.0f} {money(row.revenue):>12} "
                  f"{row.revenue_share_percent:>6.1f}% {row.return_rate_percent:>7.1f}%")
        return 0

    if args.cmd == "cohorts":
        retention = analysis.cohort_retention(df)
        print("\nrepeat purchase rate by signup month (%)")
        print(retention.to_string(na_rep="", float_format=lambda v: f"{v:.0f}"))
        later = retention.iloc[:, 1:].stack().mean()
        print(f"\naverage repeat rate after the first month: {later:.1f}%")
        return 0

    if args.cmd == "segments":
        rfm = analysis.rfm_segments(df)
        summary = analysis.segment_summary(rfm)
        print(f"\n{len(rfm):,} identifiable customers")
        print(f"\n{'segment':<20} {'customers':>10} {'revenue':>12} {'share':>7} {'avg orders':>11}")
        for segment, row in summary.iterrows():
            print(f"{segment:<20} {row.customers:>10.0f} {money(row.revenue):>12} "
                  f"{row.revenue_share_percent:>6.1f}% {row.average_orders:>11.1f}")
        top = rfm.head(5)
        print("\ntop customers by spend:")
        for customer, row in top.iterrows():
            print(f"  {customer}  {money(row.monetary):>12}  {row.frequency:>3.0f} orders  "
                  f"last seen {row.recency_days:.0f} days ago  ({row.segment})")
        return 0

    if args.cmd == "seasonality":
        table = analysis.seasonality(df)
        print("\nrevenue by month of the year (100 = average month)")
        print(table[["revenue", "index_vs_average"]].dropna().to_string(float_format=lambda v: f"{v:,.0f}"))
        print("\nrevenue by weekday")
        print(table[["weekday_revenue"]].dropna().to_string(float_format=lambda v: f"{v:,.0f}"))
        return 0

    # report
    monthly = analysis.monthly_summary(df)
    products = analysis.top_products(df)
    retention = analysis.cohort_retention(df)
    rfm = analysis.rfm_segments(df)
    segments = analysis.segment_summary(rfm)
    out_dir = args.output.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_paths = {
        "Revenue trend": charts.revenue_trend(monthly, out_dir / "revenue.png"),
        "Repeat purchases": charts.cohort_heatmap(retention, out_dir / "cohorts.png"),
        "Customer segments": charts.segment_chart(segments, out_dir / "segments.png"),
        "Best sellers": charts.product_chart(products, out_dir / "products.png"),
    }
    total = monthly["net_revenue"].sum()
    repeat_rate = retention.iloc[:, 1:].stack().mean()
    kpis = {
        "Net revenue": money(total),
        "Orders": f"{df.order_id.nunique():,}",
        "Customers": f"{df.customer_id.nunique():,}",
        "Average order": money(monthly["average_order_value"].mean()),
        "Repeat rate": f"{repeat_rate:.1f}%",
        "Return rate": f"{100 * df.is_return.mean():.1f}%",
    }
    tables = {
        "Monthly detail": monthly.tail(12)[["net_revenue", "orders", "customers", "average_order_value"]],
        "Best sellers": products.reset_index().set_index("product")[
            ["units", "revenue", "revenue_share_percent", "return_rate_percent"]],
        "Segments": segments,
    }
    path = build_report(
        args.output, period=f"{monthly.index.min():%b %Y} – {monthly.index.max():%b %Y}",
        kpis=kpis, charts=chart_paths, tables=tables,
        footer="Generated by salesinsights. Figures exclude returns from revenue and count each "
               "order once. Customers without an id are grouped as 'guest' and left out of cohorts.")
    print(f"\nreport written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
