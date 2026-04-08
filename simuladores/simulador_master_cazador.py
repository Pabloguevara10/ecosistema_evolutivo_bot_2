# =============================================================================
# NOMBRE: simulador_master_piramide_mtf.py
# CORRECCIÓN: Sincronización de tipos de datos para comparación de fechas.
# =============================================================================

import os
import pandas as pd
import numpy as np
import sys

# Configuración de rutas para dep_analisis
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(project_root, "..", "dep_analisis"))
sys.path.append(os.path.join(project_root, "dep_analisis"))

try:
    from monitor_mercado import MonitorMercado
except ImportError:
    print("❌ Error: Asegúrate de que 'monitor_mercado.py' esté en la ruta correcta.")
    sys.exit(1)

class SimuladorPiramideMaster:
    def __init__(self, symbol="AAVEUSDT", data_dir="data_historica"):
        self.symbol = symbol.upper()
        self.path = os.path.join(data_dir, self.symbol)
        self.monitor = MonitorMercado(None)
        
        # Estado de Inventario de Lotes
        self.lotes_long = 0.0
        self.lotes_short = 0.0
        self.precio_prom_long = 0.0
        self.precio_prom_short = 0.0
        
        self.historial_pnl = []

    def abrir_o_rebalancear(self, lado, cantidad, precio, ts, motivo):
        if lado == 'LONG':
            total_cant = self.lotes_long + cantidad
            self.precio_prom_long = ((self.lotes_long * self.precio_prom_long) + (cantidad * precio)) / total_cant
            self.lotes_long = total_cant
        else:
            total_cant = self.lotes_short + cantidad
            self.precio_prom_short = ((self.lotes_short * self.precio_prom_short) + (cantidad * precio)) / total_cant
            self.lotes_short = total_cant
        print(f"➕ [{ts}] {motivo} | {lado}: +{cantidad} lotes a ${precio:.2f} (Total: {total_cant:.1f})")

    def cerrar_parcial(self, lado, cantidad, precio, ts, motivo):
        if lado == 'LONG' and self.lotes_long > 0:
            cant_a_cerrar = min(cantidad, self.lotes_long)
            pnl = (precio - self.precio_prom_long) / self.precio_prom_long * 100
            self.lotes_long -= cant_a_cerrar
            self.historial_pnl.append({"ts": ts, "clase": "LONG_PARTIAL", "pnl": pnl, "motivo": motivo})
            print(f"✂️ [{ts}] {motivo} | LONG: -{cant_a_cerrar:.1f} lotes | PnL: {pnl:.2f}%")
        
        elif lado == 'SHORT' and self.lotes_short > 0:
            cant_a_cerrar = min(cantidad, self.lotes_short)
            pnl = (self.precio_prom_short - precio) / self.precio_prom_short * 100
            self.lotes_short -= cant_a_cerrar
            self.historial_pnl.append({"ts": ts, "clase": "SHORT_PARTIAL", "pnl": pnl, "motivo": motivo})
            print(f"✂️ [{ts}] {motivo} | SHORT: -{cant_a_cerrar:.1f} lotes | PnL: {pnl:.2f}%")

    def ejecutar_simulacion(self):
        print(f"🚀 Cargando y procesando ecosistema MTF para {self.symbol}...")
        
        # Carga y conversión forzada de Timestamps en todos los DFs
        def cargar_df(tf):
            path = os.path.join(self.path, f"historico_{tf}.csv")
            if not os.path.exists(path): return None
            df = pd.read_csv(path)
            df['timestamp'] = pd.to_datetime(df['timestamp']) # Forzar conversión
            return df

        df_1m = cargar_df("1m")
        df_5m = self.monitor.calcular_indicadores(cargar_df("5m"))
        df_15m = self.monitor.calcular_indicadores(cargar_df("15m"))
        df_1h = self.monitor.calcular_indicadores(cargar_df("1h"))

        if df_1m is None or df_1h is None:
            print("❌ No se pudieron cargar los archivos necesarios.")
            return

        print(f"⚙️ Iniciando bucle de simulación...")

        for i in range(1, len(df_1m)):
            row = df_1m.iloc[i]
            ts, p = row['timestamp'], row['close']
            
            # Sincronizar contextos (Busca la vela más cercana en el pasado)
            mask_1h = df_1h[df_1h['timestamp'] <= ts]
            mask_15m = df_15m[df_15m['timestamp'] <= ts]
            mask_5m = df_5m[df_5m['timestamp'] <= ts]

            if mask_1h.empty or mask_15m.empty or mask_5m.empty:
                continue # Saltar si no hay data histórica suficiente para ese minuto

            ctx_1h = mask_1h.iloc[-1]
            ctx_15m = mask_15m.iloc[-1]
            ctx_5m = mask_5m.iloc[-1]

            # A. Filtro Maestro (1H)
            sesgo = "ALCISTA" if p > ctx_1h['bb_mid'] else "BAJISTA"

            # B. Acción en Banda Superior (Rechazo Short)
            if p >= ctx_15m['bb_upper'] or p >= ctx_5m['bb_upper']:
                if row['close'] < row['open']:
                    if self.lotes_long > 0:
                        self.cerrar_parcial('LONG', 0.5, p, ts, "Rebalanceo Techo")
                    self.abrir_o_rebalancear('SHORT', 1.0, p, ts, "Apertura Short")

            # C. Acción en Banda Inferior (Rechazo Long)
            elif p <= ctx_15m['bb_lower'] or p <= ctx_5m['bb_lower']:
                if row['close'] > row['open']:
                    if self.lotes_short > 0:
                        self.cerrar_parcial('SHORT', self.lotes_short * 0.5, p, ts, "Rebalanceo Suelo")
                    
                    cant_long = 1.5 if sesgo == "ALCISTA" else 1.0
                    self.abrir_o_rebalancear('LONG', cant_long, p, ts, f"Apertura Long ({sesgo})")

            # D. Gestión de "La Ola" (Stop Loss RUPTURA al 2%)
            if self.lotes_short > 0 and p >= self.precio_prom_short * 1.02:
                self.cerrar_parcial('SHORT', self.lotes_short, p, ts, "OLA ALCISTA (SL Short)")
            if self.lotes_long > 0 and p <= self.precio_prom_long * 0.98:
                self.cerrar_parcial('LONG', self.lotes_long, p, ts, "OLA BAJISTA (SL Long)")

        if self.historial_pnl:
            res_df = pd.DataFrame(self.historial_pnl)
            res_df.to_csv("resultados_piramide_master.csv", index=False)
            print(f"🏁 Finalizado. PnL Neto: {res_df['pnl'].sum():.2f}%")
        else:
            print("🏁 Finalizado sin operaciones registradas.")

if __name__ == "__main__":
    SimuladorPiramideMaster().ejecutar_simulacion()