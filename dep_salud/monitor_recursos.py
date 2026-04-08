# =============================================================================
# NOMBRE: monitor_recursos.py
# UBICACIÓN: /dep_salud/
# OBJETIVO: Vigilar el consumo de CPU y Memoria RAM del entorno operativo.
# =============================================================================

import psutil
import os

class MonitorRecursos:
    def __init__(self, bitacora=None, cpu_limit_pct=90.0, ram_limit_pct=85.0):
        self.bitacora = bitacora
        self.cpu_limit = cpu_limit_pct
        self.ram_limit = ram_limit_pct
        # Identificar el proceso exacto del bot
        self.proceso_actual = psutil.Process(os.getpid()) 

    def _log(self, nivel, mensaje):
        if self.bitacora:
            if nivel == 'INFO': self.bitacora.info(mensaje)
            elif nivel == 'WARNING': self.bitacora.warning(mensaje)
            elif nivel == 'CRITICAL': self.bitacora.critical(mensaje)
        else:
            print(f"[{nivel}] {mensaje}")

    def chequear_salud_hardware(self) -> dict:
        """
        Calcula el uso global del servidor y el uso específico del bot.
        """
        # Uso global del sistema
        cpu_global = psutil.cpu_percent(interval=0.1)
        ram_info = psutil.virtual_memory()
        ram_global_pct = ram_info.percent
        
        # Uso específico de este bot en Megabytes
        ram_bot_mb = self.proceso_actual.memory_info().rss / (1024 * 1024)

        estado_seguro = True

        # Validaciones de estrés
        if cpu_global > self.cpu_limit:
            self._log("WARNING", f"🔥 [MONITOR RECURSOS] CPU saturada: {cpu_global}%")
            estado_seguro = False
            
        if ram_global_pct > self.ram_limit:
            self._log("CRITICAL", f"🚨 [MONITOR RECURSOS] RAM casi agotada: {ram_global_pct}%. Riesgo de colapso.")
            estado_seguro = False

        return {
            "hardware_seguro": estado_seguro,
            "cpu_global_pct": cpu_global,
            "ram_global_pct": ram_global_pct,
            "ram_bot_mb": round(ram_bot_mb, 2)
        }