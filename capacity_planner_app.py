import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from planner_core import (
    HOLDOUT_GROUP_LABELS,
    HOLDOUT_METRICS,
    REQUIRED_CALENDAR_COLS,
    REQUIRED_HOLDOUT_COLS,
    REQUIRED_ORDER_COLS,
    align_orders_with_holdout,
    append_year_totals,
    build_holdout_summary,
    build_monthly_summary,
    compute_annual_capacity_from_calendar,
    process_holdout_orders,
    process_orders,
    validate_columns,
)

st.set_page_config(page_title="Tarak Hattı Fizibilite Planlayıcı", layout="wide")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=180)
with col2:
    st.title("Tarak Hattı Fizibilite Planlayıcı")


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def read_any(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    if not isinstance(df, pd.DataFrame):
        # Guards against e.g. an Excel file with sheet_name set elsewhere
        # returning a dict of sheets, or any other non-DataFrame result —
        # fail with a clear message here instead of a cryptic error later.
        raise TypeError(
            f"'{uploaded_file.name}' bir tablo olarak okunamadı (tür: {type(df).__name__}). "
            "Dosyanın tek bir sayfa/tablo içerdiğinden emin olun."
        )
    return df


@st.cache_data(show_spinner=False)
def get_processed_line_data(orders_df: pd.DataFrame, calendar_df: pd.DataFrame, oee_by_line: dict):
    processed = process_orders(orders_df)
    summary = build_monthly_summary(processed, calendar_df, oee_by_line)
    return processed, summary


# ---------------------------------------------------------------------------
# Chart helpers (shared by the "Tüm Hatlar" tab and each per-line tab)
# ---------------------------------------------------------------------------

def capacity_vs_demand_chart(
    df: pd.DataFrame, title: str,
    capacity_color: str = "#4C72B0", required_color: str = "#DD8452",
) -> go.Figure:
    """Grouped bar (capacity vs. required hours) + utilization % line, with a 100% reference line."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(x=df["month"], y=df["capacity_hours"], name="Kapasite (sa)", marker_color=capacity_color),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=df["month"], y=df["required_hours"], name="Gereken (sa)", marker_color=required_color),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["month"], y=df["utilization_pct"], name="Doluluk %",
            mode="lines+markers+text",
            line=dict(color="black"),
            text=[f"{v:.0f}%" for v in df["utilization_pct"]],
            textposition="top center",
            textfont=dict(size=11, color="black"),
        ),
        secondary_y=True,
    )
    fig.add_hline(y=100, line_dash="dash", line_color="red", secondary_y=True)

    fig.update_layout(
        title_text=title,
        barmode="group",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(type="category", tickmode="linear")
    fig.update_yaxes(title_text="Saatler", secondary_y=False)
    fig.update_yaxes(title_text="Doluluk %", secondary_y=True)
    return fig


def value_bar_chart(df: pd.DataFrame, value_col: str, series_name: str, title: str, color: str) -> go.Figure:
    """Simple bar chart of one value column per month, with the value labeled on each bar."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["month"], y=df[value_col], name=series_name,
        marker_color=color,
        text=[f"{v:,.0f}" for v in df[value_col]],
        textposition="outside",
    ))
    fig.update_layout(
        title_text=title,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
    )
    fig.update_xaxes(type="category", tickmode="linear")
    fig.update_yaxes(title_text=series_name)
    return fig


def render_summary_table(df: pd.DataFrame, columns_tr: dict, number_formats: dict) -> None:
    """Rename to Turkish display columns, format, and render as a dataframe."""
    df_tr = df.rename(columns=columns_tr)
    display_cols = list(columns_tr.values())
    st.dataframe(df_tr[display_cols].style.format(number_formats), width="stretch")


# ---------------------------------------------------------------------------
# Sidebar: file uploads
# ---------------------------------------------------------------------------

st.sidebar.header("1. Dosya Yükle")
calendar_file = st.sidebar.file_uploader(
    "Takvim (hat, ay, çalışma_günleri, günlük_çalışma_saati)",
    type=["xlsx", "csv"],
)
orders_file = st.sidebar.file_uploader(
    "Siparişler (sipariş no, ürün, hat, ay, birim, miktar, genişlik(m), uzunluk(m), metre_başına_çevrim_süresi(sn))",
    type=["xlsx", "csv"],
)

st.sidebar.header("2. Hat OEE Değerlerini Girin")
st.sidebar.caption("Algılanan hatlar için OEE değerleri dosyadan otomatik olarak doldurulur.")

if not calendar_file or not orders_file:
    st.info("Başlamak için takvim ve sipariş dosyalarını sol sütundaki uygun yerlere yükleyin.")
    st.stop()

try:
    calendar_df = read_any(calendar_file)
    orders_df = read_any(orders_file)
    validate_columns(calendar_df, REQUIRED_CALENDAR_COLS, "Calendar file")
    validate_columns(orders_df, REQUIRED_ORDER_COLS, "Orders file")
except Exception as e:
    st.error(f"Dosya okunurken hata oluştu: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: capacity holdout upload + order/line alignment
# ---------------------------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.header("3. Kapasite Holdout")
holdout_file = st.sidebar.file_uploader(
    "Holdout siparişleri (holdout_orders_template.xlsx formatında)",
    type=["xlsx", "csv"],
)

cycle_time_overrides = pd.DataFrame(columns=["order_id", "line", "eski_cycle_time", "yeni_cycle_time"])

if holdout_file:
    try:
        holdout_raw_check = read_any(holdout_file)
        orders_df, cycle_time_overrides = align_orders_with_holdout(orders_df, holdout_raw_check)
    except Exception as e:
        st.sidebar.warning(f"Sipariş/holdout hat eşleştirmesi atlandı: {e}")

lines = sorted(orders_df["line"].dropna().unique())
if not lines:
    st.error("Sipariş dosyasında 'hat' sütununda değer bulunamadı.")
    st.stop()

oee_by_line = {
    line: st.sidebar.number_input(
        f"OEE — {line}", min_value=0.01, max_value=1.0, value=0.78, step=0.01, key=f"oee_{line}"
    )
    for line in lines
}

# ---------------------------------------------------------------------------
# Data preview
# ---------------------------------------------------------------------------

if not cycle_time_overrides.empty:
    with st.expander(
        f"⚠️ Holdout dosyasından {len(cycle_time_overrides)} adet çevrim süresi (cycle_time_sec_per_m) güncellendi",
        expanded=False,
    ):
        st.dataframe(
            cycle_time_overrides.rename(columns={
                "order_id": "Sipariş No",
                "line": "Hat",
                "eski_cycle_time": "Eski Çevrim Süresi (sn/m)",
                "yeni_cycle_time": "Yeni Çevrim Süresi (sn/m, Holdout)",
            }),
            width="stretch",
        )

with st.expander("Önizleme: Takvim ve Siparişler"):
    c1, c2 = st.columns(2)
    c1.write("**Calendar**")
    c1.dataframe(calendar_df, width="stretch")
    c2.write("**Orders**")
    c2.dataframe(orders_df, width="stretch")

try:
    processed_orders, summary = get_processed_line_data(orders_df, calendar_df, oee_by_line)
except Exception as e:
    st.error(f"Hesaplama hatası: {e}")
    st.stop()

# Aggregate across all lines, per month, for the combined tab
total_summary = (
    summary.groupby("month", as_index=False)[["capacity_hours", "required_hours", "meters", "m2"]].sum()
)
total_summary["utilization_pct"] = (
    total_summary["required_hours"] / total_summary["capacity_hours"] * 100
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_names = ["Tüm Hatlar (Toplam)"] + list(lines) + ["Kapasite Holdout"]
tabs = st.tabs(tab_names)

# --- Combined ("Tüm Hatlar") tab -------------------------------------------
with tabs[0]:
    st.subheader("Tüm Hatlar — Toplam Aylık Özet")
    col_table, col_chart = st.columns([2.5, 2])

    with col_table:
        total_summary_with_totals = append_year_totals(total_summary)
        render_summary_table(
            total_summary_with_totals,
            columns_tr={
                "month": "Ay",
                "capacity_hours": "Toplam Kapasite Saatleri",
                "required_hours": "Toplam Gereken Süre",
                "meters": "Üretilen Metre",
                "m2": "Üretilen m²",
                "utilization_pct": "Ortalama Doluluk %",
            },
            number_formats={
                "Toplam Kapasite Saatleri": "{:.0f}",
                "Toplam Gereken Süre": "{:.1f}",
                "Üretilen Metre": "{:,.0f}",
                "Üretilen m²": "{:,.0f}",
                "Ortalama Doluluk %": "{:.1f}%",
            },
        )

    with col_chart:
        fig_tot = capacity_vs_demand_chart(
            total_summary, "Tüm Hatlar Toplamı: Kapasite vs Gereken Süre",
            capacity_color="#1f77b4", required_color="#ff7f0e",
        )
        st.plotly_chart(fig_tot, width="stretch")

    col_meters_chart, col_m2_chart = st.columns(2)
    with col_meters_chart:
        st.plotly_chart(
            value_bar_chart(total_summary, "meters", "Üretilen Metre", "Tüm Hatlar Toplamı: Üretilen Metre", "#2E8B57"),
            width="stretch",
        )
    with col_m2_chart:
        st.plotly_chart(
            value_bar_chart(total_summary, "m2", "Üretilen m²", "Tüm Hatlar Toplamı: Üretilen m²", "#8A2BE2"),
            width="stretch",
        )

    st.download_button(
        label="Tüm hatlar özetini CSV olarak indir",
        data=total_summary.to_csv(index=False).encode("utf-8"),
        file_name="tum_hatlar_toplam_ozet.csv",
        mime="text/csv",
        key="dl_total",
    )

# --- Per-line tabs -----------------------------------------------------------
for tab, line in zip(tabs[1:-1], lines):
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        line_summary_with_totals = append_year_totals(line_summary)
        st.subheader(f"{line} — Aylık Özet")

        col_table, col_chart = st.columns([2.5, 2])

        with col_table:
            render_summary_table(
                line_summary_with_totals,
                columns_tr={
                    "month": "Ay",
                    "working_days": "Çalışma Günleri",
                    "hours_per_day": "Günlük Çalışma Saati",
                    "capacity_hours": "Kapasite Saatleri",
                    "required_hours": "Gereken Süre",
                    "meters": "Üretilen Metre",
                    "m2": "Üretilen m²",
                    "utilization_pct": "Doluluk %",
                },
                number_formats={
                    "Kapasite Saatleri": "{:.0f}",
                    "Gereken Süre": "{:.1f}",
                    "Üretilen Metre": "{:,.0f}",
                    "Üretilen m²": "{:,.0f}",
                    "Doluluk %": "{:.1f}%",
                },
            )

        with col_chart:
            fig = capacity_vs_demand_chart(line_summary, f"{line}: Kapasite vs Gereken Süre")
            st.plotly_chart(fig, width="stretch")

        col_meters_chart, col_m2_chart = st.columns(2)
        with col_meters_chart:
            st.plotly_chart(
                value_bar_chart(line_summary, "meters", "Üretilen Metre", f"{line}: Üretilen Metre", "#2E8B57"),
                width="stretch",
            )
        with col_m2_chart:
            st.plotly_chart(
                value_bar_chart(line_summary, "m2", "Üretilen m²", f"{line}: Üretilen m²", "#8A2BE2"),
                width="stretch",
            )

        st.download_button(
            label=f"Download {line} summary as CSV",
            data=line_summary.to_csv(index=False).encode("utf-8"),
            file_name=f"{line}_monthly_summary.csv",
            mime="text/csv",
            key=f"dl_{line}",
        )

# --- Capacity holdout tab ---------------------------------------------------
with tabs[-1]:
    st.subheader("Müşteri Bazında Kapasite Analizi")

    if not holdout_file:
        st.info("Kapasite dosyasını sol menüden yükleyin.")
    else:
        holdout_raw = read_any(holdout_file)
        try:
            validate_columns(holdout_raw, REQUIRED_HOLDOUT_COLS, "Holdout dosyası")
            long_df = process_holdout_orders(holdout_raw)
        except Exception as e:
            st.error(f"Hesaplama hatası: {e}")
            st.stop()

        available_groups = {
            k: v for k, v in HOLDOUT_GROUP_LABELS.items()
            if k == "total" or k in long_df.columns
        }

        col_select1, col_select2 = st.columns([2, 1])
        with col_select1:
            group_col = st.selectbox(
                "Gruplama",
                options=list(available_groups.keys()),
                format_func=lambda c: available_groups[c],
                key="holdout_group_select",
            )
        with col_select2:
            metric_col = st.radio(
                "Birim",
                options=list(HOLDOUT_METRICS.keys()),
                format_func=lambda m: HOLDOUT_METRICS[m]["label"],
                horizontal=True,
                key="holdout_metric_select",
            )

        metric_info = HOLDOUT_METRICS[metric_col]
        unit = metric_info["unit"]

        try:
            pivot = build_holdout_summary(
                long_df, group_col,
                value_col=metric_col, total_label=metric_info["total_label"],
            )
        except Exception as e:
            st.error(f"Hesaplama hatası: {e}")
            st.stop()

        col_table, col_chart = st.columns([2, 3])

        with col_table:
            st.dataframe(pivot.style.format("{:,.0f}"), width="stretch")

        with col_chart:
            years_str = [str(y) for y in pivot.index.tolist()]

            fig_holdout = go.Figure()

            yearly_totals = pivot.sum(axis=1)
            pivot_pct = pivot.div(yearly_totals, axis=0) * 100

            for col in pivot.columns:
                hover_text = [
                    f"<b>{col}</b><br>Yıl: {year}<br>{metric_info['label']}: {val:,.1f} {unit}<br>Payı: %{pct:.1f}"
                    for year, val, pct in zip(years_str, pivot[col], pivot_pct[col])
                ]
                fig_holdout.add_trace(go.Bar(
                    x=years_str, y=pivot[col], name=str(col),
                    hoverinfo="text", hovertext=hover_text,
                ))

            # A capacity comparison line only makes sense for the hours
            # metric — there's no meaningful "capacity in meters".
            if metric_col == "required_hours":
                capacity_df = compute_annual_capacity_from_calendar(calendar_df, oee_by_line)

                if group_col == "line":
                    for line_name in pivot.columns:
                        line_cap = capacity_df[capacity_df["line"] == line_name].set_index("year")["capacity_hours"]
                        cap_values = [line_cap.get(y, 0) for y in years_str]
                        fig_holdout.add_trace(go.Scatter(
                            x=years_str, y=cap_values, mode="lines+markers",
                            name=f"Kapasite — {line_name}",
                            line=dict(width=3, dash="dash"),
                            hoverinfo="text",
                            hovertext=[f"{line_name} ({y}): {c:,.0f} sa" for y, c in zip(years_str, cap_values)],
                        ))
                else:
                    total_factory_capacity = capacity_df.groupby("year")["capacity_hours"].sum()
                    cap_values = [total_factory_capacity.get(y, 0) for y in years_str]
                    fig_holdout.add_trace(go.Scatter(
                        x=years_str, y=cap_values, mode="lines+markers",
                        name="Toplam Fabrika Kapasitesi (2 Hat Toplamı)",
                        line=dict(color="red", width=3, dash="dash"),
                        hoverinfo="text",
                        hovertext=[f"Toplam 2 Hat Kapasitesi ({y}): {c:,.0f} sa" for y, c in zip(years_str, cap_values)],
                    ))

            fig_holdout.update_layout(
                barmode="stack",
                title_text=f"Kapasite Holdout — {available_groups[group_col]} ({metric_info['label']})",
                xaxis_title="Yıl", yaxis_title=metric_info["label"],
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5),
            )
            fig_holdout.update_xaxes(type="category", tickmode="linear")
            st.plotly_chart(fig_holdout, width="stretch")

        st.download_button(
            "Holdout özetini indir",
            data=pivot.to_csv().encode("utf-8"),
            file_name=f"kapasite_holdout_{metric_col}.csv",
            mime="text/csv",
            key="dl_holdout",
        )