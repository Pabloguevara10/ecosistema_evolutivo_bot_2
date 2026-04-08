# =============================================================================
# NOMBRE: gestor_pendientes.py
# UBICACION: /dep_registro/
# OBJETIVO: Reintentar acciones marcadas como PENDIENTE (Pilar 2).
# Politica: cada 5 ciclos, maximo 10 reintentos antes de escalar.
# =============================================================================

import json
import traceback
from typing import Callable, Dict, Any, Optional


# Politica acordada con el usuario
INTERVALO_REINTENTO_CICLOS = 5
MAX_REINTENTOS_TOTALES = 10


class GestorPendientes:
    """
    Procesa la cola de procesos_pendientes en cada ciclo del orquestador.

    Cada accion pendiente registra en `parametros_json` el contexto necesario
    para reintentarse: tipo de accion + parametros. El gestor mantiene un
    diccionario de "ejecutores" registrados por nombre de accion.
    """

    def __init__(self, gestor_registro, notificador_telegram=None, bitacora=None):
        self.registro = gestor_registro
        self.notificador = notificador_telegram
        self.bitacora = bitacora
        self.ejecutores: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    # -------------------------------------------------------------------------
    # REGISTRO DE EJECUTORES
    # -------------------------------------------------------------------------
    def registrar_ejecutor(self, tipo_accion: str, callable_ejecutor: Callable):
        """
        Asocia un nombre de accion (ej: 'ABRIR_POSICION') con la funcion que
        sabe reintentarla. La funcion recibe los parametros (dict) y debe
        retornar (ok: bool, mensaje_error: str).
        """
        self.ejecutores[tipo_accion] = callable_ejecutor

    # -------------------------------------------------------------------------
    # PROCESAMIENTO DEL CICLO
    # -------------------------------------------------------------------------
    def procesar_pendientes(self, ciclo_actual: int) -> int:
        """
        Recorre los pendientes listos y los reintenta. Retorna cuantos se procesaron.
        """
        listos = self.registro.listar_pendientes_listos(ciclo_actual)
        procesados = 0

        for fila in listos:
            id_pend = fila["id"]
            tipo_accion = fila["tipo_accion"]
            try:
                parametros = json.loads(fila["parametros_json"]) if fila["parametros_json"] else {}
            except Exception:
                parametros = {}

            ejecutor = self.ejecutores.get(tipo_accion)
            if ejecutor is None:
                # Sin ejecutor registrado, no reintentamos pero tampoco escalamos
                # automaticamente. Lo marcamos para reintento futuro.
                self._reprogramar(id_pend, fila["intentos_totales"], ciclo_actual,
                                  ultimo_error=f"Sin ejecutor registrado para '{tipo_accion}'")
                continue

            ok, mensaje_error = self._intentar(ejecutor, parametros)
            procesados += 1

            if ok:
                self.registro.marcar_pendiente_resuelto(id_pend)
                self._notificar_resuelto(id_pend, tipo_accion, parametros)
                if self.bitacora:
                    self.bitacora.registrar_actividad(
                        "GestorPendientes",
                        f"Pendiente #{id_pend} ({tipo_accion}) RESUELTO",
                    )
            else:
                nuevos_intentos = fila["intentos_totales"] + 1
                if nuevos_intentos >= MAX_REINTENTOS_TOTALES:
                    self.registro.marcar_pendiente_escalado(id_pend)
                    self._notificar_escalado(id_pend, tipo_accion, parametros, mensaje_error,
                                             nuevos_intentos)
                    if self.bitacora:
                        self.bitacora.registrar_error(
                            "GestorPendientes",
                            f"Pendiente #{id_pend} ({tipo_accion}) ESCALADO tras {nuevos_intentos} reintentos: {mensaje_error}",
                        )
                else:
                    self._reprogramar(id_pend, nuevos_intentos, ciclo_actual, mensaje_error)

        return procesados

    # -------------------------------------------------------------------------
    # AUXILIARES
    # -------------------------------------------------------------------------
    def _intentar(self, ejecutor: Callable, parametros: Dict[str, Any]):
        try:
            resultado = ejecutor(parametros)
            if isinstance(resultado, tuple) and len(resultado) == 2:
                return bool(resultado[0]), str(resultado[1] or "")
            return bool(resultado), ""
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _reprogramar(self, id_pendiente: int, intentos: int, ciclo_actual: int,
                     ultimo_error: str):
        proximo = ciclo_actual + INTERVALO_REINTENTO_CICLOS
        self.registro.actualizar_pendiente(id_pendiente, intentos, proximo, ultimo_error)

    def listar_escalados(self):
        return self.registro.listar_pendientes_estado("ESCALADO")

    # -------------------------------------------------------------------------
    # NOTIFICACIONES TELEGRAM
    # -------------------------------------------------------------------------
    def _notificar_resuelto(self, id_pend: int, tipo_accion: str, parametros: Dict[str, Any]):
        if not self.notificador:
            return
        symbol = parametros.get("symbol", "?")
        mensaje = f"\u2705 PROCESO #{id_pend} RESUELTO ({tipo_accion} {symbol})"
        try:
            self.notificador.enviar_mensaje(mensaje)
        except Exception:
            pass

    def _notificar_escalado(self, id_pend: int, tipo_accion: str, parametros: Dict[str, Any],
                            ultimo_error: str, intentos: int):
        if not self.notificador:
            return
        symbol = parametros.get("symbol", "?")
        mensaje = (
            f"\U0001f6a8\U0001f6a8 CR\u00cdTICO #{id_pend} ESCALADO\n"
            f"Acci\u00f3n: {tipo_accion}    S\u00edmbolo: {symbol}\n"
            f"Intentos totales: {intentos}/{MAX_REINTENTOS_TOTALES}\n"
            f"\u00daltimo error: {ultimo_error}\n"
            f"Requiere intervenci\u00f3n manual."
        )
        try:
            self.notificador.enviar_mensaje(mensaje)
        except Exception:
            pass
