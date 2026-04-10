# =============================================================================
# NOMBRE: liberador_cupos.py - Pertenece a dep_control
# REFACTOR Pilar 1: compara posiciones por id_posicion_binance desde SQLite
# en vez de entry_price ± 0.001 (que era fragil ante redondeos).
# Si el registro no esta disponible, usa el comportamiento legacy por precio.
# =============================================================================


class LiberadorCupos:
    def __init__(self, gestor_cupos, gestor_registro=None, telegram=None, bitacora=None):
        self.gestor_cupos = gestor_cupos
        self.registro = gestor_registro
        self.telegram = telegram
        self.bitacora = bitacora

    def auditar_y_liberar(self, posiciones_vivas_exchange):
        """
        Verifica si alguna de las ordenes registradas internamente ya cerro en
        el Exchange (fue liquidada por SL o TP).

        PILAR 1: si el registro SQLite esta disponible, compara por id_posicion_binance.
        Fallback: compara por entry_price ± 0.001 (comportamiento legacy).
        """
        if self.registro is not None:
            self._auditar_por_id_binance(posiciones_vivas_exchange)
        else:
            self._auditar_por_precio(posiciones_vivas_exchange)

    # -------------------------------------------------------------------------
    # PILAR 1 — comparacion robusta por id_posicion_binance
    # -------------------------------------------------------------------------
    def _auditar_por_id_binance(self, posiciones_vivas_exchange):
        """
        Marca como CERRADA en SQLite cualquier posicion ACTIVA cuyo
        id_posicion_binance ya no aparezca en la respuesta del exchange.
        A continuacion libera el cupo interno.
        """
        # IDs de posiciones que siguen vivas en Binance
        ids_vivas = {
            str(pos.get("id_binance") or "")
            for pos in posiciones_vivas_exchange
            if pos.get("id_binance")
        }
        # Tambien guardamos precios para el fallback del gestor_cupos
        precios_vivos = {float(pos["entry_price"]) for pos in posiciones_vivas_exchange}

        try:
            posiciones_locales = self.registro.obtener_posiciones_abiertas()
        except Exception as e:
            if self.bitacora:
                self.bitacora.registrar_error("Liberador_Cupos", f"Error SQLite: {e}")
            # Degradar a legacy
            self._auditar_por_precio(posiciones_vivas_exchange)
            return

        for pos_local in posiciones_locales:
            id_binance = str(pos_local.get("id_posicion_binance") or "")
            id_local   = pos_local.get("id_local")
            precio     = float(pos_local.get("precio_entrada", 0))
            symbol     = pos_local.get("symbol", "?")
            direccion  = pos_local.get("direccion", "?")

            # Si el id esta en la lista viva, sigue abierta
            if id_binance and id_binance in ids_vivas:
                continue

            # Sin id_binance (orden registrada antes de recibir confirmacion),
            # usamos el precio como fallback secundario
            if not id_binance:
                if any(abs(p - precio) < 0.001 for p in precios_vivos):
                    continue

            # La posicion cerro en Binance: actualizar SQLite y liberar cupo
            try:
                self.registro.cerrar_posicion(id_local)
            except Exception as e:
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Liberador_Cupos", f"No pudo cerrar id_local={id_local}: {e}"
                    )

            # Liberar en el gestor de cupos interno (comparacion por precio)
            for orden_interna in list(self.gestor_cupos.posiciones_activas):
                if abs(float(orden_interna.get("entry_price", -1)) - precio) < 0.001:
                    self.gestor_cupos.liberar_cupo(orden_interna["id"])
                    break

            espacios = self.gestor_cupos.max_ordenes - len(self.gestor_cupos.posiciones_activas)
            mensaje = (
                f"🔓 <b>CUPO LIBERADO</b>\n"
                f"Posicion {direccion} {symbol} @ {precio} cerrada en Exchange.\n"
                f"Espacios disponibles: {espacios}"
            )
            if self.bitacora:
                self.bitacora.registrar_actividad(
                    "Liberador_Cupos",
                    f"Cupo liberado: {direccion} {symbol} @ {precio} (id_local={id_local})"
                )
            if self.telegram:
                try:
                    self.telegram.enviar_mensaje(mensaje)
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # LEGACY — comparacion por precio (cuando no hay registro SQLite)
    # -------------------------------------------------------------------------
    def _auditar_por_precio(self, posiciones_vivas_exchange):
        precios_vivos = [pos["entry_price"] for pos in posiciones_vivas_exchange]
        ordenes_cerradas = []

        for orden_interna in self.gestor_cupos.posiciones_activas:
            precio_interno = orden_interna["entry_price"]
            sigue_viva = any(abs(p - precio_interno) < 0.001 for p in precios_vivos)
            if not sigue_viva:
                ordenes_cerradas.append(orden_interna)

        for orden in ordenes_cerradas:
            id_orden = orden["id"]
            precio   = orden["entry_price"]
            self.gestor_cupos.liberar_cupo(id_orden)
            espacios = self.gestor_cupos.max_ordenes - len(self.gestor_cupos.posiciones_activas)
            mensaje = (
                f"🔓 <b>CUPO LIBERADO</b>\n"
                f"La posicion en {precio} se ha cerrado en el Exchange.\n"
                f"Espacios disponibles: {espacios}"
            )
            texto_plano = mensaje.replace("<b>", "").replace("</b>", "")
            print(f"✅ [Liberador] {texto_plano}")
            if self.telegram:
                try:
                    self.telegram.enviar_mensaje(mensaje)
                except Exception:
                    pass


if __name__ == "__main__":
    print("Módulo Liberador de Cupos compilado y listo.")
