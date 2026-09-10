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

# Initialize Session State for cross-tab module selection
if "selected_mod_target" not in st.session_state:
    st.session_state["selected_mod_target"] = "--- None / All ---"


def determine_battery_type(part_id: str, feature_names) -> str:
    """Determina si la batería es Type M o Type S evaluando el PartID y el conjunto completo de Features."""
    p_id = str(part_id).upper().strip()

    if isinstance(feature_names, (list, set, pd.Series)):
        f_combined = " ".join([str(f).upper().strip() for f in feature_names])
    else:
        f_combined = str(feature_names).upper().strip()

    if (
        "_DJ" in p_id
        or "_DJ" in f_combined
        or "_DI" in p_id
        or "_DI" in f_combined
    ):
        return "Type M"
    if (
        "_M" in p_id
        or "-M" in p_id
        or "TYPE M" in p_id
        or "TYPEM" in p_id
        or p_id.endswith("M")
    ):
        return "Type M"

    if "_DA" in p_id or "_DA" in f_combined:
        return "Type S"
    if "_S" in p_id or "-S" in p_id or "TYPE S" in p_id or "TYPES" in p_id:
        return "Type S"

    return "Type S"


def extract_corner_index(feature_name: str, part_id: str) -> int:
    f = str(feature_name).lower().strip()
    if not f:
        return 0

    is_type_m = determine_battery_type(part_id, feature_name) == "Type M"

    if "l0324_aa" in f or "l324_aa" in f:
        return 1
    if "r0301_aa" in f or "r301_aa" in f:
        return 2

    if is_type_m:
        if any(k in f for k in ["l0324_dj", "l324_dj", "l0324_di", "l324_di"]):
            return 3
        if any(k in f for k in ["r0301_dj", "r301_dj", "r0301_di", "r301_di"]):
            return 4
    else:
        if "l0324_da" in f or "l324_da" in f:
            return 3
        if "r0302_da" in f or "r302_da" in f:
            return 4

    if "fl" in f or "c1" in f:
        return 1
    elif "fr" in f or "c2" in f:
        return 2
    elif "rl" in f or "c3" in f:
        return 3
    elif (
        "rr" in f or "c4" in f or "r302" in f or "r301" in f or "r00301" in f
    ):
        return 4

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
    else:
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


def calculate_corner_angle(a, b, c):
    v_ab = np.array(b) - np.array(a)
    v_ac = np.array(c) - np.array(a)
    dot_prod = np.dot(v_ab, v_ac)
    mag_ab = np.linalg.norm(v_ab)
    mag_ac = np.linalg.norm(v_ac)
    if mag_ab == 0 or mag_ac == 0:
        return 0.0
    cos_theta = np.clip(dot_prod / (mag_ab * mag_ac), -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))


def evaluate_deformation(
    delta_diags, angle_fl_dev, diff_ancho, diff_largo, max_diag_tol
):
    angular_dev_tol = 0.15
    dim_delta_tol = 0.8
    if delta_diags > max_diag_tol:
        status = "DEFORMED"
        if (
            abs(angle_fl_dev) > angular_dev_tol
            and abs(diff_ancho) < dim_delta_tol
        ):
            detail = f"PARALLELOGRAM DISTORTION (Tilt: {angle_fl_dev:+.2f}°)"
        elif abs(diff_ancho) >= dim_delta_tol:
            detail = f"TRAPEZOIDAL WIDTH VARIATION (Delta: {diff_ancho:+.2f} mm)"
        elif abs(diff_largo) >= dim_delta_tol:
            detail = (
                f"TRAPEZOIDAL LENGTH VARIATION (Delta: {diff_largo:+.2f} mm)"
            )
        else:
            detail = (
                f"COMBINED ASYMMETRY (Diagonal Delta: {delta_diags:.2f} mm)"
            )
    else:
        status = "SQUARE OK"
        detail = "Geometry within acceptable tolerance"
    return status, detail


def style_report(df, limit):
    cols_to_check = [
        "FL_X",
        "FL_Y",
        "FR_X",
        "FR_Y",
        "RL_X",
        "RL_Y",
        "RR_X",
        "RR_Y",
    ]

    def apply_styles(row):
        styles = [""] * len(row)
        for i, col in enumerate(row.index):
            if col in cols_to_check:
                val = row[col]
                if val is not None and not pd.isna(val):
                    try:
                        if abs(float(val)) > limit:
                            styles[i] = (
                                "background-color: #ff4d4d; color: white;"
                                " font-weight: bold;"
                            )
                    except:
                        pass
            elif col == "CornersOutOfSpec":
                val = row[col]
                if val is not None and not pd.isna(val) and int(val) > 0:
                    styles[i] = (
                        "background-color: #d97706; color: white;"
                        " font-weight: bold;"
                    )
            elif col == "Status":
                if str(row[col]) == "FAIL":
                    styles[i] = (
                        "background-color: #ff4d4d; color: white; font-weight:"
                        " bold;"
                    )
                elif str(row[col]) == "PASS":
                    styles[i] = (
                        "background-color: #2eb82e; color: white; font-weight:"
                        " bold;"
                    )
                elif str(row[col]) == "INCOMPLETE":
                    styles[i] = (
                        "background-color: #6b7280; color: white; font-weight:"
                        " bold;"
                    )
        return styles

    return df.style.apply(apply_styles, axis=1)


def style_squareness_report(df, diag_limit):
    def apply_styles(row):
        styles = [""] * len(row)
        for i, col in enumerate(row.index):
            if col == "Delta Diag [mm]" and pd.notna(row[col]):
                try:
                    if float(row[col]) > diag_limit:
                        styles[i] = (
                            "background-color: #ff4d4d; color: white;"
                            " font-weight: bold;"
                        )
                except:
                    pass
            if col == "Squareness Status" and str(row[col]) == "DEFORMED":
                styles[i] = (
                    "background-color: #ff4d4d; color: white; font-weight:"
                    " bold;"
                )
        return styles

    return df.style.apply(apply_styles, axis=1)


def plot_corner_deviation(df_corner, title_name, threshold_val):
    if df_corner.empty:
        return go.Figure()

    df_corner = df_corner.sort_values(by="Date", ascending=True).reset_index(
        drop=True
    )
    df_corner["Seq"] = range(1, len(df_corner) + 1)
    df_corner["Date_Str"] = df_corner["Date"].dt.strftime("%Y-%m-%d %H:%M")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_corner["Seq"],
            y=df_corner["Dev_X"],
            mode="lines+markers",
            name="X",
            line=dict(color="#D92B2B", width=1.5),
            marker=dict(size=4),
            customdata=df_corner[["PartID", "Date_Str", "CalendarWeek"]],
            hovertemplate=(
                "<b>Batería #%{x}</b><br>PartID: %{customdata[0]}<br>Fecha:"
                " %{customdata[1]}<br>CW: %{customdata[2]}<br>Dev X: %{y:.2f}"
                " mm<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_corner["Seq"],
            y=df_corner["Dev_Y"],
            mode="lines+markers",
            name="Y",
            line=dict(color="#27AE60", width=1.5),
            marker=dict(size=4),
            customdata=df_corner[["PartID", "Date_Str", "CalendarWeek"]],
            hovertemplate=(
                "<b>Batería #%{x}</b><br>PartID: %{customdata[0]}<br>Fecha:"
                " %{customdata[1]}<br>CW: %{customdata[2]}<br>Dev Y: %{y:.2f}"
                " mm<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=threshold_val,
        line_color="#D92B2B",
        line_width=1.5,
        annotation_text=f"+{threshold_val:.1f}mm",
        annotation_position="top right",
    )

    fig.add_hline(
        y=-threshold_val,
        line_color="#D92B2B",
        line_width=1.5,
        annotation_text=f"-{threshold_val:.1f}mm",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title=dict(
            text=f"<b>{title_name}</b>",
            x=0.5,
            xanchor="center",
            font=dict(color="#D92B2B", size=13),
        ),
        xaxis=dict(
            title="Batería # (Orden Cronológico)",
            showgrid=True,
            gridcolor="#E5E5E5",
        ),
        yaxis=dict(
            title="Desviación (mm)",
            showgrid=True,
            gridcolor="#E5E5E5",
            zeroline=True,
            zerolinecolor="#888888",
            range=[-threshold_val - 2.5, threshold_val + 2.5],
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


def render_battery_corner_matrix(df_battery, battery_type_name, threshold_val):
    st.subheader(f"🔋 {battery_type_name} Corner Deviation Trend (Sequential)")

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    df_fl = df_battery[df_battery["Corner"] == "Front-Left"]
    df_fr = df_battery[df_battery["Corner"] == "Front-Right"]
    df_rl = df_battery[df_battery["Corner"] == "Rear-Left"]
    df_rr = df_battery[df_battery["Corner"] == "Rear-Right"]

    with row1_col1:
        st.plotly_chart(
            plot_corner_deviation(
                df_fl, "Front-Left Corner (FL)", threshold_val
            ),
            use_container_width=True,
        )

    with row1_col2:
        st.plotly_chart(
            plot_corner_deviation(
                df_fr, "Front-Right Corner (FR)", threshold_val
            ),
            use_container_width=True,
        )

    with row2_col1:
        st.plotly_chart(
            plot_corner_deviation(
                df_rl, "Rear-Left Corner (RL)", threshold_val
            ),
            use_container_width=True,
        )

    with row2_col2:
        st.plotly_chart(
            plot_corner_deviation(
                df_rr, "Rear-Right Corner (RR)", threshold_val
            ),
            use_container_width=True,
        )


# ==============================================================================
# APLICACIÓN PRINCIPAL
# ==============================================================================
st.title("⚙️ Quality Control & Geometric Analysis Module")

st.sidebar.header("🛠️ Configuration & Tolerances")
max_diag_tol = st.sidebar.slider(
    "Max. Diagonal Delta Tolerance [mm]", 1.0, 10.0, 1.5, 0.5
)
spec_limit = st.sidebar.slider(
    "X/Y Specification Limit [±mm]", 1.0, 5.0, 3.0, 0.5
)

exclude_incomplete = st.sidebar.checkbox(
    "Excluir mediciones incompletas (esquinas faltantes)",
    value=False,
    help=(
        "Excluye del análisis y métricas (Summary, FPY, Trend) las corridas o"
        " baterías que no tengan el conjunto completo de sus 4 esquinas."
    ),
)

uploaded_file = st.file_uploader(
    "Upload your raw data file (Excel or CSV)", type=["xlsx", "xls", "csv"]
)

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
        x_dev_col = [
            c
            for c in df_raw.columns
            if "x" in c.lower() and "deviation" in c.lower()
        ][0]
        y_dev_col = [
            c
            for c in df_raw.columns
            if "y" in c.lower() and "deviation" in c.lower()
        ][0]

        df_raw["ParsedDate"] = pd.to_datetime(
            df_raw[time_col], errors="coerce"
        )
        df_raw["CalendarWeek"] = (
            "CW"
            + df_raw["ParsedDate"]
            .dt.isocalendar()
            .week.astype(str)
            .str.zfill(2)
        )
        df_raw["BatteryType"] = df_raw.apply(
            lambda row: determine_battery_type(row[part_col], row[feat_col]),
            axis=1,
        )
        df_raw["CornerIndex"] = df_raw.apply(
            lambda row: extract_corner_index(row[feat_col], row[part_col]),
            axis=1,
        )

        # MANTENER NaN EN LUGAR DE CONVERTIR A CERO
        df_raw["X_Val"] = pd.to_numeric(df_raw[x_dev_col], errors="coerce")
        df_raw["Y_Val"] = pd.to_numeric(df_raw[y_dev_col], errors="coerce")

        df_raw = df_raw.sort_values(by="ParsedDate").reset_index(drop=True)

        base_keys = []
        current_runs = []
        run_tracker = {}
        mod_corner_history = {}

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

            base_keys.append(base_key)
            current_runs.append(run_tracker[base_key])

        df_raw["BaseKey"] = base_keys
        df_raw["CurrentRun"] = current_runs

        modules_data = []
        grouped_runs = df_raw.groupby(["BaseKey", "CurrentRun"])

        for (b_key, c_run), group in grouped_runs:
            first_row = group.iloc[0]
            full_dt = first_row["ParsedDate"]
            cal_week = first_row["CalendarWeek"]
            p_val = first_row[part_col]

            bat_type = determine_battery_type(p_val, group[feat_col])

            corners = {
                1: (np.nan, np.nan),
                2: (np.nan, np.nan),
                3: (np.nan, np.nan),
                4: (np.nan, np.nan),
            }

            for _, r_item in group.iterrows():
                c_idx = r_item["CornerIndex"]
                if c_idx in [1, 2, 3, 4]:
                    corners[c_idx] = (r_item["X_Val"], r_item["Y_Val"])

            corners_out_of_spec = 0
            missing_corners = 0

            for c_idx in [1, 2, 3, 4]:
                cx, cy = corners[c_idx]
                if pd.isna(cx) or pd.isna(cy):
                    missing_corners += 1
                else:
                    if abs(cx) > spec_limit or abs(cy) > spec_limit:
                        corners_out_of_spec += 1

            is_complete = missing_corners == 0

            if not is_complete:
                status = "INCOMPLETE"
            elif corners_out_of_spec > 0:
                status = "FAIL"
            else:
                status = "PASS"

            modules_data.append({
                "Date": full_dt,
                "CalendarWeek": cal_week,
                "PartID": p_val,
                "BaseKey": b_key,
                "BatteryType": bat_type,
                "RunNum": c_run,
                "FL_X": corners[1][0],
                "FL_Y": corners[1][1],
                "FR_X": corners[2][0],
                "FR_Y": corners[2][1],
                "RL_X": corners[3][0],
                "RL_Y": corners[3][1],
                "RR_X": corners[4][0],
                "RR_Y": corners[4][1],
                "CornersOutOfSpec": corners_out_of_spec,
                "MissingCorners": missing_corners,
                "IsComplete": is_complete,
                "Status": status,
            })

        df_summary = pd.DataFrame(modules_data)
        df_summary = df_summary.sort_values(
            by=["Date", "RunNum"], ascending=True
        ).reset_index(drop=True)

        cols = [
            "Date",
            "CalendarWeek",
            "PartID",
            "BatteryType",
            "RunNum",
            "FL_X",
            "FL_Y",
            "FR_X",
            "FR_Y",
            "RL_X",
            "RL_Y",
            "RR_X",
            "RR_Y",
            "CornersOutOfSpec",
            "MissingCorners",
            "IsComplete",
            "Status",
        ]
        df_summary = df_summary[cols]

        # SELECCIÓN DE LA PRIMERA CORRIDA COMPLETA POR BATERÍA
        first_complete_records = []
        for b_key, group in df_summary.groupby("PartID"):
            complete_runs = group[group["IsComplete"] == True]
            if not complete_runs.empty:
                first_complete_records.append(complete_runs.iloc[0])
            else:
                first_complete_records.append(group.iloc[0])

        df_first_complete = pd.DataFrame(first_complete_records)

        # FILTRADO SEGÚN EL TOGGLE
        if exclude_incomplete:
            df_analysis = df_summary[df_summary["IsComplete"] == True].copy()
            df_first_valid = df_first_complete[
                df_first_complete["IsComplete"] == True
            ].copy()
            st.sidebar.warning(
                "⚠️ Excluyendo corridas/mediciones incompletas."
            )
        else:
            df_analysis = df_summary.copy()
            df_first_valid = df_first_complete.copy()

        # Pestañas de análisis
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 General Summary & FPY",
            "📈 Interactive Geometric Plot",
            "📐 Squareness Analysis",
            "🧭 Vector Drift & Conveyor Tuning",
        ])

        with tab1:
            st.subheader("📋 First Complete Measurement Quality Summary")

            if exclude_incomplete:
                st.info(
                    "ℹ️ **Filtro activo:** Se han excluido del análisis las"
                    " corridas incompletas."
                )

            total_valid_modules = len(df_first_valid)
            passed_valid = len(df_first_valid[df_first_valid["Status"] == "PASS"])
            failed_valid = len(df_first_valid[df_first_valid["Status"] == "FAIL"])
            incomplete_valid = len(
                df_first_valid[df_first_valid["Status"] == "INCOMPLETE"]
            )
            fpy_val = (
                (passed_valid / total_valid_modules * 100)
                if total_valid_modules > 0
                else 0
            )

            summary_table_data = {
                "Metric": [
                    "Unique Modules Evaluated",
                    "Passed First Complete Run (OK)",
                    "Failed First Complete Run (NOK)",
                    "Incomplete Measurements",
                    "First-Pass Yield (FPY)",
                ],
                "Value": [
                    total_valid_modules,
                    passed_valid,
                    failed_valid,
                    incomplete_valid,
                    f"{fpy_val:.1f}%",
                ],
            }
            df_quality_summary = pd.DataFrame(summary_table_data)

            col_t1, col_t2 = st.columns([1.2, 2.8])
            with col_t1:
                st.markdown("##### OVERALL SUMMARY")
                st.dataframe(
                    df_quality_summary,
                    hide_index=True,
                    use_container_width=True,
                )

            with col_t2:
                st.markdown("##### WEEKLY FIRST-PASS YIELD TREND")
                if not df_first_valid.empty:
                    weekly_group = df_first_valid.groupby("CalendarWeek")
                    weekly_data = []
                    for w, w_group in weekly_group:
                        w_total = len(w_group)
                        w_passed = len(w_group[w_group["Status"] == "PASS"])
                        w_failed = len(w_group[w_group["Status"] == "FAIL"])
                        w_rate = (
                            (w_passed / w_total * 100) if w_total > 0 else 0
                        )
                        w_fail_rate = (
                            (w_failed / w_total * 100) if w_total > 0 else 0
                        )
                        weekly_data.append({
                            "CalendarWeek": w,
                            "Total": w_total,
                            "Passed": w_passed,
                            "Failed": w_failed,
                            "PassRate": w_rate,
                            "FailRate": w_fail_rate,
                        })
                    df_weekly = pd.DataFrame(weekly_data)

                    passed_text = [
                        str(v) if v > 0 else "" for v in df_weekly["Passed"]
                    ]
                    failed_text = [
                        str(v) if v > 0 else "" for v in df_weekly["Failed"]
                    ]

                    fig_weekly = go.Figure()
                    fig_weekly.add_trace(
                        go.Bar(
                            x=df_weekly["CalendarWeek"],
                            y=df_weekly["PassRate"],
                            name="Passed (OK)",
                            marker_color="#0f766e",
                            text=passed_text,
                            textposition="inside",
                            insidetextanchor="middle",
                        )
                    )
                    fig_weekly.add_trace(
                        go.Bar(
                            x=df_weekly["CalendarWeek"],
                            y=df_weekly["FailRate"],
                            name="Failed (NOK)",
                            marker_color="#e11d48",
                            text=failed_text,
                            textposition="inside",
                            insidetextanchor="middle",
                        )
                    )
                    fig_weekly.update_layout(
                        barmode="stack",
                        yaxis=dict(range=[0, 105], title="Percentage (%)"),
                        xaxis=dict(title="Calendar Week"),
                        height=350,
                        margin=dict(l=20, r=20, t=30, b=20),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                        ),
                    )
                    fig_weekly.add_hline(
                        y=fpy_val,
                        line_dash="dash",
                        line_color="#d97706",
                        annotation_text=f"Overall FPY: {fpy_val:.1f}%",
                        annotation_position="top right",
                    )
                    st.plotly_chart(fig_weekly, use_container_width=True)
                else:
                    st.info("No data available to generate the weekly trend.")

            st.markdown("---")
            st.markdown("##### 📅 WEEKLY PASS RATE & BREAKDOWN TABLE")
            if not df_first_valid.empty:
                df_weekly_display = df_weekly[
                    ["CalendarWeek", "Total", "Passed", "Failed", "PassRate"]
                ].copy()
                df_weekly_display["PassRate"] = df_weekly_display[
                    "PassRate"
                ].apply(lambda x: f"{x:.1f}%")
                df_weekly_display.columns = [
                    "Calendar Week",
                    "Total Parts",
                    "Passed (OK)",
                    "Failed (NOK)",
                    "Pass Rate (FPY)",
                ]
                st.dataframe(
                    df_weekly_display,
                    hide_index=True,
                    use_container_width=True,
                )

            st.markdown("---")
            st.subheader("General Module Report (Chronological Order)")
            st.dataframe(
                style_report(df_analysis, spec_limit), use_container_width=True
            )

            st.divider()
            st.header("📈 Análisis Temporal de Desviación por Esquinas (2x2 Matrix)")

            corner_records = []
            for _, row in df_first_valid.iterrows():
                cw = row["CalendarWeek"]
                b_type = row["BatteryType"]
                dt = row["Date"]
                p_id = row["PartID"]

                corner_map = {
                    "Front-Left": (row["FL_X"], row["FL_Y"]),
                    "Front-Right": (row["FR_X"], row["FR_Y"]),
                    "Rear-Left": (row["RL_X"], row["RL_Y"]),
                    "Rear-Right": (row["RR_X"], row["RR_Y"]),
                }

                for c_name, (dx, dy) in corner_map.items():
                    if pd.notna(dx) and pd.notna(dy):
                        corner_records.append({
                            "CalendarWeek": cw,
                            "Date": dt,
                            "PartID": p_id,
                            "Battery_Type": b_type,
                            "Corner": c_name,
                            "Dev_X": dx,
                            "Dev_Y": dy,
                        })

            df_corner_trends = pd.DataFrame(corner_records)

            if not df_corner_trends.empty:
                df_m_trend = df_corner_trends[
                    df_corner_trends["Battery_Type"] == "Type M"
                ]
                if not df_m_trend.empty:
                    render_battery_corner_matrix(
                        df_m_trend, "Type M", spec_limit
                    )
                else:
                    st.info("No hay registros disponibles para Type M.")

                st.markdown("<br>", unsafe_allow_html=True)

                df_s_trend = df_corner_trends[
                    df_corner_trends["Battery_Type"] == "Type S"
                ]
                if not df_s_trend.empty:
                    render_battery_corner_matrix(
                        df_s_trend, "Type S", spec_limit
                    )
                else:
                    st.info("No hay registros disponibles para Type S.")
            else:
                st.warning(
                    "No hay datos suficientes de esquinas completas para"
                    " generar las gráficas de tendencia."
                )

        with tab2:
            st.subheader(
                "📈 Real Geometric Visualization (Permanent Tolerance Zones)"
            )

            if not df_analysis.empty:
                total_mods = len(df_analysis)

                col_ctrl1, col_ctrl2 = st.columns(2)
                with col_ctrl1:
                    default_start = max(0, total_mods - 10)
                    default_end = max(0, total_mods - 1)
                    selected_range = st.slider(
                        "Select Battery Range (Index):",
                        min_value=0,
                        max_value=max(0, total_mods - 1),
                        value=(default_start, default_end),
                        step=1,
                    )
                with col_ctrl2:
                    exaggeration = st.slider(
                        "Deviation Exaggeration Factor:",
                        min_value=1.0,
                        max_value=20.0,
                        value=1.0,
                        step=0.5,
                    )

                selected_mod = st.session_state["selected_mod_target"]
                if selected_mod != "--- None / All ---":
                    st.info(
                        f"🔍 **Module selected for plot focus:**"
                        f" `{selected_mod}` (Highlighted in bright cyan)"
                    )

                start_idx, end_idx = selected_range
                df_to_plot = df_analysis.iloc[
                    start_idx : end_idx + 1
                ].copy()

                fig = go.Figure()

                all_battery_types = df_analysis["BatteryType"].unique()
                for b_type in all_battery_types:
                    nom = get_nominal_coordinates(b_type)
                    nom_x = [
                        nom["RL_X"],
                        nom["FL_X"],
                        nom["FR_X"],
                        nom["RR_X"],
                        nom["RL_X"],
                    ]
                    nom_y = [
                        nom["RL_Y"],
                        nom["FL_Y"],
                        nom["FR_Y"],
                        nom["RR_Y"],
                        nom["RL_Y"],
                    ]

                    fig.add_trace(
                        go.Scatter(
                            x=nom_x,
                            y=nom_y,
                            mode="lines",
                            name=f"Nominal Baseline ({b_type})",
                            line=dict(color="green", width=2, dash="dash"),
                        )
                    )

                    corners_dict = {
                        "FL": (nom["FL_X"], nom["FL_Y"]),
                        "FR": (nom["FR_X"], nom["FR_Y"]),
                        "RL": (nom["RL_X"], nom["RL_Y"]),
                        "RR": (nom["RR_X"], nom["RR_Y"]),
                    }
                    for c_name, (cx, cy) in corners_dict.items():
                        eff_limit = spec_limit * exaggeration
                        t_xmin, t_xmax = cx - eff_limit, cx + eff_limit
                        t_ymin, t_ymax = cy - eff_limit, cy + eff_limit
                        t_box_x = [t_xmin, t_xmax, t_xmax, t_xmin, t_xmin]
                        t_box_y = [t_ymin, t_ymin, t_ymax, t_ymax, t_ymin]
                        fig.add_trace(
                            go.Scatter(
                                x=t_box_x,
                                y=t_box_y,
                                mode="lines",
                                name=f"Tolerance Zone ±{spec_limit}mm ({b_type})",
                                line=dict(
                                    color="rgba(217, 119, 6, 0.75)",
                                    width=1.5,
                                    dash="dot",
                                ),
                                showlegend=False,
                            )
                        )

                for _, row in df_to_plot.iterrows():
                    fl_x, fl_y = row["FL_X"], row["FL_Y"]
                    fr_x, fr_y = row["FR_X"], row["FR_Y"]
                    rl_x, rl_y = row["RL_X"], row["RL_Y"]
                    rr_x, rr_y = row["RR_X"], row["RR_Y"]

                    if (
                        pd.isna(fl_x)
                        or pd.isna(fr_x)
                        or pd.isna(rl_x)
                        or pd.isna(rr_x)
                    ):
                        continue

                    nom = get_nominal_coordinates(row["BatteryType"])

                    act_rl_x = nom["RL_X"] + (rl_x * exaggeration)
                    act_rl_y = nom["RL_Y"] + (rl_y * exaggeration)
                    act_fl_x = nom["FL_X"] + (fl_x * exaggeration)
                    act_fl_y = nom["FL_Y"] + (fl_y * exaggeration)
                    act_fr_x = nom["FR_X"] + (fr_x * exaggeration)
                    act_fr_y = nom["FR_Y"] + (fr_y * exaggeration)
                    act_rr_x = nom["RR_X"] + (rr_x * exaggeration)
                    act_rr_y = nom["RR_Y"] + (rr_y * exaggeration)

                    mod_x = [act_rl_x, act_fl_x, act_fr_x, act_rr_x, act_rl_x]
                    mod_y = [act_rl_y, act_fl_y, act_fr_y, act_rr_y, act_rl_y]

                    mod_identifier = f"{row['PartID']} | Run {row['RunNum']} | {str(row['Date'])[:10]}"
                    is_targeted = mod_identifier == selected_mod

                    if is_targeted:
                        color = "#00e6ff"
                        opacity = 1.0
                        width = 4
                        label = f"⭐ {mod_identifier} [SELECTED]"
                    else:
                        status = row["Status"]
                        color = "red" if status == "FAIL" else "gray"
                        opacity = 0.8 if status == "FAIL" else 0.4
                        width = 2 if status == "FAIL" else 1
                        label = (
                            f"{row['PartID']} (Run {row['RunNum']})"
                            f" [{status}]"
                        )

                    fig.add_trace(
                        go.Scatter(
                            x=mod_x,
                            y=mod_y,
                            mode="lines+markers",
                            name=label,
                            line=dict(color=color, width=width),
                            marker=dict(size=6 if is_targeted else 4),
                            opacity=opacity,
                        )
                    )

                fig.update_layout(
                    xaxis_title="Global X Axis [mm]",
                    yaxis_title="Global Y Axis [mm]",
                    height=700,
                    yaxis=dict(scaleanchor="x", scaleratio=1),
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No data available to plot.")

        with tab3:
            st.subheader(
                "📐 Advanced Squareness & Deformation Root Cause Analysis"
            )
            squareness_records = []

            for _, row in df_analysis.iterrows():
                if (
                    pd.isna(row["FL_X"])
                    or pd.isna(row["FR_X"])
                    or pd.isna(row["RL_X"])
                    or pd.isna(row["RR_X"])
                ):
                    continue

                nom = get_nominal_coordinates(row["BatteryType"])

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
                    (nom["FL_X"], nom["FL_Y"]),
                    (nom["FR_X"], nom["FR_Y"]),
                    (nom["RL_X"], nom["RL_Y"]),
                )

                fl_x_act = nom["FL_X"] + row["FL_X"]
                fl_y_act = nom["FL_Y"] + row["FL_Y"]
                fr_x_act = nom["FR_X"] + row["FR_X"]
                fr_y_act = nom["FR_Y"] + row["FR_Y"]
                rl_x_act = nom["RL_X"] + row["RL_X"]
                rl_y_act = nom["RL_Y"] + row["RL_Y"]
                rr_x_act = nom["RR_X"] + row["RR_X"]
                rr_y_act = nom["RR_Y"] + row["RR_Y"]

                d1_act = np.sqrt(
                    (rr_x_act - fl_x_act) ** 2 + (rr_y_act - fl_y_act) ** 2
                )
                d2_act = np.sqrt(
                    (rl_x_act - fr_x_act) ** 2 + (rl_y_act - fr_y_act) ** 2
                )
                w_top_act = np.sqrt(
                    (fr_x_act - fl_x_act) ** 2 + (fr_y_act - fl_y_act) ** 2
                )
                w_bot_act = np.sqrt(
                    (rr_x_act - rl_x_act) ** 2 + (rr_y_act - rl_y_act) ** 2
                )
                l_left_act = np.sqrt(
                    (rl_x_act - fl_x_act) ** 2 + (rl_y_act - fl_y_act) ** 2
                )
                l_right_act = np.sqrt(
                    (rr_x_act - fr_x_act) ** 2 + (rr_y_act - fr_y_act) ** 2
                )
                angle_fl_act = calculate_corner_angle(
                    (fl_x_act, fl_y_act),
                    (fr_x_act, fr_y_act),
                    (rl_x_act, rl_y_act),
                )

                delta_diags = abs((d1_act - d2_act) - (d1_nom - d2_nom))
                diff_ancho = (w_top_act - w_top_nom) - (w_bot_act - w_bot_nom)
                diff_largo = (l_left_act - l_left_nom) - (
                    l_right_act - l_right_nom
                )
                angle_fl_dev = angle_fl_act - angle_fl_nom

                status, detail = evaluate_deformation(
                    delta_diags,
                    angle_fl_dev,
                    diff_ancho,
                    diff_largo,
                    max_diag_tol,
                )

                squareness_records.append({
                    "Date": row["Date"],
                    "PartID": row["PartID"],
                    "RunNum": row["RunNum"],
                    "BatteryType": row["BatteryType"],
                    "Diag 1 [mm]": round(d1_act, 2),
                    "Diag 2 [mm]": round(d2_act, 2),
                    "Delta Diag [mm]": round(delta_diags, 2),
                    "Width Delta [mm]": round(diff_ancho, 2),
                    "Length Delta [mm]": round(diff_largo, 2),
                    "FL Angular Dev [°]": round(angle_fl_dev, 2),
                    "Squareness Status": status,
                    "Root Cause Details": detail,
                })

            df_squareness = pd.DataFrame(squareness_records)
            if not df_squareness.empty:
                event = st.dataframe(
                    style_squareness_report(df_squareness, max_diag_tol),
                    use_container_width=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    key="sq_table_selection",
                )

                selected_rows = event.selection.rows
                if selected_rows:
                    row_idx = selected_rows[0]
                    r_sel = df_squareness.iloc[row_idx]
                    new_target = f"{r_sel['PartID']} | Run {r_sel['RunNum']} | {str(r_sel['Date'])[:10]}"
                    if new_target != st.session_state["selected_mod_target"]:
                        st.session_state["selected_mod_target"] = new_target
                        st.rerun()
            else:
                st.info(
                    "Not enough complete 4-corner data available to calculate"
                    " squareness."
                )

        with tab4:
            st.subheader("🧭 Vector Drift, Conveyor Tuning & Rotation Analysis")

            df_vec = df_analysis.copy()
            df_vec["Centroid_X"] = df_vec[
                ["FL_X", "FR_X", "RL_X", "RR_X"]
            ].mean(axis=1)
            df_vec["Centroid_Y"] = df_vec[
                ["FL_Y", "FR_Y", "RL_Y", "RR_Y"]
            ].mean(axis=1)
            df_vec["Vector_Magnitude"] = np.sqrt(
                df_vec["Centroid_X"] ** 2 + df_vec["Centroid_Y"] ** 2
            )

            rotation_list = []
            for _, row in df_vec.iterrows():
                if (
                    pd.isna(row["FL_X"])
                    or pd.isna(row["FR_X"])
                    or pd.isna(row["RL_X"])
                    or pd.isna(row["RR_X"])
                ):
                    rotation_list.append(np.nan)
                    continue
                nom = get_nominal_coordinates(row["BatteryType"])
                f_nom_x = (nom["FL_X"] + nom["FR_X"]) / 2
                f_nom_y = (nom["FL_Y"] + nom["FR_Y"]) / 2
                r_nom_x = (nom["RL_X"] + nom["RR_X"]) / 2
                r_nom_y = (nom["RL_Y"] + nom["RR_Y"]) / 2
                v_nom_x = f_nom_x - r_nom_x
                v_nom_y = f_nom_y - r_nom_y
                angle_nom = np.degrees(np.arctan2(v_nom_y, v_nom_x))

                fl_x_act = nom["FL_X"] + row["FL_X"]
                fl_y_act = nom["FL_Y"] + row["FL_Y"]
                fr_x_act = nom["FR_X"] + row["FR_X"]
                fr_y_act = nom["FR_Y"] + row["FR_Y"]
                rl_x_act = nom["RL_X"] + row["RL_X"]
                rl_y_act = nom["RL_Y"] + row["RL_Y"]
                rr_x_act = nom["RR_X"] + row["RR_X"]
                rr_y_act = nom["RR_Y"] + row["RR_Y"]

                f_act_x = (fl_x_act + fr_x_act) / 2
                f_act_y = (fl_y_act + fr_y_act) / 2
                r_act_x = (rl_x_act + rr_x_act) / 2
                r_act_y = (rl_y_act + rr_y_act) / 2
                v_act_x = f_act_x - r_act_x
                v_act_y = f_act_y - r_act_y
                angle_act = np.degrees(np.arctan2(v_act_y, v_act_x))

                diff_angle = angle_act - angle_nom
                diff_angle = (diff_angle + 180) % 360 - 180
                rotation_list.append(diff_angle)

            df_vec["Rotation_Angle"] = rotation_list
            df_vec["WeekNum"] = (
                df_vec["CalendarWeek"]
                .str.replace("CW", "", regex=False)
                .astype(int)
            )

            col_v1, col_v2 = st.columns(2)

            with col_v1:
                st.markdown("##### 📍 Centroid Trajectory (Global X-Y Drift)")
                fig_drift = go.Figure()
                fig_drift.add_trace(
                    go.Scatter(
                        x=[0],
                        y=[0],
                        mode="markers+text",
                        marker=dict(color="green", size=12, symbol="cross"),
                        text=["Ideal (0,0)"],
                        textposition="top center",
                        name="Nominal Center",
                    )
                )
                fig_drift.add_trace(
                    go.Scatter(
                        x=df_vec["Centroid_X"],
                        y=df_vec["Centroid_Y"],
                        mode="lines+markers",
                        marker=dict(
                            size=9,
                            color=df_vec["WeekNum"],
                            colorscale="Viridis",
                            showscale=True,
                            colorbar=dict(title="Week (CW)", len=0.8, x=1.15),
                        ),
                        line=dict(color="rgba(100,100,100,0.5)", width=1.5),
                        name="Centroid Path",
                    )
                )
                fig_drift.update_layout(
                    xaxis_title="Mean X Deviation [mm]",
                    yaxis_title="Mean Y Deviation [mm]",
                    height=500,
                    yaxis=dict(scaleanchor="x", scaleratio=1),
                )
                st.plotly_chart(fig_drift, use_container_width=True)

            with col_v2:
                st.markdown("##### 📉 Error Vector Magnitude by Week")
                weekly_vector = (
                    df_vec.groupby("CalendarWeek")
                    .agg(
                        Mean_Magnitude=("Vector_Magnitude", "mean"),
                        Max_Magnitude=("Vector_Magnitude", "max"),
                        Total_Modules=("PartID", "count"),
                    )
                    .reset_index()
                )

                fig_mag = go.Figure()
                fig_mag.add_trace(
                    go.Bar(
                        x=weekly_vector["CalendarWeek"],
                        y=weekly_vector["Mean_Magnitude"],
                        name="Mean Drift Magnitude [mm]",
                        marker_color="#0f766e",
                    )
                )
                fig_mag.update_layout(
                    yaxis=dict(title="Mean Magnitude R (mm)"),
                    xaxis=dict(title="Week"),
                    height=500,
                )
                st.plotly_chart(fig_mag, use_container_width=True)

            st.markdown("---")
            st.markdown("##### 📋 Vector & Rotation Summary Table")
            df_vec_display = df_vec[[
                "Date",
                "CalendarWeek",
                "PartID",
                "BatteryType",
                "Centroid_X",
                "Centroid_Y",
                "Vector_Magnitude",
                "Rotation_Angle",
                "Status",
            ]].copy()
            df_vec_display.columns = [
                "Date",
                "Week",
                "Part ID",
                "Type",
                "Centroid X [mm]",
                "Centroid Y [mm]",
                "Magnitude R [mm]",
                "Yaw Rotation [°]",
                "Status",
            ]
            st.dataframe(
                df_vec_display.round(2),
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("---")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_analysis.to_excel(
                writer, sheet_name="Module_Summary_Report", index=False
            )
            if "df_quality_summary" in locals():
                df_quality_summary.to_excel(
                    writer,
                    sheet_name="First_Run_Quality_Summary",
                    index=False,
                )
            if "df_weekly" in locals():
                df_weekly.to_excel(
                    writer, sheet_name="Weekly_FPY_Trend", index=False
                )
            if "df_squareness" in locals() and not df_squareness.empty:
                df_squareness.to_excel(
                    writer, sheet_name="Squareness_Analysis", index=False
                )
            if "df_vec_display" in locals():
                df_vec_display.to_excel(
                    writer, sheet_name="Vector_Drift_Analysis", index=False
                )
        processed_data = output.getvalue()

        st.download_button(
            label="📥 Download Complete Excel Report",
            data=processed_data,
            file_name="Quality_Analysis_Report.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    except Exception as e:
        st.error(f"An error occurred while processing the file. Detail: {e}")
