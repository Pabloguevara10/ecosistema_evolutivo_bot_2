# Módulo: trailing_stop_dinamico.py - Pertenece a dep_control
import time
from binance.exceptions import BinanceAPIException

class ControladorDinamico:
    def __init__(self, conexion_exchange, disparador, gestor_cupos):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.disparador = disparador
        self.gestor_cupos = gestor_cupos
        
        # Parámetros dinámicos extraídos de la lógica de Sentinel_Pro
        self.be_activation_pct = 0.015  # Activa Break Even al 1.5% de ganancia
        self.be_profit_pct = 0.005      # Asegura un 0.5% mínimo
        self.trailing_dist_pct = 0.01   # Persigue el precio a un 1% de distancia

    def auditar_posiciones(self, symbol="AAVEUSDT", price_precision=3):
        """Revisa todas las posiciones abiertas y ajusta los Stop Loss si el precio avanza a favor."""
        try:
            # ENLACE SEGURO: Usamos el endpoint oficial de estado de posición en Futuros
            posiciones = self.client.futures_position_information(symbol=symbol)
            
            for pos in posiciones:
                cantidad_abierta = float(pos['positionAmt'])
                if cantidad_abierta == 0:
                    continue # Posición cerrada, ignorar
                    
                entry_price = float(pos['entryPrice'])
                mark_price = float(pos['markPrice'])
                side = "LONG" if cantidad_abierta > 0 else "SHORT"
                
                # Calcular rentabilidad actual (PNL Porcentual sin apalancamiento)
                if side == "LONG":
                    pnl_pct = (mark_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - mark_price) / entry_price
                
                # 1. Lógica de Break Even
                if pnl_pct >= self.be_activation_pct:
                    nuevo_sl = entry_price * (1 + self.be_profit_pct) if side == "LONG" else entry_price * (1 - self.be_profit_pct)
                    self._actualizar_stop_loss(symbol, side, abs(cantidad_abierta), nuevo_sl, price_precision, "BREAK EVEN")
                    self._marcar_orden_protegida(entry_price)

                # 2. Lógica de Trailing Stop
                if pnl_pct > (self.be_activation_pct + 0.01):
                    trailing_sl = mark_price * (1 - self.trailing_dist_pct) if side == "LONG" else mark_price * (1 + self.trailing_dist_pct)
                    self._actualizar_stop_loss(symbol, side, abs(cantidad_abierta), trailing_sl, price_precision, "TRAILING STOP")

        except BinanceAPIException as e:
            print(f"⚠️ [Control] Error auditando posiciones: {e.message}")

    def _actualizar_stop_loss(self, symbol, side_posicion, cantidad, nuevo_precio_sl, precision, tipo):
        """Cancela el SL anterior y coloca uno nuevo más cerca del precio actual."""
        sl_redondeado = self.disparador.redondear_precision(nuevo_precio_sl, precision)
        side_orden = "SELL" if side_posicion == "LONG" else "BUY"
        position_side = "LONG" if side_posicion == "LONG" else "SHORT"
        
        try:
            # 1. Cancelar órdenes de Stop actuales
            ordenes_abiertas = self.client.futures_get_open_orders(symbol=symbol)
            for orden in ordenes_abiertas:
                if orden['type'] == 'STOP_MARKET' and orden['positionSide'] == position_side:
                    self.client.futures_cancel_order(symbol=symbol, orderId=orden['orderId'])
            
            # 2. Colocar el nuevo Stop Loss Ajustado SIN BUG
            params_sl = {
                "symbol": symbol,
                "side": side_orden,
                "positionSide": position_side,
                "type": "STOP_MARKET",
                "stopPrice": sl_redondeado,
                "quantity": cantidad
            }
            self.client.futures_create_order(**params_sl)
            print(f"🛡️ [Control] {tipo} actualizado exitosamente a: {sl_redondeado}")
            
        except BinanceAPIException as e:
            pass # Ignoramos errores menores de latencia en cancelaciones

    def _marcar_orden_protegida(self, entry_price):
        for orden in self.gestor_cupos.posiciones_activas:
            if abs(orden['entry_price'] - entry_price) < 0.001 and not orden.get('protegida'):
                orden['protegida'] = True
                print("🔓 [Control] Riesgo liberado. El Gestor de Cupos permite nueva entrada.")