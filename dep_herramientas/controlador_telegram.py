# =============================================================================
# NOMBRE: controlador_telegram.py
# UBICACIÓN: /dep_herramientas/
# OBJETIVO: Listener asíncrono para recibir comandos remotos 24/7.
# =============================================================================

import asyncio
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

class ControladorTelegram:
    def __init__(self, token, orquestador):
        self.token = token
        self.orquestador = orquestador

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status: Devuelve una foto en texto del estado del bot."""
        estado = self.orquestador.estado_ui
        pnl = estado['balance_actual'] - estado['balance_inicial']
        
        # Limpiar texto de formato de consola (como los [green] de la librería Rich)
        msg_sistema = estado['mensajes_sistema'][-1].replace('[bold white]', '').replace('[/bold white]', '')
        
        msg = (
            f"🤖 *SENTINEL PRO - REPORTE*\n"
            f"💰 Capital USDT: `${estado['balance_actual']:.2f}`\n"
            f"📊 PnL Diario: `${pnl:+.2f}`\n"
            f"🪙 Activo: `${estado['precio_actual']:.2f}`\n\n"
            f"⚙️ Trading Activo: `{'SÍ' if self.orquestador.trading_permitido else 'NO (Pausado)'}`\n"
            f"🛡️ Última Acción: _{msg_sistema}_"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_pausar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /pausar: Inyecta el comando de pausa en el Orquestador."""
        self.orquestador.procesar_comando_manual("k l 1")
        await update.message.reply_text("⏸️ Comando recibido. Bot pausado. Se ignorarán nuevas señales.")

    async def cmd_reanudar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /reanudar: Inyecta el comando de reactivación en el Orquestador."""
        self.orquestador.procesar_comando_manual("r")
        await update.message.reply_text("▶️ Comando recibido. Bot reanudado. Operaciones activas.")

    async def cmd_panico(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /panico: Dispara el Killswitch nuclear."""
        await update.message.reply_text("🚨 ¡KILLSWITCH RECIBIDO! Iniciando liquidación de emergencia...")
        self.orquestador.procesar_comando_manual("k l 2")
        await update.message.reply_text("☢️ Posiciones liquidadas. El bot ha sido desactivado.")

    def _run_loop(self):
        """Bucle de eventos aislado para el hilo de Telegram."""
        # Se requiere un nuevo loop de eventos porque estamos en un hilo secundario
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        app = Application.builder().token(self.token).build()
        
        # Registrar los comandos
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("pausar", self.cmd_pausar))
        app.add_handler(CommandHandler("reanudar", self.cmd_reanudar))
        app.add_handler(CommandHandler("panico", self.cmd_panico))
        
        # Iniciar el oyente de forma silenciosa
        app.run_polling(drop_pending_updates=True)

    def iniciar(self):
        """Función pública para arrancar el listener en un hilo fantasma."""
        if not self.token:
            self.orquestador.log_ui("⚠️ Telegram Inactivo: No se detectó TOKEN.")
            return
            
        hilo_telegram = threading.Thread(target=self._run_loop, daemon=True)
        hilo_telegram.start()
        self.orquestador.log_ui("✈️ Módulo de Telegram conectado a la nube.")