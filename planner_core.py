"""
Shared capacity-planning logic for carding lines TRK0001 / TRK0002 (or more).
Both the CLI script and the Streamlit app import from here.
"""

import pandas as pd

REQUIRED_ORDER_COLS = [
    "order_id", "product", "line", "month", "unit",
    "quantity", "width_m", "length_m", "cycle_time_sec_per_m",
]
REQUIRED_CALENDAR_COLS = ["line", "month", "working_days", "hours_per_day"]


def convert_to_meters(row: pd.Series) -> float:
    """Turn one order's quantity into linear meters, based on unit."""
    unit = row["unit"]

    if unit == "M":
        return row["quantity"]

    if unit == "M2":
        if pd.isna(row["width_m"]) or row["width_m"] == 0:
            raise ValueError(f"{row['order_id']}: {unit} order needs width_m")
        return row["quantity"] / row["width_m"]

    if unit in ("PCS", "ADT"):
        if pd.isna(row["length_m"]) or row["length_m"] == 0:
            raise ValueError(f"{row['order_id']}: {unit} order needs length_m")
        return row["quantity"] * row["length_m"]

    raise ValueError(f"{row['order_id']}: unknown unit '{unit}'")


def compute_required_hours(row: pd.Series) -> float:
    """Ideal production time required for the order (without OEE)."""
    return (row["meters"] * row["cycle_time_sec_per_m"]) / 3600


def process_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add meters + required_hours columns to a raw orders dataframe."""
    orders = orders.copy()
    orders["meters"] = orders.apply(convert_to_meters, axis=1)
    orders["required_hours"] = orders.apply(compute_required_hours, axis=1)
    return orders


def build_monthly_summary(orders: pd.DataFrame, calendar: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """One row per (line, month): effective capacity (scaled by OEE) vs. required hours vs. utilization %."""
    calendar = calendar.copy()

    calendar["oee"] = calendar["line"].map(oee_by_line)
    if calendar["oee"].isna().any():
        missing_lines = calendar[calendar["oee"].isna()]["line"].unique()
        raise ValueError(f"Missing OEE value for line(s): {missing_lines}")

    calendar["gross_capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]
    calendar["capacity_hours"] = calendar["gross_capacity_hours"] * calendar["oee"]

    demand = (
        orders.groupby(["line", "month"])["required_hours"]
        .sum()
        .reset_index()
    )
    summary = calendar.merge(demand, on=["line", "month"], how="left")
    summary["required_hours"] = summary["required_hours"].fillna(0)
    summary["utilization_pct"] = (
        summary["required_hours"] / summary["capacity_hours"] * 100
    )
    return summary.sort_values(["line", "month"]).reset_index(drop=True)


def validate_columns(df: pd.DataFrame, required: list, label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


def append_year_totals(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds one 'YYYY Toplam' row per year to a monthly summary table that has
    at least 'month', 'capacity_hours', 'required_hours'. Works for both a
    single line's table (which also has working_days/hours_per_day) and the
    combined all-lines table (which doesn't) — only sums columns that are
    actually present, so it's safe to call on either shape.
    """
    df = monthly_df.copy()
    df["year"] = df["month"].astype(str).str.slice(0, 4)

    sum_cols = [c for c in ["working_days", "capacity_hours", "required_hours"] if c in df.columns]
    totals = df.groupby("year")[sum_cols].sum().reset_index()
    totals["month"] = totals["year"] + " Toplam"
    if "hours_per_day" in df.columns:
        totals["hours_per_day"] = ""
    totals["utilization_pct"] = totals["required_hours"] / totals["capacity_hours"] * 100

    ordered_cols = ["month"] + [c for c in df.columns if c not in ("month", "year")]
    totals = totals.reindex(columns=ordered_cols, fill_value="")

    return pd.concat([df[ordered_cols], totals], ignore_index=True)


# ---------------------------------------------------------------------------
# Capacity holdout logic
# ---------------------------------------------------------------------------

REQUIRED_HOLDOUT_COLS = [
    "order_id", "customer_plant", "internal_external", "model_key",
    "program_carline", "unit", "width_m", "length_m", "cycle_time_sec_per_m",
]
HOLDOUT_YEAR_COLS = (
    [f"vol_{y}" for y in range(2026, 2032)]
    + [str(y) for y in range(2026, 2032)]
    + list(range(2026, 2032))
)
HOLDOUT_GROUP_LABELS = {
    "total": "Toplam (Genel Özet)",
    "customer_plant": "Company",
    "internal_external": "Internal / External",
    "model_key": "Customer / Model-Key",
    "program_carline": "Program / Carline",
    "line": "Physical Line",
}


def build_holdout_summary(long_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Pivot to: rows = year, columns = group_col values, cells = required_hours."""
    grouped = long_df.copy()

    if group_col == "total":
        pivot = grouped.groupby("year")["required_hours"].sum().to_frame(name="Toplam Gereken Süre")
        return pivot.sort_index()

    if group_col not in grouped.columns:
        raise ValueError(f"Unknown grouping column: {group_col}")

    # Normalize the grouping column so values that only differ by stray
    # whitespace or by being stored as text vs. number in Excel (e.g.
    # "356" and "356 ") don't show up as separate, duplicate-looking groups.
    grouped[group_col] = (
        grouped[group_col].fillna("Unspecified").astype(str).str.strip()
    )

    pivot = grouped.pivot_table(
        index="year", columns=group_col, values="required_hours",
        aggfunc="sum", fill_value=0,
    )
    return pivot.sort_index()


def process_holdout_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """
    Reshape wide holdout orders into long format, convert each row's volume
    to meters (reuses the SAME convert_to_meters logic as the line-level
    planner, so M/M2/PCS/ADT behave identically here), then compute
    required_hours from cycle_time_sec_per_m — seconds to produce 1 meter.

    No OEE here, on purpose: OEE is applied exactly once, on the capacity
    side, in compute_annual_capacity_from_calendar. Dividing demand by OEE
    here too would double-count it (once shrinking capacity, once
    inflating demand), which overstates utilization.
    """
    orders = orders.copy()
    orders.columns = [str(c) for c in orders.columns]

    year_cols = [c for c in orders.columns if c.startswith("vol_") or c in [str(y) for y in range(2026, 2032)]]
    if not year_cols:
        raise ValueError("No year volume columns found in file.")

    id_cols = [c for c in orders.columns if c not in year_cols]
    long_df = orders.melt(id_vars=id_cols, value_vars=year_cols,
                           var_name="year", value_name="volume")
    long_df["year"] = long_df["year"].astype(str).str.replace("vol_", "", regex=False)
    long_df["volume"] = pd.to_numeric(long_df["volume"], errors="coerce").fillna(0)

    # convert_to_meters expects a 'quantity' column (and only uses 'order_id'
    # for error messages) — map volume onto it so M/M2/PCS/ADT all convert
    # the same way here as they do in the line-level planner.
    long_df["quantity"] = long_df["volume"]
    long_df["meters"] = long_df.apply(convert_to_meters, axis=1)

    long_df["required_hours"] = (long_df["meters"] * long_df["cycle_time_sec_per_m"]) / 3600

    return long_df


def compute_annual_capacity_from_calendar(calendar_df: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """
    Per (line, year): capacity_hours, built from the calendar's 'month'
    column (e.g. '2027-01'). Returns a DataFrame — not a flat dict — so
    each line's own capacity can be plotted separately, and each year
    reflects its own actual working days/hours instead of one averaged
    total reused everywhere.
    """
    df = calendar_df.copy()
    df["oee"] = df["line"].map(oee_by_line)
    if df["oee"].isna().any():
        missing = df[df["oee"].isna()]["line"].unique()
        raise ValueError(f"Missing OEE for line(s): {missing}")
    df["capacity_hours"] = df["working_days"] * df["hours_per_day"] * df["oee"]
    df["year"] = df["month"].astype(str).str.slice(0, 4)
    return df.groupby(["line", "year"])["capacity_hours"].sum().reset_index()