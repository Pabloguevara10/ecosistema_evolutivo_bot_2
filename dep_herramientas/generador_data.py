import os
import time
import requests
import pandas as pd
from datetime import datetime

class GeneradorDataBinance:
    def __init__(self, symbol="AAVEUSDT", data_dir="data_historica"):
        self.symbol = symbol.upper()
        self.base_url = "https://fapi.binance.com"
        self.endpoint = "/fapi/v1/klines"
        self.limit = 1000 # Máximo permitido de forma segura
        
        # Crear ruta limpia si no existe
        self.symbol_dir = os.path.join(data_dir, self.symbol)
        os.makedirs(self.symbol_dir, exist_ok=True)
        self.file_path = os.path.join(self.symbol_dir, "historico_1m.csv")

    def obtener_tiempo_actual_ms(self):
        return int(time.time() * 1000)

    def descargar_klines_1m(self, start_time_ms, end_time_ms):
        params = {
            "symbol": self.symbol,
            "interval": "1m",
            "startTime": start_time_ms,
            "endTime": end_time_ms,
            "limit": self.limit
        }
        
        try:
            response = requests.get(self.base_url + self.endpoint, params=params)
            
            # Control Anti-Baneo evaluando Headers de Binance
            weight = int(response.headers.get('x-mbx-used-weight-1m', 0))
            if weight > 2000:  # El límite real suele ser 2400 por minuto
                print(f"⚠️ Alerta de peso en API ({weight}). Pausa de seguridad de 30s...")
                time.sleep(30)
                
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("❌ Rate Limit Excedido (HTTP 429). Pausa obligatoria de 60s.")
                time.sleep(60)
                return None
            else:
                print(f"Error HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Error de conexión: {e}")
            time.sleep(5)
            return None

    def procesar_y_guardar(self, klines):
        # Columnas oficiales de Binance API
        columnas = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                    'close_time', 'quote_asset_volume', 'trades', 
                    'taker_buy_base', 'taker_buy_quote', 'ignore']
        
        df = pd.DataFrame(klines, columns=columnas)
        
        # Limpieza y tipado estricto adaptado a la precisión de AAVE
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        # Guardar o anexar
        if os.path.exists(self.file_path):
            df.to_csv(self.file_path, mode='a', header=False, index=False)
        else:
            df.to_csv(self.file_path, mode='w', header=True, index=False)

    def descargar_historico_completo(self, dias_atras=365):
        print(f"Iniciando descarga de {self.symbol} (1m) por los últimos {dias_atras} días...")
        
        end_time = self.obtener_tiempo_actual_ms()
        start_time = end_time - (dias_atras * 24 * 60 * 60 * 1000)
        
        tiempo_pivote = start_time
        
        while tiempo_pivote < end_time:
            print(f"Descargando bloque desde: {pd.to_datetime(tiempo_pivote, unit='ms')}")
            
            klines = self.descargar_klines_1m(tiempo_pivote, end_time)
            
            # Solución al bucle infinito por falta de datos
            if not klines:
                print("⚠️ Sin datos o error en este bloque. Avanzando 1000 minutos para evitar bucle...")
                tiempo_pivote += (1000 * 60 * 1000)
                time.sleep(2)
                continue 
                
            self.procesar_y_guardar(klines)
            
            # Actualizar el pivote temporal al timestamp de la última vela + 1 minuto
            ultimo_timestamp = klines[-1][0]
            tiempo_pivote = ultimo_timestamp + 60000 
            
            # Pequeña pausa para no saturar el servidor y mantener el weight bajo
            time.sleep(0.5)
            
        print(f"✅ Descarga completada. Archivo guardado en {self.file_path}")
        
        # Limpiar duplicados finales si existen
        self.auditar_duplicados()

    def auditar_duplicados(self):
        df = pd.read_csv(self.file_path)
        df.drop_duplicates(subset=['timestamp'], inplace=True, keep='last')
        df.sort_values(by='timestamp', inplace=True)
        df.to_csv(self.file_path, index=False)
        print("✅ Duplicados purgados. Data 1m íntegra para la simulación.")

if __name__ == "__main__":
    generador = GeneradorDataBinance(symbol="AAVEUSDT")
    generador.descargar_historico_completo(dias_atras=365)