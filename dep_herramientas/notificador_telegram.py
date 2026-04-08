import os
import requests
import threading
from dotenv import load_dotenv

class NotificadorTelegram:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def enviar_mensaje(self, mensaje: str):
        """Método público no bloqueante."""
        if not self.token or not self.chat_id:
            return # Ignora silenciosamente si no has configurado Telegram
        
        # Ejecutar en un hilo separado para evitar latencia en el trading
        hilo = threading.Thread(target=self._enviar_async, args=(mensaje,))
        hilo.start()

    def _enviar_async(self, mensaje):
        """Método privado que hace la petición a la red de Telegram."""
        try:
            payload = {
                'chat_id': self.chat_id, 
                'text': mensaje, 
                'parse_mode': 'HTML'
            }
            # Timeout muy corto para evitar cuelgues si la red de Telegram falla
            requests.post(self.base_url, data=payload, timeout=5)
        except Exception as e:
            print(f"⚠️ [Telegram] Error de red al enviar mensaje: {e}")

if __name__ == "__main__":
    print("Módulo Notificador Telegram Compilado.")