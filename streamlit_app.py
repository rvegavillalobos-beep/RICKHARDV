import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import re

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

FAIL_THRESHOLD = 3.0

# -----------------------------------------------------------------------------
# LÓGICA DE PARSEO Y MAPPING EXACTO A LA MACRO VBA
# -----------------------------------------------------------------------------

def parse_english_datetime_strict(date_val):
    """
    Réplica exacta de ParseEnglishDateTimeStrict de VBA.
    Mapea meses en inglés, hora de 12 horas AM/PM y convierte a Datetime.
    """
    if pd.isna(date_val):
        return pd.NaT
    
    # Si ya es un objeto datetime o Timestamp
    if isinstance(date_val, (pd.Timestamp, pd.DatetimeIndex)):
        return date_val

    str_date = str(date_val).replace('\n', ' ').replace('\r', ' ').strip()
    if not str_date:
        return pd.NaT

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_val = None
    for idx, m in enumerate(months, 1):
        if m.lower() in str_date.lower():
            month_val = idx
            break

    try:
        clean_str = str_date.replace(',', '')
        tokens = [t for t in clean_str.split(' ') if t.strip()]
        
        if month_val and len(tokens) >= 4:
            day = int(tokens[1])
            year = int(tokens[2])
            time_str = tokens[3].lower()
            
            is_pm = 'pm' in time_str
            is_am = 'am' in time_str
            time_clean = time_str.replace('pm', '').replace('am', '')
            
            time_parts = time_clean.split(':')
            hour = int(time_parts[0]) if len(time_parts) > 0 and time_parts[0].isdigit() else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 and time_parts[1].isdigit() else 0
            
            if is_pm and hour < 12:
                hour += 12
            if is_am and hour == 12:
                hour = 0
                
            return pd.Timestamp(year=year, month=month_val, day=day, hour=hour, minute=minute)
    except Exception:
        pass

    # Fallback genérico de pandas
    dt_parsed = pd.to_datetime(str_date, errors='coerce')
    return dt_parsed if pd.notna(dt_parsed) else pd.Timestamp("1900-01-01")


def determine_battery_type(part_id, feature_name):
    """
    Réplica de DetermineBatteryType en VBA.
    """
    p_id = str(part_id).strip().upper() if pd.notna(part_id) else ""
    f_name = str(feature_name).strip().upper() if pd.notna(feature_name) else ""

    if "_DJ" in p_id or "_DJ" in f_name or "_M" in p_id or "-M" in p_id or "TYPE M" in p_id or "TYPEM" in p_id:
        return "Type M"
    if p_id.endswith("M") or p_id.endswith("_M"):
        return "Type M"

    if "_DA" in p_id or "_DA" in f_name or "_S" in p_id or "-S" in p_id or "TYPE S" in p_id or "TYPES" in p_id:
        return "Type S"

    return "Type S"


def extract_corner_index(feature_name, part_id, battery_type):
    """
    Réplica de ExtractCornerIndex en VBA.
    Retorna 1 (FL), 2 (FR), 3 (RL), 4 (RR) o 0 (No asignado).
    """
    if pd.isna(feature_name):
        return 0

    clean_feat = str(feature_name).lower().strip()
    if not clean_feat:
        return 0

    is_type_m = (battery_type == "Type M")

    if "72_l0324_aa" in clean_feat:
        return 1
    elif "72_r0301_aa" in clean_feat:
        return 2

    if is_type_m:
        if "72_l0324_dj" in clean_feat:
            return 3
        elif "72_r0301_dj" in clean_feat:
            return 4
    else:
        if "72_l0324_da" in clean_feat:
            return 3
        elif "72_r0302_da" in clean_feat:
            return 4

    # Fallbacks si no coincide con las reglas duras
    if "fl" in clean_feat or "c1" in clean_feat:
        return 1
    elif "fr" in clean_feat or "c2" in clean_feat:
        return 2
    elif "rl" in clean_feat or "c3" in clean_feat:
        return 3
    elif "rr" in clean_feat or "c4" in clean_feat:
        return 4

    return 0


# -----------------------------------------------------------------------------
# PROCESAMIENTO Y DEDUCCIÓN DE CORRIDAS (RUNS)
# -----------------------------------------------------------------------------

@st.cache_data
def process_data(file):
    # Carga de archivo raw
    if file.name.endswith(('.xlsx', '.xls')):
        df_raw = pd.read_excel(file, header=None)
    else:
        df_raw = pd.read_csv(file, header=None)

    # Identificación dinámica del renglón de encabezados
    header_idx = 0
    for idx in range(min(15, len(df_raw))):
        row_vals = [str(v).lower() for v in df_raw.iloc[idx].values if pd.notna(v)]
        row_str = " ".join(row_vals)
        if "part" in row_str and ("feature" in row_str or "time" in row_str or "date" in row_str):
            header_idx = idx
            break

    file.seek(0)
    if file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file, skiprows=header_idx)
    else:
        df = pd.read_csv(file, skiprows=header_idx)

    # Reestructuración y mapeo de columnas (Col 1: Date, Col 2: PartID, Col 3: Feature, Col 4: ValX, Col 7: ValY)
    cols = list(df.columns)
    date_col = cols[0]
    part_col = cols[1]
    feat_col = cols[2]
    valx_col = cols[3] if len(cols) > 3 else cols[0]
    valy_col = cols[6] if len(cols) > 6 else (cols[4] if len(cols) > 4 else cols[0])

    records = []
    for idx, row in df.iterrows():
        raw_date = row[date_col]
        p_id = str(row[part_col]).strip().replace('\r', '').replace('\n', '') if pd.notna(row[part_col]) else ""
        f_name = str(row[feat_col]).strip() if pd.notna(row[feat_col]) else ""

        if p_id != "" and pd.notna(raw_date):
            parsed_dt = parse_english_datetime_strict(raw_date)
            
            if parsed_dt != pd.Timestamp("1900-01-01"):
                formatted_date = parsed_dt.strftime('%Y-%m-%d')
                cal_week_num = parsed_dt.isocalendar().week
                cal_week_str = f"CW{cal_week_num:02d}"
            else:
                formatted_date = "1900-01-01"
                cal_week_str = "CW00"

            b_type = determine_battery_type(p_id, f_name)

            try:
                vx = float(row[valx_col]) if pd.notna(row[valx_col]) else 0.0
            except ValueError:
                vx = 0.0

            try:
                vy = float(row[valy_col]) if pd.notna(row[valy_col]) else 0.0
            except ValueError:
                vy = 0.0

            is_out_of_spec = (vx < -FAIL_THRESHOLD or vx > FAIL_THRESHOLD or vy < -FAIL_THRESHOLD or vy > FAIL_THRESHOLD)

            records.append({
                "FullDateTime": parsed_dt,
                "FormattedDate": formatted_date,
                "CalendarWeek": cal_week_str,
                "PartID": p_id,
                "BatteryType": b_type,
                "FeatureName": f_name,
                "ValX": vx,
                "ValY": vy,
                "IsOutOfSpec": is_out_of_spec
            })

    if not records:
        return pd.DataFrame(), pd.DataFrame()

    df_records = pd.DataFrame(records)

    # ORDENAMIENTO CRONOLÓGICO ESTRICTO (Equivalente al QuickSort en VBA)
    df_records = df_records.sort_values(by="FullDateTime").reset_index(drop=True)

    # LÓGICA DE DETECCIÓN DE RUNS Y DICCIONARIOS DE CONSOLIDACIÓN
    run_tracker = {}
    mod_corner_history = {}
    dict_modules = {}

    for _, rec in df_records.iterrows():
        base_key = f"{rec['FormattedDate']}|{rec['PartID']}"

        if base_key not in run_tracker:
            run_tracker[base_key] = 1
            mod_corner_history[base_key] = rec['FeatureName']
        else:
            if rec['FeatureName'] in mod_corner_history[base_key]:
                run_tracker[base_key] += 1
                mod_corner_history[base_key] = rec['FeatureName']
            else:
                mod_corner_history[base_key] += ";" + rec['FeatureName']

        current_run = run_tracker[base_key]
        full_module_key = f"{base_key}|RUN{current_run}"
        
        c_num = extract_corner_index(rec['FeatureName'], rec['PartID'], rec['BatteryType'])

        if full_module_key not in dict_modules:
            mod_data = {
                "Date": rec['FullDateTime'].strftime('%d/%m/%Y') if rec['FullDateTime'] != pd.Timestamp("1900-01-01") else "1900-01-01",
                "DateTime": rec['FullDateTime'],
                "PartID": rec['PartID'],
                "BatteryType": rec['BatteryType'],
                "CalendarWeek": rec['CalendarWeek'],
                "RunNum": current_run,
                "OutOfSpecCount": 1 if rec['IsOutOfSpec'] else 0,
                "FL_X": None, "FL_Y": None,
                "FR_X": None, "FR_Y": None,
                "RL_X": None, "RL_Y": None,
                "RR_X": None, "RR_Y": None
            }

            if 1 <= c_num <= 4:
                corners_map = {1: ("FL_X", "FL_Y"), 2: ("FR_X", "FR_Y"), 3: ("RL_X", "RL_Y"), 4: ("RR_X", "RR_Y")}
                kx, ky = corners_map[c_num]
                mod_data[kx] = rec['ValX']
                mod_data[ky] = rec['ValY']

            dict_modules[full_module_key] = mod_data
        else:
            mod_data = dict_modules[full_module_key]

            # PROMOCIÓN DINÁMICA DE TIPO (Type S -> Type M)
            if mod_data["BatteryType"] == "Type S" and rec['BatteryType'] == "Type M":
                mod_data["BatteryType"] = "Type M"

            if rec['IsOutOfSpec']:
                mod_data["OutOfSpecCount"] += 1

            if 1 <= c_num <= 4:
                corners_map = {1: ("FL_X", "FL_Y"), 2: ("FR_X", "FR_Y"), 3: ("RL_X", "RL_Y"), 4: ("RR_X", "RR_Y")}
                kx, ky = corners_map[c_num]
                mod_data[kx] = rec['ValX']
                mod_data[ky] = rec['ValY']

            dict_modules[full_module_key] = mod_data

    # CONSTRUCCIÓN DEL DATAFRAME FINAL DE MÓDULOS
    modules_list = []
    for key, item in dict_modules.items():
        out_spec_pts = item["OutOfSpecCount"]
        
        # REGLA 1 SOLUCIONADA: FAIL únicamente si out_spec_pts > 0 (Desviaciones >= +/-3.0mm)
        overall_pass = "FAIL" if out_spec_pts > 0 else "PASS"

        modules_list.append({
            "Date": item["Date"],
            "DateTime": item["DateTime"],
            "CW": item["CalendarWeek"],
            "PartID": item["PartID"],
            "BatteryType": item["BatteryType"],
            "RunNum": item["RunNum"],
            "Run": f"Run {item['RunNum']}",
            "FL_X": item["FL_X"] if item["FL_X"] is not None else 0.0,
            "FL_Y": item["FL_Y"] if item["FL_Y"] is not None else 0.0,
            "FR_X": item["FR_X"] if item["FR_X"] is not None else 0.0,
            "FR_Y": item["FR_Y"] if item["FR_Y"] is not None else 0.0,
            "RL_X": item["RL_X"] if item["RL_X"] is not None else 0.0,
            "RL_Y": item["RL_Y"] if item["RL_Y"] is not None else 0.0,
            "RR_X": item["RR_X"] if item["RR_X"] is not None else 0.0,
            "RR_Y": item["RR_Y"] if item["RR_Y"] is not None else 0.0,
            "OutOfSpecPoints": out_spec_pts,
            "OverallPass": overall_pass
        })

    df_modules = pd.DataFrame(modules_list)
    return df_records, df_modules


# -----------------------------------------------------------------------------
# INTERFAZ STREAMLIT
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Carga de Datos y Filtros")
uploaded_file = st.sidebar.file_uploader("Cargar reporte Raw (CSV o Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    df_raw, df_modules = process_data(uploaded_file)

    if df_modules.empty:
        st.error("No se encontraron registros válidos para procesar.")
    else:
        cw_list = sorted(df_modules["CW"].unique())
        selected_cw = st.sidebar.multiselect("Calendar Week (CW)", options=cw_list, default=cw_list)
        
        type_list = sorted(df_modules["BatteryType"].unique())
        selected_type = st.sidebar.multiselect("Tipo de Batería", options=type_list, default=type_list)

        df_filtered = df_modules[
            (df_modules["CW"].isin(selected_cw)) & 
            (df_modules["BatteryType"].isin(selected_type))
        ]

        tab1, tab2 = st.tabs(["📊 Executive Dashboard & Runs", "📐 Vector Shift Visualizer"])

        with tab1:
            st.subheader("📊 Executive Quality & FPY Performance")

            # Módulos de Primera Corrida (Run 1)
            df_run1 = df_filtered[df_filtered["RunNum"] == 1]

            total_mod = len(df_run1)
            pass_mod = len(df_run1[df_run1["OverallPass"] == "PASS"])
            fail_mod = len(df_run1[df_run1["OverallPass"] == "FAIL"])
            fpy_global = (pass_mod / total_mod * 100) if total_mod > 0 else 0.0

            summary_df = pd.DataFrame({
                "Metric": ["Unique Modules Tested (First-Run)", "Passed First-Run (OK)", "Failed First-Run (NOK)", "First-Pass Yield (FPY)"],
                "Value": [f"{total_mod}", f"{pass_mod}", f"{fail_mod}", f"{fpy_global:.1f}%"]
            })
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            st.divider()

            st.markdown("### 📑 Detailed Measurement Log (All Runs & Retests)")

            display_runs = df_filtered[[
                "Date", "CW", "PartID", "BatteryType", "Run",
                "FL_X", "FL_Y", "FR_X", "FR_Y", "RL_X", "RL_Y", "RR_X", "RR_Y",
                "OutOfSpecPoints", "OverallPass"
            ]].rename(columns={
                "PartID": "Part ID (Module)",
                "BatteryType": "Type",
                "Run": "Run #",
                "OutOfSpecPoints": "Out-of-Spec Points",
                "OverallPass": "Module Status"
            })

            def style_run_table(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                dev_cols = ["FL_X", "FL_Y", "FR_X", "FR_Y", "RL_X", "RL_Y", "RR_X", "RR_Y"]

                # Destacar celdas con desviaciones >= +/- 3.0 mm
                for col in dev_cols:
                    mask = df[col].apply(lambda v: abs(v) >= FAIL_THRESHOLD)
                    styles.loc[mask, col] = 'background-color: #f8d7da; color: #721c24; font-weight: bold;'

                pass_mask = df["Module Status"] == "PASS"
                fail_mask = df["Module Status"] == "FAIL"
                styles.loc[pass_mask, "Module Status"] = 'background-color: #d4edda; color: #155724; font-weight: bold;'
                styles.loc[fail_mask, "Module Status"] = 'background-color: #f8d7da; color: #721c24; font-weight: bold;'

                return styles

            formatted_runs = display_runs.style.apply(style_run_table, axis=None).format({
                "FL_X": "{:.2f}", "FL_Y": "{:.2f}",
                "FR_X": "{:.2f}", "FR_Y": "{:.2f}",
                "RL_X": "{:.2f}", "RL_Y": "{:.2f}",
                "RR_X": "{:.2f}", "RR_Y": "{:.2f}",
                "Out-of-Spec Points": "{:d}"
            })

            st.dataframe(formatted_runs, use_container_width=True, hide_index=True, height=500)

        with tab2:
            st.subheader("📐 Vector Shift Visualizer")
            df_filtered["Part_Run_Label"] = df_filtered["PartID"] + " (" + df_filtered["Run"] + ")"
            all_labels = list(df_filtered["Part_Run_Label"].unique())

            if all_labels:
                selected_label = st.selectbox("Seleccionar Módulo y Corrida:", all_labels)
                row = df_filtered[df_filtered["Part_Run_Label"] == selected_label].iloc[0]

                st.write(f"**Estatus:** {row['OverallPass']} | **Puntos fuera de especificación (>= 3.0mm):** {row['OutOfSpecPoints']}")

else:
    st.info("👆 Por favor sube un archivo `.xlsx` o `.csv` en la barra lateral.")
