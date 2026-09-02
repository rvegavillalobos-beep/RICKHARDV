import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Quality Control & Geometric Analysis",
    page_icon="⚙️",
    layout="wide",
)


# --- FUNCIONES DE SOPORTE ---
def determine_battery_type(part_id: str, feature_name: str) -> str:
  p_id = str(part_id).upper().strip()
  f_name = str(feature_name).upper().strip()

  if "_DJ" in p_id or "_DJ" in f_name or "_DA" in f_name:
    return "Type M" if "_DJ" in f_name or "_DJ" in p_id else "Type S"
  return "Type S"


def extract_corner_index(feature_name: str) -> int:
  f = str(feature_name).lower().strip()
  # Mapeo exacto basado en la nomenclatura de los features CAD / Raw Data
  if "l0324" in f and "aa" in f:
     return 1  # FL (Front-Left AA)
  elif "r0301" in f and "aa" in f:
     return 2  # FR (Front-Right AA)
  elif "l0324" in f and ("dj" in f or "da" in f or "cc" in f or "bd" in f):
     return 3  # RL (Rear-Left)
  elif ("r0301" in f or "r302" in f or "r309" in f or "r308" in f) and (
      "dj" in f or "da" in f or "cc" in f or "bd" in f
  ):
     return 4  # RR (Rear-Right)
  
  # Fallbacks genéricos por si cambia la nomenclatura
  if "fl" in f: return 1
  if "fr" in f: return 2
  if "rl" in f: return 3
  if "rr" in f: return 4
  return 0


def get_nominal_coordinates(bat_type: str):
  if bat_type.upper() == "TYPE S":
    return {
        "FL_X": 2290.48, "FL_Y": -559.4,
        "FR_X": 2290.48, "FR_Y": 558.9,
        "RL_X": 997.28,  "RL_Y": -559.4,
        "RR_X": 997.28,  "RR_Y": 511.1,
    }
  else:  # Type M o genérico
    return {
        "FL_X": 2290.48, "FL_Y": -559.4,
        "FR_X": 2290.48, "FR_Y": 558.9,
        "RL_X": 609.31,  "RL_Y": -583.3,
        "RR_X": 609.31,  "RR_Y": 535.0,
    }


def calculate_corner_angle(xa, ya, xb, yb, xc, yc):
  v_ab_x, v_ab_y = xb - xa, yb - ya
  v_ac_x, v_ac_y = xc - xa, yc - ya
  dot_product = (v_ab_x * v_ac_x) + (v_ab_y * v_ac_y)
  mag_ab = np.sqrt(v_ab_x**2 + v_ab_y**2)
  mag_ac = np.sqrt(v_ac_x**2 + v_ac_y**2)
  if mag_ab == 0 or mag_ac == 0:
    return 0.0
  cos_theta = np.clip(dot_product / (mag_ab * mag_ac), -1.0, 1.0)
  return float(np.degrees(np.arccos(cos_theta)))


# --- INTERFAZ STREAMLIT ---
st.title("⚙️ Módulo de Control de Calidad y Análisis Geométrico")

st.sidebar.header("🛠️ Configuración y Tolerancias")
max_diag_tol = st.sidebar.slider("Tolerancia Máx. Delta Diagonales [mm]", 0.5, 3.0, 1.5, 0.1)
spec_limit = st.sidebar.slider("Límite de Especificación X/Y [±mm]", 1.0, 5.0, 3.0, 0.5)

uploaded_file = st.file_uploader("Sube tu archivo de datos raw (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
  try:
    if uploaded_file.name.endswith(".csv"):
      df_raw = pd.read_csv(uploaded_file, skiprows=2)
    else:
      df_raw = pd.read_excel(uploaded_file, skiprows=2)

    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    time_col = [c for c in df_raw.columns if "time" in c.lower()][0]
    part_col = [c for c in df_raw.columns if "part" in c.lower()][0]
    feat_col = [c for c in df_raw.columns if "feature" in c.lower()][0]
    x_dev_col = [c for c in df_raw.columns if "x" in c.lower() and "deviation" in c.lower()][0]
    y_dev_col = [c for c in df_raw.columns if "y" in c.lower() and "deviation" in c.lower()][0]

    df_raw["ParsedDate"] = pd.to_datetime(df_raw[time_col], errors="coerce")
    df_raw["CalendarWeek"] = "CW" + df_raw["ParsedDate"].dt.isocalendar().week.astype(str).str.zfill(2)
    df_raw["BatteryType"] = df_raw.apply(lambda row: determine_battery_type(row[part_col], row[feat_col]), axis=1)
    df_raw["CornerIndex"] = df_raw.apply(lambda row: extract_corner_index(row[feat_col]), axis=1)
    df_raw["X_Val"] = pd.to_numeric(df_raw[x_dev_col], errors="coerce").fillna(0.0)
    df_raw["Y_Val"] = pd.to_numeric(df_raw[y_dev_col], errors="coerce").fillna(0.0)
    
    # Identificar fuera de especificación por esquina (± spec_limit)
    df_raw["IsOutOfSpec"] = (
        (df_raw["X_Val"].abs() > spec_limit) | 
        (df_raw["Y_Val"].abs() > spec_limit)
    )

    # --- AGRUPACIÓN CORRECTA: 1 Batería (Time + PartID) por línea ---
    modules_data = []
    # Agrupamos estrictamente por la combinación única de Fecha/Hora y PartID
    grouped = df_raw.groupby([time_col, part_col])

    for (t_val, p_val), group in grouped:
      first_row = group.iloc().iloc[0]
      full_dt = first_row["ParsedDate"]
      cal_week = first_row["CalendarWeek"]
      bat_type = first_row["BatteryType"]

      corners = {1: (None, None), 2: (None, None), 3: (None, None), 4: (None, None)}
      out_spec_flags = []

      for _, r_item in group.iterrows():
        c_idx = r_item["CornerIndex"]
        if c_idx in [1, 2, 3, 4]:
          corners[c_idx] = (r_item["X_Val"], r_item["Y_Val"])
          out_spec_flags.append(r_item["IsOutOfSpec"])

      total_out_spec = sum(out_spec_flags) if out_spec_flags else 0
      status = "FAIL" if total_out_spec > 0 else "PASS"

      modules_data.append({
          "Date": full_dt,
          "CalendarWeek": cal_week,
          "PartID": p_val,
          "BatteryType": bat_type,
          "FL_X": corners[1][0], "FL_Y": corners[1][1],
          "FR_X": corners[2][0], "FR_Y": corners[2][1],
          "RL_X": corners[3][0], "RL_Y": corners[3][1],
          "RR_X": corners[4][0], "RR_Y": corners[4][1],
          "OutOfSpecCount": total_out_spec,
          "Status": status,
      })

    df_summary = pd.DataFrame(modules_data)

    tab1, tab2, tab3 = st.tabs([
        "📊 Resumen General (1 Línea por Batería)", 
        "📈 Gráfica Geométrica Interactiva", 
        "📐 Análisis de Escuadría"
    ])

    with tab1:
      st.subheader("Reporte General de Módulos (Todas las esquinas por medición)")
      st.dataframe(df_summary, use_container_width=True)

      col1, col2, col3 = st.columns(3)
      total_modules = len(df_summary)
      passed_modules = len(df_summary[df_summary["Status"] == "PASS"])
      fpy = (passed_modules / total_modules * 100) if total_modules > 0 else 0

      col1.metric("Total de Baterías Inspeccionadas", total_modules)
      col2.metric("Aprobadas dentro de Spec (±3mm)", passed_modules)
      col3.metric("First-Pass Yield (FPY)", f"{fpy:.1f}%")

    with tab2:
      st.subheader("Visualización Geométrica por Batería")
      if not df_summary.empty:
        selected_idx = st.selectbox(
            "Selecciona una Batería (PartID y Fecha):", 
            df_summary.index, 
            format_func=lambda i: f"{df_summary.loc[i, 'Date']} | {df_summary.loc[i, 'PartID']} ({df_summary.loc[i, 'Status']})"
        )
        row_sel = df_summary.loc[selected_idx]
        
        fig = go.Figure()
        nom = get_nominal_coordinates(row_sel["BatteryType"])
        
        # Dibujar perfil nominal
        nom_box = [
            (nom["RL_X"], nom["RL_Y"]), 
            (nom["FL_X"], nom["FL_Y"]), 
            (nom["FR_X"], nom["FR_Y"]), 
            (nom["RR_X"], nom["RR_Y"]), 
            (nom["RL_X"], nom["RL_Y"])
        ]
        fig.add_trace(go.Scatter(
            x=[p[0] for p in nom_box], y=[p[1] for p in nom_box],
            mode="lines", name="Nominal CAD", line=dict(color="blue", width=2, dash="dash")
        ))

        # Dibujar perfil real medido si las esquinas no son nulas
        if not pd.isna(row_sel["FL_X"]):
          act_box = [
              (nom["RL_X"] + row_sel["RL_X"], nom["RL_Y"] + row_sel["RL_Y"]),
              (nom["FL_X"] + row_sel["FL_X"], nom["FL_Y"] + row_sel["FL_Y"]),
              (nom["FR_X"] + row_sel["FR_X"], nom["FR_Y"] + row_sel["FR_Y"]),
              (nom["RR_X"] + row_sel["RR_X"], nom["RR_Y"] + row_sel["RR_Y"]),
              (nom["RL_X"] + row_sel["RL_X"], nom["RL_Y"] + row_sel["RL_Y"])
          ]
          color_line = "red" if row_sel["Status"] == "FAIL" else "green"
          fig.add_trace(go.Scatter(
              x=[p[0] for p in act_box], y=[p[1] for p in act_box],
              mode="lines+markers", name=f"Medido ({row_sel['Status']})",
              line=dict(color=color_line, width=3), marker=dict(size=8)
          ))

        fig.update_layout(
            xaxis_title="Eje X (mm)", yaxis_title="Eje Y (mm)",
            height=500, title=f"Batería: {row_sel['PartID']}"
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
      st.subheader("Análisis de Escuadría y Diagonales")
      squareness_records = []

      for _, row in df_summary.iterrows():
        if pd.isna(row["FL_X"]): continue
        nom = get_nominal_coordinates(row["BatteryType"])
        
        d1_nom = np.sqrt((nom["RR_X"] - nom["FL_X"])**2 + (nom["RR_Y"] - nom["FL_Y"])**2)
        d2_nom = np.sqrt((nom["RL_X"] - nom["FR_X"])**2 + (nom["RL_Y"] - nom["FR_Y"])**2)

        fl_x_act = nom["FL_X"] + row["FL_X"]
        fl_y_act = nom["FL_Y"] + row["FL_Y"]
        fr_x_act = nom["FR_X"] + row["FR_X"]
        fr_y_act = nom["FR_Y"] + row["FR_Y"]
        rl_x_act = nom["RL_X"] + row["RL_X"]
        rl_y_act = nom["RL_Y"] + row["RL_Y"]
        rr_x_act = nom["RR_X"] + row["RR_X"]
        rr_y_act = nom["RR_Y"] + row["RR_Y"]

        d1_act = np.sqrt((rr_x_act - fl_x_act)**2 + (rr_y_act - fl_y_act)**2)
        d2_act = np.sqrt((rl_x_act - fr_x_act)**2 + (rl_y_act - fr_y_act)**2)

        delta_diags = abs((d1_act - d2_act) - (d1_nom - d2_nom))
        status = "DEFORMED" if delta_diags > max_diag_tol else "SQUARE OK"

        squareness_records.append({
            "PartID": row["PartID"],
            "BatteryType": row["BatteryType"],
            "Diag Delta [mm]": round(delta_diags, 2),
            "Squareness Status": status,
        })

      df_squareness = pd.DataFrame(squareness_records)
      st.dataframe(df_squareness, use_container_width=True)

    # --- EXPORTAR A EXCEL ---
    st.markdown("---")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_summary.to_excel(writer, sheet_name="Module_Summary_Report", index=False)
      if 'df_squareness' in locals() and not df_squareness.empty:
        df_squareness.to_excel(writer, sheet_name="Squareness_Analysis", index=False)
    processed_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte Completo en Excel",
        data=processed_data,
        file_name="Quality_Analysis_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

  except Exception as e:
    st.error(f"Ocurrió un error al procesar el archivo. Detalle: {e}")
