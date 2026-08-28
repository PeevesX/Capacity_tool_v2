"""
Shared capacity-planning logic for carding lines TRK0001 / TRK0002 (or more).
Both the CLI script and the Streamlit app import from here.

Nothing in this module touches Streamlit — it's pure pandas so it can be
unit-tested and reused outside the app.
"""

import re

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

HOLDOUT_METRICS = {
    "required_hours": {"label": "Süre (Saat)", "unit": "sa", "total_label": "Toplam Gereken Süre"},
    "meters": {"label": "Üretim (Metre)", "unit": "m", "total_label": "Toplam Üretilen Metre"},
    "m2": {"label": "Üretim (m²)", "unit": "m²", "total_label": "Toplam Üretilen m²"},
}

# Lines that run double-width material and slit it into two strips, so one
# meter of machine travel yields two meters of finished product.
# Add a line code here (e.g. "TRK0003") if another double-width line is
# introduced later — nothing else in this file needs to change.
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
# Wide-format orders file (GPN-based, one row per GPN+Line, monthly volume
# columns named "Part volume-M{ay}{yıl}", e.g. "Part volume-12027" = Jan 2027)
# ---------------------------------------------------------------------------

WIDE_ORDERS_VOLUME_PATTERN = re.compile(r"^Part volume-(\d{1,2})(\d{4})$")


def load_wide_orders(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the GPN-based wide orders file into the long (order_id,
    product, line, month, unit, quantity, width_m, length_m,
    cycle_time_sec_per_m) shape the rest of this module expects.

    Each row already carries its own line, unit, width_m, length_m, and
    cycle_time_sec_per_m — if a GPN genuinely runs on both TRK0001 and
    TRK0002, the file simply has two rows for it, each with that line's
    own cycle time. No separate holdout-alignment step is needed to
    infer this (see align_orders_with_holdout, now unused for this).

    Numeric volume cells that come through as text/oddly formatted are
    coerced to numbers; anything that still can't be read as a number
    becomes 0 rather than raising, since a handful of stray formatting
    quirks shouldn't block the whole file from loading.
    """
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {}
    if "Line No" in df.columns:
        rename_map["Line No"] = "line"
    for cand in ("UNIT\nTR", "UNIT TR"):
        if cand in df.columns:
            rename_map[cand] = "unit"
            break
    if "GPN" in df.columns:
        rename_map["GPN"] = "order_id"
    if "GPN Description" in df.columns:
        rename_map["GPN Description"] = "product"
    df = df.rename(columns=rename_map)

    volume_cols = [c for c in df.columns if WIDE_ORDERS_VOLUME_PATTERN.match(c)]
    if not volume_cols:
        raise ValueError("No 'Part volume-M{ay}{yıl}' columns found in file.")

    id_cols = [c for c in df.columns if c not in volume_cols]
    long_df = df.melt(
        id_vars=id_cols, value_vars=volume_cols,
        var_name="_volcol", value_name="quantity",
    )

    def _parse_month(colname: str) -> str:
        m = WIDE_ORDERS_VOLUME_PATTERN.match(colname)
        month_num, year = int(m.group(1)), m.group(2)
        return f"{year}-{month_num:02d}"

    long_df["month"] = long_df["_volcol"].apply(_parse_month)
    long_df = long_df.drop(columns=["_volcol"])

    long_df["quantity"] = pd.to_numeric(long_df["quantity"], errors="coerce").fillna(0)
    long_df["order_id"] = long_df["order_id"].astype(str)

    return long_df


# ---------------------------------------------------------------------------
# Orders -> required hours / meters / m2
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
    """
    Turn one order's quantity into square meters (finished area), based on unit.
    - M2: quantity is already an area.
    - M: quantity * width_m.
    - ADT / PCS: quantity * length_m * width_m.
    """
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
    """
    Ideal production time required for the order (without OEE).

    Double-width lines (see DOUBLE_WIDTH_LINES) split the web down the
    middle after production, so the machine only has to travel half the
    finished meters — hence the /2. This only affects *hours*; the
    finished-meters figure (row["meters"]) is unaffected, since the
    customer still receives the full meterage.
    """
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
    hours, produced meters, and produced m².

    Required hours and meters are summed per (line, month) as-is, since
    each line's row reflects that line's own real machine load. m² (the
    physically shipped area) is deduplicated by (order_id, month) BEFORE
    the per-line grouping — a sandwich order duplicated across two lines
    (see align_orders_with_holdout) still ships as ONE m², so only one of
    its duplicate rows should contribute to the m² total.
    """
    calendar = calendar.copy()

    calendar["oee"] = calendar["line"].map(oee_by_line)
    if calendar["oee"].isna().any():
        missing_lines = calendar[calendar["oee"].isna()]["line"].unique()
        raise ValueError(f"Missing OEE value for line(s): {missing_lines}")

    calendar["gross_capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]
    calendar["capacity_hours"] = calendar["gross_capacity_hours"] * calendar["oee"]

    demand_hours_meters = (
        orders.groupby(["line", "month"])[["required_hours", "meters"]]
        .sum()
        .reset_index()
    )

    orders_unique_m2 = orders.drop_duplicates(subset=["order_id", "month"], keep="first")
    demand_m2 = (
        orders_unique_m2.groupby(["line", "month"])["m2"]
        .sum()
        .reset_index()
    )

    demand = pd.merge(demand_hours_meters, demand_m2, on=["line", "month"], how="outer")

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
    """numerator / denominator * 100, without blowing up on zero-capacity rows."""
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
    """
    Pivot to: rows = year, columns = group_col values, cells = value_col
    ('required_hours', 'meters', or 'm2' — see HOLDOUT_METRICS).

    For m2 (shipped area), a sandwich order duplicated across two lines
    (see align_orders_with_holdout) still ships as ONE m² of finished
    product — so it's deduplicated by (year, order_id) BEFORE any
    grouping happens, regardless of what group_col is. This deliberately
    does NOT include 'line' in the dedup subset: doing so would make the
    dedup a no-op whenever group_col == 'line', since (year, order_id,
    line) is already unique per row by construction — line is exactly
    what differs between the two duplicate rows. (That was the earlier
    bug: m² still doubled specifically when grouping by Physical Line.)

    required_hours is NOT deduplicated: each line's row reflects that
    line's own real, separate machine time, and both genuinely occur.
    """
    grouped = long_df.copy()

    if value_col == "m2" and "order_id" in grouped.columns:
        grouped = grouped.drop_duplicates(subset=["year", "order_id"], keep="first")

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
    """
    Reconcile the regular orders file with the holdout forecast.

    1. Multi-line split: if an order_id appears against a single line in
       orders_df but against multiple lines in holdout_df (e.g. a
       sandwich/double-layer product produced partly on TRK0001 and partly
       on TRK0002), this duplicates that order row once per line the
       holdout lists. Each copy carries the order's full quantity.

    2. Cycle-time standardization: holdout is treated as the source of
       truth for cycle_time_sec_per_m. Wherever an order_id also appears
       in the holdout file, the holdout's cycle_time_sec_per_m overrides
       whatever value is in the orders file, if the two differ. Every
       such override is recorded so the caller can show what changed.

    Returns:
        (aligned_orders_df, overrides_df)
    """
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
    """
    Yearly capacity per line, extended out across HOLDOUT_FORECAST_YEARS.

    Lines with calendar data for a given year use that year's actual
    total; lines missing a year fall back to that line's overall
    calendar total as a stand-in estimate.
    """
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