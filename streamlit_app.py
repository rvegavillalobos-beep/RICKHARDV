import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ==============================================================================
# 1. BARRA LATERAL (Sidebar): Slider dinámico para el Threshold (3.0mm por defecto)
# ==============================================================================
st.sidebar.header("Configuración de Tolerancia")
threshold = st.sidebar.slider(
    "Umbral de Desviación (mm)",
    min_value=0.5,
    max_value=6.0,
    value=3.0,  # Valor por defecto pedido
    step=0.1,
    help="Define la línea límite superior e inferior de tolerancia.",
)


# ==============================================================================
# 2. FUNCIÓN AUXILIAR: Generador de Gráfica por Esquina (Estilo exacto a la foto)
# ==============================================================================
def plot_corner_deviation(df_corner, title_name, threshold_val):
    """Genera una gráfica individual de desviación X e Y a lo largo del tiempo (CW).

    df_corner debe contener las columnas: 'CW', 'Dev_X', 'Dev_Y'
    """
    fig = go.Figure()

    # Desviación X (Línea Roja)
    fig.add_trace(
        go.Scatter(
            x=df_corner["CW"],
            y=df_corner["Dev_X"],
            mode="lines+markers",
            name="X",
            line=dict(color="#D92B2B", width=1.5),
            marker=dict(size=4),
        )
    )

    # Desviación Y (Línea Verde)
    fig.add_trace(
        go.Scatter(
            x=df_corner["CW"],
            y=df_corner["Dev_Y"],
            mode="lines+markers",
            name="Y",
            line=dict(color="#27AE60", width=1.5),
            marker=dict(size=4),
        )
    )

    # Línea de Umbral Superior (+Threshold)
    fig.add_hline(
        y=threshold_val,
        line_color="#D92B2B",
        line_width=1.5,
        annotation_text=f"+{threshold_val}mm",
        annotation_position="top right",
    )

    # Línea de Umbral Inferior (-Threshold)
    fig.add_hline(
        y=-threshold_val,
        line_color="#D92B2B",
        line_width=1.5,
        annotation_text=f"-{threshold_val}mm",
        annotation_position="bottom right",
    )

    # Diseño estético (Recrea la cabecera roja de tu imagen)
    fig.update_layout(
        title=dict(
            text=f"<b>{title_name}</b>",
            x=0.5,
            xanchor="center",
            font=dict(color="white", size=13),
        ),
        # Pinta la barra de título de rojo como en el software industrial
        title_background_color="#D92B2B",
        xaxis=dict(
            title="CW",
            showgrid=True,
            gridcolor="#E5E5E5",
            dtick=5 if len(df_corner) > 20 else 1,
        ),
        yaxis=dict(
            title="Desviación (mm)",
            showgrid=True,
            gridcolor="#E5E5E5",
            zeroline=True,
            zerolinecolor="#888888",
            range=[-threshold_val - 3, threshold_val + 3],  # Dinámico según threshold
        ),
        height=260,
        margin=dict(l=10, r=10, t=35, b=25),
        plot_bgcolor="#F8F9FA",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        template="plotly_white",
    )

    return fig


# ==============================================================================
# 3. FUNCIÓN DE RENDERIZADO: Acomodo Geométrico 2x2 de la Batería
# ==============================================================================
def render_battery_corner_matrix(df_battery, battery_type_name, threshold_val):
    """Crea una disposición física 2x2 de las esquinas:

    [ Top-Left (FL)     ] [ Top-Right (FR)    ]
    [ Bottom-Left (RL)  ] [ Bottom-Right (RR) ]
    """
    st.subheader(f"🔋 {battery_type_name} Deviation Plot Over Time")

    # Definimos la grilla de 2 columnas x 2 filas
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    # Filtrar datos de cada esquina (Ajusta los nombres de tus esquinas según tu DataFrame)
    df_fl = df_battery[df_battery["Corner"] == "Front-Left"]
    df_fr = df_battery[df_battery["Corner"] == "Front-Right"]
    df_rl = df_battery[df_battery["Corner"] == "Rear-Left"]
    df_rr = df_battery[df_battery["Corner"] == "Rear-Right"]

    # Esquina Superior Izquierda (Front-Left)
    with row1_col1:
        st.plotly_chart(
            plot_corner_deviation(
                df_fl, "Esquina Superior Izquierda (FL)", threshold_val
            ),
            use_container_width=True,
        )

    # Esquina Superior Derecha (Front-Right)
    with row1_col2:
        st.plotly_chart(
            plot_corner_deviation(
                df_fr, "Esquina Superior Derecha (FR)", threshold_val
            ),
            use_container_width=True,
        )

    # Esquina Inferior Izquierda (Rear-Left)
    with row2_col1:
        st.plotly_chart(
            plot_corner_deviation(
                df_rl, "Esquina Inferior Izquierda (RL)", threshold_val
            ),
            use_container_width=True,
        )

    # Esquina Inferior Derecha (Rear-Right)
    with row2_col2:
        st.plotly_chart(
            plot_corner_deviation(
                df_rr, "Esquina Inferior Derecha (RR)", threshold_val
            ),
            use_container_width=True,
        )


# ==============================================================================
# 4. IMPLEMENTACIÓN AL FINAL DE TU PRIMERA PESTAÑA ("General Summary")
# ==============================================================================

# Suponiendo que estás dentro del bloque de tu primer Tab:
# with tab1:
#     ... tus KPIs y tablas anteriores ...

st.divider()  # Separador visual al final de la pestaña
st.header("📈 Análisis Temporal de Desviación por Esquinas")

# --- SIMULACIÓN DE DATOS (Sustituye esta sección por tu DataFrame real) ---
np.random.seed(42)
cws = [f"CW{i}" for i in range(1, 26)]
corners = ["Front-Left", "Front-Right", "Rear-Left", "Rear-Right"]

records = []
for b_type in ["Type M", "Type S"]:
    for c in corners:
        for cw in cws:
            records.append({
                "Battery_Type": b_type,
                "Corner": c,
                "CW": cw,
                "Dev_X": np.random.normal(0, 1.2),  # Simulación de desviación X
                "Dev_Y": np.random.normal(-1.0, 1.0),  # Simulación de desviación Y
            })
df_data = pd.DataFrame(records)
# --------------------------------------------------------------------------

# 1. Despliegue para TYPE M
df_type_m = df_data[df_data["Battery_Type"] == "Type M"]
render_battery_corner_matrix(df_type_m, "Type M", threshold)

st.markdown("<br>", unsafe_allow_html=True)  # Espaciado

# 2. Despliegue para TYPE S
df_type_s = df_data[df_data["Battery_Type"] == "Type S"]
render_battery_corner_matrix(df_type_s, "Type S", threshold)
