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


# --- FUNCIONES DE SOPORTE (Portadas fielmente desde VBA) ---
def determine_battery_type(part_id: str, feature_name: str) -> str:
  p_id = str(part_id).upper().strip()
  f_name = str(feature_name).upper().strip()

  if "_DJ" in p_id or "_DJ" in f_name:
    return "Type M"
  if "_M" in p_id or "-M" in p_id or "TYPE M" in p_id or "TYPEM" in p_id:
    return "Type M"
  if p_id.endswith("M") or p_id.endswith("_M"):
    return "Type M"

  if "_DA" in p_id or "_DA" in f_name:
    return "Type S"
  if "_S" in p_id or "-S" in p_id or "TYPE S" in p_id or "TYPES" in p_id:
    return "Type S"

  return "Type S"


def extract_corner_index(feature_name: str, part_id: str) -> int:
  f = str(feature_name).lower().strip()
  if not f:
    return 0

  is_type_m = determine_battery_type(part_id, feature_name) == "Type M"

  # Coincidencias estrictas por ID de feature específicos
  if "72_l0324_aa" in f:
    return 1
  if "72_r0301_aa" in f:
    return 2

  if is_type_m:
    if "72_l0324_dj" in f:
      return 3
    if "72_r0301_dj" in f:
      return 4
  else:
    if "72_l0324_da" in f:
      return 3
    if "72_r0302_da" in f:
      return 4

  # Patrones generales de respaldo idénticos a VBA
  if "fl" in f or "c1" in f:
    return 1
  elif "fr" in f or "c2" in f:
    return 2
  elif "rl" in f or "c3" in f:
    return 3
  elif "rr" in f or "c4" in f or "r302" in f or "r301" in f or "r0301" in f:
    return 4
  
  return 0


def get_nominal_coordinates(bat_type: str):
  if bat_type.upper() == "TYPE S":
    return {
        "FL_X": 2290.48, "FL_Y": -559.4,
        "FR_X": 2290.48, "FR_Y": 558.9,
        "RL_X": 997.28,  "RL_Y": -559.4,
        "RR_X": 997.28,  "RR_Y": 511.1,
    }
  else:
    return {
        "FL_X": 2290.48, "FL_Y": -559.4,
        "FR_X": 2290.48, "FR_Y": 558.9,
        "RL_X": 609.31,  "RL_Y": -583.3,
        "RR_X": 609.31,  "RR_Y": 535.0,
    }


def style_report(df, limit):
  cols_to_check = ['FL_X', 'FL_Y', 'FR_X', 'FR_Y', 'RL_X', 'RL_Y', 'RR_X', 'RR_Y']
  def apply_styles(row):
    styles = [''] * len(row)
    for i, col in enumerate(row.index):
      if col in cols_to_check:
        val = row[col]
        if val is not None and not pd.isna(val):
          try:
            if abs(float(val)) > limit:
              styles[i] = 'background-color: #ff4d4d; color: white; font-weight: bold;'
          except:
            pass
      if col == 'Status':
        if str(row[col]) == 'FAIL':
          styles[i] = 'background-color: #ff4d4d; color: white; font-weight: bold;'
        elif str(row[col]) == 'PASS':
          styles[i] = 'background-color: #2eb82e; color: white; font-weight: bold;'
    return styles
  return df.style.apply(apply_styles, axis=1)


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
    
    # Aquí aplicamos la función corregida idéntica al VBA
    df_raw["CornerIndex"] = df_raw.apply(lambda row: extract_corner_index(row[feat_col], row[part_col]), axis=1)
    
    df_raw["X_Val"] = pd.to_numeric(df_raw[x_dev_col], errors="coerce").fillna(0.0)
    df_raw["Y_Val"] = pd.to_numeric(df_raw[y_dev_col], errors="coerce").fillna(0.0)
    
    df_raw["IsOutOfSpec"] = (
        (df_raw["X_Val"].abs() > spec_limit) | 
        (df_raw["Y_Val"].abs() > spec_limit)
    )

    modules_data = []
    
    # Lógica de agrupación de runs idéntica a la macro VBA
    run_tracker = {}
    mod_corner_history = {}

    # Ordenamos por fecha para simular el comportamiento secuencial del arreglo de VBA
    df_raw = df_raw.sort_values(by="ParsedDate").reset_index(drop=True)

    for _, r_item in df_raw.iterrows():
      f_date_str = str(r_item["ParsedDate"].date())
      p_val = r_item[part_col]
      base_key = f"{f_date_str}|{p_val}"
      f_name = r_item[feat_col]

      if base_key not in run_tracker:
        run_tracker[base_key] = 1
        mod_corner_history[base_key] = f_name
      else:
        if f_name in mod_corner_history[base_key]:
          run_tracker[base_key] += 1
          mod_corner_history[base_key] = f_name
        else:
          mod_corner_history[base_key] += f";{f_name}"

      current_run = run_tracker[base_key]
      r_item["CurrentRun"] = current_run
      r_item["BaseKey"] = base_key

    # Agrupamos por baseKey y Run para consolidar las 4 esquinas por batería/corrida
    grouped_runs = df_raw.groupby(["BaseKey", "CurrentRun"])

    for (b_key, c_run), group in grouped_runs:
      first_row = group.iloc[0]
      full_dt = first_row["ParsedDate"]
      cal_week = first_row["CalendarWeek"]
      bat_type = first_row["BatteryType"]
      p_val = first_row[part_col]

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
          "RunNum": c_run,
          "FL_X": corners[1][0], "FL_Y": corners[1][1],
          "FR_X": corners[2][0], "FR_Y": corners[2][1],
          "RL_X": corners[3][0], "RL_Y": corners[3][1],
          "RR_X": corners[4][0], "RR_Y": corners[4][1],
          "OutOfSpecCount": total_out_spec,
          "Status": status,
      })

    df_summary = pd.DataFrame(modules_data)
    df_summary = df_summary.sort_values(by="Date", ascending=True).reset_index(drop=True)

    cols = ["Date", "CalendarWeek", "PartID", "BatteryType", "RunNum", 
            "FL_X", "FL_Y", "FR_X", "FR_Y", "RL_X", "RL_Y", "RR_X", "RR_Y", 
            "OutOfSpecCount", "Status"]
    df_summary = df_summary[cols]

    tab1, tab2, tab3 = st.tabs([
        "📊 Resumen General (1 Línea por Batería)", 
        "📈 Gráfica Geométrica Interactiva", 
        "📐 Análisis de Escuadría"
    ])

    with tab1:
      st.subheader("Reporte General de Módulos (Orden Cronológico)")
      st.dataframe(style_report(df_summary, spec_limit), use_container_width=True)

      col1, col2, col3 = st.columns(3)
      total_modules = len(df_summary)
      passed_modules = len(df_summary[df_summary["Status"] == "PASS"])
      fpy = (passed_modules / total_modules * 100) if total_modules > 0 else 0

      col1.metric("Total de Baterías Inspeccionadas", total_modules)
      col2.metric(f"Aprobadas dentro de Spec (±{spec_limit}mm)", passed_modules)
      col3.metric("First-Pass Yield (FPY)", f"{fpy:.1f}%")

    with tab2:
      st.subheader("Visualización Geométrica por Batería")
      if not df_summary.empty:
        valid_plot_df = df_summary.dropna(subset=["FL_X", "FR_X", "RL_X", "RR_X"])
        if not valid_plot_df.empty:
          selected_idx = st.selectbox(
              "Selecciona una Batería (Fecha, PartID y Run):", 
              valid_plot_df.index, 
              format_func=lambda i: f"{df_summary.loc[i, 'Date']} | {df_summary.loc[i, 'PartID']} (Run {df_summary.loc[i, 'RunNum']}) [{df_summary.loc[i, 'Status']}]"
          )
          row_sel = df_summary.loc[selected_idx]
          
          fig = go.Figure()
          nom = get_nominal_coordinates(row_sel["BatteryType"])
          
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
              height=500, title=f"Batería: {row_sel['PartID']} (Run {row_sel['RunNum']})"
          )
          st.plotly_chart(fig, use_container_width=True)
        else:
          st.warning("No hay baterías con las 4 esquinas medidas simultáneamente para graficar.")

    with tab3:
      st.subheader("Análisis de Escuadría y Diagonales")
      squareness_records = []

      for _, row in df_summary.iterrows():
        if pd.isna(row["FL_X"]) or pd.isna(row["FR_X"]) or pd.isna(row["RL_X"]) or pd.isna(row["RR_X"]):
          continue
          
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
            "Date": row["Date"],
            "PartID": row["PartID"],
            "RunNum": row["RunNum"],
            "BatteryType": row["BatteryType"],
            "Diag Delta [mm]": round(delta_diags, 2),
            "Squareness Status": status,
        })

      df_squareness = pd.DataFrame(squareness_records)
      if not df_squareness.empty:
        st.dataframe(df_squareness, use_container_width=True)
      else:
        st.info("No hay suficientes datos completos de 4 esquinas para calcular escuadría.")

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
