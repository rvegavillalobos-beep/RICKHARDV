import streamlit as st
import pandas as pd
import numpy as np

# Configuración inicial de la página
st.set_page_config(
    page_title="Dimensional & Root Cause Analysis", 
    layout="wide"
)

st.title("📐 Dimensional & Root Cause Analysis Dashboard")

# ==========================================
# 1. CONTROLES DE BARRA LATERAL (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Configuración del Análisis")

# Toggle para excluir mediciones incompletas
exclude_incomplete = st.sidebar.checkbox(
    "Excluir mediciones incompletas", 
    value=True,
    help="Si está activo, las piezas con coordenadas faltantes se marcarán con RunNum = 0 y Status = 'INCOMPLETE'."
)

# Carga opcional de archivo
uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo de mediciones (CSV o Excel)", 
    type=["csv", "xlsx"]
)

# ==========================================
# 2. CARGA Y PREPARACIÓN DE DATOS
# ==========================================
if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file)
    else:
        df_raw = pd.read_excel(uploaded_file)
else:
    # Datos sintéticos de muestra para ejecución inmediata
    data = {
        "Serial": [f"SN-{i:03d}" for i in range(1, 11)],
        "RunNum": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "FL_X": [100.1, 100.2, np.nan, 100.0, 99.8, 100.3, np.nan, 100.1, 100.0, 99.9],
        "FR_X": [100.0, 100.1, 100.2, 100.1, 99.9, 100.2, 100.1, 100.0, 99.8, 100.1],
        "RL_X": [100.2, 100.0, 100.1, 100.2, 100.0, 100.1, np.nan, 100.2, 100.1, 100.0],
        "RR_X": [100.1, 100.2, 100.0, 100.0, 99.7, 100.0, 100.2, 100.1, 100.0, 99.9],
        "FL_Y": [200.0, 200.1, np.nan, 200.2, 199.9, 200.1, np.nan, 200.0, 200.1, 199.8],
        "FR_Y": [200.1, 200.0, 200.1, 200.0, 200.0, 200.2, 200.0, 200.1, 199.9, 200.0],
        "RL_Y": [200.0, 200.2, 200.0, 200.1, 199.8, 200.0, np.nan, 200.2, 200.0, 200.1],
        "RR_Y": [200.2, 200.1, 200.2, 200.0, 199.9, 200.1, 200.1, 200.0, 200.1, 200.0],
    }
    df_raw = pd.DataFrame(data)

# Procesamiento global
df_analysis = df_raw.copy()

# Evaluación de completitud
required_cols = ["FL_X", "FR_X", "RL_X", "RR_X"]
df_analysis["is_complete"] = ~df_analysis[required_cols].isna().any(axis=1)

# Clasificación de registros según la bandera exclude_incomplete
if exclude_incomplete:
    # Marcar mediciones incompletas con RunNum = 0 y Status = INCOMPLETE
    df_analysis.loc[~df_analysis["is_complete"], "RunNum"] = 0
    df_analysis.loc[~df_analysis["is_complete"], "Status"] = "INCOMPLETE"
    df_analysis.loc[~df_analysis["is_complete"], "corners_out_of_spec"] = None
    df_analysis.loc[df_analysis["is_complete"], "Status"] = "OK"
else:
    # Conservar RunNum original y clasificar únicamente por estado
    df_analysis["Status"] = np.where(
        df_analysis["is_complete"], "OK", "INCOMPLETE_MEASUREMENT"
    )

# ==========================================
# 3. NAVEGACIÓN POR PESTAÑAS
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📊 General Summary & FPY", 
    "📈 Detailed Run Analysis", 
    "📐 Advanced Squareness & Deformation Root Cause Analysis"
])

# ------------------------------------------
# TAB 1: General Summary & FPY
# ------------------------------------------
with tab1:
    st.subheader("📊 General Summary & First Pass Yield (FPY)")
    
    # Filtrado estricto a primera corrida válida
    df_run1 = df_analysis[df_analysis["RunNum"] == 1]
    
    col1, col2, col3 = st.columns(3)
    total_records = len(df_analysis)
    run1_count = len(df_run1)
    passed_count = len(df_run1[df_run1["Status"] == "OK"])
    
    fpy_rate = (passed_count / run1_count * 100) if run1_count > 0 else 0.0

    col1.metric("Total Registros Cargados", total_records)
    col2.metric("Unidades Procesadas (Run 1)", run1_count)
    col3.metric("First Pass Yield (FPY)", f"{fpy_rate:.1f}%")

    st.markdown("#### Vista General de Datos Procesados")
    st.dataframe(df_analysis, use_container_width=True)

# ------------------------------------------
# TAB 2: Detailed Run Analysis
# ------------------------------------------
with tab2:
    st.subheader("📈 Detailed Run Analysis")
    st.write("Análisis filtrado omitiendo mediciones fuera de corrida estándar (RunNum > 0).")
    
    df_runs_valid = df_analysis[df_analysis["RunNum"] > 0]
    st.dataframe(df_runs_valid, use_container_width=True)

# ------------------------------------------
# TAB 3: Advanced Squareness & Deformation
# ------------------------------------------
with tab3:
    st.subheader("📐 Advanced Squareness & Deformation Root Cause Analysis")

    # FILTRADO CORREGIDO: Respetar la bandera del sidebar
    df_sq_input = df_analysis.copy()
    if exclude_incomplete:
        df_sq_input = df_sq_input[df_sq_input["Status"] != "INCOMPLETE"]

    squareness_records = []

    for idx, row in df_sq_input.iterrows():
        # Verificación de respaldo para omitir registros con nulos
        if (
            pd.isna(row["FL_X"])
            or pd.isna(row["FR_X"])
            or pd.isna(row["RL_X"])
            or pd.isna(row["RR_X"])
        ):
            continue

        # Cálculo de diagonales (distancia euclidiana entre esquinas)
        diag1 = np.sqrt(
            (row["RR_X"] - row["FL_X"]) ** 2 + (row["RR_Y"] - row["FL_Y"]) ** 2
        )
        diag2 = np.sqrt(
            (row["RL_X"] - row["FR_X"]) ** 2 + (row["RL_Y"] - row["FR_Y"]) ** 2
        )
        
        delta_diag = abs(diag1 - diag2)
        squareness_error = (row["FL_X"] - row["FR_X"]) - (row["RL_X"] - row["RR_X"])

        squareness_records.append({
            "Serial": row.get("Serial", f"Index_{idx}"),
            "RunNum": row.get("RunNum", 0),
            "Status": row.get("Status", "UNKNOWN"),
            "Diag_1_mm": round(diag1, 3),
            "Diag_2_mm": round(diag2, 3),
            "Delta_Diag_mm": round(delta_diag, 3),
            "Squareness_Error_mm": round(squareness_error, 3)
        })

    df_squareness = pd.DataFrame(squareness_records)

    if not df_squareness.empty:
        st.success(
            f"Análisis completado para {len(df_squareness)} registros "
            f"({'incompletos excluidos' if exclude_incomplete else 'incluyendo todos los registros validables'})."
        )
        
        m1, m2 = st.columns(2)
        m1.metric("Máx. Δ Diagonales", f"{df_squareness['Delta_Diag_mm'].max():.3f} mm")
        m2.metric("Promedio Error Escuadra", f"{df_squareness['Squareness_Error_mm'].mean():.3f} mm")

        st.dataframe(df_squareness, use_container_width=True)

        st.markdown("##### Desviación de Escuadra por Pieza")
        st.bar_chart(df_squareness.set_index("Serial")["Squareness_Error_mm"])
    else:
        st.warning("No hay registros válidos para calcular escuadra bajo el criterio actual del filtro.")
