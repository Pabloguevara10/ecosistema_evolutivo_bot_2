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
carpetas_deptos = ["dep_herramientas", "dep_analisis", "dep_ejecucion", "dep_salud"]
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
    from reporte_diagnostico import ReporteDiagnostico
except ImportError as e:
    print(f"❌ Error de Importación: {e}")
    sys.exit(1)

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
        
        self.conexion = ConexionWrapper(API_KEY, API_SECRET, testnet=True)
        self.auditor = AuditorRed(self.conexion, self.bitacora)
        self.monitor_hw = MonitorRecursos(self.bitacora)
        self.diagnostico = ReporteDiagnostico(self.monitor_hw, self.bitacora)
        self.monitor = MonitorMercado(self.conexion.client)
        self.comparador = ComparadorEstrategias()
        self.emisor = EmisorSenales()
        self.gestor = GestorCupos()
        self.evaluador = EvaluadorEntradas(self.gestor)
        self.disparador = DisparadorBinance(self.conexion)
        self.asegurador = AseguradorPosicion(self.conexion, self.disparador)

        # RIESGO INSTITUCIONAL: 5% del balance por operación (calculado vs Stop Loss)
        self.porcentaje_riesgo = 0.05 

        self.bitacora.registrar_actividad("Main_Orquestador", "Módulos instanciados y variables de estado cargadas.")

    def log_ui(self, mensaje):
        hora = datetime.now().strftime("%H:%M:%S")
        texto = f"[{hora}] {mensaje}"
        print(texto)

    def actualizar_balance(self, es_inicio=False):
        try:
            balances = self.conexion.client.futures_account_balance()
            for b in balances:
                if b['asset'] == 'USDT':
                    saldo = float(b['balance'])
                    self.estado_ui['balance_actual'] = saldo
                    if es_inicio:
                        self.estado_ui['balance_inicial'] = saldo
                    return
        except Exception as e:
            self.bitacora.registrar_error("Conexión Binance", f"Error actualizando balance: {str(e)}")

    def actualizar_posiciones_en_vivo(self):
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
            self.conexion.client.futures_cancel_all_open_orders(symbol=self.symbol)
            posiciones = self.conexion.client.futures_position_information(symbol=self.symbol)
            for pos in posiciones:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    side_salida = "SELL" if amt > 0 else "BUY"
                    pos_side = pos['positionSide'] 
                    self.conexion.client.futures_create_order(
                        symbol=self.symbol, side=side_salida, positionSide=pos_side,
                        type="MARKET", quantity=abs(amt)
                    )
                    self.bitacora.registrar_operacion("CERRAR_POSICION", self.symbol, side_salida, abs(amt), 0.0, "Cierre de Pánico")
            self.log_ui("☢️ POSICIONES LIQUIDADAS. El bot está inactivo.")
        except Exception as e:
            self.log_ui(f"❌ FALLO CRÍTICO EN KILLSWITCH: {e}")
            self.bitacora.registrar_error("Main_Orquestador", f"Fallo en Pánico Nuclear: {str(e)}")

    def ciclo_analisis(self):
        adn = self.comparador.adn['parametros']
        ahora = time.time()
        
        if ahora - self.ultimo_update_mtf >= 60 or not self.cache_mtf:
            try:
                self.cache_mtf["1d"] = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "1d"), 14)
                self.cache_mtf["4h"] = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "4h"), adn['rsi_period_macro'])
                self.cache_mtf["1h"] = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "1h"), 14)
                self.cache_mtf["15m"] = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "15m"), adn['rsi_period_micro'])
                self.cache_mtf["5m"] = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "5m"), 14)
                self.ultimo_update_mtf = ahora
            except Exception as e:
                self.bitacora.registrar_error("Monitor_Mercado", f"Fallo al actualizar velas MTF: {str(e)}")
                self.log_ui(f"⚠️ Reintento de red MTF en el próximo ciclo.")
                return 
        
        try:
            df_1m = self.monitor.calcular_indicadores(self.monitor.obtener_velas(self.symbol, "1m"), 14)
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

        if self.config_estrategias["VIP_ADN"] and self.cache_mtf.get("1h") is not None:
            try:
                df_1h = self.cache_mtf["1h"]
                df_4h = self.cache_mtf["4h"]
                df_15m = self.cache_mtf["15m"]
                
                scanner = StructureScanner(df_1h)
                scanner.precompute()
                precio_actual = self.estado_ui['precio_actual'] 
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

        try:
            self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side=side, tipo_orden="MARKET",
                cantidad=cantidad_monedas, precio=None, price_precision=2, qty_precision=1    
            )
            self.estado_ui['entradas_hoy'] += 1
            self.bitacora.registrar_operacion("ABRIR_POSICION", self.symbol, side, round(cantidad_monedas, 1), precio_mercado, "Estrategia VIP")

            if lote_manual is None:
                self.gestor.registrar_entrada(f"ORD_{int(time.time())}", side, precio_mercado)
            
            sl_price = precio_mercado * (1 - sl_pct) if side == 'BUY' else precio_mercado * (1 + sl_pct)
            tp_price = precio_mercado * (1 + paquete_senal['tp_pct']) if side == 'BUY' else precio_mercado * (1 - paquete_senal['tp_pct'])
            side_salida = "SELL" if side == "BUY" else "BUY"
            pos_side = "LONG" if side == "BUY" else "SHORT"
            qty_formateada = round(cantidad_monedas, 1)

            # Colocar Protecciones
            self.conexion.client.futures_create_order(symbol=self.symbol, side=side_salida, positionSide=pos_side, type="STOP_MARKET", stopPrice=round(sl_price, 2), quantity=qty_formateada)
            self.bitacora.registrar_operacion("COLOCAR_SL", self.symbol, side_salida, qty_formateada, round(sl_price, 2), "Estrategia VIP")
            
            self.conexion.client.futures_create_order(symbol=self.symbol, side=side_salida, positionSide=pos_side, type="TAKE_PROFIT_MARKET", stopPrice=round(tp_price, 2), quantity=qty_formateada)
            self.bitacora.registrar_operacion("COLOCAR_TP", self.symbol, side_salida, qty_formateada, round(tp_price, 2), "Estrategia VIP")
            
            self.log_ui(f"✅ PROTECCIÓN VIP ACTIVA. SL: {sl_price:.2f} | TP: {tp_price:.2f}")
        except Exception as e:
            self.log_ui(f"❌ Fallo crítico en disparador VIP: {e}")
            self.bitacora.registrar_error("Disparador VIP", str(e))

    def ciclo_ejecucion_mtf(self, senal):
        lado = senal['lado']
        accion = senal['accion']
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
        
        try:
            self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side=side_binance, tipo_orden=tipo_orden,
                cantidad=cantidad_final, precio=precio_limit, price_precision=2, qty_precision=1    
            )
            self.estado_ui['entradas_hoy'] += 1
            self.log_ui(f"✅ MTF {lado} Ejecutado | Lotes: {senal.get('lotaje', 1.0)}")
            self.bitacora.registrar_operacion("ABRIR_POSICION", self.symbol, side_binance, round(cantidad_final, 1), precio_mercado, "Estrategia MTF")
            
            # --- NUEVO: COLOCACIÓN DE PROTECCIONES EN MTF ---
            sl_price = precio_mercado * (1 - sl_pct) if side_binance == 'BUY' else precio_mercado * (1 + sl_pct)
            tp_price = precio_mercado * (1 + tp_pct) if side_binance == 'BUY' else precio_mercado * (1 - tp_pct)
            qty_formateada = round(cantidad_final, 1)

            self.conexion.client.futures_create_order(symbol=self.symbol, side=side_salida, positionSide=pos_side, type="STOP_MARKET", stopPrice=round(sl_price, 2), quantity=qty_formateada)
            self.bitacora.registrar_operacion("COLOCAR_SL", self.symbol, side_salida, qty_formateada, round(sl_price, 2), "Estrategia MTF")
            
            self.conexion.client.futures_create_order(symbol=self.symbol, side=side_salida, positionSide=pos_side, type="TAKE_PROFIT_MARKET", stopPrice=round(tp_price, 2), quantity=qty_formateada)
            self.bitacora.registrar_operacion("COLOCAR_TP", self.symbol, side_salida, qty_formateada, round(tp_price, 2), "Estrategia MTF")
            self.log_ui(f"✅ PROTECCIÓN MTF ACTIVA. SL: {sl_price:.2f} | TP: {tp_price:.2f}")

            if senal.get('use_trailing', False):
                self.log_ui(f"🌊 MTF: Activando Trailing Stop de la Ola...")
                
        except Exception as e:
            self.log_ui(f"❌ Fallo MTF: {e}")
            self.bitacora.registrar_error("Disparador MTF", str(e))

    def hilo_motor_trading(self):
        while True:
            try:
                if datetime.now().weekday() >= 5:
                    if self.estado_ui['estado_bot'] != "[yellow]REPOSO (FIN DE SEMANA)[/yellow]":
                        self.estado_ui['estado_bot'] = "[yellow]REPOSO (FIN DE SEMANA)[/yellow]"
                        self.log_ui("💤 Pausando bot por fin de semana.")
                        self.bitacora.registrar_actividad("Main_Orquestador", "Pausa automática por fin de semana.")
                    time.sleep(60) 
                    continue
                else:
                    if self.estado_ui['estado_bot'] == "[yellow]REPOSO (FIN DE SEMANA)[/yellow]":
                        self.estado_ui['estado_bot'] = "[green]OPERATIVO[/green]"
                        self.log_ui("▶️ Apertura de mercado. Reanudando operaciones.")
                        self.bitacora.registrar_actividad("Main_Orquestador", "Reanudación automática, apertura de mercado.")

                ping_start = time.time()
                self.conexion.client.ping()
                self.estado_ui['latencia'] = f"{int((time.time() - ping_start)*1000)}ms"
                
                self.ciclo_analisis()
                self.actualizar_balance()
                self.actualizar_posiciones_en_vivo()
                
                time.sleep(5)
            except Exception as e:
                self.bitacora.registrar_error("Hilo_Motor_Trading", str(e))
                with open("sentinel_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.now()}] ERROR EN HILO MOTOR:\n{traceback.format_exc()}\n")
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

        threading.Thread(target=self.hilo_motor_trading, daemon=True).start()
        threading.Thread(target=self.hilo_escucha_teclado, daemon=True).start()
        
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