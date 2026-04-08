# Módulo: certificador_ordenes.py - Pertenece a dep_herramientas
from binance.error import ClientError

class CertificadorOrdenes:
    def __init__(self, conexion_exchange):
        self.conexion = conexion_exchange
        self.client = self.conexion.client

    def verificar_estado_orden(self, symbol: str, order_id: int) -> str:
        """
        Consulta la API de Binance y retorna el estado inmutable de la orden.
        Respuestas posibles: 'NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED'
        """
        try:
            ts = self.conexion.sincronizador.get_timestamp_corregido()
            orden_info = self.client.query_order(symbol=symbol.upper(), orderId=order_id, timestamp=ts)
            
            estado = orden_info.get('status', 'UNKNOWN')
            return estado
            
        except ClientError as e:
            # Si la orden fue cancelada muy rápido o no existe, Binance puede arrojar error
            if e.error_code == -2013: # Order does not exist
                return "NOT_FOUND"
                
            print(f"⚠️ [Certificador] Error de red consultando orden {order_id}: {e.error_message}")
            return "ERROR"
            
    def orden_fue_llenada(self, symbol: str, order_id: int) -> bool:
        """
        Método rápido de validación binaria (True/False) para uso directo del Asegurador.
        """
        estado = self.verificar_estado_orden(symbol, order_id)
        if estado == "FILLED":
            return True
        return False

if __name__ == "__main__":
    print("Módulo Certificador de Órdenes Compilado.")