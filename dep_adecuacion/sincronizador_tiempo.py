# Módulo: sincronizador_tiempo.py - Pertenece a dep_adecuacion
import time
from binance.um_futures import UMFutures

class SincronizadorTiempo:
    def __init__(self, client: UMFutures):
        self.client = client
        self.time_offset = 0
        self.last_sync_time = 0
        self.sync_interval = 3600 # Resincronizar obligatoriamente cada 1 hora

    def sincronizar(self, forzar=False):
        now = time.time()
        # Solo sincroniza si pasó el tiempo prudencial o si se fuerza por un error previo
        if forzar or (now - self.last_sync_time > self.sync_interval):
            try:
                # Consulta el servidor de Binance (No consume peso/Rate Limit crítico)
                server_time = int(self.client.time()['serverTime'])
                local_time = int(now * 1000)
                self.time_offset = server_time - local_time
                self.last_sync_time = now
                
                # Solo imprime si el desfase es notable (>1 segundo) para no ensuciar la consola
                if abs(self.time_offset) > 1000:
                    print(f"⏱️ Reloj Resincronizado. Desfase corregido: {self.time_offset}ms")
            except Exception as e:
                print(f"⚠️ [Sincronizador] Fallo al leer tiempo del servidor: {e}")

    def get_timestamp_corregido(self):
        """Devuelve el tiempo local milimétricamente ajustado al de Binance."""
        self.sincronizar() # Chequeo rutinario silencioso
        return int(time.time() * 1000) + self.time_offset

if __name__ == "__main__":
    print("Módulo Sincronizador de Tiempo Compilado.")