# Módulo: disparador_binance.py - Pertenece a dep_ejecucion
import time
from binance.exceptions import BinanceAPIException

class DisparadorBinance:
    def __init__(self, conexion_exchange):
        self.conexion = conexion_exchange
        self.client = self.conexion.client

    def redondear_precision(self, valor: float, precision: int) -> float:
        """Formatea el precio y la cantidad según el Tick Size/Step Size permitido."""
        formato = f"{{:.{precision}f}}"
        return float(formato.format(valor))

    def ejecutar_orden_entrada(self, symbol: str, side: str, tipo_orden: str, cantidad: float, precio: float = None, price_precision: int = 3, qty_precision: int = 1):
        """
        Dispara la orden de entrada en Hedge Mode.
        """
        qty_redondeada = self.redondear_precision(cantidad, qty_precision)
        position_side = "LONG" if side == "BUY" else "SHORT"
        
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(), # BUY o SELL
            "positionSide": position_side,
            "type": tipo_orden.upper(),
            "quantity": qty_redondeada
        }

        if tipo_orden.upper() == "LIMIT":
            if not precio:
                raise ValueError("Se requiere un 'precio' para órdenes LIMIT.")
            params["price"] = self.redondear_precision(precio, price_precision)
            params["timeInForce"] = "GTC"

        try:
            print(f"🚀 ENVIANDO ORDEN: {side} {qty_redondeada} {symbol} a {precio if precio else 'MARKET'}")
            # ENLACE SEGURO: Usamos el endpoint de futuros validado
            respuesta = self.client.futures_create_order(**params)
            print(f"✅ ORDEN TOMADA POR EL EXCHANGE: ID {respuesta.get('orderId')}")
            return respuesta
        except BinanceAPIException as e:
            print(f"❌ ERROR EN DISPARADOR: Código {e.status_code} - {e.message}")
            return None
        except Exception as e:
            print(f"❌ ERROR GENERAL: {str(e)}")
            return None