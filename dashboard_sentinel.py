# =============================================================================
# NOMBRE: dashboard_sentinel.py
# UBICACIÓN: RAÍZ DEL PROYECTO
# OBJETIVO: Separación de Responsabilidades (UI/UX). Genera la interfaz gráfica.
# =============================================================================

import sys

try:
    from rich.table import Table
    from rich.panel import Panel
    from rich.console import Group
except ImportError:
    print("❌ Faltan dependencias visuales. Ejecuta: python -m pip install rich")
    sys.exit(1)

class DashboardSentinel:
    
    @staticmethod
    def formatear_pendiente(valores, is_vol=False):
        # Manejo seguro por si la data no llega lista
        if not isinstance(valores, (list, tuple)) or len(valores) < 2:
            return str(valores)
            
        prev, act = valores[0], valores[1]
        
        if is_vol:
            if act > prev: return f"{prev/1000:.1f}k ➔ [green]{act/1000:.1f}k ▲[/green]"
            elif act < prev: return f"{prev/1000:.1f}k ➔ [red]{act/1000:.1f}k ▼[/red]"
            return f"{prev/1000:.1f}k ➔ [yellow]{act/1000:.1f}k ▶[/yellow]"

        if act > prev + 0.1: return f"{prev:.1f} ➔ [green]{act:.1f} ▲[/green]"
        elif act < prev - 0.1: return f"{prev:.1f} ➔ [red]{act:.1f} ▼[/red]"
        return f"{prev:.1f} ➔ [yellow]{act:.1f} ▶[/yellow]"

    @staticmethod
    def generar_vista(estado_ui, symbol):
        # ==========================================
        # 0. ENCABEZADO (KPIs Principales)
        # ==========================================
        grid_kpi = Table.grid(expand=True)
        for _ in range(5):
            grid_kpi.add_column(justify="center")
        
        precio_actual = estado_ui.get('precio_actual', 0.0)
        balance = estado_ui.get('balance_actual', 0.0)
        estado = estado_ui.get('estado_bot', 'N/A')
        latencia = estado_ui.get('latencia', '0ms')
        entradas = estado_ui.get('entradas_hoy', 0)

        grid_kpi.add_row(
            f"🪙 [bold]Precio:[/bold] [cyan]${precio_actual:.3f}[/cyan]",
            f"💰 [bold]Balance:[/bold] [green]${balance:.2f}[/green]",
            f"🤖 [bold]Estado:[/bold] {estado}",
            f"⏱️ [bold]Latencia:[/bold] [yellow]{latencia}[/yellow]",
            f"🎯 [bold]Entradas Hoy:[/bold] [magenta]{entradas}[/magenta]"
        )
        
        encabezado = Panel(grid_kpi, title=f"🦅 SENTINEL PRO - {symbol} 🦅", border_style="gold1", style="bold white")

        # ==========================================
        # 1. MATRIZ MTF
        # ==========================================
        matriz = Table(title="📊 Análisis Multi-Timeframe (MTF)", expand=True, border_style="cyan")
        matriz.add_column("TF", justify="center", style="cyan", no_wrap=True)
        matriz.add_column("RSI", justify="center")
        matriz.add_column("MACD", justify="center")
        matriz.add_column("Stoch", justify="center")
        matriz.add_column("ADX", justify="center")
        matriz.add_column("Volumen", justify="center")
        matriz.add_column("BBoll (Ancho|Dist)", justify="center") 
        matriz.add_column("Divergencia", justify="center")
        matriz.add_column("Tendencia", justify="center")

        mtf_data = estado_ui.get('mtf', {})
        for tf in ["1d", "4h", "1h", "15m", "5m", "1m"]:
            if tf in mtf_data:
                d = mtf_data[tf]
                matriz.add_row(
                    tf.upper(), 
                    DashboardSentinel.formatear_pendiente(d.get('rsi', [0,0])),
                    DashboardSentinel.formatear_pendiente(d.get('macd', [0,0])),
                    DashboardSentinel.formatear_pendiente(d.get('stoch', [0,0])),
                    DashboardSentinel.formatear_pendiente(d.get('adx', [0,0])),
                    DashboardSentinel.formatear_pendiente(d.get('vol', [0,0]), is_vol=True),
                    str(d.get('bb', 'N/A')),
                    str(d.get('div', 'N/A')),
                    str(d.get('trend', 'N/A'))
                )

        # ==========================================
        # 2. NUEVA REJILLA: OPERACIONES ABIERTAS
        # ==========================================
        tabla_ops = Table(title="🛡️ Operaciones Abiertas (Gestor de Riesgo)", expand=True, border_style="green")
        tabla_ops.add_column("Activo", justify="center", style="bold white")
        tabla_ops.add_column("Lado", justify="center")
        tabla_ops.add_column("Cantidad", justify="center", style="yellow")
        tabla_ops.add_column("Precio", justify="center", style="cyan")
        tabla_ops.add_column("SL", justify="center", style="red")
        tabla_ops.add_column("TP", justify="center", style="green")
        tabla_ops.add_column("BE", justify="center", style="magenta")
        tabla_ops.add_column("ID Orden", justify="center", style="dim")
        tabla_ops.add_column("Estado", justify="center")

        posiciones = estado_ui.get('posiciones_activas', [])
        if not posiciones:
            tabla_ops.add_row("-", "-", "-", "-", "-", "-", "-", "-", "[dim]Sin operaciones activas[/dim]")
        else:
            for pos in posiciones:
                lado = pos.get('side', 'N/A')
                lado_fmt = "[bold green]LONG 🔼[/bold green]" if lado == "LONG" else "[bold red]SHORT 🔽[/bold red]" if lado == "SHORT" else lado
                estado_fmt = "[bold cyan]🔒 Asegurada (BE)[/bold cyan]" if pos.get('protegida') else "[bold yellow]⏳ Corriendo[/bold yellow]"
                
                tabla_ops.add_row(
                    str(pos.get('symbol', symbol)),
                    lado_fmt,
                    str(pos.get('cantidad', '0')),
                    f"{pos.get('entry_price', 0):.3f}" if isinstance(pos.get('entry_price'), (int, float)) else str(pos.get('entry_price', '0')),
                    str(pos.get('sl', 'N/A')),
                    str(pos.get('tp', 'N/A')),
                    str(pos.get('be', 'N/A')),
                    str(pos.get('order_id', 'N/A')),
                    estado_fmt
                )

        # ==========================================
        # 3. PANEL DE LOGS (Altura Fija)
        # ==========================================
        mensajes = estado_ui.get('mensajes_sistema', [])
        # Rellenamos con líneas vacías para forzar que la caja no cambie de tamaño
        while len(mensajes) < 6:
            mensajes.append("")
        
        texto_logs = "\n".join(mensajes[-6:])
        monitor = Panel(
            f"[bold white]{texto_logs}[/bold white]", 
            title="🖥️ Monitor de Eventos del Sistema", 
            border_style="blue",
            height=8 # ALTURA FIJA ANTI-DESPLAZAMIENTO
        )
        
        # ==========================================
        # 4. CONSOLA DE COMANDOS
        # ==========================================
        comando_actual = estado_ui.get('comando_buffer', '')
        consola = Panel(
            f"[bold cyan]>[/bold cyan] {comando_actual}█", 
            title="⌨️ Comando Manual", 
            border_style="yellow",
            height=3
        )

        return Group(encabezado, matriz, tabla_ops, monitor, consola)