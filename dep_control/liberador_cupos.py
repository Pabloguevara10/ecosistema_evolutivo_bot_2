# Módulo: liberador_cupos.py - Pertenece a dep_control
class LiberadorCupos:
    def __init__(self, gestor_cupos, telegram=None):
        self.gestor_cupos = gestor_cupos
        self.telegram = telegram
        
    def auditar_y_liberar(self, posiciones_vivas_exchange):
        """
        Verifica si alguna de las órdenes registradas internamente ya desapareció 
        del Exchange (fue liquidada por SL o TP).
        """
        # Extraemos los precios de entrada de las órdenes que actualmente están en Binance
        precios_vivos = [pos['entry_price'] for pos in posiciones_vivas_exchange]
        
        ordenes_cerradas = []
        
        for orden_interna in self.gestor_cupos.posiciones_activas:
            precio_interno = orden_interna['entry_price']
            
            # Chequeamos si el precio de la orden interna sigue existiendo en el exchange
            # (Se usa un margen de 0.001 para tolerar leves redondeos de punto flotante)
            sigue_viva = any(abs(p - precio_interno) < 0.001 for p in precios_vivos)
            
            if not sigue_viva:
                ordenes_cerradas.append(orden_interna)
                
        # Proceso de liberación
        for orden in ordenes_cerradas:
            id_orden = orden['id']
            precio = orden['entry_price']
            
            self.gestor_cupos.liberar_cupo(id_orden)
            
            espacios = self.gestor_cupos.max_ordenes - len(self.gestor_cupos.posiciones_activas)
            mensaje = f"🔓 <b>CUPO LIBERADO</b>\nLa posición en {precio} se ha cerrado en el Exchange.\nEspacios disponibles: {espacios}"
            
            print(f"✅ [Liberador] {mensaje.replace('<b>', '').replace('</b>', '')}")
            
            if self.telegram:
                self.telegram.enviar_mensaje(mensaje)

if __name__ == "__main__":
    print("Módulo Liberador de Cupos Compilado.")