# =============================================================================
# NOMBRE: Simon_Sentinel_Gold_MTF.py
# UBICACIÓN: /simuladores/
# OBJETIVO: Simulador de Alta Fidelidad configurado con ADN MTF-9696E766
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# --- 1. CONFIGURACIÓN DINÁMICA DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

tools_path = os.path.join(project_root, 'dep_herramientas')
sys.path.append(tools_path)

try:
    from StructureScanner_2 import StructureScanner
    from Reporter import TradingReporter
    print(f"✅ Entorno vinculado: {tools_path}")
except ImportError as e:
    print(f"❌ Error de Vinculación: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN DEL ADN GANADOR (MTF-9696E766)
# =============================================================================
class Config:
    DATA_BASE_PATH = os.path.join(project_root, "data_historica", "AAVEUSDT")
    FILE_4H  = os.path.join(DATA_BASE_PATH, "historico_4h.csv")
    FILE_1H  = os.path.join(DATA_BASE_PATH, "historico_1h.csv")
    FILE_15M = os.path.join(DATA_BASE_PATH, "historico_15m.csv")
    
    # --- PARÁMETROS GENÉTICOS ---
    # Setup Macro (4H)
    G_RSI_PERIOD_MACRO = 9
    G_RSI_OVERSOLD_MACRO = 36
    G_RSI_OVERBOUGHT_MACRO = 64
    
    # Setup Micro (15m) - Ajustados al promedio de mutaciones
    G_RSI_PERIOD_MICRO = 14
    G_RSI_OVERSOLD_MICRO = 35
    G_RSI_OVERBOUGHT_MICRO = 65
    
    # Filtros Estructurales (1H)
    G_FILTRO_DIST_FIBO_MAX = 0.015   
    
    # Gestión de Riesgo Institucional
    G_SL_NORMAL = 0.0192  # 1.92%
    G_TP_NORMAL = 0.0427  # 4.27%
    LEVERAGE = 10
    INITIAL_CAPITAL = 1500

# =============================================================================
# 3. PROCESADOR DE DATOS
# =============================================================================
class DataProcessor:
    @staticmethod
    def prepare_data(df, rsi_period):
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        k_fast = df['close'].ewm(span=12).mean()
        k_slow = df['close'].ewm(span=26).mean()
        macd_line = k_fast - k_slow
        df['macd_hist'] = macd_line - macd_line.ewm(span=9).mean()
        
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['obv_slope'] = df['obv'].diff(3).fillna(0)
        
        return df.dropna()

# =============================================================================
# 4. MOTOR DE SIMULACIÓN MULTITEMPORAL
# =============================================================================
class SimonSentinel:
    def __init__(self):
        self.reporter = TradingReporter("Sentinel_MTF-9696E766", initial_capital=Config.INITIAL_CAPITAL)
        self.positions = []
        self.scanner_1h = None
        
    def load_data(self):
        print("📂 Cargando Datos Históricos...")
        for f in [Config.FILE_4H, Config.FILE_1H, Config.FILE_15M]:
            if not os.path.exists(f):
                print(f"❌ Archivo no encontrado: {f}")
                sys.exit(1)
            
        self.df_4h = DataProcessor.prepare_data(pd.read_csv(Config.FILE_4H), Config.G_RSI_PERIOD_MACRO)
        self.df_1h = DataProcessor.prepare_data(pd.read_csv(Config.FILE_1H), 14)
        self.df_15m = DataProcessor.prepare_data(pd.read_csv(Config.FILE_15M), Config.G_RSI_PERIOD_MICRO)
        
        for df in [self.df_4h, self.df_1h, self.df_15m]:
            if pd.api.types.is_numeric_dtype(df['timestamp']) and df['timestamp'].iloc[0] > 10000000000:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        print("🧠 Inicializando Scanner de Estructuras...")
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
        print(f"🚀 Ejecutando Simulación Estricta de ADN: MTF-9696E766...")
        for i in range(50, len(self.df_15m)):
            row_15m = self.df_15m.iloc[i]
            ts = row_15m.name
            
            if self.positions:
                active_trade = self.positions[0]
                self._manage_trade(active_trade, row_15m)
                if active_trade['status'] == 'CLOSED':
                    self.reporter.add_trade(active_trade)
                    self.positions.clear()
                continue 
                
            self._check_entry(row_15m, ts, i)
            
        self.reporter.generate_report()

    def _check_entry(self, row_15m, ts, idx_15m):
        idx_4h = self.df_4h.index.get_indexer([ts], method='pad')[0]
        idx_1h = self.df_1h.index.get_indexer([ts], method='pad')[0]
        if idx_4h == -1 or idx_1h == -1: return
        
        row_4h = self.df_4h.iloc[idx_4h]
        row_1h = self.df_1h.iloc[idx_1h]

        rsi_4h = row_4h['rsi']
        macd_1h = row_1h['macd_hist']
        obv_slope_1h = row_1h['obv_slope']
        dist_fibo_1h = self.get_fibo_context(ts)
        
        rsi_15m = row_15m['rsi']
        prev_rsi_15m = self.df_15m.iloc[idx_15m-1]['rsi']
        rsi_slope_15m = rsi_15m - prev_rsi_15m
        
        signal = None
        
        # --- LÓGICA LONG ---
        if rsi_4h < Config.G_RSI_OVERSOLD_MACRO:
            if rsi_15m < Config.G_RSI_OVERSOLD_MICRO and rsi_slope_15m > 2:
                if dist_fibo_1h < Config.G_FILTRO_DIST_FIBO_MAX and macd_1h > 0 and obv_slope_1h > -500:
                    signal = "LONG"

        # --- LÓGICA SHORT ---
        elif rsi_4h > Config.G_RSI_OVERBOUGHT_MACRO:
            if rsi_15m > Config.G_RSI_OVERBOUGHT_MICRO and rsi_slope_15m < -2:
                if dist_fibo_1h < Config.G_FILTRO_DIST_FIBO_MAX and macd_1h < 0 and obv_slope_1h < 500:
                    signal = "SHORT"

        if signal:
            self._open_position(ts, row_15m['close'], signal)

    def _open_position(self, ts, price, side):
        tp_price = price * (1 + Config.G_TP_NORMAL) if side == 'LONG' else price * (1 - Config.G_TP_NORMAL)
        sl_price = price * (1 - Config.G_SL_NORMAL) if side == 'LONG' else price * (1 + Config.G_SL_NORMAL)
        
        trade = {
            'Trade_ID': f"9696_{ts.strftime('%m%d%H%M')}",
            'Side': side, 'Entry_Time': ts, 'Entry_Price': price,
            'SL': sl_price, 'TP': tp_price,
            'status': 'OPEN', 'PnL_Pct': 0.0, 'Exit_Price': None, 'Exit_Time': None
        }
        self.positions.append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        if trade['Side'] == 'LONG':
            if curr >= trade['TP']: self._close(trade, trade['TP'], row.name)
            elif curr <= trade['SL']: self._close(trade, trade['SL'], row.name)
        else:
            if curr <= trade['TP']: self._close(trade, trade['TP'], row.name)
            elif curr >= trade['SL']: self._close(trade, trade['SL'], row.name)

    def _close(self, trade, price, time):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['status'] = 'CLOSED'
        if trade['Side'] == 'LONG':
            trade['PnL_Pct'] = (price - trade['Entry_Price']) / trade['Entry_Price']
        else:
            trade['PnL_Pct'] = (trade['Entry_Price'] - price) / trade['Entry_Price']
        # Aplicar apalancamiento al PNL final
        trade['PnL_Pct'] *= Config.LEVERAGE

if __name__ == "__main__":
    sim = SimonSentinel()
    sim.load_data()
    sim.run()