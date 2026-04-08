# =============================================================================
# NOMBRE: reporte_diagnostico.py
# UBICACIÓN: /dep_salud/
# OBJETIVO: Consolidar la telemetría y generar un archivo de salud diario.
# =============================================================================

import os
import json
import time
from datetime import datetime

class ReporteDiagnostico:
    def __init__(self, monitor_recursos, bitacora):
        self.monitor = monitor_recursos
        self.bitacora = bitacora
        
        # Marcador de tiempo para calcular Uptime
        self.tiempo_arranque = time.time()
        self.ultimo_reporte_dia = None
        
        # Crear subcarpeta para reportes de salud
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.dir_reportes = os.path.join(project_root, "logs", "diagnosticos_salud")
        os.makedirs(self.dir_reportes, exist_ok=True)

    def generar_reporte(self):
        """
        Crea un snapshot (foto) de cómo está el sistema en este instante.
        """
        uptime_segundos = time.time() - self.tiempo_arranque
        horas_activas = round(uptime_segundos / 3600, 2)
        
        stats_hw = self.monitor.chequear_salud_hardware()
        
        fecha_actual = datetime.now()
        
        reporte = {
            "timestamp": fecha_actual.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_horas": horas_activas,
            "estado_general": "OPTIMO" if stats_hw["hardware_seguro"] else "EN RIESGO",
            "telemetria_hardware": stats_hw
        }
        
        # Guardamos un archivo por día
        nombre_archivo = f"salud_{fecha_actual.strftime('%Y-%m-%d')}.json"
        ruta_completa = os.path.join(self.dir_reportes, nombre_archivo)
        
        # Si el archivo ya existe, leemos lo que tiene y le agregamos el nuevo reporte (Historial)
        historial = []
        if os.path.exists(ruta_completa):
            try:
                with open(ruta_completa, 'r') as f:
                    historial = json.load(f)
            except:
                pass
                
        historial.append(reporte)
        
        with open(ruta_completa, 'w') as f:
            json.dump(historial, f, indent=4)
            
        self.bitacora.info(f"📊 [DIAGNÓSTICO] Reporte de salud guardado. Uptime: {horas_activas} hrs | RAM Bot: {stats_hw['ram_bot_mb']} MB")
        self.ultimo_reporte_dia = fecha_actual.day

    def chequear_corte_diario(self):
        """
        Verifica si ya es necesario generar el reporte. 
        Ideal para llamarlo cada 1 hora o al cambiar de día.
        """
        dia_actual = datetime.now().day
        if self.ultimo_reporte_dia != dia_actual:
            self.generar_reporte()