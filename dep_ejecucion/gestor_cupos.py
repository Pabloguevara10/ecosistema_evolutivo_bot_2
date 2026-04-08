# =============================================================================
# UBICACIÓN: /dep_ejecucion/gestor_cupos.py
# OBJETIVO: Control de tráfico dual (Core-Satellite) para estrategias concurrentes.
# Aislamiento de margen y fraccionamiento de riesgo institucional.
# =============================================================================

import logging

class GestorCupos:
    def __init__(self, capital_total=1500.0, max_operaciones_light=2, max_operaciones_vip=1):
        self.capital_total = capital_total
        
        # 🚦 Configuración de Slots (Semáforo Dual)
        self.max_light = max_operaciones_light  # Espacios para el Motor MTF
        self.max_vip = max_operaciones_vip      # Espacio exclusivo para Francotirador Elliott
        
        # ⚖️ Partición de Riesgo Institucional
        self.riesgo_light = 0.015  # 1.5% de riesgo por trade para MTF
        self.riesgo_vip = 0.030    # 3.0% de riesgo por trade para Elliott (Asimetría alta)
        
        # 📦 Control de Estado Interno
        self.operaciones_activas = {
            'LIGHT': [],
            'VIP': []
        }
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("GestorCupos")

    def actualizar_capital(self, nuevo_capital):
        """Actualiza el capital vivo tras cada operación cerrada para aplicar interés compuesto."""
        self.capital_total = nuevo_capital

    def registrar_apertura(self, trade_id, tipo_estrategia):
        """Bloquea un slot formalmente tras la confirmación de Binance."""
        if tipo_estrategia == 'LIGHT':
            self.operaciones_activas['LIGHT'].append(trade_id)
        elif tipo_estrategia == 'VIP':
            self.operaciones_activas['VIP'].append(trade_id)
        self.logger.info(f"🟢 Slot Ocupado [{tipo_estrategia}]: {trade_id}")

    def registrar_cierre(self, trade_id):
        """Libera el slot cuando el Monitor de Posiciones detecta cierre por SL/TP."""
        if trade_id in self.operaciones_activas['LIGHT']:
            self.operaciones_activas['LIGHT'].remove(trade_id)
            self.logger.info(f"🔴 Slot Liberado [LIGHT]: {trade_id}")
        elif trade_id in self.operaciones_activas['VIP']:
            self.operaciones_activas['VIP'].remove(trade_id)
            self.logger.info(f"🔴 Slot Liberado [VIP]: {trade_id}")

    def solicitar_autorizacion(self, tipo_estrategia, precio_entrada, precio_sl, leverage=10):
        """
        Evalúa el tráfico y calcula el lotaje milimétrico.
        Retorna: (Autorizado: bool, Cantidad_Monedas: float, Mensaje: str)
        """
        # 1. Verificación de Semáforo (Aislamiento de Estrategias)
        if tipo_estrategia == 'LIGHT':
            if len(self.operaciones_activas['LIGHT']) >= self.max_light:
                return False, 0.0, "Rechazado: Cupos LIGHT agotados"
            riesgo_aplicar = self.riesgo_light
            
        elif tipo_estrategia == 'VIP':
            if len(self.operaciones_activas['VIP']) >= self.max_vip:
                return False, 0.0, "Rechazado: Cupo VIP (Elliott) agotado"
            riesgo_aplicar = self.riesgo_vip
        else:
            return False, 0.0, "Rechazado: Clasificación de estrategia desconocida"

        # 2. Cálculo de Riesgo Fraccionado (Positon Sizing)
        distancia_sl_abs = abs(precio_entrada - precio_sl)
        if distancia_sl_abs == 0:
            return False, 0.0, "Rechazado: Distancia de Stop Loss inválida (0)"
            
        riesgo_usd = self.capital_total * riesgo_aplicar
        cantidad_monedas = riesgo_usd / distancia_sl_abs
        
        # 3. Filtro de Protección de Margen (Margin Call Prevention)
        margen_requerido = (cantidad_monedas * precio_entrada) / leverage
        
        # El bot no permitirá que ninguna operación inmovilice más del 30% de la cuenta
        if margen_requerido > (self.capital_total * 0.30): 
            self.logger.warning(f"⚠️ Operación {tipo_estrategia} rechazada: Requiere inmovilizar {margen_requerido:.2f} USD de margen.")
            return False, 0.0, "Rechazado: Exposición de margen excesiva"

        self.logger.info(f"✅ Autorizado [{tipo_estrategia}]: {cantidad_monedas:.3f} AAVE | Riesgo: {riesgo_usd:.2f} USD")
        return True, cantidad_monedas, "Autorizado"