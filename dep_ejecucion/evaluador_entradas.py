# =============================================================================
# UBICACIÓN: /dep_ejecucion/evaluador_entradas.py
# OBJETIVO: "La Aduana". Intercepta las señales duales, calcula precios de salida
# y solicita presupuesto al Gestor de Cupos antes de aprobar el disparo.
# =============================================================================

import logging

class EvaluadorEntradas:
    def __init__(self, gestor_cupos, leverage=10):
        self.gestor = gestor_cupos
        self.leverage = leverage
        
        # ⚙️ Parámetros por defecto para el Motor LIGHT (Intradiario)
        # La estrategia VIP (Elliott) ya trae sus SL/TP dinámicos desde el análisis
        self.sl_light_pct = 0.015  # Riesgo de 1.5% del precio
        self.tp_light_pct = 0.030  # Beneficio de 3.0% del precio
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("EvaluadorEntradas")

    def procesar_senal(self, paquete_analisis, precio_actual):
        """
        Toma la señal en crudo, define el riesgo y solicita el lotaje.
        """
        if not paquete_analisis:
            return None

        estrategia = paquete_analisis.get('estrategia')
        senal = paquete_analisis.get('senal')
        
        # 1. Definición de Precios de Salida (Stop Loss y Take Profit)
        precio_sl = paquete_analisis.get('sl_dinamico')
        precio_tp = paquete_analisis.get('tp_dinamico')

        # Si es una señal LIGHT, o por algún error el VIP no calculó el SL, usamos la matemática fija
        if estrategia == 'LIGHT' or not precio_sl:
            if senal == 'LONG':
                precio_sl = precio_actual * (1 - self.sl_light_pct)
                precio_tp = precio_actual * (1 + self.tp_light_pct)
            else:
                precio_sl = precio_actual * (1 + self.sl_light_pct)
                precio_tp = precio_actual * (1 - self.tp_light_pct)

        self.logger.info(f"🚦 Recibida señal {estrategia} {senal} a {precio_actual} USDT")

        # 2. Solicitar Presupuesto Institucional al Gestor de Cupos
        autorizado, cantidad_monedas, msj = self.gestor.solicitar_autorizacion(
            tipo_estrategia=estrategia,
            precio_entrada=precio_actual,
            precio_sl=precio_sl,
            leverage=self.leverage
        )

        # 3. Emitir el Veredicto Final para el Disparador de Binance
        if autorizado:
            self.logger.info(f"🟢 Vía libre. Presupuesto asignado: {cantidad_monedas:.3f} AAVE.")
            return {
                'ejecutar': True,
                'estrategia': estrategia,
                'senal': senal,
                'precio_entrada': precio_actual,
                'sl': round(precio_sl, 4),
                'tp': round(precio_tp, 4),
                'cantidad': round(cantidad_monedas, 3) # Precisión requerida por Binance
            }
        else:
            self.logger.warning(f"🔴 Orden {estrategia} {senal} Abortada: {msj}")
            return {
                'ejecutar': False,
                'motivo': msj
            }