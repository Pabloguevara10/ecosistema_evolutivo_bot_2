# =============================================================================
# NOMBRE: Simon_Sentinel_Gold_MTF.py
# UBICACIÓN: /simuladores/
# OBJETIVO: Estrategia Gamma V7 en Cascada (4H -> 1H -> 15m)
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DINÁMICA DE RUTAS ---
# Obtenemos la ruta de 'simuladores'
current_dir = os.path.dirname(os.path.abspath(__file__))
# Subimos un nivel al directorio raíz del bot
project_root = os.path.dirname(current_dir)

# Ruta a la carpeta de dependencias
tools_path = os.path.join(project_root, 'dep_herramientas')
sys.path.append(tools_path)

try:
    # Importación desde dep_herramientas
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print(f"✅ Entorno vinculado: {tools_path}")
except ImportError as e:
    print(f"❌ Error de Vinculación: {e}")
    print("Verifica que StructureScanner_2.py esté en 'dep_herramientas'.")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN DE RUTAS DE DATOS
# =============================================================================
class Config:
    # Construcción de rutas absolutas hacia la data histórica
    DATA_BASE_PATH = os.path.join(project_root, "data_historica", "AAVEUSDT")
    
    FILE_4H  = os.path.join(DATA_BASE_PATH, "historico_4h.csv")
    FILE_1H  = os.path.join(DATA_BASE_PATH, "historico_1h.csv")
    FILE_15M = os.path.join(DATA_BASE_PATH, "historico_15m.csv")
    
    # --- PARÁMETROS ESTRATÉGICOS ---
    G_RSI_PERIOD = 14
    G_RSI_OVERSOLD_4H = 35
    G_RSI_OVERBOUGHT_4H = 65
    G_FILTRO_DIST_FIBO_MAX = 0.008   
    G_FILTRO_MACD_MIN = 0.0          
    G_FILTRO_OBV_SLOPE_MIN = -500    
    G_TP_NORMAL = 0.035; G_SL_NORMAL = 0.020; G_TRAIL_TRIGGER = 0.50
    INITIAL_CAPITAL = 2000

# =============================================================================
# 3. MOTOR DE PROCESAMIENTO Y SIMULACIÓN
# =============================================================================
class DataProcessor:
    @staticmethod
    def prepare_data(df):
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(Config.G_RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(Config.G_RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        k_fast = df['close'].ewm(span=12).mean(); k_slow = df['close'].ewm(span=26).mean()
        df['macd_hist'] = k_fast - k_slow - (k_fast - k_slow).ewm(span=9).mean()
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['obv_slope'] = df['obv'].diff(3).fillna(0)
        return df.dropna()

class SimonSentinel:
    def __init__(self):
        self.reporter = TradingReporter("Sentinel_Gold_MTF", initial_capital=Config.INITIAL_CAPITAL)
        self.positions = []
        self.scanner_1h = None
        
    def load_data(self):
        print("📂 Accediendo a base de datos histórica...")
        for f in [Config.FILE_4H, Config.FILE_1H, Config.FILE_15M]:
            if not os.path.exists(f):
                print(f"❌ Archivo no encontrado: {f}")
                sys.exit(1)
            
        self.df_4h = DataProcessor.prepare_data(pd.read_csv(Config.FILE_4H))
        self.df_1h = DataProcessor.prepare_data(pd.read_csv(Config.FILE_1H))
        self.df_15m = DataProcessor.prepare_data(pd.read_csv(Config.FILE_15M))
        
        for df in [self.df_4h, self.df_1h, self.df_15m]:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        print("🧠 Inicializando StructureScanner_2...")
        self.scanner_1h = StructureScanner(self.df_1h)
        self.scanner_1h.precompute() 

    def get_fibo_context(self, ts):
        idx = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx == -1: return 999
        ctx = self.scanner_1h.get_fibonacci_context(idx)
        if not ctx: return 999
        price = self.df_1h.iloc[idx]['close']
        return min([abs(price - v) / price for v in ctx['fibs'].values()])

    def run(self):
        print(f"🚀 Ejecutando Cascada 4H -> 1H -> 15m...")
        for i in range(50, len(self.df_15m)):
            row_15m = self.df_15m.iloc[i]
            ts = row_15m.name
            if self.positions:
                self._manage_trade(self.positions[0], row_15m)
                if self.positions[0]['status'] == 'CLOSED':
                    self.reporter.add_trade(self.positions[0])
                    self.positions.clear()
                continue 
            self._check_entry(row_15m, ts, i)
        self.reporter.generate_report()

    def _check_entry(self, row_15m, ts, idx_15m):
        idx_4h = self.df_4h.index.get_indexer([ts], method='pad')[0]
        idx_1h = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx_4h == -1 or idx_1h == -1: return
        
        # Lógica de Cascada
        if self.df_4h.iloc[idx_4h]['rsi'] < Config.G_RSI_OVERSOLD_4H: # Setup 4H
            if row_15m['rsi'] < 35 and (row_15m['rsi'] - self.df_15m.iloc[idx_15m-1]['rsi']) > 2: # Trigger 15m
                if self.get_fibo_context(ts) < Config.G_FILTRO_DIST_FIBO_MAX: # Filtro 1H
                    self._open_position(ts, row_15m['close'], "LONG")

    def _open_position(self, ts, price, side):
        trade = {
            'Trade_ID': f"MTF_{ts.strftime('%H%M')}",
            'Side': side, 'Entry_Time': ts, 'Entry_Price': price,
            'SL': price * (1 - Config.G_SL_NORMAL), 'TP': price * (1 + Config.G_TP_NORMAL),
            'status': 'OPEN', 'PnL_Pct': 0.0
        }
        self.positions.append(trade)

    def _manage_trade(self, trade, row):
        if row['close'] >= trade['TP']: self._close(trade, trade['TP'], row.name, "TP")
        elif row['close'] <= trade['SL']: self._close(trade, trade['SL'], row.name, "SL")

    def _close(self, trade, price, time, reason):
        trade['PnL_Pct'] = (price - trade['Entry_Price']) / trade['Entry_Price'] if trade['Side'] == 'LONG' else (trade['Entry_Price'] - price) / trade['Entry_Price']
        trade['status'] = 'CLOSED'

if __name__ == "__main__":
    sim = SimonSentinel()
    sim.load_data()
    sim.run()