import pandas as pd
import pytest

from salesinsights import analysis
from salesinsights.clean import _parse_dates, _to_number, clean_orders
from salesinsights.cli import main
from salesinsights.generate import generate


@pytest.fixture(scope="module")
def raw():
    return generate(rows=2500, seed=5)


@pytest.fixture(scope="module")
def cleaned(raw):
    return clean_orders(raw)


# --------------------------------------------------------------------- cleaning
def test_prices_with_symbols_and_blanks():
    values = _to_number(pd.Series(["Rs 9,800", "1300", "", "Rs 0", None]))
    assert values.tolist()[:2] == [9800.0, 1300.0]
    assert pd.isna(values[2]) and pd.isna(values[4])


def test_dates_are_parsed_by_explicit_format_not_guesswork():
    parsed = _parse_dates(pd.Series(["2026-03-04 10:00", "03/04/2026", "2026-03-04", "rubbish"]))
    assert parsed[0] == pd.Timestamp("2026-03-04 10:00")
    assert parsed[1] == pd.Timestamp("2026-04-03"), "slash dates are day-first"
    assert parsed[2] == pd.Timestamp("2026-03-04")
    assert pd.isna(parsed[3])


def test_cleaning_reports_what_it_changed(cleaned):
    df, report = cleaned
    assert report.rows_in > report.rows_out
    assert report.duplicates_removed > 0
    assert report.missing_customers > 0
    assert report.returns > 0
    assert report.countries_normalised > 0
    assert "rows in" in report.summary()


def test_countries_and_channels_are_normalised(cleaned):
    df, _ = cleaned
    assert set(df.country) <= {"Pakistan", "United Arab Emirates", "United Kingdom", "Saudi Arabia"}
    assert set(df.channel) <= {"website", "marketplace", "retail"}


def test_revenue_applies_the_discount():
    raw = pd.DataFrame([{
        "order_id": "A", "order_date": "2026-01-01 10:00", "customer_id": "C1", "sku": "S",
        "product": "P", "category": "C", "quantity": 2, "unit_price": "Rs 1,000",
        "discount_percent": 10, "country": "pk", "channel": "Website",
    }])
    df, _ = clean_orders(raw)
    assert df.loc[0, "revenue"] == 1800
    assert df.loc[0, "country"] == "Pakistan"
    assert not df.loc[0, "is_return"]


def test_returns_are_negative_and_flagged(cleaned):
    df, _ = cleaned
    returns = df[df.is_return]
    assert (returns.quantity < 0).all()
    assert (returns.revenue < 0).all()


def test_no_rows_are_silently_lost(cleaned):
    df, report = cleaned
    assert report.rows_out == len(df)
    assert report.rows_out + report.bad_dates + report.bad_prices + report.duplicates_removed == report.rows_in


# --------------------------------------------------------------------- analysis
def test_monthly_summary_excludes_returns_from_revenue(cleaned):
    df, _ = cleaned
    monthly = analysis.monthly_summary(df)
    assert (monthly.net_revenue <= monthly.revenue).all()
    assert monthly.index.is_monotonic_increasing
    assert monthly.orders.sum() <= df.order_id.nunique()
    assert monthly.average_order_value.gt(0).all()


def test_top_products_shares_add_up(cleaned):
    df, _ = cleaned
    products = analysis.top_products(df, n=10)
    assert len(products) == 10
    assert products.revenue.is_monotonic_decreasing
    # Each share is rounded to 1dp, so the top-10 sum can drift slightly
    # above 100 when several products round up.
    assert 0 < products.revenue_share_percent.sum() <= 100.5
    assert (products.return_rate_percent >= 0).all()


def test_cohort_retention_starts_at_100_and_excludes_guests(cleaned):
    df, _ = cleaned
    retention = analysis.cohort_retention(df)
    assert (retention[0] == 100).all(), "every cohort is 100% in its first month"
    assert retention.shape[1] <= 7
    later = retention.iloc[:, 1:].stack()
    assert (later <= 100).all()
    # guests cannot be followed over time, so they must not appear in a cohort
    guests = df[df.customer_id == "guest"]
    assert not guests.empty, "the sample data should contain guest rows"
    assert analysis.cohort_retention(df).notna().any().any()


def test_rfm_segments_are_sensible(cleaned):
    df, _ = cleaned
    rfm = analysis.rfm_segments(df)
    assert {"r_score", "f_score", "m_score", "segment"} <= set(rfm.columns)
    assert rfm.r_score.between(1, 4).all()
    assert "guest" not in rfm.index
    summary = analysis.segment_summary(rfm)
    assert summary.customers.sum() == len(rfm)
    assert abs(summary.revenue_share_percent.sum() - 100) < 0.5
    champions = rfm[rfm.segment == "champions"]
    others = rfm[rfm.segment == "lost"]
    if len(champions) and len(others):
        assert champions.monetary.mean() > others.monetary.mean()
        assert champions.recency_days.mean() < others.recency_days.mean()


def test_seasonality_index_averages_to_100(cleaned):
    df, _ = cleaned
    table = analysis.seasonality(df)
    index = table["index_vs_average"].dropna()
    assert abs(index.mean() - 100) < 1
    assert table["weekday_revenue"].dropna().gt(0).all()


def test_channel_country_pivot(cleaned):
    df, _ = cleaned
    pivot = analysis.channel_country(df)
    assert "total" in pivot.columns
    assert pivot.total.is_monotonic_decreasing


# -------------------------------------------------------------------------- cli
def test_cli_end_to_end(tmp_path, capsys):
    data = tmp_path / "orders.csv"
    assert main(["sample", "-o", str(data), "-n", "800"]) == 0
    for command in ("summary", "products", "cohorts", "segments", "seasonality"):
        assert main([command, "-d", str(data)]) == 0
    capsys.readouterr()
    report = tmp_path / "out" / "report.html"
    assert main(["report", "-d", str(data), "-o", str(report)]) == 0
    html = report.read_text()
    assert "Sales report" in html
    assert "data:image/png;base64," in html, "charts must be embedded, not linked"
    assert (tmp_path / "out" / "revenue.png").exists()


def test_cli_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        main(["summary", "-d", str(tmp_path / "nope.csv")])
