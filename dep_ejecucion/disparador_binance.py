# Modulo: disparador_binance.py - Pertenece a dep_ejecucion
# Refactor Pilar 2: usa CoordinadorReintentos para reintentos progresivos
# y registra cada orden exitosa en SQLite (Pilar 1).


class DisparadorBinance:
    def __init__(self, conexion_exchange, coordinador=None, gestor_registro=None,
                 bitacora=None):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.coordinador = coordinador
        self.registro = gestor_registro
        self.bitacora = bitacora

    def redondear_precision(self, valor: float, precision: int) -> float:
        """Formatea el precio y la cantidad segun el Tick Size/Step Size permitido."""
        formato = f"{{:.{precision}f}}"
        return float(formato.format(valor))

    def ejecutar_orden_entrada(self, symbol: str, side: str, tipo_orden: str,
                                cantidad: float, precio: float = None,
                                price_precision: int = 3, qty_precision: int = 1,
                                estrategia_origen: str = ""):
        """
        Dispara la orden de entrada en Hedge Mode.
        Pilar 2: usa coordinador con reintentos progresivos.
        Pilar 1: registra la orden en SQLite tras confirmacion.
        """
        qty_redondeada = self.redondear_precision(cantidad, qty_precision)
        position_side = "LONG" if side == "BUY" else "SHORT"

        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "positionSide": position_side,
            "type": tipo_orden.upper(),
            "quantity": qty_redondeada,
        }

        if tipo_orden.upper() == "LIMIT":
            if not precio:
                raise ValueError("Se requiere un 'precio' para ordenes LIMIT.")
            params["price"] = self.redondear_precision(precio, price_precision)
            params["timeInForce"] = "GTC"

        parametros_pendiente = {
            "symbol": symbol.upper(),
            "direccion": position_side,
            "cantidad": qty_redondeada,
            "precio": precio if precio else "MARKET",
            "tipo_orden": tipo_orden.upper(),
            "side": side.upper(),
            "estrategia_origen": estrategia_origen,
        }

        if self.bitacora:
            self.bitacora.registrar_actividad(
                "Disparador",
                f"Enviando ORDEN {side} {qty_redondeada} {symbol} a "
                f"{precio if precio else 'MARKET'}"
            )

        # PILAR 2: coordinador o ejecucion directa (compatibilidad)
        if self.coordinador is not None:
            resultado = self.coordinador.ejecutar(
                accion=lambda: self.client.futures_create_order(**params),
                tipo_accion="ABRIR_POSICION",
                parametros_pendiente=parametros_pendiente,
            )
            if not resultado.ok:
                return None
            respuesta = resultado.respuesta
        else:
            try:
                respuesta = self.client.futures_create_order(**params)
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error("Disparador", f"Fallo orden: {e}")
                return None

        if self.bitacora:
            self.bitacora.registrar_operacion(
                "ABRIR_POSICION", symbol.upper(), side.upper(),
                qty_redondeada, precio if precio else 0.0, estrategia_origen
            )

        # PILAR 1: persistir en SQLite
        if self.registro is not None and respuesta:
            try:
                # Para ordenes MARKET, Binance devuelve avgPrice con el precio real de llenado.
                # Si se usa precio=None (MARKET), precio seria 0.0 sin esta correccion.
                precio_fill = float(respuesta.get("avgPrice") or 0.0)
                if precio_fill == 0.0 and precio:
                    precio_fill = float(precio)

                id_posicion_local = self.registro.crear_posicion(
                    symbol=symbol.upper(),
                    direccion=position_side,
                    precio_entrada=precio_fill,
                    cantidad=qty_redondeada,
                    estrategia_origen=estrategia_origen,
                    estado="PENDIENTE",
                )
                # Marcar inmediatamente como ACTIVA — la orden MARKET se llena
                # en el mismo instante. Sin este paso, obtener_posiciones_abiertas()
                # no la ve y los guards de "posicion activa" fallan.
                self.registro.marcar_posicion_activa(
                    id_posicion_local,
                    str(respuesta.get("orderId"))
                )
                self.registro.registrar_orden(
                    tipo="ENTRADA",
                    symbol=symbol.upper(),
                    side=side.upper(),
                    position_side=position_side,
                    cantidad=qty_redondeada,
                    precio=float(precio) if precio else None,
                    id_orden_binance=str(respuesta.get("orderId")),
                    id_posicion_local=id_posicion_local,
                    estado="ACEPTADA",
                )
                # Devolvemos enriquecida para que el caller asocie la posicion
                if isinstance(respuesta, dict):
                    respuesta["__id_posicion_local"] = id_posicion_local
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Disparador", f"No se pudo persistir orden en SQLite: {e}"
                    )

        return respuesta
