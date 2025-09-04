import websocket
import json
import gzip
import io
import time
import traceback

# En el __init__ de tu clase, agrega:
# self.orden_pendiente = False
# self.last_signal_time = 0

def start_websocket(self):
    # Variables de control
    symbol = self.symbol
    interval = self.temporalidad  # Asumiendo self.temporalidad es el interval

    # Calcula el debounce_interval basado en el timeframe (ej. '1m' -> 60s)
    debounce_interval = self._get_interval_seconds(interval)  # Método helper abajo

    # Inicia una conexión WebSocket evitando múltiples conexiones simultáneas
    if self.ws_running:
        print("⚠️ WebSocket ya está en ejecución, evitando conexión duplicada.")
        return
    self.ws_running = True  # Marcar WebSocket como activo

    channel = {
        "id": "e745cd6d-d0f6-4a70-8d5a-043e4c741b40",
        "reqType": "sub",
        "dataType": f"{symbol}@kline_{interval}"
    }

    def on_open(ws):
        print(f"📡 Conectado a WebSocket para {symbol}")
        ws.send(json.dumps(channel))

    def on_message(ws, message):
        try:
            compressed_data = gzip.GzipFile(fileobj=io.BytesIO(message), mode='rb')
            decompressed_data = compressed_data.read().decode('utf-8')
            data = json.loads(decompressed_data)

            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:  
                vela = data["data"][0]  

                # ✅ Validar que la vela tenga todas las claves necesarias
                required_keys = {"o", "h", "l", "c", "v", "T"}  
                if not required_keys.issubset(vela.keys()):  
                    print(f"{self.indicator} WEBSOCKET - ⚠️ Datos de vela inválidos, descartando paquete: {vela}")  
                    return  # 🔴 No procesamos data mala

                # ✅ Procesar solo si la data es válida
                self.last_price = float(vela["c"])  
                avg_price = (float(vela["c"]) + float(vela["o"]) + float(vela["h"]) + float(vela["l"])) / 4  
                self.avg_price = mgo.redondeo(avg_price, self.pip_price)  
                self.df_vela = mgo.conv_pdataframe(data["data"])

                print(f"\n{self.indicator} WEBSOCKET - Exchange: {self.exchange}, Symbol: {symbol}, Temporalidad: {interval}, Dirección de operación: {self.indicator} {self.positionside}")
                print(f"{self.indicator} WEBSOCKET - Información de vela actual:\n{self.df_vela}")

                # Throttling: Chequea si ha pasado el intervalo desde la última señal procesada
                current_time = time.time()
                if current_time - self.last_signal_time > debounce_interval and not self.orden_pendiente:
                    # Primera señal válida en la ventana: Procesar
                    self.last_signal_time = current_time
                    self.orden_pendiente = True  # Activar flag de orden pendiente

                    # Se evalua la entrada con websocket
                    resultado = self.estrategia_instancia.evaluar_entrada()
                    if resultado.get("estrategia_valida", False):
                        # Llamada a la función para colocar la orden de mercado o limit
                        self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, resultado)
                        print(f"{self.indicator} WEBSOCKET - 📉📈 Señal activada, ejecutando entrada en {self.positionside} 🔥💰\n")

                    # Verifica si la posición se abrió correctamente (esto puede ser lento, pero el flag/throttling lo protege)
                    positions = self.get_open_position()
                    if self.positionside == "LONG":
                        long_amt = float(positions["LONG"].get("positionAmt", 0))
                        if long_amt > 0:
                            self.position_opened_by_strategy = True
                            self.orden_pendiente = False  # Reset flag al confirmar
                            print(f"{self.indicator} WEBSOCKET -✅ Posición abierta en {self.positionside}. Cambiando a monitoreo.")
                            ws.close()  # Cerrar WebSocket para volver al monitoreo de la posición
                            return
                    elif self.positionside == "SHORT":
                        short_amt = float(positions["SHORT"].get("positionAmt", 0))
                        if short_amt > 0:
                            self.position_opened_by_strategy = True
                            self.orden_pendiente = False  # Reset flag al confirmar
                            print(f"{self.indicator} WEBSOCKET -✅ Posición abierta en {self.positionside}. Cambiando a monitoreo.")
                            ws.close()  # Cerrar WebSocket para volver al monitoreo de la posición
                            return

                    # Si no se abrió (ej. orden limit no tocada), el flag queda activo hasta que expire el throttle
                    # En el próximo mensaje, si el tiempo expiró, reseteará y reintentará si hay nueva señal

                else:
                    print(f"{self.indicator} WEBSOCKET - ⚠️ Señal ignorada: Orden pendiente o dentro de ventana de throttling ({debounce_interval}s).")

                # Chequeo de expiración: Si el throttle expiró y aún no se abrió, reset flag y cierra para reevaluar
                if current_time - self.last_signal_time > debounce_interval and self.orden_pendiente:
                    print(f"{self.indicator} WEBSOCKET - ⏰ Tiempo de throttling expirado sin apertura. Reseteando y cerrando para reevaluar.")
                    self.orden_pendiente = False
                    ws.close()  # Cierra y permite reevaluar condiciones
                    return

        except Exception as e:
            print(f"{self.indicator} WEBSOCKET -❌ Error procesando mensaje: {e}")
            traceback.print_exc()

    def on_error(ws, error):
        print(f"⚠️ Error en WebSocket {self.indicator}: {error}, Intentando reconectar...")
        self.ws_running = False  # Marcar WebSocket como inactivo
        self._reconnect()

    def on_close(ws, close_status_code, close_msg):
        print(f"⚠️ Conexión WebSocket {self.indicator} cerrada.")
        self.ws_running = False  # Marcar WebSocket como inactivo
        #self._reconnect(symbol, interval)

    self.ws = websocket.WebSocketApp(
        self.ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    self.ws.run_forever()  # self.ws.run_forever(ping_interval=30)  # Envia Ping cada 30 segundos

# Método helper para convertir interval a segundos (agrega esto a tu clase)
def _get_interval_seconds(self, interval_str):
    # Parser simple para intervalos como '1m', '5m', '1h', '4h', '1d', etc.
    unit = interval_str[-1].lower()
    value = int(interval_str[:-1])
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        print(f"⚠️ Intervalo desconocido: {interval_str}. Usando default 60s.")
        return 60  # Default a 1m