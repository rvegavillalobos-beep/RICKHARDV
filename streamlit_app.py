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
