import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import math

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTADO GLOBAL
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Battery Dimensional Analytics",
    page_icon="🔋",
    layout="wide"
)

if "selected_part_id" not in st.session_state:
    st.session_state["selected_part_id"] = None

st.title("🔋 Battery Dimensional Analytics & Quality Engine")

# -----------------------------------------------------------------------------
# NOMINALES Y TOLERANCIAS GEOMÉTRICAS
# -----------------------------------------------------------------------------
NOMINALS = {
    "TYPE S": {
        "FL_X": 2290.48, "FL_Y": -559.40,
        "FR_X": 2290.48, "FR_Y": 558.90,
        "RL_X": 997.28,  "RL_Y": -559.40,
        "RR_X": 997.28,  "RR_Y": 511.10
    },
    "TYPE M": {
        "FL_X": 2290.48, "FL_Y": -559.40,
        "FR_X": 2290.48, "FR_Y": 558.90,
        "RL_X": 609.31,  "RL_Y": -583.30,
        "RR_X": 609.31,  "RR_Y": 535.00
    }
}

MAX_DIAG_DELTA_TOL = 1.5
ANGULAR_DEV_TOL = 0.15
DIM_DELTA_TOL = 0.8
POINT_DEV_TOL = 3.0  # Umbral para resaltado fuera de especificación por punto

def parse_english_datetime(date_str):
    if pd.isna(date_str):
        return pd.NaT
    clean_str = str(date_str).replace('\n', ' ').replace('\r', ' ').strip()
    try:
        return pd.to_datetime(clean_str, errors='coerce')
    except Exception:
        return pd.NaT

def determine_battery_type(part_id, feature_name):
    p_id = str(part_id).upper()
    f_name = str(feature_name).upper()
    if "_DJ" in p_id or "_DJ" in f_name or "_M" in p_id or p_id.endswith("M"):
        return "Type M"
    return "Type S"

def extract_corner_index(feature_name, battery_type):
    f_name = str(feature_name).lower().strip()
    
    if "72_l0324_aa" in f_name or "fl" in f_name or "c1" in f_name:
        return "FL"
    if "72_r0301_aa" in f_name or "fr" in f_name or "c2" in f_name:
        return "FR"
    
    if battery_type == "Type M":
        if "72_l0324_dj" in f_name or "rl" in f_name or "c3" in f_name:
            return "RL"
        if "72_r0301_dj" in f_name or "rr" in f_name or "c4" in f_name:
            return "RR"
    else:
        if "72_l0324_da" in f_name or "rl" in f_name or "c3" in f_name:
            return "RL"
        if "72_r0302_da" in f_name or "rr" in f_name or "c4" in f_name:
            return "RR"
            
    return None

def calculate_corner_angle(xA, yA, xB, yB, xC, yC):
    vAB_x, vAB_y = xB - xA, yB - yA
    vAC_x, vAC_y = xC - xA, yC - yA
    
    dotProduct = (vAB_x * vAC_x) + (vAB_y * vAC_y)
    magAB = math.sqrt(vAB_x**2 + vAB_y**2)
    magAC = math.sqrt(vAC_x**2 + vAC_y**2)
    
    if magAB == 0 or magAC == 0:
        return 0.0
        
    cosTheta = dotProduct / (magAB * magAC)
    cosTheta = max(-1.0, min(1.0, cosTheta))
    
    return math.degrees(math.acos(cosTheta))

@st.cache_data
def process_data(file):
    if file.name.endswith(('.xlsx', '.xls')):
        df_raw = pd.read_excel(file, header=None)
    else:
        df_raw = pd.read_csv(file, header=None)
    
    header_idx = 0
    for idx in range(min(15, len(df_raw))):
        row_values = [str(val).lower() for val in df_raw.iloc[idx].values if pd.notna(val)]
        row_combined = " ".join(row_values)
        if "part id" in row_combined and ("feature" in row_combined or "time" in row_combined):
            header_idx = idx
            break

    file.seek(0)
    if file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file, skiprows=header_idx)
    else:
        df = pd.read_csv(file, skiprows=header_idx)
        
    df.columns = [str(col).strip() for col in df.columns]
    
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        if "time" in c_lower or "date" in c_lower: col_map[col] = "Time"
        elif "part" in c_lower: col_map[col] = "PartID"
        elif "feature" in c_lower: col_map[col] = "FeatureName"
        elif c_lower in ["x deviation", "valx", "x"]: col_map[col] = "ValX"
        elif c_lower in ["y deviation", "valy", "y"]: col_map[col] = "ValY"
        elif c_lower in ["z deviation", "valz", "z"]: col_map[col] = "ValZ"
        
    df = df.rename(columns=col_map)
    df = df.dropna(subset=["PartID"]).copy()
    
    df["DateTime"] = df["Time"].apply(parse_english_datetime) if "Time" in df.columns else pd.Timestamp.now()
    df["ValX"] = pd.to_numeric(df.get("ValX", 0.0), errors="coerce").fillna(0.0)
    df["ValY"] = pd.to_numeric(df.get("ValY", 0.0), errors="coerce").fillna(0.0)
    df["ValZ"] = pd.to_numeric(df.get("ValZ", 0.0), errors="coerce").fillna(0.0)
    
    df["BatteryType"] = df.apply(lambda r: determine_battery_type(r["PartID"], r.get("FeatureName", "")), axis=1)
    df["Corner"] = df.apply(lambda r: extract_corner_index(r.get("FeatureName", ""), r["BatteryType"]), axis=1)
    df["DateFormatted"] = df["DateTime"].dt.strftime('%d/%m/%Y').fillna("Unknown")
    df["CW"] = df["DateTime"].apply(lambda dt: f"CW{dt.isocalendar().week:02d}" if pd.notna(dt) else "CW00")
    
    df = df.sort_values("DateTime")
    
    modules = []
    part_run_counter = {}
    
    for (d_date, p_id), group in df.groupby(["DateFormatted", "PartID"], sort=False):
        b_type = group["BatteryType"].iloc[0]
        cw = group["CW"].iloc[0]
        dt_val = group["DateTime"].iloc[0]
        
        # Conteo de corridas por módulo (Run #)
        part_run_counter[p_id] = part_run_counter.get(p_id, 0) + 1
        run_label = f"Run {part_run_counter[p_id]}"
        
        fl_row, fr_row = group[group["Corner"] == "FL"], group[group["Corner"] == "FR"]
        rl_row, rr_row = group[group["Corner"] == "RL"], group[group["Corner"] == "RR"]
        
        fl_dx = fl_row["ValX"].values[0] if not fl_row.empty else 0.0
        fl_dy = fl_row["ValY"].values[0] if not fl_row.empty else 0.0
        fr_dx = fr_row["ValX"].values[0] if not fr_row.empty else 0.0
        fr_dy = fr_row["ValY"].values[0] if not fr_row.empty else 0.0
        rl_dx = rl_row["ValX"].values[0] if not rl_row.empty else 0.0
        rl_dy = rl_row["ValY"].values[0] if not rl_row.empty else 0.0
        rr_dx = rr_row["ValX"].values[0] if not rr_row.empty else 0.0
        rr_dy = rr_row["ValY"].values[0] if not rr_row.empty else 0.0
        
        # Conteo de puntos fuera de especificación (Valores absolutos mayores al umbral)
        deviations = [fl_dx, fl_dy, fr_dx, fr_dy, rl_dx, rl_dy, rr_dx, rr_dy]
        out_of_spec_pts = sum(1 for dev in deviations if abs(dev) >= POINT_DEV_TOL)
        
        nom_key = "TYPE M" if b_type == "Type M" else "TYPE S"
        nom = NOMINALS[nom_key]
        
        d1_nom = math.sqrt((nom["RR_X"] - nom["FL_X"])**2 + (nom["RR_Y"] - nom["FL_Y"])**2)
        d2_nom = math.sqrt((nom["RL_X"] - nom["FR_X"])**2 + (nom["RL_Y"] - nom["FR_Y"])**2)
        w_top_nom = math.sqrt((nom["FR_X"] - nom["FL_X"])**2 + (nom["FR_Y"] - nom["FL_Y"])**2)
        w_bot_nom = math.sqrt((nom["RR_X"] - nom["RL_X"])**2 + (nom["RR_Y"] - nom["RL_Y"])**2)
        l_left_nom = math.sqrt((nom["RL_X"] - nom["FL_X"])**2 + (nom["RL_Y"] - nom["FL_Y"])**2)
        l_right_nom = math.sqrt((nom["RR_X"] - nom["FR_X"])**2 + (nom["RR_Y"] - nom["FR_Y"])**2)
        angle_fl_nom = calculate_corner_angle(nom["FL_X"], nom["FL_Y"], nom["FR_X"], nom["FR_Y"], nom["RL_X"], nom["RL_Y"])
        
        fl_x, fl_y = nom["FL_X"] + fl_dx, nom["FL_Y"] + fl_dy
        fr_x, fr_y = nom["FR_X"] + fr_dx, nom["FR_Y"] + fr_dy
        rl_x, rl_y = nom["RL_X"] + rl_dx, nom["RL_Y"] + rl_dy
        rr_x, rr_y = nom["RR_X"] + rr_dx, nom["RR_Y"] + rr_dy
        
        d1_act = math.sqrt((rr_x - fl_x)**2 + (rr_y - fl_y)**2)
        d2_act = math.sqrt((rl_x - fr_x)**2 + (rl_y - fr_y)**2)
        w_top_act = math.sqrt((fr_x - fl_x)**2 + (fr_y - fl_y)**2)
        w_bot_act = math.sqrt((rr_x - rl_x)**2 + (rr_y - rl_y)**2)
        l_left_act = math.sqrt((rl_x - fl_x)**2 + (rl_y - fl_y)**2)
        l_right_act = math.sqrt((rr_x - fr_x)**2 + (rr_y - fr_y)**2)
        angle_fl_act = calculate_corner_angle(fl_x, fl_y, fr_x, fr_y, rl_x, rl_y)
        
        delta_diags = abs((d1_act - d2_act) - (d1_nom - d2_nom))
        diff_ancho = (w_top_act - w_top_nom) - (w_bot_act - w_bot_nom)
        diff_largo = (l_left_act - l_left_nom) - (l_right_act - l_right_nom)
        angle_fl_dev = angle_fl_act - angle_fl_nom
        
        if delta_diags > MAX_DIAG_DELTA_TOL or out_of_spec_pts > 0:
            status_str = "DEFORMED"
            overall_pass = "FAIL"
            if abs(angle_fl_dev) > ANGULAR_DEV_TOL and abs(diff_ancho) < DIM_DELTA_TOL:
                detail_str = f"Parallelogram Distortion (Tilt: {angle_fl_dev:+.2f}°)"
            elif abs(diff_ancho) >= DIM_DELTA_TOL:
                detail_str = f"Trapezoidal Width Var (Delta: {diff_ancho:+.2f} mm)"
            elif abs(diff_largo) >= DIM_DELTA_TOL:
                detail_str = f"Trapezoidal Length Var (Delta: {diff_largo:+.2f} mm)"
            else:
                detail_str = f"Out-of-Spec / Asymmetry (Diag Delta: {delta_diags:.2f} mm)"
        else:
            status_str = "SQUARE OK"
            overall_pass = "PASS"
            detail_str = "Within Tolerance"
            
        modules.append({
            "DateTime": dt_val, "Date": d_date, "Calendar Week": cw, "Part ID (Module)": p_id, 
            "Type": b_type, "Run #": run_label,
            "FL_X": fl_dx, "FL_Y": fl_dy, "FR_X": fr_dx, "FR_Y": fr_dy,
            "RL_X": rl_dx, "RL_Y": rl_dy, "RR_X": rr_dx, "RR_Y": rr_dy,
            "Out-of-Spec Points": out_of_spec_pts, "Module Status": overall_pass,
            "Diag1_Act": d1_act, "Diag2_Act": d2_act, "DeltaDiagonals": delta_diags,
            "WidthDelta": diff_ancho, "LengthDelta": diff_largo, "AngleDevFL": angle_fl_dev,
            "SquareStatus": status_str, "RootCause": detail_str
        })
            
    return df, pd.DataFrame(modules)

# -----------------------------------------------------------------------------
# INTERFAZ Y NAVEGACIÓN STREAMLIT
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Carga de Datos y Filtros")
uploaded_file = st.sidebar.file_uploader("Cargar reporte Raw (CSV o Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    df_raw, df_modules = process_data(uploaded_file)
    
    if df_modules.empty:
        st.error("No se encontraron registros válidos.")
    else:
        cw_list = sorted(df_modules["Calendar Week"].unique())
        selected_cw = st.sidebar.multiselect("Calendar Week (CW)", options=cw_list, default=cw_list)
        type_list = sorted(df_modules["Type"].unique())
        selected_type = st.sidebar.multiselect("Tipo de Batería", options=type_list, default=type_list)
        
        df_filtered = df_modules[
            (df_modules["Calendar Week"].isin(selected_cw)) & 
            (df_modules["Type"].isin(selected_type))
        ]
        
        tab1, tab2, tab3 = st.tabs([
            "📊 Executive Quality Dashboard", 
            "📐 Vector Shift Visualizer", 
            "🔍 Squareness & Inspection Table"
        ])
        
        # ---------------------------------------------------------------------
        # TAB 1: EXECUTIVE QUALITY DASHBOARD (REPLICANDO LA TABLA Y GRÁFICOS)
        # ---------------------------------------------------------------------
        with tab1:
            st.subheader("📊 Executive Quality & Dimensional Inspection Log")
            
            total_mod = len(df_filtered)
            pass_mod = len(df_filtered[df_filtered["Module Status"] == "PASS"])
            fail_mod = len(df_filtered[df_filtered["Module Status"] == "FAIL"])
            fpy_global = (pass_mod / total_mod * 100) if total_mod > 0 else 0.0
            
            # 1. RESUMEN EJECUTIVO KPI
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Runs", f"{total_mod}")
            k2.metric("Passed (OK)", f"{pass_mod}")
            k3.metric("Failed (NOK)", f"{fail_mod}")
            k4.metric("First-Pass Yield (FPY)", f"{fpy_global:.1f}%")
            
            st.divider()

            # 2. TABLA PRINCIPAL (ESTILO MACRO DE EXCEL EN LA IMAGEN)
            st.markdown("### 📋 Dimensional Measurement Log")
            st.caption("Resaltado automático de desviaciones extremas (<-3.00 mm o >3.00 mm) y estatus del módulo.")

            main_display_cols = [
                "Date", "Calendar Week", "Part ID (Module)", "Type", "Run #",
                "FL_X", "FL_Y", "FR_X", "FR_Y", "RL_X", "RL_Y", "RR_X", "RR_Y",
                "Out-of-Spec Points", "Module Status"
            ]
            
            df_table = df_filtered[main_display_cols].copy()

            def style_excel_table(val):
                if val == "FAIL":
                    return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
                if val == "PASS":
                    return 'background-color: #d4edda; color: #155724; font-weight: bold;'
                if isinstance(val, (int, float)):
                    if abs(val) >= POINT_DEV_TOL and val != 0:
                        return 'color: #dc3545; font-weight: bold;'
                return ''

            format_dict = {
                "FL_X": "{:.2f}", "FL_Y": "{:.2f}",
                "FR_X": "{:.2f}", "FR_Y": "{:.2f}",
                "RL_X": "{:.2f}", "RL_Y": "{:.2f}",
                "RR_X": "{:.2f}", "RR_Y": "{:.2f}",
                "Out-of-Spec Points": "{:d}"
            }

            st.dataframe(
                df_table.style.map(style_excel_table).format(format_dict),
                use_container_width=True,
                hide_index=True,
                height=480
            )

            st.divider()

            # 3. GRÁFICO DE BARRAS APILADAS Y DESGLOSE SEMANAL
            col_chart, col_table = st.columns([1, 1], gap="large")
            
            cw_summary = df_filtered.groupby("Calendar Week").agg(
                Total=('Part ID (Module)', 'count'),
                Passed=('Module Status', lambda x: (x == 'PASS').sum()),
                Failed=('Module Status', lambda x: (x == 'FAIL').sum())
            ).reset_index()
            
            cw_summary["PassPct"] = (cw_summary["Passed"] / cw_summary["Total"]) * 100
            cw_summary["FailPct"] = (cw_summary["Failed"] / cw_summary["Total"]) * 100

            with col_chart:
                st.markdown("### 📈 Weekly First-Pass Yield Trend (%)")
                
                fig_stacked = go.Figure()
                fig_stacked.add_trace(go.Bar(
                    x=cw_summary["Calendar Week"], y=cw_summary["PassPct"],
                    name="Passed (OK)", marker_color="#2E7D32"
                ))
                fig_stacked.add_trace(go.Bar(
                    x=cw_summary["Calendar Week"], y=cw_summary["FailPct"],
                    name="Failed (NOK)", marker_color="#C62828"
                ))
                
                fig_stacked.add_hline(
                    y=fpy_global, line_dash="dash", line_color="#FFB300", line_width=2.5,
                    annotation_text=f"Total FPY: {fpy_global:.1f}%", annotation_position="top right"
                )

                fig_stacked.update_layout(
                    barmode='stack', yaxis_title="Percentage (%)", yaxis=dict(range=[0, 105]),
                    height=380, margin=dict(l=20, r=20, t=30, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_stacked, use_container_width=True)

            with col_table:
                st.markdown("### 🗓️ WEEKLY FPY BREAKDOWN")
                display_cw = cw_summary.rename(columns={
                    "Calendar Week": "Calendar Week", "Total": "Total Runs",
                    "Passed": "Passed (OK)", "Failed": "Failed (NOK)", "PassPct": "Pass Rate (%)"
                })[["Calendar Week", "Total Runs", "Passed (OK)", "Failed (NOK)", "Pass Rate (%)"]]
                
                st.dataframe(
                    display_cw,
                    use_container_width=True,
                    hide_index=True,
                    height=380,
                    column_config={
                        "Pass Rate (%)": st.column_config.ProgressColumn(
                            "Pass Rate (%)", format="%.1f%%", min_value=0, max_value=100
                        )
                    }
                )

        # ---------------------------------------------------------------------
        # TAB 2: VECTOR SHIFT VISUALIZER
        # ---------------------------------------------------------------------
        with tab2:
            st.subheader("📐 Vector Shift Visualizer")
            
            all_parts = list(df_filtered["Part ID (Module)"].unique())
            default_idx = 0
            if st.session_state["selected_part_id"] in all_parts:
                default_idx = all_parts.index(st.session_state["selected_part_id"])
            
            col_sel, col_scale = st.columns([2, 1])
            selected_part = col_sel.selectbox("Seleccionar Módulo (Part ID):", all_parts, index=default_idx)
            scale = col_scale.slider("Factor de Magnificación:", min_value=1, max_value=50, value=20)
            
            row = df_filtered[df_filtered["Part ID (Module)"] == selected_part].iloc[0]
            
            st.markdown("---")
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            
            pass_color = "🟢 PASS" if row["Module Status"] == "PASS" else "🔴 FAIL"
            square_color = "🟢 OK" if row["SquareStatus"] == "SQUARE OK" else "🔴 DEFORMED"
            
            m1.metric("Overall Result", pass_color)
            m2.metric("Squareness", square_color)
            m3.metric("Type", row["Type"])
            m4.metric("Calendar Week", row["Calendar Week"])
            m5.metric("Date", str(row["Date"]))
            m6.metric("Root Cause", row["RootCause"])
            st.markdown("---")
            
            nom_key = "TYPE M" if row["Type"] == "Type M" else "TYPE S"
            nom = NOMINALS[nom_key]
            
            x_nom = [nom["RL_X"], nom["RR_X"], nom["FR_X"], nom["FL_X"], nom["RL_X"]]
            y_nom = [nom["RL_Y"], nom["RR_Y"], nom["FR_Y"], nom["FL_Y"], nom["RL_Y"]]
            
            x_real = [
                nom["RL_X"] + row["RL_X"] * scale,
                nom["RR_X"] + row["RR_X"] * scale,
                nom["FR_X"] + row["FR_X"] * scale,
                nom["FL_X"] + row["FL_X"] * scale,
                nom["RL_X"] + row["RL_X"] * scale
            ]
            y_real = [
                nom["RL_Y"] + row["RL_Y"] * scale,
                nom["RR_Y"] + row["RR_Y"] * scale,
                nom["FR_Y"] + row["FR_Y"] * scale,
                nom["FL_Y"] + row["FL_Y"] * scale,
                nom["RL_Y"] + row["RL_Y"] * scale
            ]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_nom, y=y_nom, mode='lines', name='Nominal Fixture', line=dict(color='gray', dash='dash')))
            
            color = 'red' if row["Module Status"] == "FAIL" else 'green'
            fig.add_trace(go.Scatter(x=x_real, y=y_real, mode='lines+markers', name=f'Medido ({scale}x Scale)', line=dict(color=color, width=3)))
            
            fig.update_layout(
                title=f"Módulo: {row['Part ID (Module)']} ({row['Type']})",
                xaxis_title="Eje X Fixture (mm)", yaxis_title="Eje Y Fixture (mm)",
                yaxis=dict(scaleanchor="x", scaleratio=1), width=800, height=700
            )
            st.plotly_chart(fig, use_container_width=True)

        # ---------------------------------------------------------------------
        # TAB 3: SQUARENESS & INSPECTION TABLE
        # ---------------------------------------------------------------------
        with tab3:
            st.subheader("🔍 Squareness & Geometric Inspection Table")
            st.info("💡 **Tip:** Selecciona cualquier fila en la tabla para cargar automáticamente ese módulo en el **Vector Shift Visualizer**.")
            
            def highlight_deformed(val):
                if val == "DEFORMED" or val == "FAIL": 
                    return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold;'
                if val == "SQUARE OK" or val == "PASS": 
                    return 'background-color: #c6efce; color: #006100;'
                return ''

            display_df = df_filtered[[
                "Part ID (Module)", "Module Status", "SquareStatus", "Type", "Calendar Week", "Date",
                "Diag1_Act", "Diag2_Act", "DeltaDiagonals", 
                "WidthDelta", "LengthDelta", "AngleDevFL", "RootCause"
            ]]

            selection = st.dataframe(
                display_df.style.map(highlight_deformed, subset=["SquareStatus", "Module Status"])
                .format({
                    "Diag1_Act": "{:.2f}", "Diag2_Act": "{:.2f}",
                    "DeltaDiagonals": "{:.2f}", "WidthDelta": "{:.2f}",
                    "LengthDelta": "{:.2f}", "AngleDevFL": "{:+.2f}°"
                }),
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            
            selected_rows = selection.get("selection", {}).get("rows", [])
            if selected_rows:
                selected_index = selected_rows[0]
                part_selected = display_df.iloc[selected_index]["Part ID (Module)"]
                st.session_state["selected_part_id"] = part_selected
                st.success(f"🎯 Módulo seleccionado: **{part_selected}**. Ve a la pestaña **Vector Shift Visualizer** para inspeccionarlo.")

            st.divider()

            st.subheader("📄 Detailed Measurement Log (Raw Features)")
            filtered_part_ids = df_filtered["Part ID (Module)"].unique()
            df_raw_filtered = df_raw[df_raw["PartID"].isin(filtered_part_ids)].copy()
            
            if "DateTime" in df_raw_filtered.columns:
                df_raw_filtered["DateTime"] = df_raw_filtered["DateTime"].dt.strftime('%Y-%m-%d %H:%M:%S')

            st.dataframe(
                df_raw_filtered,
                use_container_width=True,
                hide_index=True
            )
