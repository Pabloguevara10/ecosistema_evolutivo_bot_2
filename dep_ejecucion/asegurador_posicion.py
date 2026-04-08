# Módulo: asegurador_posicion.py - Pertenece a dep_ejecucion
import time
from binance.exceptions import BinanceAPIException

class AseguradorPosicion:
    def __init__(self, conexion_exchange, disparador):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.disparador = disparador

    def esperar_llenado(self, symbol: str, order_id: int, max_intentos: int = 60, delay_segundos: float = 1.0) -> bool:
        """
        Bucle de espera. Consulta a Binance si la orden limit/market ya fue ejecutada (FILLED).
        """
        print(f"⏳ Esperando llenado de la orden {order_id}...")
        for _ in range(max_intentos):
            try:
                # ENLACE SEGURO: Usamos endpoint de futuros
                orden_info = self.client.futures_get_order(symbol=symbol, orderId=order_id)
                
                if orden_info['status'] == 'FILLED':
                    print("🎯 ORDEN LLENADA. El precio tocó la entrada.")
                    return True
                elif orden_info['status'] in ['CANCELED', 'EXPIRED', 'REJECTED']:
                    print(f"⚠️ ORDEN {orden_info['status']}. Abortando protección.")
                    return False
                    
                time.sleep(delay_segundos)
                
            except BinanceAPIException as e:
                print(f"⚠️ Error consultando estado de orden: {e.message}")
                time.sleep(delay_segundos)
                
        print("⏱️ TIEMPO DE ESPERA AGOTADO. La orden sigue abierta sin llenarse.")
        return False

    def colocar_protecciones(self, symbol: str, side_entrada: str, cantidad: float, sl_price: float, tp_price: float, price_precision: int):
        """
        Dispara Stop Loss y Take Profit fijos en Binance tras confirmar el llenado.
        """
        side_salida = "SELL" if side_entrada == "BUY" else "BUY"
        position_side = "LONG" if side_entrada == "BUY" else "SHORT"
        
        sl_redondeado = self.disparador.redondear_precision(sl_price, price_precision)
        tp_redondeado = self.disparador.redondear_precision(tp_price, price_precision)
        
        # PARÁMETROS LIMPIOS: Sin el bug de closePosition, pasando cantidad explícita
        params_sl = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "STOP_MARKET",
            "stopPrice": sl_redondeado,
            "quantity": cantidad 
        }
        
        params_tp = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": tp_redondeado,
            "quantity": cantidad
        }

        try:
            self.client.futures_create_order(**params_sl)
            print(f"🛡️ STOP LOSS FIJADO EN: {sl_redondeado}")
            
            self.client.futures_create_order(**params_tp)
            print(f"💰 TAKE PROFIT FIJADO EN: {tp_redondeado}")
            
            print("✅ POSICIÓN BLINDADA CON ÉXITO.")
            return True
        except BinanceAPIException as e:
            print(f"❌ ERROR CRÍTICO COLOCANDO PROTECCIONES: {e.message}")
            return False