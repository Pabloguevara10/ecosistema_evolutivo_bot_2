# Módulo: generador_reportes.py - Pertenece a dep_desarrollo
import os
import json
import pandas as pd
from datetime import datetime

class GeneradorReportes:
    def __init__(self):
        self.ruta_db_estrategias = os.path.join("dep_desarrollo", "bbdd_estrategias", "estrategias_aprobadas.json")
        self.directorio_salida = os.path.join("dep_desarrollo", "reportes_exportados")
        os.makedirs(self.directorio_salida, exist_ok=True)

    def exportar_estrategias_a_csv(self):
        if not os.path.exists(self.ruta_db_estrategias):
            print("⚠️ No hay base de datos de estrategias para exportar.")
            return False

        with open(self.ruta_db_estrategias, 'r') as file:
            try:
                estrategias = json.load(file)
            except json.JSONDecodeError:
                print("❌ Error leyendo el archivo JSON de estrategias.")
                return False

        if not estrategias:
            print("⚠️ La base de datos está vacía. El motor evolutivo aún no ha aprobado ninguna estrategia.")
            return False

        lista_plana = []
        for est in estrategias:
            # Aplanar el diccionario para que encaje perfectamente en columnas de CSV
            fila = {
                "ID_Estrategia": est.get("id_estrategia"),
                "Fecha_Aprobacion": est.get("fecha_aprobacion"),
                "Activo": est.get("activo"),
                
                # Extraer ADN
                "RSI_Periodo": est.get("parametros", {}).get("rsi_period"),
                "RSI_Oversold": est.get("parametros", {}).get("rsi_oversold"),
                "RSI_Overbought": est.get("parametros", {}).get("rsi_overbought"),
                "StopLoss_Pct": est.get("parametros", {}).get("sl_pct"),
                "TakeProfit_Pct": est.get("parametros", {}).get("tp_pct"),
                "Apalancamiento": est.get("parametros", {}).get("leverage"),
                
                # Extraer Métricas
                "Total_Trades_Simulados": est.get("metricas_certificacion", {}).get("total_trades_base"),
                "Riesgo_Ruina_Pct": est.get("metricas_certificacion", {}).get("riesgo_ruina_pct"),
                "Peor_Drawdown_Esperado_Pct": est.get("metricas_certificacion", {}).get("drawdown_esperado_95_pct")
            }
            lista_plana.append(fila)

        df = pd.DataFrame(lista_plana)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"Reporte_Estrategias_Aprobadas_{timestamp}.csv"
        ruta_salida = os.path.join(self.directorio_salida, nombre_archivo)
        
        df.to_csv(ruta_salida, index=False)
        print(f"✅ Reporte exportado exitosamente para análisis humano en: {ruta_salida}")
        return True

if __name__ == "__main__":
    exportador = GeneradorReportes()
    exportador.exportar_estrategias_a_csv()