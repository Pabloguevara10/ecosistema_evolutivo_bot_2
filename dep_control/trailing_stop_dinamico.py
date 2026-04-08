# Modulo: trailing_stop_dinamico.py - Pertenece a dep_control
# Refactor Pilar 1+3:
#   - Lee posiciones desde el registro SQLite local (no consulta Binance cada ciclo)
#   - Modifica SL via ModificadorOrdenesSeguro (nuevo SL ANTES de cancelar viejo)

class ControladorDinamico:
    def __init__(self, conexion_exchange, disparador, gestor_cupos,
                 gestor_registro=None, modificador_seguro=None, bitacora=None):
        self.conexion = conexion_exchange
        self.client = self.conexion.client
        self.disparador = disparador
        self.gestor_cupos = gestor_cupos
        self.registro = gestor_registro
        self.modificador = modificador_seguro
        self.bitacora = bitacora

        # Parametros dinamicos extraidos de la logica de Sentinel_Pro
        self.be_activation_pct = 0.015  # Activa Break Even al 1.5% de ganancia
        self.be_profit_pct = 0.005      # Asegura un 0.5% minimo
        self.trailing_dist_pct = 0.01   # Persigue el precio a un 1% de distancia

    def auditar_posiciones(self, symbol="AAVEUSDT", price_precision=3, mark_price=None):
        """
        Revisa todas las posiciones abiertas y ajusta los Stop Loss si el precio avanza a favor.
        Lee del registro SQLite local cuando esta disponible (Pilar 1).
        """
        try:
            posiciones = self._obtener_posiciones(symbol)
            if mark_price is None:
                # Solo si no nos pasaron el precio, lo consultamos a Binance
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                mark_price = float(ticker["price"])

            for pos in posiciones:
                cantidad_abierta = pos["cantidad"] if isinstance(pos, dict) else float(pos.get("positionAmt", 0))
                if cantidad_abierta == 0:
                    continue

                entry_price = pos["precio_entrada"] if "precio_entrada" in pos else float(pos.get("entryPrice", 0))
                side = pos.get("direccion") or ("LONG" if cantidad_abierta > 0 else "SHORT")

                # Calcular rentabilidad actual (PNL Porcentual sin apalancamiento)
                if side == "LONG":
                    pnl_pct = (mark_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - mark_price) / entry_price

                # 1. Logica de Break Even
                if pnl_pct >= self.be_activation_pct:
                    nuevo_sl = entry_price * (1 + self.be_profit_pct) if side == "LONG" else entry_price * (1 - self.be_profit_pct)
                    self._actualizar_stop_loss(symbol, side, abs(cantidad_abierta), nuevo_sl,
                                                price_precision, "BREAK EVEN", pos)
                    self._marcar_orden_protegida(entry_price)

                # 2. Logica de Trailing Stop
                if pnl_pct > (self.be_activation_pct + 0.01):
                    trailing_sl = mark_price * (1 - self.trailing_dist_pct) if side == "LONG" else mark_price * (1 + self.trailing_dist_pct)
                    self._actualizar_stop_loss(symbol, side, abs(cantidad_abierta), trailing_sl,
                                                price_precision, "TRAILING STOP", pos)

        except Exception as e:
            if self.bitacora:
                self.bitacora.registrar_error("Control_Trailing", f"Error auditando posiciones: {e}")

    def _obtener_posiciones(self, symbol):
        """Pilar 1: lee del registro SQLite si esta disponible. Fallback a Binance."""
        if self.registro is not None:
            return self.registro.obtener_posiciones_abiertas(symbol)
        # Fallback (solo si no hay registro inyectado)
        return self.client.futures_position_information(symbol=symbol)

    def _actualizar_stop_loss(self, symbol, side_posicion, cantidad, nuevo_precio_sl,
                              precision, tipo, pos):
        """
        PILAR 3: Coloca el nuevo SL ANTES de cancelar el anterior.
        Si esta disponible el ModificadorOrdenesSeguro, delega ahi (con reintentos).
        """
        sl_redondeado = self.disparador.redondear_precision(nuevo_precio_sl, precision)
        side_orden = "SELL" if side_posicion == "LONG" else "BUY"
        position_side = "LONG" if side_posicion == "LONG" else "SHORT"

        # Identificar la orden de SL anterior (en el registro local)
        id_orden_anterior_binance = None
        id_orden_anterior_local = None
        id_posicion_local = pos.get("id_local") if isinstance(pos, dict) else None

        if self.registro is not None:
            try:
                ordenes_sl = self.registro.obtener_ordenes_proteccion(
                    symbol=symbol, position_side=position_side, tipo="SL"
                )
                if ordenes_sl:
                    # La mas reciente
                    ultima = ordenes_sl[-1]
                    id_orden_anterior_binance = ultima.get("id_orden_binance")
                    id_orden_anterior_local = ultima.get("id_local")
            except Exception:
                pass

        # Si no tenemos modificador seguro, no podemos respetar el Pilar 3.
        # En ese caso bailamos out con un log fuerte para que se vea.
        if self.modificador is None:
            if self.bitacora:
                self.bitacora.registrar_error(
                    "Control_Trailing",
                    "ModificadorOrdenesSeguro no inyectado. Omitiendo actualizacion "
                    "de SL para no exponer la posicion."
                )
            return

        resultado = self.modificador.reemplazar_orden_proteccion(
            symbol=symbol,
            position_side=position_side,
            side_orden=side_orden,
            tipo_orden="STOP_MARKET",
            nuevo_stop_price=sl_redondeado,
            cantidad=cantidad,
            id_orden_anterior_binance=id_orden_anterior_binance,
            id_orden_anterior_local=id_orden_anterior_local,
            id_posicion_local=id_posicion_local,
            descripcion=tipo,
        )

        if resultado["ok"]:
            if self.bitacora:
                self.bitacora.registrar_operacion(
                    "ACTIVAR_TRAILING" if "TRAILING" in tipo else "ACTIVAR_BE",
                    symbol, side_orden, cantidad, sl_redondeado, tipo
                )
            if resultado.get("limpieza_pendiente") and self.bitacora:
                self.bitacora.registrar_diagnostico(
                    "Control_Trailing",
                    "Posicion protegida por DOS SL temporalmente; limpieza pendiente."
                )

    def _marcar_orden_protegida(self, entry_price):
        for orden in self.gestor_cupos.posiciones_activas:
            if abs(orden['entry_price'] - entry_price) < 0.001 and not orden.get('protegida'):
                orden['protegida'] = True
                if self.bitacora:
                    self.bitacora.registrar_actividad(
                        "Control_Trailing",
                        "Riesgo liberado. El Gestor de Cupos permite nueva entrada."
                    )
