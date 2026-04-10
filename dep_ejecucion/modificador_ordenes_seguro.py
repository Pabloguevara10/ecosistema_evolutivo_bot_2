# =============================================================================
# NOMBRE: modificador_ordenes_seguro.py
# UBICACION: /dep_ejecucion/
# OBJETIVO: Implementar el Pilar 3 - Modificacion de ordenes sin exposicion.
# La posicion SIEMPRE tiene al menos un SL/TP activo en Binance en todo momento.
# =============================================================================

from typing import Optional, Dict, Any


class ModificadorOrdenesSeguro:
    """
    Reemplaza una orden de proteccion (SL o TP) sin exponer la posicion.

    Secuencia inviolable (Pilar 3):
        1. Colocar la NUEVA orden con coordinador (reintentos progresivos)
        2. Confirmar que Binance la acepto
        3. Registrar la nueva en SQLite
        4. Cancelar la orden ANTERIOR con coordinador (reintentos progresivos)
        5. Confirmar la cancelacion
        6. Marcar la anterior como CANCELADA en SQLite

    Si los pasos 4-6 fallan: la posicion sigue protegida (tiene ambas
    ordenes vivas en Binance) y se crea un proceso PENDIENTE de "limpieza"
    para cancelar la orden anterior cuando vuelva a haber red.
    """

    def __init__(self, conexion_exchange, coordinador, gestor_registro, bitacora=None):
        self.conexion = conexion_exchange
        self.client = conexion_exchange.client
        self.coordinador = coordinador
        self.registro = gestor_registro
        self.bitacora = bitacora

    def reemplazar_orden_proteccion(
        self,
        symbol: str,
        position_side: str,
        side_orden: str,
        tipo_orden: str,
        nuevo_stop_price: float,
        cantidad: float,
        id_orden_anterior_binance: Optional[str] = None,
        id_orden_anterior_local: Optional[int] = None,
        id_posicion_local: Optional[int] = None,
        descripcion: str = "REEMPLAZO_PROTECCION",
    ) -> Dict[str, Any]:
        """
        Devuelve un dict con:
            ok: bool
            id_nueva_binance: str | None
            id_nueva_local: int | None
            limpieza_pendiente: bool   (True si la cancelacion del antiguo no se confirmo)
        """
        # Tipos validos: STOP_MARKET (SL) o TAKE_PROFIT_MARKET (TP)
        params_nueva = {
            "symbol": symbol,
            "side": side_orden,
            "positionSide": position_side,
            "type": tipo_orden,
            "stopPrice": nuevo_stop_price,
            "quantity": cantidad,
        }

        parametros_pendiente = {
            "symbol": symbol,
            "direccion": position_side,
            "cantidad": cantidad,
            "precio": nuevo_stop_price,
            "tipo_orden": tipo_orden,
            "descripcion": descripcion,
        }

        # PASO 1+2: Colocar nueva orden con reintentos
        resultado = self.coordinador.ejecutar(
            accion=lambda: self.client.futures_create_order(**params_nueva),
            tipo_accion=f"COLOCAR_NUEVA_{tipo_orden}",
            parametros_pendiente=parametros_pendiente,
        )

        if not resultado.ok:
            # No se pudo colocar la nueva. La anterior sigue activa: la posicion
            # sigue protegida. El coordinador ya marco PENDIENTE.
            return {
                "ok": False,
                "id_nueva_binance": None,
                "id_nueva_local": None,
                "limpieza_pendiente": False,
            }

        respuesta = resultado.respuesta
        id_nueva_binance = str(respuesta.get("orderId")) if respuesta else None

        # PASO 3: Registrar nueva en SQLite
        tipo_local = "SL" if "STOP" in tipo_orden else "TP"
        try:
            id_nueva_local = self.registro.registrar_orden(
                tipo=tipo_local,
                symbol=symbol,
                side=side_orden,
                position_side=position_side,
                cantidad=cantidad,
                precio=nuevo_stop_price,
                id_orden_binance=id_nueva_binance,
                id_posicion_local=id_posicion_local,
                estado="ACEPTADA",
            )
        except Exception as e:
            id_nueva_local = None
            if self.bitacora:
                self.bitacora.registrar_error(
                    "ModificadorSeguro",
                    f"No se pudo registrar nueva orden en SQLite: {e}"
                )

        # En este punto la posicion tiene DOS protecciones vivas en Binance.
        # No hay riesgo de exposicion.

        # PASO 4+5: Cancelar la anterior si la conocemos
        limpieza_pendiente = False
        if id_orden_anterior_binance:
            cancelacion = self.coordinador.ejecutar(
                accion=lambda: self.client.futures_cancel_order(
                    symbol=symbol, orderId=id_orden_anterior_binance
                ),
                tipo_accion=f"CANCELAR_ANTIGUA_{tipo_orden}",
                parametros_pendiente={
                    "symbol": symbol,
                    "id_orden_binance": id_orden_anterior_binance,
                    "tipo_orden": tipo_orden,
                    "id_orden_local_a_marcar": id_orden_anterior_local,
                },
            )

            if cancelacion.ok:
                # PASO 6: Marcar antigua como CANCELADA en SQLite
                if id_orden_anterior_local is not None:
                    try:
                        self.registro.cancelar_orden(id_orden_anterior_local)
                    except Exception:
                        pass
            else:
                limpieza_pendiente = True
                if self.bitacora:
                    self.bitacora.registrar_diagnostico(
                        "ModificadorSeguro",
                        f"Cancelacion de orden anterior pendiente. La posicion tiene "
                        f"dos protecciones vivas hasta que el GestorPendientes complete."
                    )

        return {
            "ok": True,
            "id_nueva_binance": id_nueva_binance,
            "id_nueva_local": id_nueva_local,
            "limpieza_pendiente": limpieza_pendiente,
        }
