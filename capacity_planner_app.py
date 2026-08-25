import io
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from planner_core import (
    HOLDOUT_GROUP_LABELS,
    REQUIRED_CALENDAR_COLS,
    REQUIRED_ORDER_COLS,
    build_holdout_summary,
    build_monthly_summary,
    compute_annual_capacity_from_calendar,
    process_holdout_orders,
    process_orders,
    validate_columns,
)

st.set_page_config(page_title="Tarak Hattı Fizibilite Planlayıcı", layout="wide")

# Header Section
col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=180)
with col2:
    st.title("Tarak Hattı Fizibilite Planlayıcı")


# ---------- Caching ----------
@st.cache_data(show_spinner=False)
def read_any(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


@st.cache_data(show_spinner=False)
def get_processed_line_data(orders_df: pd.DataFrame, calendar_df: pd.DataFrame, oee_by_line: dict):
    processed = process_orders(orders_df)
    summary = build_monthly_summary(processed, calendar_df, oee_by_line)
    return processed, summary


# ---------- Sidebar: Inputs ----------
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

lines = sorted(orders_df["line"].dropna().unique())
if not lines:
    st.error("Sipariş dosyasında 'hat' sütununda değer bulunamadı.")
    st.stop()

oee_by_line = {}
for line in lines:
    oee_by_line[line] = st.sidebar.number_input(
        f"OEE — {line}", min_value=0.01, max_value=1.0, value=0.78, step=0.01, key=f"oee_{line}"
    )

# ---------- Sidebar: 3. Kapasite Holdout ----------
st.sidebar.markdown("---")
st.sidebar.header("3. Kapasite Holdout")
holdout_file = st.sidebar.file_uploader(
    "Holdout siparişleri (holdout_orders_template.xlsx formatında)",
    type=["xlsx", "csv"],
)
holdout_oee = st.sidebar.number_input(
    "Holdout OEE", min_value=0.01, max_value=1.0, value=0.78, step=0.01, key="holdout_oee"
)

# ---------- Data Preview ----------
with st.expander("Önizleme: Takvim ve Siparişler"):
    c1, c2 = st.columns(2)
    c1.write("**Calendar**")
    c1.dataframe(calendar_df, use_container_width=True)
    c2.write("**Orders**")
    c2.dataframe(orders_df, use_container_width=True)

try:
    processed_orders, summary = get_processed_line_data(orders_df, calendar_df, oee_by_line)
except Exception as e:
    st.error(f"Hesaplama hatası: {e}")
    st.stop()

# Build Total Aggregated Summary across all lines per month
total_summary = (
    summary.groupby("month", as_index=False)[["capacity_hours", "required_hours"]]
    .sum()
)
total_summary["utilization_pct"] = (
    total_summary["required_hours"] / total_summary["capacity_hours"] * 100
)

# ---------- Dynamic Tab Generation ----------
tab_names = ["Tüm Hatlar (Toplam)"] + list(lines) + ["Kapasite Holdout"]
tabs = st.tabs(tab_names)

# Render Combined Tab (All Lines)
with tabs[0]:
    st.subheader("Tüm Hatlar — Toplam Aylık Özet")
    col_table, col_chart = st.columns([2.5, 2])

    with col_table:
        total_summary_tr = total_summary.rename(columns={
            "month": "Ay",
            "capacity_hours": "Toplam Kapasite Saatleri",
            "required_hours": "Toplam Gereken Süre",
            "utilization_pct": "Ortalama Doluluk %",
        })
        st.dataframe(
            total_summary_tr[
                ["Ay", "Toplam Kapasite Saatleri", "Toplam Gereken Süre", "Ortalama Doluluk %"]
            ].style.format({
                "Toplam Kapasite Saatleri": "{:.0f}",
                "Toplam Gereken Süre": "{:.1f}",
                "Ortalama Doluluk %": "{:.1f}%",
            }),
            use_container_width=True,
        )

    with col_chart:
        fig_tot = make_subplots(specs=[[{"secondary_y": True}]])
        fig_tot.add_trace(
            go.Bar(x=total_summary["month"], y=total_summary["capacity_hours"], name="Kapasite (sa)", marker_color="#1f77b4"),
            secondary_y=False,
        )
        fig_tot.add_trace(
            go.Bar(x=total_summary["month"], y=total_summary["required_hours"], name="Gereken (sa)", marker_color="#ff7f0e"),
            secondary_y=False,
        )
        fig_tot.add_trace(
            go.Scatter(x=total_summary["month"], y=total_summary["utilization_pct"], name="Doluluk %", mode="lines+markers", line=dict(color="black")),
            secondary_y=True,
        )
        fig_tot.add_hline(y=100, line_dash="dash", line_color="red", secondary_y=True)
        fig_tot.update_layout(
            title_text="Tüm Hatlar Toplamı: Kapasite vs Gereken Süre",
            barmode="group",
            margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_tot.update_xaxes(type="category", tickmode="linear")
        fig_tot.update_yaxes(title_text="Saatler", secondary_y=False)
        fig_tot.update_yaxes(title_text="Doluluk %", secondary_y=True)
        st.plotly_chart(fig_tot, use_container_width=True)

    csv_bytes_tot = total_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Tüm hatlar özetini CSV olarak indir",
        data=csv_bytes_tot,
        file_name="tum_hatlar_toplam_ozet.csv",
        mime="text/csv",
        key="dl_total",
    )

# Render individual Line tabs (TRK0001, TRK0002 etc.)
for tab, line in zip(tabs[1:-1], lines):
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        st.subheader(f"{line} — Aylık Özet")

        col_table, col_chart = st.columns([2.5, 2])

        with col_table:
            line_summary_tr = line_summary.rename(columns={
                "month": "Ay",
                "working_days": "Çalışma Günleri",
                "hours_per_day": "Günlük Çalışma Saati",
                "capacity_hours": "Kapasite Saatleri",
                "required_hours": "Gereken Süre",
                "utilization_pct": "Doluluk %",
            })
            st.dataframe(
                line_summary_tr[
                    ["Ay", "Çalışma Günleri", "Günlük Çalışma Saati", "Kapasite Saatleri", "Gereken Süre", "Doluluk %"]
                ].style.format({
                    "Kapasite Saatleri": "{:.0f}",
                    "Gereken Süre": "{:.1f}",
                    "Doluluk %": "{:.1f}%",
                }),
                use_container_width=True,
            )

        with col_chart:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Bar(x=line_summary["month"], y=line_summary["capacity_hours"], name="Kapasite (sa)", marker_color="#4C72B0"),
                secondary_y=False,
            )
            fig.add_trace(
                go.Bar(x=line_summary["month"], y=line_summary["required_hours"], name="Gereken (sa)", marker_color="#DD8452"),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(x=line_summary["month"], y=line_summary["utilization_pct"], name="Doluluk %", mode="lines+markers", line=dict(color="black")),
                secondary_y=True,
            )
            fig.add_hline(y=100, line_dash="dash", line_color="red", secondary_y=True)
            fig.update_layout(
                title_text=f"{line}: Kapasite vs Gereken Süre",
                barmode="group",
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig.update_xaxes(type="category", tickmode="linear")
            fig.update_yaxes(title_text="Saatler", secondary_y=False)
            fig.update_yaxes(title_text="Doluluk %", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

        csv_bytes = line_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download {line} summary as CSV",
            data=csv_bytes,
            file_name=f"{line}_monthly_summary.csv",
            mime="text/csv",
            key=f"dl_{line}",
        )

# Render the Kapasite Holdout Tab
# ---------- Render the Kapasite Holdout Tab ----------
with tabs[-1]:
    st.subheader("Müşteri Bazında Kapasite Analizi")
    if not holdout_file:
        st.info("Kapasite dosyasını sol menüden yükleyin.")
    else:
        holdout_raw = read_any(holdout_file)
        try:
            if "line" in holdout_raw.columns and holdout_raw["line"].notna().any():
                long_df = process_holdout_orders(holdout_raw, oee_by_line)
            else:
                long_df = process_holdout_orders(holdout_raw, holdout_oee)
        except Exception as e:
            st.error(f"Hesaplama hatası: {e}")
            st.stop()

        group_col = st.selectbox(
            "Gruplama",
            options=list(HOLDOUT_GROUP_LABELS.keys()),
            format_func=lambda c: HOLDOUT_GROUP_LABELS[c],
            key="holdout_group_select",
        )
        pivot = build_holdout_summary(long_df, group_col)

        col_table, col_chart = st.columns([2, 3])

        with col_table:
            st.dataframe(pivot.style.format("{:,.0f}"), use_container_width=True)

        with col_chart:
            years_str = [str(y) for y in pivot.index.tolist()]
            capacity_dict = compute_annual_capacity_from_calendar(calendar_df, oee_by_line)

            fig_holdout = go.Figure()

            # 1. Bar Grafiği (Gereken Saatler)
            yearly_totals = pivot.sum(axis=1)
            pivot_pct = pivot.div(yearly_totals, axis=0) * 100

            for col in pivot.columns:
                hover_text = [
                    f"<b>{col}</b><br>Yıl: {year}<br>Gereken Süre: {val:,.1f} sa<br>Payı: %{pct:.1f}"
                    for year, val, pct in zip(years_str, pivot[col], pivot_pct[col])
                ]
                fig_holdout.add_trace(go.Bar(
                    x=years_str,
                    y=pivot[col],
                    name=str(col),
                    hoverinfo="text",
                    hovertext=hover_text
                ))

            # 2. Maksimum Yıllık Kapasite Çizgisi (Güvenli Lookup)
            cap_values = [
                capacity_dict.get(y, capacity_dict.get("default", 0))
                for y in years_str
            ]

            fig_holdout.add_trace(go.Scatter(
                x=years_str,
                y=cap_values,
                mode="lines+markers",
                name="Maks. Yıllık Kapasite",
                line=dict(color="red", width=3, dash="dash"),
                hoverinfo="text",
                hovertext=[f"Maks. Kapasite ({y}): {c:,.0f} sa" for y, c in zip(years_str, cap_values)],
            ))

            fig_holdout.update_layout(
                barmode="stack",
                title_text=f"Kapasite Holdout — {HOLDOUT_GROUP_LABELS[group_col]}",
                xaxis_title="Yıl",
                yaxis_title="Süre (Saat)",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5),
            )
            fig_holdout.update_xaxes(type="category", tickmode="linear")
            st.plotly_chart(fig_holdout, use_container_width=True)

        csv_bytes = pivot.to_csv().encode("utf-8")
        st.download_button(
            "Holdout özetini indir",
            data=csv_bytes,
            file_name="kapasite_holdout.csv",
            mime="text/csv",
            key="dl_holdout",
        )