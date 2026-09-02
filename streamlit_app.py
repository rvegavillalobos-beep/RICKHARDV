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


# --- FUNCIONES DE SOPORTE (Lógica VBA traducida) ---
def determine_battery_type(part_id: str, feature_name: str) -> str:
  p_id = str(part_id).upper().strip()
  f_name = str(feature_name).upper().strip()

  if "_DJ" in p_id or "_DJ" in f_name:
    return "Type M"
  elif (
      "_M" in p_id
      or "-M" in p_id
      or "TYPE M" in p_id
      or "TYPEM" in p_id
      or p_id.endswith("M")
  ):
    return "Type M"

  if "_DA" in p_id or "_DA" in f_name:
    return "Type S"
  elif (
      "_S" in p_id
      or "-S" in p_id
      or "TYPE S" in p_id
      or "TYPES" in p_id
      or p_id.endswith("S")
  ):
    return "Type S"

  return "Type S"


def extract_corner_index(feature_name: str, part_id: str) -> int:
  clean_feature = str(feature_name).lower().strip()
  if not clean_feature:
    return 0

  is_type_m = determine_battery_type(part_id, feature_name) == "Type M"

  if "72_l0324_aa" in clean_feature:
    return 1
  elif "72_r0301_aa" in clean_feature:
    return 2

  if is_type_m:
    if "72_l0324_dj" in clean_feature:
      return 3
    elif "72_r0301_dj" in clean_feature:
      return 4
  else:
    if "72_l0324_da" in clean_feature:
      return 3
    elif "72_r0302_da" in clean_feature:
      return 4

  if "fl" in clean_feature or "c1" in clean_feature:
    return 1
  elif "fr" in clean_feature or "c2" in clean_feature:
    return 2
  elif "rl" in clean_feature or "c3" in clean_feature:
    return 3
  elif "rr" in clean_feature or "c4" in clean_feature:
    return 4
  else:
    return 0


def get_nominal_coordinates(bat_type: str):
  if bat_type.upper() == "TYPE S":
    return {
        "FL_X": 2290.48,
        "FL_Y": -559.4,
        "FR_X": 2290.48,
        "FR_Y": 558.9,
        "RL_X": 997.28,
        "RL_Y": -559.4,
        "RR_X": 997.28,
        "RR_Y": 511.1,
    }
  elif bat_type.upper() == "TYPE M":
    return {
        "FL_X": 2290.48,
        "FL_Y": -559.4,
        "FR_X": 2290.48,
        "FR_Y": 558.9,
        "RL_X": 609.31,
        "RL_Y": -583.3,
        "RR_X": 609.31,
        "RR_Y": 535.0,
    }
  return None


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

# Barra Lateral: Configuración y Tolerancias Dinámicas
st.sidebar.header("🛠️ Configuración y Tolerancias")
max_diag_tol = st.sidebar.slider(
    "Tolerancia Máx. Delta Diagonales [mm]", 0.5, 3.0, 1.5, 0.1
)
critical_diag = st.sidebar.slider(
    "Límite Crítico Delta Diagonales [mm]", 2.0, 5.0, 3.0, 0.1
)
angular_tol = st.sidebar.slider(
    "Tolerancia Desviación Angular [°]", 0.05, 0.50, 0.15, 0.01
)
dim_tol = st.sidebar.slider(
    "Tolerancia Variación Dimensional [mm]", 0.1, 2.0, 0.8, 0.1
)
spec_limit = st.sidebar.slider(
    "Límite de Especificación X/Y [±mm]", 1.0, 5.0, 3.0, 0.5
)

uploaded_file = st.file_uploader(
    "Sube tu archivo de datos raw (Excel o CSV)", type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:
  try:
    # Leer archivo omitiendo las primeras 2 filas de título y tomando la fila 3 como header
    if uploaded_file.name.endswith(".csv"):
      df_raw = pd.read_csv(uploaded_file, skiprows=2)
    else:
      df_raw = pd.read_excel(uploaded_file, skiprows=2)

    # Limpieza básica de columnas
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Mapeo de columnas requeridas según la imagen
    time_col = [c for c in df_raw.columns if "time" in c.lower()][0]
    part_col = [c for c in df_raw.columns if "part" in c.lower()][0]
    feat_col = [c for c in df_raw.columns if "feature" in c.lower()][0]
    x_dev_col = [
        c for c in df_raw.columns if "x" in c.lower() and "deviation" in c.lower()
    ][0]
    y_dev_col = [
        c for c in df_raw.columns if "y" in c.lower() and "deviation" in c.lower()
    ][0]

    df_raw["ParsedDate"] = pd.to_datetime(df_raw[time_col], errors="coerce")
    df_raw["CalendarWeek"] = (
        "CW"
        + df_raw["ParsedDate"]
        .dt.isocalendar()
        .week.astype(str)
        .str.zfill(2)
    )
    df_raw["BatteryType"] = df_raw.apply(
        lambda row: determine_battery_type(row[part_col], row[feat_col]), axis=1
    )
    df_raw["CornerIndex"] = df_raw.apply(
        lambda row: extract_corner_index(row[feat_col], row[part_col]), axis=1
    )
    df_raw["X_Val"] = pd.to_numeric(df_raw[x_dev_col], errors="coerce").fillna(
        0.0
    )
    df_raw["Y_Val"] = pd.to_numeric(df_raw[y_dev_col], errors="coerce").fillna(
        0.0
    )
    df_raw["IsOutOfSpec"] = (
        (df_raw["X_Val"] < -spec_limit)
        | (df_raw["X_Val"] > spec_limit)
        | (df_raw["Y_Val"] < -spec_limit)
        | (df_raw["Y_Val"] > spec_limit)
    )

    # Agrupación por Módulo y Corrida (Run)
    df_raw["FormattedDate"] = df_raw["ParsedDate"].dt.strftime("%Y-%m-%d")
    df_raw["BaseKey"] = (
        df_raw["FormattedDate"]
        + "|"
        + df_raw[part_col].astype(str).str.strip()
    )

    # Simulación de Runs secuenciales
    run_tracker = {}
    run_list = []
    for idx, row in df_raw.iterrows():
      bkey = row["BaseKey"]
      if bkey not in run_tracker:
        run_tracker[bkey] = 1
      else:
        run_tracker[bkey] += 1
      run_list.append(run_tracker[bkey])
    df_raw["RunNum"] = run_list

    # Pivotear esquinas (FL=1, FR=2, RL=3, RR=4) para construir el reporte resumido
    modules_data = []
    grouped = df_raw.groupby(["BaseKey", "RunNum"])
    for (bkey, run_num), group in grouped:
      first_row = group.iloc[0]
      part_id = first_row[part_col]
      bat_type = first_row["BatteryType"]
      cal_week = first_row["CalendarWeek"]
      full_dt = first_row["ParsedDate"]
      out_spec_count = group["IsOutOfSpec"].sum()

      corners = {1: (None, None), 2: (None, None), 3: (None, None), 4: (None, None)}
      for _, r_item in group.iterrows():
        c_idx = r_item["CornerIndex"]
        if c_idx in [1, 2, 3, 4]:
          corners[c_idx] = (r_item["X_Val"], r_item["Y_Val"])

      modules_data.append({
          "Date": full_dt,
          "CalendarWeek": cal_week,
          "PartID": part_id,
          "BatteryType": bat_type,
          "RunNum": run_num,
          "FL_X": corners[1][0],
          "FL_Y": corners[1][1],
          "FR_X": corners[2][0],
          "FR_Y": corners[2][1],
          "RL_X": corners[3][0],
          "RL_Y": corners[3][1],
          "RR_X": corners[4][0],
          "RR_Y": corners[4][1],
          "OutOfSpecCount": out_spec_count,
          "Status": "FAIL" if out_spec_count > 0 else "PASS",
      })

    df_summary = pd.DataFrame(modules_data)

    # --- TABS DE VISUALIZACIÓN ---
    tab1, tab2, tab3 = st.tabs(
        [
            "📊 Resumen de Módulos (FPY)",
            "📈 Gráfica Geométrica Interactiva",
            "📐 Análisis de Escuadría",
        ]
    )

    with tab1:
      st.subheader("Reporte General de Módulos y Vector Shift")
      st.dataframe(df_summary, use_container_width=True)

      col1, col2, col3 = st.columns(3)
      total_modules = len(
          df_summary[df_summary["RunNum"] == 1]
      )
      passed_modules = len(
          df_summary[(df_summary["RunNum"] == 1) & (df_summary["Status"] == "PASS")]
      )
      fpy = (passed_modules / total_modules * 100) if total_modules > 0 else 0

      col1.metric("Módulos Únicos (Run 1)", total_modules)
      col2.metric("Aprobados Primera Corrida", passed_modules)
      col3.metric("First-Pass Yield (FPY)", f"{fpy:.1f}%")

    with tab2:
      st.subheader("Simulación Geométrica y Posicionamiento (50x30 mm)")
      num_to_graph = st.slider(
          "Número de baterías recientes a graficar", 1, len(df_summary), 10
      )

      fig = go.Figure()
      # Marco Nominal (Type S por defecto o genérico)
      nom_box = [(-25, -15), (-25, 15), (25, 15), (25, -15), (-25, -15)]
      fig.add_trace(
          go.Scatter(
              x=[p[0] for p in nom_box],
              y=[p[1] for p in nom_box],
              mode="lines",
              name="Perfil Nominal",
              line=dict(color="green", width=3),
          )
      )

      subset_plot = df_summary.tail(num_to_graph)
      for _, row in subset_plot.iterrows():
        nom = get_nominal_coordinates(row["BatteryType"])
        if nom and not pd.isna(row["FL_X"]):
          xs = [
              nom["RL_X"] + row["RL_X"],
              nom["FL_X"] + row["FL_X"],
              nom["FR_X"] + row["FR_X"],
              nom["RR_X"] + row["RR_X"],
              nom["RL_X"] + row["RL_X"],
          ]
          ys = [
              nom["RL_Y"] + row["RL_Y"],
              nom["FL_Y"] + row["FL_Y"],
              nom["FR_Y"] + row["FR_Y"],
              nom["RR_Y"] + row["RR_Y"],
              nom["RL_Y"] + row["RL_Y"],
          ]
          color = "red" if row["Status"] == "FAIL" else "gray"
          fig.add_trace(
              go.Scatter(
                  x=xs,
                  y=ys,
                  mode="lines+markers",
                  name=f"{row['PartID']} (R{row['RunNum']})",
                  line=dict(color=color, width=1),
                  marker=dict(size=4),
              )
          )

      fig.update_layout(
          xaxis_title="Eje X (mm)",
          yaxis_title="Eje Y (mm)",
          xaxis=dict(range=[-35, 35]),
          yaxis=dict(range=[-25, 25]),
          height=500,
      )
      st.plotly_chart(fig, use_container_width=True)

    with tab3:
      st.subheader("Análisis Avanzado de Escuadría y Deformación")
      squareness_records = []

      for _, row in df_summary.iterrows():
        nom = get_nominal_coordinates(row["BatteryType"])
        if nom and not pd.isna(row["FL_X"]):
          # Coordenadas Nominales
          d1_nom = np.sqrt(
              (nom["RR_X"] - nom["FL_X"]) ** 2
              + (nom["RR_Y"] - nom["FL_Y"]) ** 2
          )
          d2_nom = np.sqrt(
              (nom["RL_X"] - nom["FR_X"]) ** 2
              + (nom["RL_Y"] - nom["FR_Y"]) ** 2
          )
          w_top_nom = np.sqrt(
              (nom["FR_X"] - nom["FL_X"]) ** 2
              + (nom["FR_Y"] - nom["FL_Y"]) ** 2
          )
          w_bot_nom = np.sqrt(
              (nom["RR_X"] - nom["RL_X"]) ** 2
              + (nom["RR_Y"] - nom["RL_Y"]) ** 2
          )
          l_left_nom = np.sqrt(
              (nom["RL_X"] - nom["FL_X"]) ** 2
              + (nom["RL_Y"] - nom["FL_Y"]) ** 2
          )
          l_right_nom = np.sqrt(
              (nom["RR_X"] - nom["FR_X"]) ** 2
              + (nom["RR_Y"] - nom["FR_Y"]) ** 2
          )
          angle_fl_nom = calculate_corner_angle(
              nom["FL_X"],
              nom["FL_Y"],
              nom["FR_X"],
              nom["FR_Y"],
              nom["RL_X"],
              nom["RL_Y"],
          )

          # Coordenadas Reales
          fl_x_act = nom["FL_X"] + row["FL_X"]
          fl_y_act = nom["FL_Y"] + row["FL_Y"]
          fr_x_act = nom["FR_X"] + row["FR_X"]
          fr_y_act = nom["FR_Y"] + row["FR_Y"]
          rl_x_act = nom["RL_X"] + row["RL_X"]
          rl_y_act = nom["RL_Y"] + row["RL_Y"]
          rr_x_act = nom["RR_X"] + row["RR_X"]
          rr_y_act = nom["RR_Y"] + row["RR_Y"]

          d1_act = np.sqrt((rr_x_act - fl_x_act) ** 2 + (rr_y_act - fl_y_act) ** 2)
          d2_act = np.sqrt((rl_x_act - fr_x_act) ** 2 + (rl_y_act - fr_y_act) ** 2)
          w_top_act = np.sqrt((fr_x_act - fl_x_act) ** 2 + (fr_y_act - fl_y_act) ** 2)
          w_bot_act = np.sqrt((rr_x_act - rl_x_act) ** 2 + (rr_y_act - rl_y_act) ** 2)
          l_left_act = np.sqrt((rl_x_act - fl_x_act) ** 2 + (rl_y_act - fl_y_act) ** 2)
          l_right_act = np.sqrt((rr_x_act - fr_x_act) ** 2 + (rr_y_act - fr_y_act) ** 2)
          angle_fl_act = calculate_corner_angle(
              fl_x_act, fl_y_act, fr_x_act, fr_y_act, rl_x_act, rl_y_act
          )

          delta_diags = abs((d1_act - d2_act) - (d1_nom - d2_nom))
          diff_ancho = (w_top_act - w_top_nom) - (w_bot_act - w_bot_nom)
          diff_largo = (l_left_act - l_left_nom) - (l_right_act - l_right_nom)
          angle_dev = angle_fl_act - angle_fl_nom

          if delta_diags > max_diag_tol:
            status = "DEFORMED"
            detail = f"Deformación geométrica (Delta Diag: {delta_diags:.2f} mm)"
          else:
            status = "SQUARE OK"
            detail = "Geometría dentro de tolerancia"

          squareness_records.append({
              "PartID": row["PartID"],
              "BatteryType": row["BatteryType"],
              "Diag Delta [mm]": round(delta_diags, 2),
              "Angular Dev [°]": round(angle_dev, 2),
              "Squareness Status": status,
              "Details": detail,
          })

      df_squareness = pd.DataFrame(squareness_records)
      st.dataframe(df_squareness, use_container_width=True)

    # --- EXPORTAR A EXCEL ---
    st.markdown("---")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
      df_summary.to_excel(writer, sheet_name="Module_Summary_Report", index=False)
      df_squareness.to_excel(
          writer, sheet_name="Squareness_Analysis_Report", index=False
      )
    processed_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte Completo en Excel",
        data=processed_data,
        file_name="Quality_Analysis_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

  except Exception as e:
    st.error(
        f"Ocurrió un error al procesar el archivo. Verifica el formato. Detalle:"
        f" {e}"
    )
