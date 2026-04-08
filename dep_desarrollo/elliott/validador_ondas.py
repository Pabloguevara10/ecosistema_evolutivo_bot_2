# =============================================================================
# UBICACIÓN: /dep_desarrollo/elliott/validador_ondas.py
# OBJETIVO: Escanear pivotes y aplicar las 3 reglas inquebrantables de Elliott.
# =============================================================================

import pandas as pd

class ValidadorElliott:
    def __init__(self):
        pass

    def identificar_ondas(self, df_pivotes):
        patrones_validos = []
        
        # Necesitamos secuencias de 6 puntos (Origen + 5 finales de onda)
        for i in range(len(df_pivotes) - 5):
            p0 = df_pivotes.iloc[i]
            p1 = df_pivotes.iloc[i+1]
            p2 = df_pivotes.iloc[i+2]
            p3 = df_pivotes.iloc[i+3]
            p4 = df_pivotes.iloc[i+4]
            p5 = df_pivotes.iloc[i+5]
            
            # Cálculo de magnitudes de onda absolutas
            w1 = abs(p1['precio'] - p0['precio'])
            w2 = abs(p2['precio'] - p1['precio'])
            w3 = abs(p3['precio'] - p2['precio'])
            w4 = abs(p4['precio'] - p3['precio'])
            w5 = abs(p5['precio'] - p4['precio'])
            
            # ==========================================
            # EVALUACIÓN DE IMPULSO ALCISTA
            # ==========================================
            if p0['tipo'] == 'MIN':
                if not (p1['tipo'] == 'MAX' and p2['tipo'] == 'MIN' and p3['tipo'] == 'MAX' and p4['tipo'] == 'MIN' and p5['tipo'] == 'MAX'):
                    continue
                    
                # Regla 1: Onda 2 no retrocede el 100% de Onda 1
                regla_1 = p2['precio'] > p0['precio']
                
                # Regla 2: Onda 3 NUNCA es la más corta (comparada con W1 y W5)
                regla_2 = not (w3 < w1 and w3 < w5)
                
                # Regla 3: Onda 4 no invade el territorio de la Onda 1
                regla_3 = p4['precio'] > p1['precio']
                
                # Confirmación direccional macro
                tendencia_ok = p3['precio'] > p1['precio'] and p5['precio'] > p3['precio']
                
                if regla_1 and regla_2 and regla_3 and tendencia_ok:
                    patrones_validos.append(self._empaquetar(p0, p1, p2, p3, p4, p5, w1, w2, w3, w4, w5, 'ALCISTA'))
                    
            # ==========================================
            # EVALUACIÓN DE IMPULSO BAJISTA
            # ==========================================
            elif p0['tipo'] == 'MAX':
                if not (p1['tipo'] == 'MIN' and p2['tipo'] == 'MAX' and p3['tipo'] == 'MIN' and p4['tipo'] == 'MAX' and p5['tipo'] == 'MIN'):
                    continue
                    
                regla_1 = p2['precio'] < p0['precio']
                regla_2 = not (w3 < w1 and w3 < w5)
                regla_3 = p4['precio'] < p1['precio']
                tendencia_ok = p3['precio'] < p1['precio'] and p5['precio'] < p3['precio']
                
                if regla_1 and regla_2 and regla_3 and tendencia_ok:
                    patrones_validos.append(self._empaquetar(p0, p1, p2, p3, p4, p5, w1, w2, w3, w4, w5, 'BAJISTA'))
                    
        return pd.DataFrame(patrones_validos)

    def _empaquetar(self, p0, p1, p2, p3, p4, p5, w1, w2, w3, w4, w5, direccion):
        # Empaquetamos coordenadas y relaciones matemáticas de Fibonacci
        return {
            'direccion': direccion,
            'p0_ts': p0['timestamp'], 'p0_precio': p0['precio'],
            'p1_ts': p1['timestamp'], 'p1_precio': p1['precio'],
            'p2_ts': p2['timestamp'], 'p2_precio': p2['precio'],
            'p3_ts': p3['timestamp'], 'p3_precio': p3['precio'],
            'p4_ts': p4['timestamp'], 'p4_precio': p4['precio'],
            'p5_ts': p5['timestamp'], 'p5_precio': p5['precio'],
            'fibo_w2': round(w2 / w1, 3) if w1 > 0 else 0, # Ideal: 0.618
            'fibo_w3': round(w3 / w1, 3) if w1 > 0 else 0, # Ideal: > 1.618
            'fibo_w4': round(w4 / w3, 3) if w3 > 0 else 0  # Ideal: 0.382
        }