# =============================================================================
# NOMBRE: monitor_mercado.py
# UBICACIÓN: /dep_analisis/
# OBJETIVO: Descargar K-lines en vivo de Binance y calcular indicadores MTF.
# =============================================================================

import pandas as pd
import pandas_ta as ta

class MonitorMercado:
    def __init__(self, client):
        """
        Recibe el cliente oficial de Binance inyectado desde el Orquestador Central.
        """
        self.client = client

    def obtener_velas(self, symbol, timeframe, limit=150):
        """
        Descarga el histórico reciente de velas japonesas.
        Se usa un límite de 150 para darle suficiente "historia" al ADX y MACD 
        para que sus promedios móviles converjan con precisión.
        """
        try:
            # Binance Futures Klines
            klines = self.client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
            
            # Estructurar la matriz de datos crudos
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Limpieza y conversión de tipos
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            # Retornar solo las columnas institucionales
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            print(f"❌ [MonitorMercado] Error descargando velas de {timeframe} para {symbol}: {e}")
            return pd.DataFrame()

    def calcular_indicadores(self, df, rsi_period=14):
        """
        Inyecta la matemática algorítmica al DataFrame crudo usando pandas_ta.
        """
        if df is None or df.empty:
            return df

        # Trabajamos sobre una copia para evitar el warning 'SettingWithCopyWarning' de Pandas
        df = df.copy()

        # ---------------------------------------------------------
        # 1. RSI (Relative Strength Index)
        # ---------------------------------------------------------
        df['rsi'] = ta.rsi(df['close'], length=rsi_period)

        # ---------------------------------------------------------
        # 2. MACD (Moving Average Convergence Divergence)
        # Estándar: Fast=12, Slow=26, Signal=9
        # ---------------------------------------------------------
        macd_df = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd_df is not None:
            # pandas_ta genera 3 columnas: MACD_12_26_9, MACDh_12_26_9 (Histograma), MACDs_12_26_9 (Señal)
            # Mapeamos a nombres simples para que el Orquestador los lea fácilmente
            df['macd'] = macd_df.iloc[:, 0]       # Línea MACD principal
            df['macd_hist'] = macd_df.iloc[:, 1]  # Histograma (Útil para divergencias)

        # ---------------------------------------------------------
        # 3. StochRSI (Stochastic RSI)
        # Estándar: Length=14, RSI=14, K=3, D=3
        # ---------------------------------------------------------
        stochrsi_df = ta.stochrsi(df['close'], length=14, rsi_length=14, k=3, d=3)
        if stochrsi_df is not None:
            # CORRECCIÓN: pandas_ta ya devuelve el valor escalado de 0 a 100.
            df['stochrsi'] = stochrsi_df.iloc[:, 0] # Línea K (Rápida)

        # ---------------------------------------------------------
        # 4. ADX (Average Directional Index)
        # Estándar: Length=14. Mide la fuerza de la tendencia, no la dirección.
        # ---------------------------------------------------------
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx_df is not None:
            df['adx'] = adx_df.iloc[:, 0] # Línea ADX principal

        # ---------------------------------------------------------
        # 5. Bandas de Bollinger (BB) y OBV (Opcionales para tu Evaluador)
        # ---------------------------------------------------------
        bb_df = ta.bbands(df['close'], length=20, std=2)
        if bb_df is not None:
            df['bb_lower'] = bb_df.iloc[:, 0]
            df['bb_mid'] = bb_df.iloc[:, 1]
            df['bb_upper'] = bb_df.iloc[:, 2]

        # Limpiamos las primeras filas (NaN) generadas por el retraso de las medias móviles
        df.dropna(inplace=True)
        
        return df