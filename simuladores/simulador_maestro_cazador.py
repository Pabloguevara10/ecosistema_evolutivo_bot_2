# =============================================================================
# NOMBRE: simulador_maestro_cazador.py
# UBICACIÓN: /simuladores/
# OBJETIVO: Backtesting forense con protección total contra IndexError.
# =============================================================================

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

# Ajuste dinámico de rutas
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(project_root, "..", "dep_analisis"))
sys.path.append(os.path.join(project_root, "dep_analisis"))

try:
    from monitor_mercado import MonitorMercado
except ImportError:
    print("❌ Error: Asegúrate de que 'dep_analisis' esté en la raíz del proyecto.")
    sys.exit(1)

class MaestroCazador:
    def __init__(self, symbol="AAVEUSDT", data_dir="data_historica"):
        self.symbol = symbol.upper()
        self.base_path = os.path.join(data_dir, self.symbol)
        self.output_file = os.path.join(self.base_path, "reporte_maestro_cazador.csv")
        self.monitor = MonitorMercado(None)
        self.tfs = ["1m", "5m", "15m", "1h", "4h", "1d"]
        self.data_mtf = {}

    def cargar_y_preparar(self):
        for tf in self.tfs:
            file_path = os.path.join(self.base_path, f"historico_{tf}.csv")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                self.data_mtf[tf] = self.monitor.calcular_indicadores(df)
                print(f"✅ Data {tf} lista.")
            else:
                print(f"⚠️ Archivo ausente: {file_path}")

    def calcular_pivotes_fibo(self, high, low, close):
        p = (high + low + close) / 3
        r = high - low
        return {
            'p': p, 'r1': p + (r * 0.382), 'r2': p + (r * 0.618),
            's1': p - (r * 0.382), 's2': p - (r * 0.618)
        }

    def capturar_estado_previo(self, timestamp, tf, intervalos=5):
        """Captura indicadores con blindaje total contra errores de índice."""
        if tf not in self.data_mtf: return {}
        df = self.data_mtf[tf]
        
        try:
            # Buscar el índice de la vela que contiene o precede al evento
            idx_list = df.index[df['timestamp'] <= timestamp].tolist()
            if not idx_list:
                return {f"{tf}_{k}": "N/A" for k in ["RSI", "MACD", "Stoch", "ADX", "BB_Ancho", "BB_Dist"]}
            
            idx_actual = idx_list[-1]
            idx_target = max(0, idx_actual - intervalos)
            
            # Verificación extra de seguridad antes del acceso
            if idx_target >= len(df):
                idx_target = len(df) - 1

            row = df.iloc[idx_target]
            
            # Cálculo de métricas de Bollinger
            bb_mid = row.get('bb_mid', 0)
            bb_ancho = 0
            bb_dist = 0
            if bb_mid > 0:
                bb_ancho = ((row.get('bb_upper', 0) - row.get('bb_lower', 0)) / bb_mid) * 100
                bb_dist = ((row.get('close', 0) - bb_mid) / bb_mid) * 100

            return {
                f"{tf}_RSI": round(row.get('rsi', 0), 2),
                f"{tf}_MACD": round(row.get('macd', 0), 4),
                f"{tf}_Stoch": round(row.get('stochrsi', 0), 2),
                f"{tf}_ADX": round(row.get('adx', 0), 2),
                f"{tf}_BB_Ancho": round(bb_ancho, 2),
                f"{tf}_BB_Dist": round(bb_dist, 3)
            }
        except Exception:
            # Si algo falla, devolvemos N/A para no romper el loop
            return {f"{tf}_{k}": "N/A" for k in ["RSI", "MACD", "Stoch", "ADX", "BB_Ancho", "BB_Dist"]}

    def ejecutar_simulacion(self):
        print(f"🚀 Iniciando Simulación Maestro Cazador...")
        self.cargar_y_preparar()
        
        if '1d' not in self.data_mtf or '1m' not in self.data_mtf:
            print("❌ No hay suficiente data base (1d/1m).")
            return

        df_1d = self.data_mtf['1d']
        df_1m = self.data_mtf['1m']
        reporte = []

        for i in range(1, len(df_1d)):
            dia_actual = df_1d.iloc[i]
            dia_previo = df_1d.iloc[i-1]
            fecha_str = dia_actual['timestamp'].strftime('%Y-%m-%d')
            
            # Contexto
            pivotes = self.calcular_pivotes_fibo(dia_previo['high'], dia_previo['low'], dia_previo['close'])
            trend_prev = "Alcista" if dia_previo['close'] > dia_previo['open'] else "Bajista" if dia_previo['close'] < dia_previo['open'] else "Lateral"
            
            # Segmentar 1m
            mask = (df_1m['timestamp'] >= dia_actual['timestamp']) & (df_1m['timestamp'] < dia_actual['timestamp'] + timedelta(days=1))
            data_dia = df_1m[mask]
            
            if data_dia.empty: continue
            
            # Localizar extremos
            ts_max = data_dia.loc[data_dia['high'].idxmax()]['timestamp']
            ts_min = data_dia.loc[data_dia['low'].idxmin()]['timestamp']

            for tipo, ts, precio in [("MAX", ts_max, dia_actual['high']), ("MIN", ts_min, dia_actual['low'])]:
                dist_p = (precio - pivotes['p']) / pivotes['p'] * 100
                fila = {
                    "Fecha": fecha_str, "Evento": tipo, "Precio": precio,
                    "Trend_Previo": trend_prev, "Distancia_Pivot_P_%": round(dist_p, 3)
                }
                
                for tf in ["1m", "5m", "15m", "1h", "4h"]:
                    fila.update(self.capturar_estado_previo(ts, tf))
                
                reporte.append(fila)

        if reporte:
            pd.DataFrame(reporte).to_csv(self.output_file, index=False)
            print(f"🏁 Simulación exitosa. Reporte en: {self.output_file}")
        else:
            print("⚠️ Sin datos generados.")

if __name__ == "__main__":
    MaestroCazador().ejecutar_simulacion()