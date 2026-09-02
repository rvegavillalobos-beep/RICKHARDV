# ---------------------------------------------------------------------
# TAB 1: EXECUTIVE QUALITY DASHBOARD (ACTUALIZADO)
# ---------------------------------------------------------------------
with tab1:
    st.subheader("📊 Executive Quality & FPY Performance")
    
    total_mod = len(df_filtered)
    pass_mod = len(df_filtered[df_filtered["OverallPass"] == "PASSED (OK)"])
    fail_mod = len(df_filtered[df_filtered["OverallPass"] == "FAILED (NOK)"])
    fpy_global = (pass_mod / total_mod * 100) if total_mod > 0 else 0.0
    
    # 1. TABLAS SUPERIORES DE RESUMEN EJECUTIVO
    col_summary, col_space = st.columns([1, 2])
    
    with col_summary:
        st.markdown("##### 📋 FIRST-RUN QUALITY SUMMARY")
        summary_data = {
            "Metric": [
                "Unique Modules (Run)", 
                "Passed First-Run (OK)", 
                "Failed First-Run (NOK)", 
                "First-Pass Yield (FPY)"
            ],
            "Value": [
                f"{total_mod}", 
                f"{pass_mod}", 
                f"{fail_mod}", 
                f"{fpy_global:.1f}%"
            ]
        }
        df_kpi_table = pd.DataFrame(summary_data)
        st.dataframe(
            df_kpi_table,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # 2. TABLA Y GRÁFICO SEMANAL DE FPY EN DOS COLUMNAS
    col_chart, col_table = st.columns([3, 2])
    
    # Preparación de datos por semana
    cw_summary = df_filtered.groupby("CW").agg(
        Total=('PartID', 'count'),
        Passed=('OverallPass', lambda x: (x == 'PASSED (OK)').sum()),
        Failed=('OverallPass', lambda x: (x == 'FAILED (NOK)').sum())
    ).reset_index()
    
    cw_summary["PassRate"] = (cw_summary["Passed"] / cw_summary["Total"]) * 100
    cw_summary["PassPct"] = (cw_summary["Passed"] / cw_summary["Total"]) * 100
    cw_summary["FailPct"] = (cw_summary["Failed"] / cw_summary["Total"]) * 100

    with col_chart:
        st.markdown("### 📈 Weekly First-Pass Yield Trend (%)")
        
        fig_stacked = go.Figure()
        
        # Barra Passed (Verde industrial)
        fig_stacked.add_trace(go.Bar(
            x=cw_summary["CW"], 
            y=cw_summary["PassPct"],
            name="Passed (OK)", 
            marker_color="#2E7D32"
        ))
        
        # Barra Failed (Rojo terracota)
        fig_stacked.add_trace(go.Bar(
            x=cw_summary["CW"], 
            y=cw_summary["FailPct"],
            name="Failed (NOK)", 
            marker_color="#C62828"
        ))
        
        # Línea Horizontal FPY Global / Promedio
        fig_stacked.add_hline(
            y=fpy_global, 
            line_dash="dash", 
            line_color="#FFB300", 
            line_width=2.5,
            annotation_text=f"Total FPY: {fpy_global:.1f}%", 
            annotation_position="top right",
            annotation_font=dict(size=12, color="#FFB300", family="sans-serif")
        )

        fig_stacked.update_layout(
            barmode='stack',
            yaxis_title="Percentage (%)",
            yaxis=dict(range=[0, 105]),
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(
                orientation="h", 
                yanchor="bottom", 
                y=1.02, 
                xanchor="right", 
                x=1
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_stacked, use_container_width=True)

    with col_table:
        st.markdown("### 🗓️ WEEKLY FPY BREAKDOWN")
        
        display_cw = cw_summary.rename(columns={
            "CW": "Calendar Week",
            "Total": "Unique Modules",
            "Passed": "Passed (OK)",
            "Failed": "Failed (NOK)",
            "PassRate": "Pass Rate (%)"
        })[["Calendar Week", "Unique Modules", "Passed (OK)", "Failed (NOK)", "Pass Rate (%)"]]
        
        st.dataframe(
            display_cw.style.format({
                "Unique Modules": "{:d}",
                "Passed (OK)": "{:d}",
                "Failed (NOK)": "{:d}",
                "Pass Rate (%)": "{:.1f}%"
            }).background_gradient(subset=["Pass Rate (%)"], cmap="YlGn", vmin=0, vmax=100),
            use_container_width=True,
            hide_index=True,
            height=420
        )
