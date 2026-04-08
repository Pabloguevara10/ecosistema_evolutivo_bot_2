# Módulo: resampler_data.py - Pertenece a dep_herramientas
import os
import pandas as pd

class ResamplerData:
    def __init__(self, symbol="AAVEUSDT", data_dir="data_historica"):
        self.symbol = symbol.upper()
        self.symbol_dir = os.path.join(data_dir, self.symbol)
        self.file_1m = os.path.join(self.symbol_dir, "historico_1m.csv")
        
        # Diccionario matemático para agrupar velas preservando la integridad del OHLC
        self.ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

    def cargar_data_base(self):
        if not os.path.exists(self.file_1m):
            raise FileNotFoundError(f"No se encontró la data base de 1m en {self.file_1m}")
            
        print(f"Cargando base de datos de 1 minuto para {self.symbol}...")
        df = pd.read_csv(self.file_1m)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df

    def auditar_gaps(self, df):
        # Verifica la diferencia temporal entre cada fila
        diferencias = df.index.to_series().diff()
        # Un gap ocurre si el salto es mayor a 1 minuto exacto
        gaps = diferencias[diferencias > pd.Timedelta(minutes=1)]
        
        if not gaps.empty:
            print(f"⚠️ ADVERTENCIA: Se detectaron {len(gaps)} 'Gaps' o huecos en la data de liquidez de AAVE.")
            print("El departamento de adecuación auditará estos vacíos de liquidez más adelante.")
        else:
            print("✅ Auditoría de Integridad: Data 1m continua, sin saltos de tiempo.")

    def generar_temporalidad(self, df, timeframe, nombre_archivo):
        print(f"Procesando remuestreo matemático para temporalidad: {timeframe}...")
        
        # Ejecución del Resampling aglomerativo
        df_resampled = df.resample(timeframe).agg(self.ohlc_dict)
        
        # Eliminar las filas NaN generadas en tiempos donde el exchange no reportó trades
        df_resampled.dropna(inplace=True)
        df_resampled.reset_index(inplace=True)
        
        ruta_salida = os.path.join(self.symbol_dir, f"historico_{nombre_archivo}.csv")
        df_resampled.to_csv(ruta_salida, index=False)
        print(f"✅ Archivo creado exitosamente: {ruta_salida}")

    def ejecutar_flujo_completo(self):
        try:
            df_base = self.cargar_data_base()
            self.auditar_gaps(df_base)
            
            # Generar temporalidades estándar para los simuladores del motor evolutivo
            self.generar_temporalidad(df_base, '5min', '5m')
            self.generar_temporalidad(df_base, '15min', '15m')
            self.generar_temporalidad(df_base, '1h', '1h')
            self.generar_temporalidad(df_base, '4h', '4h')
            
            # NUEVO: Generar temporalidad de 1 Día para conciencia situacional
            self.generar_temporalidad(df_base, '1D', '1d')
            
            print(f"🏁 Todas las transformaciones de datos para {self.symbol} han finalizado.")
            
        except Exception as e:
            print(f"❌ Error durante el proceso de Resampling: {e}")

if __name__ == "__main__":
    # Prueba de ejecución aislada
    resampler = ResamplerData(symbol="AAVEUSDT")
    resampler.ejecutar_flujo_completo()