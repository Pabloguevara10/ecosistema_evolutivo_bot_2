# CONTEXTO DEL PROYECTO — Ecosistema Evolutivo Bot

> Este archivo documenta las decisiones de arquitectura, los pilares de desarrollo y los protocolos acordados para la evolución del bot. Debe ser leído antes de realizar cualquier modificación al código.

---

## 1. Descripción General del Ecosistema

El ecosistema funciona como un fondo de inversión automatizado. La información fluye en una sola dirección:

```
Mercado → Analista → Gestor de Riesgo → Ejecutor → Orquestador
```

El sistema opera en Binance en **Hedge Mode (Modo Cobertura)** y está compuesto por los siguientes departamentos:

| Departamento | Rol |
|---|---|
| `dep_analisis/` | El Cerebro — indicadores técnicos y señales |
| `dep_ejecucion/` | La Aduana y el Brazo Armado — presupuesto y órdenes |
| `dep_control/` | El Guardaespaldas — custodia de posiciones abiertas |
| `dep_salud/` | Caja Negra y Telemetría — logs y monitoreo |
| `dep_herramientas/` | Utilidades — Telegram, fractales, calculadoras |
| `dep_desarrollo/` | Laboratorio — backtesting y optimización genética |

---

## 2. Pilares de Desarrollo (Reglas Inmutables)

Estos tres pilares son **no negociables** y deben estar presentes en cada módulo que interactúe con Binance o gestione posiciones.

---

### PILAR 1 — Registro Físico como Fuente de Verdad Local

**Problema que resuelve:** El bot no puede depender exclusivamente de Binance para conocer el estado de sus posiciones y órdenes. Una desconexión momentánea no debe paralizar la operación.

**Solución:**
- Existe un archivo de registro local en formato **SQLite** que se mantiene sincronizado con el estado real del exchange.
- Cualquier módulo del bot consulta primero el registro local, no Binance.
- Las consultas a Binance se reducen a un rol de **validación periódica** (cada 1 a 3 minutos), no de fuente primaria en tiempo real.
- Esto libera ancho de banda de la API para otras operaciones sin riesgo de saturación.

**Especificaciones técnicas:**
- **Formato:** SQLite (`.db`) — garantiza integridad transaccional. Si el proceso se interrumpe a mitad de una escritura, el archivo no queda corrupto. Múltiples hilos pueden consultarlo simultáneamente sin colisión.
- **Rotación:** Un archivo por mes. Nomenclatura: `posiciones_YYYY_MM.db`
- **Ubicación sugerida:** `/registro/` en la raíz del proyecto (generada automáticamente).
- **Contenido mínimo del registro:** ID de posición, símbolo, dirección (LONG/SHORT), precio de entrada, tamaño, ID de orden SL activo, ID de orden TP activo, estado (activa/cerrada/pendiente), timestamp de apertura, timestamp de cierre, estrategia origen (MTF/VIP).

---

### PILAR 2 — Protocolo Universal: Ejecutar → Verificar → Registrar

**Problema que resuelve:** Ninguna interacción con Binance se puede dar por exitosa sin confirmación explícita. Una orden que "se envió" no es una orden que "fue aceptada".

**Regla:**
```
PASO 1: Enviar la orden a Binance
PASO 2: Confirmar respuesta positiva de Binance (orden aceptada)
PASO 3: Registrar en el archivo SQLite local
```

Este orden es **estricto e inviolable**. Nunca se registra algo que no fue confirmado. Nunca se elimina una orden antigua sin haber registrado la nueva.

**Protocolo de reintentos (aplica a cada paso individualmente):**

| Intento | Espera previa |
|---|---|
| 1° intento | inmediato |
| 2° intento | 1 segundo |
| 3° intento | 3 segundos |
| 4° intento | 9 segundos |

- Si el 3° reintento falla: el proceso se marca como **PENDIENTE** mediante una variable lógica.
- El bot **continúa operando** normalmente. No se detiene.
- El proceso pendiente se reactiva automáticamente después de un número determinado de ciclos o un intervalo de tiempo configurable.
- Se notifica por **Telegram** inmediatamente al marcar como pendiente.
- Se notifica por **Telegram** nuevamente cuando el proceso pendiente se resuelve exitosamente (o falla definitivamente).

**Alcance:** Este protocolo aplica a **TODA** interacción con Binance, incluyendo:
- Apertura de posiciones
- Colocación de SL y TP
- Modificación de órdenes (cancelar + reemplazar)
- Cierre de posiciones
- Cualquier consulta que requiera acción posterior

---

### PILAR 3 — Protocolo de Modificación de Órdenes sin Exposición

**Problema que resuelve:** Al modificar un Stop Loss (especialmente al activar Break Even o Trailing Stop), existe el riesgo de cancelar el SL existente antes de confirmar que el nuevo fue aceptado, dejando la posición sin protección.

**Regla para modificación de SL (y cualquier orden de protección):**

```
PASO 1: Colocar el NUEVO Stop Loss en Binance
PASO 2: Confirmar que Binance aceptó el nuevo SL (con reintentos si es necesario)
PASO 3: Registrar el nuevo SL en el archivo SQLite local
PASO 4: Solicitar cancelación del SL ANTERIOR en Binance
PASO 5: Confirmar cancelación del SL anterior
PASO 6: Actualizar el registro SQLite (marcar SL anterior como cancelado)
```

**Principio:** La posición siempre tiene **al menos un SL activo** en el exchange en todo momento. Nunca se cancela el anterior sin haber confirmado el nuevo.

Este mismo protocolo aplica para modificaciones de TP y para cualquier otra orden de protección que deba ser reemplazada.

---

## 3. Decisiones Técnicas Acordadas

| Decisión | Valor elegido | Razón |
|---|---|---|
| Formato de registro | SQLite | Integridad transaccional, acceso concurrente seguro |
| Rotación de registros | Mensual | Archivos manejables, histórico organizado |
| Nomenclatura | `posiciones_YYYY_MM.db` | Consistente con el sistema de logs existente |
| Reintentos | Progresivos: 1s → 3s → 9s | Balance entre velocidad y no saturar la API |
| Notificación Telegram | Al fallo (3° intento) y al resolver | Visibilidad completa del inicio y fin de incidencias |
| Consulta periódica a Binance | Cada 1 a 3 minutos | Solo validación, no fuente primaria |
| Consulta operativa | Registro SQLite local | Fuente primaria de verdad |

---

## 4. Metodología de Trabajo con Claude

**Regla principal:** Precisión sobre velocidad. No se improvisa nada.

**Flujo acordado:**
1. Claude realiza un **análisis completo y profundo** del repositorio antes de proponer ningún cambio.
2. Claude presenta el análisis y espera confirmación explícita de que tiene pleno control del código.
3. Solo después de esa confirmación se procede con modificaciones.
4. Cada modificación se discute antes de implementarse.
5. Claude puede y debe **hacer preguntas** ante cualquier ambigüedad.

---

## 5. Preguntas Abiertas / Pendientes de Definir

Estos puntos aún no han sido respondidos y deben aclararse antes de implementar los módulos correspondientes:

- [ ] ¿Cuántos ciclos del orquestador deben pasar antes de reintentar un proceso PENDIENTE?
- [ ] ¿Hay un número máximo de reintentos totales para un proceso PENDIENTE antes de escalarlo a alerta crítica?
- [ ] ¿El módulo de registro SQLite será un módulo independiente (`dep_registro/`) o se integrará dentro de `dep_salud/`?
- [ ] ¿Qué información mínima debe aparecer en la notificación de Telegram cuando un proceso queda PENDIENTE?

---

## 6. Estructura Actual del Repositorio

```
ecosistema_evolutivo_bot/
├── 📄 main_orquestador.py          ← Director de Orquesta (bucle principal)
├── 📄 dashboard_sentinel.py        ← Interfaz Gráfica UI
├── 📄 .env                         ← Credenciales API y Telegram (NO versionar)
│
├── 📁 dep_analisis/                ← El Cerebro
│   ├── monitor_mercado.py
│   ├── comparador_estrategias.py
│   ├── estrategia_piramide_mtf.py
│   └── emisor_señales.py
│
├── 📁 dep_control/                 ← El Guardaespaldas
│   ├── monitor_posiciones.py
│   ├── trailing_stop_dinamico.py
│   ├── estadistico_operativo.py
│   └── liberador_cupos.py
│
├── 📁 dep_ejecucion/               ← La Aduana y El Brazo Armado
│   ├── evaluador_entradas.py
│   ├── gestor_cupos.py
│   ├── disparador_binance.py
│   └── asegurador_posicion.py
│
├── 📁 dep_salud/                   ← Monitoreo y Registros
│   ├── bitacora_central.py
│   ├── monitor_recursos.py
│   ├── auditor_red.py
│   └── reporte_diagnostico.py
│
├── 📁 dep_herramientas/            ← Utilidades y Comunicaciones
│   ├── controlador_telegram.py
│   ├── StructureScanner_2.py
│   └── calculadoras_indicadores.py
│
├── 📁 dep_desarrollo/              ← Laboratorio y Backtesting
│   ├── motor_evolutivo.py
│   ├── certificador_estrategias.py
│   └── 📁 bbdd_estrategias/
│
└── 📁 logs/                        ← Generado automáticamente
    ├── 📁 actividad/
    ├── 📁 operaciones/
    └── 📁 salud/
```

---

*Documento generado como contexto de desarrollo. Actualizar conforme se tomen nuevas decisiones.*