# =============================================================================
# NOMBRE: comparador_estrategias.py
# UBICACIÓN: /dep_analisis/
# OBJETIVO: Cerebro Analítico Dual. Evalúa en paralelo la estrategia MTF (Light)
# y la estrategia de Ondas de Elliott (VIP) asignando prioridad absoluta.
# =============================================================================

import json
import os
import pandas as pd
import numpy as np

class ComparadorEstrategias:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        # Enrutamiento de ADN MTF
        self.ruta_db = os.path.join(project_root, "dep_desarrollo", "bbdd_estrategias", "estrategias_aprobadas_mtf.json")
        self.adn = self._cargar_adn_vigente()

        # 🎯 Parámetros Institucionales del Francotirador (Elliott V3)
        self.atr_period = 14
        self.atr_mult = 2.5
        self.fibo_w2_min = 0.382
        self.fibo_w2_max = 0.950

    def _cargar_adn_vigente(self):
        if not os.path.exists(self.ruta_db):
            print(f"⚠️ [Comparador] No se halló BBDD de ADN en {self.ruta_db}. Se usarán parámetros por defecto.")
            # Parámetros salvavidas en caso de que la BBDD falle
            return {'parametros': {'rsi_os_macro': 36, 'rsi_ob_macro': 64, 'rsi_os_micro': 35, 'rsi_ob_micro': 65, 'fibo_max_dist': 0.015}}
        
        with open(self.ruta_db, 'r') as file:
            estrategias = json.load(file)
            
        mejor_estrategia = estrategias[-1]  # Toma la última mutación aprobada
        print(f"🧬 [Comparador] Motor LIGHT cargado con ADN: {mejor_estrategia.get('id_estrategia', 'Default')}")
        return mejor_estrategia

    def evaluar_mercado(self, df_4h, df_1h, df_15m, dist_fibo):
        """
        El Enrutador Maestro: Evalúa el mercado en ambas lógicas.
        PRIORIDAD 1: Francotirador Elliott (VIP)
        PRIORIDAD 2: Motor Evolutivo (LIGHT)
        """
        # 1. Intentar cazar la Onda 3 (Alta Asimetría)
        senal_vip = self._evaluar_condiciones_elliott(df_1h, df_15m)
        if senal_vip:
            return senal_vip # Prioridad Absoluta
            
        # 2. Si el mercado está sucio, usar Motor Light para rascar flujo de caja
        senal_light = self._evaluar_condiciones_mtf(df_4h, df_1h, df_15m, dist_fibo)
        if senal_light:
            return senal_light
            
        return None

    def _evaluar_condiciones_mtf(self, df_4h, df_1h, df_15m, dist_fibo):
        """Lógica estricta de Cascada 4H -> 1H -> 15m (Motor LIGHT)."""
        parametros = self.adn['parametros']
        
        rsi_4h = df_4h.iloc[-1]['rsi']
        rsi_15m = df_15m.iloc[-1]['rsi']
        rsi_15m_prev = df_15m.iloc[-2]['rsi']
        macd_1h = df_1h.iloc[-1].get('macd_hist', 0)
        obv_slope_1h = df_1h.iloc[-1].get('obv_slope', 0)

        if rsi_4h < parametros['rsi_os_macro']:
            if rsi_15m < parametros['rsi_os_micro'] and (rsi_15m - rsi_15m_prev) > 2:
                if dist_fibo < parametros['fibo_max_dist'] and macd_1h > 0 and obv_slope_1h > -500:
                    return {'estrategia': 'LIGHT', 'senal': 'LONG', 'sl_dinamico': None, 'tp_dinamico': None}

        elif rsi_4h > parametros['rsi_ob_macro']:
            if rsi_15m > parametros['rsi_ob_micro'] and (rsi_15m - rsi_15m_prev) < -2:
                if dist_fibo < parametros['fibo_max_dist'] and macd_1h < 0 and obv_slope_1h < 500:
                    return {'estrategia': 'LIGHT', 'senal': 'SHORT', 'sl_dinamico': None, 'tp_dinamico': None}

        return None

    def _evaluar_condiciones_elliott(self, df_1h, df_15m):
        """Lógica del Francotirador: Busca la Onda 3 validando retrocesos estructurales."""
        df_pivotes = self._extraer_pivotes_vivo(df_1h)
        
        if len(df_pivotes) < 3:
            return None
            
        p0 = df_pivotes.iloc[-3]
        p1 = df_pivotes.iloc[-2]
        p2 = df_pivotes.iloc[-1]
        
        w1_size = abs(p1['precio'] - p0['precio'])
        if w1_size == 0: return None
        
        row_15m = df_15m.iloc[-1]
        rsi_15m = row_15m['rsi']
        rsi_slope = rsi_15m - df_15m.iloc[-2]['rsi']
        
        # Generar MACD 15m al vuelo para confirmar momentum si no existe en la matriz
        if 'macd_hist' not in df_15m.columns:
            k_fast = df_15m['close'].ewm(span=12, adjust=False).mean()
            k_slow = df_15m['close'].ewm(span=26, adjust=False).mean()
            macd_hist = (k_fast - k_slow) - (k_fast - k_slow).ewm(span=9, adjust=False).mean()
            macd_15m = macd_hist.iloc[-1]
        else:
            macd_15m = row_15m['macd_hist']

        # CAZA DE ONDA 3 ALCISTA
        if p0['tipo'] == 'MIN' and p1['tipo'] == 'MAX' and p2['tipo'] == 'MIN':
            if p2['precio'] > p0['precio']: # Regla Inquebrantable
                fibo_w2 = abs(p2['precio'] - p1['precio']) / w1_size
                if self.fibo_w2_min <= fibo_w2 <= self.fibo_w2_max:
                    if rsi_15m < 48 and rsi_slope > 1 and macd_15m > 0:
                        tp = p2['precio'] + (w1_size * 1.618)
                        sl = p2['precio'] * 0.995 # Invalidación bajo p2
                        return {'estrategia': 'VIP', 'senal': 'LONG', 'sl_dinamico': sl, 'tp_dinamico': tp}

        # CAZA DE ONDA 3 BAJISTA
        elif p0['tipo'] == 'MAX' and p1['tipo'] == 'MIN' and p2['tipo'] == 'MAX':
            if p2['precio'] < p0['precio']: # Regla Inquebrantable
                fibo_w2 = abs(p2['precio'] - p1['precio']) / w1_size
                if self.fibo_w2_min <= fibo_w2 <= self.fibo_w2_max:
                    if rsi_15m > 52 and rsi_slope < -1 and macd_15m < 0:
                        tp = p2['precio'] - (w1_size * 1.618)
                        sl = p2['precio'] * 1.005 # Invalidación sobre p2
                        return {'estrategia': 'VIP', 'senal': 'SHORT', 'sl_dinamico': sl, 'tp_dinamico': tp}
                        
        return None

    def _extraer_pivotes_vivo(self, df_1h):
        """Motor matemático ultra-rápido para vectorizar la estructura de 1H en milisegundos."""
        df = df_1h.copy()
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.max(pd.concat([high_low, high_close, low_close], axis=1), axis=1)
        df['atr'] = true_range.rolling(self.atr_period).mean()
        df.dropna(inplace=True)

        tendencia = 1
        ultimo_extremo = df['high'].iloc[0]
        pivotes = []

        for ts, row in df.iterrows():
            umbral = row['atr'] * self.atr_mult
            if tendencia == 1:
                if row['high'] > ultimo_extremo:
                    ultimo_extremo = row['high']
                elif row['low'] < ultimo_extremo - umbral:
                    pivotes.append({'precio': ultimo_extremo, 'tipo': 'MAX'})
                    tendencia = -1
                    ultimo_extremo = row['low']
            else:
                if row['low'] < ultimo_extremo:
                    ultimo_extremo = row['low']
                elif row['high'] > ultimo_extremo + umbral:
                    pivotes.append({'precio': ultimo_extremo, 'tipo': 'MIN'})
                    tendencia = 1
                    ultimo_extremo = row['high']
        
        return pd.DataFrame(pivotes[-10:]) # Solo necesitamos los últimos para Elliott