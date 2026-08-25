<<<<<<< HEAD
=======
<<<<<<< HEAD

>>>>>>> 946fc96 (Added Holdouts, and chart updates)
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
<<<<<<< HEAD
    process_holdout_orders,
=======
=======
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
    process_holdout_orders,
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
    process_orders,
    validate_columns,
)

st.set_page_config(page_title="Tarak Hattı Fizibilite Planlayıcı", layout="wide")
<<<<<<< HEAD

# Header Section
col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=180)
=======
<<<<<<< HEAD
col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=600)   # bump this number until it looks right
=======

# Header Section
col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=180)
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
with col2:
    st.title("Tarak Hattı Fizibilite Planlayıcı")


<<<<<<< HEAD
# ---------- Caching ----------
@st.cache_data(show_spinner=False)
def read_any(uploaded_file) -> pd.DataFrame:
=======
<<<<<<< HEAD
def read_any(uploaded_file) -> pd.DataFrame:
    """Read an uploaded .xlsx or .csv into a dataframe."""
=======
# ---------- Caching ----------
@st.cache_data(show_spinner=False)
def read_any(uploaded_file) -> pd.DataFrame:
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


<<<<<<< HEAD
=======
<<<<<<< HEAD
# ---------- Sidebar: uploads + OEE ----------
=======
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
@st.cache_data(show_spinner=False)
def get_processed_line_data(orders_df: pd.DataFrame, calendar_df: pd.DataFrame, oee_by_line: dict):
    processed = process_orders(orders_df)
    summary = build_monthly_summary(processed, calendar_df, oee_by_line)
    return processed, summary


# ---------- Sidebar: Inputs ----------
<<<<<<< HEAD
=======
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
st.sidebar.header("1. Dosya Yükle")
calendar_file = st.sidebar.file_uploader(
    "Takvim (hat, ay, çalışma_günleri, günlük_çalışma_saati)",
    type=["xlsx", "csv"],
)
orders_file = st.sidebar.file_uploader(
<<<<<<< HEAD
    "Siparişler (sipariş no, ürün, hat, ay, birim, miktar, genişlik(m), uzunluk(m), metre_başına_çevrim_süresi(sn))",
=======
<<<<<<< HEAD
    "Siparişler (sipariş no, ürün, hat, ay, birim, miktar,"
    " genişlik(m), uzunluk(m), metre_başına_çevrim_süresi(sn))",
=======
    "Siparişler (sipariş no, ürün, hat, ay, birim, miktar, genişlik(m), uzunluk(m), metre_başına_çevrim_süresi(sn))",
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
    type=["xlsx", "csv"],
)

st.sidebar.header("2. Hat OEE Değerlerini Girin")
st.sidebar.caption("Algılanan hatlar için OEE değerleri dosyadan otomatik olarak doldurulur.")

<<<<<<< HEAD
=======
<<<<<<< HEAD
# ---------- Main logic ----------
=======
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
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
<<<<<<< HEAD
        f"OEE — {line}", min_value=0.01, max_value=1.0, value=0.78, step=0.01, key=f"oee_{line}"
=======
<<<<<<< HEAD
        f"OEE — {line}", min_value=0.01, max_value=1.0, value=0.78, step=0.01
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
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
<<<<<<< HEAD
    processed_orders, summary = get_processed_line_data(orders_df, calendar_df, oee_by_line)
=======
    processed_orders = process_orders(orders_df, oee_by_line)
    summary = build_monthly_summary(processed_orders, calendar_df)
=======
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
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
except Exception as e:
    st.error(f"Hesaplama hatası: {e}")
    st.stop()

<<<<<<< HEAD
# ---------- Dynamic Tab Generation ----------
tab_names = list(lines) + ["Kapasite Holdout"]
tabs = st.tabs(tab_names)

# Render individual Line tabs (TRK0001, TRK0002 vb.)
for tab, line in zip(tabs[:-1], lines):
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        st.subheader(f"{line} — Aylık Özet")
=======
<<<<<<< HEAD
# ---------- Results, one tab per line ----------
tabs = st.tabs(list(lines))
for tab, line in zip(tabs, lines):
    
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        st.subheader(f"{line} — aylık özet")
=======
# ---------- Dynamic Tab Generation ----------
tab_names = list(lines) + ["Kapasite Holdout"]
tabs = st.tabs(tab_names)

# Render individual Line tabs (TRK0001, TRK0002 vb.)
for tab, line in zip(tabs[:-1], lines):
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        st.subheader(f"{line} — Aylık Özet")
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)

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
<<<<<<< HEAD
                    ["Ay", "Çalışma Günleri", "Günlük Çalışma Saati", "Kapasite Saatleri", "Gereken Süre", "Doluluk %"]
=======
<<<<<<< HEAD
                    ["Ay", "Çalışma Günleri", "Günlük Çalışma Saati", "Kapasite Saatleri",
                     "Gereken Süre", "Doluluk %"]
=======
                    ["Ay", "Çalışma Günleri", "Günlük Çalışma Saati", "Kapasite Saatleri", "Gereken Süre", "Doluluk %"]
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
                ].style.format({
                    "Kapasite Saatleri": "{:.0f}",
                    "Gereken Süre": "{:.1f}",
                    "Doluluk %": "{:.1f}%",
                }),
                use_container_width=True,
            )

        with col_chart:
<<<<<<< HEAD
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
            # Tüm ayların gösterilmesini zorunlu kılan ekşen ayarları
            fig.update_xaxes(type="category", tickmode="linear")
            fig.update_yaxes(title_text="Saatler", secondary_y=False)
            fig.update_yaxes(title_text="Doluluk %", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)
=======
<<<<<<< HEAD
            fig, ax1 = plt.subplots(figsize=(7, 5))
            x = range(len(line_summary))
            width = 0.35
            ax1.bar([i - width / 2 for i in x], line_summary["capacity_hours"],
                    width, label="Kapasite (sa)", color="#4C72B0")
            ax1.bar([i + width / 2 for i in x], line_summary["required_hours"],
                    width, label="Gereken (sa)", color="#DD8452")
            ax1.set_xticks(list(x))
            ax1.set_xticklabels(line_summary["month"], rotation=45)
            ax1.set_ylabel("Saatler")
            ax1.legend(loc="upper left")

            ax2 = ax1.twinx()
            ax2.plot(x, line_summary["utilization_pct"], color="black",
                      marker="o", label="Doluluk %")
            ax2.axhline(100, color="red", linestyle="--", linewidth=1)
            ax2.set_ylabel("Doluluk %")
            ax2.legend(loc="upper right")

            plt.title(f"{line}: Kapasite vs Gereken Süre ve Doluluk")
            fig.tight_layout()
            st.pyplot(fig)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)

        csv_bytes = line_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download {line} summary as CSV",
            data=csv_bytes,
            file_name=f"{line}_monthly_summary.csv",
            mime="text/csv",
<<<<<<< HEAD
=======
=======
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
            # Tüm ayların gösterilmesini zorunlu kılan ekşen ayarları
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
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
            key=f"dl_{line}",
        )

# ---------- Render the Kapasite Holdout Tab ----------
# ---------- Render the Kapasite Holdout Tab ----------
# ---------- Render the Kapasite Holdout Tab ----------
with tabs[-1]:
    st.subheader("Müşteri Bazında Kapasite Analizi")
    if not holdout_file:
        st.info("Kapasite dosyasını sol menüden yükleyin.")
    else:
        holdout_raw = read_any(holdout_file)
        try:
            long_df = process_holdout_orders(holdout_raw)
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
            st.dataframe(pivot.style.format("{:.0f}"), use_container_width=True)

        with col_chart:
            years_str = [str(y) for y in pivot.index.tolist()]
            
            # 1. Yıllık Kapasiteleri Takvimden Dinamik Olarak Çek
            from planner_core import compute_annual_capacity_from_calendar
            annual_capacities = compute_annual_capacity_from_calendar(calendar_df, oee_by_line)

            # Grafikte çizdirilecek yıl bazlı kapasite listesini oluştur
            default_cap = annual_capacities.get("default", list(annual_capacities.values())[0] if annual_capacities else 0)
            capacity_line_values = [annual_capacities.get(y, default_cap) for y in years_str]

            # 2. Yüzdelik Değerlerin Hesaplanması (O Yılın Toplam Holdout Yükü İçindeki Payı)
            yearly_totals = pivot.sum(axis=1)
            pivot_pct = pivot.div(yearly_totals, axis=0) * 100

            fig_holdout = go.Figure()

            # Stacked Bar Katmanları (Süre + Yüzde İpucu)
            for col in pivot.columns:
                hover_text = [
                    f"<b>{col}</b><br>"
                    f"Yıl: {year}<br>"
                    f"Gereken Süre: {val:,.1f} sa<br>"
                    f"Payı: %{pct:.1f}"
                    for year, val, pct in zip(years_str, pivot[col], pivot_pct[col])
                ]
                
                fig_holdout.add_trace(
                    go.Bar(
                        x=years_str,
                        y=pivot[col],
                        name=str(col),
                        hoverinfo="text",
                        hovertext=hover_text,
                    )
                )

            # 3. Takvimden Alınan Maksimum Kapasite Çizgisi
            fig_holdout.add_trace(
                go.Scatter(
                    x=years_str,
                    y=capacity_line_values,
                    mode="lines+markers",
                    name="Maks. Yıllık Kapasite (Takvim)",
                    line=dict(color="black", width=3, dash="dash"),
                    hoverinfo="text",
                    hovertext=[f"Maks. Kapasite ({year}): {cap:,.0f} sa" for year, cap in zip(years_str, capacity_line_values)]
                )
            )

            fig_holdout.update_layout(
                barmode="stack",
                title_text=f"Kapasite: {HOLDOUT_GROUP_LABELS[group_col]} Bazında",
                xaxis_title="Yıl",
                yaxis_title="Gereken Süre (saat)",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(title=HOLDOUT_GROUP_LABELS[group_col], orientation="h", y=-0.2),
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
<<<<<<< HEAD
=======
>>>>>>> e0fa1ed (Added Holdouts, and chart updates)
>>>>>>> 946fc96 (Added Holdouts, and chart updates)
        )