# Módulo: inicializador_sistema.py - Pertenece a dep_adecuacion
import os
from dotenv import load_dotenv
from dep_adecuacion.conexion_exchange import ConexionExchange

class InicializadorSistema:
    def __init__(self):
        # Cargar variables ocultas desde el .env
        load_dotenv()
        self.mode = os.getenv("MODE", "TESTNET").upper()
        
        # Asignación selectiva de credenciales
        if self.mode == "TESTNET":
            self.api_key = os.getenv("BINANCE_API_KEY_TESTNET")
            self.api_secret = os.getenv("BINANCE_API_SECRET_TESTNET")
        else:
            self.api_key = os.getenv("BINANCE_API_KEY_REAL")
            self.api_secret = os.getenv("BINANCE_API_SECRET_REAL")
            
        self.conexion = None

    def arrancar(self, symbol="AAVEUSDT", leverage=5):
        print("\n==================================================")
        print(f"🚀 INICIANDO BOT DE FUTUROS EN MODO: {self.mode}")
        print("==================================================")
        
        if not self.api_key or not self.api_secret:
            raise ValueError(f"❌ CRÍTICO: Faltan credenciales API para {self.mode} en el archivo .env")

        es_testnet = (self.mode == "TESTNET")
        
        # Instanciar el Lego de Conexión
        self.conexion = ConexionExchange(self.api_key, self.api_secret, testnet=es_testnet)
        
        # Configurar parámetros vitales de supervivencia en Binance
        self.conexion.configurar_cuenta(symbol=symbol, leverage=leverage)
        
        # Verificar Balance para confirmar operatividad
        balance = self.conexion.obtener_balance_usdt()
        print(f"💰 Balance actual disponible: {balance:.2f} USDT")
        print("🟢 DEPARTAMENTO DE ADECUACIÓN: EN LÍNEA Y OPERATIVO.")
        print("==================================================\n")
        
        # Devuelve el objeto de conexión certificado para que los demás departamentos lo usen
        return self.conexion

if __name__ == "__main__":
    # Prueba Aislada (Requiere que tengas tu archivo .env configurado y dependencias instaladas)
    # pip install python-dotenv binance-futures-connector
    try:
        inicializador = InicializadorSistema()
        conexion_lista = inicializador.arrancar(symbol="AAVEUSDT", leverage=5)
    except Exception as e:
        print(f"Fallo en prueba de arranque: {e}")