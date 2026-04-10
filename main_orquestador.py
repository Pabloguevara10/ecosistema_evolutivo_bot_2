# =============================================================================
# NOMBRE: main_orquestador.py
# UBICACIÓN: RAÍZ DEL PROYECTO
# OBJETIVO: Orquestador Central Multi-Hilo con Memoria Caché y Separación Visual.
# INCLUYE: Integración Segura de Estrategia Pirámide MTF y VIP ADN.
# =============================================================================

import os
import sys
import time
import threading
import msvcrt
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from binance.client import Client
from dotenv import load_dotenv

# Dependencia Visual (El diseño real vive en dashboard_sentinel.py)
try:
    from rich.live import Live
    from rich.console import Console
except ImportError:
    print("❌ Faltan dependencias visuales. Ejecuta: python -m pip install rich")
    sys.exit(1)

from dashboard_sentinel import DashboardSentinel

# --- 🔑 CARGA DE CREDENCIALES DESDE .env ---
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY_TESTNET")
API_SECRET = os.getenv("BINANCE_API_SECRET_TESTNET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

if not API_KEY or not API_SECRET:
    print("❌ Error Crítico: No se encontraron las variables de Binance en .env")
    sys.exit(1)

# --- RUTAS ESTRICTAS ---
project_root = os.path.dirname(os.path.abspath(__file__))
carpetas_deptos = ["dep_herramientas", "dep_analisis", "dep_ejecucion",
                    "dep_salud", "dep_control", "dep_registro"]
for carpeta in carpetas_deptos:
    ruta_completa = os.path.join(project_root, carpeta)
    if os.path.exists(ruta_completa):
        sys.path.append(ruta_completa)

try:
    from StructureScanner_2 import StructureScanner
    from monitor_mercado import MonitorMercado
    from comparador_estrategias import ComparadorEstrategias
    from emisor_señales import EmisorSenales
    from evaluador_entradas import EvaluadorEntradas
    from gestor_cupos import GestorCupos
    from disparador_binance import DisparadorBinance
    from asegurador_posicion import AseguradorPosicion
    from bitacora_central import BitacoraCentral
    from auditor_red import AuditorRed
    from monitor_recursos import MonitorRecursos
    from controlador_telegram import ControladorTelegram
    from notificador_telegram import NotificadorTelegram
    from reporte_diagnostico import ReporteDiagnostico
    # --- Pilares 1, 2 y 3 ---
    from dep_registro import GestorRegistro, GestorPendientes
    from coordinador_reintentos import CoordinadorReintentos
    from modificador_ordenes_seguro import ModificadorOrdenesSeguro
    from trailing_stop_dinamico import ControladorDinamico
except ImportError as e:
    print(f"❌ Error de Importación: {e}")
    sys.exit(1)

# --- MODULO IA LOCAL (opcional: el bot opera sin IA si no esta disponible) ---
try:
    import numpy as _np_ia
    from ia_local.inference.model_server import IAClient
    from ia_local.config import (
        OBS_SPACE_DIM as _IA_OBS_DIM,
        IA_CAPITAL_PCT, REGLAS_CAPITAL_PCT, CONFIANZA_IA_SOLO,
    )
    _IA_DISPONIBLE = True
except Exception as _ia_err:
    _IA_DISPONIBLE = False
    print(f"[IA] Modulo IA no disponible ({_ia_err}). Operando en modo reglas clasicas.")

class SincronizadorDummy:
    def get_timestamp_corregido(self):
        return int(time.time() * 1000)

class ConexionWrapper:
    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.sincronizador = SincronizadorDummy()

# =============================================================================
# ORQUESTADOR CENTRAL
# =============================================================================
class OrquestadorCentral:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        self.inicio_sesion = datetime.now()
        
        # --- VARIABLES DE CONTROL (KILLSWITCH) ---
        self.trading_permitido = True
        
        # --- MEMORIA CACHÉ (NUEVO SISTEMA DUAL TRACK) ---
        self.cache_mtf = {}
        self.ultimo_update_mtf = 0
        # Cache de la vela 1m: la vela cierra cada 60s, refrescamos cada 20s
        self.cache_1m = None
        self.ultimo_update_1m = 0
        self.intervalo_1m_seg = 20
        # Pool reutilizable para fetches MTF en paralelo
        self._mtf_pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix="mtf")
        
        self.config_estrategias = {
            "VIP_ADN": True,         
            "PIRAMIDE_MTF": True     
        }
        
        self.estrategia_piramide = None
        if self.config_estrategias["PIRAMIDE_MTF"]:
            try:
                from estrategia_piramide_mtf import EstrategiaPiramideMTF
                self.estrategia_piramide = EstrategiaPiramideMTF()
            except ImportError:
                self.config_estrategias["PIRAMIDE_MTF"] = False

        self.estado_ui = {
            "precio_actual": 0.0,  
            "balance_inicial": 0.0,
            "balance_actual": 0.0,
            "latencia": "0ms",
            "entradas_hoy": 0,
            "telegram_status": "[green]Activo[/green]" if TELEGRAM_TOKEN else "[yellow]Inactivo[/yellow]",
            "mensajes_sistema": ["", "", "Sistemas armados. Esperando datos..."],
            "comando_buffer": "", 
            "estado_bot": "[green]OPERATIVO[/green]",
            "posiciones_activas": [], 
            "mtf": {
                "1d": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"},
                "4h": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"},
                "1h": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"},
                "15m": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"},
                "5m": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"},
                "1m": {"rsi": [0,0], "macd": [0,0], "stoch": [0,0], "adx": [0,0], "vol": [0,0], "bb": "Calc...", "div": "Ninguna", "trend": "Lateral"}
            }
        }
        
        # INICIALIZACIÓN DE LA NUEVA BITÁCORA DE 3 REPORTES
        self.bitacora = BitacoraCentral()

        # --- PILAR 1: REGISTRO SQLITE LOCAL (fuente de verdad) ---
        self.registro = GestorRegistro()
        # --- TELEGRAM SALIENTE (notificaciones de pendientes/escalados) ---
        self.notificador = NotificadorTelegram()

        # Contador de ciclos del motor: usado por coordinador y gestor de pendientes
        self._ciclo_actual = 0
        # Cooldown post-entrada: impide abrir nueva posicion por COOLDOWN_ENTRADA_SEG
        # segundos tras la ultima apertura (evita piramidacion por senales repetidas)
        self._timestamp_ultima_entrada = 0.0
        self.COOLDOWN_ENTRADA_SEG = 900  # 15 minutos
        # Marca de la ultima sincronizacion contra Binance (segs unix)
        self._ultima_sync_binance = 0.0
        self._ultima_sync_balance = 0.0  # Timer independiente para snapshot de balance
        # Detectar cierres de posicion (SL/TP ejecutados) cada 30s
        self.intervalo_sync_binance_seg = 30
        # Balance real contra Binance: solo cada 120s para reducir presion API
        self.intervalo_sync_balance_seg = 120

        # --- PILAR 2: COORDINADOR DE REINTENTOS PROGRESIVOS ---
        self.coordinador = CoordinadorReintentos(
            gestor_registro=self.registro,
            notificador_telegram=self.notificador,
            bitacora=self.bitacora,
            obtener_ciclo_actual=lambda: self._ciclo_actual,
        )

        # --- GESTOR DE PROCESOS PENDIENTES (Pilar 2) ---
        self.gestor_pendientes = GestorPendientes(
            gestor_registro=self.registro,
            notificador_telegram=self.notificador,
            bitacora=self.bitacora,
        )

        self.conexion = ConexionWrapper(API_KEY, API_SECRET, testnet=True)
        self.auditor = AuditorRed(self.conexion, self.bitacora)
        self.monitor_hw = MonitorRecursos(self.bitacora)
        self.diagnostico = ReporteDiagnostico(self.monitor_hw, self.bitacora)
        self.monitor = MonitorMercado(self.conexion.client)
        self.comparador = ComparadorEstrategias()
        self.emisor = EmisorSenales()
        self.gestor = GestorCupos()
        self.evaluador = EvaluadorEntradas(self.gestor)
        self.disparador = DisparadorBinance(
            self.conexion, coordinador=self.coordinador,
            gestor_registro=self.registro, bitacora=self.bitacora,
        )
        self.asegurador = AseguradorPosicion(
            self.conexion, self.disparador, coordinador=self.coordinador,
            gestor_registro=self.registro, bitacora=self.bitacora,
        )

        # --- PILAR 3: MODIFICADOR SEGURO Y CONTROLADOR DE TRAILING ---
        self.modificador_seguro = ModificadorOrdenesSeguro(
            self.conexion, self.coordinador, self.registro, bitacora=self.bitacora,
        )
        self.controlador_trailing = ControladorDinamico(
            self.conexion, self.disparador, self.gestor,
            gestor_registro=self.registro,
            modificador_seguro=self.modificador_seguro,
            bitacora=self.bitacora,
        )

        # RIESGO INSTITUCIONAL: 5% del balance por operación (calculado vs Stop Loss)
        self.porcentaje_riesgo = 0.05

        # --- MODULO IA: cliente HTTP al servidor de inferencia local ---
        # El servidor IA corre en proceso separado (python -m ia_local.inference.model_server).
        # Si no esta disponible, el bot opera en modo 100% reglas clasicas sin degradacion.
        self.ia_client = None
        self._ia_activa = False
        self._ultimo_obs_ia: object = None  # ultimo vector obs enviado a la IA
        if _IA_DISPONIBLE:
            try:
                self.ia_client = IAClient()
                self._ia_activa = self.ia_client.disponible
                if self._ia_activa:
                    self.log_ui("🤖 Modulo IA conectado. Modo hibrido IA+Reglas activado.")
                    self.bitacora.registrar_actividad(
                        "IA_Local", "IAClient conectado. Modo hibrido activado."
                    )
            except Exception as _e_ia:
                self.log_ui(f"⚠️ IA no conectada: {_e_ia}")

        self.bitacora.registrar_actividad("Main_Orquestador", "Módulos instanciados y variables de estado cargadas.")

    def log_ui(self, mensaje):
        hora = datetime.now().strftime("%H:%M:%S")
        texto = f"[{hora}] {mensaje}"
        print(texto)

    def actualizar_balance(self, es_inicio=False, forzar=False):
        """
        PILAR 1: lee del snapshot SQLite. Solo va a Binance al inicio o cuando
        han pasado intervalo_sync_binance_seg desde la ultima sincronizacion.
        """
        if not es_inicio and not forzar:
            snap = self.registro.obtener_ultimo_snapshot()
            if snap is not None:
                self.estado_ui['balance_actual'] = float(snap['balance_usdt'])
                return

        try:
            balances = self.conexion.client.futures_account_balance()
            for b in balances:
                if b['asset'] == 'USDT':
                    saldo = float(b['balance'])
                    self.estado_ui['balance_actual'] = saldo
                    if es_inicio:
                        self.estado_ui['balance_inicial'] = saldo
                    # Persistir snapshot en SQLite
                    try:
                        self.registro.guardar_snapshot_cuenta(saldo)
                    except Exception:
                        pass
                    return
        except Exception as e:
            self.bitacora.registrar_error("Conexión Binance", f"Error actualizando balance: {str(e)}")

    def actualizar_posiciones_en_vivo(self):
        """
        PILAR 1: construye la UI desde el registro SQLite.
        La validacion contra Binance ocurre en sincronizar_con_binance() cada 120s.
        """
        try:
            posiciones_local = self.registro.obtener_posiciones_abiertas(self.symbol)
            nuevas_pos_ui = []
            for pos in posiciones_local:
                ordenes_sl = self.registro.obtener_ordenes_proteccion(
                    self.symbol, pos['direccion'], 'SL'
                )
                ordenes_tp = self.registro.obtener_ordenes_proteccion(
                    self.symbol, pos['direccion'], 'TP'
                )
                sl = float(ordenes_sl[-1]['precio']) if ordenes_sl else "N/A"
                tp = float(ordenes_tp[-1]['precio']) if ordenes_tp else "N/A"
                # Mostrar ID local de la posicion + estado de protecciones registradas
                id_local_val = pos.get('id_local')
                id_parts = [f"L#{id_local_val}"] if id_local_val is not None else []
                id_parts.append("SL✓" if ordenes_sl else "SL✗")
                id_parts.append("TP✓" if ordenes_tp else "TP✗")
                id_mostrar = " ".join(id_parts)

                nuevas_pos_ui.append({
                    "symbol": pos['symbol'],
                    "side": pos['direccion'],
                    "cantidad": abs(float(pos['cantidad'])),
                    "entry_price": float(pos['precio_entrada']),
                    "sl": sl,
                    "tp": tp,
                    "be": "N/A",
                    "order_id": id_mostrar,
                    "protegida": bool(ordenes_sl),
                })
            self.estado_ui["posiciones_activas"] = nuevas_pos_ui
        except Exception as e:
            self.bitacora.registrar_error("Estado Local", f"Fallo al leer registro local: {e}")

    def _construir_ui_legacy(self):
        """
        Funcion legacy original que consultaba Binance directamente.
        Se mantiene como referencia y se invoca en sincronizar_con_binance().
        """
        try:
            posiciones = self.conexion.client.futures_position_information(symbol=self.symbol)
            vivas = [p for p in posiciones if float(p['positionAmt']) != 0]

            ordenes_abiertas = self.conexion.client.futures_get_open_orders(symbol=self.symbol)

            nuevas_pos_ui = []
            for pos in vivas:
                amt = float(pos['positionAmt'])
                side_pos = "LONG" if amt > 0 else "SHORT"
                
                side_cierre_esperado = "SELL" if side_pos == "LONG" else "BUY"

                sl = "N/A"
                tp = "N/A"
                ids_ordenes = []

                for ord in ordenes_abiertas:
                    if ord.get('side') == side_cierre_esperado:
                        tipo_orden = ord.get('type', '')
                        
                        if 'STOP' in tipo_orden:
                            sl = float(ord.get('stopPrice', 0))
                            ids_ordenes.append(str(ord.get('orderId', ''))[-5:])
                        elif 'TAKE_PROFIT' in tipo_orden or 'TAKE' in tipo_orden:
                            tp = float(ord.get('stopPrice', 0))
                            ids_ordenes.append(str(ord.get('orderId', ''))[-5:])

                id_mostrar = "-".join(list(set(ids_ordenes))) if ids_ordenes else "Sin Órdenes"

                protegida = False
                if hasattr(self, 'gestor') and hasattr(self.gestor, 'posiciones_activas'):
                    for g_pos in self.gestor.posiciones_activas:
                        if abs(float(g_pos.get('entry_price', 0)) - float(pos['entryPrice'])) < 0.001:
                            protegida = g_pos.get('protegida', False)
                            break

                be_val = sl if protegida and sl != "N/A" else "N/A"

                nuevas_pos_ui.append({
                    "symbol": pos['symbol'],
                    "side": side_pos,
                    "cantidad": abs(amt),
                    "entry_price": float(pos['entryPrice']),
                    "sl": sl,
                    "tp": tp,
                    "be": be_val,
                    "order_id": id_mostrar,
                    "protegida": protegida
                })

            self.estado_ui["posiciones_activas"] = nuevas_pos_ui
        except Exception as e:
            self.bitacora.registrar_error("Escáner Posiciones", f"Fallo al leer datos en vivo: {str(e)}")
            with open("sentinel_debug.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now()}] ERROR LEYENDO POSICIONES API:\n{traceback.format_exc()}\n")

    def sincronizar_con_binance(self):
        """
        PILAR 1: Validacion periodica contra Binance.
          - Cada 30s: detecta cierres de posicion (SL/TP ejecutados) y sincroniza SQLite.
          - Cada 120s: refresca snapshot de balance.
        """
        ahora = time.time()
        if ahora - self._ultima_sync_binance < self.intervalo_sync_binance_seg:
            return
        self._ultima_sync_binance = ahora

        # 1) Detectar posiciones cerradas por SL/TP y actualizar SQLite + cancelar huerfanas
        try:
            self._detectar_y_procesar_cierres()
        except Exception as e:
            self.bitacora.registrar_error("Sync Binance", f"Error detectando cierres: {e}")

        # 2) Snapshot de balance — solo cada intervalo_sync_balance_seg (120s)
        if ahora - self._ultima_sync_balance >= self.intervalo_sync_balance_seg:
            self._ultima_sync_balance = ahora
            try:
                self.actualizar_balance(forzar=True)
            except Exception as e:
                self.bitacora.registrar_error("Sync Binance", f"Error actualizando balance: {e}")

    def _detectar_y_procesar_cierres(self):
        """
        Detecta posiciones que Binance cerro via SL o TP pero que SQLite
        todavia registra como ACTIVA. Para cada una:
          1. Cancela en Binance las ordenes de proteccion huerfanas (la que no se ejecuto).
          2. Marca la posicion como CERRADA en SQLite y cancela sus ordenes activas.
          3. Corrige entry_price si es 0.0 (bug de sesiones anteriores sin avgPrice).
          4. Notifica por Telegram.
        Se invoca cada 30s desde sincronizar_con_binance().
        """
        posiciones_sqlite = self.registro.obtener_posiciones_abiertas(self.symbol)
        if not posiciones_sqlite:
            return  # Nada que verificar — evitamos la llamada a Binance innecesaria

        datos_binance = self.conexion.client.futures_position_information(symbol=self.symbol)

        # Mapa positionSide -> {amt, entryPrice}
        mapa_binance = {}
        for p in datos_binance:
            ps = str(p.get("positionSide", "")).upper()
            mapa_binance[ps] = {
                "amt":        float(p.get("positionAmt", 0)),
                "entryPrice": float(p.get("entryPrice", 0)),
            }

        ordenes_abiertas_cargadas = None  # Carga perezosa: solo si se detecta algun cierre

        for pos in posiciones_sqlite:
            direccion = str(pos.get("direccion", "")).upper()
            id_local  = pos.get("id_local")
            info      = mapa_binance.get(direccion, {"amt": 0, "entryPrice": 0})

            if info["amt"] == 0:
                # ── Posicion cerrada en Binance, aun ACTIVA en SQLite ──────────────
                self.bitacora.registrar_diagnostico(
                    "Sync_Cierres",
                    f"Posicion {direccion} id_local={id_local} cerrada en Binance. Procesando.",
                )

                # Cargar ordenes abiertas una sola vez por ciclo de sync
                if ordenes_abiertas_cargadas is None:
                    try:
                        ordenes_abiertas_cargadas = self.conexion.client.futures_get_open_orders(
                            symbol=self.symbol
                        )
                    except Exception as e_ord:
                        self.bitacora.registrar_error(
                            "Sync_Cierres", f"No se pudo obtener ordenes abiertas: {e_ord}"
                        )
                        ordenes_abiertas_cargadas = []

                # Cancelar ordenes de proteccion huerfanas (TP si SL disparo, o viceversa)
                side_proteccion = "SELL" if direccion == "LONG" else "BUY"
                for o in ordenes_abiertas_cargadas:
                    if (str(o.get("positionSide", "")).upper() == direccion and
                            str(o.get("side", "")).upper() == side_proteccion):
                        try:
                            self.conexion.client.futures_cancel_order(
                                symbol=self.symbol, orderId=o["orderId"]
                            )
                            self.bitacora.registrar_actividad(
                                "Sync_Cierres",
                                f"Orden huerfana {o['orderId']} ({o.get('type','?')}) cancelada.",
                            )
                        except Exception as e_cancel:
                            # -2011 = orden ya cancelada o ejecutada: es esperado, ignorar
                            self.bitacora.registrar_diagnostico(
                                "Sync_Cierres",
                                f"Orden {o['orderId']} no cancelable (ya ejecutada?): {e_cancel}",
                            )

                # Marcar CERRADA en SQLite + cancelar ordenes ACEPTADA asociadas
                try:
                    self.registro.cerrar_posicion(id_local)
                    self.registro.cancelar_ordenes_de_posicion(id_local)
                except Exception as e_sq:
                    self.bitacora.registrar_error(
                        "Sync_Cierres", f"Error actualizando SQLite: {e_sq}"
                    )

                # Notificar Telegram
                try:
                    self.notificador.enviar_mensaje(
                        f"✅ Posicion cerrada detectada\n"
                        f"Simbolo: {self.symbol}   Direccion: {direccion}\n"
                        f"ID local: {id_local}\n"
                        f"(SL o TP activado automaticamente en Binance)"
                    )
                except Exception:
                    pass

                self.log_ui(
                    f"📋 Cierre detectado: {direccion} {self.symbol} "
                    f"(id={id_local}) — SQLite y dashboard actualizados."
                )

            else:
                # ── Posicion aun abierta: corregir entry_price si es 0.0 ───────────
                # Bug de sesiones anteriores: MARKET orders guardaban precio_entrada=0.0
                precio_sqlite = float(pos.get("precio_entrada", 0))
                precio_binance = info["entryPrice"]
                if precio_sqlite == 0.0 and precio_binance > 0:
                    try:
                        self.registro.actualizar_precio_entrada(id_local, precio_binance)
                        self.bitacora.registrar_diagnostico(
                            "Sync_Cierres",
                            f"Entry price id={id_local} corregido desde Binance: {precio_binance}",
                        )
                    except Exception as e_precio:
                        self.bitacora.registrar_error(
                            "Sync_Cierres", f"Error actualizando entry price: {e_precio}"
                        )

    def obtener_valor_seguro(self, df, columna, posicion):
        return df[columna].iloc[posicion] if columna in df.columns else 0.0

    def procesar_comando_manual(self, comando):
        comando = comando.strip().lower()
        adn = self.comparador.adn['parametros']
        precio = self.estado_ui['precio_actual']

        self.bitacora.registrar_actividad("Consola", f"Comando manual recibido: {comando}")

        if comando == "k l 1":
            self.trading_permitido = False
            self.estado_ui['estado_bot'] = "[yellow]PAUSADO[/yellow]"
            self.log_ui("⏸️ KILLSWITCH ACTIVADO: Operaciones Pausadas.")
            self.bitacora.registrar_actividad("Main_Orquestador", "Trading pausado por usuario.")
            
        elif comando == "k l 2":
            self.trading_permitido = False
            self.estado_ui['estado_bot'] = "[red]EMERGENCIA[/red]"
            self.log_ui("🚨 EMERGENCIA: Pausando bot y cerrando posiciones...")
            self.bitacora.registrar_actividad("Main_Orquestador", "Pánico Nuclear activado por usuario.")
            self.ejecutar_panico_nuclear()

        elif comando == "r":
            self.trading_permitido = True
            self.estado_ui['estado_bot'] = "[green]OPERATIVO[/green]"
            self.log_ui("▶️ SISTEMA REANUDADO: Operaciones Activas.")
            self.bitacora.registrar_actividad("Main_Orquestador", "Trading reanudado por usuario.")

        elif comando.startswith("c "):
            try:
                qty = float(comando.split(" ")[1])
                self.log_ui(f"🧑‍💻 COMANDO RECIBIDO: LONG de {qty} lotes...")
                paquete = self.emisor.empaquetar_entrada(self.comparador.adn['id_estrategia'], {'senal':'LONG'}, precio, adn)
                self.ciclo_ejecucion(paquete, lote_manual=qty)
            except:
                self.log_ui("❌ Error de Sintaxis. Usa: c 1")

        elif comando.startswith("v "):
            try:
                qty = float(comando.split(" ")[1])
                self.log_ui(f"🧑‍💻 COMANDO RECIBIDO: SHORT de {qty} lotes...")
                paquete = self.emisor.empaquetar_entrada(self.comparador.adn['id_estrategia'], {'senal':'SHORT'}, precio, adn)
                self.ciclo_ejecucion(paquete, lote_manual=qty)
            except:
                self.log_ui("❌ Error de Sintaxis. Usa: v 1")
        else:
            if comando: self.log_ui(f"⚠️ Comando desconocido: '{comando}'")

    def ejecutar_panico_nuclear(self):
        try:
            # Pilar 2: cancelacion atomica con coordinador
            self.coordinador.ejecutar(
                accion=lambda: self.conexion.client.futures_cancel_all_open_orders(symbol=self.symbol),
                tipo_accion="CANCELAR_TODO",
                parametros_pendiente={"symbol": self.symbol},
            )
            # Para conocer posiciones a cerrar, sincronizamos con Binance una vez
            posiciones = self.conexion.client.futures_position_information(symbol=self.symbol)
            for pos in posiciones:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    side_salida = "SELL" if amt > 0 else "BUY"
                    pos_side = pos['positionSide']
                    self.coordinador.ejecutar(
                        accion=lambda s=side_salida, ps=pos_side, q=abs(amt): self.conexion.client.futures_create_order(
                            symbol=self.symbol, side=s, positionSide=ps,
                            type="MARKET", quantity=q
                        ),
                        tipo_accion="CERRAR_POSICION",
                        parametros_pendiente={
                            "symbol": self.symbol, "direccion": pos_side,
                            "cantidad": abs(amt), "precio": "MARKET",
                        },
                    )
                    self.bitacora.registrar_operacion("CERRAR_POSICION", self.symbol, side_salida, abs(amt), 0.0, "Cierre de Pánico")
            self.log_ui("☢️ POSICIONES LIQUIDADAS. El bot está inactivo.")
        except Exception as e:
            self.log_ui(f"❌ FALLO CRÍTICO EN KILLSWITCH: {e}")
            self.bitacora.registrar_error("Main_Orquestador", f"Fallo en Pánico Nuclear: {str(e)}")

    def _fetch_mtf_tf(self, tf, rsi_period):
        """Fetch + indicadores de un timeframe. Usado por el ThreadPoolExecutor."""
        velas = self.monitor.obtener_velas(self.symbol, tf)
        return tf, self.monitor.calcular_indicadores(velas, rsi_period)

    def ciclo_analisis(self):
        adn = self.comparador.adn['parametros']
        ahora = time.time()

        # PARALELIZACION MTF (Fase F): los 5 fetches al exchange se ejecutan
        # simultaneamente en lugar de secuencialmente. Reduce latencia ~5x.
        if ahora - self.ultimo_update_mtf >= 60 or not self.cache_mtf:
            try:
                tareas = [
                    ("1d", 14),
                    ("4h", adn['rsi_period_macro']),
                    ("1h", 14),
                    ("15m", adn['rsi_period_micro']),
                    ("5m", 14),
                ]
                futuros = [self._mtf_pool.submit(self._fetch_mtf_tf, tf, rsi)
                           for tf, rsi in tareas]
                for fut in futuros:
                    tf, df = fut.result(timeout=30)
                    self.cache_mtf[tf] = df
                self.ultimo_update_mtf = ahora
            except Exception as e:
                self.bitacora.registrar_error("Monitor_Mercado", f"Fallo al actualizar velas MTF: {str(e)}")
                self.log_ui(f"⚠️ Reintento de red MTF en el próximo ciclo.")
                return

        # CACHE 1M (Fase F): la vela 1m cierra cada 60s; refrescar cada 5s era
        # un fetch de Binance desperdiciado. Cacheamos `intervalo_1m_seg` segundos.
        try:
            if self.cache_1m is None or (ahora - self.ultimo_update_1m) >= self.intervalo_1m_seg:
                self.cache_1m = self.monitor.calcular_indicadores(
                    self.monitor.obtener_velas(self.symbol, "1m"), 14
                )
                self.ultimo_update_1m = ahora
            df_1m = self.cache_1m
        except Exception as e:
            self.bitacora.registrar_error("Monitor_Mercado", f"Fallo al actualizar vela 1m: {str(e)}")
            return

        dfs = {"1d": self.cache_mtf.get("1d"), "4h": self.cache_mtf.get("4h"), "1h": self.cache_mtf.get("1h"), 
               "15m": self.cache_mtf.get("15m"), "5m": self.cache_mtf.get("5m"), "1m": df_1m}
        
        if df_1m is not None and not df_1m.empty:
            self.estado_ui['precio_actual'] = df_1m.iloc[-1]['close']

        for tf, df in dfs.items():
            if df is not None and len(df) > 1:
                self.estado_ui['mtf'][tf]['rsi'] = [self.obtener_valor_seguro(df, 'rsi', -2), self.obtener_valor_seguro(df, 'rsi', -1)]
                self.estado_ui['mtf'][tf]['macd'] = [self.obtener_valor_seguro(df, 'macd', -2), self.obtener_valor_seguro(df, 'macd', -1)]
                self.estado_ui['mtf'][tf]['stoch'] = [self.obtener_valor_seguro(df, 'stochrsi', -2), self.obtener_valor_seguro(df, 'stochrsi', -1)]
                self.estado_ui['mtf'][tf]['adx'] = [self.obtener_valor_seguro(df, 'adx', -2), self.obtener_valor_seguro(df, 'adx', -1)]
                self.estado_ui['mtf'][tf]['vol'] = [self.obtener_valor_seguro(df, 'volume', -2), self.obtener_valor_seguro(df, 'volume', -1)]
                
                c_price = df.iloc[-1]['close']
                bb_up = self.obtener_valor_seguro(df, 'bb_upper', -1)
                bb_mid = self.obtener_valor_seguro(df, 'bb_mid', -1)
                bb_low = self.obtener_valor_seguro(df, 'bb_lower', -1)
                
                if bb_mid > 0:
                    ancho_pct = ((bb_up - bb_low) / bb_mid) * 100
                    dist_centro_pct = ((c_price - bb_mid) / bb_mid) * 100
                    if c_price >= bb_mid:
                        self.estado_ui['mtf'][tf]['bb'] = f"{ancho_pct:.1f}% | [green]{dist_centro_pct:+.2f}%[/green]"
                    else:
                        self.estado_ui['mtf'][tf]['bb'] = f"{ancho_pct:.1f}% | [red]{dist_centro_pct:+.2f}%[/red]"
                
                rsi_act = self.estado_ui['mtf'][tf]['rsi'][1]
                if rsi_act > 60: self.estado_ui['mtf'][tf]['trend'] = "[green]Alcista[/green]"
                elif rsi_act < 40: self.estado_ui['mtf'][tf]['trend'] = "[red]Bajista[/red]"
                else: self.estado_ui['mtf'][tf]['trend'] = "[yellow]Lateral[/yellow]"

        if not self.trading_permitido:
            return

        # precio_actual debe estar disponible para el ciclo IA incluso si VIP_ADN falla
        precio_actual = float(self.estado_ui.get('precio_actual', 0.0))

        if self.config_estrategias["VIP_ADN"] and self.cache_mtf.get("1h") is not None:
            try:
                df_1h = self.cache_mtf["1h"]
                df_4h = self.cache_mtf["4h"]
                df_15m = self.cache_mtf["15m"]
                
                scanner = StructureScanner(df_1h)
                scanner.precompute()
                ctx_fibo = scanner.get_fibonacci_context(len(df_1h) - 1)
                dist_fibo = min([abs(precio_actual - v) / precio_actual for v in ctx_fibo['fibs'].values()]) if ctx_fibo else 999

                signal = self.comparador.evaluar_mercado(df_4h, df_1h, df_15m, dist_fibo)
                
                if signal:
                    tipo_senal = signal.get('senal', 'UNKNOWN')
                    self.log_ui(f"🚨 ALERTA ESTRUCTURAL VIP: {tipo_senal}")
                    self.bitacora.registrar_actividad("Comparador VIP", f"Señal detectada: {tipo_senal}")
                    paquete = self.emisor.empaquetar_entrada(self.comparador.adn['id_estrategia'], signal, precio_actual, adn)
                    self.ciclo_ejecucion(paquete)
            except Exception as e:
                self.bitacora.registrar_error("Ruteo VIP", str(e))

        if self.config_estrategias["PIRAMIDE_MTF"] and self.estrategia_piramide and self.cache_mtf.get("1h") is not None:
            try:
                datos_mtf = {"1h": self.cache_mtf["1h"], "15m": self.cache_mtf["15m"], "5m": self.cache_mtf["5m"]}
                senal_mtf = self.estrategia_piramide.calcular_senyal(datos_mtf)

                if senal_mtf:
                    self.log_ui(f"⚡ ALERTA MTF: {senal_mtf['accion']} ({senal_mtf['motivo']})")
                    self.bitacora.registrar_actividad("Motor MTF", f"Señal detectada: {senal_mtf['accion']}")
                    self.ciclo_ejecucion_mtf(senal_mtf)
            except Exception as e:
                self.log_ui(f"⚠️ Error procesando Pirámide MTF: {e}")
                self.bitacora.registrar_error("Ruteo MTF", str(e))

        # -----------------------------------------------------------------------
        # CAPA IA: decision hibrida IA + Reglas Clasicas
        # Corre DESPUES de las reglas clasicas. Si la IA propone una accion
        # con alta confianza y las reglas clasicas no detectaron senal, la IA
        # puede abrir su propia posicion sobre el porcentaje de capital asignado.
        # -----------------------------------------------------------------------
        if self._ia_activa and self.ia_client is not None:
            try:
                self._ciclo_ia(precio_actual)
            except Exception as e_ia:
                self.bitacora.registrar_error("IA_Local", f"Ciclo IA fallo: {e_ia}")

    # =========================================================================
    # MODULO IA: LOGICA HIBRIDA
    # =========================================================================

    def _construir_obs_ia(self, precio_actual: float) -> object:
        """
        Construye el vector de observacion para la IA (OBS_SPACE_DIM dims)
        usando los DataFrames del cache MTF y el estado del portfolio.

        El vector es aplanado en el mismo orden que usa MTFTensorBuilder,
        por lo que el MarketFeatureExtractor puede reconstruir los slices.

        Si el cache MTF esta incompleto, retorna None (la IA no se consulta).
        """
        if not _IA_DISPONIBLE:
            return None
        try:
            from ia_local.config import TIMEFRAMES, WINDOW_SIZES, FEATURES_POR_TF

            partes = []
            for tf in TIMEFRAMES:
                df = self.cache_mtf.get(tf)
                if df is None or len(df) == 0:
                    # Si falta un TF, rellenar con ceros
                    window = WINDOW_SIZES[tf]
                    n_feat = len(FEATURES_POR_TF[tf])
                    partes.append(_np_ia.zeros(window * n_feat, dtype=_np_ia.float32))
                    continue

                feats  = FEATURES_POR_TF[tf]
                window = WINDOW_SIZES[tf]
                # Tomar las ultimas `window` filas y las columnas de features
                cols_disponibles = [c for c in feats if c in df.columns]
                n_feat = len(feats)

                if cols_disponibles:
                    slice_df = df[cols_disponibles].iloc[-window:].values.astype(_np_ia.float32)
                    # Rellenar columnas faltantes con ceros
                    if len(cols_disponibles) < n_feat:
                        pad_cols = n_feat - len(cols_disponibles)
                        slice_df = _np_ia.hstack([
                            slice_df,
                            _np_ia.zeros((slice_df.shape[0], pad_cols), dtype=_np_ia.float32)
                        ])
                    # Asegurar que tiene exactamente `window` filas
                    if slice_df.shape[0] < window:
                        pad_rows = window - slice_df.shape[0]
                        slice_df = _np_ia.vstack([
                            _np_ia.zeros((pad_rows, n_feat), dtype=_np_ia.float32),
                            slice_df
                        ])
                    partes.append(slice_df[:window].flatten())
                else:
                    partes.append(_np_ia.zeros(window * n_feat, dtype=_np_ia.float32))

            market_flat = _np_ia.concatenate(partes).astype(_np_ia.float32)

            # Estado del portfolio (9 dims: 6 base + 3 TSL segun PORTFOLIO_STATE_DIM)
            balance     = self.estado_ui.get("balance_actual", 2000.0) or 2000.0
            balance_ini = self.estado_ui.get("balance_inicial", 2000.0) or 2000.0
            posiciones  = self.estado_ui.get("posiciones_activas", [])
            tiene_pos   = 1.0 if posiciones else 0.0
            pnl_pos     = sum(float(p.get("pnl_pct", 0)) for p in posiciones) if posiciones else 0.0
            capital_ratio = min(balance / max(balance_ini, 1.0), 2.0) - 1.0  # [-1, 1]
            drawdown    = max(0.0, (balance_ini - balance) / max(balance_ini, 1.0))
            entradas_hoy = float(self.estado_ui.get("entradas_hoy", 0))
            overtrade   = min(entradas_hoy / 8.0, 1.0)
            # TSL dims: ratio posicion restante, distancia TSL normalizada, incertidumbre
            # Cuando no hay posicion abierta: ratio=0, tsl_dist=2.0/10=0.2 (neutro), incert=0
            ratio_pos_rest = 1.0 if posiciones else 0.0  # posicion completa = 1.0
            tsl_dist_norm  = 0.2   # 2.0 ATR / 10 = 0.2 (distancia normal normalizada)
            incertidumbre  = 0.0   # el servidor IA calcula esto; aqui siempre 0.0

            portfolio_vec = _np_ia.array([
                capital_ratio,
                tiene_pos,
                min(max(pnl_pos, -1.0), 1.0),
                min(drawdown, 1.0),
                overtrade,
                0.0,           # dist_sl (no disponible directamente aqui)
                ratio_pos_rest,
                tsl_dist_norm,
                incertidumbre,
            ], dtype=_np_ia.float32)

            obs = _np_ia.concatenate([market_flat, portfolio_vec])
            obs = _np_ia.nan_to_num(obs, nan=0.0, posinf=1.0, neginf=-1.0)
            return obs

        except Exception as e:
            self.bitacora.registrar_error("IA_Obs", f"Error construyendo obs: {e}")
            return None

    def _ciclo_ia(self, precio_actual: float):
        """
        Consulta la IA y, si tiene confianza suficiente, abre una posicion
        sobre el porcentaje de capital asignado al modulo IA (IA_CAPITAL_PCT=70%).

        Logica hibrida:
        - Si la IA propone LONG/SHORT con confianza >= CONFIANZA_IA_SOLO: ejecuta.
        - Si confianza < umbral: ignora la IA, las reglas clasicas ya decidieron.
        - La IA no interfiere con posiciones abiertas por las reglas clasicas.
        - La experiencia del paso siempre se envia al OnlineTrainer para aprendizaje.
        """
        obs = self._construir_obs_ia(precio_actual)
        if obs is None:
            return

        # Guardar obs para calcular la experiencia en el siguiente ciclo
        obs_prev = self._ultimo_obs_ia
        self._ultimo_obs_ia = obs

        # Consultar servidor IA (timeout = 0.5s — no bloquea el ciclo)
        resultado_ia = self.ia_client.predecir(obs, deterministic=True)
        if resultado_ia is None:
            self._ia_activa = False
            self.log_ui("⚠️ Servidor IA desconectado. Modo reglas clasicas.")
            return

        accion    = resultado_ia.get("accion", 0)
        confianza = resultado_ia.get("confianza", 0.0)
        regimen   = resultado_ia.get("regimen", "?")

        # Actualizar UI con estado de la IA
        self.log_ui(
            f"🤖 IA: accion={accion} | conf={confianza:.2f} | "
            f"regimen={regimen} | lat={resultado_ia.get('latencia_ms',0):.1f}ms"
        )

        # --- Decision de ejecucion ---
        # Acciones IA: 0=HOLD, 1-3=LONG, 4-6=SHORT, 7=CLOSE, 8-9=PIRAMIDE
        LONG_ACCIONES  = {1, 2, 3}
        SHORT_ACCIONES = {4, 5, 6}

        if confianza < CONFIANZA_IA_SOLO:
            # Confianza insuficiente: la IA pasa, las reglas clasicas mandan
            return

        posiciones_activas = self.estado_ui.get("posiciones_activas", [])
        if posiciones_activas:
            # Ya hay posicion abierta: la IA no abre encima por seguridad
            return

        if accion in LONG_ACCIONES:
            side_ia = "BUY"
        elif accion in SHORT_ACCIONES:
            side_ia = "SELL"
        else:
            return  # HOLD o CLOSE: no actuar

        # Sizing: porcentaje del capital asignado a la IA
        self.actualizar_balance()
        capital_ia   = self.estado_ui["balance_actual"] * IA_CAPITAL_PCT
        adn          = self.comparador.adn["parametros"]
        sl_pct       = adn.get("stop_loss_pct", 0.019)
        tp_pct       = adn.get("take_profit_pct", 0.043)
        cantidad_ia  = (capital_ia * self.porcentaje_riesgo) / (precio_actual * sl_pct)
        cantidad_ia  = round(cantidad_ia, 1)

        if cantidad_ia <= 0:
            return

        self.log_ui(
            f"🤖 IA EJECUTANDO: {side_ia} | conf={confianza:.2f} | "
            f"qty={cantidad_ia} | regimen={regimen}"
        )
        self.bitacora.registrar_actividad(
            "IA_Local",
            f"Accion IA: {side_ia} qty={cantidad_ia} conf={confianza:.2f} regimen={regimen}"
        )

        # Construir paquete de senal compatible con ciclo_ejecucion
        paquete_ia = {
            "side":            side_ia,
            "precio_referencia": precio_actual,
            "sl_pct":          sl_pct,
            "tp_pct":          tp_pct,
            "id_estrategia":   "IA_LOCAL",
        }
        self.ciclo_ejecucion(paquete_ia, lote_manual=cantidad_ia)

    # =========================================================================

    def ciclo_ejecucion(self, paquete_senal, lote_manual=None):
        side = paquete_senal['side']
        precio_referencia = paquete_senal['precio_referencia']
        sl_pct = paquete_senal['sl_pct']

        precio_mercado = float(self.conexion.client.futures_symbol_ticker(symbol=self.symbol)['price'])
        self.actualizar_balance()
        
        # --- RIESGO INSTITUCIONAL: LOTE CALCULADO EN BASE AL STOP LOSS ---
        capital_en_riesgo = self.estado_ui['balance_actual'] * self.porcentaje_riesgo
        
        if lote_manual is not None:
            cantidad_monedas = lote_manual
            self.log_ui(f"⚠️ Aplicando Override de Riesgo: {cantidad_monedas} Lotes.")
            self.bitacora.registrar_actividad("Gestor de Riesgo", f"Override manual activado: {cantidad_monedas} lotes.")
        else:
            if not self.evaluador.validar_viabilidad(paquete_senal, precio_mercado): 
                self.bitacora.registrar_actividad("Evaluador VIP", "Entrada rechazada (Filtro de viabilidad).")
                return
            if not self.gestor.solicitar_cupo(side, precio_referencia): 
                self.bitacora.registrar_actividad("Gestor Cupos", "Entrada rechazada (Cupo máximo alcanzado).")
                return
            
            # Cantidad = Riesgo_Maximo / (Precio_Actual * Porcentaje_SL)
            cantidad_monedas = capital_en_riesgo / (precio_mercado * sl_pct)
            self.bitacora.registrar_actividad("Gestor de Riesgo", f"Aprobación VIP: Calculados {cantidad_monedas:.3f} lotes para un riesgo de ${capital_en_riesgo:.2f}")

        # COOLDOWN: no abrir si pasaron menos de COOLDOWN_ENTRADA_SEG desde la ultima entrada
        ahora = time.time()
        if ahora - self._timestamp_ultima_entrada < self.COOLDOWN_ENTRADA_SEG:
            restante = int(self.COOLDOWN_ENTRADA_SEG - (ahora - self._timestamp_ultima_entrada))
            self.bitacora.registrar_diagnostico(
                "Gestor Entradas", f"Cooldown activo: {restante}s restantes para nueva entrada."
            )
            return

        try:
            resultado_orden = self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side=side, tipo_orden="MARKET",
                cantidad=cantidad_monedas, precio=None, price_precision=2, qty_precision=1
            )
            # GUARD CRITICO: si la orden no fue confirmada por Binance,
            # NO colocar protecciones para no crear SL/TP sin posicion asociada.
            if resultado_orden is None:
                self.log_ui("⚠️ Orden VIP no confirmada por Binance — se omiten protecciones.")
                self.bitacora.registrar_diagnostico(
                    "Disparador VIP", "Orden retorno None — protecciones abortadas."
                )
                return

            self.estado_ui['entradas_hoy'] += 1
            self._timestamp_ultima_entrada = time.time()
            self.bitacora.registrar_operacion("ABRIR_POSICION", self.symbol, side, round(cantidad_monedas, 1), precio_mercado, "Estrategia VIP")

            if lote_manual is None:
                try:
                    self.gestor.registrar_apertura(f"ORD_{int(time.time())}", "VIP")
                except Exception:
                    pass

            sl_price = precio_mercado * (1 - sl_pct) if side == 'BUY' else precio_mercado * (1 + sl_pct)
            tp_price = precio_mercado * (1 + paquete_senal['tp_pct']) if side == 'BUY' else precio_mercado * (1 - paquete_senal['tp_pct'])
            qty_formateada = round(cantidad_monedas, 1)

            # id_posicion_local viene embebido en la respuesta si el disparador lo registro
            id_posicion_local = None
            if isinstance(resultado_orden, dict):
                id_posicion_local = resultado_orden.get("__id_posicion_local")

            # Colocar Protecciones (Pilar 3: nuevo antes de cancelar viejo)
            self.asegurador.colocar_protecciones(
                symbol=self.symbol,
                side_entrada=side,
                cantidad=qty_formateada,
                sl_price=sl_price,
                tp_price=tp_price,
                price_precision=2,
                id_posicion_local=id_posicion_local,
            )
            self.log_ui(f"✅ PROTECCIÓN VIP ACTIVA. SL: {sl_price:.2f} | TP: {tp_price:.2f}")
        except Exception as e:
            self.log_ui(f"❌ Fallo crítico en disparador VIP: {e}")
            self.bitacora.registrar_error("Disparador VIP", str(e))

    def ciclo_ejecucion_mtf(self, senal):
        lado = senal['lado']
        accion = senal['accion']

        # GUARDIA: no abrir si ya hay posicion activa (evita piramidacion no controlada)
        posiciones_ui = self.estado_ui.get("posiciones_activas", [])
        if posiciones_ui:
            return
        # Fallback directo a SQLite si la UI no esta actualizada aun
        try:
            if self.registro is not None and self.registro.obtener_posiciones_abiertas(self.symbol):
                return
        except Exception:
            pass

        self.actualizar_balance()

        fraccion = senal.get('reducir_contraria', 0)
        if fraccion > 0:
            lado_contrario = "SHORT" if lado == "LONG" else "LONG"
            self.log_ui(f"✂️ MTF: Reduciendo {fraccion*100}% posición {lado_contrario}")

        precio_mercado = float(self.conexion.client.futures_symbol_ticker(symbol=self.symbol)['price'])
        
        # --- RIESGO INSTITUCIONAL MTF ---
        sl_pct = senal.get('sl_pct', 0.02) # Extrae el SL de MTF o asume 2% por seguridad
        tp_pct = senal.get('tp_pct', 0.04) # Asume 4% si no lo envía
        
        capital_en_riesgo = self.estado_ui['balance_actual'] * self.porcentaje_riesgo
        cantidad_base = capital_en_riesgo / (precio_mercado * sl_pct)
        cantidad_final = cantidad_base * senal.get('lotaje', 1.0)
        self.bitacora.registrar_actividad("Gestor de Riesgo", f"Aprobación MTF: Calculados {cantidad_final:.3f} lotes.")
        
        side_binance = "BUY" if lado == "LONG" else "SELL"
        side_salida = "SELL" if side_binance == "BUY" else "BUY"
        pos_side = "LONG" if side_binance == "BUY" else "SHORT"
        
        tipo_orden = senal.get('tipo_orden', 'MARKET')
        precio_limit = senal.get('precio_limit', None)
        
        # COOLDOWN: no abrir si pasaron menos de COOLDOWN_ENTRADA_SEG desde la ultima entrada
        ahora = time.time()
        if ahora - self._timestamp_ultima_entrada < self.COOLDOWN_ENTRADA_SEG:
            restante = int(self.COOLDOWN_ENTRADA_SEG - (ahora - self._timestamp_ultima_entrada))
            self.bitacora.registrar_diagnostico(
                "Gestor Entradas", f"Cooldown MTF activo: {restante}s restantes."
            )
            return

        try:
            resultado_orden = self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side=side_binance, tipo_orden=tipo_orden,
                cantidad=cantidad_final, precio=precio_limit, price_precision=2, qty_precision=1
            )
            # GUARD CRITICO: si la orden no fue confirmada por Binance,
            # NO colocar protecciones para no crear SL/TP sin posicion asociada.
            if resultado_orden is None:
                self.log_ui("⚠️ Orden MTF no confirmada por Binance — se omiten protecciones.")
                self.bitacora.registrar_diagnostico(
                    "Disparador MTF", "Orden retorno None — protecciones abortadas."
                )
                return

            self.estado_ui['entradas_hoy'] += 1
            self._timestamp_ultima_entrada = time.time()
            self.log_ui(f"✅ MTF {lado} Ejecutado | Lotes: {senal.get('lotaje', 1.0)}")
            self.bitacora.registrar_operacion("ABRIR_POSICION", self.symbol, side_binance, round(cantidad_final, 1), precio_mercado, "Estrategia MTF")

            # Colocar Protecciones (Pilar 3: nuevo antes de cancelar viejo)
            sl_price = precio_mercado * (1 - sl_pct) if side_binance == 'BUY' else precio_mercado * (1 + sl_pct)
            tp_price = precio_mercado * (1 + tp_pct) if side_binance == 'BUY' else precio_mercado * (1 - tp_pct)
            qty_formateada = round(cantidad_final, 1)

            id_posicion_local = None
            if isinstance(resultado_orden, dict):
                id_posicion_local = resultado_orden.get("__id_posicion_local")

            self.asegurador.colocar_protecciones(
                symbol=self.symbol,
                side_entrada=side_binance,
                cantidad=qty_formateada,
                sl_price=sl_price,
                tp_price=tp_price,
                price_precision=2,
                id_posicion_local=id_posicion_local,
            )
            self.log_ui(f"✅ PROTECCIÓN MTF ACTIVA. SL: {sl_price:.2f} | TP: {tp_price:.2f}")

            if senal.get('use_trailing', False):
                self.log_ui(f"🌊 MTF: Activando Trailing Stop de la Ola...")

        except Exception as e:
            self.log_ui(f"❌ Fallo MTF: {e}")
            self.bitacora.registrar_error("Disparador MTF", str(e))

    # =========================================================================
    # HILOS ESPECIALIZADOS (R1: Refactor profundo - un departamento por hilo)
    # SQLite WAL permite acceso concurrente seguro entre todos ellos.
    # =========================================================================

    def _en_pausa_fin_de_semana(self) -> bool:
        """Devuelve True si es fin de semana y aplica el cambio de estado UI."""
        if datetime.now().weekday() >= 5:
            if self.estado_ui['estado_bot'] != "[yellow]REPOSO (FIN DE SEMANA)[/yellow]":
                self.estado_ui['estado_bot'] = "[yellow]REPOSO (FIN DE SEMANA)[/yellow]"
                self.log_ui("💤 Pausando bot por fin de semana.")
                self.bitacora.registrar_actividad("Main_Orquestador", "Pausa automática por fin de semana.")
            return True
        if self.estado_ui['estado_bot'] == "[yellow]REPOSO (FIN DE SEMANA)[/yellow]":
            self.estado_ui['estado_bot'] = "[green]OPERATIVO[/green]"
            self.log_ui("▶️ Apertura de mercado. Reanudando operaciones.")
            self.bitacora.registrar_actividad("Main_Orquestador", "Reanudación automática, apertura de mercado.")
        return False

    def hilo_motor_trading(self):
        """Hilo principal: ping de latencia + ciclo de analisis (cada 5s)."""
        while True:
            try:
                if self._en_pausa_fin_de_semana():
                    time.sleep(60)
                    continue

                ping_start = time.time()
                self.conexion.client.ping()
                self.estado_ui['latencia'] = f"{int((time.time() - ping_start)*1000)}ms"

                self.ciclo_analisis()

                self._ciclo_actual += 1
                time.sleep(5)
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Motor_Trading", str(e))
                with open("sentinel_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.now()}] ERROR EN HILO MOTOR:\n{traceback.format_exc()}\n")
                time.sleep(5)

    def hilo_estado_local(self):
        """PILAR 1: lee balance y posiciones del SQLite cada 5s. Sin tocar Binance."""
        while True:
            try:
                if self._en_pausa_fin_de_semana():
                    time.sleep(60)
                    continue
                self.actualizar_balance()
                self.actualizar_posiciones_en_vivo()
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Estado_Local", str(e))
            time.sleep(5)

    def hilo_sincronizacion_binance(self):
        """PILAR 1: detecta cierres SL/TP cada 30s; balance real cada 120s."""
        while True:
            try:
                if self._en_pausa_fin_de_semana():
                    time.sleep(60)
                    continue
                self.sincronizar_con_binance()
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Sync_Binance", str(e))
            time.sleep(self.intervalo_sync_binance_seg)

    def hilo_pendientes(self):
        """PILAR 2: procesa la cola de procesos pendientes cada 5s."""
        while True:
            try:
                self.gestor_pendientes.procesar_pendientes(self._ciclo_actual)
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Pendientes", str(e))
            time.sleep(5)

    def hilo_control_riesgo(self):
        """Audita posiciones para Break Even / Trailing Stop. Lee del registro local."""
        while True:
            try:
                if self._en_pausa_fin_de_semana():
                    time.sleep(60)
                    continue
                self.controlador_trailing.auditar_posiciones(
                    symbol=self.symbol, price_precision=2,
                    mark_price=self.estado_ui.get('precio_actual') or None,
                )
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Control_Riesgo", str(e))
            time.sleep(5)

    def hilo_escucha_teclado(self):
        while True:
            if msvcrt.kbhit():
                tecla = msvcrt.getch()
                try:
                    tecla_str = tecla.decode('utf-8')
                    if tecla == b'\r': 
                        if self.estado_ui["comando_buffer"].strip():
                            self.procesar_comando_manual(self.estado_ui["comando_buffer"])
                        self.estado_ui["comando_buffer"] = ""
                    elif tecla == b'\x08': 
                        self.estado_ui["comando_buffer"] = self.estado_ui["comando_buffer"][:-1]
                    else:
                        self.estado_ui["comando_buffer"] += tecla_str
                except:
                    pass
            time.sleep(0.05) 

    def arrancar_sistema(self):
        try:
            self.conexion.client.futures_change_leverage(symbol=self.symbol, leverage=self.comparador.adn['parametros']['leverage'])
            self.conexion.client.futures_change_margin_type(symbol=self.symbol, marginType='ISOLATED')
            self.conexion.client.futures_change_position_mode(dualSidePosition="true") 
        except Exception: pass

        self.actualizar_balance(es_inicio=True)

        # --- Hilos especializados (R1: refactor profundo) ---
        threading.Thread(target=self.hilo_motor_trading, daemon=True, name="Motor").start()
        threading.Thread(target=self.hilo_estado_local, daemon=True, name="EstadoLocal").start()
        threading.Thread(target=self.hilo_sincronizacion_binance, daemon=True, name="SyncBinance").start()
        threading.Thread(target=self.hilo_pendientes, daemon=True, name="Pendientes").start()
        threading.Thread(target=self.hilo_control_riesgo, daemon=True, name="ControlRiesgo").start()
        threading.Thread(target=self.hilo_escucha_teclado, daemon=True, name="Teclado").start()
        
        telegram = ControladorTelegram(TELEGRAM_TOKEN, self)
        telegram.iniciar()
        self.bitacora.registrar_actividad("Main_Orquestador", "Hilo motor, escucha y Telegram iniciados.")

        # ===================================================================
        # LA CAJA NEGRA: SISTEMA DUAL DE LOGS (PANTALLA + ARCHIVO DEBUG)
        # ===================================================================
        terminal_original = sys.stdout
        stderr_original = sys.stderr
        consola_nativa = Console(file=terminal_original)

        class AtrapaPrints:
            def __init__(self, estado_ui):
                self.estado_ui = estado_ui
                self.log_file = open("sentinel_debug.log", "a", encoding="utf-8")
                self.log_file.write(f"\n--- INICIO DE SESIÓN: {datetime.now()} ---\n")
                
            def write(self, msg):
                self.log_file.write(msg)
                self.log_file.flush()
                
                lineas = [l for l in msg.split('\n') if l.strip()]
                if lineas:
                    lista = self.estado_ui.setdefault("mensajes_sistema", [])
                    for linea in lineas:
                        if "File " not in linea and "line " not in linea:
                            lista.append(linea[:130]) 
                    while len(lista) > 6:
                        lista.pop(0)
                        
            def flush(self): pass

        atrapador = AtrapaPrints(self.estado_ui)
        sys.stdout = atrapador
        sys.stderr = atrapador 
        # ===================================================================

        with Live(DashboardSentinel.generar_vista(self.estado_ui, self.symbol), console=consola_nativa, refresh_per_second=2, screen=True) as live:
            while True:
                try:
                    live.update(DashboardSentinel.generar_vista(self.estado_ui, self.symbol))
                    time.sleep(0.5)
                except KeyboardInterrupt:
                    sys.stdout = terminal_original 
                    sys.stderr = stderr_original
                    self.bitacora.registrar_actividad("Main_Orquestador", "Sistema apagado por el usuario (Ctrl+C).")
                    break
                except Exception as e:
                    self.bitacora.registrar_error("Interfaz UI", str(e))
                    with open("sentinel_debug.log", "a", encoding="utf-8") as f:
                        f.write(f"\n[{datetime.now()}] ERROR EN UI LIVE:\n{traceback.format_exc()}\n")

if __name__ == "__main__":
    bot = OrquestadorCentral(symbol="AAVEUSDT")
    bot.arrancar_sistema()