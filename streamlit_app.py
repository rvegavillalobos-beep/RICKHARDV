import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Calculador de Perfil de Conveyor", layout="wide")

st.title("Calculador de Perfiles de Aceleración y Frenado - Conveyor")
st.markdown("Gráficas interactivas con Plotly para hacer zoom, pan y análisis detallado.")

# --- INICIALIZACIÓN DE ESTADOS (Valores Default Solicitados) ---
defaults = {
    "conveyor_length": 3000.0,
    "speed_fast_a": 300.0,
    "speed_slow_a": 100.0,
    "accel_a": 300.0,
    "decel_a": 300.0,
    "sensor_distance_a": 150.0,
    
    "comparar": False,
    "speed_fast_b": 450.0,
    "speed_slow_b": 120.0,
    "accel_b": 400.0,
    "decel_b": 300.0,
    "sensor_distance_b": 150.0
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- BARRA LATERAL DE PARÁMETROS ---
st.sidebar.header("Geometría Global")
st.sidebar.number_input("Largo total del conveyor (mm)", value=st.session_state.conveyor_length, step=100.0, key="conveyor_length")

st.sidebar.header("Perfil Principal (Perfil A)")
st.sidebar.number_input("SPEED_AUTO_FAST A (mm/s)", value=st.session_state.speed_fast_a, step=10.0, key="speed_fast_a")
st.sidebar.number_input("SPEED_AUTO_SLOW A (mm/s)", value=st.session_state.speed_slow_a, step=10.0, key="speed_slow_a")
st.sidebar.number_input("RAMP_ACCEL A (mm/s²)", value=st.session_state.accel_a, step=50.0, key="accel_a")
st.sidebar.number_input("RAMP_DECEL A (mm/s²)", value=st.session_state.decel_a, step=50.0, key="decel_a")
st.sidebar.number_input("Distancia Sensor Reducción A (mm)", value=st.session_state.sensor_distance_a, step=50.0, key="sensor_distance_a")

st.sidebar.markdown("---")
st.sidebar.checkbox("Comparar con Perfil B", value=st.session_state.comparar, key="comparar")

if st.session_state.comparar:
    st.sidebar.header("Perfil de Comparación (Perfil B)")
    st.sidebar.number_input("SPEED_AUTO_FAST B (mm/s)", value=st.session_state.speed_fast_b, step=10.0, key="speed_fast_b")
    st.sidebar.number_input("SPEED_AUTO_SLOW B (mm/s)", value=st.session_state.speed_slow_b, step=10.0, key="speed_slow_b")
    st.sidebar.number_input("RAMP_ACCEL B (mm/s²)", value=st.session_state.accel_b, step=50.0, key="accel_b")
    st.sidebar.number_input("RAMP_DECEL B (mm/s²)", value=st.session_state.decel_b, step=50.0, key="decel_b")
    st.sidebar.number_input("Distancia Sensor Reducción B (mm)", value=st.session_state.sensor_distance_b, step=50.0, key="sensor_distance_b")

# --- FUNCIÓN DE CÁLCULO CINEMÁTICO ---
def calcular_perfil(v_fast, v_slow, accel, decel, length, s_dist):
    dt = 0.01
    t_max = 20.0
    steps = int(t_max / dt)
    
    t = np.zeros(steps)
    pos = np.zeros(steps)
    vel = np.zeros(steps)
    
    p = 0.0
    v = 0.0
    pos_sensor_red = length - s_dist
    pos_stop = length
    state = "ACCEL_FAST"
    
    t_accel_end = 0.0
    t_sensor_red = 0.0
    t_slow_reached = 0.0
    t_brake_start = 0.0
    
    for i in range(1, steps):
        t[i] = t[i-1] + dt
        
        if state == "ACCEL_FAST":
            v += accel * dt
            if v >= v_fast:
                v = v_fast
                t_accel_end = t[i]
                state = "CRUISE_FAST"
        elif state == "CRUISE_FAST":
            if p >= pos_sensor_red:
                t_sensor_red = t[i]
                state = "DECEL_TO_SLOW"
        elif state == "DECEL_TO_SLOW":
            v -= decel * dt
            if v <= v_slow:
                v = v_slow
                t_slow_reached = t[i]
                state = "CRUISE_SLOW"
        elif state == "CRUISE_SLOW":
            dist_frenado_nec = (v_slow**2) / (2 * decel) if decel > 0 else 0
            if p >= (pos_stop - dist_frenado_nec):
                t_brake_start = t[i]
                state = "DECEL_TO_STOP"
        elif state == "DECEL_TO_STOP":
            v -= decel * dt
            if v <= 0:
                v = 0.0
                state = "DONE"
        elif state == "DONE":
            v = 0.0
            
        p += v * dt
        if p > length:
            p = length
            v = 0.0
            
        pos[i] = p
        vel[i] = v
        
        if state == "DONE" and i > 50 and np.all(vel[i-20:i] == 0):
            t = t[:i+1]
            pos = pos[:i+1]
            vel = vel[:i+1]
            break
            
    return t, pos, vel, t_sensor_red, t_brake_start

t_a, pos_a, vel_a, t_red_a, t_stop_a = calcular_perfil(
    st.session_state.speed_fast_a, st.session_state.speed_slow_a, 
    st.session_state.accel_a, st.session_state.decel_a, 
    st.session_state.conveyor_length, st.session_state.sensor_distance_a
)

if st.session_state.comparar:
    t_b, pos_b, vel_b, t_red_b, t_stop_b = calcular_perfil(
        st.session_state.speed_fast_b, st.session_state.speed_slow_b, 
        st.session_state.accel_b, st.session_state.decel_b, 
        st.session_state.conveyor_length, st.session_state.sensor_distance_b
    )

# --- CONSTRUCCIÓN DE GRÁFICAS CON PLOTLY ---
fig = make_subplots(
    rows=1, cols=2, 
    subplot_titles=("Perfil de Velocidad", "Perfil de Posición"),
    horizontal_spacing=0.12
)

# --- GRÁFICA DE VELOCIDAD (Columna 1) ---
fig.add_trace(go.Scatter(x=t_a, y=vel_a, mode='lines', name='Velocidad A', line=dict(color='#1f77b4', width=3)), row=1, col=1)
fig.add_trace(go.Scatter(x=[t_red_a, t_red_a], y=[0, max(vel_a)*1.1], mode='lines', name='Sensor Reducción A', line=dict(color="#ff7f0e", width=2, dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=[t_stop_a, t_stop_a], y=[0, max(vel_a)*1.1], mode='lines', name='Inicio Stop A', line=dict(color="#d62728", width=2, dash="dash")), row=1, col=1)

if st.session_state.comparar:
    max_v_gen = max(max(vel_a), max(vel_b))
    fig.add_trace(go.Scatter(x=t_b, y=vel_b, mode='lines', name='Velocidad B', line=dict(color='#9467bd', width=3, dash='dashdot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=[t_red_b, t_red_b], y=[0, max_v_gen*1.1], mode='lines', name='Sensor Reducción B', line=dict(color="#17becf", width=2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=[t_stop_b, t_stop_b], y=[0, max_v_gen*1.1], mode='lines', name='Inicio Stop B', line=dict(color="#e377c2", width=2, dash="dash")), row=1, col=1)

# --- GRÁFICA DE POSICIÓN (Columna 2) ---
fig.add_trace(go.Scatter(x=t_a, y=pos_a, mode='lines', name='Posición A', line=dict(color='#2ca02c', width=3)), row=1, col=2)
fig.add_shape(type="line", x0=0, x1=t_a[-1], y0=st.session_state.conveyor_length, y1=st.session_state.conveyor_length, line=dict(color="#d62728", width=2, dash="dash"), row=1, col=2)
fig.add_shape(type="line", x0=0, x1=t_a[-1], y0=st.session_state.conveyor_length-st.session_state.sensor_distance_a, y1=st.session_state.conveyor_length-st.session_state.sensor_distance_a, line=dict(color="#ff7f0e", width=2, dash="dot"), row=1, col=2)
fig.add_shape(type="line", x0=t_red_a, x1=t_red_a, y0=0, y1=st.session_state.conveyor_length, line=dict(color="rgba(255, 127, 14, 0.5)", width=1.5, dash="dot"), row=1, col=2)
fig.add_shape(type="line", x0=t_stop_a, x1=t_stop_a, y0=0, y1=st.session_state.conveyor_length, line=dict(color="rgba(214, 39, 40, 0.5)", width=1.5, dash="dash"), row=1, col=2)

if st.session_state.comparar:
    fig.add_trace(go.Scatter(x=t_b, y=pos_b, mode='lines', name='Posición B', line=dict(color='#8c564b', width=3, dash='dashdot')), row=1, col=2)
    fig.add_shape(type="line", x0=0, x1=t_b[-1], y0=st.session_state.conveyor_length-st.session_state.sensor_distance_b, y1=st.session_state.conveyor_length-st.session_state.sensor_distance_b, line=dict(color="#17becf", width=2, dash="dot"), row=1, col=2)
    fig.add_shape(type="line", x0=t_red_b, x1=t_red_b, y0=0, y1=st.session_state.conveyor_length, line=dict(color="rgba(23, 190, 207, 0.5)", width=1.5, dash="dot"), row=1, col=2)
    fig.add_shape(type="line", x0=t_stop_b, x1=t_stop_b, y0=0, y1=st.session_state.conveyor_length, line=dict(color="rgba(227, 119, 194, 0.5)", width=1.5, dash="dash"), row=1, col=2)

# Configuración de ejes y diseño general con leyenda externa en la parte baja
fig.update_xaxes(title_text="Tiempo (s)", row=1, col=1)
fig.update_yaxes(title_text="Velocidad (mm/s)", row=1, col=1)
fig.update_xaxes(title_text="Tiempo (s)", row=1, col=2)
fig.update_yaxes(title_text="Posición (mm)", row=1, col=2)

fig.update_layout(
    height=600,
    template="plotly_white",
    hovermode="x unified",
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.22,
        xanchor="center",
        x=0.5,
        font=dict(size=10)
    ),
    margin=dict(b=120)
)

st.plotly_chart(fig, use_container_width=True)

# --- MÉTRICAS COMPARATIVAS ---
st.markdown("---")
st.subheader("⏱️ Desglose de Tiempos del Ciclo")

if not st.session_state.comparar:
    col_m0, col_m1, col_m2, col_m3, col_m4 = st.columns(5)
    col_m0.metric("Tiempo Total Ciclo", f"{t_a[-1]:.2f} s")
    col_m1.metric("Aceleración", f"{t_red_a:.2f} s")
    col_m2.metric("Desacel. a Slow", f"{(t_stop_a - t_red_a):.2f} s")
    col_m3.metric("Velocidad Slow", f"{(t_a[-1] - t_stop_a):.2f} s")
    col_m4.metric("Frenado Final", f"{(t_a[-1] - t_stop_a):.2f} s")
else:
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Perfil A**")
        ca1, ca2, ca3 = st.columns(3)
        ca1.metric("Total Ciclo A", f"{t_a[-1]:.2f} s")
        ca2.metric("Sensor A", f"{st.session_state.sensor_distance_a} mm")
        ca3.metric("Frenado A", f"{st.session_state.decel_a} mm/s²")
    with col_b:
        st.markdown("**Perfil B**")
        cb1, cb2, cb3 = st.columns(3)
        cb1.metric("Total Ciclo B", f"{t_b[-1]:.2f} s")
        cb2.metric("Sensor B", f"{st.session_state.sensor_distance_b} mm")
        cb3.metric("Frenado B", f"{st.session_state.decel_b} mm/s²")
