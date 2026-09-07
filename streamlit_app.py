import matplotlib.pyplot as plt
import numpy as np

# Esquinas reales del módulo (desviaciones en mm)
fl = np.array([1.0, 1.5])
fr = np.array([2.0, 1.5])
rr = np.array([2.0, 2.5])
rl = np.array([1.0, 2.5])

# Coordenadas para trazar el perímetro del rectángulo
rect_x = [fl[0], fr[0], rr[0], rl[0], fl[0]]
rect_y = [fl[1], fr[1], rr[1], rl[1], fl[1]]

# Centroide calculado
cx, cy = 1.5, 2.0

# Configuración de la gráfica
fig, ax = plt.subplots(figsize=(7, 7))

# Trazar el rectángulo real
ax.plot(
    rect_x,
    rect_y,
    "b-o",
    linewidth=2,
    label="Módulo Real (Esquinas medidas)",
)

# Etiquetas de las esquinas
ax.text(
    fl[0] - 0.2,
    fl[1] + 0.1,
    "FL(1.0, 1.5)",
    fontsize=9,
    color="darkblue",
)
ax.text(
    fr[0] + 0.1,
    fr[1] + 0.1,
    "FR(2.0, 1.5)",
    fontsize=9,
    color="darkblue",
)
ax.text(
    rr[0] + 0.1,
    rr[1] - 0.2,
    "RR(2.0, 2.5)",
    fontsize=9,
    color="darkblue",
)
ax.text(
    rl[0] - 0.4,
    rl[1] - 0.2,
    "RL(1.0, 2.5)",
    fontsize=9,
    color="darkblue",
)

# Origen nominal (0,0)
ax.plot(
    0, 0, "go", markersize=10, label="Origen Nominal Ideal (0, 0)"
)

# Centroide real
ax.plot(
    cx,
    cy,
    "ro",
    markersize=9,
    label=f"Centroide Real ({cx}, {cy})",
)

# Flecha del vector de deriva (Magnitud R y Ángulo)
ax.annotate(
    "",
    xy=(cx, cy),
    xytext=(0, 0),
    arrowprops=dict(
        arrowstyle="-|>", color="purple", lw=2.5, mutation_scale=15
    ),
)

# Texto descriptivo del vector
ax.text(
    cx / 2 - 0.4,
    cy / 2 + 0.3,
    "Vector R = 2.50 mm\nθ = 53.13°",
    color="purple",
    fontsize=10,
    weight="bold",
    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.8),
)

# Ejes y referencias visuales
ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
ax.axvline(0, color="gray", linewidth=0.8, linestyle="--")
ax.set_xlim(-1.0, 3.5)
ax.set_ylim(-1.0, 3.5)
ax.set_aspect("equal")

ax.set_xlabel("Eje X [mm] (-X Front / +X Back)", fontsize=10)
ax.set_ylabel("Eje Y [mm] (-Y Left / +Y Right)", fontsize=10)
ax.set_title(
    "Representación Física: Centroide y Vector de Deriva",
    fontsize=12,
    weight="bold",
)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", frameon=True)

plt.tight_layout()
plt.show()
