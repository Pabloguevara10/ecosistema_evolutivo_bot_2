# Modulo: asegurador_posicion.py - Pertenece a dep_ejecucion
# Refactor Pilar 1+2+3:
#   - Pilar 2: usa CoordinadorReintentos para SL/TP con reintentos progresivos
#   - Pilar 1: registra cada orden en SQLite tras confirmacion
#   - Pilar 3 defensivo: antes de colocar nuevas protecciones, cancela las
#     existentes EN BINANCE (no solo en SQLite) para evitar acumulacion de
#     ordenes fantasma cuando el tracking SQLite falla silenciosamente.

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

    # =========================================================================
    # ESPERA DE LLENADO
    # =========================================================================
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

    # =========================================================================
    # CONSULTA DE ORDENES EXISTENTES EN BINANCE (fuente de verdad externa)
    # =========================================================================
    def _obtener_ids_proteccion_en_binance(self, symbol: str, position_side: str):
        """
        Consulta Binance para obtener los IDs de todas las ordenes de
        proteccion (SL y TP) ACTUALMENTE abiertas para esta posicion.

        Retorna: (ids_sl: list[str], ids_tp: list[str])

        Se usa como fuente de verdad cuando SQLite no tiene los IDs
        (por fallo silencioso en el registro inicial).
        """
        ids_sl = []
        ids_tp = []
        try:
            ordenes = self.client.futures_get_open_orders(symbol=symbol)
            # Para posicion LONG: las protecciones son ordenes SELL
            # Para posicion SHORT: las protecciones son ordenes BUY
            side_proteccion = "SELL" if position_side == "LONG" else "BUY"

            for o in ordenes:
                if (str(o.get("positionSide", "")).upper() == position_side.upper() and
                        str(o.get("side", "")).upper() == side_proteccion.upper()):
                    tipo = str(o.get("type", "")).upper()
                    oid = str(o["orderId"])
                    if tipo == "STOP_MARKET":
                        ids_sl.append(oid)
                    elif tipo == "TAKE_PROFIT_MARKET":
                        ids_tp.append(oid)
        except Exception as e:
            if self.bitacora:
                self.bitacora.registrar_error(
                    "Asegurador",
                    f"No se pudieron leer ordenes abiertas de Binance: {e}"
                )
        return ids_sl, ids_tp

    def _cancelar_ordenes_en_binance(self, symbol: str, ids: list):
        """
        Cancela una lista de IDs de ordenes en Binance usando el coordinador
        (reintentos progresivos). Errores individuales se registran pero no
        detienen el bucle — la posicion sigue protegida por las nuevas ordenes.
        """
        for oid in ids:
            try:
                if self.coordinador is not None:
                    self.coordinador.ejecutar(
                        accion=lambda o=oid: self.client.futures_cancel_order(
                            symbol=symbol, orderId=o
                        ),
                        tipo_accion="CANCELAR_ORDEN_VIEJA",
                        parametros_pendiente={"symbol": symbol, "id_orden_binance": oid},
                    )
                else:
                    self.client.futures_cancel_order(symbol=symbol, orderId=oid)
                if self.bitacora:
                    self.bitacora.registrar_actividad(
                        "Asegurador", f"Orden vieja cancelada: {oid}"
                    )
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Asegurador", f"Fallo cancelando orden {oid}: {e}"
                    )

    # =========================================================================
    # COLOCACION DE PROTECCIONES (SL + TP)
    # =========================================================================
    def colocar_protecciones(self, symbol: str, side_entrada: str, cantidad: float,
                              sl_price: float, tp_price: float, price_precision: int,
                              id_posicion_local: int = None):
        """
        Coloca Stop Loss y Take Profit para una posicion abierta.

        FLUJO PILAR 3 DEFENSIVO:
          1. Consulta Binance: guarda IDs de SL/TP existentes (si hay).
          2. Coloca NUEVO SL en Binance (via coordinador con reintentos).
          3. Al confirmar el nuevo SL: cancela los SL viejos de la lista del paso 1.
          4. Coloca NUEVO TP en Binance.
          5. Al confirmar el nuevo TP: cancela los TP viejos.
          6. Registra las nuevas ordenes en SQLite.

        En ningun momento la posicion queda sin proteccion: siempre hay al
        menos una orden de cada tipo activa antes de cancelar la anterior.
        """
        side_salida = "SELL" if side_entrada == "BUY" else "BUY"
        position_side = "LONG" if side_entrada == "BUY" else "SHORT"

        sl_redondeado = self.disparador.redondear_precision(sl_price, price_precision)
        tp_redondeado = self.disparador.redondear_precision(tp_price, price_precision)

        # PASO 1: Capturar IDs de protecciones YA EXISTENTES en Binance
        # Hacemos esto ANTES de colocar las nuevas para poder cancelarlas
        # despues de confirmar que las nuevas estan activas.
        ids_sl_viejos, ids_tp_viejos = self._obtener_ids_proteccion_en_binance(
            symbol, position_side
        )
        if ids_sl_viejos or ids_tp_viejos:
            if self.bitacora:
                self.bitacora.registrar_diagnostico(
                    "Asegurador",
                    f"Protecciones existentes detectadas — SL:{ids_sl_viejos} "
                    f"TP:{ids_tp_viejos}. Se cancelaran tras confirmar las nuevas."
                )

        # PASO 2: Colocar nuevo SL
        params_sl = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "STOP_MARKET",
            "stopPrice": sl_redondeado,
            "quantity": cantidad,
        }
        ok_sl = self._colocar_orden_proteccion(
            params_sl, "SL", "COLOCAR_SL",
            id_posicion_local, side_salida, position_side, cantidad, sl_redondeado
        )

        # PASO 3: Si nuevo SL confirmado → cancelar SL(s) anteriores
        if ok_sl and ids_sl_viejos:
            self._cancelar_ordenes_en_binance(symbol, ids_sl_viejos)

        # PASO 4: Colocar nuevo TP
        params_tp = {
            "symbol": symbol,
            "side": side_salida,
            "positionSide": position_side,
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": tp_redondeado,
            "quantity": cantidad,
        }
        ok_tp = self._colocar_orden_proteccion(
            params_tp, "TP", "COLOCAR_TP",
            id_posicion_local, side_salida, position_side, cantidad, tp_redondeado
        )

        # PASO 5: Si nuevo TP confirmado → cancelar TP(s) anteriores
        if ok_tp and ids_tp_viejos:
            self._cancelar_ordenes_en_binance(symbol, ids_tp_viejos)

        if ok_sl and ok_tp:
            if self.bitacora:
                self.bitacora.registrar_actividad(
                    "Asegurador",
                    f"Posicion blindada SL={sl_redondeado} TP={tp_redondeado}"
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
