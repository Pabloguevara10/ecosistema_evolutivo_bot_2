# =============================================================================
# NOMBRE: auditor_red.py
# UBICACIÓN: /7_DEPARTAMENTO_SALUD/
# OBJETIVO: Verificar latencia y conexión con Exchange antes de operar.
# =============================================================================

import time
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

class AuditorRed:
    def __init__(self, conexion_exchange, bitacora=None):
        self.client = conexion_exchange.client
        self.bitacora = bitacora
        
        # Umbral máximo de latencia en milisegundos (1 segundo)
        self.max_latencia_ms = 1000 

    def _log(self, nivel, mensaje):
        """Envía los mensajes a la bitácora si existe, si no, usa print."""
        if self.bitacora:
            if nivel == 'INFO': self.bitacora.info(mensaje)
            elif nivel == 'WARNING': self.bitacora.warning(mensaje)
            elif nivel == 'ERROR': self.bitacora.error(mensaje)
        else:
            print(f"[{nivel}] {mensaje}")

    def verificar_internet_global(self) -> bool:
        """Verifica si el servidor tiene acceso a la red externa."""
        try:
            # Hacemos un ping a los servidores de Cloudflare
            requests.get("https://1.1.1.1", timeout=3)
            return True
        except requests.ConnectionError:
            self._log("ERROR", "[AUDITOR RED] Pérdida total de conexión a Internet.")
            return False
        except requests.Timeout:
            self._log("WARNING", "[AUDITOR RED] Tiempo de espera agotado al verificar DNS (Timeout).")
            return False

    def verificar_latencia_binance(self) -> bool:
        """Mide los milisegundos exactos que tarda Binance en responder un ping."""
        try:
            inicio = time.time()
            self.client.ping()
            fin = time.time()
            
            latencia_ms = (fin - inicio) * 1000
            
            if latencia_ms > self.max_latencia_ms:
                self._log("WARNING", f"[AUDITOR RED] Latencia crítica con Binance: {latencia_ms:.0f}ms (Límite: {self.max_latencia_ms}ms)")
                return False
                
            self._log("INFO", f"[AUDITOR RED] Enlace Binance estable. Latencia: {latencia_ms:.0f}ms")
            return True
            
        except (BinanceAPIException, BinanceRequestException) as e:
            self._log("ERROR", f"[AUDITOR RED] Falla en la API de Binance: {e}")
            return False
        except Exception as e:
            self._log("ERROR", f"[AUDITOR RED] Error inesperado de conexión al Exchange: {e}")
            return False

    def chequeo_salud_integral(self) -> bool:
        """
        Rutina de validación principal. Retorna True solo si es seguro operar.
        """
        if not self.verificar_internet_global():
            return False
            
        if not self.verificar_latencia_binance():
            return False
            
        return True