# Ordenamos por fecha para simular el comportamiento secuencial del arreglo de VBA
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

    # Asignamos las columnas de vuelta al DataFrame para evitar el KeyError
    df_raw["BaseKey"] = base_keys
    df_raw["CurrentRun"] = current_runs

    # Agrupamos por baseKey y Run para consolidar las 4 esquinas por batería/corrida
    grouped_runs = df_raw.groupby(["BaseKey", "CurrentRun"])
