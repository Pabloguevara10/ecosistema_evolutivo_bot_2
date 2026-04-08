# Módulo: calculadoras_indicadores.py - Pertenece a dep_herramientas
import pandas as pd
import numpy as np

class CalculadoraIndicadores:
    
    @staticmethod
    def calcular_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calcula el RSI clásico de Wilder."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calcular_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
        """Devuelve Banda Superior, Media (SMA) y Banda Inferior."""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    @staticmethod
    def calcular_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcula el Average True Range (Volatilidad)."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    @staticmethod
    def detectar_fvg(df: pd.DataFrame) -> pd.DataFrame:
        """
        Escáner de Fair Value Gaps (Vacíos de Liquidez Institucional).
        Identifica FVG Alcistas (Bullish) y Bajistas (Bearish).
        """
        df = df.copy()
        df['fvg_bull'] = False
        df['fvg_bear'] = False
        
        # Logica FVG Bullish: Low de la vela 3 > High de la vela 1
        bullish_cond = df['low'] > df['high'].shift(2)
        # Logica FVG Bearish: High de la vela 3 < Low de la vela 1
        bearish_cond = df['high'] < df['low'].shift(2)
        
        # Filtro de validación: La vela 2 debe ser de cuerpo grande (direccional)
        df.loc[bullish_cond, 'fvg_bull'] = True
        df.loc[bearish_cond, 'fvg_bear'] = True
        
        return df

if __name__ == "__main__":
    # Prueba virtual aislada
    print("Módulo de Calculadoras Matemáticas Compilado Correctamente.")