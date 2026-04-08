# =============================================================================
# NOMBRE: motor_evolutivo.py
# UBICACIÓN: /dep_desarrollo/
# OBJETIVO: Motor Genético para Estrategia Cascada MTF (4H -> 1H -> 15m)
# =============================================================================

import os
import sys
import json
import random
import uuid
import pandas as pd
import numpy as np
from datetime import datetime

# Rutas del ecosistema
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'dep_herramientas'))

try:
    from StructureScanner_2 import StructureScanner
    from dep_desarrollo.certificador_estrategias import CertificadorMonteCarlo
except ImportError as e:
    print(f"❌ Error de Dependencias: {e}")
    sys.exit(1)

class MotorEvolutivoMTF:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        self.data_dir = os.path.join(project_root, "data_historica", self.symbol)
        self.ruta_db = os.path.join(current_dir, "bbdd_estrategias", "estrategias_aprobadas_mtf.json")
        self.estrategias_aprobadas = self._cargar_db()
        self.df_master = None
        self.scanner_1h = None

    def _cargar_db(self):
        if os.path.exists(self.ruta_db):
            with open(self.ruta_db, 'r') as file:
                try: return json.load(file)
                except: return []
        return []

    def _calcular_indicadores(self, df):
        """Calcula todas las mutaciones posibles de RSI de una sola vez."""
        df = df.copy()
        for p in [9, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(p).mean()
            rs = gain / loss
            df[f'rsi_{p}'] = 100 - (100 / (1 + rs))
        
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        df['macd_hist'] = k_fast - k_slow - (k_fast - k_slow).ewm(span=9).mean()
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['obv_slope'] = df['obv'].diff(3).fillna(0)
        return df.dropna()

    def preparar_entorno(self):
        print(f"⚙️ Cargando y vectorizando matrices temporales de {self.symbol}...")
        df_4h_raw = pd.read_csv(os.path.join(self.data_dir, "historico_4h.csv"), parse_dates=['timestamp']).set_index('timestamp')
        df_1h_raw = pd.read_csv(os.path.join(self.data_dir, "historico_1h.csv"), parse_dates=['timestamp']).set_index('timestamp')
        df_15m_raw = pd.read_csv(os.path.join(self.data_dir, "historico_15m.csv"), parse_dates=['timestamp']).set_index('timestamp')

        df_4h = self._calcular_indicadores(df_4h_raw)
        df_1h = self._calcular_indicadores(df_1h_raw)
        df_15m = self._calcular_indicadores(df_15m_raw)

        # Inicializar el Scanner de Fibonacci en 1H
        self.scanner_1h = StructureScanner(df_1h)
        self.scanner_1h.precompute()

        # Preparar índices y pre-cálculo de pendientes (slopes)
        df_1h['idx_1h'] = np.arange(len(df_1h))
        for p in [9, 14, 21]:
            df_15m[f'rsi_{p}_prev'] = df_15m[f'rsi_{p}'].shift(1)
        df_15m.dropna(inplace=True)

        # Fusionar todas las temporalidades (Merge AsOf) para simulación en O(N)
        df_15m = df_15m.reset_index()
        df_4h = df_4h.reset_index().add_suffix('_4h').rename(columns={'timestamp_4h': 'timestamp'})
        df_1h = df_1h.reset_index().add_suffix('_1h').rename(columns={'timestamp_1h': 'timestamp'})
        
        m1 = pd.merge_asof(df_15m, df_4h, on='timestamp')
        self.df_master = pd.merge_asof(m1, df_1h, on='timestamp')
        print("✅ Matriz MTF Maestra construida. Entorno listo.")

    def generar_adn(self):
        """Genera un genoma más flexible para no estrangular las operaciones."""
        return {
            "rsi_period_macro": random.choice([9, 14]),
            "rsi_os_macro": random.randint(35, 48),  
            "rsi_ob_macro": random.randint(52, 65),  
            
            "rsi_period_micro": random.choice([9, 14]),
            "rsi_os_micro": random.randint(30, 42),  
            "rsi_ob_micro": random.randint(58, 70),  
            
            "fibo_max_dist": round(random.uniform(0.008, 0.025), 4), 
            
            "sl_pct": round(random.uniform(0.015, 0.035), 4),
            "tp_pct": round(random.uniform(0.025, 0.070), 4),
            "leverage": 5
        }

    def _get_fibo_dist(self, idx, price):
        ctx = self.scanner_1h.get_fibonacci_context(int(idx))
        if not ctx: return 999
        return min([abs(price - v) / price for v in ctx['fibs'].values()])

    def simular_mutacion(self, adn):
        """Evaluador hiperrápido que reemplaza a SimuladorBinance."""
        trades = []
        trade_abierto = None
        
        # Mapeo rápido de columnas según el ADN
        col_rsi_mac = f"rsi_{adn['rsi_period_macro']}_4h"
        col_rsi_mic = f"rsi_{adn['rsi_period_micro']}"
        col_rsi_mic_prev = f"rsi_{adn['rsi_period_micro']}_prev"
        
        for row in self.df_master.itertuples():
            if trade_abierto:
                curr = row.close
                if trade_abierto['Side'] == 'LONG':
                    if curr >= trade_abierto['TP']:
                        trade_abierto['PnL_Pct'] = (trade_abierto['TP'] - trade_abierto['Entry_Price']) / trade_abierto['Entry_Price']
                        trades.append(trade_abierto); trade_abierto = None
                    elif curr <= trade_abierto['SL']:
                        trade_abierto['PnL_Pct'] = (trade_abierto['SL'] - trade_abierto['Entry_Price']) / trade_abierto['Entry_Price']
                        trades.append(trade_abierto); trade_abierto = None
                else: # SHORT
                    if curr <= trade_abierto['TP']:
                        trade_abierto['PnL_Pct'] = (trade_abierto['Entry_Price'] - trade_abierto['TP']) / trade_abierto['Entry_Price']
                        trades.append(trade_abierto); trade_abierto = None
                    elif curr >= trade_abierto['SL']:
                        trade_abierto['PnL_Pct'] = (trade_abierto['Entry_Price'] - trade_abierto['SL']) / trade_abierto['Entry_Price']
                        trades.append(trade_abierto); trade_abierto = None
                continue 
            
            # Busqueda MTF
            rsi_macro = getattr(row, col_rsi_mac)
            rsi_micro = getattr(row, col_rsi_mic)
            rsi_micro_prev = getattr(row, col_rsi_mic_prev)
            
            if pd.isna(rsi_macro) or pd.isna(row.idx_1h_1h): continue
            signal = None
            
            # Setup Long
            if rsi_macro < adn['rsi_os_macro']:
                if rsi_micro < adn['rsi_os_micro'] and (rsi_micro - rsi_micro_prev) > 2:
                    if self._get_fibo_dist(row.idx_1h_1h, row.close_1h) < adn['fibo_max_dist'] and row.macd_hist_1h > 0 and row.obv_slope_1h > -500:
                        signal = "LONG"
            # Setup Short
            elif rsi_macro > adn['rsi_ob_macro']:
                if rsi_micro > adn['rsi_ob_micro'] and (rsi_micro - rsi_micro_prev) < -2:
                    if self._get_fibo_dist(row.idx_1h_1h, row.close_1h) < adn['fibo_max_dist'] and row.macd_hist_1h < 0 and row.obv_slope_1h < 500:
                        signal = "SHORT"
                        
            if signal:
                price = row.close
                trade_abierto = {
                    'Side': signal,
                    'Entry_Price': price,
                    'TP': price * (1 + adn['tp_pct']) if signal == 'LONG' else price * (1 - adn['tp_pct']),
                    'SL': price * (1 - adn['sl_pct']) if signal == 'LONG' else price * (1 + adn['sl_pct']),
                }
        return trades

    def ejecutar_generacion(self, poblacion=10):
        self.preparar_entorno()
        print(f"\n🧬 Iniciando Evolución MTF: Probando {poblacion} mutaciones en 1 Año de Datos...")
        
        for i in range(poblacion):
            adn = self.generar_adn()
            print(f"\n--- Evaluando Mutación {i+1}/{poblacion} ---")
            
            historial = self.simular_mutacion(adn)
            total_trades = len(historial)
            
            if total_trades < 20:
                print(f"❌ Descartada (Pocas señales: {total_trades}).")
                continue
                
            print(f"📊 {total_trades} Operaciones generadas. Pasando a Estrés Monte Carlo...")
            
            # Integración Monte Carlo
            certificador = CertificadorMonteCarlo(historial, iteraciones=1000, leverage=adn['leverage'])
            reporte = certificador.ejecutar_certificacion()
            
            # ==========================================
            # GENERACIÓN DEL REPORTE DETALLADO (NUEVO)
            # ==========================================
            ganadoras = [t for t in historial if t['PnL_Pct'] > 0]
            perdedoras = [t for t in historial if t['PnL_Pct'] <= 0]
            
            win_rate = (len(ganadoras) / total_trades) * 100
            avg_win = np.mean([t['PnL_Pct'] for t in ganadoras]) * adn['leverage'] * 100 if ganadoras else 0
            avg_loss = np.mean([t['PnL_Pct'] for t in perdedoras]) * adn['leverage'] * 100 if perdedoras else 0
            roi_bruto = sum(t['PnL_Pct'] for t in historial) * adn['leverage'] * 100
            
            # Extracción segura de datos del reporte Monte Carlo
            ruina = reporte.get('riesgo_ruina', reporte.get('riesgo_ruina_absoluta', 'N/A'))
            dd_esperado = reporte.get('drawdown_esperado', reporte.get('drawdown_maximo', 'N/A'))
            estado = "✅ APROBADA" if reporte.get('aprobado', False) else "❌ RECHAZADA"
            
            print("\n" + "="*55)
            print(f"📋 REPORTE DETALLADO - MUTACIÓN {i+1}")
            print("="*55)
            print(f"🧬 ADN (Parámetros Clave):")
            print(f"   RSI Macro: {adn['rsi_period_macro']} | OS: {adn['rsi_os_macro']} | OB: {adn['rsi_ob_macro']}")
            print(f"   SL: {adn['sl_pct']*100:.2f}% | TP: {adn['tp_pct']*100:.2f}%")
            print("-" * 55)
            print(f"📈 Win Rate Base:      {win_rate:.1f}% ({len(ganadoras)} Ganadas / {len(perdedoras)} Perdidas)")
            print(f"💵 Ganancia Promedio:  +{avg_win:.2f}% (Apalancado {adn['leverage']}x)")
            print(f"💸 Pérdida Promedio:   {avg_loss:.2f}% (Apalancado {adn['leverage']}x)")
            print(f"💰 ROI Bruto Base:     {roi_bruto:.2f}%")
            print("-" * 55)
            
            # Formateo de las salidas de Monte Carlo
            ruina_str = f"{ruina:.2f}%" if isinstance(ruina, float) else f"{ruina}"
            dd_str = f"{dd_esperado:.2f}%" if isinstance(dd_esperado, float) else f"{dd_esperado}"
            
            print(f"🔬 Riesgo de Ruina MC: {ruina_str}")
            print(f"📉 Drawdown Peor Caso: {dd_str}")
            print(f"⚖️ ESTADO FINAL:       {estado}")
            print("="*55 + "\n")
            
            if reporte.get('aprobado', False):
                self._guardar_aprobada(adn, reporte)

    def _guardar_aprobada(self, adn, reporte):
        est_final = {
            "id_estrategia": f"MTF-{uuid.uuid4().hex[:8].upper()}",
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parametros": adn,
            "metricas": reporte
        }
        self.estrategias_aprobadas.append(est_final)
        os.makedirs(os.path.dirname(self.ruta_db), exist_ok=True)
        with open(self.ruta_db, 'w') as f:
            json.dump(self.estrategias_aprobadas, f, indent=4)
        print(f"💎 ¡MUTACIÓN DORADA ENCONTRADA Y GUARDADA! ID: {est_final['id_estrategia']}")

if __name__ == "__main__":
    motor = MotorEvolutivoMTF(symbol="AAVEUSDT")
    motor.ejecutar_generacion(poblacion=15)