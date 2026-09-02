import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Battery Module Dimensional & FPY Analytics",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UI styling matching standard industrial dashboards
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0056b3;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-pass {
        background-color: #d4edda;
        color: #155724;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 4px;
        text-align: center;
    }
    .status-fail {
        background-color: #f8d7da;
        color: #721c24;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 4px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DATA PROCESSING & RUN NUMBERING ENGINE
# ==========================================
@st.cache_data
def process_dimensional_data(df, spec_limit=3.0):
    """
    Processes raw measurement logs, assigns Run # based on DateTime sequence,
    calculates out-of-spec points per corner, and assigns Module Status.
    """
    # Ensure DateTime parsing
    if 'DateTime' in df.columns:
        df['DateTime'] = pd.to_datetime(df['DateTime'])
    elif 'Date' in df.columns:
        df['DateTime'] = pd.to_datetime(df['Date'])
    else:
        st.error("Data must contain a 'DateTime' or 'Date' column.")
        return None, None

    # Sort strictly chronologically by Part ID and DateTime
    df = df.sort_values(by=['PartID', 'DateTime']).reset_index(drop=True)

    # Assign Run Number dynamically per Part ID
    df['Run_Index'] = df.groupby('PartID').cumcount() + 1
    df['Run #'] = 'Run ' + df['Run_Index'].astype(str)

    # Format Date & Calendar Week (CW)
    df['DateFormatted'] = df['DateTime'].dt.strftime('%d/%m/%Y')
    df['Calendar Week'] = 'CW' + df['DateTime'].dt.isocalendar().week.astype(str)

    # Dimensional Point Columns (FL, FR, RL, RR in X and Y)
    dim_cols = ['FL_X', 'FL_Y', 'FR_X', 'FR_Y', 'RL_X', 'RL_Y', 'RR_X', 'RR_Y']
    for col in dim_cols:
        if col not in df.columns:
            df[col] = 0.0

    # Count out-of-spec points per row (abs deviation > spec_limit)
    out_of_spec_matrix = df[dim_cols].abs() > spec_limit
    df['Out-of-Spec Points'] = out_of_spec_matrix.sum(axis=1)

    # Module Status: PASS if 0 out of spec points, else FAIL
    df['Module Status'] = np.where(df['Out-of-Spec Points'] == 0, 'PASS', 'FAIL')

    # -------------------------------------------------------------
    # SEPARATION FOR FPY: FIRST-RUN ONLY VS FULL HISTORICAL
    # -------------------------------------------------------------
    first_run_df = df[df['Run_Index'] == 1].copy()

    return df, first_run_df

# ==========================================
# SAMPLE DATA GENERATOR (FOR DEMO/TESTING)
# ==========================================
def generate_sample_data():
    np.random.seed(42)
    part_ids = [
        "FO88995390126B152N0000111296112",
        "FO88944960126B153N0000111296112",
        "FO88944960126B153N0000211296112",
        "FO88944960126B154N0000111296112",
        "FO88944960126B154N0000211296112",
        "FO88995390126B156N0000111296112",
        "FO88995390126B156N0000211296112"
    ]
    
    rows = []
    base_date = pd.Timestamp("2026-06-01")
    
    for pid in part_ids:
        # Determine number of runs (1 to 3)
        n_runs = np.random.choice([1, 2, 3], p=[0.4, 0.4, 0.2])
        part_type = "Type S" if "152" in pid or "156" in pid else "Type M"
        
        for run in range(n_runs):
            run_time = base_date + pd.Timedelta(days=np.random.randint(0, 5), hours=run*2)
            
            # Simulate shift values
            fl_x = round(np.random.uniform(-4.5, 2.5), 2)
            fl_y = round(np.random.uniform(-4.5, 2.5), 2)
            fr_x = round(np.random.uniform(-3.5, 1.5), 2)
            fr_y = round(np.random.uniform(-4.0, 1.0), 2)
            rl_x = round(np.random.uniform(-3.5, 3.5), 2)
            rl_y = round(np.random.uniform(-5.8, 1.0), 2)
            rr_x = round(np.random.uniform(-6.0, 1.5), 2)
            rr_y = round(np.random.uniform(-5.0, 2.5), 2)
            
            rows.append({
                "DateTime": run_time,
                "PartID": pid,
                "Type": part_type,
                "FL_X": fl_x, "FL_Y": fl_y,
                "FR_X": fr_x, "FR_Y": fr_y,
                "RL_X": rl_x, "RL_Y": rl_y,
                "RR_X": rr_x, "RR_Y": rr_y
            })
            
    return pd.DataFrame(rows)

# ==========================================
# APP LAYOUT & SIDEBAR CONTROLS
# ==========================================
st.title("🔋 Battery Module Dimensional & FPY Analytics")

st.sidebar.header("⚙️ Configuration & Data Source")
data_source = st.sidebar.radio("Data Source:", ["Use Sample Data", "Upload CSV/Excel"])

if data_source == "Upload CSV/Excel":
    uploaded_file = st.sidebar.file_uploader("Upload File", type=['csv', 'xlsx'])
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    else:
        st.warning("Please upload a file to proceed.")
        st.stop()
else:
    df_raw = generate_sample_data()

spec_limit = st.sidebar.slider("Tolerance Limit (± mm):", min_value=1.0, max_value=5.0, value=3.0, step=0.1)

# Process Data
full_df, first_run_df = process_dimensional_data(df_raw, spec_limit=spec_limit)

# Filter Sidebar Options
st.sidebar.markdown("---")
st.sidebar.header("🔍 Global Filters")
selected_weeks = st.sidebar.multiselect("Calendar Week:", options=sorted(full_df['Calendar Week'].unique()), default=sorted(full_df['Calendar Week'].unique()))
selected_types = st.sidebar.multiselect("Module Type:", options=sorted(full_df['Type'].unique()), default=sorted(full_df['Type'].unique()))

# Filter datasets
filtered_full = full_df[(full_df['Calendar Week'].isin(selected_weeks)) & (full_df['Type'].isin(selected_types))]
filtered_first = first_run_df[(first_run_df['Calendar Week'].isin(selected_weeks)) & (first_run_df['Type'].isin(selected_types))]

# Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📊 Weekly FPY Breakdown & KPIs", "🎯 Vector Shift Visualizer", "📋 Run History & Inspection Table"])

# ==========================================
# TAB 1: WEEKLY FPY BREAKDOWN & KPIS
# ==========================================
with tab1:
    st.markdown("### 📈 Quality Metrics (Calculated STRICTLY on First-Run / Run 1)")
    
    total_first_units = len(filtered_first)
    passed_first_units = len(filtered_first[filtered_first['Module Status'] == 'PASS'])
    failed_first_units = total_first_units - passed_first_units
    fpy_rate = (passed_first_units / total_first_units * 100) if total_first_units > 0 else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("First-Run Production", f"{total_first_units} Units")
    col2.metric("First-Pass Yield (FPY)", f"{fpy_rate:.2f}%")
    col3.metric("Passed (Run 1)", f"{passed_first_units}", delta_color="normal")
    col4.metric("Failed (Run 1)", f"{failed_first_units}", delta="-Failed", delta_color="inverse")

    st.markdown("---")
    st.subheader("Weekly FPY Breakdown & Volume Trend")
    
    # Weekly aggregation based strictly on First-Run
    weekly_fpy = filtered_first.groupby('Calendar Week').agg(
        Total_Units=('PartID', 'count'),
        Pass_Units=('Module Status', lambda x: (x == 'PASS').sum()),
        Fail_Units=('Module Status', lambda x: (x == 'FAIL').sum())
    ).reset_index()
    
    weekly_fpy['FPY_%'] = (weekly_fpy['Pass_Units'] / weekly_fpy['Total_Units']) * 100

    fig_fpy = go.Figure()
    fig_fpy.add_trace(go.Bar(
        x=weekly_fpy['Calendar Week'], y=weekly_fpy['Pass_Units'], name='PASS (Run 1)', marker_color='#28a745'
    ))
    fig_fpy.add_trace(go.Bar(
        x=weekly_fpy['Calendar Week'], y=weekly_fpy['Fail_Units'], name='FAIL (Run 1)', marker_color='#dc3545'
    ))
    fig_fpy.add_trace(go.Scatter(
        x=weekly_fpy['Calendar Week'], y=weekly_fpy['FPY_%'], name='FPY %', yaxis='y2',
        mode='lines+markers+text', text=weekly_fpy['FPY_%'].round(1).astype(str) + '%',
        textposition='top center', line=dict(color='#007bff', width=3)
    ))

    fig_fpy.update_layout(
        barmode='stack',
        title="Weekly First-Pass Yield (FPY) and Defect Ratio",
        xaxis=dict(title="Calendar Week"),
        yaxis=dict(title="Volume (Modules)"),
        yaxis2=dict(title="FPY (%)", overlaying='y', side='right', range=[0, 110]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_fpy, use_container_width=True)

# ==========================================
# TAB 2: VECTOR SHIFT VISUALIZER
# ==========================================
with tab2:
    st.markdown("### 🎯 Vector Shift Visualizer per Module Run")
    
    part_list = filtered_full['PartID'].unique()
    if len(part_list) == 0:
        st.warning("No parts match the selected filters.")
    else:
        col_sel1, col_sel2 = st.columns([2, 1])
        with col_sel1:
            selected_part = st.selectbox("Select Part ID (Module):", options=part_list)
        
        # Filter runs available for the selected part
        part_runs = filtered_full[filtered_full['PartID'] == selected_part]
        
        with col_sel2:
            selected_run = st.selectbox("Select Run Number:", options=part_runs['Run #'].unique())

        selected_row = part_runs[part_runs['Run #'] == selected_run].iloc[0]

        st.info(f"Showing **{selected_part}** | **{selected_run}** | Date: **{selected_row['DateFormatted']}** | Status: **{selected_row['Module Status']}**")

        # Plot Vector Displacements
        fig_vector = go.Figure()
        corners = {'FL': (0, 1), 'FR': (1, 1), 'RL': (0, 0), 'RR': (1, 0)}
        
        for corner, pos in corners.items():
            dx = selected_row[f'{corner}_X']
            dy = selected_row[f'{corner}_Y']
            
            is_out = abs(dx) > spec_limit or abs(dy) > spec_limit
            color = '#dc3545' if is_out else '#28a745'
            
            # Nominal point
            fig_vector.add_trace(go.Scatter(
                x=[pos[0]], y=[pos[1]], mode='markers+text',
                text=[f"{corner} (Nominal)"], textposition="top center",
                marker=dict(size=12, color='gray', symbol='cross'),
                showlegend=False
            ))
            
            # Measured vector line
            fig_vector.add_trace(go.Scatter(
                x=[pos[0], pos[0] + dx/10], y=[pos[1], pos[1] + dy/10],
                mode='lines+markers',
                line=dict(color=color, width=3),
                name=f"{corner}: ΔX={dx:.2f}, ΔY={dy:.2f}"
            ))

        fig_vector.update_layout(
            title=f"Dimensional Shift Vectors ({selected_run}) - Tolerance Envelope: ±{spec_limit}mm",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=500
        )
        st.plotly_chart(fig_vector, use_container_width=True)

# ==========================================
# TAB 3: RUN HISTORY & INSPECTION TABLE
# ==========================================
with tab3:
    st.markdown("### 📋 Complete Measurement Log & Run History")
    st.caption("Displays all measurement runs including initial checks (Run 1) and subsequent re-runs / re-work.")

    # Select columns to display matching the requested format exactly
    display_cols = [
        'DateFormatted', 'Calendar Week', 'PartID', 'Type', 'Run #',
        'FL_X', 'FL_Y', 'FR_X', 'FR_Y', 'RL_X', 'RL_Y', 'RR_X', 'RR_Y',
        'Out-of-Spec Points', 'Module Status'
    ]
    
    table_df = filtered_full[display_cols].copy()
    table_df.rename(columns={'DateFormatted': 'Date', 'PartID': 'Part ID (Module)'}, inplace=True)

    # Apply Highlighting for Out of Spec Points and Status
    def highlight_cells(val):
        if isinstance(val, (int, float)):
            if abs(val) > spec_limit:
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
        return ''

    def highlight_status(val):
        if val == 'FAIL':
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
        elif val == 'PASS':
            return 'background-color: #d4edda; color: #155724; font-weight: bold;'
        return ''

    # Apply Pandas Styler
    styled_df = table_df.style\
        .applymap(highlight_cells, subset=['FL_X', 'FL_Y', 'FR_X', 'FR_Y', 'RL_X', 'RL_Y', 'RR_X', 'RR_Y'])\
        .applymap(highlight_status, subset=['Module Status'])\
        .format({'FL_X': '{:.2f}', 'FL_Y': '{:.2f}', 'FR_X': '{:.2f}', 'FR_Y': '{:.2f}', 
                 'RL_X': '{:.2f}', 'RL_Y': '{:.2f}', 'RR_X': '{:.2f}', 'RR_Y': '{:.2f}'})

    st.dataframe(styled_df, use_container_width=True, height=600)
    
    # Download Button
    csv = table_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Full Run History (CSV)",
        data=csv,
        file_name="battery_module_run_history.csv",
        mime="text/csv"
    )
