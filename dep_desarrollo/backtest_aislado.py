# Módulo: backtest_aislado.py - Pertenece a dep_desarrollo
import pandas as pd

class SimuladorBinance:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 1000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.df = df
        self.capital = initial_capital
        self.capital_inicial = initial_capital
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.historial_trades = []
        
    def redondear_precio(self, precio: float, tick_size: int = 3) -> float:
        """Ajuste de precisión (AAVE suele usar 2 a 3 decimales en Binance)."""
        return round(precio, tick_size)

    def simular_estrategia(self, señales_entrada: list, params_riesgo: dict):
        """
        señales_entrada: lista de diccionarios [{'timestamp': index, 'side': 'LONG', 'entry_price': 100.50}]
        params_riesgo: {'sl_pct': 0.02, 'tp_pct': 0.04, 'leverage': 5}
        """
        print(f"Iniciando simulación sobre {len(señales_entrada)} señales...")
        
        for señal in señales_entrada:
            idx_entrada = señal['timestamp']
            
            # Recortar el dataframe desde el momento de la señal hacia el futuro
            if idx_entrada not in self.df.index:
                continue
            futuro_df = self.df.loc[idx_entrada:]
            if futuro_df.empty or len(futuro_df) < 2:
                continue
                
            entry_price = self.redondear_precio(señal['entry_price'])
            side = señal['side']
            
            # Definir niveles de salida
            sl_dist = entry_price * params_riesgo['sl_pct']
            tp_dist = entry_price * params_riesgo['tp_pct']
            
            sl_price = self.redondear_precio(entry_price - sl_dist) if side == 'LONG' else self.redondear_precio(entry_price + sl_dist)
            tp_price = self.redondear_precio(entry_price + tp_dist) if side == 'LONG' else self.redondear_precio(entry_price - tp_dist)
            
            trade_resultado = self._procesar_trade(futuro_df, side, entry_price, sl_price, tp_price)
            if trade_resultado:
                self.historial_trades.append(trade_resultado)
                
        return self.historial_trades

    def _procesar_trade(self, futuro_df, side, entry_price, sl_price, tp_price):
        orden_tomada = False
        
        for _, vela in futuro_df.iterrows():
            low, high = vela['low'], vela['high']
            
            # 1. Verificar si la orden limit/market fue tomada
            if not orden_tomada:
                if (side == 'LONG' and low <= entry_price) or (side == 'SHORT' and high >= entry_price):
                    orden_tomada = True
                continue # Pasa a la siguiente vela para evitar sesgo de la misma vela
                
            # 2. Si la orden está viva, buscar salidas
            if side == 'LONG':
                if low <= sl_price:
                    return {'resultado': 'LOSS', 'pnl_pct': (sl_price - entry_price) / entry_price}
                if high >= tp_price:
                    return {'resultado': 'WIN', 'pnl_pct': (tp_price - entry_price) / entry_price}
            else:
                if high >= sl_price:
                    return {'resultado': 'LOSS', 'pnl_pct': (entry_price - sl_price) / entry_price}
                if low <= tp_price:
                    return {'resultado': 'WIN', 'pnl_pct': (entry_price - tp_price) / entry_price}
                    
        return None # El backtest terminó y la orden quedó abierta

if __name__ == "__main__":
    print("Módulo de Backtesting Aislado Compilado Correctamente.")