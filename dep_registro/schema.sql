-- =============================================================================
-- SCHEMA: posiciones_YYYY_MM.db
-- UBICACION: /registro/
-- OBJETIVO: Fuente de verdad transaccional local. Pilar 1 del bot.
-- Compatible con SQLite >= 3.24
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- =============================================================================
-- TABLA: posiciones
-- Estado de cada posicion abierta o cerrada en el exchange.
-- =============================================================================
CREATE TABLE IF NOT EXISTS posiciones (
    id_local            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_posicion_binance TEXT,
    symbol              TEXT NOT NULL,
    direccion           TEXT NOT NULL CHECK (direccion IN ('LONG', 'SHORT')),
    precio_entrada      REAL NOT NULL,
    cantidad            REAL NOT NULL,
    estado              TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'ACTIVA', 'CERRADA', 'CANCELADA')),
    timestamp_apertura  TEXT NOT NULL,
    timestamp_cierre    TEXT,
    estrategia_origen   TEXT,
    pnl_realizado       REAL
);

CREATE INDEX IF NOT EXISTS idx_pos_symbol ON posiciones(symbol);
CREATE INDEX IF NOT EXISTS idx_pos_estado ON posiciones(estado);
CREATE INDEX IF NOT EXISTS idx_pos_id_binance ON posiciones(id_posicion_binance);

-- =============================================================================
-- TABLA: ordenes
-- Ordenes individuales de entrada, SL y TP. Una posicion tiene N ordenes.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ordenes (
    id_local          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_orden_binance  TEXT,
    id_posicion_local INTEGER,
    tipo              TEXT NOT NULL CHECK (tipo IN ('ENTRADA', 'SL', 'TP', 'CIERRE')),
    symbol            TEXT NOT NULL,
    side              TEXT NOT NULL,
    position_side     TEXT NOT NULL,
    precio            REAL,
    cantidad          REAL NOT NULL,
    estado            TEXT NOT NULL CHECK (estado IN ('NUEVA', 'ACEPTADA', 'LLENADA', 'CANCELADA', 'RECHAZADA', 'PENDIENTE')),
    timestamp         TEXT NOT NULL,
    FOREIGN KEY (id_posicion_local) REFERENCES posiciones(id_local) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ord_symbol ON ordenes(symbol);
CREATE INDEX IF NOT EXISTS idx_ord_estado ON ordenes(estado);
CREATE INDEX IF NOT EXISTS idx_ord_id_binance ON ordenes(id_orden_binance);
CREATE INDEX IF NOT EXISTS idx_ord_pos_local ON ordenes(id_posicion_local);

-- =============================================================================
-- TABLA: procesos_pendientes
-- Acciones que fallaron 3 veces y deben reintentarse posteriormente.
-- =============================================================================
CREATE TABLE IF NOT EXISTS procesos_pendientes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_accion             TEXT NOT NULL,
    parametros_json         TEXT NOT NULL,
    intentos_totales        INTEGER NOT NULL DEFAULT 0,
    proximo_reintento_ciclo INTEGER NOT NULL DEFAULT 0,
    estado                  TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'RESUELTO', 'ESCALADO', 'ABORTADO')),
    timestamp_creacion      TEXT NOT NULL,
    timestamp_resolucion    TEXT,
    ultimo_error            TEXT
);

CREATE INDEX IF NOT EXISTS idx_pend_estado ON procesos_pendientes(estado);
CREATE INDEX IF NOT EXISTS idx_pend_proximo ON procesos_pendientes(proximo_reintento_ciclo);

-- =============================================================================
-- TABLA: snapshot_cuenta
-- Cache del balance y equity. Refrescado cada 120s.
-- =============================================================================
CREATE TABLE IF NOT EXISTS snapshot_cuenta (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    balance_usdt    REAL NOT NULL,
    equity          REAL,
    pnl_flotante    REAL
);

CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshot_cuenta(timestamp);
