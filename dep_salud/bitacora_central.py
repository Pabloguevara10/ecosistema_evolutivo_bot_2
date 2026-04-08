# =============================================================================
# NOMBRE: bitacora_central.py
# UBICACIÓN: /dep_salud/
# OBJETIVO: Sistema de Logging Institucional. Genera 3 reportes independientes:
# 1. Salud (Errores y diagnósticos)
# 2. Actividad (Eventos internos, aprobaciones, recepciones)
# 3. Operaciones (Ejecuciones en Binance: Entradas, SL, TP, BE, Trailing)
# =============================================================================

import logging
import os
from datetime import datetime

class BitacoraCentral:
    def __init__(self):
        # 1. Crear directorios principales y subdirectorios de reportes
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.log_dir = os.path.join(project_root, "logs")
        
        self.dir_salud = os.path.join(self.log_dir, "salud")
        self.dir_actividad = os.path.join(self.log_dir, "actividad")
        self.dir_operaciones = os.path.join(self.log_dir, "operaciones")
        
        os.makedirs(self.dir_salud, exist_ok=True)
        os.makedirs(self.dir_actividad, exist_ok=True)
        os.makedirs(self.dir_operaciones, exist_ok=True)

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        # 2. Configuradores de Loggers independientes
        self.logger_salud = self._crear_logger("Salud", os.path.join(self.dir_salud, f"salud_{fecha_hoy}.log"))
        self.logger_actividad = self._crear_logger("Actividad", os.path.join(self.dir_actividad, f"actividad_{fecha_hoy}.log"))
        self.logger_operaciones = self._crear_logger("Operaciones", os.path.join(self.dir_operaciones, f"operaciones_{fecha_hoy}.log"))

    def _crear_logger(self, nombre, ruta_archivo):
        logger = logging.getLogger(nombre)
        logger.setLevel(logging.INFO)
        
        # Evitar duplicidad si se instancia múltiples veces
        if not logger.handlers:
            fh = logging.FileHandler(ruta_archivo, encoding='utf-8')
            fh.setLevel(logging.INFO)
            # Formato estricto: Fecha y Hora | Mensaje
            formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        return logger

    # ===============================================================
    # REPORTE 1: SALUD DEL SISTEMA (Errores y Módulos)
    # ===============================================================
    def registrar_error(self, modulo: str, error: str):
        """Registra excepciones y fallos. Ej: bitacora.registrar_error('Disparador Binance', 'Order timeout')"""
        mensaje = f"[ERROR] | MÓDULO: {modulo} | DETALLE: {error}"
        self.logger_salud.error(mensaje)

    def registrar_diagnostico(self, modulo: str, mensaje: str):
        """Registra métricas de CPU/RAM o advertencias. Ej: uso excesivo de memoria."""
        self.logger_salud.info(f"[DIAGNÓSTICO] | MÓDULO: {modulo} | {mensaje}")

    # ===============================================================
    # REPORTE 2: ACTIVIDAD DEL SISTEMA (Acciones, Evaluaciones y Telegram)
    # ===============================================================
    def registrar_actividad(self, modulo: str, accion: str):
        """Registra procesos del bot. Ej: bitacora.registrar_actividad('Evaluador', 'Señal LONG aprobada por cupo')"""
        mensaje = f"[INFO] | MÓDULO: {modulo} | ACCIÓN: {accion}"
        self.logger_actividad.info(mensaje)

    def registrar_telegram(self, modulo: str, comando: str, detalles: str=""):
        """Registra interacciones específicas de Telegram."""
        mensaje = f"[TELEGRAM] | MÓDULO: {modulo} | INSTRUCCIÓN: {comando} | DETALLES: {detalles}"
        self.logger_actividad.info(mensaje)

    # ===============================================================
    # REPORTE 3: OPERACIONES (Ejecuciones Financieras con el Exchange)
    # ===============================================================
    def registrar_operacion(self, accion: str, symbol: str, side: str, cantidad: float, precio: float, detalles: str = ""):
        """
        accion debe ser: 'ABRIR_POSICION', 'COLOCAR_SL', 'COLOCAR_TP', 'CERRAR_POSICION', 'ACTIVAR_BE', 'ACTIVAR_TRAILING'
        Ej: bitacora.registrar_operacion('COLOCAR_SL', 'AAVEUSDT', 'SELL', 0.5, 98.40)
        """
        mensaje = f"[{accion}] | PAR: {symbol} | LADO: {side} | CANT: {cantidad} | PRECIO: {precio} | NOTAS: {detalles}"
        self.logger_operaciones.info(mensaje)


if __name__ == "__main__":
    # Prueba local del sistema de logs. Ejecuta este archivo directamente para probar.
    bitacora = BitacoraCentral()
    bitacora.registrar_actividad("Main_Orquestador", "Inicialización exitosa del sistema.")
    bitacora.registrar_operacion("ABRIR_POSICION", "AAVEUSDT", "SHORT", 0.5, 95.50, "Orden MTF Market")
    bitacora.registrar_error("Disparador_Binance", "Order type not supported on Testnet")
    bitacora.registrar_telegram("Controlador_TG", "Pausar Bot", "Recibido desde usuario admin")
    print("✅ Sistema de logs generado. Revisa las subcarpetas dentro de /logs/")