# =============================================================================
# NOMBRE: coordinador_reintentos.py
# UBICACION: /dep_ejecucion/
# OBJETIVO: Wrapper universal para toda interaccion con Binance.
# Implementa el Pilar 2: Ejecutar -> Verificar -> Registrar con reintentos
# progresivos (0s, 1s, 3s, 9s) y marca PENDIENTE al 3er fallo.
# =============================================================================

import time
import traceback
from datetime import datetime
from typing import Callable, Any, Optional, Dict


# Politica de reintentos progresivos (Pilar 2)
ESPERAS_REINTENTO = [0, 1, 3, 9]  # 4 intentos en total
INTERVALO_PRIMER_REINTENTO_CICLOS = 5  # despues del 3er fallo, esperar 5 ciclos

# Errores de Binance que son DETERMINÍSTICOS (no de red): no tiene sentido reintentar.
# -2019: Margin is insufficient
# -2011: Unknown order sent (orden ya cancelada)
# -1013: Filter failure (precio/cantidad invalida)
# -1111: Precision is over the maximum defined for this asset
ERRORES_NO_REINTENTABLES = {-2019, -2011, -1013, -1111}


class Resultado:
    """Resultado tipado de una invocacion al coordinador."""

    __slots__ = ("ok", "respuesta", "pendiente_id", "ultimo_error", "intentos")

    def __init__(self, ok: bool, respuesta: Any = None, pendiente_id: Optional[int] = None,
                 ultimo_error: str = "", intentos: int = 0):
        self.ok = ok
        self.respuesta = respuesta
        self.pendiente_id = pendiente_id
        self.ultimo_error = ultimo_error
        self.intentos = intentos

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return (f"Resultado(ok={self.ok}, intentos={self.intentos}, "
                f"pendiente_id={self.pendiente_id})")


class CoordinadorReintentos:
    """
    Wrapper universal. Cualquier llamada a Binance debe pasar por aqui.

    Uso tipico:
        resultado = coordinador.ejecutar(
            accion=lambda: client.futures_create_order(**params),
            tipo_accion='COLOCAR_SL',
            parametros_pendiente={'symbol': 'AAVEUSDT', 'cantidad': 0.5, ...},
        )
        if resultado.ok:
            ...usar resultado.respuesta...
        else:
            ...el coordinador ya marco PENDIENTE y notifico Telegram...
    """

    def __init__(self, gestor_registro=None, notificador_telegram=None, bitacora=None,
                 obtener_ciclo_actual: Optional[Callable[[], int]] = None):
        self.registro = gestor_registro
        self.notificador = notificador_telegram
        self.bitacora = bitacora
        self._obtener_ciclo = obtener_ciclo_actual or (lambda: 0)

    # -------------------------------------------------------------------------
    # API PUBLICA
    # -------------------------------------------------------------------------
    def ejecutar(
        self,
        accion: Callable[[], Any],
        tipo_accion: str,
        parametros_pendiente: Optional[Dict[str, Any]] = None,
        crear_pendiente_al_fallar: bool = True,
    ) -> Resultado:
        """
        Ejecuta `accion` con reintentos progresivos. Si los 4 intentos fallan
        (intento 1 + 3 reintentos), marca como PENDIENTE.
        """
        ultimo_error = ""
        ultimo_traceback = ""
        respuesta = None

        for intento_idx, espera in enumerate(ESPERAS_REINTENTO, start=1):
            if espera > 0:
                time.sleep(espera)
            try:
                respuesta = accion()
                # Exito: registramos en bitacora si esta disponible
                if self.bitacora:
                    self.bitacora.registrar_actividad(
                        "Coordinador",
                        f"{tipo_accion} OK en intento {intento_idx}",
                    )
                return Resultado(ok=True, respuesta=respuesta, intentos=intento_idx)
            except Exception as e:
                ultimo_error = self._formatear_error(e)
                ultimo_traceback = traceback.format_exc()
                if self.bitacora:
                    self.bitacora.registrar_error(
                        "Coordinador",
                        f"{tipo_accion} FALLO intento {intento_idx}: {ultimo_error}",
                    )
                # Si el error es determinístico (no de red), no tiene sentido reintentar.
                # Salimos del loop inmediatamente para ahorrar 13s de espera inútil.
                codigo_binance = getattr(e, "code", None)
                if codigo_binance in ERRORES_NO_REINTENTABLES:
                    if self.bitacora:
                        self.bitacora.registrar_diagnostico(
                            "Coordinador",
                            f"{tipo_accion} error determinístico ({codigo_binance}) — sin reintentos.",
                        )
                    break

        # Los 4 intentos fallaron. Marcamos PENDIENTE.
        pendiente_id = None
        if crear_pendiente_al_fallar and self.registro is not None:
            try:
                ciclo = self._obtener_ciclo()
                pendiente_id = self.registro.crear_pendiente(
                    tipo_accion=tipo_accion,
                    parametros=parametros_pendiente or {},
                    intentos_iniciales=len(ESPERAS_REINTENTO),
                    proximo_reintento_ciclo=ciclo + INTERVALO_PRIMER_REINTENTO_CICLOS,
                    ultimo_error=ultimo_error,
                )
            except Exception:
                pendiente_id = None

        self._notificar_pendiente(
            pendiente_id=pendiente_id,
            tipo_accion=tipo_accion,
            parametros=parametros_pendiente or {},
            ultimo_error=ultimo_error,
            ultimo_traceback=ultimo_traceback,
        )

        return Resultado(
            ok=False,
            respuesta=None,
            pendiente_id=pendiente_id,
            ultimo_error=ultimo_error,
            intentos=len(ESPERAS_REINTENTO),
        )

    # -------------------------------------------------------------------------
    # AUXILIARES
    # -------------------------------------------------------------------------
    def _formatear_error(self, e: Exception) -> str:
        # BinanceAPIException expone .code y .message; los demas no
        codigo = getattr(e, "code", None) or getattr(e, "status_code", None)
        mensaje = getattr(e, "message", None) or str(e)
        if codigo is not None:
            return f"code={codigo} msg={mensaje}"
        return f"{type(e).__name__}: {mensaje}"

    def _notificar_pendiente(self, pendiente_id, tipo_accion, parametros,
                              ultimo_error, ultimo_traceback):
        if not self.notificador:
            return
        symbol = parametros.get("symbol", "?")
        direccion = parametros.get("direccion") or parametros.get("position_side", "?")
        cantidad = parametros.get("cantidad", "?")
        precio = parametros.get("precio", "?")

        # Tomamos solo la primera linea del traceback de la excepcion (el tipo)
        tipo_excepcion = ultimo_traceback.strip().split("\n")[-1] if ultimo_traceback else "?"

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensaje = (
            f"\u26a0\ufe0f PROCESO PENDIENTE [#{pendiente_id}]\n"
            f"Acci\u00f3n: {tipo_accion}\n"
            f"S\u00edmbolo: {symbol}    Direcci\u00f3n: {direccion}\n"
            f"Cantidad: {cantidad}    Precio: {precio}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"Intentos realizados: {len(ESPERAS_REINTENTO)}/{len(ESPERAS_REINTENTO)}\n"
            f"\u00daltimo error Binance: {ultimo_error}\n"
            f"Stack: {tipo_excepcion}\n"
            f"Timestamp: {ahora}\n"
            f"Pr\u00f3ximo reintento: en ~{INTERVALO_PRIMER_REINTENTO_CICLOS * 5}s"
        )
        try:
            self.notificador.enviar_mensaje(mensaje)
        except Exception:
            pass
