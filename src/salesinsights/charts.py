"""Charts for the report. One idea per chart, no decoration for its own sake."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

STYLE = {"figure.dpi": 130, "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
         "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "600"}
BLUE, AMBER, GREY = "#2563eb", "#f59e0b", "#94a3b8"


def revenue_trend(monthly, path: str | Path) -> Path:
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.bar(monthly.index, monthly["net_revenue"], width=20, color=BLUE, label="net revenue")
        rolling = monthly["net_revenue"].rolling(3, min_periods=1).mean()
        ax.plot(monthly.index, rolling, color=AMBER, lw=2, label="3-month average")
        ax.set_title("Monthly net revenue")
        ax.set_ylabel("revenue")
        ax.yaxis.set_major_formatter(lambda v, _: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}k")
        ax.legend(fontsize=8)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return Path(path)


def cohort_heatmap(retention, path: str | Path) -> Path:
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(7, max(3, 0.32 * len(retention))))
        data = retention.to_numpy(dtype=float)
        ax.imshow(np.where(np.isnan(data), 0, data), cmap="Blues", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(data.shape[1]), [f"+{i}" for i in retention.columns])
        ax.set_yticks(range(len(retention)), [d.strftime("%b %Y") for d in retention.index])
        ax.set_title("Repeat purchase rate by signup month (%)")
        ax.grid(False)
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                if not np.isnan(data[i, j]) and data[i, j] > 0:
                    ax.text(j, i, f"{data[i, j]:.0f}", ha="center", va="center", fontsize=7,
                            color="white" if data[i, j] > 55 else "#1e293b")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return Path(path)


def segment_chart(summary, path: str | Path) -> Path:
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(1, 2, figsize=(8, 3.2))
        summary["customers"].sort_values().plot.barh(ax=ax[0], color=GREY)
        ax[0].set_title("Customers per segment")
        ax[0].set_ylabel("")
        summary["revenue"].sort_values().plot.barh(ax=ax[1], color=BLUE)
        ax[1].set_title("Revenue per segment")
        ax[1].set_ylabel("")
        ax[1].xaxis.set_major_formatter(lambda v, _: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}k")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return Path(path)


def product_chart(products, path: str | Path) -> Path:
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(7.5, 3.4))
        labels = [f"{name}" for _, name, _ in products.index]
        ax.barh(labels[::-1], products["revenue"][::-1], color=BLUE)
        ax.set_title("Revenue by product")
        ax.xaxis.set_major_formatter(lambda v, _: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}k")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return Path(path)
