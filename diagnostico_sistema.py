# =============================================================================
# NOMBRE: diagnostico_sistema.py
# OBJETIVO: Panel de salud del ecosistema IA en tiempo real.
#           Ejecutar en una 4a terminal mientras los otros 3 corren.
#
# USO:
#   python diagnostico_sistema.py          # una sola lectura
#   python diagnostico_sistema.py --watch  # refresca cada 10s
# =============================================================================

import os, sys, json, time, urllib.request, urllib.error
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Forzar UTF-8 en la consola de Windows (evita UnicodeEncodeError)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent

# ─────────────────────────────────────────────
# Colores ANSI para consola
# ─────────────────────────────────────────────
OK   = "\033[92m"   # verde
WARN = "\033[93m"   # amarillo
ERR  = "\033[91m"   # rojo
BOLD = "\033[1m"
DIM  = "\033[2m"
RST  = "\033[0m"

def ok(s):   return f"{OK}✔ {s}{RST}"
def warn(s): return f"{WARN}⚠ {s}{RST}"
def err(s):  return f"{ERR}✘ {s}{RST}"
def bold(s): return f"{BOLD}{s}{RST}"
def dim(s):  return f"{DIM}{s}{RST}"

# ─────────────────────────────────────────────
# Checks individuales
# ─────────────────────────────────────────────

def check_servidor_ia():
    """Verifica el servidor FastAPI en http://127.0.0.1:8080"""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/estado", timeout=2) as r:
            estado = json.loads(r.read())
        with urllib.request.urlopen("http://127.0.0.1:8080/metricas", timeout=2) as r:
            metricas = json.loads(r.read())
        return {"online": True, "estado": estado, "metricas": metricas}
    except urllib.error.URLError:
        return {"online": False}
    except Exception as e:
        return {"online": False, "error": str(e)}

def check_entrenador():
    """Verifica el progreso del entrenamiento leyendo el directorio de checkpoints y MLflow."""
    resultado = {}

    # Checkpoints del PPO
    ckpt_dir = ROOT / "ia_local" / "inference" / "checkpoints"
    if ckpt_dir.exists():
        # Ordenar por mtime (mas reciente al final), no por nombre alfanumerico
        ckpts = sorted(ckpt_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        resultado["checkpoints"] = len(ckpts)
        if ckpts:
            ultimo = ckpts[-1]
            resultado["ultimo_checkpoint"] = ultimo.name
            resultado["ult_ckpt_hace_min"] = round(
                (time.time() - ultimo.stat().st_mtime) / 60, 1
            )
    else:
        resultado["checkpoints"] = 0

    # Modelo de produccion
    modelo_zip = ROOT / "ia_local" / "inference" / "modelo_produccion.zip"
    modelo_onnx = ROOT / "ia_local" / "inference" / "modelo_produccion.onnx"
    resultado["modelo_pt_existe"]   = modelo_zip.exists()
    resultado["modelo_onnx_existe"] = modelo_onnx.exists()
    if modelo_zip.exists():
        _mtime = modelo_zip.stat().st_mtime
        resultado["modelo_hace_min"]   = round((time.time() - _mtime) / 60, 1)
        resultado["modelo_mtime_epoch"] = _mtime   # segundos desde epoch, para comparar con T2

    # Metricas MLflow (ultima run)
    mlflow_dir = ROOT / "ia_local" / "mlflow_runs"
    resultado["mlflow_activo"] = mlflow_dir.exists()
    if mlflow_dir.exists():
        runs = list(mlflow_dir.rglob("metrics/capital"))
        if runs:
            ultimo_run = max(runs, key=lambda p: p.stat().st_mtime)
            try:
                lineas = ultimo_run.read_text().strip().split("\n")
                ultima = lineas[-1].split()
                resultado["capital_ultima_eval"] = float(ultima[1])
            except Exception:
                pass

            sharpe_f = ultimo_run.parent / "sharpe_rolling"
            if sharpe_f.exists():
                try:
                    lineas = sharpe_f.read_text().strip().split("\n")
                    ultima = lineas[-1].split()
                    resultado["sharpe_ultima_eval"] = float(ultima[1])
                except Exception:
                    pass

            dd_f = ultimo_run.parent / "drawdown"
            if dd_f.exists():
                try:
                    lineas = dd_f.read_text().strip().split("\n")
                    ultima = lineas[-1].split()
                    resultado["drawdown_ultima_eval"] = float(ultima[1])
                except Exception:
                    pass

    return resultado

def check_bot_orquestador():
    """Verifica el log del bot buscando errores recientes."""
    resultado = {}
    log_file = ROOT / "sentinel_debug.log"
    if log_file.exists():
        resultado["log_existe"] = True
        lineas = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        errores_recientes = [l for l in lineas[-50:] if "ERROR" in l.upper()]
        resultado["errores_recientes"] = len(errores_recientes)
        resultado["ultimo_error"] = errores_recientes[-1][:80] if errores_recientes else None
        resultado["log_ultima_linea"] = lineas[-1][:80] if lineas else "vacío"
        resultado["log_hace_min"] = round(
            (time.time() - log_file.stat().st_mtime) / 60, 1
        )
    else:
        resultado["log_existe"] = False
    return resultado

def check_buffer_per():
    """Verifica si el buffer PER tiene datos acumulados."""
    buf_file = ROOT / "ia_local" / "inference" / "checkpoints" / "per_buffer.pkl"
    if buf_file.exists():
        size_mb = buf_file.stat().st_size / 1_048_576
        return {"existe": True, "size_mb": round(size_mb, 2)}
    return {"existe": False}

# ─────────────────────────────────────────────
# Renderizado del panel
# ─────────────────────────────────────────────

def render_panel():
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = "─" * 60

    print(f"\n{bold(linea)}")
    print(f"{bold('  PANEL DE SALUD — ECOSISTEMA IA TRADING')}")
    print(f"  {dim(ahora)}")
    print(f"{bold(linea)}")

    # ── TERMINAL 2: Servidor IA ─────────────────────────────────
    print(f"\n{bold('[ T2 ] SERVIDOR IA  (http://127.0.0.1:8080)')}")
    srv = check_servidor_ia()
    if not srv["online"]:
        print(f"  {err('OFFLINE — el servidor no responde')}")
        print(f"  {warn('Verifica que T2 esta corriendo:')}")
        print(f"  {dim('  python -m ia_local.inference.model_server')}")
    else:
        estado   = srv["estado"]
        metricas = srv["metricas"]
        cargado  = estado.get("modelo_cargado", False)
        tipo     = estado.get("tipo", "ninguno")
        version  = estado.get("version", "?")[:19]
        pasos    = estado.get("pasos_online", 0)

        if cargado:
            print(f"  {ok(f'Online | Modelo: {tipo.upper()} | Version: {version}')}")
        else:
            print(f"  {warn('Online — MODO FALLBACK (sin modelo cargado)')}")
            print(f"  {dim('  Esperando que T1 complete el entrenamiento...')}")

        lat  = metricas.get("latencia_media", 0)
        p95  = metricas.get("latencia_p95", 0)
        ninf = metricas.get("n_inferencias", 0)
        print(f"  Inferencias:  {bold(str(ninf))}  |  "
              f"Latencia media: {bold(f'{lat:.1f}ms')}  |  "
              f"P95: {bold(f'{p95:.1f}ms')}")

        if pasos > 0:
            print(f"  {ok(f'OnlineTrainer activo: {pasos:,} pasos acumulados')}")
        else:
            print(f"  {dim('  OnlineTrainer: esperando primeras experiencias...')}")

    # ── TERMINAL 1: Entrenador ──────────────────────────────────
    print(f"\n{bold('[ T1 ] ENTRENADOR OFFLINE  (offline_trainer)')}")
    ent = check_entrenador()

    ckpts = ent.get("checkpoints", 0)
    if ckpts == 0:
        print(f"  {warn('Sin checkpoints aun — entrenamiento en progreso o no iniciado')}")
        print(f"  {dim('  El primer checkpoint aparece tras ~10.000 pasos PPO')}")
    else:
        ult  = ent.get("ultimo_checkpoint", "?")
        hace = ent.get("ult_ckpt_hace_min", 0)
        print(f"  {ok(f'{ckpts} checkpoint(s) guardados')}")
        print(f"  Ultimo: {bold(ult)}  ({dim(f'hace {hace} min')})")

    modelo_listo = ent.get("modelo_pt_existe", False)
    onnx_listo   = ent.get("modelo_onnx_existe", False)
    if modelo_listo:
        hace_m = ent.get("modelo_hace_min", 0)
        print(f"  {ok(f'modelo_produccion.zip listo (hace {hace_m} min)')}")
        if onnx_listo:
            print(f"  {ok('modelo_produccion.onnx listo (inferencia rapida)')}")
        else:
            print(f"  {warn('ONNX no exportado aun (se exporta en validar_y_guardar)')}")

        # Solo pedir reinicio si T2 tiene una version MAS ANTIGUA que el zip actual.
        # La version de T2 sigue el formato YYYYMMDD_HHMMSS (ej: 20260409_210504).
        zip_mtime = ent.get("modelo_mtime_epoch", 0)
        t2_version = srv.get("estado", {}).get("version", "") if srv.get("online") else ""
        t2_dt = None
        try:
            if t2_version and len(t2_version) >= 15:
                t2_dt = datetime.strptime(t2_version[:15], "%Y%m%d_%H%M%S")
        except ValueError:
            pass

        if t2_dt is not None:
            zip_dt = datetime.fromtimestamp(zip_mtime)
            if zip_dt > t2_dt + timedelta(seconds=30):
                print(f"\n  {WARN}{BOLD}► Reinicia T2: hay un modelo mas nuevo que la version cargada{RST}")
                hora_zip = zip_dt.strftime("%H:%M:%S")
                hora_t2  = t2_dt.strftime("%H:%M:%S")
                print(f"  {dim(f'  Zip: {hora_zip}  |  T2 cargado: {hora_t2}')}")
            else:
                print(f"  {ok('T2 ya tiene la version mas reciente cargada')}")
        else:
            # T2 offline o version sin formato esperado: mostrar aviso conservador
            if not srv.get("online"):
                print(f"\n  {WARN}{BOLD}► Inicia T2 para que el servidor cargue el modelo{RST}")
            else:
                print(f"  {ok('Modelo disponible en produccion')}")
    else:
        print(f"  {warn('modelo_produccion.zip no existe aun')}")
        print(f"  {dim('  Se genera al finalizar el entrenamiento completo')}")

    if ent.get("mlflow_activo"):
        cap    = ent.get("capital_ultima_eval")
        sharpe = ent.get("sharpe_ultima_eval")
        dd     = ent.get("drawdown_ultima_eval")
        partes = []
        if cap    is not None: partes.append(f"Capital={cap:.2f}")
        if sharpe is not None: partes.append(f"Sharpe={sharpe:.3f}")
        if dd     is not None: partes.append(f"DD={dd:.2%}")
        if partes:
            print(f"  MLflow ultima eval: {bold(' | '.join(partes))}")
        else:
            print(f"  {dim('  MLflow activo — metricas aun no disponibles')}")

    # ── TERMINAL 3: Bot Orquestador ─────────────────────────────
    print(f"\n{bold('[ T3 ] BOT ORQUESTADOR  (main_orquestador.py)')}")
    bot = check_bot_orquestador()

    if not bot.get("log_existe"):
        print(f"  {dim('Sin log de errores (sentinel_debug.log) — buena señal')}")
        print(f"  {ok('Bot corriendo sin errores registrados')}")
    else:
        errores = bot.get("errores_recientes", 0)
        hace_m  = bot.get("log_hace_min", 0)
        if errores == 0:
            print(f"  {ok(f'Sin errores recientes | Log actualizado hace {hace_m} min')}")
        else:
            print(f"  {err(f'{errores} error(es) reciente(s) en el log')}")
            ult_err = bot.get("ultimo_error", "")
            if ult_err:
                print(f"  Ultimo: {dim(ult_err)}")

        ultima = bot.get("log_ultima_linea", "")
        if ultima:
            print(f"  Ultima linea: {dim(ultima)}")

    # ── BUFFER PER ──────────────────────────────────────────────
    print(f"\n{bold('[ MEM ] BUFFER DE EXPERIENCIAS (PER)')}")
    buf = check_buffer_per()
    if buf.get("existe"):
        size_mb = buf['size_mb']
        print(f"  {ok(f'Buffer guardado en disco: {size_mb} MB')}")
    else:
        print(f"  {dim('Sin buffer en disco aun (se guarda al detener el servidor)')}")

    # ── DIAGNOSTICO GLOBAL ──────────────────────────────────────
    print(f"\n{bold(linea)}")
    problemas = []
    if not srv["online"]:
        problemas.append("T2 (servidor IA) no responde")
    if not ent.get("modelo_pt_existe"):
        problemas.append("T1 aun entrenando (modelo no generado)")
    if bot.get("errores_recientes", 0) > 0:
        problemas.append(f"T3 tiene {bot['errores_recientes']} error(es) en el log")

    if not problemas:
        print(f"  {ok(bold('SISTEMA SALUDABLE'))}")
    else:
        print(f"  {warn(bold('ATENCIONES:'))}")
        for p in problemas:
            print(f"    {warn(p)}")

    print(f"{bold(linea)}\n")

# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostico del ecosistema IA")
    parser.add_argument("--watch", action="store_true",
                        help="Refrescar cada 10 segundos (Ctrl+C para salir)")
    parser.add_argument("--intervalo", type=int, default=10,
                        help="Segundos entre refresco en modo --watch")
    args = parser.parse_args()

    if args.watch:
        print(f"Modo watch — refrescando cada {args.intervalo}s (Ctrl+C para salir)")
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                render_panel()
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            print("\nDiagnostico detenido.")
    else:
        render_panel()
