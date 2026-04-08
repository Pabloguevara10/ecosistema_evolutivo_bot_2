# Modulo: asegurador_posicion.py - Pertenece a dep_ejecucion
# Refactor Pilar 1+2: usa CoordinadorReintentos para SL/TP y registra en SQLite.

import time


class AseguradorPosicion:
    def __init__(self, conexion_exchange, disparador, coordinador=None,
                 gestor_registro=None, bitacora=None):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.disparador = disparador
        self.coordinador = coordinador
        self.registro = gestor_registro
        self.bitacora = bitacora

    def esperar_llenado(self, symbol: str, order_id: int, max_intentos: int = 60,
                        delay_segundos: float = 1.0) -> bool:
        """
        Bucle de espera. Consulta a Binance si la orden limit/market ya fue ejecutada (FILLED).
        Pilar 2 light: usa esperas (1s) hasta max_intentos.
        """
        if self.bitacora:
            self.bitacora.registrar_actividad(
                "Asegurador", f"Esperando llenado de la orden {order_id}"
            )

        for _ in range(max_intentos):
            try:
                orden_info = self.client.futures_get_order(symbol=symbol, orderId=order_id)
                if orden_info["status"] == "FILLED":
                    if self.bitacora:
                        self.bitacora.registrar_actividad(
                            "Asegurador", f"Orden {order_id} LLENADA"
                        )
                    return True
                elif orden_info["status"] in ["CANCELED", "EXPIRED", "REJECTED"]:
                    if self.bitacora:
                        self.bitacora.registrar_diagnostico(
                            "Asegurador",
                            f"Orden {order_id} {orden_info['status']} - abortando proteccion"
                        )
                    return False
                time.sleep(delay_segundos)
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Asegurador", f"Error consultando orden {order_id}: {e}"
                    )
                time.sleep(delay_segundos)

        if self.bitacora:
            self.bitacora.registrar_diagnostico(
                "Asegurador", f"Timeout esperando llenado de orden {order_id}"
            )
        return False

    def colocar_protecciones(self, symbol: str, side_entrada: str, cantidad: float,
                              sl_price: float, tp_price: float, price_precision: int,
                              id_posicion_local: int = None):
        """
        Dispara Stop Loss y Take Profit fijos en Binance tras confirmar el llenado.
        Pilar 2: cada uno via coordinador (reintentos).
        Pilar 1: cada uno persistido en SQLite tras confirmacion.
        """
        side_salida = "SELL" if side_entrada == "BUY" else "BUY"
        position_side = "LONG" if side_entrada == "BUY" else "SHORT"

        sl_redondeado = self.disparador.redondear_precision(sl_price, price_precision)
        tp_redondeado = self.disparador.redondear_precision(tp_price, price_precision)

        params_sl = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "STOP_MARKET",
            "stopPrice": sl_redondeado,
            "quantity": cantidad,
        }
        params_tp = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": tp_redondeado,
            "quantity": cantidad,
        }

        ok_sl = self._colocar_orden_proteccion(
            params_sl, "SL", "COLOCAR_SL",
            id_posicion_local, side_salida, position_side, cantidad, sl_redondeado
        )
        ok_tp = self._colocar_orden_proteccion(
            params_tp, "TP", "COLOCAR_TP",
            id_posicion_local, side_salida, position_side, cantidad, tp_redondeado
        )

        if ok_sl and ok_tp:
            if self.bitacora:
                self.bitacora.registrar_actividad(
                    "Asegurador", f"Posicion blindada SL={sl_redondeado} TP={tp_redondeado}"
                )
            return True
        return False

    def _colocar_orden_proteccion(self, params, tipo_local, tipo_accion,
                                   id_posicion_local, side, position_side,
                                   cantidad, precio):
        symbol = params["symbol"]
        parametros_pendiente = {
            "symbol": symbol,
            "direccion": position_side,
            "cantidad": cantidad,
            "precio": precio,
            "tipo_orden": params["type"],
            "id_posicion_local": id_posicion_local,
        }

        if self.coordinador is not None:
            resultado = self.coordinador.ejecutar(
                accion=lambda: self.client.futures_create_order(**params),
                tipo_accion=tipo_accion,
                parametros_pendiente=parametros_pendiente,
            )
            if not resultado.ok:
                return False
            respuesta = resultado.respuesta
        else:
            try:
                respuesta = self.client.futures_create_order(**params)
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Asegurador", f"Fallo {tipo_accion}: {e}"
                    )
                return False

        if self.bitacora:
            self.bitacora.registrar_operacion(
                tipo_accion, symbol, side, cantidad, precio, ""
            )

        if self.registro is not None and respuesta:
            try:
                self.registro.registrar_orden(
                    tipo=tipo_local,
                    symbol=symbol,
                    side=side,
                    position_side=position_side,
                    cantidad=cantidad,
                    precio=precio,
                    id_orden_binance=str(respuesta.get("orderId")),
                    id_posicion_local=id_posicion_local,
                    estado="ACEPTADA",
                )
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Asegurador", f"No se pudo persistir {tipo_local} en SQLite: {e}"
                    )
        return True
