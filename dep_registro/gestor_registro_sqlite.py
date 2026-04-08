# =============================================================================
# NOMBRE: gestor_registro_sqlite.py
# UBICACION: /dep_registro/
# OBJETIVO: Fuente de verdad transaccional local (Pilar 1).
# Rotacion mensual: posiciones_YYYY_MM.db
# =============================================================================

import os
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any


class GestorRegistro:
    """
    Gestor unico de la base SQLite local. Punto de entrada para:
      - posiciones (ACTIVA / CERRADA / PENDIENTE)
      - ordenes (ENTRADA / SL / TP / CIERRE)
      - procesos_pendientes (Pilar 2)
      - snapshot_cuenta (cache balance/equity)

    Cada instancia mantiene una sola conexion compartida con check_same_thread=False.
    Las escrituras estan serializadas con un Lock para garantizar atomicidad.
    """

    def __init__(self, directorio_registro: Optional[str] = None):
        if directorio_registro is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            directorio_registro = os.path.join(project_root, "registro")
        os.makedirs(directorio_registro, exist_ok=True)
        self.directorio = directorio_registro

        self._lock = threading.RLock()
        self._mes_actual = self._mes_string()
        self._ruta_db = self._ruta_para_mes(self._mes_actual)
        self._conexion = self._abrir_conexion(self._ruta_db)
        self._aplicar_schema()

    # -------------------------------------------------------------------------
    # INFRAESTRUCTURA INTERNA
    # -------------------------------------------------------------------------
    def _mes_string(self) -> str:
        return datetime.now().strftime("%Y_%m")

    def _ruta_para_mes(self, mes: str) -> str:
        return os.path.join(self.directorio, f"posiciones_{mes}.db")

    def _abrir_conexion(self, ruta: str) -> sqlite3.Connection:
        conn = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _aplicar_schema(self):
        ruta_schema = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        with open(ruta_schema, "r", encoding="utf-8") as f:
            sql = f.read()
        with self._lock:
            self._conexion.executescript(sql)

    def _verificar_rotacion(self):
        """Si cambio el mes, abre una DB nueva y cierra la anterior."""
        mes_ahora = self._mes_string()
        if mes_ahora != self._mes_actual:
            with self._lock:
                try:
                    self._conexion.close()
                except Exception:
                    pass
                self._mes_actual = mes_ahora
                self._ruta_db = self._ruta_para_mes(mes_ahora)
                self._conexion = self._abrir_conexion(self._ruta_db)
                self._aplicar_schema()

    def _now_iso(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def cerrar(self):
        with self._lock:
            try:
                self._conexion.close()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # POSICIONES
    # -------------------------------------------------------------------------
    def crear_posicion(
        self,
        symbol: str,
        direccion: str,
        precio_entrada: float,
        cantidad: float,
        estrategia_origen: str = "",
        id_posicion_binance: Optional[str] = None,
        estado: str = "PENDIENTE",
    ) -> int:
        """Inserta una posicion nueva. Retorna id_local."""
        self._verificar_rotacion()
        with self._lock:
            cur = self._conexion.execute(
                """
                INSERT INTO posiciones
                    (id_posicion_binance, symbol, direccion, precio_entrada, cantidad,
                     estado, timestamp_apertura, estrategia_origen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id_posicion_binance,
                    symbol,
                    direccion,
                    float(precio_entrada),
                    float(cantidad),
                    estado,
                    self._now_iso(),
                    estrategia_origen,
                ),
            )
            return cur.lastrowid

    def marcar_posicion_activa(self, id_local: int, id_posicion_binance: Optional[str] = None):
        self._verificar_rotacion()
        with self._lock:
            if id_posicion_binance is not None:
                self._conexion.execute(
                    "UPDATE posiciones SET estado = 'ACTIVA', id_posicion_binance = ? WHERE id_local = ?",
                    (id_posicion_binance, id_local),
                )
            else:
                self._conexion.execute(
                    "UPDATE posiciones SET estado = 'ACTIVA' WHERE id_local = ?",
                    (id_local,),
                )

    def cerrar_posicion(self, id_local: int, pnl_realizado: Optional[float] = None):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                """
                UPDATE posiciones
                   SET estado = 'CERRADA', timestamp_cierre = ?, pnl_realizado = COALESCE(?, pnl_realizado)
                 WHERE id_local = ?
                """,
                (self._now_iso(), pnl_realizado, id_local),
            )

    def obtener_posicion(self, id_local: int) -> Optional[Dict[str, Any]]:
        self._verificar_rotacion()
        with self._lock:
            row = self._conexion.execute(
                "SELECT * FROM posiciones WHERE id_local = ?", (id_local,)
            ).fetchone()
        return dict(row) if row else None

    def obtener_posiciones_abiertas(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lectura primaria del bot. Reemplaza futures_position_information() en el caliente."""
        self._verificar_rotacion()
        with self._lock:
            if symbol:
                rows = self._conexion.execute(
                    "SELECT * FROM posiciones WHERE estado = 'ACTIVA' AND symbol = ?",
                    (symbol,),
                ).fetchall()
            else:
                rows = self._conexion.execute(
                    "SELECT * FROM posiciones WHERE estado = 'ACTIVA'"
                ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # ORDENES
    # -------------------------------------------------------------------------
    def registrar_orden(
        self,
        tipo: str,
        symbol: str,
        side: str,
        position_side: str,
        cantidad: float,
        precio: Optional[float] = None,
        id_orden_binance: Optional[str] = None,
        id_posicion_local: Optional[int] = None,
        estado: str = "ACEPTADA",
    ) -> int:
        self._verificar_rotacion()
        with self._lock:
            cur = self._conexion.execute(
                """
                INSERT INTO ordenes
                    (id_orden_binance, id_posicion_local, tipo, symbol, side, position_side,
                     precio, cantidad, estado, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(id_orden_binance) if id_orden_binance is not None else None,
                    id_posicion_local,
                    tipo,
                    symbol,
                    side,
                    position_side,
                    precio,
                    float(cantidad),
                    estado,
                    self._now_iso(),
                ),
            )
            return cur.lastrowid

    def actualizar_estado_orden(self, id_local: int, estado: str):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                "UPDATE ordenes SET estado = ? WHERE id_local = ?",
                (estado, id_local),
            )

    def cancelar_orden(self, id_local: int):
        self.actualizar_estado_orden(id_local, "CANCELADA")

    def obtener_ordenes_activas(self, id_posicion_local: int) -> List[Dict[str, Any]]:
        self._verificar_rotacion()
        with self._lock:
            rows = self._conexion.execute(
                """
                SELECT * FROM ordenes
                 WHERE id_posicion_local = ?
                   AND estado IN ('NUEVA', 'ACEPTADA')
                """,
                (id_posicion_local,),
            ).fetchall()
        return [dict(r) for r in rows]

    def obtener_ordenes_proteccion(self, symbol: str, position_side: str, tipo: str) -> List[Dict[str, Any]]:
        """Devuelve SL o TP activos para un symbol/position_side."""
        self._verificar_rotacion()
        with self._lock:
            rows = self._conexion.execute(
                """
                SELECT * FROM ordenes
                 WHERE symbol = ? AND position_side = ? AND tipo = ?
                   AND estado IN ('NUEVA', 'ACEPTADA')
                """,
                (symbol, position_side, tipo),
            ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # PROCESOS PENDIENTES (Pilar 2)
    # -------------------------------------------------------------------------
    def crear_pendiente(
        self,
        tipo_accion: str,
        parametros: Dict[str, Any],
        intentos_iniciales: int,
        proximo_reintento_ciclo: int,
        ultimo_error: str = "",
    ) -> int:
        self._verificar_rotacion()
        with self._lock:
            cur = self._conexion.execute(
                """
                INSERT INTO procesos_pendientes
                    (tipo_accion, parametros_json, intentos_totales, proximo_reintento_ciclo,
                     estado, timestamp_creacion, ultimo_error)
                VALUES (?, ?, ?, ?, 'PENDIENTE', ?, ?)
                """,
                (
                    tipo_accion,
                    json.dumps(parametros, default=str),
                    int(intentos_iniciales),
                    int(proximo_reintento_ciclo),
                    self._now_iso(),
                    ultimo_error,
                ),
            )
            return cur.lastrowid

    def listar_pendientes_listos(self, ciclo_actual: int) -> List[Dict[str, Any]]:
        self._verificar_rotacion()
        with self._lock:
            rows = self._conexion.execute(
                """
                SELECT * FROM procesos_pendientes
                 WHERE estado = 'PENDIENTE' AND proximo_reintento_ciclo <= ?
                """,
                (int(ciclo_actual),),
            ).fetchall()
        return [dict(r) for r in rows]

    def listar_pendientes_estado(self, estado: str) -> List[Dict[str, Any]]:
        self._verificar_rotacion()
        with self._lock:
            rows = self._conexion.execute(
                "SELECT * FROM procesos_pendientes WHERE estado = ?", (estado,)
            ).fetchall()
        return [dict(r) for r in rows]

    def actualizar_pendiente(
        self,
        id_pendiente: int,
        intentos_totales: int,
        proximo_reintento_ciclo: int,
        ultimo_error: str = "",
    ):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                """
                UPDATE procesos_pendientes
                   SET intentos_totales = ?, proximo_reintento_ciclo = ?, ultimo_error = ?
                 WHERE id = ?
                """,
                (int(intentos_totales), int(proximo_reintento_ciclo), ultimo_error, id_pendiente),
            )

    def marcar_pendiente_resuelto(self, id_pendiente: int):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                """
                UPDATE procesos_pendientes
                   SET estado = 'RESUELTO', timestamp_resolucion = ?
                 WHERE id = ?
                """,
                (self._now_iso(), id_pendiente),
            )

    def marcar_pendiente_escalado(self, id_pendiente: int):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                """
                UPDATE procesos_pendientes
                   SET estado = 'ESCALADO', timestamp_resolucion = ?
                 WHERE id = ?
                """,
                (self._now_iso(), id_pendiente),
            )

    # -------------------------------------------------------------------------
    # SNAPSHOT CUENTA (cache de balance)
    # -------------------------------------------------------------------------
    def guardar_snapshot_cuenta(self, balance_usdt: float, equity: Optional[float] = None,
                                 pnl_flotante: Optional[float] = None):
        self._verificar_rotacion()
        with self._lock:
            self._conexion.execute(
                """
                INSERT INTO snapshot_cuenta (timestamp, balance_usdt, equity, pnl_flotante)
                VALUES (?, ?, ?, ?)
                """,
                (self._now_iso(), float(balance_usdt), equity, pnl_flotante),
            )

    def obtener_ultimo_snapshot(self) -> Optional[Dict[str, Any]]:
        self._verificar_rotacion()
        with self._lock:
            row = self._conexion.execute(
                "SELECT * FROM snapshot_cuenta ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
