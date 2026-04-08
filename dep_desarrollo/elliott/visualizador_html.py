# =============================================================================
# UBICACIÓN: /dep_desarrollo/elliott/visualizador_html.py
# OBJETIVO: Generar HTML con Velas, ZigZag y Conteo Numérico de Ondas de Elliott.
# =============================================================================

import os
import plotly.graph_objects as go

class VisualizadorElliott:
    def __init__(self, symbol="AAVEUSDT"):
        self.symbol = symbol
        self.ruta_salida = os.path.join(os.path.dirname(__file__), "reportes")
        os.makedirs(self.ruta_salida, exist_ok=True)

    def renderizar_grafico(self, df_velas, df_pivotes, df_ondas, nombre_archivo="auditoria_elliott.html"):
        print("🎨 Renderizando gráfico interactivo de alta resolución...")
        
        # 1. Velas Japonesas
        fig = go.Figure(data=[go.Candlestick(
            x=df_velas['timestamp'],
            open=df_velas['open'], high=df_velas['high'],
            low=df_velas['low'], close=df_velas['close'],
            name='Precio', opacity=0.5
        )])

        # 2. Estructura ZigZag en bruto
        fig.add_trace(go.Scatter(
            x=df_pivotes['timestamp'],
            y=df_pivotes['precio'],
            mode='lines+markers',
            name='Estructura ATR',
            line=dict(color='gray', width=1, dash='dot'),
            marker=dict(size=6, color='gray')
        ))

        # 3. Resaltar Ondas de Elliott Válidas
        if df_ondas is not None and not df_ondas.empty:
            for idx, row in df_ondas.iterrows():
                color = 'lime' if row['direccion'] == 'ALCISTA' else 'magenta'
                fig.add_trace(go.Scatter(
                    x=[row['p0_ts'], row['p1_ts'], row['p2_ts'], row['p3_ts'], row['p4_ts'], row['p5_ts']],
                    y=[row['p0_precio'], row['p1_precio'], row['p2_precio'], row['p3_precio'], row['p4_precio'], row['p5_precio']],
                    mode='lines+markers+text',
                    name=f"Ciclo {row['direccion']} #{idx}",
                    line=dict(color=color, width=4),
                    marker=dict(size=12, color='white', line=dict(color=color, width=2)),
                    text=['0', '1', '2', '3', '4', '5'],
                    textposition="top center",
                    textfont=dict(size=14, color="white")
                ))

        fig.update_layout(
            title=f"Auditoría Visual Elliott Wave - {self.symbol}",
            yaxis_title="Precio (USDT)",
            xaxis_title="Tiempo",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            showlegend=True
        )

        ruta_final = os.path.join(self.ruta_salida, nombre_archivo)
        fig.write_html(ruta_final)
        print(f"✅ Gráfico guardado exitosamente en: {ruta_final}")