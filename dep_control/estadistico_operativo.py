# Módulo: estadistico_operativo.py - Pertenece a dep_control
import os
import pandas as pd
from datetime import datetime

class EstadisticoOperativo:
    def __init__(self):
        self.archivo_logs = os.path.join("dep_control", "registro_operaciones.csv")
        # Asegurar directorio
        os.makedirs(os.path.dirname(self.archivo_logs), exist_ok=True)
        self._inicializar_archivo()

    def _inicializar_archivo(self):
        if not os.path.exists(self.archivo_logs):
            df = pd.DataFrame(columns=['Fecha', 'Activo', 'Lado', 'Precio_Entrada', 'Precio_Salida', 'PNL_USDT', 'Estrategia_ID'])
            df.to_csv(self.archivo_logs, index=False)

    def registrar_trade_cerrado(self, symbol, side, entry_price, exit_price, pnl, id_estrategia):
        nuevo_registro = pd.DataFrame([{
            'Fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Activo': symbol,
            'Lado': side,
            'Precio_Entrada': entry_price,
            'Precio_Salida': exit_price,
            'PNL_USDT': round(pnl, 4),
            'Estrategia_ID': id_estrategia
        }])
        
        nuevo_registro.to_csv(self.archivo_logs, mode='a', header=False, index=False)
        print(f"📊 [Estadística] Trade cerrado registrado. PNL: {pnl} USDT.")