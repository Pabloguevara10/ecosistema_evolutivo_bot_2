# =============================================================================
# NOMBRE: estrategia_piramide_mtf.py
# UBICACIÓN: /dep_analisis/
# OBJETIVO: Rebalanceo asimétrico (1.0 vs 1.5) con Órdenes LIMIT y Filtro de Fricción.
# =============================================================================

import pandas as pd

class EstrategiaPiramideMTF:
    def __init__(self, ATR_15M_MAX=2.5, min_bandwidth_pct=1.5):
        self.id_estrategia = "PIRAMIDE_MTF"
        # El trailing_callback se envía como porcentaje decimal para Binance
        self.trailing_callback = ATR_15M_MAX / 100.0 
        self.min_bandwidth_pct = min_bandwidth_pct

    def evaluar_fase_maestra(self, precio_act, bb_mid_1h):
        """Define el sesgo institucional basado en la media de 1 Hora."""
        return "ALCISTA" if precio_act > bb_mid_1h else "BAJISTA"

    def calcular_senyal(self, datos_mtf):
        """
        Ingiere el ecosistema MTF y devuelve un diccionario de ejecución.
        Si no hay condiciones óptimas o el mercado está comprimido, devuelve None.
        """
        df_5m = datos_mtf.get('5m')
        df_15m = datos_mtf.get('15m')
        df_1h = datos_mtf.get('1h')

        # Verificación de integridad de datos
        if df_5m is None or df_15m is None or df_1h is None:
            return None
        if df_5m.empty or df_15m.empty or df_1h.empty:
            return None

        p_act = df_5m.iloc[-1]['close']
        bb_1h = df_1h.iloc[-1]
        bb_15m = df_15m.iloc[-1]
        bb_5m = df_5m.iloc[-1]

        # 1. FILTRO DE FRICCIÓN (SQUEEZE AVOIDANCE)
        # Evita operar si las bandas de 15m están muy juntas (pérdida por spread/fees)
        bandwidth_15m = ((bb_15m['bb_upper'] - bb_15m['bb_lower']) / bb_15m['bb_mid']) * 100
        if bandwidth_15m < self.min_bandwidth_pct:
            return None 

        # 2. DEFINIR SESGO DE 1 HORA
        sesgo = self.evaluar_fase_maestra(p_act, bb_1h['bb_mid'])

        # 3. LÓGICA DE LA OLA (RUPTURA DE VOLATILIDAD)
        # Se prioriza la ruptura fuerte antes que el rebalanceo. Órdenes MARKET.
        if bb_15m['adx'] > 25:
            # Ruptura Alcista
            if p_act > bb_15m['bb_upper'] * 1.01:
                return {
                    "estrategia": self.id_estrategia,
                    "lado": "LONG",
                    "tipo_orden": "MARKET",
                    "precio_limit": None,
                    "lotaje": 1.0,
                    "accion": "ENTRADA_OLA_ALCISTA",
                    "reducir_contraria": 1.0, # Liquida todo el Short si lo hay
                    "motivo": "Ruptura Volatilidad 15m confirmada por ADX",
                    "use_trailing": True,
                    "trailing_pct": self.trailing_callback
                }
            # Ruptura Bajista
            elif p_act < bb_15m['bb_lower'] * 0.99:
                return {
                    "estrategia": self.id_estrategia,
                    "lado": "SHORT",
                    "tipo_orden": "MARKET",
                    "precio_limit": None,
                    "lotaje": 1.0,
                    "accion": "ENTRADA_OLA_BAJISTA",
                    "reducir_contraria": 1.0, # Liquida todo el Long si lo hay
                    "motivo": "Ruptura Volatilidad 15m confirmada por ADX",
                    "use_trailing": True,
                    "trailing_pct": self.trailing_callback
                }

        # 4. LÓGICA DE REBALANCEO (PING-PONG)
        # Se utilizan órdenes LIMIT para atrapar el precio exactamente en la banda (Maker Fee)
        
        # Techo: Rechazo en banda superior
        if p_act >= bb_15m['bb_upper'] or p_act >= bb_5m['bb_upper']:
            if df_5m.iloc[-1]['close'] < df_5m.iloc[-1]['open']: 
                lotaje_final = 1.5 if sesgo == "BAJISTA" else 1.0
                return {
                    "estrategia": self.id_estrategia,
                    "lado": "SHORT",
                    "tipo_orden": "LIMIT",
                    "precio_limit": round(bb_15m['bb_upper'], 3),
                    "lotaje": lotaje_final,
                    "accion": "REBALANCEO_TECHO",
                    "reducir_contraria": 0.5, # Vende la mitad del inventario LONG
                    "motivo": f"Rechazo Techo MTF | Sesgo {sesgo}",
                    "use_trailing": False
                }

        # Suelo: Rechazo en banda inferior
        elif p_act <= bb_15m['bb_lower'] or p_act <= bb_5m['bb_lower']:
            if df_5m.iloc[-1]['close'] > df_5m.iloc[-1]['open']: 
                lotaje_final = 1.5 if sesgo == "ALCISTA" else 1.0
                return {
                    "estrategia": self.id_estrategia,
                    "lado": "LONG",
                    "tipo_orden": "LIMIT",
                    "precio_limit": round(bb_15m['bb_lower'], 3),
                    "lotaje": lotaje_final,
                    "accion": "REBALANCEO_SUELO",
                    "reducir_contraria": 0.5, # Vende la mitad del inventario SHORT
                    "motivo": f"Rechazo Suelo MTF | Sesgo {sesgo}",
                    "use_trailing": False
                }

        return None