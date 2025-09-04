import time
import json
import gzip
import io
import traceback
import websocket # Asegúrate de que websocket-client está instalado

# Asumo que esta función podría estar en otro lugar, pero la pongo aquí para el ejemplo
def convertir_intervalo_a_segundos(intervalo):
    """Convierte un intervalo de string (ej. '5m', '1h') a segundos."""
    numero = int(intervalo[:-1])
    unidad = intervalo[-1]
    if unidad == 'm':
        return numero * 60
    elif unidad == 'h':
        return numero * 3600
    elif unidad == 'd':
        return numero * 86400
    return numero # Por si es solo un número de segundos

class TuClaseDeBot: # Reemplaza con el nombre de tu clase
    # ... (aquí irían tu __init__ y otros métodos) ...
    
    # ### NUEVO ### - Inicializa estas variables en el __init__ de tu clase
    def __init__(self, symbol, temporalidad, ...):
        # ... tus otras inicializaciones ...
        self.symbol = symbol
        self.temporalidad = temporalidad
        self.orden_pendiente = False
        self.tiempo_ultima_orden = 0
        # Establecemos el cooldown dinámicamente basado en la temporalidad
        self.COOLDOWN_SEGUNDOS = convertir_intervalo_a_segundos(self.temporalidad)
        # ... el resto de tus atributos ...

    def start_websocket(self):
        # Variables de control
        symbol = self.symbol
        interval = self.temporalidad

        # Inicia una conexión WebSocket
        if self.ws_running:
            print("⚠️ WebSocket ya está en ejecución, evitando conexión duplicada.")
            return
        self.ws_running = True

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
                # ... (tu código de descompresión y validación de vela es perfecto, no cambia) ...
                compressed_data = gzip.GzipFile(fileobj=io.BytesIO(message), mode='rb')
                decompressed_data = compressed_data.read().decode('utf-8')
                data = json.loads(decompressed_data)

                if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                    vela = data["data"][0]
                    # ... (tu validación de claves está bien) ...
                    
                    # ### NUEVO - PASO 1: Lógica de Cooldown y Timeout (El "Guardián") ###
                    # Este bloque se ejecuta PRIMERO en cada mensaje.
                    if self.orden_pendiente:
                        tiempo_transcurrido = time.time() - self.tiempo_ultima_orden
                        
                        # Si la orden no se ha llenado y el cooldown/timeout ha expirado
                        if tiempo_transcurrido > self.COOLDOWN_SEGUNDOS:
                            print(f"{self.indicator} WEBSOCKET - ⌛️ Timeout. La orden no se ejecutó en {self.COOLDOWN_SEGUNDOS}s. Reevaluando...")
                            self.orden_pendiente = False # Reseteamos para poder enviar otra orden
                            self.tiempo_ultima_orden = 0
                            ws.close() # Cerramos para volver al bucle principal y reevaluar todo
                            return
                        else:
                            # Si aún estamos en cooldown, ignoramos el mensaje y no hacemos nada más.
                            # print(f"Cooldown activo. Ignorando señal. Tiempo restante: {self.COOLDOWN_SEGUNDOS - tiempo_transcurrido:.0f}s")
                            return

                    # Procesamiento de la vela (tu código original)
                    self.last_price = float(vela["c"])
                    # ... (resto de tu procesamiento de vela) ...
                    self.df_vela = mgo.conv_pdataframe(data["data"])

                    print(f"\n{self.indicator} WEBSOCKET - Buscando señal para {self.positionside}...")
                    
                    # Se evalua la entrada con websocket
                    resultado = self.estrategia_instancia.evaluar_entrada()

                    # ### MODIFICADO - PASO 2: La condición de entrada ahora es más simple y segura ###
                    if resultado.get("estrategia_valida", False) and not self.orden_pendiente:
                        
                        # ### PASO 3: Activación INMEDIATA del bloqueo ###
                        print(f"{self.indicator} WEBSOCKET - 📉📈 Señal activada, ejecutando entrada en {self.positionside} 🔥💰")
                        
                        # Llamada a la función para colocar la orden (esto no cambia)
                        # Asumimos que esta función devuelve True si el envío fue exitoso
                        exito_envio = self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, resultado)

                        if exito_envio:
                            print(f"{self.indicator} WEBSOCKET - ✅ Orden enviada al exchange. Bloqueo activado por {self.COOLDOWN_SEGUNDOS}s.")
                            self.orden_pendiente = True
                            self.tiempo_ultima_orden = time.time()
                            
                            # Cerramos el websocket para que el bucle principal se encargue de monitorear la orden
                            ws.close()
                            return
                        else:
                            print(f"{self.indicator} WEBSOCKET - ❌ Fallo al enviar la orden al exchange. No se activa el bloqueo.")

                    # ### ELIMINADO ###
                    # Se elimina por completo la sección que llamaba a self.get_open_position()
                    # porque era la causa de la latencia y la condición de carrera.

            except Exception as e:
                print(f"{self.indicator} WEBSOCKET -❌ Error procesando mensaje: {e}")
                traceback.print_exc()

        # ... (el resto de tu código, on_error, on_close, y la inicialización de WebSocketApp es perfecto) ...
        
        
# ... dentro de tu clase, la función on_message ...

def on_message(ws, message):
    try:
        # ... tu código de descompresión y validación de vela sigue igual, es perfecto ...
        
        # Obtenemos el tiempo actual una sola vez al principio
        current_time = time.time()

        # =================================================================
        # === MÁQUINA DE ESTADOS: UN SOLO LUGAR PARA TOMAR DECISIONES ===
        # =================================================================

        # ESTADO 1: ¿Estamos esperando una orden y ya expiró su tiempo?
        if self.pending_order and (current_time - self.last_signal_time > self.time_wait):
            print(f"⏰ Tiempo de espera para orden pendiente expirado. Cancelando y reevaluando...")
            self.set_cancel_order("LIMIT")  # Cancela órdenes pendientes del par
            self.pending_order = False      # <-- Resetea el flag
            self.estrategia_instancia.reiniciar_condiciones()
            ws.close()                      # <-- Cierra para que el bucle principal reevalue todo desde cero
            return

        # ESTADO 2: ¿Estamos esperando una orden que todavía está dentro de su tiempo?
        elif self.pending_order:
            # print("⏳ Orden pendiente, esperando ejecución o timeout. Ignorando nueva vela.") # Log opcional
            return # <-- No hacemos NADA MÁS. Esperamos pacientemente.

        # ESTADO 3: No hay orden pendiente. ¿Podemos buscar una nueva señal?
        # Esta es la lógica original de throttling/cooldown
        elif not self.pending_order and (current_time - self.last_signal_time > self.time_wait):
            # Aquí procesamos la vela (tu código)
            # ... self.last_price, self.avg_price, etc. ...
            print(f"\n{self.indicator} WEBSOCKET - Buscando nueva señal para {self.positionside}...")

            resultado = self.estrategia_instancia.evaluar_entrada()

            if resultado.get("estrategia_valida", False):
                print(f"📉📈 ¡Señal de entrada válida detectada!")
                
                # Enviamos la orden (market o limit)
                exito_envio = self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, resultado)
                
                if exito_envio:
                    # ¡SOLO SI LA ORDEN SE ENVIÓ CON ÉXITO, CAMBIAMOS DE ESTADO!
                    print(f"✅ Orden enviada al exchange. Iniciando monitoreo por {self.time_wait}s.")
                    self.pending_order = True       # <-- Flag activado en el momento correcto
                    self.last_signal_time = time.time() # <-- Reiniciamos el temporizador AHORA
                    
                    # El trabajo del WebSocket ha terminado. Su única misión era enviar la orden.
                    # El bucle principal se encargará de confirmar si se llenó.
                    ws.close()
                    return
                else:
                    print(f"❌ La orden no pudo ser enviada al exchange. El bot sigue buscando.")
                    
            # Si la estrategia no es válida, no hacemos nada y esperamos a la siguiente vela.
        
        # Si ninguna de las condiciones anteriores se cumple, significa que estamos dentro del
        # cooldown inicial pero sin una orden pendiente, simplemente ignoramos el tick.

    except Exception as e:
        print(f"{self.indicator} WEBSOCKET -❌ Error procesando mensaje: {e}")
        traceback.print_exc()        