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

    if unit == "PCS":
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

    # Apply OEE directly to gross capacity
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


# ---------------------------------------------------------------------------
# Capacity holdout logic
# ---------------------------------------------------------------------------

REQUIRED_HOLDOUT_COLS = [
    "order_id", "customer_plant", "internal_external", "model_key",
    "program_carline", "unit", "cycle_time_sec_per_unit",
]
HOLDOUT_YEAR_COLS = [f"vol_{y}" for y in range(2026, 2032)] + [str(y) for y in range(2026, 2032)] + list(range(2026, 2032))
HOLDOUT_GROUP_LABELS = {
    "total": "Toplam (Genel Özet)",
    "customer_plant": "Company",
    "internal_external": "Internal / External",
    "model_key": "Customer / Model-Key",
    "program_carline": "Program / Carline",
}


def build_holdout_summary(long_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    Pivot to: rows = year, columns = group_col values, cells = required_hours.
    """
    grouped = long_df.copy()

    if group_col == "total":
        pivot = grouped.groupby("year")["required_hours"].sum().to_frame(name="Toplam Gereken Süre")
        return pivot.sort_index()

    if group_col not in grouped.columns:
        raise ValueError(f"Unknown grouping column: {group_col}")

    grouped[group_col] = grouped[group_col].fillna("Unspecified")

    pivot = grouped.pivot_table(
        index="year",
        columns=group_col,
        values="required_hours",
        aggfunc="sum",
        fill_value=0,
    )
    return pivot.sort_index()


def process_holdout_orders(orders: pd.DataFrame, oee) -> pd.DataFrame:
    """
    Reshape wide holdout orders into long format and compute required_hours.
    """
    orders = orders.copy()
    # Standardize column headers to string
    orders.columns = [str(c) for c in orders.columns]

    year_cols = [c for c in orders.columns if c.startswith("vol_") or c in [str(y) for y in range(2026, 2032)]]
    if not year_cols:
        raise ValueError(f"No year volume columns found in file.")

    id_cols = [c for c in orders.columns if c not in year_cols]
    long_df = orders.melt(id_vars=id_cols, value_vars=year_cols,
                           var_name="year", value_name="volume")
    long_df["year"] = long_df["year"].astype(str).str.replace("vol_", "", regex=False)
    long_df["volume"] = pd.to_numeric(long_df["volume"], errors="coerce").fillna(0)

    ideal_hours = (long_df["volume"] * long_df["cycle_time_sec_per_unit"]) / 3600

    if isinstance(oee, dict):
        if "line" not in long_df.columns:
            # If no line column present, fallback to average of oee_by_line
            avg_oee = sum(oee.values()) / len(oee) if oee else 0.78
            long_df["required_hours"] = ideal_hours / avg_oee
        else:
            missing = set(long_df["line"].dropna().unique()) - set(oee.keys())
            if missing:
                raise ValueError(f"No OEE set for line(s): {sorted(missing)}")
            long_df["required_hours"] = ideal_hours / long_df["line"].map(oee)
    else:
        long_df["required_hours"] = ideal_hours / oee

    return long_df


def compute_annual_capacity_from_calendar(calendar_df: pd.DataFrame, oee_by_line: dict) -> dict:
    """
    Computes total annual net capacity hours per line aggregated across all months.
    """
    df = calendar_df.copy()
    df["oee"] = df["line"].map(oee_by_line)
    df["capacity_hours"] = df["working_days"] * df["hours_per_day"] * df["oee"]

    annual_total = df["capacity_hours"].sum()
    
    # Returns annual capacity mapped to all holdout years (2026-2031)
    return {str(y): annual_total for y in range(2026, 2032)}