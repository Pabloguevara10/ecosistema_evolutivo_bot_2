# =============================================================================
# NOMBRE: emisor_señales.py
# UBICACIÓN: /4_DEPARTAMENTO_ANALISIS/
# OBJETIVO: Empaquetar la orden para su transmisión al Depto de Ejecución.
# =============================================================================

class EmisorSenales:
    def __init__(self):
        pass

    def empaquetar_entrada(self, id_estrategia: str, side: str, precio_referencia: float, adn_parametros: dict) -> dict:
        """
        Crea el 'Paquete de Entrada' inmutable.
        Contiene todo lo necesario para evaluar slippage, cupos y asegurar la posición.
        """
        paquete = {
            'id_estrategia': id_estrategia,
            'side': side,
            'precio_referencia': precio_referencia,
            'sl_pct': adn_parametros['sl_pct'],
            'tp_pct': adn_parametros['tp_pct'],
            'leverage': adn_parametros['leverage']
        }
        print(f"📦 [Emisor] Paquete de señal {side} creado correctamente.")
        return paquete