# =============================================================================
# UBICACIÓN: /dep_desarrollo/elliott/laboratorio_elliott.py
# OBJETIVO: Procesar data, extraer pivotes, validar ondas y generar reportes.
# =============================================================================

import os
import sys
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(current_dir)

try:
    from extractor_zigzag import ExtractorZigZagATR
    from validador_ondas import ValidadorElliott
    from visualizador_html import VisualizadorElliott
except ImportError as e:
    print(f"❌ Error de Importación en Laboratorio: {e}")
    sys.exit(1)

class LaboratorioElliott:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        self.ruta_data = os.path.join(project_root, "data_historica", self.symbol, "historico_1h.csv")
        self.ruta_reportes = os.path.join(current_dir, "reportes")
        os.makedirs(self.ruta_reportes, exist_ok=True)

    def cargar_datos(self, limite=None):
        print(f"📥 Cargando matriz histórica de {self.symbol}...")
        df = pd.read_csv(self.ruta_data)
        try: df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except ValueError: df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        if limite: return df.tail(limite).reset_index(drop=True)
        return df

    def ejecutar_ensayo(self):
        df_velas = self.cargar_datos(limite=None) 
        
        # 1. Extracción de Estructura
        print("⚙️ Ejecutando Motor de Extracción ZigZag (ATR)...")
        extractor = ExtractorZigZagATR(atr_period=14, atr_multiplier=2.5)
        df_pivotes = extractor.extraer_pivotes(df_velas)
        
        # 2. Validación de Ondas
        print("⚖️ Ejecutando Juez Validador de Elliott...")
        validador = ValidadorElliott()
        df_ondas = validador.identificar_ondas(df_pivotes)
        
        if df_ondas.empty:
            print("⚠️ El validador no encontró ninguna estructura de 5 ondas que cumpla las reglas inquebrantables.")
            return

        # 3. Guardar Reportes
        ruta_csv_pivotes = os.path.join(self.ruta_reportes, "metricas_pivotes.csv")
        ruta_csv_ondas = os.path.join(self.ruta_reportes, "metricas_ondas_validas.csv")
        
        df_pivotes.to_csv(ruta_csv_pivotes, index=False)
        df_ondas.to_csv(ruta_csv_ondas, index=False)
        
        print("\n" + "="*70)
        print(f"🏆 RESULTADO: Se encontraron {len(df_ondas)} ciclos de Elliott perfectos.")
        print("Muestra de las relaciones matemáticas (Fibonacci) de los últimos 5:")
        print("="*70)
        print(df_ondas[['direccion', 'p0_ts', 'fibo_w2', 'fibo_w3', 'fibo_w4']].tail(5).to_string(index=False))
        print("="*70 + "\n")
        
        # 4. Renderizado Visual
        visualizador = VisualizadorElliott(self.symbol)
        visualizador.renderizar_grafico(df_velas, df_pivotes, df_ondas, "auditoria_elliott_completa.html")

if __name__ == "__main__":
    lab = LaboratorioElliott()
    lab.ejecutar_ensayo()