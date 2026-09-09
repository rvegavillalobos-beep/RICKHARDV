import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración general de la app
st.set_page_config(page_title="Dashboard de Desviaciones de Baterías", layout="wide")

# ==============================================================================
# 1. BARRA LATERAL (SIDEBAR)
# ==============================================================================
st.sidebar.header("Panel de Control")

# Slider dinámico de tolerancia/threshold (ajustable en mm)
threshold = st.sidebar.slider(
    "Tolerancia de Desviación Threshold (mm)",
    min_value=1.0,
    max_value=10.0,
    value=3.0,
    step=0.5,
    key="threshold_slider"
)

# ==============================================================================
# 2. CARGA/GENERACIÓN DE DATOS
# Sustituye 'load_data()' por tu lectura real (ej: pd.read_excel() o SQL query)
# ==============================================================================
@st.cache_data
def load_data():
    np.random.seed(42)
    weeks = list(range(1, 51))  # Calendary Weeks (CW 1 a 50)
    corners = ["FL", "FR", "RL", "RR"]
    types = ["Type M", "Type S"]
    
    rows = []
    for b_type in types:
        for cw in weeks:
            for c in corners:
                # Simulación de datos de desviación en mm
                dev_x = np.random.normal(loc=0.0, scale=1.4)
                dev_y = np.random.normal(loc=-1.0, scale=1.1)
                rows.append({
                    "CW": cw,
                    "battery_type": b_type,
                    "corner": c,
                    "dev_x": dev_x,
                    "dev_y": dev_y
                })
    return pd.DataFrame(rows)

df_devs = load_data()

# ==============================================================================
# 3. FUNCIÓN DE RENDERIZADO DE GRÁFICOS DE 4 ESQUINAS (2x2)
# ==============================================================================
def plot_battery_corners(df, battery_type_name, threshold_val):
    # Filtrar por tipo de batería y ordenar cronológicamente por CW
    df_filtered = df[df['battery_type'] == battery_type_name].sort_values('CW')
    
    # Acomodo físico de las 4 esquinas en un layout 2x2
    corners_layout = [
        {"id": "FL", "title": "Front-Left (FL)", "row": 1, "col": 1},
        {"id": "FR", "title": "Front-Right (FR)", "row": 1, "col": 2},
        {"id": "RL", "title": "Rear-Left (RL)", "row": 2, "col": 1},
        {"id": "RR", "title": "Rear-Right (RR)", "row": 2, "col": 2},
    ]
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[c["title"] for c in corners_layout],
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0.12,
        horizontal_spacing=0.06
    )
    
    for c in corners_layout:
        corner_data = df_filtered[df_filtered['corner'] == c["id"]]
        
        # Desviación X (Línea Roja)
        fig.add_trace(
            go.Scatter(
                x=corner_data['CW'], y=corner_data['dev_x'],
                mode='lines+markers', name='Dev X',
                line=dict(color='#D32F2F', width=1.5),
                marker=dict(size=4),
                showlegend=(c["id"] == "FL")  # Muestra leyenda solo en la primera subgráfica
            ),
            row=c["row"], col=c["col"]
        )
        
        # Desviación Y (Línea Verde)
        fig.add_trace(
            go.Scatter(
                x=corner_data['CW'], y=corner_data['dev_y'],
                mode='lines+markers', name='Dev Y',
                line=dict(color='#2E7D32', width=1.5),
                marker=dict(size=4),
                showlegend=(c["id"] == "FL")
            ),
            row=c["row"], col=c["col"]
        )
        
        # Línea de Límite Superior (+Threshold)
        fig.add_hline(
            y=threshold_val, line_dash="solid", line_color="#E53935", line_width=1.5,
            row=c["row"], col=c["col"]
        )
        # Línea de Límite Inferior (-Threshold)
        fig.add_hline(
            y=-threshold_val, line_dash="solid", line_color="#E53935", line_width=1.5,
            row=c["row"], col=c["col"]
        )

    # Ajuste de layout estilo monitor industrial / calidad
    fig.update_layout(
        title=dict(text=f"<b>{battery_type_name} Deviation Plot Over Time</b>", font=dict(size=18)),
        height=600,
        margin=dict(l=40, r=40, t=60, b=40),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Configuración de ejes
    fig.update_yaxes(title_text="Desviación (mm)")
    fig.update_xaxes(title_text="CW", dtick=5)
    
    return fig

# ==============================================================================
# 4. ESTRUCTURA DEL DASHBOARD (PESTAÑAS)
# ==============================================================================
tab1, tab2 = st.tabs(["General Summary", "Detalles Adicionales"])

with tab1:
    # --- Contenido existente superior de tu General Summary ---
    st.title("General Summary")
    st.write("Métricas generales de control de proceso e indicadores de producción.")
    
    # Divisor hacia la sección de gráficos de esquinas al final de la pestaña
    st.divider()
    
    # --- TYPE M DEVIATION PLOT ---
    st.subheader("Type M Deviation plot over time")
    fig_type_m = plot_battery_corners(df_devs, "Type M", threshold)
    st.plotly_chart(fig_type_m, use_container_width=True)
    
    st.write("---")
    
    # --- TYPE S DEVIATION PLOT ---
    st.subheader("Type S Deviation plot over time")
    fig_type_s = plot_battery_corners(df_devs, "Type S", threshold)
    st.plotly_chart(fig_type_s, use_container_width=True)

with tab2:
    st.subheader("Detalles y registros de datos")
    st.dataframe(df_devs)
