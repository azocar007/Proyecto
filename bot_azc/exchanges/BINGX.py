### Modulo BingX ###

import pprint
import traceback
import pandas as pd
import os
import time
from datetime import datetime
import threading
import calendar
import hmac
import hashlib
import json
import gzip
import io
import psutil
import websocket
import requests
import Modos_de_gestion_operativa as mgo
from typing import Callable, Optional

PosLong = mgo.PosicionLong()
PosShort = mgo.PosicionShort()

# Definiendo la clase BingX
class BingX:

    def __init__(self, estrategia: Optional[Callable] = None, dict: dict = None):

        """ Inicializa la clase BingX con los parámetros necesarios para operar en el exchange. """
        self.exchange = "BINGX"
        self.api_key = "eQIiQ5BK4BGJJNgAce6QPN3iZRtjVUuo5NgVP2lnbe5xgywXr0pjP3x1tWaFnqVmavHXLRjFYOlg502XxkcKw"
        self.api_secret = "OkIfPdSZOG1nua7UI7bKfbO211T3eS21XVwBymT8zg84lAwmrjtcDnZKfAd7dPJVuATTUe3ibzUwaWxTuCLw"
        self.trade_type = "contractPerpetual"
        self.session = requests.Session()
        self.session.headers.update({
            "X-BX-APIKEY": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.base_url = "https://open-api.bingx.com"
        self.ws_url = "wss://open-api-swap.bingx.com/swap-market"
        self.ws = None
        self.ws_running = False  # Controla si el WebSocket está activo
        self.position_opened_by_strategy = False  # Flag para control de entrada
        self._detener_monitor = threading.Event()

        """ Variables del diccionario de entrada """
        self.dict = dict
        self.symbol = str(self.dict["symbol"]).upper() + "-USDT"
        self.positionside = str(self.dict["positionside"]).upper() # "LONG" o "SHORT"
        self.modo_operacion = str(self.dict["modo_operacion"]).upper() # "UNICO", "ALTERNADO", "SIMULTANEO", "CARDIACO" 
        self.modo_gestion = str(self.dict["modo_gestion"]).upper() # "REENTRADAS", "RATIO BENEFICIO/PERDIDA", "SNOW BALL"
        self.monto_sl = float(self.dict["monto_sl"])
        self.type = str(self.dict["type"]).upper() # "LIMIT" o "MARKET" o "BBO"
        self.gestion_take_profit = str(self.dict["gestion_take_profit"]).upper() # "RATIO BENEFICIO/PERDIDA", "% TAKE PROFIT"
        self.ratio = float(self.dict["ratio"]) if "ratio" in self.dict else 1
        self.gestion_vol = str(self.dict["gestion_vol"]).upper() # "MARTINGALA", "% DE REENTRADAS", "AGRESIVO"
        self.cant_ree = int(self.dict["cant_ree"]) if "cant_ree" in self.dict else 0
        self.dist_ree = float(self.dict["dist_ree"]) if "dist_ree" in self.dict else 1
        self.porcentaje_vol_ree = int(self.dict["porcentaje_vol_ree"]) if "porcentaje_vol_ree" in self.dict else 0
        self.monedas = float(self.dict["monedas"])
        self.usdt = float(self.dict["usdt"])
        self.segundos_monitoreo = int(self.dict["segundos"]) if "segundos" in self.dict else 10
        self.temporalidad = str(self.dict["temporalidad"]) if "temporalidad" in self.dict else "1m"
        self.cant_candles = int(self.dict["cant_velas"]) if "cant_velas" in self.dict else 1

        """ Variables de calculo predefinidas para los metodos check_strategy() y monedas_de_entrada() """
        self.last_price = None
        self.avg_price = None
        self.df_vela: pd.DataFrame = None
        self.precio_sl = None
        self.precio_entrada = None         # Solo se usa en los condicionales del metodo set_limit_market_order()
        self.estrategia = estrategia
        # 📊 DataFrame y control de actualización
        self.df: pd.DataFrame = None      # Contendrá las velas convertidas a DataFrame dinamico
        self.last_df_update = 0           # Timestamp (epoch UTC) de la última actualización
        self.pending_order = False
        self.last_signal_time = 0
        self.orden_timestamp = None
        self._ultima_vela = None
        self.df_thread = None             # Referencia al hilo de actualización de df_dynamic
        self.long = None
        self.short = None
        self.enter_params = {"estrategia_valida": False}
        self.indicator = "🟢" if (self.positionside).upper() == "LONG" else "🔴"
        self.time_wait = int(self.dict["tiempo_espera"]) if self.dict["tiempo_espera"] in [0, None] else mgo.temporalidad_a_segundos(self.temporalidad)
        self.pip_price = self.pip_precio()
        self.decimales_price = self.cant_deci_precio()
        self.pip_mon = self.pip_moneda()


    """ METODOS PARA OBETENER INFORMACION DE LA CUENTA Y DEL ACTIVO """

    # Metodo para generar la firma HMAC SHA256 requerida por la API.
    def _get_signature(self, params: str) -> str:
        return hmac.new(self.api_secret.encode(), params.encode(), hashlib.sha256).hexdigest()

    # Metodo para obtener el timestamp actual.
    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))

    # Metodo para obtener el balance de la cuenta
    def get_balance(self):
        timestamp = self._get_timestamp()
        params = f"timestamp={timestamp}&tradeType={self.trade_type}"
        signature = self._get_signature(params)
        url = f"{self.base_url}/openApi/swap/v2/user/balance?{params}&signature={signature}"
        response = self.session.get(url)
        """
        A continuación se muestra la información que se puede obtener en el dict "balance":
        asset →             El activo de la cuenta (USDT).
        availableMargin →   Lo que puedes usar para operar.
        balance →           Todo tu saldo de la cuenta.
        equity →            Tu balance total incluyendo ganancias/pérdidas abiertas.
        freezedMargin →     Cuánto de tu saldo está congelado.
        realisedProfit →    Las ganancias/perdidas que ya cerraste.
        shortUid →          Tu ID de usuario.
        unrealizedProfit →  Si tienes posiciones abiertas, muestra cuánto has ganado o perdido.
        usedMargin →        Cuánto de tu saldo está en uso como margen.
        userId →            Tu ID de usuario.
        """
        return response.json()["data"]["balance"]

    # Metodo para obtener informacion de la moneda
    def inf_moneda(self):
        url = f"{self.base_url}/openApi/swap/v2/quote/contracts"
        response = self.session.get(url)
        data = response.json()
        for contract in data.get("data", []):
            if contract["symbol"] == self.symbol:
                return contract
        return None

    # Metodo para obtener el pip del precio
    def pip_precio(self):
        url = f"{self.base_url}/openApi/swap/v2/quote/contracts"
        response = self.session.get(url)
        data = response.json()
        for contract in data.get("data", []):
            if contract["symbol"] == self.symbol:
                return 10 ** -contract["pricePrecision"]
        return None

    # Metodo para obtener cantidad de decimales del precio
    def cant_deci_precio(self):
        url = f"{self.base_url}/openApi/swap/v2/quote/contracts"
        response = self.session.get(url)
        data = response.json()
        for contract in data.get("data", []):
            if contract["symbol"] == self.symbol:
                return contract["pricePrecision"]
        return None

    # Metodo para obtener pip de la moneda
    def pip_moneda(self):
        url = f"{self.base_url}/openApi/swap/v2/quote/contracts"
        response = self.session.get(url)
        data = response.json()
        for contract in data.get("data", []):
            if contract["symbol"] == self.symbol:
                return contract["tradeMinQuantity"]
        return None

    # Metodo para obtener monto minimo USDT
    def min_usdt(self):
        url = f"{self.base_url}/openApi/swap/v2/quote/contracts"
        response = self.session.get(url)
        data = response.json()
        for contract in data.get("data", []):
            if contract["symbol"] == self.symbol:
                return contract["tradeMinUSDT"]
        return None

    # Metodo para obtener y ajustar el maximo apalancamiento
    def max_apalancamiento(self):
        symbol = self.symbol
        """ Función para obtener el apalancamiento máximo de un activo """
        def get_leverage(symbol: str):
            params = {
                "symbol": symbol,
            }
            data = self._send_request("GET", "/openApi/swap/v2/trade/leverage", params) # devuelve un diccionario
            #pprint.pprint({"DEBUG - Respuesta API": data}) # comprobar respuesta de API
            maxlongleverage = data["data"]["maxLongLeverage"]
            longleverage = data["data"]["longLeverage"]
            maxshortleverage = data["data"]["maxShortLeverage"]
            shortleverage = data["data"]["shortLeverage"]
            print(f"Apalancamiento máximo 🟢 LONG: {maxlongleverage}, actual: {longleverage}")
            print(f"Apalancamiento máximo 🔴 SHORT: {maxshortleverage}, actual: {shortleverage}")
            return {
                "maxlongleverage": maxlongleverage,
                "longleverage": longleverage,
                "maxshortleverage": maxshortleverage,
                "shortleverage": shortleverage  
            }

        """ Función para setear el apalancamiento del activo """
        def set_leverage(symbol: str, leverage: int, side: str):
            params = {
                "symbol": symbol,
                "leverage": leverage,
                "side": side
            }
            return self._send_request("POST", "/openApi/swap/v2/trade/leverage", params)

        data = get_leverage(symbol)
        maxlongleverage = data["maxlongleverage"]
        longleverage = data["longleverage"]
        maxshortleverage = data["maxshortleverage"]
        shortleverage = data["shortleverage"]

        if maxlongleverage == longleverage and maxshortleverage == shortleverage:
            print("Apalancamiento ajustado a maximos valores.")
        else:
            print("Seteando a valores maximos permitidos...")
            set_leverage(symbol, maxlongleverage, "LONG")
            set_leverage(symbol, maxshortleverage, "SHORT")
            get_leverage(symbol)


    """ METODOS PARA SEGUIMIENTO Y EJECUCIÓN DEL LA ESTRATEGIA """

    # Metodo para conocer todas las posiciones abiertas
    def get_all_open_positions(self):
        timestamp = self._get_timestamp()
        params = f"timestamp={timestamp}&tradeType={self.trade_type}"
        signature = self._get_signature(params)
        url = f"{self.base_url}/openApi/swap/v2/user/positions?{params}&signature={signature}"
        response = self.session.get(url)
        data = response.json()
        #pprint.pprint({"DEBUG - Respuesta API completa": data["data"]})  # 🔍 Verifica si el activo aparece en la respuesta

        # Lista de respuesta
        posiciones = []

        if "data" not in data or not data["data"]:
            print("DEBUG - No hay posiciones abiertas.")
            return posiciones

        for pos in data["data"]:
            #raw_symbol = pos.get("symbol", "")
            #clean_symbol = mgo.limpiar_symbol(raw_symbol)
            posicion = {
                        "symbol": pos["symbol"], # clean_symbol
                        "positionside": pos["positionSide"],
                        "avgPrice": pos.get("avgPrice", "N/A"),
                        "positionAmt": pos.get("positionAmt", "N/A")
                        }
            posiciones.append(posicion)
        #pprint.pprint(posiciones) # 🔍 Verifica la cantidad de posiciones que aparece en la respuesta
        return posiciones

    # Metodo para conocer si existe una posicion abierta en LONG o SHORT con reintentos infinitos
    def get_open_position(self):
        timestamp = self._get_timestamp()
        params = f"timestamp={timestamp}&tradeType={self.trade_type}"
        signature = self._get_signature(params)
        url = f"{self.base_url}/openApi/swap/v2/user/positions?{params}&signature={signature}"
        response = self.session.get(url)
        data = response.json()
        #pprint.pprint({"DEBUG - Respuesta API completa": data["data"]})  # 🔍 Verifica si el activo aparece en la respuesta

        long_position = {}
        short_position = {}

        if "data" not in data or not data["data"]:
            print("DEBUG - No hay posiciones abiertas.")
            return {"LONG": long_position, "SHORT": short_position}

        for position in data["data"]:
            #pprint.pprint({"DEBUG - Datos de posición": position})  # 🔍 Verifica cómo la API devuelve los datos
            if position["symbol"] == self.symbol:
                if position["positionSide"] == "LONG": #float(position.get("positionAmt", 0)) > 0 and 
                    long_position = {
                        "avgPrice": position.get("avgPrice", "N/A"),
                        "positionAmt": position.get("positionAmt", "N/A")
                    }
                elif position["positionSide"] == "SHORT": #float(position.get("positionAmt", 0)) > 0 and 
                    short_position = {
                        "avgPrice": position.get("avgPrice", "N/A"),
                        "positionAmt": position.get("positionAmt", "N/A")
                    }
        return {"LONG": long_position, "SHORT": short_position}

    # Función para mantener el monto de las monedas iniciales
    def monedas_de_entrada(self, positionside: str):
        # Variables
        monto_sl = self.monto_sl
        cant_ree = self.cant_ree
        dist_ree = self.dist_ree
        porcentaje_vol_ree = self.porcentaje_vol_ree
        gestion_vol = self.gestion_vol
        precio_sl = self.precio_sl

        positions = self.get_open_position()
        precio_long = float(positions["LONG"]["avgPrice"])
        precio_short = float(positions["SHORT"]["avgPrice"])
        monedas_long = float(positions["LONG"]["positionAmt"])
        monedas_short = float(positions["SHORT"]["positionAmt"])

        if not self.modo_operacion == "CARDIACO":

            monedas = self.monedas
            usdt = self.usdt

            if positionside == "LONG" and precio_long > 0:
                precio = precio_long
            elif positionside == "SHORT" and precio_short > 0:
                precio = precio_short
            else:
                precio = self.precio_entrada

            if positionside == "LONG":
                pos = PosLong
                precio_sl = precio * (100 - dist_ree) / 100 if monedas == 0 and usdt == 0 else None
            else:  # positionside == "SHORT"
                pos = PosShort
                precio_sl = precio * (100 + dist_ree) / 100 if monedas == 0 and usdt == 0 else None

            if monedas == 0:
                if usdt == 0:
                    monedas = pos.vol_monedas(monto_sl, precio, precio_sl)
                    monedas = monedas / cant_ree
                else:
                    monedas = usdt / precio

        else: # modo_operacion == "CARDIACO"
            usdt = self.usdt
            if positionside == "LONG" and precio_long > 0:
                monedas = monedas_long
                precio = precio_long
                pos = PosLong
            elif positionside == "SHORT" and precio_short > 0:
                monedas = monedas_short
                precio = precio_short
                pos = PosShort

        data = pos.recompras(precio, monto_sl, cant_ree, dist_ree, monedas,
                            porcentaje_vol_ree, usdt, gestion_vol)

        #print(f"DEBUG - Cantidad de monedas: {monedas}, Cantidad de reentradas: {len(data['prices'])}\n")

        return {"monedas": float(monedas),"cant_ree": int(len(data["prices"]))}

    # Metodo para gestionar el stop loss
    def dynamic_sl_manager(self, symbol: str, positionside: str):

        posiciones = self.get_open_position()
        long_amt = float(posiciones["LONG"].get("positionAmt", 0))
        short_amt = float(posiciones["SHORT"].get("positionAmt", 0))

        if positionside == "LONG" and long_amt > 0:
            orders = self.get_current_open_orders("STOP_MARKET")
            list_sl = orders["long_amt_orders"]

            if not list_sl:
                print(f"{self.indicator} Posición LONG no tiene Stop Loss. Colocando...\n")
                avg_price = float(posiciones["LONG"].get("avgPrice", 0))
                stop_price = PosLong.stop_loss(avg_price, self.monto_sl, long_amt)
                self.set_stop_loss(symbol, positionside, long_amt, stop_price)

            elif list_sl[0] != long_amt:
                print(f"{self.indicator} Stop Loss incorrecto en LONG. Cancelando y colocando uno nuevo...\n")
                long_order_id = orders["long_orders"][0]
                self._cancel_order(symbol, long_order_id)
                avg_price = float(posiciones["LONG"].get("avgPrice", 0))
                stop_price = PosLong.stop_loss(avg_price, self.monto_sl, long_amt)
                self.set_stop_loss(symbol, positionside, long_amt, stop_price)

            else:
                print(f"{self.indicator} Posición LONG ya tiene Stop Loss correcto.\n")

        elif positionside == "SHORT" and short_amt > 0:
            orders = self.get_current_open_orders("STOP_MARKET")
            list_sl = orders["short_amt_orders"]

            if not list_sl:
                print(f"{self.indicator} Posición SHORT no tiene Stop Loss. Colocando...\n")
                avg_price = float(posiciones["SHORT"].get("avgPrice", 0))
                stop_price = PosShort.stop_loss(avg_price, self.monto_sl, short_amt)
                self.set_stop_loss(symbol, positionside, short_amt, stop_price)

            elif list_sl[0] != short_amt:
                print(f"{self.indicator} Stop Loss incorrecto en SHORT. Cancelando y colocando uno nuevo...\n")
                short_order_id = orders["short_orders"][0]
                self._cancel_order(symbol, short_order_id)
                avg_price = float(posiciones["SHORT"].get("avgPrice", 0))
                stop_price = PosShort.stop_loss(avg_price, self.monto_sl, short_amt)
                self.set_stop_loss(symbol, positionside, short_amt, stop_price)

            else:
                print(f"{self.indicator} Posición SHORT ya tiene Stop Loss correcto.\n")

    # Metodo para gestionar el take profit
    def dynamic_tp_manager(self,  symbol: str, positionside: str):

        posiciones = self.get_open_position()
        long_amt = float(posiciones["LONG"].get("positionAmt", 0))
        short_amt = float(posiciones["SHORT"].get("positionAmt", 0))

        if positionside == "LONG" and long_amt > 0:
            orders = self.get_current_open_orders("TAKE_PROFIT")
            list_tp = orders["long_amt_orders"]

            if not list_tp:
                print(f"{self.indicator} No hay Take Profit en LONG. Colocando uno...\n")
                avg_price = float(posiciones["LONG"].get("avgPrice", 0))
                tp_price = PosLong.take_profit(self.gestion_take_profit, avg_price, self.monto_sl, long_amt, self.ratio)
                self.set_take_profit(symbol, positionside, long_amt, tp_price)

            elif list_tp[0] != long_amt:
                print(f"{self.indicator} Take Profit incorrecto en LONG. Reemplazando...\n")
                long_tp_id = orders["long_orders"][0]
                self._cancel_order(symbol, long_tp_id)
                avg_price = float(posiciones["LONG"].get("avgPrice", 0))
                tp_price = PosLong.take_profit(self.gestion_take_profit, avg_price, self.monto_sl, long_amt, self.ratio)
                self.set_take_profit(symbol, positionside, long_amt, tp_price)

            else:
                print(f"{self.indicator} Take Profit en LONG está correcto.\n")

        elif positionside == "SHORT" and short_amt > 0:
            orders = self.get_current_open_orders("TAKE_PROFIT")
            list_tp = orders["short_amt_orders"]

            if not list_tp:
                print(f"{self.indicator} No hay Take Profit en SHORT. Colocando uno...\n")
                avg_price = float(posiciones["SHORT"].get("avgPrice", 0))
                tp_price = PosShort.take_profit(self.gestion_take_profit, avg_price, self.monto_sl, short_amt, self.ratio)
                self.set_take_profit(symbol, positionside, short_amt, tp_price)

            elif list_tp[0] != short_amt:
                print(f"{self.indicator} Take Profit incorrecto en SHORT. Reemplazando...\n")
                short_tp_id = orders["short_orders"][0]
                self._cancel_order(symbol, short_tp_id)
                avg_price = float(posiciones["SHORT"].get("avgPrice", 0))
                tp_price = PosShort.take_profit(self.gestion_take_profit, avg_price, self.monto_sl, short_amt, self.ratio)
                self.set_take_profit(symbol, positionside, short_amt, tp_price)

            else:
                print(f"{self.indicator} Take Profit en SHORT está correcto.\n")

    # Metodo para gestionar las reentradas
    def dynamic_reentradas_manager(self, symbol: str, positionside: str, modo_gestion: str):

        posiciones = self.get_open_position()
        long_amt = float(posiciones["LONG"].get("positionAmt", 0))
        short_amt = float(posiciones["SHORT"].get("positionAmt", 0))
        datos_iniciales = self.monedas_de_entrada(positionside)
        monedas_iniciales = datos_iniciales["monedas"]
        cant_ree_real = datos_iniciales["cant_ree"]

        if positionside == "LONG" and long_amt > 0 and modo_gestion == "REENTRADAS":
            orders = self.get_current_open_orders("LIMIT")
            list_rl = orders["long_amt_orders"] # lista de montos de las reentradas LONG

            if not list_rl and long_amt == monedas_iniciales:
                print(f"{self.indicator} Posición LONG no tiene reentradas. Colocando...\n")
                self.set_limit_market_order(symbol, positionside, modo_gestion)

            elif cant_ree_real > len(list_rl) and long_amt == monedas_iniciales:
                print(f"{self.indicator} Ajustando la posición LONG a la cantidad de reentradas correctas...\n")
                self.set_cancel_order("LIMIT")
                self.set_limit_market_order(symbol, positionside, modo_gestion)

            else:
                print(f"{self.indicator} Posición LONG ya tiene las reentradas correctas.\n")

        elif positionside == "SHORT" and short_amt > 0 and modo_gestion == "REENTRADAS":
            orders = self.get_current_open_orders("STOP_MARKET")
            list_rs = orders["short_amt_orders"]

            if not list_rs and short_amt == monedas_iniciales:
                print(f"{self.indicator} Posición SHORT no tiene reentradas. Colocando...\n")
                self.set_limit_market_order(symbol, positionside, modo_gestion)

            elif cant_ree_real > len(list_rs) and short_amt == monedas_iniciales:
                print(f"{self.indicator} Ajustando la posición SHORT a la cantidad de reentradas correctas...\n")
                self.set_cancel_order("LIMIT")
                self.set_limit_market_order(symbol, positionside, modo_gestion)

            else:
                print(f"{self.indicator} Posición SHORT ya tiene las reentradas correctas.\n")

    # Metodo para gestion de posiciones abiertas
    def monitor_open_positions(self):
        symbol = self.symbol
        positionside = self.positionside
        modo_gestion = self.modo_gestion

        self.dynamic_sl_manager(symbol, positionside)
        self.dynamic_tp_manager(symbol, positionside)
        if self.modo_gestion == "REENTRADAS" or self.modo_gestion == "SNOW BALL":
            self.dynamic_reentradas_manager(symbol, positionside, modo_gestion)

    # Metodo para gestionar las ordenes pendientes
    def monitor_pending_order_2(self):
        symbol = self.symbol
        positionside = self.positionside
        typee = self.type
        max_wait = self.time_wait
        current_time = time.time()

        # 1️⃣ Cancelar si ya se superó el TP sin ejecutar
        entry_price = self.long if positionside == "LONG" else self.short
        sl_price = self.precio_sl
        rr_ratio = self.ratio
        tp_distance = abs(entry_price - sl_price) * rr_ratio
        if positionside == "LONG":
            tp_price = mgo.redondeo((entry_price + tp_distance), self.pip_price)
        else:
            tp_price = mgo.redondeo((entry_price - tp_distance), self.pip_price)

        if (positionside == "LONG" and self.last_price >= tp_price) or \
        (positionside == "SHORT" and self.last_price <= tp_price):
            print(f"⚠️ El precio actual {self.last_price}, cruza el TP {tp_price} sin ejecutar la orden. Cancelando...")
            self.set_cancel_order(typee)
            return

        # 2️⃣ Cancelar por tiempo excedido
        elapsed = current_time - self.orden_timestamp
        if elapsed > max_wait:
            print(f"⏳ Orden pendiente en {positionside} superó {max_wait}seg → Cancelando.")
            self.set_cancel_order(typee)
            return

    # Metodo maestro para monitorear el activo y decidir acciones
    def master_monitor(self, symbol: str=None, positionside: str=None):
        symbol = symbol or self.symbol
        positionside = positionside or self.positionside
        typee = self.type
        seg = self.segundos_monitoreo
        interval = self.temporalidad

        MAX_REQUESTS_PER_MINUTE = 60
        request_count = 0
        start_time = time.time()

        while True:
            if request_count >= MAX_REQUESTS_PER_MINUTE:
                elapsed_time = time.time() - start_time
                if elapsed_time < 60:
                    sleep_time = 60 - elapsed_time
                    print(f"⏳ Esperando {sleep_time:.2f} segundos para evitar bloqueos...")
                    time.sleep(sleep_time)
                request_count = 0
                start_time = time.time()

            try:
                # Obtener la última vela y actualizar last_price
                ult_vela = self.get_last_candles(symbol, interval)
                self.last_price = float(ult_vela[0]["close"])  # Actualiza el último precio conocido
                vela = mgo.conv_pdataframe(ult_vela)
                #print(f"Datos de vela cruda:\n{ult_vela}\n{self.last_price}")
                print(f"{self.indicator} MASTER - Datos del DataFrame:\n{vela.tail(1).to_string(index=True)}")

                if self.orden_timestamp is not None:
                    order_time = datetime.fromtimestamp(self.orden_timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n{self.indicator} MASTER - Datos de ultima señal de apertura:\n{order_time} - {self.enter_params}\n")

                positions = self.get_open_position()
                print(f"{self.indicator} MASTER - 📊 Posiciones abiertas en {symbol}:\n🔴 SHORT: {positions["SHORT"]}\n🟢 LONG: {positions["LONG"]}")
                print(f"{self.indicator} MASTER - Posiciones abiertas: {positions}.\nMonitoreando posición 🔍 {positionside.upper()}, cada {seg} segundos.\n")

                pending_orders = self.get_current_open_orders(typee)
                #print(f"{self.indicator} MASTER - 📊 Ordenes pendientes en {symbol}:\n🔴 SHORT: {pending_orders["SHORT"]}\n🟢 LONG: {pending_orders["LONG"]}")
                print(f"{self.indicator} MASTER - 📊 Ordenes pendientes en {symbol}:\n🔴 SHORT: {pending_orders["short_price_ordersId"]}\n🟢 LONG: {pending_orders["long_price_ordersId"]}\nMonitoreando Orden 🔍 {positionside.upper()}, cada {seg} segundos.\n")

                # Control para posiciones abiertas
                if float(positions.get(positionside, {}).get("positionAmt", 0)) > 0:
                    # Si hay posición, llamamos al especialista en gestionar posiciones
                    self.monitor_open_positions()

                # Control para ordenes pendientes
                elif float(pending_orders.get(positionside, 0)) > 0:
                    # Si no hay posición PERO hay orden, llamamos al especialista en gestionar órdenes
                    self.monitor_pending_order()

                else: # Si no hay posición ni orden, iniciamos la estrategia para abrir posición
                    print(f"{self.indicator} MASTER - No hay posición abierta en {positionside}.\n⌛ Esperando señal para abrir posición...")
                    if not self.modo_operacion == "CARDIACO":
                        self.check_strategy_loop()
                    else:
                        print("🧘 Modo CARDIACO: no se abrirán nuevas posiciones automáticamente.")

                request_count += 1

            except Exception as e:
                print(f"{self.indicator} ❌ MASTER - Error obteniendo posiciones: {e}\n")
                traceback.print_exc()

            time.sleep(seg)

    # Metodo para obtener las ordenes abiertas
    def get_current_open_orders(self, type: str = None):
        # Variables de control
        symbol = self.symbol
        type = type.upper()
        """ A continuación se muestran los tipos admitidos para type
                LIMIT: Limit Order
                MARKET: Market Order
                STOP_MARKET: Stop Market Order
                TAKE_PROFIT_MARKET: Take Profit Market Order
                STOP: Stop Limit Order
                TAKE_PROFIT: Take Profit Limit Order
                TRIGGER_LIMIT: Stop Limit Order with Trigger
                TRIGGER_MARKET: Stop Market Order with Trigger
                TRAILING_STOP_MARKET: Trailing Stop Market Order
                TRAILING_TP_SL: Trailing TakeProfit or StopLoss
        """
        params = {
                "symbol": symbol,
                "type": type,
                }
        data = self._send_request("GET", "/openApi/swap/v2/trade/openOrders", params)

        long_ordersId = []
        long_amt_ordersId = []
        long_price_ordersId = []
        short_ordersId = []
        short_amt_ordersId = []
        short_price_ordersId = []

        #pprint.pprint(data["data"]["orders"])

        for order in data.get("data", {}).get("orders", []):
            if symbol and order.get("symbol") != symbol:
                continue

            if type == "LIMIT":
                price_ordersId = order["price"]
            else:
                price_ordersId = order["stopPrice"]

            if order.get("positionSide") == "LONG":
                long_ordersId.append(order["orderId"])
                long_amt_ordersId.append(float(order["origQty"]))
                long_price_ordersId.append(float(price_ordersId))
            elif order.get("positionSide") == "SHORT":
                short_ordersId.append(order["orderId"])
                short_amt_ordersId.append(float(order["origQty"]))
                short_price_ordersId.append(float(price_ordersId))

        if type == "STOP_MARKET":
            mensaje = "STOP LOSS"
        elif type == "TAKE_PROFIT":
            mensaje = "TAKE PROFIT LIMIT"
        elif type == "TAKE_PROFIT_MARKET":
            mensaje = "TAKE PROFIT MARKET"
        elif type == "LIMIT":
            mensaje = "Total ordenes LIMIT"
        elif type == "TRIGGER_MARKET":
            mensaje = "Total ordenes TRIGGER"
        else:
            mensaje = "Total ordenes"

        print(f"🟢 {mensaje} LONG: {len(long_ordersId)}")
        if len(long_ordersId) == 0:
            print("No hay órdenes abiertas en LONG.")
        else:
            for ordersId, price_orders, amt_ordersId in zip(long_ordersId, long_price_ordersId, long_amt_ordersId):
                print(f"Orden pendiente: {ordersId}, {price_orders}, {amt_ordersId}")

        print(f"🔴 {mensaje} SHORT: {len(short_ordersId)}")
        if len(short_ordersId) == 0:
            print("No hay órdenes abiertas en SHORT.")
        else:
            for ordersId, price_orders, amt_ordersId in zip(short_ordersId, short_price_ordersId, short_amt_ordersId):
                print(f"Orden pendiente: {ordersId}, {price_orders}, {amt_ordersId}")

        return {
                "symbol": symbol,
                "long_orders": long_ordersId,
                "long_amt_orders": long_amt_ordersId,
                "long_price_ordersId": long_price_ordersId,
                "LONG": len(long_ordersId),
                "short_orders": short_ordersId,
                "short_amt_orders": short_amt_ordersId,
                "short_price_ordersId": short_price_ordersId,
                "SHORT": len(short_ordersId)
                }

    # Metodo para obtener información de la ultima vela
    def get_last_candles(self, symbol: str, interval: str = "1m", limit: int = 1):
        url = f"{self.base_url}/openApi/swap/v3/quote/klines?symbol={symbol}&interval={interval}&limit={limit}"

        while True:  # 🔄 Bucle infinito hasta obtener velas válidas
            try:
                response = self.session.get(url, timeout=10)

                if response.status_code != 200:
                    print(f"❌ ERROR - Código de estado HTTP: {response.status_code}")
                    time.sleep(2)
                    continue

                try:
                    data = response.json()
                except requests.exceptions.JSONDecodeError:
                    #print("❌ ERROR - No se pudo decodificar la respuesta JSON.")
                    time.sleep(2)
                    continue

                candles = data.get("data", [])
                if not isinstance(candles, list) or len(candles) < limit:
                    #print("❌ ERROR - No se encontraron suficientes datos de velas.")
                    time.sleep(2)
                    continue

                # ✅ Insertar metadata (símbolo y temporalidad)
                #candles.insert(0, {"symbol": symbol, "temporalidad": interval})

                return candles  # 🔥 Solo retornamos si todo está OK

            except Exception as e:
                print(f"❌ ERROR - Excepción inesperada en get_last_candles: {e}")
                time.sleep(2)
                continue

    # Metodo para obtener el precio en tiempo real con websocket
    def start_websocket(self,):
        # Variables de control
        symbol = self.symbol
        interval = self.temporalidad

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
                    #print(vela)
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
                    """
                    Ejemplo de Información vela que proviene de MONITOR y WEBSOCKET para BingX: MON-USDT@kline_temporaidad:
                    websocket= [{'c': '2.9983', 'o': '2.9963', 'h': '2.9999', 'l': '2.9963', 'v': '45268', 'T': 1750033320000}]
                    HTTP= [{'close': '3.0276', 'high': '3.0276', 'low': '3.0221', 'open': '3.0230', 'time': 1750028760000, 'volume': '5195.00'}]
                    """
                    print(f"\n{self.indicator} WEBSOCKET - Exchange: {self.exchange}, Symbol: {symbol}, Temporalidad: {interval}, Dirección de operación: {self.positionside}, Ultimo precio: {self.last_price}")
                    print(f"{self.indicator} WEBSOCKET - Información de vela actual:\n{self.df_vela}")

                    # Se evalua la entrada con websocket
                    df_temp = pd.concat([self.df_dynamic, self.df_vela])
                    resultado = self.estrategia_instancia.evaluar_entrada(df_temp)
                    if resultado.get("estrategia_valida", False):
                        self.estrategia_instancia.reiniciar_condiciones()
                        self.enter_params = resultado
                        self.precio_sl = resultado.get("stop_loss", None)
                        self.monedas = resultado.get("cant_mon", None)
                        if self.positionside == "LONG":
                            self.long = resultado.get("precio_entrada", None)
                        else: # self.positionside == "SHORT"
                            self.short = resultado.get("precio_entrada", None)
                        print("✅ señal de apertura detectada. Cambiando a monitoreo.")
                        ws.close()  # Cerrar WebSocket para volver al monitoreo de la posición
                        return
                    else: # No hay señal, se reinician las condiciones
                        self.estrategia_instancia.reiniciar_condiciones()
                        ws.close()  # Cerrar WebSocket para volver a la evaluación de la estrategia
                        return


            except Exception as e:
                print(f"{self.indicator} WEBSOCKET -❌ Error procesando mensaje: {e}")
                #traceback.print_exc()

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
        self.ws.run_forever() # self.ws.run_forever(ping_interval=30)  # Envia Ping cada 30 segundos

    # Metodo para realizar la reconeción de la websocket
    def _reconnect(self):
        # Intenta reconectar el WebSocket después de 5 segundos
        time.sleep(5)
        print(f"♻️ Reintentando WebSocket {self.indicator} conexión...")
        threading.Thread(target=self.start_websocket).start()

    # Estrategia de entrada al mercado
    def check_strategy_loop(self):
        print(f"{self.indicator} CHECK STRATEGY - 🎯 velas Iniciando bucle para evaluación de estrategia")

        while True:
            try:
                # Extracción de datos para el dataframe dinamico
                seconds = mgo.temporalidad_a_segundos(self.temporalidad)
                now = time.time()

                # Si la estrategia envio señal de entrada
                if self.enter_params.get("estrategia_valida", False):

                    # Llamada a la función para colocar la orden de mercado o limit
                    self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, self.enter_params)
                    self.api_secretorden_timestamp = time.time()
                    #orden_timestamp = pd.to_datetime(orden_timestamp, unit='ms')
                    #self.orden_timestamp = calendar.timegm(orden_timestamp.utctimetuple())
                    if self.positionside == "LONG":
                        self.precio_entrada = self.long
                    else: # self.positionside == "SHORT"
                        self.precio_entrada = self.short
                    print(f"{self.indicator} CHECK STRATEGY -📉 Señal activada, ejecutando entrada en {self.positionside} 🔥💰\nPrecio de entrada {self.precio_entrada}, Precio de Stop loss {self.precio_sl}\n")
                    time.sleep(3)

                    # Verifica si la posición se abrió correctamente
                    positions = self.get_open_position()
                    if self.positionside == "LONG":
                        long_amt = float(positions["LONG"].get("positionAmt", 0))
                        if long_amt > 0:
                            self.position_opened_by_strategy = True
                            self.enter_params = {"estrategia_valida": False} # Reinicia la señal de entrada
                            self.precio_sl = None
                            self.long = None
                            self.short = None
                            print(f"{self.indicator} CHECK STRATEGY -✅ Posición abierta en {self.positionside}. MASTER MONITOR.")
                            return
                    elif self.positionside == "SHORT":
                        short_amt = float(positions["SHORT"].get("positionAmt", 0))
                        if short_amt > 0:
                            self.position_opened_by_strategy = True
                            self.enter_params = {"estrategia_valida": False} # Reinicia la señal de entrada
                            self.precio_sl = None
                            self.long = None
                            self.short = None
                            print(f"{self.indicator} CHECK STRATEGY -✅ Posición abierta en {self.positionside}. MASTER MONITOR.")
                            return

                    # Verifica si existen ordenes abiertas
                    open_order = self.get_current_open_orders("LIMIT")
                    if (self.positionside == "LONG" and open_order["LONG"] > 0) or (self.positionside == "SHORT" and open_order["SHORT"] > 0):
                        self.pending_order = True
                        self.enter_params = {"estrategia_valida": False} # Reinicia la señal de entrada
                        self.precio_sl = None
                        self.long = None
                        self.short = None
                        print(f"{self.indicator} CHECK STRATEGY -✅ Orden pendiente en {self.positionside}. Cambiando a MASTER MONITOR.")
                        return

                if self.df is None or (now - self.last_df_update > seconds):
                    try: #  Verifica que no haya errores en el Dataframe
                        nuevo_df = mgo.conv_pdataframe(self.get_last_candles(self.symbol, self.temporalidad, self.cant_candles))
                        if nuevo_df is None or nuevo_df.empty:
                            raise ValueError("DataFrame vacío o None recibido.")
                        self.df = nuevo_df
                        # Detectar si el tiempo está en índice o en columna
                        if "Time" in self.df.columns:
                            t = pd.to_datetime(self.df["Time"].iloc[-1], unit="ms")
                        else:
                            t = self.df.index[-1].to_pydatetime()                        
                        self.last_df_update = calendar.timegm(t.utctimetuple())
                    except Exception as e:
                        print(f"{self.indicator} CHECK STRATEGY - ❌ Error actualizando DataFrame: {e}")
                        traceback.print_exc()
                        time.sleep(3)
                        continue  # Reintenta rápido sin esperar nueva vela

                    self.df_dynamic = self.df.iloc[:-1]
                    if "Time" in self.df_dynamic.columns:
                        df_ahora = self.df_dynamic["Time"].iloc[-1]
                    else:
                        df_ahora = self.df_dynamic.index[-1]

                    if self._ultima_vela != df_ahora:
                        print(f"{self.indicator} CHECK STRATEGY - 🔍 Nueva vela detectada")
                        self._ultima_vela = df_ahora

                        # Se instancia la estrategia
                        self.estrategia_instancia = self.estrategia(
                                                                    self.df_dynamic,
                                                                    self.last_price,
                                                                    self.avg_price,
                                                                    self.decimales_price,
                                                                    self.indicator,
                                                                    self.positionside,
                                                                    self.monto_sl
                                                                    )

                        self.estrategia_instancia._calcular_indicadores()
                        self.estrategia_instancia.condiciones_sin_websocket()
                        #self.start_websocket() # Inicia el WebSocket para ensayos
                        # Si requiere websocket, se inicia la conexión
                        if self.estrategia_instancia.requiere_websocket():
                            if self.estrategia_instancia.activar_websocket():
                                self.estrategia_instancia.incrementar_ventana()
                                self.start_websocket()
                                print(f"{self.indicator} CHECK STRATEGY - Activando WebSocket para {self.symbol} con temporalidad {self.temporalidad} dirección {self.positionside} ...")

                        else: # Si no requiere websocket, se evalua la entrada solo con indicadores
                            resultado = self.estrategia_instancia.evaluar_entrada()
                            if resultado.get("estrategia_valida", False):
                                self.estrategia_instancia.reiniciar_condiciones()
                                self.enter_params = resultado
                                self.precio_sl = resultado.get("stop_loss", None)
                                self.monedas = resultado.get("cant_mon", None)
                                if self.positionside == "LONG":
                                    self.long = resultado.get("precio_entrada", None)
                                else: # self.positionside == "SHORT"
                                    self.short = resultado.get("precio_entrada", None)
                                print("✅ señal de apertura detectada. Cambiando a monitoreo.")

            except Exception as e:
                print(f"{self.indicator} CHECK STRATEGY - ❌ Error: {e}\n")
                traceback.print_exc()
            time.sleep(1.0)


    """ METODOS PARA EJECUTAR OPERACIONES EN LA CUENTA """

    # Metodo para generar la firma HMAC SHA256 requerida por la API
    def _send_request(self, method: str, endpoint: str, params: dict) -> dict:
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        timestamp = self._get_timestamp()
        params_str = f"{param_str}&timestamp={timestamp}" if param_str else f"timestamp={timestamp}"

        signature = self._get_signature(params_str)

        url = f"{self.base_url}{endpoint}?{params_str}&signature={signature}"
        headers = {"X-BX-APIKEY": self.api_key}

        response = requests.request(method, url, headers=headers)
        #data = response.json()
        #pprint.pprint({"DEBUG - Respuesta API": data})

        return response.json()

    # Metodo para colocar el take profit
    def set_take_profit(self, symbol: str, positionside: str, quantity: float, stop_price: float,
                        working_type: str = "CONTRACT_PRICE", order_type: str = "LIMIT") -> dict:
        # Ajustando decimales
        stop_price = mgo.redondeo(stop_price, self.pip_precio())
        quantity = mgo.redondeo(quantity, self.pip_moneda())

        side = "SELL" if positionside == "LONG" else "BUY"

        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": positionside,
            "type": None,
            "quantity": quantity,
            "stopPrice": stop_price,
            "workingType": working_type,
        }
        if order_type == "LIMIT":
            params["type"] = "TAKE_PROFIT"
            params["price"] = stop_price
        else: # order_type == "MARKET"
            params["type"] = "TAKE_PROFIT_MARKET"

        return self._send_request("POST", "/openApi/swap/v2/trade/order", params)

    # Metodo para colocar el stop loss
    def set_stop_loss(self, symbol: str, positionside: str, quantity: float,
                        stop_price: float, working_type: str = "CONTRACT_PRICE") -> dict:
        # Ajustando decimales
        stop_price = mgo.redondeo(stop_price, self.pip_precio())
        quantity = mgo.redondeo(quantity, self.pip_moneda())

        side = "SELL" if positionside == "LONG" else "BUY"

        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": positionside,
            "type": "STOP_MARKET",
            "quantity": quantity,
            "stopPrice": stop_price,
            "workingType": working_type,
        }

        return self._send_request("POST", "/openApi/swap/v2/trade/order", params)

    # Metodo para colocar una orden de mercado o limit
    def _limit_market_order(self, symbol: str, positionside: str, quantity: float, price: float = None,
                            type: str = "MARKET", working_type: str = "CONTRACT_PRICE") -> dict:
        """"
        Ejemplos de uso:
        positionSide="LONG" con side="BUY" → Abre una posición larga.
        positionSide="LONG" con side="SELL" → Cierra una posición larga.
        positionSide="SHORT" con side="SELL" → Abre una posición corta.
        positionSide="SHORT" con side="BUY" → Cierra una posición corta.
        
        OPCIONES DE TYPE:
        
        LIMIT: Limit Order
        MARKET: Market Order
        TRAILING_STOP_MARKET: Trailing Stop Market Order
        TRAILING_TP_SL: Trailing TakeProfit or StopLoss
        
        Obligatorio uso de stopPrice
        STOP_MARKET: Stop Market Order
        TAKE_PROFIT_MARKET: Take Profit Market Order
        STOP: Stop Limit Order
        TAKE_PROFIT: Take Profit Limit Order
        TRIGGER_LIMIT: Stop Limit Order with Trigger
        TRIGGER_MARKET: Stop Market Order with Trigger
        """
        # Ajustando decimales
        price = mgo.redondeo(price, self.pip_precio())
        quantity = mgo.redondeo(quantity, self.pip_moneda())

        side = "BUY" if positionside == "LONG" else "SELL"

        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": positionside,
            "type": type,
            "quantity": quantity,
            "price": price,
            "workingType": working_type,
        }
        if type == "TRIGGER_MARKET":
            params["stopPrice"] = price

        return self._send_request("POST", "/openApi/swap/v2/trade/order", params)

    # Metodo para crear una posicion limit
    def set_limit_market_order(self, symbol: str, positionside: str, modo_gestion: str, diccionario: dict = None):
        # Variables generales
        type = self.type # "LIMIT" o "MARKET" o "TRIGGER_MARKET"
        monto_sl = self.monto_sl
        cant_ree = self.cant_ree
        dist_ree = self.dist_ree
        monedas = self.monedas
        usdt = self.usdt
        porcentaje_vol_ree = self.porcentaje_vol_ree
        gestion_vol = self.gestion_vol
        # Estas variables vienen de la funcion strategy
        precio = diccionario["precio_entrada"]
        precio_sl = diccionario["stop_loss"]

        if modo_gestion == "RATIO BENEFICIO/PERDIDA":
            # Se calcula el volumen de la entrada
            if positionside == "LONG":
                monedas = PosLong.vol_monedas(monto_sl, precio, precio_sl)
            elif positionside == "SHORT":
                monedas = PosShort.vol_monedas(monto_sl, precio, precio_sl)
            # Se ejecuta la entrada
            self._limit_market_order(
                symbol = symbol,
                positionside = positionside,
                quantity = monedas,
                price = precio,
                type = type
                )
            return self.get_current_open_orders("LIMIT")

        elif modo_gestion == "REENTRADAS":

            positions = self.get_open_position()
            long_amt = float(positions["LONG"].get("positionAmt", 0))
            short_amt = float(positions["SHORT"].get("positionAmt", 0))

            if positionside == "LONG":
                if long_amt == 0:
                    datos = self.monedas_de_entrada(positionside)
                    monedas = datos["monedas"]

                    self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = monedas,
                    price = precio,
                    type = type
                    )

                    positions = self.get_open_position()
                precio = float(positions["LONG"]["avgPrice"])
                monedas = float(positions["LONG"]["positionAmt"])
                data = PosLong.recompras(precio, monto_sl, cant_ree, dist_ree, monedas, porcentaje_vol_ree, usdt, gestion_vol)

            elif positionside == "SHORT":
                if short_amt== 0:
                    datos = self.monedas_de_entrada(positionside)
                    monedas = datos["monedas"]

                    self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = monedas,
                    price = precio,
                    type = type
                    )

                    positions = self.get_open_position()
                precio = float(positions["SHORT"]["avgPrice"])
                monedas = float(positions["SHORT"]["positionAmt"])
                data = PosShort.recompras(precio, monto_sl, cant_ree, dist_ree, monedas, porcentaje_vol_ree, usdt, gestion_vol)

            # Datos del diccionario para armar las ordenes
            quantity: list = data["quantitys"]
            price: list = data["prices"]
            num_orders = 0

            for quantity, price in zip(data["quantitys"], data["prices"]):
                self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = quantity,
                    price = price,
                    type = "LIMIT"
                )
                num_orders += 1
                print(f"Orden {num_orders} enviada: {positionside} => {price} @ {quantity}")
                time.sleep(1)  # Espera 1 segundo entre cada orden
            return self.get_current_open_orders("LIMIT")

        else: # modo_gestion == "SNOW BALL"

            positions = self.get_open_position()
            long_amt = float(positions["LONG"].get("positionAmt", 0))
            short_amt = float(positions["SHORT"].get("positionAmt", 0))

            if positionside == "LONG":
                if long_amt == 0:
                    # 1ra entrada
                    if monedas == 0 and usdt == 0:
                        precio_sl = precio * (100 - dist_ree) / 100
                        monedas = PosLong.vol_monedas(monto_sl, precio, precio_sl)
                        monedas = monedas / cant_ree

                    elif monedas == 0 and usdt != 0:
                        monedas = usdt / precio

                    self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = monedas,
                    price = precio,
                    type = type
                    )
                    # resto de entradas
                    positions = self.get_open_position()
                precio = float(positions["LONG"]["avgPrice"])
                monedas = float(positions["LONG"]["positionAmt"])
                data = PosLong.snow_ball(precio, monto_sl, cant_ree, dist_ree, monedas, porcentaje_vol_ree, usdt, gestion_vol)

            elif positionside == "SHORT":
                if short_amt == 0:
                    # 1ra entrada
                    if monedas == 0 and usdt == 0:
                        precio_sl = precio * (100 + dist_ree) / 100
                        monedas = PosShort.vol_monedas(monto_sl, precio, precio_sl)
                        monedas = monedas / cant_ree

                    elif monedas == 0 and usdt != 0:
                        monedas = usdt / precio

                    self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = monedas,
                    price = precio,
                    type = type
                    )

                    # resto de entradas
                    positions = self.get_open_position()
                precio = float(positions["SHORT"]["avgPrice"])
                monedas = float(positions["SHORT"]["positionAmt"])
                data = PosShort.snow_ball(precio, monto_sl, cant_ree, dist_ree, monedas, porcentaje_vol_ree, usdt, gestion_vol)

            # Datos del diccionario para armar las ordenes
            quantity: list = data["quantitys"]
            price: list = data["prices"]
            num_orders = 0

            for quantity, price in zip(data["quantitys"], data["prices"]):
                self._limit_market_order(
                    symbol = symbol,
                    positionside = positionside,
                    quantity = quantity,
                    price = price,
                    type = "TRIGGER_MARKET"
                )
                num_orders += 1
                print(f"Orden {num_orders} enviada: {positionside} => {price} @ {quantity}")
                time.sleep(1)  # Espera 1 segundo entre cada orden
            return self.get_current_open_orders("TRIGGER_MARKET")

    # Metodo para cancelar una orden
    def _cancel_order(self, symbol: str, order_id: int = None):
        params = {
            "orderId": order_id, #requerido
            "symbol": symbol
            }
        print(f"Ordenid: {order_id} cancelada")
        return self._send_request("DELETE", "/openApi/swap/v2/trade/order", params)

    # Metodo para cancelar todas las ordenes abiertas por positionSide
    def set_cancel_order(self, type: str = None):
        # Variables de control
        symbol = self.symbol
        positionside = self.positionside

        if positionside == "LONG":
            if self.get_current_open_orders(type)["long_total"] == 0:
                return
            else:
                orders = self.get_current_open_orders(type)["long_orders"]
                for order in orders:
                    self._cancel_order(symbol, order)
                    time.sleep(1)
        elif positionside == "SHORT":
            if self.get_current_open_orders(type)["short_total"] == 0:
                return
            else:
                orders = self.get_current_open_orders(type)["short_orders"]
                for order in orders:
                    self._cancel_order(symbol, order)
                    time.sleep(1)
        else:
            print("No se ha especificado un positionSide válido. Debe ser 'LONG' o 'SHORT'.")

        return self.get_current_open_orders(type)
