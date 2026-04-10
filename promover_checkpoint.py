# =============================================================================
# promover_checkpoint.py
# OBJETIVO: Promueve manualmente el ultimo checkpoint entrenado a
#           ia_local/inference/modelo_produccion.zip para que el servidor
#           de inferencia (T2) pueda cargarlo.
#
# USO:
#   python promover_checkpoint.py                  # promueve el ultimo checkpoint
#   python promover_checkpoint.py --steps 90000    # promueve un checkpoint especifico
# =============================================================================

import os
import sys
import shutil
import argparse
from datetime import datetime

IA_ROOT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ia_local")
CKPT_DIR = os.path.join(IA_ROOT, "inference", "checkpoints")
DEST_ZIP = os.path.join(IA_ROOT, "inference", "modelo_produccion.zip")
SYMBOL   = "AAVEUSDT"


def listar_checkpoints():
    if not os.path.isdir(CKPT_DIR):
        return []
    zips = [f for f in os.listdir(CKPT_DIR) if f.endswith(".zip") and SYMBOL in f]
    return sorted(zips, key=lambda f: int(f.split("_steps")[0].split("_")[-1]))


def promover(steps: int = None):
    checkpoints = listar_checkpoints()
    if not checkpoints:
        print(f"[ERROR] No hay checkpoints en {CKPT_DIR}")
        sys.exit(1)

    print(f"\nCheckpoints disponibles:")
    for i, c in enumerate(checkpoints):
        size_mb = os.path.getsize(os.path.join(CKPT_DIR, c)) / 1024 / 1024
        marker = " <-- ULTIMO" if i == len(checkpoints) - 1 else ""
        print(f"  [{i+1:2d}] {c}  ({size_mb:.1f} MB){marker}")

    if steps is not None:
        nombre_buscado = f"ppo_{SYMBOL}_{steps}_steps.zip"
        origen = os.path.join(CKPT_DIR, nombre_buscado)
        if not os.path.exists(origen):
            print(f"\n[ERROR] No existe: {nombre_buscado}")
            sys.exit(1)
    else:
        # Usar el checkpoint con mas pasos (el ultimo)
        origen = os.path.join(CKPT_DIR, checkpoints[-1])

    nombre_origen = os.path.basename(origen)
    size_mb = os.path.getsize(origen) / 1024 / 1024
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n  Promoviendo: {nombre_origen} ({size_mb:.1f} MB)")
    print(f"  Destino:     {DEST_ZIP}")
    print(f"  Timestamp:   {ts}")

    # Backup del modelo anterior si existe
    if os.path.exists(DEST_ZIP):
        backup = DEST_ZIP.replace(".zip", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
        shutil.copy2(DEST_ZIP, backup)
        print(f"  Backup:      {os.path.basename(backup)}")

    shutil.copy2(origen, DEST_ZIP)
    print(f"\n  [OK] modelo_produccion.zip actualizado correctamente.")
    print(f"\n  Ahora reinicia el servidor T2:")
    print(f"    Ctrl+C en T2, luego:")
    print(f"    python -m ia_local.inference.model_server")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promover checkpoint a produccion")
    parser.add_argument("--steps", type=int, default=None,
                        help="Pasos del checkpoint a promover (default: el mayor disponible)")
    args = parser.parse_args()
    promover(args.steps)
