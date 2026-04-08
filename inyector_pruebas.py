# =============================================================================
# NOMBRE: inyector_pruebas.py
# UBICACIÓN: RAÍZ DEL PROYECTO
# OBJETIVO: Módulo independiente de Pruebas de Integración (Integration Testing).
# Permite inyectar señales falsas para validar sintaxis de Binance y Telegram.
# =============================================================================

import os
import sys
import time
import requests
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

# --- 🔑 CARGA DE CREDENCIALES DESDE .env ---
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY_TESTNET")
API_SECRET = os.getenv("BINANCE_API_SECRET_TESTNET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# Reemplaza esto con tu ID de chat real si deseas probar los envíos de Telegram
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TU_CHAT_ID_AQUI") 

if not API_KEY or not API_SECRET:
    print("❌ Error: Faltan credenciales de Binance en el .env")
    sys.exit(1)

# --- RUTAS ESTRICTAS ---
project_root = os.path.dirname(os.path.abspath(__file__))
carpetas_deptos = ["dep_herramientas", "dep_analisis", "dep_ejecucion", "dep_salud"]
for carpeta in carpetas_deptos:
    sys.path.append(os.path.join(project_root, carpeta))

# --- IMPORTACIONES DE MÓDULOS REALES ---
try:
    from disparador_binance import DisparadorBinance
    from bitacora_central import BitacoraCentral
    from emisor_señales import EmisorSenales
except ImportError as e:
    print(f"❌ Error importando módulos del ecosistema: {e}")
    sys.exit(1)

# --- CLASES WRAPPER DE SOPORTE ---
class SincronizadorDummy:
    def get_timestamp_corregido(self): return int(time.time() * 1000)

class ConexionWrapper:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret, testnet=True)
        self.sincronizador = SincronizadorDummy()

class InyectorPruebas:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        print("🔌 Conectando a Binance Testnet...")
        self.conexion = ConexionWrapper(API_KEY, API_SECRET)
        self.bitacora = BitacoraCentral()
        self.disparador = DisparadorBinance(self.conexion)
        self.emisor = EmisorSenales()
        
        # Parámetros por defecto para pruebas
        self.leverage = 10
        self.riesgo_fijo_usdt = 5.0 # Invertir 5 USDT de margen por prueba
        
        self.configurar_entorno()

    def configurar_entorno(self):
        try:
            self.conexion.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.conexion.client.futures_change_margin_type(symbol=self.symbol, marginType='ISOLATED')
        except Exception:
            pass # Falla silenciosamente si ya está en isolated
            
        # Forzar a Binance Testnet a usar Hedge Mode (Modo de Cobertura)
        try:
            self.conexion.client.futures_change_position_mode(dualSidePosition="true")
            print("⚙️ Modo de Posición: HEDGE (Cobertura) validado.")
        except Exception:
            pass

    def obtener_precio(self):
        return float(self.conexion.client.futures_symbol_ticker(symbol=self.symbol)['price'])

    def calcular_lotes(self, precio):
        poder_compra = self.riesgo_fijo_usdt * self.leverage
        return poder_compra / precio

    def enviar_telegram_prueba(self):
        if not TELEGRAM_TOKEN or TELEGRAM_CHAT_ID == "TU_CHAT_ID_AQUI":
            print("⚠️ Faltan datos de Telegram. Configura TELEGRAM_CHAT_ID en el script o .env")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Test Sentinel: Conexión Exitosa"}
        try:
            resp = requests.post(url, json=payload)
            if resp.status_code == 200:
                print("✅ Mensaje de Telegram enviado con éxito.")
            else:
                print(f"❌ Falló Telegram: {resp.text}")
        except Exception as e:
            print(f"❌ Error de red con Telegram: {e}")

    # ==========================================
    # CASOS DE PRUEBA (HEDGE MODE SIN CLOSEPOSITION)
    # ==========================================
    def test_conexion(self):
        print("\n--- PRUEBA 1: CONEXIÓN BÁSICA ---")
        try:
            balances = self.conexion.client.futures_account_balance()
            usdt = next((float(b['balance']) for b in balances if b['asset'] == 'USDT'), 0)
            precio = self.obtener_precio()
            print(f"✅ Conectado. Balance USDT: ${usdt:.2f}")
            print(f"✅ Precio {self.symbol}: ${precio:.2f}")
            self.enviar_telegram_prueba()
        except Exception as e:
            print(f"❌ Error en test de conexión: {e}")

    def test_vip_long(self):
        print("\n--- PRUEBA 2: VIP LONG (ENTRADA + SL + TP) ---")
        precio = self.obtener_precio()
        qty = self.calcular_lotes(precio)
        qty_formateado = round(qty, 1) # Aseguramos 1 decimal para AAVE
        
        try:
            # 1. Ejecutar Mercado
            print(f"🚀 Enviando orden BUY MARKET. Cantidad: {qty_formateado}")
            self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side="BUY", tipo_orden="MARKET",
                cantidad=qty, precio=None, price_precision=2, qty_precision=1
            )
            print("✅ Orden de entrada ejecutada.")

            # 2. Configurar SL (-2%) y TP (+4%)
            sl_price = round(precio * 0.98, 2)
            tp_price = round(precio * 1.04, 2)
            
            print(f"🛡️ Configurando SL a {sl_price:.2f} y TP a {tp_price:.2f}")
            
            # 3. Colocar Protecciones (Pasando la cantidad explícitamente en lugar de closePosition)
            self.conexion.client.futures_create_order(
                symbol=self.symbol, side="SELL", positionSide="LONG", 
                type="STOP_MARKET", stopPrice=sl_price, quantity=qty_formateado
            )
            self.conexion.client.futures_create_order(
                symbol=self.symbol, side="SELL", positionSide="LONG", 
                type="TAKE_PROFIT_MARKET", stopPrice=tp_price, quantity=qty_formateado
            )
            print("✅ SL y TP colocados correctamente.")
            
        except BinanceAPIException as e:
            print(f"❌ ERROR DE SINTAXIS BINANCE: {e.message}")
        except Exception as e:
            print(f"❌ ERROR GENERAL: {e}")

    def test_vip_short(self):
        print("\n--- PRUEBA 3: VIP SHORT (ENTRADA + SL + TP) ---")
        precio = self.obtener_precio()
        qty = self.calcular_lotes(precio)
        qty_formateado = round(qty, 1) # Aseguramos 1 decimal para AAVE
        
        try:
            print(f"🚀 Enviando orden SELL MARKET. Cantidad: {qty_formateado}")
            self.disparador.ejecutar_orden_entrada(
                symbol=self.symbol, side="SELL", tipo_orden="MARKET",
                cantidad=qty, precio=None, price_precision=2, qty_precision=1
            )
            print("✅ Orden de entrada ejecutada.")

            sl_price = round(precio * 1.02, 2) # Short SL es arriba
            tp_price = round(precio * 0.96, 2) # Short TP es abajo
            
            print(f"🛡️ Configurando SL a {sl_price:.2f} y TP a {tp_price:.2f}")
            
            # Protecciones (Pasando la cantidad explícitamente en lugar de closePosition)
            self.conexion.client.futures_create_order(
                symbol=self.symbol, side="BUY", positionSide="SHORT", 
                type="STOP_MARKET", stopPrice=sl_price, quantity=qty_formateado
            )
            self.conexion.client.futures_create_order(
                symbol=self.symbol, side="BUY", positionSide="SHORT", 
                type="TAKE_PROFIT_MARKET", stopPrice=tp_price, quantity=qty_formateado
            )
            print("✅ SL y TP colocados correctamente.")
            
        except BinanceAPIException as e:
            print(f"❌ ERROR DE SINTAXIS BINANCE: {e.message}")
        except Exception as e:
            print(f"❌ ERROR GENERAL: {e}")

    def panico_limpiar_todo(self):
        print("\n--- ☢️ BOTÓN DEL PÁNICO: LIMPIANDO TESTNET ☢️ ---")
        try:
            # 1. Cancelar pendientes normales
            self.conexion.client.futures_cancel_all_open_orders(symbol=self.symbol)
            print("✅ Órdenes pendientes (SL/TP) canceladas.")
            
            # 2. Cerrar posiciones abiertas
            posiciones = self.conexion.client.futures_position_information(symbol=self.symbol)
            for pos in posiciones:
                amt = float(pos['positionAmt'])
                if amt != 0:
                    side_salida = "SELL" if amt > 0 else "BUY"
                    pos_side = pos['positionSide'] 
                    
                    self.conexion.client.futures_create_order(
                        symbol=self.symbol, 
                        side=side_salida, 
                        positionSide=pos_side, 
                        type="MARKET", 
                        quantity=abs(amt)
                    )
            print("✅ Posiciones liquidadas a mercado. Cuenta limpia.")
            
        except BinanceAPIException as e:
            print(f"❌ Error de API de Binance al limpiar: {e.message}")
        except Exception as e:
            print(f"❌ Error al limpiar: {e}")

    def menu(self):
        while True:
            print("\n" + "="*45)
            print("🔬 INYECTOR DE PRUEBAS - SENTINEL PRO 🔬")
            print("="*45)
            print("[1] Probar Conexión Binance y Telegram")
            print("[2] Inyectar Señal: VIP LONG (Compra + Red)")
            print("[3] Inyectar Señal: VIP SHORT (Venta + Red)")
            print("[5] ☢️ LIMPIAR CUENTA (Cerrar TODO) ☢️")
            print("[0] Salir")
            print("="*45)
            
            opcion = input("Elige una opción: ").strip()
            
            if opcion == "1": self.test_conexion()
            elif opcion == "2": self.test_vip_long()
            elif opcion == "3": self.test_vip_short()
            elif opcion == "5": self.panico_limpiar_todo()
            elif opcion == "0": 
                print("Saliendo del inyector...")
                break
            else:
                print("⚠️ Opción no válida.")

if __name__ == "__main__":
    app = InyectorPruebas(symbol="AAVEUSDT")
    app.menu()