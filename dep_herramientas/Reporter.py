# =============================================================================
# NOMBRE: Reporter.py
# UBICACIÓN: /dep_herramientas/
# OBJETIVO: Registrar operaciones y generar métricas de rendimiento.
# =============================================================================

import pandas as pd

class TradingReporter:
    def __init__(self, strategy_name, initial_capital=1000.0):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades = []
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0

    def add_trade(self, trade_dict):
        """Recibe el diccionario de la operación cerrada y actualiza el capital"""
        # Calcular PnL en dólares basándose en el % ganado/perdido
        pnl_usd = self.current_capital * trade_dict['PnL_Pct']
        self.current_capital += pnl_usd
        
        # Registrar métricas adicionales
        trade_dict['Capital_Acumulado'] = self.current_capital
        trade_dict['PnL_USD'] = pnl_usd
        self.trades.append(trade_dict)

        # Calcular Drawdown Máximo
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def generate_report(self):
        """Imprime el resumen de la estrategia al finalizar la simulación"""
        print("\n" + "="*50)
        print(f"📊 REPORTE DE SIMULACIÓN: {self.strategy_name}")
        print("="*50)
        
        total_trades = len(self.trades)
        
        if total_trades == 0:
            print("⚠️ No se ejecutaron operaciones con esta configuración.")
            print("="*50)
            return

        ganadoras = [t for t in self.trades if t['PnL_Pct'] > 0]
        perdedoras = [t for t in self.trades if t['PnL_Pct'] <= 0]
        
        win_rate = (len(ganadoras) / total_trades) * 100
        roi_total = ((self.current_capital - self.initial_capital) / self.initial_capital) * 100
        
        print(f"Capital Inicial:      ${self.initial_capital:.2f}")
        print(f"Capital Final:        ${self.current_capital:.2f}")
        print(f"ROI Total:            {roi_total:.2f}%")
        print(f"Max Drawdown:         {self.max_drawdown*100:.2f}%")
        print("-" * 50)
        print(f"Total Operaciones:    {total_trades}")
        print(f"Operaciones Ganadas:  {len(ganadoras)}")
        print(f"Operaciones Perdidas: {len(perdedoras)}")
        print(f"Win Rate (Tasa Acierto): {win_rate:.1f}%")
        print("="*50)
        
        # Opcional: Guardar en CSV para que puedas revisarlo en Excel
        df = pd.DataFrame(self.trades)
        archivo_salida = f"reporte_{self.strategy_name}.csv"
        df.to_csv(archivo_salida, index=False)
        print(f"📁 Log detallado guardado en: {archivo_salida}")