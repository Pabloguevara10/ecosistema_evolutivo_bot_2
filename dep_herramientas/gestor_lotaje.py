# Módulo: gestor_lotaje.py - Pertenece a dep_herramientas
class GestorLotaje:
    @staticmethod
    def calcular_cantidad(balance_usdt: float, pct_capital_por_trade: float, apalancamiento: int, precio_entrada: float, step_size_precision: int = 1) -> float:
        """
        Devuelve el tamaño exacto de la orden a colocar en Binance.
        Ej: Balance $1000, pct=0.05 (5%), Apalancamiento=5x. 
        Inversión real = $50. Poder de compra = $250.
        """
        if balance_usdt <= 0 or precio_entrada <= 0:
            print("⚠️ [Gestor Lotaje] Balance o precio inválido. Orden abortada.")
            return 0.0
            
        poder_adquisitivo = (balance_usdt * pct_capital_por_trade) * apalancamiento
        cantidad_monedas = poder_adquisitivo / precio_entrada
        
        # Recortar decimales para que Binance no rechace la orden por "Invalid QTY"
        formato = f"{{:.{step_size_precision}f}}"
        cantidad_final = float(formato.format(cantidad_monedas))
        
        return cantidad_final

if __name__ == "__main__":
    print("Módulo Gestor de Lotaje Compilado.")