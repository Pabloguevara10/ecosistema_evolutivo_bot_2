# =============================================================================
# NOMBRE: manejador_errores.py
# UBICACION: /dep_salud/
# OBJETIVO: Decorador universal @con_bitacora para normalizar el manejo de
# excepciones en todo el codigo. Captura, clasifica y delega a BitacoraCentral.
# =============================================================================

import functools
import traceback
from typing import Optional, Callable, Any

try:
    from binance.exceptions import BinanceAPIException
except Exception:  # pragma: no cover - permitir tests sin la libreria
    BinanceAPIException = type("BinanceAPIException", (Exception,), {})


def con_bitacora(modulo: str, retorno_en_fallo: Any = None,
                 reraise: bool = False, bitacora_attr: str = "bitacora"):
    """
    Decorador para metodos de instancia: captura excepciones y las registra
    en self.bitacora (o el atributo indicado por `bitacora_attr`).

    Parametros:
      - modulo: nombre del modulo a usar en el log.
      - retorno_en_fallo: valor que se retorna si la funcion lanza excepcion.
      - reraise: si True, vuelve a lanzar la excepcion despues de loguear.
      - bitacora_attr: nombre del atributo que apunta a la BitacoraCentral.
    """

    def decorador(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except BinanceAPIException as e:
                _registrar(self, bitacora_attr, modulo, func.__name__, e,
                           tipo="API_BINANCE")
                if reraise:
                    raise
                return retorno_en_fallo
            except ConnectionError as e:
                _registrar(self, bitacora_attr, modulo, func.__name__, e,
                           tipo="CONEXION")
                if reraise:
                    raise
                return retorno_en_fallo
            except Exception as e:
                _registrar(self, bitacora_attr, modulo, func.__name__, e,
                           tipo="GENERAL")
                if reraise:
                    raise
                return retorno_en_fallo

        return wrapper

    return decorador


def _registrar(instancia, bitacora_attr: str, modulo: str, funcion: str,
               excepcion: Exception, tipo: str):
    bitacora = getattr(instancia, bitacora_attr, None)
    detalle = f"[{tipo}] {funcion}() -> {type(excepcion).__name__}: {excepcion}"
    if bitacora is not None:
        try:
            bitacora.registrar_error(modulo, detalle)
        except Exception:
            # Si la bitacora misma falla, no propagamos
            pass
    else:
        # Fallback minimo si no hay bitacora disponible
        print(f"[ERROR-NO-BITACORA] {modulo} | {detalle}")
