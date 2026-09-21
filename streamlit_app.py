with col_v1:
    st.markdown("##### 📍 Weekly Centroid Macro Drift (Global X-Y Offset)")
    split_by_type = st.checkbox(
        "Split by Battery Type (Type S vs Type M)",
        value=True,
        key="split_centroid_by_type",
    )

    fig_drift = go.Figure()
    fig_drift.add_trace(
        go.Scatter(
            x=[0], y=[0], mode="markers+text", marker=dict(color="#10b981", size=14, symbol="cross"),
            text=["Ideal (0,0)"], textposition="top center", name="Nominal Center",
        )
    )

    type_line_colors = {"Type S": "#2563eb", "Type M": "#f59e0b"}
    type_point_colors = {"Type S": "rgba(37, 99, 235, 0.35)", "Type M": "rgba(245, 158, 11, 0.35)"}

    if split_by_type:
        for b_type in sorted(df_centroid_raw["BatteryType"].dropna().unique().tolist()):
            df_type_raw = df_centroid_raw[df_centroid_raw["BatteryType"] == b_type]

            fig_drift.add_trace(
                go.Scatter(
                    x=df_type_raw["Centroid_X"], y=df_type_raw["Centroid_Y"], mode="markers",
                    marker=dict(size=5, color=type_point_colors.get(b_type, "rgba(156,163,175,0.35)")),
                    name=f"Individual Parts ({b_type})",
                    hovertemplate=f"Part Centroid ({b_type})<br>X: %{{x:.2f}} mm<br>Y: %{{y:.2f}} mm<extra></extra>",
                )
            )

            df_weekly_centroids_type = (
                df_type_raw.groupby("CalendarWeek")
                .agg(Mean_X=("Centroid_X", "mean"), Mean_Y=("Centroid_Y", "mean"),
                     WeekNum=("WeekNum", "first"), Sample_Count=("PartID", "count"))
                .reset_index().sort_values("WeekNum")
            )

            fig_drift.add_trace(
                go.Scatter(
                    x=df_weekly_centroids_type["Mean_X"], y=df_weekly_centroids_type["Mean_Y"],
                    mode="lines+markers+text",
                    marker=dict(size=12, color=type_line_colors.get(b_type, "#2563eb"), line=dict(width=1.5, color="white")),
                    line=dict(color=type_line_colors.get(b_type, "#2563eb"), width=3),
                    text=df_weekly_centroids_type["CalendarWeek"], textposition="top right",
                    name=f"Weekly Drift Path ({b_type})",
                    customdata=df_weekly_centroids_type[["Sample_Count"]],
                    hovertemplate=(
                        f"<b>%{{text}} Average ({b_type})</b><br>Mean X Offset: %{{x:.2f}} mm<br>"
                        "Mean Y Offset: %{y:.2f} mm<br>Sample Size: %{customdata[0]} parts<extra></extra>"
                    ),
                )
            )
    else:
        fig_drift.add_trace(
            go.Scatter(
                x=df_centroid_raw["Centroid_X"], y=df_centroid_raw["Centroid_Y"], mode="markers",
                marker=dict(size=5, color="#9ca3af", opacity=0.35), name="Individual Parts",
                hovertemplate="Part Centroid<br>X: %{x:.2f} mm<br>Y: %{y:.2f} mm<extra></extra>",
            )
        )
        fig_drift.add_trace(
            go.Scatter(
                x=df_weekly_centroids["Mean_X"], y=df_weekly_centroids["Mean_Y"], mode="lines+markers+text",
                marker=dict(
                    size=12, color=df_weekly_centroids["WeekNum"], colorscale="Viridis", showscale=True,
                    colorbar=dict(title="Week (CW)", len=0.8, x=1.12), line=dict(width=1.5, color="white"),
                ),
                line=dict(color="#2563eb", width=3), text=df_weekly_centroids["CalendarWeek"],
                textposition="top right", name="Weekly Drift Path (Combined)",
                customdata=df_weekly_centroids[["Sample_Count"]],
                hovertemplate=(
                    "<b>%{text} Average</b><br>Mean X Offset: %{x:.2f} mm<br>"
                    "Mean Y Offset: %{y:.2f} mm<br>Sample Size: %{customdata[0]} parts<extra></extra>"
                ),
            )
        )

    fig_drift.update_layout(
        xaxis=dict(title="Mean X Deviation [mm]", zeroline=True, zerolinecolor="#6b7280"),
        yaxis=dict(title="Mean Y Deviation [mm]", zeroline=True, zerolinecolor="#6b7280", scaleanchor="x", scaleratio=1),
        height=520, margin=dict(l=10, r=10, t=30, b=10), template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_drift, use_container_width=True)
