"""
Shared capacity-planning logic for carding lines TRK0001 / TRK0002 (or more).
<<<<<<< HEAD
Both the CLI script and the Streamlit app import from here.
=======
<<<<<<< HEAD
Both the CLI script and the Streamlit app import from here, so the math
only lives in one place.
=======
Both the CLI script and the Streamlit app import from here.
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
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
            raise ValueError(f"{row['order_id']}: M2 order needs width_m")
        return row["quantity"] / row["width_m"]

    if unit == "PCS":
        if pd.isna(row["length_m"]) or row["length_m"] == 0:
            raise ValueError(f"{row['order_id']}: PCS order needs length_m")
        return row["quantity"] * row["length_m"]

    raise ValueError(f"{row['order_id']}: unknown unit '{unit}'")


<<<<<<< HEAD
def compute_required_hours(row: pd.Series) -> float:
    """Ideal production time required for the order (without OEE)."""
    return (row["meters"] * row["cycle_time_sec_per_m"]) / 3600
=======
<<<<<<< HEAD
def compute_required_hours(row: pd.Series, oee_by_line: dict) -> float:
    """Ideal time for the meters, inflated by that line's OEE."""
    line = row["line"]
    if line not in oee_by_line:
        raise ValueError(f"{row['order_id']}: no OEE set for line '{line}'")
    ideal_hours = (row["meters"] * row["cycle_time_sec_per_m"]) / 3600
    return ideal_hours / oee_by_line[line]
>>>>>>> 946fc96 (Added Holdouts, and chart updates)


def process_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add meters + required_hours columns to a raw orders dataframe."""
    orders = orders.copy()
    orders["meters"] = orders.apply(convert_to_meters, axis=1)
    orders["required_hours"] = orders.apply(compute_required_hours, axis=1)
    return orders


def build_monthly_summary(orders: pd.DataFrame, calendar: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """One row per (line, month): effective capacity (scaled by OEE) vs. required hours vs. utilization %."""
    calendar = calendar.copy()
<<<<<<< HEAD
=======
    calendar["capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]
=======
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
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
    
    # Apply OEE directly to gross capacity
    calendar["oee"] = calendar["line"].map(oee_by_line)
    if calendar["oee"].isna().any():
        missing_lines = calendar[calendar["oee"].isna()]["line"].unique()
        raise ValueError(f"Missing OEE value for line(s): {missing_lines}")

    calendar["gross_capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]
    calendar["capacity_hours"] = calendar["gross_capacity_hours"] * calendar["oee"]
<<<<<<< HEAD
=======
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)

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

<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
def compute_annual_capacity_from_calendar(calendar_df: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """
    Takvimdeki aylık çalışma sürelerini ve OEE'leri kullanarak yıllık toplam hat kapasitesini hesaplar.
    """
    df = calendar_df.copy()
    df["oee"] = df["line"].map(oee_by_line)
    df["capacity_hours"] = df["working_days"] * df["hours_per_day"] * df["oee"]
    
    # Yıllık toplam kapasite (Eğer takvim tek bir yılı kapsıyorsa bu değer her hat için yıllık toplamdır)
    annual_line_capacity = df.groupby("line")["capacity_hours"].sum().reset_index()
    total_annual_capacity = annual_line_capacity["capacity_hours"].sum()
    
    return total_annual_capacity

<<<<<<< HEAD
=======
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)

def validate_columns(df: pd.DataFrame, required: list, label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> 946fc96 (Added Holdouts, and chart updates)


# ---------------------------------------------------------------------------
# Capacity holdout logic
# ---------------------------------------------------------------------------

REQUIRED_HOLDOUT_COLS = [
    "order_id", "customer_plant", "internal_external", "model_key",
    "program_carline", "unit", "cycle_time_sec_per_unit",
]
HOLDOUT_YEAR_COLS = [f"vol_{y}" for y in range(2026, 2032)]
HOLDOUT_GROUP_LABELS = {
    "customer_plant": "Company",
    "internal_external": "Internal / External",
    "model_key": "Customer / Model-Key",
    "program_carline": "Program / Carline",
}


def process_holdout_orders(orders: pd.DataFrame, oee: float = 1.0) -> pd.DataFrame:
    """
    Reshape the wide holdout orders into long format and compute required_hours.
    """
    year_cols = [c for c in HOLDOUT_YEAR_COLS if c in orders.columns]
    if not year_cols:
        raise ValueError(f"No year volume columns found (expected some of {HOLDOUT_YEAR_COLS})")

    id_cols = [c for c in orders.columns if c not in year_cols]
    long_df = orders.melt(
        id_vars=id_cols, value_vars=year_cols,
        var_name="year", value_name="volume",
    )
    long_df["year"] = long_df["year"].str.replace("vol_", "", regex=False)
    long_df["volume"] = long_df["volume"].fillna(0)

    # OEE parametresi verilirse (1.0'dan küçükse) gerekli saati OEE ile şişirir
    ideal_hours = (long_df["volume"] * long_df["cycle_time_sec_per_unit"]) / 3600
    long_df["required_hours"] = ideal_hours / oee
    return long_df


def build_holdout_summary(long_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    Pivot to: rows = year, columns = group_col values, cells = required_hours.
    """
    if group_col not in long_df.columns:
        raise ValueError(f"Unknown grouping column: {group_col}")

    grouped = long_df.copy()
    grouped[group_col] = grouped[group_col].fillna("Unspecified")

    pivot = grouped.pivot_table(
        index="year", columns=group_col, values="required_hours",
        aggfunc="sum", fill_value=0,
    )
    return pivot.sort_index()
def compute_annual_capacity_from_calendar(calendar_df: pd.DataFrame, oee_by_line: dict) -> dict:
    """
    Takvimdeki verileri kullanarak yıl bazında toplam net kapasiteyi (saat) hesaplar.
    Eğer takvimde 'year' veya 'yıl' sütunu yoksa, toplam takvim kapasitesini varsayılan olarak döner.
    """
    df = calendar_df.copy()
    df["oee"] = df["line"].map(oee_by_line)
    df["capacity_hours"] = df["working_days"] * df["hours_per_day"] * df["oee"]

    # Takvimde yıl sütununu kontrol et ('year' veya 'yıl' / 'yil')
    year_col = None
    for col in df.columns:
        if str(col).lower() in ["year", "yıl", "yil"]:
            year_col = col
            break

    if year_col:
        # Yıl sütunu varsa yıl bazında toplam al
        annual_cap = df.groupby(year_col)["capacity_hours"].sum().to_dict()
        # Yıl anahtarlarını string yap (ör. "2026")
        return {str(k): v for k, v in annual_cap.items()}
    else:
        # Yıl sütunu yoksa takvimdeki tüm ayların toplamını tek yıllık kapasite kabul et
        total_cap = df["capacity_hours"].sum()
<<<<<<< HEAD
        return {"default": total_cap}
=======
        return {"default": total_cap}
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
