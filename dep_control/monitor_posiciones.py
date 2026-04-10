# =============================================================================
# NOMBRE: monitor_posiciones.py - Pertenece a dep_control
# REFACTOR Pilar 1: lee posiciones desde el registro SQLite local.
# La validacion contra Binance se hace solo mediante validar_contra_binance(),
# que el hilo de sincronizacion invoca cada 120 s (no en cada ciclo).
# =============================================================================

from binance.exceptions import BinanceAPIException


class MonitorPosiciones:
    def __init__(self, conexion_exchange, gestor_registro=None, bitacora=None):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.registro = gestor_registro
        self.bitacora = bitacora

    def obtener_posiciones_vivas(self, symbol="AAVEUSDT"):
        """
        PILAR 1: devuelve posiciones activas desde el registro SQLite.
        Si el registro no esta disponible, hace fallback a Binance.
        """
        if self.registro is not None:
            try:
                filas = self.registro.obtener_posiciones_abiertas(symbol)
                resultado = []
                for pos in filas:
                    cantidad = float(pos.get("cantidad", 0))
                    side = pos.get("direccion", "LONG")
                    resultado.append({
                        "symbol":       pos.get("symbol", symbol),
                        "cantidad":     cantidad if side == "LONG" else -cantidad,
                        "entry_price":  float(pos.get("precio_entrada", 0)),
                        "mark_price":   0.0,   # se actualiza en el ciclo de precio
                        "side":         side,
                        "pnl_usdt":     0.0,   # se calcula con precio actual
                        "id_local":     pos.get("id_local"),
                        "id_binance":   pos.get("id_posicion_binance"),
                    })
                return resultado
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Monitor_Posiciones",
                        f"Fallo lectura SQLite, usando Binance: {e}"
                    )

        # Fallback a Binance (solo cuando no hay registro inyectado)
        return self._obtener_de_binance(symbol)

    def validar_contra_binance(self, symbol="AAVEUSDT"):
        """
        PILAR 1 — sincronizacion periodica.
        Consulta Binance y devuelve la lista real. El orquestador la usa para
        detectar discrepancias con el registro local y corregirlas.
        Solo se llama cada 120 s desde hilo_sincronizacion_binance.
        """
        return self._obtener_de_binance(symbol)

    def _obtener_de_binance(self, symbol):
        posiciones_vivas = []
        try:
            datos = self.client.futures_position_information(symbol=symbol)
            for pos in datos:
                cantidad = float(pos["positionAmt"])
                if cantidad != 0:
                    posiciones_vivas.append({
                        "symbol":      pos["symbol"],
                        "cantidad":    cantidad,
                        "entry_price": float(pos["entryPrice"]),
                        "mark_price":  float(pos["markPrice"]),
                        "side":        "LONG" if cantidad > 0 else "SHORT",
                        "pnl_usdt":    float(pos["unRealizedProfit"]),
                        "id_local":    None,
                        "id_binance":  None,
                    })
        except BinanceAPIException as e:
            msg = f"Fallo de lectura API Binance: {getattr(e, 'message', e)}"
            if self.bitacora:
                self.bitacora.registrar_error("Monitor_Posiciones", msg)
            else:
                print(f"⚠️ [Monitor Posiciones] {msg}")
        return posiciones_vivas


if __name__ == "__main__":
    print("Módulo Monitor de Posiciones compilado y listo.")
