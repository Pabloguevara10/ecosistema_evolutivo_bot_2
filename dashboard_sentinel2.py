# =============================================================================
# NOMBRE: dashboard_sentinel.py
# UBICACIÓN: RAÍZ DEL PROYECTO
# OBJETIVO: Interfaz Web para observar el rendimiento del Ecosistema
# EJECUCIÓN: streamlit run dashboard_sentinel.py
# =============================================================================

import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Sentinel Pro Dashboard", layout="wide", page_icon="🤖")

# --- ESTILOS ---
st.markdown("""
    <style>
    .kpi-card {
        background-color: #1e1e1e;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00ff00;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
    }
    .kpi-title { font-size: 14px; color: #aaaaaa; margin-bottom: 5px; }
    .kpi-value { font-size: 28px; font-weight: bold; color: #ffffff; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Sentinel Pro - Panel de Control MTF")
st.markdown("Monitorización en tiempo real del ecosistema evolutivo.")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=10) # Refresca los datos cada 10 segundos
def cargar_datos():
    ruta_csv = "reporte_Sentinel_MTF-9696E766.csv"
    if os.path.exists(ruta_csv):
        df = pd.read_csv(ruta_csv)
        df['Entry_Time'] = pd.to_datetime(df['Entry_Time'])
        return df
    return None

df = cargar_datos()

if df is not None and not df.empty:
    # --- CÁLCULO DE KPIs ---
    total_trades = len(df)
    ganadoras = len(df[df['PnL_Pct'] > 0])
    win_rate = (ganadoras / total_trades) * 100
    
    capital_inicial = 1000.0
    capital_actual = df['Capital_Acumulado'].iloc[-1]
    roi = ((capital_actual - capital_inicial) / capital_inicial) * 100
    
    # --- FILA SUPERIOR: TARJETAS KPI ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Capital Actual</div><div class='kpi-value'>${capital_actual:,.2f}</div></div>", unsafe_allow_html=True)
    with col2:
        color_roi = "#00ff00" if roi > 0 else "#ff0000"
        st.markdown(f"<div class='kpi-card' style='border-left-color:{color_roi}'><div class='kpi-title'>ROI Total</div><div class='kpi-value' style='color:{color_roi}'>{roi:,.2f}%</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='kpi-card' style='border-left-color:#00aaff'><div class='kpi-title'>Win Rate</div><div class='kpi-value'>{win_rate:.1f}%</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='kpi-card' style='border-left-color:#ffaa00'><div class='kpi-title'>Total Operaciones</div><div class='kpi-value'>{total_trades}</div></div>", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)

    # --- GRÁFICO DE CURVA DE CAPITAL ---
    st.subheader("📈 Curva de Crecimiento del Capital")
    # Preparamos los datos para el gráfico
    chart_data = df[['Entry_Time', 'Capital_Acumulado']].set_index('Entry_Time')
    st.line_chart(chart_data, use_container_width=True)

    # --- TABLA DE ÚLTIMAS OPERACIONES ---
    st.subheader("📋 Registro de Operaciones Recientes")
    
    # Aplicamos color al PnL
    def color_pnl(val):
        color = 'green' if val > 0 else 'red'
        return f'color: {color}'

    display_df = df[['Trade_ID', 'Side', 'Entry_Time', 'Entry_Price', 'PnL_USD', 'PnL_Pct']].tail(15).iloc[::-1]
    
    # Formateo visual
    st.dataframe(
        display_df.style.map(color_pnl, subset=['PnL_USD', 'PnL_Pct']).format({'Entry_Price': '${:.2f}', 'PnL_USD': '${:.2f}', 'PnL_Pct': '{:.2%}'}),
        use_container_width=True
    )
else:
    st.warning("No se encontró el archivo de reporte. Ejecuta el simulador o el orquestador primero para generar datos.")