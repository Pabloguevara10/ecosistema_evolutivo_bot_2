# =============================================================================
# NOMBRE: certificador_estrategias.py
# UBICACIÓN: /dep_desarrollo/
# OBJETIVO: Test de estrés Monte Carlo para validar estrategias robustas.
# =============================================================================

import random
import numpy as np

class CertificadorMonteCarlo:
    def __init__(self, trades, iteraciones=1000, leverage=1):
        self.trades = trades
        self.iteraciones = iteraciones
        self.leverage = leverage
        # Extraer PnL_Pct asegurando que existe y multiplicando por el apalancamiento real
        self.pnl_history = [t['PnL_Pct'] * self.leverage for t in self.trades if 'PnL_Pct' in t]

    def simular_universo(self):
        """Crea una línea temporal alternativa barajando aleatoriamente los trades."""
        if not self.pnl_history:
            return []
        
        # Desordenamos el historial para crear un "universo paralelo"
        universo = random.sample(self.pnl_history, len(self.pnl_history))
        
        capital = 1.0 # Empezamos con el 100% del capital base
        curva = [capital]
        for pnl in universo:
            capital += capital * pnl
            curva.append(capital)
        return curva

    def calcular_drawdown(self, curva):
        """Calcula el Maximum Drawdown de una curva de capital."""
        picos = np.maximum.accumulate(curva)
        # Evitamos división por cero en escenarios extremos
        picos[picos == 0] = 1e-9 
        drawdowns = (picos - curva) / picos
        return np.max(drawdowns)

    def ejecutar_certificacion(self):
        # Si la muestra es muy pequeña, abortamos la certificación
        if len(self.pnl_history) < 20:
            return {
                "riesgo_ruina_absoluta": "N/A",
                "drawdown_esperado": "N/A",
                "aprobado": False,
                "error": "Insuficientes operaciones"
            }

        ruinas = 0
        max_drawdowns = []

        for _ in range(self.iteraciones):
            curva = self.simular_universo()
            
            # Criterio de Ruina: Si el capital cae un 90% (queda < 0.1)
            if any(c < 0.1 for c in curva):
                ruinas += 1
            
            dd = self.calcular_drawdown(curva)
            max_drawdowns.append(dd)

        # Cálculo de métricas finales
        riesgo_ruina = (ruinas / self.iteraciones) * 100
        # Tomamos el percentil 95 (el peor escenario probable)
        dd_esperado = np.percentile(max_drawdowns, 95) * 100 

        # ==============================================================
        # ⚖️ CRITERIOS DE APROBACIÓN ESTRICTOS (MODO INSTITUCIONAL)
        # ==============================================================
        # Una estrategia solo es digna de operar dinero real si:
        # 1. Su riesgo de quemar la cuenta es menor al 3%
        # 2. Su Drawdown en el peor caso posible es menor al 55%
        # ==============================================================
        aprobado = bool(riesgo_ruina < 3.0 and dd_esperado < 55.0)

        # Devolvemos el diccionario con las keys exactas que espera el motor
        return {
            "riesgo_ruina_absoluta": float(riesgo_ruina),
            "drawdown_esperado": float(dd_esperado),
            "aprobado": aprobado
        }