# =============================================================================
# limpiar_ordenes_duplicadas.py
# OBJETIVO: Limpieza de emergencia de ordenes SL/TP acumuladas en Binance.
#
# Problema: el bot acumulo multiples pares SL+TP para la misma posicion
# porque colocar_protecciones() no cancelaba las ordenes anteriores.
#
# Este script:
#   1. Consulta Binance para ver todas las ordenes condicionales abiertas.
#   2. Para cada posicion activa, identifica TODOS los SL y TP duplicados.
#   3. Conserva SOLO la orden mas reciente de cada tipo (el que tiene el
#      stopPrice mas beneficioso para la posicion).
#   4. Cancela el resto.
#
# USO:
#   python limpiar_ordenes_duplicadas.py              # modo preview (sin cambios)
#   python limpiar_ordenes_duplicadas.py --ejecutar   # ejecuta la limpieza
#   python limpiar_ordenes_duplicadas.py --cancelar-todo  # cancela TODAS las ordenes
# =============================================================================

import os, sys, argparse
from collections import defaultdict
from binance.client import Client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Mismas variables de entorno que usa main_orquestador.py
API_KEY    = os.environ.get("BINANCE_API_KEY_TESTNET", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET_TESTNET", "")
TESTNET    = True   # cambiar a False para produccion real
SYMBOL     = "AAVEUSDT"


def listar_ordenes_condicionales(client, symbol):
    """Retorna todas las ordenes condicionales abiertas para el symbol."""
    try:
        ordenes = client.futures_get_open_orders(symbol=symbol)
        condicionales = [
            o for o in ordenes
            if o.get("type") in ("STOP_MARKET", "TAKE_PROFIT_MARKET")
        ]
        return condicionales
    except Exception as e:
        print(f"[ERROR] No se pudieron obtener ordenes: {e}")
        return []


def agrupar_por_posicion(ordenes):
    """
    Agrupa las ordenes por (positionSide, type).
    Retorna: {(pos_side, tipo): [lista de ordenes]}
    """
    grupos = defaultdict(list)
    for o in ordenes:
        clave = (o["positionSide"], o["type"])
        grupos[clave].append(o)
    return grupos


def orden_mas_beneficiosa(ordenes_grupo, pos_side, tipo):
    """
    Para un grupo de ordenes del mismo tipo y posicion, selecciona
    la que tiene el stopPrice mas beneficioso para la posicion.

    LONG + SL:  quiere el SL mas ALTO (mayor proteccion)
    LONG + TP:  quiere el TP mas ALTO (mayor ganancia)
    SHORT + SL: quiere el SL mas BAJO (mayor proteccion)
    SHORT + TP: quiere el TP mas BAJO (mayor ganancia)
    """
    if not ordenes_grupo:
        return None

    reverse = True  # alto = mejor
    if pos_side == "SHORT" and tipo in ("STOP_MARKET", "TAKE_PROFIT_MARKET"):
        reverse = False  # bajo = mejor para SHORT

    ordenadas = sorted(
        ordenes_grupo,
        key=lambda o: float(o.get("stopPrice", 0)),
        reverse=reverse
    )
    return ordenadas[0]  # la primera es la mas beneficiosa


def main():
    parser = argparse.ArgumentParser(description="Limpieza de ordenes duplicadas en Binance")
    parser.add_argument("--ejecutar", action="store_true",
                        help="Ejecutar la limpieza (por defecto solo preview)")
    parser.add_argument("--cancelar-todo", action="store_true",
                        help="Cancelar TODAS las ordenes condicionales del symbol")
    args = parser.parse_args()

    if not API_KEY or not API_SECRET:
        print("[ERROR] Credenciales de Binance no encontradas.")
        print("  Define BINANCE_API_KEY y BINANCE_API_SECRET en el entorno o .env")
        sys.exit(1)

    print(f"\nConectando a Binance {'TESTNET' if TESTNET else 'PRODUCCION'}...")
    client = Client(API_KEY, API_SECRET, testnet=TESTNET)

    ordenes = listar_ordenes_condicionales(client, SYMBOL)
    print(f"\nOrdenes condicionales abiertas en {SYMBOL}: {len(ordenes)}")

    if not ordenes:
        print("No hay ordenes que limpiar.")
        return

    if args.cancelar_todo:
        print(f"\n{'[PREVIEW]' if not args.ejecutar else '[EJECUTANDO]'} "
              f"Cancelando TODAS las ordenes condicionales...")
        for o in ordenes:
            print(f"  Cancelando {o['type']} | side={o['positionSide']} | "
                  f"stopPrice={o['stopPrice']} | qty={o['origQty']} | id={o['orderId']}")
            if args.ejecutar:
                try:
                    client.futures_cancel_order(symbol=SYMBOL, orderId=o["orderId"])
                    print(f"    → OK")
                except Exception as e:
                    print(f"    → ERROR: {e}")
        if not args.ejecutar:
            print("\n[PREVIEW] Pasa --ejecutar para aplicar los cambios.")
        return

    # Agrupar y decidir cuales conservar
    grupos = agrupar_por_posicion(ordenes)

    print("\nAnalisis por grupo (positionSide / tipo):")
    a_cancelar = []
    a_conservar = []

    for (pos_side, tipo), grupo in sorted(grupos.items()):
        mejor = orden_mas_beneficiosa(grupo, pos_side, tipo)
        duplicados = [o for o in grupo if o["orderId"] != mejor["orderId"]]

        print(f"\n  [{pos_side}] {tipo}: {len(grupo)} orden(es)")
        print(f"    CONSERVAR (stop={mejor['stopPrice']} qty={mejor['origQty']}): "
              f"id={mejor['orderId']}")

        for d in duplicados:
            print(f"    CANCELAR  (stop={d['stopPrice']} qty={d['origQty']}): "
                  f"id={d['orderId']}")
            a_cancelar.append(d)

        a_conservar.append(mejor)

    print(f"\nResumen: conservar {len(a_conservar)} | cancelar {len(a_cancelar)}")

    if not a_cancelar:
        print("No hay duplicados que eliminar.")
        return

    if not args.ejecutar:
        print("\n[PREVIEW] Pasa --ejecutar para aplicar la limpieza.")
        return

    print("\n[EJECUTANDO] Cancelando ordenes duplicadas...")
    ok = 0
    fail = 0
    for o in a_cancelar:
        try:
            client.futures_cancel_order(symbol=SYMBOL, orderId=o["orderId"])
            print(f"  [OK] Cancelada: {o['type']} stop={o['stopPrice']} id={o['orderId']}")
            ok += 1
        except Exception as e:
            print(f"  [ERR] Fallo cancelar {o['orderId']}: {e}")
            fail += 1

    print(f"\nLimpieza completa: {ok} canceladas, {fail} fallidas.")
    if fail == 0:
        print("✔ La posicion ahora tiene exactamente 1 SL y 1 TP activos.")


if __name__ == "__main__":
    main()
