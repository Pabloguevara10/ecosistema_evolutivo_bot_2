# Módulo: conexion_exchange.py - Pertenece a dep_adecuacion
import os
from binance.um_futures import UMFutures
from binance.error import ClientError
from dep_adecuacion.sincronizador_tiempo import SincronizadorTiempo

class ConexionExchange:
    def __init__(self, api_key, api_secret, testnet=True):
        self.testnet = testnet
        # Enrutamiento dinámico según el entorno elegido
        base_url = 'https://testnet.binancefuture.com' if testnet else 'https://fapi.binance.com'
        
        self.client = UMFutures(key=api_key, secret=api_secret, base_url=base_url, timeout=20)
        self.sincronizador = SincronizadorTiempo(self.client)
        self.sincronizador.sincronizar(forzar=True)
        self.activo = False
        
    def configurar_cuenta(self, symbol="AAVEUSDT", leverage=5):
        """Fuerza al Exchange a adoptar la configuración requerida por el bot."""
        print(f"⚙️ Configurando estructura de cuenta para {symbol}...")
        ts = self.sincronizador.get_timestamp_corregido()
        
        # 1. Modo Cobertura (Hedge Mode) obligatorio para abrir Long y Short simultáneos
        try:
            self.client.change_position_mode(dualSidePosition="true", recvWindow=5000, timestamp=ts)
            print("✅ Hedge Mode (Modo Cobertura) Activado exitosamente.")
        except ClientError as e:
            if e.error_code == -4059: # Código de error que significa "Ya estabas en Hedge Mode"
                pass 
            else:
                print(f"⚠️ Error al fijar Hedge Mode: {e}")

        # 2. Apalancamiento (Leverage)
        try:
            self.client.change_leverage(symbol=symbol, leverage=leverage, recvWindow=5000, timestamp=ts)
            print(f"✅ Apalancamiento ajustado y bloqueado en {leverage}x.")
        except ClientError as e:
            print(f"⚠️ Error al fijar Apalancamiento: {e}")
            
        self.activo = True

    def obtener_balance_usdt(self):
        """Consulta el capital disponible para operar en la billetera de Futuros."""
        if not self.activo: return 0.0
        try:
            ts = self.sincronizador.get_timestamp_corregido()
            balances = self.client.balance(recvWindow=5000, timestamp=ts)
            for asset in balances:
                if asset['asset'] == 'USDT':
                    return float(asset['balance'])
            return 0.0
        except Exception as e:
            print(f"❌ Error obteniendo balance del Exchange: {e}")
            return 0.0

if __name__ == "__main__":
    print("Módulo de Conexión Exchange Compilado.")