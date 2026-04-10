# =============================================================================
# DEPARTAMENTO: dep_registro
# OBJETIVO: Fuente de verdad transaccional local (Pilar 1).
# Independiente de dep_salud (telemetria) y dep_ejecucion (acciones).
# =============================================================================

from .gestor_registro_sqlite import GestorRegistro
from .gestor_pendientes import GestorPendientes

__all__ = ["GestorRegistro", "GestorPendientes"]
