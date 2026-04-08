# =============================================================================
# UBICACIÓN: /dep_desarrollo/elliott/extractor_zigzag.py
# OBJETIVO: Detección dinámica de pivotes basada en volatilidad (ATR).
# =============================================================================

import numpy as np
import pandas as pd

class ExtractorZigZagATR:
    def __init__(self, atr_period=14, atr_multiplier=2.5):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def calcular_atr(self, df):
        df = df.copy()
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(self.atr_period).mean()
        return df

    def extraer_pivotes(self, df):
        """
        Escanea la serie temporal y marca un pivote solo si el precio
        revierte más allá de (ATR * Multiplicador).
        """
        df = self.calcular_atr(df).dropna()
        pivotes = []
        
        tendencia_actual = 1  # 1 alcista, -1 bajista
        ultimo_extremo = df['high'].iloc[0]
        indice_extremo = df['timestamp'].iloc[0]
        
        for idx, row in df.iterrows():
            umbral = row['atr'] * self.atr_multiplier
            
            if tendencia_actual == 1:
                if row['high'] > ultimo_extremo:
                    ultimo_extremo = row['high']
                    indice_extremo = row['timestamp']
                elif row['low'] < ultimo_extremo - umbral:
                    pivotes.append({'timestamp': indice_extremo, 'precio': ultimo_extremo, 'tipo': 'MAX'})
                    tendencia_actual = -1
                    ultimo_extremo = row['low']
                    indice_extremo = row['timestamp']
            else:
                if row['low'] < ultimo_extremo:
                    ultimo_extremo = row['low']
                    indice_extremo = row['timestamp']
                elif row['high'] > ultimo_extremo + umbral:
                    pivotes.append({'timestamp': indice_extremo, 'precio': ultimo_extremo, 'tipo': 'MIN'})
                    tendencia_actual = 1
                    ultimo_extremo = row['high']
                    indice_extremo = row['timestamp']
                    
        return pd.DataFrame(pivotes)