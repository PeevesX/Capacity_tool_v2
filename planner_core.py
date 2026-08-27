"""
Shared capacity-planning logic for carding lines TRK0001 / TRK0002 (or more).
Both the CLI script and the Streamlit app import from here.

Nothing in this module touches Streamlit — it's pure pandas so it can be
unit-tested and reused outside the app.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_ORDER_COLS = [
    "order_id", "product", "line", "month", "unit",
    "quantity", "width_m", "length_m", "cycle_time_sec_per_m",
]
REQUIRED_CALENDAR_COLS = ["line", "month", "working_days", "hours_per_day"]

REQUIRED_HOLDOUT_COLS = [
    "order_id", "customer_plant", "internal_external", "model_key",
    "program_carline", "unit", "width_m", "length_m", "cycle_time_sec_per_m",
]

HOLDOUT_GROUP_LABELS = {
    "total": "Toplam (Genel Özet)",
    "customer_plant": "Company",
    "internal_external": "Internal / External",
    "model_key": "Customer / Model-Key",
    "program_carline": "Program / Carline",
    "line": "Physical Line",
}

# value_col options for the holdout pivot/summary — hours, meters, or m².
HOLDOUT_METRICS = {
    "required_hours": {"label": "Süre (Saat)", "unit": "sa", "total_label": "Toplam Gereken Süre"},
    "meters": {"label": "Üretim (Metre)", "unit": "m", "total_label": "Toplam Üretilen Metre"},
    "m2": {"label": "Üretim (m²)", "unit": "m²", "total_label": "Toplam Üretilen m²"},
}

# Lines that run double-width material and slit it into two strips, so one
# meter of machine travel yields two meters of finished product.
DOUBLE_WIDTH_LINES = {"TRK0002"}

HOLDOUT_FORECAST_YEARS = range(2026, 2032)


# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------

def validate_columns(df: pd.DataFrame, required: list, label: str) -> None:
    """Raise a clear error listing any required columns missing from df."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


# ---------------------------------------------------------------------------
# Orders -> required hours / meters
# ---------------------------------------------------------------------------

def convert_to_meters(row: pd.Series) -> float:
    """Turn one order's quantity into linear (finished) meters, based on unit."""
    unit = str(row.get("unit", "")).strip().upper()
    qty = row["quantity"]

    if unit == "M":
        return qty

    if unit == "M2":
        if pd.isna(row["width_m"]) or row["width_m"] == 0:
            raise ValueError(f"{row.get('order_id', '?')}: {unit} order needs width_m")
        return qty / row["width_m"]

    if unit in ("PCS", "ADT"):
        if pd.isna(row["length_m"]) or row["length_m"] == 0:
            raise ValueError(f"{row.get('order_id', '?')}: {unit} order needs length_m")
        return qty * row["length_m"]

    raise ValueError(f"{row.get('order_id', '?')}: unknown unit '{unit}'")


def convert_to_m2(row: pd.Series) -> float:
    """Turn one order's quantity into square meters (finished area), based on unit."""
    unit = str(row.get("unit", "")).strip().upper()
    qty = row["quantity"]

    if unit == "M2":
        return qty

    if unit == "M":
        if pd.isna(row["width_m"]) or row["width_m"] == 0:
            raise ValueError(f"{row.get('order_id', '?')}: {unit} order needs width_m for m² conversion")
        return qty * row["width_m"]

    if unit in ("PCS", "ADT"):
        if pd.isna(row["length_m"]) or row["length_m"] == 0:
            raise ValueError(f"{row.get('order_id', '?')}: {unit} order needs length_m for m² conversion")
        if pd.isna(row["width_m"]) or row["width_m"] == 0:
            raise ValueError(f"{row.get('order_id', '?')}: {unit} order needs width_m for m² conversion")
        return qty * row["length_m"] * row["width_m"]

    raise ValueError(f"{row.get('order_id', '?')}: unknown unit '{unit}'")


def compute_required_hours(row: pd.Series) -> float:
    """Ideal production time required for the order (without OEE)."""
    base_hours = (row["meters"] * row["cycle_time_sec_per_m"]) / 3600

    if str(row.get("line", "")).strip() in DOUBLE_WIDTH_LINES:
        return base_hours / 2

    return base_hours


def process_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add meters + m2 + required_hours columns to a raw orders dataframe."""
    orders = orders.copy()
    orders["meters"] = orders.apply(convert_to_meters, axis=1)
    orders["m2"] = orders.apply(convert_to_m2, axis=1)
    orders["required_hours"] = orders.apply(compute_required_hours, axis=1)
    return orders


# ---------------------------------------------------------------------------
# Monthly capacity vs. demand
# ---------------------------------------------------------------------------

def build_monthly_summary(orders: pd.DataFrame, calendar: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """
    One row per (line, month): effective capacity (scaled by OEE), required
    hours, produced meters, produced m², and utilization %.
    For m² and meters on shared/sandwich orders split across lines, 
    duplicate order references are handled so physical shipment totals remain correct.
    """
    calendar = calendar.copy()

    calendar["oee"] = calendar["line"].map(oee_by_line)
    if calendar["oee"].isna().any():
        missing_lines = calendar[calendar["oee"].isna()]["line"].unique()
        raise ValueError(f"Missing OEE value for line(s): {missing_lines}")

    calendar["gross_capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]
    calendar["capacity_hours"] = calendar["gross_capacity_hours"] * calendar["oee"]

    # For required_hours, sum normally per line & month
    demand_hours = (
        orders.groupby(["line", "month"])["required_hours"]
        .sum()
        .reset_index()
    )

    # For meters and m2, if an order_id appears multiple times across lines (sandwiches), 
    # take unique order values per line or drop duplicates for physical shipment summation
    orders_unique_metric = orders.drop_duplicates(subset=["order_id", "line", "month"])
    demand_metrics = (
        orders_unique_metric.groupby(["line", "month"])[["meters", "m2"]]
        .sum()
        .reset_index()
    )

    demand = pd.merge(demand_hours, demand_metrics, on=["line", "month"], how="outer")

    summary = calendar.merge(demand, on=["line", "month"], how="left")
    summary["required_hours"] = summary["required_hours"].fillna(0)
    summary["meters"] = summary["meters"].fillna(0)
    summary["m2"] = summary["m2"].fillna(0)
    summary["utilization_pct"] = _safe_pct(summary["required_hours"], summary["capacity_hours"])
    return summary.sort_values(["line", "month"]).reset_index(drop=True)


def append_year_totals(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Adds one 'YYYY Toplam' row per year to a monthly summary table."""
    df = monthly_df.copy()
    df["year"] = df["month"].astype(str).str.slice(0, 4)

    sum_cols = [c for c in ["working_days", "capacity_hours", "required_hours", "meters", "m2"] if c in df.columns]
    totals = df.groupby("year")[sum_cols].sum().reset_index()
    totals["month"] = totals["year"] + " Toplam"
    if "hours_per_day" in df.columns:
        totals["hours_per_day"] = ""
    totals["utilization_pct"] = _safe_pct(totals["required_hours"], totals["capacity_hours"])

    ordered_cols = ["month"] + [c for c in df.columns if c not in ("month", "year")]
    totals = totals.reindex(columns=ordered_cols, fill_value="")

    return pd.concat([df[ordered_cols], totals], ignore_index=True)


def _safe_pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.replace(0, pd.NA)
    return (numerator / denom * 100).fillna(0)


# ---------------------------------------------------------------------------
# Capacity holdout (customer / program level, multi-year)
# ---------------------------------------------------------------------------

def process_holdout_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Reshape wide holdout orders into long format and compute metrics."""
    orders = orders.copy()
    orders.columns = [str(c).strip() for c in orders.columns]

    if "Line No" in orders.columns and "line" not in orders.columns:
        orders = orders.rename(columns={"Line No": "line"})

    forecast_year_strs = [str(y) for y in HOLDOUT_FORECAST_YEARS]
    year_cols = [
        c for c in orders.columns
        if c.startswith("vol_") or c in forecast_year_strs
    ]
    if not year_cols:
        raise ValueError("No year volume columns found in file.")

    id_cols = [c for c in orders.columns if c not in year_cols]
    long_df = orders.melt(
        id_vars=id_cols, value_vars=year_cols,
        var_name="year", value_name="volume",
    )
    long_df["year"] = long_df["year"].astype(str).str.replace("vol_", "", regex=False)
    long_df["volume"] = pd.to_numeric(long_df["volume"], errors="coerce").fillna(0)

    long_df["quantity"] = long_df["volume"]
    long_df["meters"] = long_df.apply(convert_to_meters, axis=1)
    long_df["m2"] = long_df.apply(convert_to_m2, axis=1)
    long_df["required_hours"] = long_df.apply(compute_required_hours, axis=1)

    return long_df


def build_holdout_summary(
    long_df: pd.DataFrame, group_col: str,
    value_col: str = "required_hours", total_label: str = "Toplam Gereken Süre",
) -> pd.DataFrame:
    """Pivot holdout summary table."""
    grouped = long_df.copy()

    if value_col in ["meters", "m2"] and "order_id" in grouped.columns:
        # For physical shipment metrics on holdout/sandwiches, avoid double counting duplicate references if split
        grouped = grouped.drop_duplicates(subset=["year", "order_id", group_col] if group_col != "total" else ["year", "order_id"])

    if group_col == "total":
        pivot = grouped.groupby("year")[value_col].sum().to_frame(name=total_label)
        return pivot.sort_index()

    if group_col not in grouped.columns:
        raise ValueError(f"Unknown grouping column: {group_col}")

    grouped[group_col] = grouped[group_col].fillna("Unspecified").astype(str).str.strip()

    pivot = grouped.pivot_table(
        index="year", columns=group_col, values=value_col,
        aggfunc="sum", fill_value=0,
    )
    return pivot.sort_index()


def align_orders_with_holdout(orders_df: pd.DataFrame, holdout_df: pd.DataFrame):
    """Reconcile regular orders with holdout forecast and standardize cycle times."""
    orders = orders_df.copy()
    holdout = holdout_df.copy()

    if "Line No" in holdout.columns and "line" not in holdout.columns:
        holdout = holdout.rename(columns={"Line No": "line"})

    if "line" not in holdout.columns:
        return orders, pd.DataFrame(columns=["order_id", "line", "eski_cycle_time", "yeni_cycle_time"])

    has_holdout_cycle_time = "cycle_time_sec_per_m" in holdout.columns

    def _apply_cycle_time_override(row_copy: dict, h_row: pd.Series, overrides: list) -> None:
        if not has_holdout_cycle_time or pd.isna(h_row.get("cycle_time_sec_per_m")):
            return
        new_ct = float(h_row["cycle_time_sec_per_m"])
        old_ct = row_copy.get("cycle_time_sec_per_m")
        if pd.isna(old_ct) or float(old_ct) != new_ct:
            overrides.append({
                "order_id": row_copy.get("order_id"),
                "line": row_copy.get("line"),
                "eski_cycle_time": old_ct,
                "yeni_cycle_time": new_ct,
            })
        row_copy["cycle_time_sec_per_m"] = new_ct

    aligned_rows = []
    overrides: list = []

    for order_id, group in orders.groupby("order_id"):
        matching_holdout = holdout[holdout["order_id"] == order_id]

        if matching_holdout.empty:
            aligned_rows.extend(group.to_dict("records"))
            continue

        if len(matching_holdout) > 1 and "line" in matching_holdout.columns:
            for _, h_row in matching_holdout.iterrows():
                row_copy = group.iloc[0].to_dict()
                row_copy["line"] = h_row["line"]
                _apply_cycle_time_override(row_copy, h_row, overrides)
                aligned_rows.append(row_copy)
        else:
            h_row = matching_holdout.iloc[0]
            for _, o_row in group.iterrows():
                row_copy = o_row.to_dict()
                _apply_cycle_time_override(row_copy, h_row, overrides)
                aligned_rows.append(row_copy)

    aligned_df = pd.DataFrame(aligned_rows)
    overrides_df = pd.DataFrame(overrides, columns=["order_id", "line", "eski_cycle_time", "yeni_cycle_time"])
    return aligned_df, overrides_df


def compute_annual_capacity_from_calendar(calendar_df: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """Yearly capacity per line extended across HOLDOUT_FORECAST_YEARS."""
    df = calendar_df.copy()
    df["oee"] = df["line"].map(oee_by_line)

    if df["oee"].isna().any():
        missing = df[df["oee"].isna()]["line"].unique()
        raise ValueError(f"OEE eksik olan hat(lar): {missing}")

    df["capacity_hours"] = df["working_days"] * df["hours_per_day"] * df["oee"]
    df["year"] = df["month"].astype(str).str.slice(0, 4)

    annual_by_line = df.groupby(["line", "year"])["capacity_hours"].sum().reset_index()

    all_lines = list(oee_by_line.keys())
    all_years = [str(y) for y in HOLDOUT_FORECAST_YEARS]

    records = []
    for line in all_lines:
        line_data = annual_by_line[annual_by_line["line"] == line]
        fallback_cap = line_data["capacity_hours"].sum() if not line_data.empty else 0.0

        for year in all_years:
            match = line_data[line_data["year"] == year]
            value = match["capacity_hours"].values[0] if not match.empty else fallback_cap
            records.append({"line": line, "year": year, "capacity_hours": value})

    return pd.DataFrame(records)