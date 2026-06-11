"""
Seafarer Candidate Dashboard
Reads from Supabase `seafarer_addresses` table.
Run: streamlit run dashboard.py
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str) -> str:
    """Read from Streamlit secrets (cloud) or fall back to .env (local)."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, "")


# ── Page config ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Seafarer Candidate Dashboard",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Tighten default padding */
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    /* KPI card */
    .kpi-card {
        background: #1e2a3a;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        border-left: 4px solid #4c9be8;
    }
    .kpi-title { font-size: 0.82rem; color: #8fa3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { font-size: 2.1rem; font-weight: 700; color: #e8f0fe; margin: 0.3rem 0 0; }
    .kpi-sub   { font-size: 0.78rem; color: #6b8299; }

    /* Section headers */
    .section-header {
        font-size: 1rem;
        font-weight: 600;
        color: #c9d8e8;
        margin-bottom: 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #2d3f52;
    }

    /* Hide Streamlit's default footer */
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Fetching data from Supabase…")
def load_data() -> pd.DataFrame:
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_KEY")
    if not url or not key:
        st.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        st.stop()

    sb = create_client(url, key)

    rows = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            sb.table("seafarer_addresses")
            .select("seaman_id,rank,name,surname,relation,country,country_code,city,email,phone,mobile,imported_at")
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["imported_at"] = pd.to_datetime(df["imported_at"], errors="coerce")

    # Normalise text columns
    for col in ["rank", "relation", "country", "country_code", "city"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").str.strip()

    # Contact completeness flags
    df["has_email"]  = df["email"].notna()  & (df["email"]  != "")
    df["has_phone"]  = df["phone"].notna()  & (df["phone"]  != "")
    df["has_mobile"] = df["mobile"].notna() & (df["mobile"] != "")

    return df


# ── Sidebar – filters ─────────────────────────────────────────────────────────────

df_all = load_data()

with st.sidebar:
    st.image("https://img.icons8.com/fluency/48/anchor.png", width=40)
    st.title("Filters")

    countries = sorted(df_all["country"].unique().tolist())
    sel_countries = st.multiselect("Country", countries, placeholder="All countries")

    ranks = sorted(df_all["rank"].unique().tolist())
    sel_ranks = st.multiselect("Rank", ranks, placeholder="All ranks")

    relations = sorted(df_all["relation"].unique().tolist())
    sel_relations = st.multiselect("Relation", relations, placeholder="All relations")

    st.markdown("---")
    st.caption("Data refreshes every 5 min")
    if st.button("Force refresh"):
        st.cache_data.clear()
        st.rerun()

# Apply filters
df = df_all.copy()
if sel_countries:
    df = df[df["country"].isin(sel_countries)]
if sel_ranks:
    df = df[df["rank"].isin(sel_ranks)]
if sel_relations:
    df = df[df["relation"].isin(sel_relations)]

# ── Header ────────────────────────────────────────────────────────────────────────

st.markdown("## ⚓ Seafarer Candidate Dashboard")
st.markdown(
    f"**{len(df):,}** candidates shown"
    + (f" · filtered from **{len(df_all):,}** total" if len(df) < len(df_all) else " · full dataset")
    + (f" · last imported {df_all['imported_at'].max().strftime('%d %b %Y %H:%M UTC') if not df_all.empty else ''}")
)

st.markdown("---")

# ── KPI row ───────────────────────────────────────────────────────────────────────

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

def kpi_html(title, value, sub=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""

pct_email  = f"{df['has_email'].mean()*100:.0f}% have email"  if not df.empty else ""
pct_mobile = f"{df['has_mobile'].mean()*100:.0f}% have mobile" if not df.empty else ""

with kpi1:
    st.markdown(kpi_html("Total Candidates", f"{len(df):,}", f"{df['country'].nunique()} countries"), unsafe_allow_html=True)
with kpi2:
    st.markdown(kpi_html("Countries", f"{df['country'].nunique():,}", f"{df['city'].nunique()} cities"), unsafe_allow_html=True)
with kpi3:
    st.markdown(kpi_html("Unique Ranks", f"{df['rank'].nunique():,}", ""), unsafe_allow_html=True)
with kpi4:
    st.markdown(kpi_html("With Email", f"{df['has_email'].sum():,}", pct_email), unsafe_allow_html=True)
with kpi5:
    st.markdown(kpi_html("With Mobile", f"{df['has_mobile'].sum():,}", pct_mobile), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 1: World map + Relation pie ──────────────────────────────────────────────

col_map, col_pie = st.columns([2, 1])

with col_map:
    st.markdown('<div class="section-header">Candidates by Country</div>', unsafe_allow_html=True)
    country_counts = (
        df[df["country"] != "Unknown"]
        .groupby(["country", "country_code"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if not country_counts.empty:
        fig_map = px.choropleth(
            country_counts,
            locations="country_code",
            color="count",
            hover_name="country",
            hover_data={"count": True, "country_code": False},
            color_continuous_scale="Blues",
            labels={"count": "Candidates"},
            template="plotly_dark",
        )
        fig_map.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_colorbar=dict(title="Candidates", thickness=12),
            geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False, showcoastlines=True, coastlinecolor="#2d3f52"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=320,
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No data to display.")

with col_pie:
    st.markdown('<div class="section-header">By Relation Type</div>', unsafe_allow_html=True)
    rel_counts = df["relation"].value_counts().reset_index()
    rel_counts.columns = ["relation", "count"]
    if not rel_counts.empty:
        fig_pie = px.pie(
            rel_counts,
            names="relation",
            values="count",
            hole=0.45,
            color_discrete_sequence=px.colors.sequential.Blues_r,
            template="plotly_dark",
        )
        fig_pie.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font_size=11),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=320,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No data to display.")

# ── Row 2: Top countries bar + Contact completeness ─────────────────────────────

col_bar, col_contact = st.columns([2, 1])

with col_bar:
    st.markdown('<div class="section-header">Top 20 Countries by Candidate Count</div>', unsafe_allow_html=True)
    top_countries = (
        df[df["country"] != "Unknown"]["country"]
        .value_counts()
        .head(20)
        .reset_index()
    )
    top_countries.columns = ["country", "count"]
    if not top_countries.empty:
        fig_ctry = px.bar(
            top_countries.sort_values("count"),
            x="count",
            y="country",
            orientation="h",
            color="count",
            color_continuous_scale="Blues",
            labels={"count": "Candidates", "country": ""},
            template="plotly_dark",
            text="count",
        )
        fig_ctry.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_ctry.update_layout(
            margin=dict(l=0, r=60, t=0, b=0),
            showlegend=False,
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=420,
            yaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_ctry, use_container_width=True)
    else:
        st.info("No data to display.")

with col_contact:
    st.markdown('<div class="section-header">Contact Info Completeness</div>', unsafe_allow_html=True)
    if not df.empty:
        contact_data = pd.DataFrame({
            "field": ["Email", "Phone", "Mobile"],
            "has":   [df["has_email"].sum(), df["has_phone"].sum(), df["has_mobile"].sum()],
            "missing": [
                (~df["has_email"]).sum(),
                (~df["has_phone"]).sum(),
                (~df["has_mobile"]).sum(),
            ],
        })
        fig_contact = go.Figure()
        fig_contact.add_trace(go.Bar(
            name="Available",
            y=contact_data["field"],
            x=contact_data["has"],
            orientation="h",
            marker_color="#4c9be8",
        ))
        fig_contact.add_trace(go.Bar(
            name="Missing",
            y=contact_data["field"],
            x=contact_data["missing"],
            orientation="h",
            marker_color="#2d3f52",
        ))
        fig_contact.update_layout(
            barmode="stack",
            template="plotly_dark",
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(orientation="h", y=-0.15, x=0, font_size=11),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=220,
        )
        st.plotly_chart(fig_contact, use_container_width=True)

    # Payroll ID coverage
    st.markdown('<div class="section-header" style="margin-top:1rem">Payroll ID Coverage</div>', unsafe_allow_html=True)
    if not df.empty and "payroll_id" in df.columns:
        has_payroll = df["payroll_id"].notna() & (df["payroll_id"] != "")
        pct = has_payroll.mean() * 100
        st.metric("Candidates with Payroll ID", f"{has_payroll.sum():,}", f"{pct:.1f}%")
    else:
        st.info("No payroll data.")

# ── Row 3: Top ranks ──────────────────────────────────────────────────────────────

st.markdown('<div class="section-header">Top 25 Ranks by Candidate Count</div>', unsafe_allow_html=True)

top_ranks = df[df["rank"] != "Unknown"]["rank"].value_counts().head(25).reset_index()
top_ranks.columns = ["rank", "count"]
if not top_ranks.empty:
    fig_rank = px.bar(
        top_ranks,
        x="rank",
        y="count",
        color="count",
        color_continuous_scale="Blues",
        labels={"count": "Candidates", "rank": "Rank"},
        template="plotly_dark",
        text="count",
    )
    fig_rank.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig_rank.update_layout(
        margin=dict(l=0, r=0, t=10, b=120),
        showlegend=False,
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        xaxis=dict(tickangle=-40, tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_rank, use_container_width=True)
else:
    st.info("No rank data to display.")

# ── Row 4: Top cities + Rank × Country heatmap ───────────────────────────────────

col_city, col_heat = st.columns([1, 2])

with col_city:
    st.markdown('<div class="section-header">Top 15 Cities</div>', unsafe_allow_html=True)
    top_cities = df[df["city"] != "Unknown"]["city"].value_counts().head(15).reset_index()
    top_cities.columns = ["city", "count"]
    if not top_cities.empty:
        fig_city = px.bar(
            top_cities.sort_values("count"),
            x="count",
            y="city",
            orientation="h",
            color="count",
            color_continuous_scale="Blues",
            labels={"count": "Candidates", "city": ""},
            template="plotly_dark",
            text="count",
        )
        fig_city.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_city.update_layout(
            margin=dict(l=0, r=50, t=0, b=0),
            showlegend=False,
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=380,
            yaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_city, use_container_width=True)
    else:
        st.info("No city data.")

with col_heat:
    st.markdown('<div class="section-header">Top Ranks × Top Countries (Heatmap)</div>', unsafe_allow_html=True)
    top10_ranks     = df[df["rank"] != "Unknown"]["rank"].value_counts().head(10).index.tolist()
    top10_countries = df[df["country"] != "Unknown"]["country"].value_counts().head(10).index.tolist()
    heat_df = (
        df[df["rank"].isin(top10_ranks) & df["country"].isin(top10_countries)]
        .groupby(["rank", "country"])
        .size()
        .reset_index(name="count")
    )
    if not heat_df.empty:
        pivot = heat_df.pivot(index="rank", columns="country", values="count").fillna(0)
        fig_heat = px.imshow(
            pivot,
            color_continuous_scale="Blues",
            aspect="auto",
            labels=dict(color="Candidates"),
            template="plotly_dark",
            text_auto=True,
        )
        fig_heat.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=380,
            xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
            coloraxis_colorbar=dict(thickness=10),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Insufficient data for heatmap.")

# ── Candidate Data Table ──────────────────────────────────────────────────────────

st.markdown("---")
st.markdown('<div class="section-header">Candidate Records</div>', unsafe_allow_html=True)

search = st.text_input("Search by name, surname, rank, or city", placeholder="e.g. Master, Manila, John…")

display_df = df[["seaman_id", "surname", "name", "rank", "relation", "country", "city", "email", "phone", "mobile", "imported_at"]].copy()
display_df = display_df.rename(columns={
    "seaman_id": "ID",
    "surname":   "Surname",
    "name":      "Name",
    "rank":      "Rank",
    "relation":  "Relation",
    "country":   "Country",
    "city":      "City",
    "email":     "Email",
    "phone":     "Phone",
    "mobile":    "Mobile",
    "imported_at": "Imported",
})

if search:
    mask = (
        display_df["Surname"].str.contains(search, case=False, na=False)
        | display_df["Name"].str.contains(search, case=False, na=False)
        | display_df["Rank"].str.contains(search, case=False, na=False)
        | display_df["City"].str.contains(search, case=False, na=False)
    )
    display_df = display_df[mask]

st.caption(f"Showing {len(display_df):,} records")
st.dataframe(
    display_df,
    use_container_width=True,
    height=400,
    column_config={
        "ID":       st.column_config.NumberColumn("ID", width="small"),
        "Imported": st.column_config.DatetimeColumn("Imported", format="DD MMM YYYY"),
    },
)

# ── Footer ────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption("Candina Group · Seafarer Candidate Dashboard · Data sourced from CrewInspector via Supabase")
