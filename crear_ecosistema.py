import os

def construir_ecosistema():
    # Estructura de carpetas limpia y compatible con Python
    directorios = [
        "data_historica/AAVEUSDT",
        "dep_adecuacion",
        "dep_desarrollo/bbdd_estrategias",
        "dep_herramientas",
        "dep_analisis",
        "dep_ejecucion",
        "dep_control"
    ]

    # Diccionario de módulos por departamento
    archivos_iniciales = {
        "dep_adecuacion": ["inicializador_sistema.py", "conexion_exchange.py", "sincronizador_tiempo.py"],
        "dep_desarrollo": ["motor_evolutivo.py", "backtest_aislado.py", "certificador_estrategias.py", "generador_reportes.py"],
        "dep_herramientas": ["generador_data.py", "resampler_data.py", "calculadoras_indicadores.py", "gestor_lotaje.py", "certificador_ordenes.py"],
        "dep_analisis": ["monitor_mercado.py", "comparador_estrategias.py", "emisor_señales.py"],
        "dep_ejecucion": ["evaluador_entradas.py", "disparador_binance.py", "gestor_cupos.py", "asegurador_posicion.py"],
        "dep_control": ["monitor_posiciones.py", "trailing_stop_dinamico.py", "liberador_cupos.py", "estadistico_operativo.py"]
    }

    print("Iniciando construcción del ecosistema modular (Nombres Limpios)...")

    # Crear directorios y archivos __init__.py para hacerlos paquetes de Python
    for directorio in directorios:
        os.makedirs(directorio, exist_ok=True)
        print(f"📁 Directorio verificado: {directorio}")
        
        # Ignorar la creación de __init__.py en la carpeta de datos
        if "data_historica" not in directorio:
            init_file = os.path.join(directorio, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w", encoding="utf-8") as f:
                    f.write(f"# Paquete inicializado: {directorio}\n")

    # Crear archivo main orquestador
    if not os.path.exists("main_orquestador.py"):
        with open("main_orquestador.py", "w", encoding="utf-8") as f:
            f.write("# Archivo central. Hilos y procesos asíncronos (Dormido hasta Fase 3)\n")
    
    # Inyectar archivos dormidos en cada departamento
    for dep, archivos in archivos_iniciales.items():
        for archivo in archivos:
            ruta = os.path.join(dep, archivo)
            if not os.path.exists(ruta):
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(f"# Módulo: {archivo} - Pertenece a {dep}\n")
                print(f"📄 Archivo creado: {ruta}")

    print("\n✅ Ecosistema construido con éxito. Estructura compatible con importaciones de Python.")

if __name__ == "__main__":
    construir_ecosistema()