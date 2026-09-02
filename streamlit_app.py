import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Battery Dimensional Analytics",
    page_icon="🔋",
    layout="wide"
)

st.title("🔋 Battery Dimensional Analytics & Inspection Engine")
st.markdown("Herramienta avanzada para análisis de distorsión geométrica, Vector Shift y FPY.")

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES (ETL Y GEOMETRÍA)
# -----------------------------------------------------------------------------

def parse_english_datetime(date_str):
    """Parsea fechas en formato 'Aug 19, 2026 7:16pm' limpiando saltos de línea."""
    if pd.isna(date_str):
        return pd.NaT
    clean_str = str(date_str).replace('\n', ' ').replace('\r', ' ').strip()
    
    # Intentar parseo automático con pandas
    try:
        return pd.to_datetime(clean_str, format='%b %d, %Y %I:%M%p', errors='coerce')
    except Exception:
        return pd.to_datetime(clean_str, errors='coerce')

def determine_battery_type(part_id, feature_name):
    p_id = str(part_id).upper()
    f_name = str(feature_name).upper()
    if "_DJ" in p_id or "_DJ" in f_name or "_M" in p_id or p_id.endswith("M"):
        return "Type M"
    return "Type S"

def extract_corner_index(feature_name, battery_type):
    f_name = str(feature_name).lower().strip()
    
    # Esquinas Frontales (C1=FL, C2=FR)
    if "72_l0324_aa" in f_name or "fl" in f_name or "c1" in f_name:
        return "FL"
    if "72_r0301_aa" in f_name or "fr" in f_name or "c2" in f_name:
        return "FR"
    
    # Esquinas Traseras (C3=RL, C4=RR) según Tipo de Batería
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

@st.cache_data
def process_data(file):
    # Detectar encabezados (pueden estar en la fila 0, 1 o 2)
    df_raw = pd.read_excel(file) if file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(file)
    
    # Buscar la fila que contiene las columnas clave
    header_idx = None
    for idx, row in df_raw.iterrows():
        row_str = " ".join(row.astype(str)).lower()
        if "part id" in row_str and "feature" in row_str:
            header_idx = idx
            break
            
    if header_idx is not None:
        if file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file, skiprows=header_idx+1)
        else:
            df = pd.read_csv(file, skiprows=header_idx+1)
    else:
        df = df_raw.copy()
        
    # Limpiar nombres de columnas
    df.columns = [str(col).strip() for col in df.columns]
    
    # Mapeo flexible de columnas
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        if "time" in c_lower or "date" in c_lower: col_map[col] = "Time"
        elif "part" in c_lower: col_map[col] = "PartID"
        elif "feature" in c_lower: col_map[col] = "FeatureName"
        elif c_lower == "x deviation" or c_lower == "valx" or c_lower == "x": col_map[col] = "ValX"
        elif c_lower == "y deviation" or c_lower == "valy" or c_lower == "y": col_map[col] = "ValY"
        elif c_lower == "z deviation" or c_lower == "valz" or c_lower == "z": col_map[col] = "ValZ"
        elif "x lower" in c_lower: col_map[col] = "X_Low"
        elif "x upper" in c_lower: col_map[col] = "X_High"
        elif "y lower" in c_lower: col_map[col] = "Y_Low"
        elif "y upper" in c_lower: col_map[col] = "Y_High"
        
    df = df.rename(columns=col_map)
    
    # Parseo de fechas y números
    df["DateTime"] = df["Time"].apply(parse_english_datetime)
    df = df.dropna(subset=["DateTime", "PartID"]).copy()
    
    df["ValX"] = pd.to_numeric(df["ValX"], errors="coerce").fillna(0.0)
    df["ValY"] = pd.to_numeric(df["ValY"], errors="coerce").fillna(0.0)
    df["ValZ"] = pd.to_numeric(df["ValZ"], errors="coerce").fillna(0.0)
    
    x_low = df["X_Low"].iloc[0] if "X_Low" in df.columns else -3.0
    x_high = df["X_High"].iloc[0] if "X_High" in df.columns else 3.0
    y_low = df["Y_Low"].iloc[0] if "Y_Low" in df.columns else -3.0
    y_high = df["Y_High"].iloc[0] if "Y_High" in df.columns else 3.0
    
    df["OutOfSpec"] = (df["ValX"] < x_low) | (df["ValX"] > x_high) | \
                      (df["ValY"] < y_low) | (df["ValY"] > y_high)
                      
    df["BatteryType"] = df.apply(lambda r: determine_battery_type(r["PartID"], r["FeatureName"]), axis=1)
    df["Corner"] = df.apply(lambda r: extract_corner_index(r["FeatureName"], r["BatteryType"]), axis=1)
    df["DateFormatted"] = df["DateTime"].dt.strftime('%Y-%m-%d')
    df["CW"] = "CW" + df["DateTime"].dt.isocalendar().week.map("{:02d}".format)
    
    # Agrupar por Módulo y Run
    df = df.sort_values("DateTime")
    
    modules = []
    for (d_date, p_id), group in df.groupby(["DateFormatted", "PartID"]):
        # Lógica para detectar Runs (re-mediciones)
        corner_history = []
        run_count = 1
        
        for idx, row in group.iterrows():
            c_name = row["Corner"]
            if c_name in corner_history:
                run_count += 1
                corner_history = [c_name]
            else:
                corner_history.append(c_name)
                
            b_type = row["BatteryType"]
            cw = row["CW"]
            dt_val = row["DateTime"]
            
            # Buscar datos por esquina
            fl_row = group[group["Corner"] == "FL"]
            fr_row = group[group["Corner"] == "FR"]
            rl_row = group[group["Corner"] == "RL"]
            rr_row = group[group["Corner"] == "RR"]
            
            fl_x = fl_row["ValX"].values[0] if not fl_row.empty else 0.0
            fl_y = fl_row["ValY"].values[0] if not fl_row.empty else 0.0
            fr_x = fr_row["ValX"].values[0] if not fr_row.empty else 0.0
            fr_y = fr_row["ValY"].values[0] if not fr_row.empty else 0.0
            rl_x = rl_row["ValX"].values[0] if not rl_row.empty else 0.0
            rl_y = rl_row["ValY"].values[0] if not rl_row.empty else 0.0
            rr_x = rr_row["ValX"].values[0] if not rr_row.empty else 0.0
            rr_y = rr_row["ValY"].values[0] if not rr_row.empty else 0.0
            
            is_fail = group["OutOfSpec"].any()
            
            modules.append({
                "DateTime": dt_val,
                "Date": d_date,
                "CW": cw,
                "PartID": p_id,
                "BatteryType": b_type,
                "Run": f"Run {run_count}",
                "RunNum": run_count,
                "FL_X": fl_x, "FL_Y": fl_y, "FL_Shift": np.hypot(fl_x, fl_y),
                "FR_X": fr_x, "FR_Y": fr_y, "FR_Shift": np.hypot(fr_x, fr_y),
                "RL_X": rl_x, "RL_Y": rl_y, "RL_Shift": np.hypot(rl_x, rl_y),
                "RR_X": rr_x, "RR_Y": rr_y, "RR_Shift": np.hypot(rr_x, rr_y),
                "Status": "FAIL" if is_fail else "PASS"
            })
            break # Un registro consolidado por módulo/run
            
    df_modules = pd.DataFrame(modules)
    return df, df_modules

# -----------------------------------------------------------------------------
# SIDEBAR / CARGA DE ARCHIVO
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Carga de Datos y Filtros")
uploaded_file = st.sidebar.file_drop_target = st.sidebar.file_uploader("Cargar reporte Raw (CSV o Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    df_raw, df_modules = process_data(uploaded_file)
    
    # Filtros laterales
    cw_list = sorted(df_modules["CW"].unique())
    selected_cw = st.sidebar.multiselect("Filtrar por Calendar Week (CW)", options=cw_list, default=cw_list)
    
    type_list = sorted(df_modules["BatteryType"].unique())
    selected_type = st.sidebar.multiselect("Filtrar por Tipo de Batería", options=type_list, default=type_list)
    
    # Aplicar Filtros
    df_filtered = df_modules[
        (df_modules["CW"].isin(selected_cw)) & 
        (df_modules["BatteryType"].isin(selected_type))
    ]
    
    # -------------------------------------------------------------------------
    # TAB 1: RESUMEN Y KPIS DE CALIDAD
    # -------------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 Resumen & FPY", "📐 Vector Shift Visualizer", "🔍 Geometría y Diagonales"])
    
    with tab1:
        st.subheader("KPIs Principales (First-Run Quality)")
        
        # Filtrar solo Run 1 para FPY real
        df_run1 = df_filtered[df_filtered["RunNum"] == 1]
        
        total_mod = len(df_run1)
        pass_mod = len(df_run1[df_run1["Status"] == "PASS"])
        fail_mod = len(df_run1[df_run1["Status"] == "FAIL"])
        fpy = (pass_mod / total_mod * 100) if total_mod > 0 else 0.0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Módulos Únicos (Run 1)", total_mod)
        col2.metric("Aprobados (PASS)", pass_mod)
        col3.metric("Rechazados (FAIL)", fail_mod, delta_color="inverse")
        col4.metric("First-Pass Yield (FPY)", f"{fpy:.1f}%")
        
        st.divider()
        st.markdown("### Tendencia Semanal de FPY")
        
        # FPY por Semana
        fpy_weekly = df_run1.groupby("CW").agg(
            Total=('PartID', 'count'),
            Pass=('Status', lambda x: (x == 'PASS').sum()),
            Fail=('Status', lambda x: (x == 'FAIL').sum())
        ).reset_index()
        fpy_weekly["FPY_%"] = (fpy_weekly["Pass"] / fpy_weekly["Total"]) * 100
        
        st.dataframe(fpy_weekly.style.format({"FPY_%": "{:.1f}%"}), use_container_width=True)
        
    # -------------------------------------------------------------------------
    # TAB 2: VECTOR SHIFT & INSPECCIÓN INDIVIDUAL
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Visualizador de Deformación Geométrica Magnificada")
        
        col_sel, col_scale = st.columns([2, 1])
        selected_part = col_sel.selectbox("Seleccionar Módulo (Part ID):", df_filtered["PartID"].unique())
        scale_factor = col_scale.slider("Escala de Magnificación (Offsets):", min_value=1, max_value=50, value=20)
        
        row = df_filtered[df_filtered["PartID"] == selected_part].iloc[0]
        
        # Dimensiones nominales estándar (modificables)
        nom_w = 400.0
        nom_l = 600.0
        
        # Puntos Nominales
        px_nom = [0, nom_w, nom_w, 0, 0]
        py_nom = [0, 0, nom_l, nom_l, 0]
        
        # Offsets Magnificados
        px_real = [
            0 + row["RL_X"] * scale_factor,
            nom_w + row["RR_X"] * scale_factor,
            nom_w + row["FR_X"] * scale_factor,
            0 + row["FL_X"] * scale_factor,
            0 + row["RL_X"] * scale_factor
        ]
        py_real = [
            0 + row["RL_Y"] * scale_factor,
            0 + row["RR_Y"] * scale_factor,
            nom_l + row["FR_Y"] * scale_factor,
            nom_l + row["FL_Y"] * scale_factor,
            0 + row["RL_Y"] * scale_factor
        ]
        
        fig = go.Figure()
        
        # Contorno Nominal
        fig.add_trace(go.Scatter(
            x=px_nom, y=py_nom,
            mode='lines',
            name='Nominal (Ideal)',
            line=dict(color='gray', dash='dash')
        ))
        
        # Contorno Real Magnificado
        line_color = 'red' if row["Status"] == "FAIL" else 'green'
        fig.add_trace(go.Scatter(
            x=px_real, y=py_real,
            mode='lines+markers',
            name=f'Deformado ({scale_factor}x Scale)',
            line=dict(color=line_color, width=3)
        ))
        
        fig.update_layout(
            title=f"Mapa de Deformación - Módulo {row['PartID']} ({row['BatteryType']}) - Status: {row['Status']}",
            xaxis_title="Eje X (mm)",
            yaxis_title="Eje Y (mm)",
            yaxis=dict(scaleanchor="x", scaleratio=1),
            width=700, height=800
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    # -------------------------------------------------------------------------
    # TAB 3: ANÁLISIS GEOMÉTRICO Y DIAGONALES
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Cálculo de Diagonales, Cizallamiento y Efecto Trapecio")
        
        nom_w = 400.0
        nom_l = 600.0
        
        # Calcular diagonales reales
        def calc_diags(r):
            fl = np.array([0 + r["FL_X"], nom_l + r["FL_Y"]])
            fr = np.array([nom_w + r["FR_X"], nom_l + r["FR_Y"]])
            rl = np.array([0 + r["RL_X"], 0 + r["RL_Y"]])
            rr = np.array([nom_w + r["RR_X"], 0 + r["RR_Y"]])
            
            d1 = np.linalg.norm(fl - rr) # FL a RR
            d2 = np.linalg.norm(fr - rl) # FR a RL
            
            w_top = np.linalg.norm(fl - fr)
            w_bot = np.linalg.norm(rl - rr)
            
            return pd.Series([d1, d2, d1 - d2, w_top - w_bot])

        df_geom = df_filtered.copy()
        df_geom[["Diag1_mm", "Diag2_mm", "Delta_Diagonals_mm", "Trapezoid_Delta_mm"]] = df_geom.apply(calc_diags, axis=1)
        
        st.dataframe(
            df_geom[["PartID", "BatteryType", "CW", "Status", "Diag1_mm", "Diag2_mm", "Delta_Diagonals_mm", "Trapezoid_Delta_mm"]]
            .style.format({
                "Diag1_mm": "{:.2f}",
                "Diag2_mm": "{:.2f}",
                "Delta_Diagonals_mm": "{:.2f}",
                "Trapezoid_Delta_mm": "{:.2f}"
            }),
            use_container_width=True
        )

else:
    st.info("👆 Por favor sube un archivo de mediciones `.xlsx` o `.csv` en la barra lateral para iniciar el análisis.")
