import io
import math
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

# Configuración de la página de Streamlit
st.set_page_config(
    page_title='Análisis de Metrología - Control Geométrico',
    page_icon='📊',
    layout='wide',
)

# --- CONSTANTES Y TOLERANCIAS ---
OUT_OF_SPEC_LIMIT = 1.0  # Límite en mm para desviaciones individuales (X, Y)
MAX_DIAG_DELTA_TOL = 1.5  # Tolerancia para diferencia de diagonales

# Valores nominales de referencia por tipo de batería (Ajustables según tus fixtures)
NOMINALS = {
    'TYPE S': {
        'FL_X': 0.0,
        'FL_Y': 0.0,
        'FR_X': 1000.0,
        'FR_Y': 0.0,
        'RL_X': 0.0,
        'RL_Y': 2000.0,
        'RR_X': 1000.0,
        'RR_Y': 2000.0,
    },
    'TYPE L': {
        'FL_X': 0.0,
        'FL_Y': 0.0,
        'FR_X': 1200.0,
        'FR_Y': 0.0,
        'RL_X': 0.0,
        'RL_Y': 2500.0,
        'RR_X': 1200.0,
        'RR_Y': 2500.0,
    },
}

# --- FUNCIONES AUXILIARES ---


def parse_english_datetime(val):
  if pd.isna(val):
    return pd.NaT
  if isinstance(val, (datetime, pd.Timestamp)):
    return val
  try:
    return pd.to_datetime(val)
  except Exception:
    try:
      return pd.to_datetime(val, format='%d/%m/%Y %H:%M:%S', errors='coerce')
    except:
      return pd.NaT


def determine_battery_type(part_id, feature_name):
  p_str = str(part_id).upper()
  f_str = str(feature_name).upper()
  if 'L' in p_str or 'LONG' in f_str:
    return 'TYPE L'
  return 'TYPE S'


def extract_corner_index(feature_name, battery_type):
  f_upper = str(feature_name).upper()
  if 'FL' in f_upper or 'FRONT_LEFT' in f_upper or 'F_L' in f_upper:
    return 'FL'
  elif 'FR' in f_upper or 'FRONT_RIGHT' in f_upper or 'F_R' in f_upper:
    return 'FR'
  elif 'RL' in f_upper or 'REAR_LEFT' in f_upper or 'R_L' in f_upper:
    return 'RL'
  elif 'RR' in f_upper or 'REAR_RIGHT' in f_upper or 'R_R' in f_upper:
    return 'RR'
  return 'UNKNOWN'


def calculate_corner_angle(x1, y1, x2, y2, x3, y3):
  v1 = np.array([x2 - x1, y2 - y1])
  v2 = np.array([x3 - x1, y3 - y1])
  cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
  cos_theta = np.clip(cos_theta, -1.0, 1.0)
  angle_rad = np.arccos(cos_theta)
  return np.degrees(angle_rad)


# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO (LÓGICA VBA) ---
@st.cache_data
def process_data(file):
  if file.name.endswith(('.xlsx', '.xls')):
    df_raw = pd.read_excel(file, header=None)
  else:
    df_raw = pd.read_csv(file, header=None)

  header_idx = 0
  for idx in range(min(15, len(df_raw))):
    row_values = [
        str(val).lower() for val in df_raw.iloc[idx].values if pd.notna(val)
    ]
    row_combined = ' '.join(row_values)
    if 'part id' in row_combined and (
        'feature' in row_combined or 'time' in row_combined
    ):
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
    if 'time' in c_lower or 'date' in c_lower:
      col_map[col] = 'Time'
    elif 'part' in c_lower:
      col_map[col] = 'PartID'
    elif 'feature' in c_lower:
      col_map[col] = 'FeatureName'
    elif c_lower in ['x deviation', 'valx', 'x']:
      col_map[col] = 'ValX'
    elif c_lower in ['y deviation', 'valy', 'y']:
      col_map[col] = 'ValY'
    elif c_lower in ['z deviation', 'valz', 'z']:
      col_map[col] = 'ValZ'

  df = df.rename(columns=col_map)
  df = df.dropna(subset=['PartID']).copy()

  df['DateTime'] = (
      df['Time'].apply(parse_english_datetime)
      if 'Time' in df.columns
      else pd.Timestamp.now()
  )
  df['ValX'] = pd.to_numeric(df.get('ValX', 0.0), errors='coerce').fillna(0.0)
  df['ValY'] = pd.to_numeric(df.get('ValY', 0.0), errors='coerce').fillna(0.0)
  df['ValZ'] = pd.to_numeric(df.get('ValZ', 0.0), errors='coerce').fillna(0.0)

  df['BatteryType'] = df.apply(
      lambda r: determine_battery_type(r['PartID'], r.get('FeatureName', '')),
      axis=1,
  )
  df['Corner'] = df.apply(
      lambda r: extract_corner_index(
          r.get('FeatureName', ''), r['BatteryType']
      ),
      axis=1,
  )
  df['DateFormatted'] = (
      df['DateTime'].dt.strftime('%Y-%m-%d').fillna('Unknown')
  )
  df['CW'] = df['DateTime'].apply(
      lambda dt: (
          f'CW{dt.isocalendar().week:02d}' if pd.notna(dt) else 'CW00'
      )
  )

  df = df.sort_values('DateTime').reset_index(drop=True)

  # --- DETECCIÓN DE RUNS POR REPETICIÓN DE FEATURE (ESTILO VBA) ---
  run_tracker = {}
  mod_corner_history = {}
  run_nums = []

  for idx, row in df.iterrows():
    date_str = row['DateFormatted']
    p_id = str(row['PartID'])
    f_name = str(row['FeatureName'])
    base_key = f'{date_str}|{p_id}'

    if base_key not in run_tracker:
      run_tracker[base_key] = 1
      mod_corner_history[base_key] = f_name
    else:
      if f_name in mod_corner_history[base_key]:
        run_tracker[base_key] += 1
        mod_corner_history[base_key] = f_name
      else:
        mod_corner_history[base_key] += f';{f_name}'

    run_nums.append(run_tracker[base_key])

  df['RunNum'] = run_nums
  df['RunGroup'] = (
      df['DateFormatted']
      + '|'
      + df['PartID']
      + '|RUN'
      + df['RunNum'].astype(str)
  )

  modules = []
  for run_group_key, group in df.groupby('RunGroup'):
    p_id = group['PartID'].iloc[0]
    b_type = group['BatteryType'].iloc[0]
    cw = group['CW'].iloc[0]
    dt_val = group['DateTime'].iloc[0]
    d_date = (
        pd.to_datetime(dt_val).strftime('%d/%m/%Y')
        if pd.notna(dt_val)
        else 'Unknown'
    )
    run_num = group['RunNum'].iloc[0]

    fl_row = group[group['Corner'] == 'FL']
    fr_row = group[group['Corner'] == 'FR']
    rl_row = group[group['Corner'] == 'RL']
    rr_row = group[group['Corner'] == 'RR']

    fl_dx = fl_row['ValX'].values[0] if not fl_row.empty else 0.0
    fl_dy = fl_row['ValY'].values[0] if not fl_row.empty else 0.0
    fr_dx = fr_row['ValX'].values[0] if not fr_row.empty else 0.0
    fr_dy = fr_row['ValY'].values[0] if not fr_row.empty else 0.0
    rl_dx = rl_row['ValX'].values[0] if not rl_row.empty else 0.0
    rl_dy = rl_row['ValY'].values[0] if not rl_row.empty else 0.0
    rr_dx = rr_row['ValX'].values[0] if not rr_row.empty else 0.0
    rr_dy = rr_row['ValY'].values[0] if not rr_row.empty else 0.0

    coords = [fl_dx, fl_dy, fr_dx, fr_dy, rl_dx, rl_dy, rr_dx, rr_dy]
    out_of_spec_count = sum(1 for c in coords if abs(c) > OUT_OF_SPEC_LIMIT)

    nom = NOMINALS.get(b_type, NOMINALS['TYPE S'])
    d1_nom = math.sqrt(
        (nom['RR_X'] - nom['FL_X']) ** 2 + (nom['RR_Y'] - nom['FL_Y']) ** 2
    )
    d2_nom = math.sqrt(
        (nom['RL_X'] - nom['FR_X']) ** 2 + (nom['RL_Y'] - nom['FR_Y']) ** 2
    )
    w_top_nom = math.sqrt(
        (nom['FR_X'] - nom['FL_X']) ** 2 + (nom['FR_Y'] - nom['FL_Y']) ** 2
    )
    w_bot_nom = math.sqrt(
        (nom['RR_X'] - nom['RL_X']) ** 2 + (nom['RR_Y'] - nom['RL_Y']) ** 2
    )
    l_left_nom = math.sqrt(
        (nom['RL_X'] - nom['FL_X']) ** 2 + (nom['RL_Y'] - nom['FL_Y']) ** 2
    )
    l_right_nom = math.sqrt(
        (nom['RR_X'] - nom['FR_X']) ** 2 + (nom['RR_Y'] - nom['FR_Y']) ** 2
    )
    angle_fl_nom = calculate_corner_angle(
        nom['FL_X'],
        nom['FL_Y'],
        nom['FR_X'],
        nom['FR_Y'],
        nom['RL_X'],
        nom['RL_Y'],
    )

    fl_x, fl_y = nom['FL_X'] + fl_dx, nom['FL_Y'] + fl_dy
    fr_x, fr_y = nom['FR_X'] + fr_dx, nom['FR_Y'] + fr_dy
    rl_x, rl_y = nom['RL_X'] + rl_dx, nom['RL_Y'] + rl_dy
    rr_x, rr_y = nom['RR_X'] + rr_dx, nom['RR_Y'] + rr_dy

    d1_act = math.sqrt((rr_x - fl_x) ** 2 + (rr_y - fl_y) ** 2)
    d2_act = math.sqrt((rl_x - fr_x) ** 2 + (rl_y - fr_y) ** 2)
    w_top_act = math.sqrt((fr_x - fl_x) ** 2 + (fr_y - fl_y) ** 2)
    w_bot_act = math.sqrt((rr_x - rl_x) ** 2 + (rr_y - rl_y) ** 2)
    l_left_act = math.sqrt((rl_x - fl_x) ** 2 + (rl_y - fl_y) ** 2)
    l_right_act = math.sqrt((rr_x - fr_x) ** 2 + (rr_y - fr_y) ** 2)
    angle_fl_act = calculate_corner_angle(
        fl_x, fl_y, fr_x, fr_y, rl_x, rl_y
    )

    delta_diags = abs((d1_act - d2_act) - (d1_nom - d2_nom))
    diff_ancho = (w_top_act - w_top_nom) - (w_bot_act - w_bot_nom)
    diff_largo = (l_left_act - l_left_nom) - (l_right_act - l_right_nom)
    angle_fl_dev = angle_fl_act - angle_fl_nom

    if delta_diags > MAX_DIAG_DELTA_TOL or out_of_spec_count > 0:
      status_str = 'DEFORMED'
      overall_pass = 'FAIL'
      detail_str = (
          f'Out-of-Spec Points ({out_of_spec_count})'
          if out_of_spec_count > 0
          else 'Geometric Distortion'
      )
    else:
      status_str = 'SQUARE OK'
      overall_pass = 'PASS'
      detail_str = 'Within Tolerance'

    modules.append({
        'DateTime': dt_val,
        'Date': d_date,
        'CW': cw,
        'PartID': p_id,
        'BatteryType': b_type,
        'FL_DX': fl_dx,
        'FL_DY': fl_dy,
        'FR_DX': fr_dx,
        'FR_DY': fr_dy,
        'RL_DX': rl_dx,
        'RL_DY': rl_dy,
        'RR_DX': rr_dx,
        'RR_DY': rr_dy,
        'Diag1_Act': d1_act,
        'Diag2_Act': d2_act,
        'DeltaDiagonals': delta_diags,
        'WidthDelta': diff_ancho,
        'LengthDelta': diff_largo,
        'AngleDevFL': angle_fl_dev,
        'Out_of_Spec_Points': out_of_spec_count,
        'SquareStatus': status_str,
        'OverallPass': overall_pass,
        'RootCause': detail_str,
        'RunNum': run_num,
        'RunStr': f'Run {run_num}',
    })

  df_mod = pd.DataFrame(modules)
  return df, df_mod


# --- INTERFAZ GRÁFICA DE STREAMLIT ---


def main():
  st.title('📊 Dashboard de Metrología y Control Geométrico')
  st.markdown(
      'Sistema automatizado de análisis para marcos de baterías y validación de'
      ' fixtures.'
  )

  uploaded_file = st.file_uploader(
      'Carga tu archivo de reporte de metrología (Excel o CSV)',
      type=['xlsx', 'xls', 'csv'],
  )

  if uploaded_file is not None:
    with st.spinner('Procesando datos y calculando geometría...'):
      try:
        df_raw, df_mod = process_data(uploaded_file)
      except Exception as e:
        st.error(f'Error al procesar el archivo: {e}')
        return

    st.success('¡Archivo procesado con éxito!')

    # Tarjetas de Métricas Superiores
    col1, col2, col3, col4 = st.columns(4)
    total_runs = len(df_mod)
    passes = len(df_mod[df_mod['OverallPass'] == 'PASS'])
    fails = len(df_mod[df_mod['OverallPass'] == 'FAIL'])
    pass_rate = (passes / total_runs * 100) if total_runs > 0 else 0

    col1.metric('Total Mediciones (Runs)', total_runs)
    col2.metric('Aprobados (PASS)', passes, delta=f'{pass_rate:.1f}%')
    col3.metric('Rechazados (FAIL)', fails)
    col4.metric('Límite de Tolerancia', f'±{OUT_OF_SPEC_LIMIT} mm')

    st.markdown('---')

    # Filtros laterales
    st.sidebar.header('Filtros de Búsqueda')
    selected_status = st.sidebar.selectbox(
        'Estatus General', ['TODOS', 'PASS', 'FAIL']
    )
    selected_date = st.sidebar.selectbox(
        'Fecha de Medición', ['TODAS'] + list(df_mod['Date'].unique())
    )

    filtered_df = df_mod.copy()
    if selected_status != 'TODOS':
      filtered_df = filtered_df[filtered_df['OverallPass'] == selected_status]
    if selected_date != 'TODAS':
      filtered_df = filtered_df[filtered_df['Date'] == selected_date]

    st.subheader(f'Resultados Filtrados ({len(filtered_df)} registros)')
    st.dataframe(filtered_df, use_container_width=True)

    # Exportación a Excel
    output = io.BytesIO()
 with pd.ExcelWriter(output) as writer:
      filtered_df.to_excel(writer, sheet_name='Resultados_Metrologia', index=False)
    processed_data = output.getvalue()

    st.download_button(
        label='📥 Descargar Reporte en Excel',
        data=processed_data,
        file_name='Reporte_Metrologia_Procesado.xlsx',
        mime=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
  else:
    st.info(
        '👉 Por favor, carga un archivo de datos (Excel o CSV) en la parte'
        ' superior para iniciar.'
    )


if __name__ == '__main__':
  main()
