

__init__(self):
    self.opened_order = False        # Controla si ya hay una orden LIMIT enviada
    self.order_timestamp = None      # Marca cuándo se envió la orden
    self.order_timeout = 60          # Tiempo máximo en segundos para cancelar orden pendiente
    self.last_order_id = None        # Guardar ID de la última orden colocada



def start_websocket(self,):
    # Variables de control
    symbol = self.symbol
    interval = self.temporalidad

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
            compressed_data = gzip.GzipFile(fileobj=io.BytesIO(message), mode='rb')
            decompressed_data = compressed_data.read().decode('utf-8')
            data = json.loads(decompressed_data)

            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:  
                vela = data["data"][0]  
                required_keys = {"o", "h", "l", "c", "v", "T"}  
                if not required_keys.issubset(vela.keys()):  
                    print(f"{self.indicator} WEBSOCKET - ⚠️ Datos de vela inválidos, descartando paquete: {vela}")  
                    return  

                self.last_price = float(vela["c"])  
                avg_price = (float(vela["c"]) + float(vela["o"]) + float(vela["h"]) + float(vela["l"])) / 4  
                self.avg_price = mgo.redondeo(avg_price, self.pip_price)  
                self.df_vela = mgo.conv_pdataframe(data["data"])

                print(f"\n{self.indicator} WEBSOCKET - Exchange: {self.exchange}, Symbol: {symbol}, Temporalidad: {interval}, Dirección: {self.positionside}")
                print(f"{self.indicator} WEBSOCKET - Información de vela actual:\n{self.df_vela}")

                # 🛑 Bloqueo de múltiples órdenes
                if self.opened_order:
                    # Verificar si ya pasó el timeout de la orden pendiente
                    if self.order_timestamp and (time.time() - self.order_timestamp > self.order_timeout):
                        print(f"{self.indicator} WEBSOCKET - ⏳ Orden pendiente expirada, cancelando...")
                        self.set_cancel_order(symbol)
                        self.opened_order = False
                        self.last_order_id = None
                    else:
                        print(f"{self.indicator} WEBSOCKET - ⏸ Señal ignorada, ya existe orden pendiente.")
                        return  

                # Revisar si ya existe orden en el exchange
                open_orders = self.get_current_open_order()
                if open_orders:
                    print(f"{self.indicator} WEBSOCKET - ⚠️ Ya existe orden abierta en exchange, ignorando nueva señal.")
                    self.opened_order = True
                    self.order_timestamp = time.time()
                    return  

                # ✅ Evaluar estrategia
                resultado = self.estrategia_instancia.evaluar_entrada()
                if resultado.get("estrategia_valida", False):
                    order_id = self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, resultado)
                    print(f"{self.indicator} WEBSOCKET - 📉📈 Señal activada, ejecutando entrada en {self.positionside} 🔥💰\n")

                    # Marcar orden pendiente
                    self.opened_order = True
                    self.order_timestamp = time.time()
                    self.last_order_id = order_id

                    # Verificar si la posición ya se abrió
                    positions = self.get_open_position()
                    if self.positionside == "LONG":
                        long_amt = float(positions["LONG"].get("positionAmt", 0))
                        if long_amt > 0:
                            self.position_opened_by_strategy = True
                            print(f"{self.indicator} WEBSOCKET -✅ Posición abierta en {self.positionside}. Cambiando a monitoreo.")
                            ws.close()
                            return
                    elif self.positionside == "SHORT":
                        short_amt = float(positions["SHORT"].get("positionAmt", 0))
                        if short_amt > 0:
                            self.position_opened_by_strategy = True
                            print(f"{self.indicator} WEBSOCKET -✅ Posición abierta en {self.positionside}. Cambiando a monitoreo.")
                            ws.close()
                            return

        except Exception as e:
            print(f"{self.indicator} WEBSOCKET -❌ Error procesando mensaje: {e}")
            traceback.print_exc()
