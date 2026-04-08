# =============================================================================
# NOMBRE: generador_data2.py
# UBICACIÓN: /dep_herramientas/
# OBJETIVO: Descargar data faltante desde 2024 usando timestamps exactos (Milisegundos).
# =============================================================================

import os
import pandas as pd
from binance.client import Client
from datetime import datetime

class GeneradorData:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        # Usamos el cliente sin API Keys porque descargar Klines es público
        self.client = Client()
        
        # Rutas del Ecosistema
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.data_dir = os.path.join(project_root, "data_historica", self.symbol)
        
        self.archivo_ancla = os.path.join(self.data_dir, "historico_1ma.csv")
        self.archivo_final = os.path.join(self.data_dir, "historico_1m.csv")
        
        # Aseguramos que la carpeta exista
        os.makedirs(self.data_dir, exist_ok=True)

    def _descargar_bloque_binance(self, start_ts, end_ts):
        # Convertimos a texto solo para mostrar un registro legible en la terminal
        inicio_legible = datetime.fromtimestamp(start_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
        fin_legible = datetime.fromtimestamp(end_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"📥 Descargando velas de 1m desde Binance...")
        print(f"   Desde: {inicio_legible}")
        print(f"   Hasta: {fin_legible}")
        
        # Le enviamos enteros a la API, evitando por completo el DeprecationWarning
        klines = self.client.futures_historical_klines(
            symbol=self.symbol,
            interval=Client.KLINE_INTERVAL_1MINUTE,
            start_str=start_ts,
            end_str=end_ts
        )
        
        print(f"✅ Descarga completada: {len(klines)} velas obtenidas.")
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        
        # Limpiar y formatear
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        return df

    def fusionar_historia(self):
        print("="*60)
        print(f"🔄 INICIANDO PROTOCOLO DE FUSIÓN DE DATOS: {self.symbol}")
        print("="*60)
        
        # 1. Leer el archivo ancla
        if not os.path.exists(self.archivo_ancla):
            print(f"❌ Error: No se encuentra el archivo {self.archivo_ancla}")
            print("Asegúrate de haber renombrado tu archivo histórico base a 'historico_1ma.csv'")
            return
            
        print("📂 Leyendo archivo ancla (historico_1ma.csv)...")
        df_ancla = pd.read_csv(self.archivo_ancla)
        
        # Detectar el formato del timestamp (ms o string)
        if pd.api.types.is_numeric_dtype(df_ancla['timestamp']) and df_ancla['timestamp'].iloc[0] > 10000000000:
            df_ancla['timestamp'] = pd.to_datetime(df_ancla['timestamp'], unit='ms')
        else:
            df_ancla['timestamp'] = pd.to_datetime(df_ancla['timestamp'])
            
        # 2. Encontrar la fecha más antigua
        df_ancla = df_ancla.sort_values(by='timestamp')
        fecha_mas_antigua = df_ancla['timestamp'].iloc[0]
        
        # 3. 🛠️ Convertir ambas fechas a Milisegundos puros (Enteros)
        fecha_inicio = datetime(2024, 1, 1)
        start_ts = int(fecha_inicio.timestamp() * 1000)
        end_ts = int(fecha_mas_antigua.timestamp() * 1000)
        
        # 4. Descargar la data faltante enviando milisegundos
        df_nuevo = self._descargar_bloque_binance(start_ts, end_ts)
        
        if df_nuevo.empty:
            print("⚠️ No se encontraron datos nuevos en ese rango. ¿Seguro que el ancla no empieza antes de 2024?")
            return
            
        # 5. Coser los datos
        print("🧵 Cosiendo matrices temporales...")
        df_unificado = pd.concat([df_nuevo, df_ancla], ignore_index=True)
        
        # 6. Limpieza final: Ordenar y quitar duplicados en la sutura
        df_unificado = df_unificado.drop_duplicates(subset=['timestamp'], keep='first')
        df_unificado = df_unificado.sort_values(by='timestamp').reset_index(drop=True)
        
        # 7. Guardar archivo final
        print(f"💾 Guardando base de datos maestra ({len(df_unificado)} filas totales)...")
        df_unificado.to_csv(self.archivo_final, index=False)
        
        print(f"✅ ¡ÉXITO! Archivo '{self.archivo_final}' generado correctamente.")
        print(f"   Rango total: {df_unificado['timestamp'].iloc[0]} -> {df_unificado['timestamp'].iloc[-1]}")
        print("="*60)

if __name__ == "__main__":
    generador = GeneradorData(symbol="AAVEUSDT")
    generador.fusionar_historia()