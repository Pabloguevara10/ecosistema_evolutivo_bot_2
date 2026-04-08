# =============================================================================
# NOMBRE: Simon_Sentinel_Elliott_v3.py
# UBICACIÓN: /simuladores/
# OBJETIVO: Simulador Híbrido MTF + Validación de Elliott + Riesgo Institucional
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os

# --- 1. CONFIGURACIÓN DINÁMICA DE RUTAS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

tools_path = os.path.join(project_root, 'dep_herramientas')
sys.path.append(tools_path)

try:
    from Reporter import TradingReporter
    print(f"✅ Entorno vinculado: {tools_path}")
except ImportError as e:
    print(f"❌ Error de Vinculación: {e}")
    sys.exit(1)

# =============================================================================
# 2. CONFIGURACIÓN DEL ECOSISTEMA INSTITUCIONAL
# =============================================================================
class Config:
    DATA_BASE_PATH = os.path.join(project_root, "data_historica", "AAVEUSDT")
    FILE_1H  = os.path.join(DATA_BASE_PATH, "historico_1h.csv")
    FILE_15M = os.path.join(DATA_BASE_PATH, "historico_15m.csv")
    
    # Parámetros Elliott y ATR
    ATR_PERIOD = 14
    ATR_MULTIPLIER = 2.5
    FIBO_W2_MIN = 0.382
    FIBO_W2_MAX = 0.950
    
    # --- GESTIÓN DE RIESGO INSTITUCIONAL ---
    INITIAL_CAPITAL = 2000
    LEVERAGE = 10
    RISK_PER_TRADE = 0.08       # Riesgo máximo de 8% del capital vivo por trade
    BE_ACTIVATION_PCT = 0.012   # Si el precio va 1.2% a favor, mover a Breakeven

# =============================================================================
# 3. PROCESADOR Y RASTREADOR DE ONDAS (Con MACD)
# =============================================================================
class ElliottProcessor:
    @staticmethod
    def prepare_data(df, rsi_period=14):
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        
        # 1. RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. MACD Histogram (Doble Confirmación)
        k_fast = df['close'].ewm(span=12, adjust=False).mean()
        k_slow = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = k_fast - k_slow
        df['macd_hist'] = macd_line - macd_line.ewm(span=9, adjust=False).mean()
        
        return df.dropna()

    @staticmethod
    def precompute_live_pivots(df_1h):
        print("⚙️ Mapeando topología estructural del mercado (ATR)...")
        df = df_1h.copy()
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
        df['atr'] = true_range.rolling(Config.ATR_PERIOD).mean()
        df.dropna(inplace=True)

        tendencia = 1
        ultimo_extremo = df['high'].iloc[0]
        ts_extremo = df.index[0]
        pivotes = []

        for ts, row in df.iterrows():
            umbral = row['atr'] * Config.ATR_MULTIPLIER
            if tendencia == 1:
                if row['high'] > ultimo_extremo:
                    ultimo_extremo = row['high']
                    ts_extremo = ts
                elif row['low'] < ultimo_extremo - umbral:
                    pivotes.append({'ts_pivote': ts_extremo, 'precio': ultimo_extremo, 'tipo': 'MAX', 'ts_confirmacion': ts})
                    tendencia = -1
                    ultimo_extremo = row['low']
                    ts_extremo = ts
            else:
                if row['low'] < ultimo_extremo:
                    ultimo_extremo = row['low']
                    ts_extremo = ts
                elif row['high'] > ultimo_extremo + umbral:
                    pivotes.append({'ts_pivote': ts_extremo, 'precio': ultimo_extremo, 'tipo': 'MIN', 'ts_confirmacion': ts})
                    tendencia = 1
                    ultimo_extremo = row['high']
                    ts_extremo = ts
                    
        return pd.DataFrame(pivotes)

# =============================================================================
# 4. MOTOR DE SIMULACIÓN ELLIOTT V3
# =============================================================================
class SimonSentinelElliott:
    def __init__(self):
        self.reporter = TradingReporter("Sentinel_Elliott_V3", initial_capital=Config.INITIAL_CAPITAL)
        self.positions = []
        self.current_capital = Config.INITIAL_CAPITAL
        
    def load_data(self):
        print("📂 Cargando Datos Históricos con Telemetría MACD...")
        self.df_1h = ElliottProcessor.prepare_data(pd.read_csv(Config.FILE_1H))
        self.df_15m = ElliottProcessor.prepare_data(pd.read_csv(Config.FILE_15M), 14)
        
        for df in [self.df_1h, self.df_15m]:
            if pd.api.types.is_numeric_dtype(df['timestamp']) and df['timestamp'].iloc[0] > 10000000000:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

        self.df_pivotes = ElliottProcessor.precompute_live_pivots(self.df_1h)

    def run(self):
        print(f"🛡️ Iniciando Caza de Onda 3 con Escudo Institucional (Riesgo: 3%)...")
        for i in range(10, len(self.df_15m)):
            row_15m = self.df_15m.iloc[i]
            ts = row_15m.name
            
            if self.positions:
                active_trade = self.positions[0]
                self._manage_trade(active_trade, row_15m)
                if active_trade['status'] == 'CLOSED':
                    self.reporter.add_trade(active_trade)
                    self.positions.clear()
                continue 
                
            self._check_elliott_entry(row_15m, ts, i)
            
        self.reporter.generate_report()

    def _check_elliott_entry(self, row_15m, ts, idx_15m):
        pivotes_visibles = self.df_pivotes[self.df_pivotes['ts_confirmacion'] <= ts]
        if len(pivotes_visibles) < 3: return
            
        p0 = pivotes_visibles.iloc[-3]
        p1 = pivotes_visibles.iloc[-2]
        p2 = pivotes_visibles.iloc[-1]
        w1_size = abs(p1['precio'] - p0['precio'])
        if w1_size == 0: return
        
        rsi_15m = row_15m['rsi']
        prev_rsi_15m = self.df_15m.iloc[idx_15m-1]['rsi']
        rsi_slope = rsi_15m - prev_rsi_15m
        macd_15m = row_15m['macd_hist'] # Doble Confirmación
        
        signal = None
        tp_dinamico = None
        sl_dinamico = None
        
        # --- LÓGICA: CAZA DE ONDA 3 ALCISTA ---
        if p0['tipo'] == 'MIN' and p1['tipo'] == 'MAX' and p2['tipo'] == 'MIN':
            if p2['precio'] > p0['precio']:
                fibo_w2 = abs(p2['precio'] - p1['precio']) / w1_size
                if Config.FIBO_W2_MIN <= fibo_w2 <= Config.FIBO_W2_MAX:
                    # Gatillo: RSI girando + MACD positivo
                    if rsi_15m < 48 and rsi_slope > 1 and macd_15m > 0:
                        signal = "LONG"
                        tp_dinamico = p2['precio'] + (w1_size * 1.618)
                        sl_dinamico = p2['precio'] * 0.995 

        # --- LÓGICA: CAZA DE ONDA 3 BAJISTA ---
        elif p0['tipo'] == 'MAX' and p1['tipo'] == 'MIN' and p2['tipo'] == 'MAX':
            if p2['precio'] < p0['precio']:
                fibo_w2 = abs(p2['precio'] - p1['precio']) / w1_size
                if Config.FIBO_W2_MIN <= fibo_w2 <= Config.FIBO_W2_MAX:
                    # Gatillo: RSI girando + MACD negativo
                    if rsi_15m > 52 and rsi_slope < -1 and macd_15m < 0:
                        signal = "SHORT"
                        tp_dinamico = p2['precio'] - (w1_size * 1.618)
                        sl_dinamico = p2['precio'] * 1.005 

        if signal and sl_dinamico and tp_dinamico:
            self._open_position(ts, row_15m['close'], signal, tp_dinamico, sl_dinamico)

    def _open_position(self, ts, price, side, tp_price, sl_price):
        # 🧮 CÁLCULO DE LOTAJE ESTRATÉGICO
        riesgo_usd = self.current_capital * Config.RISK_PER_TRADE
        riesgo_por_moneda = abs(price - sl_price)
        
        if riesgo_por_moneda == 0: return
        
        cantidad_monedas = riesgo_usd / riesgo_por_moneda
        margen_requerido = (cantidad_monedas * price) / Config.LEVERAGE
        
        # Filtro de sobre-exposición de margen
        if margen_requerido > self.current_capital:
            margen_requerido = self.current_capital * 0.95
            cantidad_monedas = (margen_requerido * Config.LEVERAGE) / price
            
        trade = {
            'Trade_ID': f"EW3_{side[:1]}_{ts.strftime('%m%d')}",
            'Side': side, 'Entry_Time': ts, 'Entry_Price': price,
            'SL': sl_price, 'TP': tp_price, 'Qty': cantidad_monedas,
            'Capital_Entrada': self.current_capital,
            'Trailing_Active': False,
            'status': 'OPEN', 'PnL_Pct': 0.0, 'Exit_Price': None, 'Exit_Time': None
        }
        self.positions.append(trade)

    def _manage_trade(self, trade, row):
        curr = row['close']
        entry = trade['Entry_Price']
        
        if trade['Side'] == 'LONG':
            # 🛡️ Escudo Breakeven Activo
            if not trade['Trailing_Active'] and curr >= entry * (1 + Config.BE_ACTIVATION_PCT):
                trade['SL'] = entry * 1.002 # Breakeven + comisiones
                trade['Trailing_Active'] = True
                
            if curr >= trade['TP']: self._close(trade, trade['TP'], row.name)
            elif curr <= trade['SL']: self._close(trade, trade['SL'], row.name)
            
        else:
            # 🛡️ Escudo Breakeven Activo
            if not trade['Trailing_Active'] and curr <= entry * (1 - Config.BE_ACTIVATION_PCT):
                trade['SL'] = entry * 0.998 # Breakeven + comisiones
                trade['Trailing_Active'] = True
                
            if curr <= trade['TP']: self._close(trade, trade['TP'], row.name)
            elif curr >= trade['SL']: self._close(trade, trade['SL'], row.name)

    def _close(self, trade, price, time):
        trade['Exit_Price'] = price
        trade['Exit_Time'] = time
        trade['status'] = 'CLOSED'
        
        # Matemáticas Financieras Reales
        if trade['Side'] == 'LONG':
            pnl_usd = trade['Qty'] * (price - trade['Entry_Price'])
        else:
            pnl_usd = trade['Qty'] * (trade['Entry_Price'] - price)
            
        self.current_capital += pnl_usd
        
        # PnL_Pct adaptado para que el Reporter calcule la curva de balance correctamente
        trade['PnL_Pct'] = pnl_usd / trade['Capital_Entrada']

if __name__ == "__main__":
    sim = SimonSentinelElliott()
    sim.load_data()
    sim.run()