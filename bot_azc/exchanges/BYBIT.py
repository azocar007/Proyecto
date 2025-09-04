import os
import time
import threading
import hmac
import hashlib
import json
# import gzip
# import io
import psutil
from pybit.unified_trading import HTTP
from pybit.unified_trading import WebSocket as PybitWebSocket

import Modos_de_gestion_operativa as mgo

class Bybit:
    def __init__(self, dict_config: dict):
        self.dict_config = dict_config
        self.nombre_bot = str(dict_config.get("nombre_bot", "BybitBot"))
        print(f"[{self.nombre_bot}] Inicializando...")

        # --- API Credentials & Session ---
        self.api_key = str(dict_config.get("api_key", "TlBcrKNc5NN1b3UDhU"))
        self.api_secret = str(dict_config.get("api_secret", "Arlzmsc840ZAzacj1vbaNkQEAx5z9xCqKCt2"))
        self.testnet = bool(dict_config.get("testnet", True))
        try:
            self.session = HTTP(testnet=self.testnet, api_key=self.api_key, api_secret=self.api_secret)
            print(f"[{self.nombre_bot}] Sesión HTTP para {'Testnet' if self.testnet else 'Mainnet'} creada.")
        except Exception as e:
            print(f"[{self.nombre_bot}] CRITICAL: Fallo al inicializar sesión HTTP: {e}")
            raise 

        # --- Trading Parameters ---
        self.symbol = str(dict_config.get("symbol", "BTC")).upper() + "USDT"
        self.positionside = str(dict_config.get("positionside", "LONG")).upper() 
        self.modo_cobertura = bool(dict_config.get("modo_cobertura", False)) 
        
        # --- WebSocket Configuration ---
        self.ws_url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        self.ws = None 
        self.ws_running = False 
        self.ws_should_run = True 
        self.ws_reconnect_delay = 10 
        self.last_price = None 
        self.position_opened_by_strategy = False 

        # --- Strategy Entry Signal Prices ---
        self.precio_entrada_long = float(dict_config.get("precio_entrada_long", 0)) 
        self.precio_entrada_short = float(dict_config.get("precio_entrada_short", 0))

        # --- Order and Position Management Settings ---
        self.modo_gestion = str(dict_config.get("modo_gestion_de_ordenes", "GAFAS")).upper() 
        self.tipo_orden_entrada = str(dict_config.get("tipo_de_orden_entrada", "MARKET")).upper()
        self.apalancamiento = int(dict_config.get("apalancamiento", 10))
        # self.balance_total_USDT = float(dict_config.get("balance_total_USDT", 1000.0)) # For reference
        self.riesgo_por_operacion_porcentaje = float(dict_config.get("riesgo_por_operacion_porcentaje", 1.0))
        
        self.monto_sl_base = float(dict_config.get("monto_sl_base", 10.0)) 
        self.cant_ree = int(dict_config.get("cant_ree", 0)) 
        self.dist_ree = float(dict_config.get("dist_ree", 1.0)) 
        self.usdt_entrada_inicial = float(dict_config.get("usdt_entrada_inicial", 0)) 
        self.porcentaje_vol_ree = int(dict_config.get("porcentaje_vol_ree", 0)) 
        self.gestion_vol = str(dict_config.get("gestion_vol", "MARTINGALA")).upper() 
        
        self.gestion_take_profit = str(dict_config.get("gestion_take_profit", "RATIO BENEFICIO/PERDIDA")).upper()
        self.ratio_beneficio_perdida = float(dict_config.get("ratio_beneficio_perdida", 1.5)) 
        self.tipo_orden_sl_tp = str(dict_config.get("tipo_orden_sl_tp", "Market")).upper() 
        
        self.temporalidad = str(dict_config.get("temporalidad", "1m")) 

        # --- Internal State & Calculation Variables ---
        self.precio_entrada_referencia = float(dict_config.get("precio_entrada_referencia", 0)) 
        self.stop_loss_calculado = None 
        self.take_profit_calculado = None 
        self.cantidad_a_operar_inicial = float(dict_config.get("cantidad_a_operar_inicial", 0)) 
        
        self.estado_operacion = "IDLE" 
        self.id_orden_limit_entrada = None 
        self.max_intentos_orden = int(dict_config.get("max_intentos_orden", 3))
        # self.stop_loss_usdt_gafas = float(dict_config.get("stop_loss_usdt_gafas", self.monto_sl_base))

        # --- Instrument Info (populated by _get_instrument_info) ---
        self.inf_moneda_raw = None; self.pip_precio = None; self.min_usdt_compra = None; self.price_scale = None;
        self.cant_decimales_precio = 0; self.cant_decimales_moneda = 0; self.min_qty_compra = None;
        self.max_qty_compra = None; self.qty_step = None; self.inf_moneda_dict = {} 

        # --- mgo Instances ---
        self.PosLong = mgo.PosicionLong(); self.PosShort = mgo.PosicionShort()
        
        if self.cantidad_a_operar_inicial == 0 and self.usdt_entrada_inicial > 0 and self.precio_entrada_referencia > 0:
            self.cantidad_a_operar_inicial = self.usdt_entrada_inicial / self.precio_entrada_referencia
            print(f"[{self.nombre_bot}] Cantidad inicial calculada: {self.cantidad_a_operar_inicial} {self.symbol[:-4]} (USDT {self.usdt_entrada_inicial} @ {self.precio_entrada_referencia})")

        self._initial_exchange_setup() 
        self._get_instrument_info()    
        
        # self.riesgo_operacion_usdt = self.balance_total_USDT * (self.riesgo_por_operacion_porcentaje / 100) # Actual balance is fetched
        self.cant_ordenes_activas_max = int(dict_config.get("cant_ordenes_activas_max", 5)) 
        
        self._detener_monitor_mem = threading.Event()
        self._hilo_monitor_mem = None
        self.segundos_monitoreo_mem = int(dict_config.get("segundos_monitoreo_memoria", 0)) # Default 0 (disabled)

        print(f"[{self.nombre_bot}] Inicialización completa para {self.symbol}.")


    def _initial_exchange_setup(self):
        """Configura el modo de posición (One-Way/Hedge) y el apalancamiento en Bybit."""
        try:
            mode_to_set = 3 if self.modo_cobertura else 0
            self.session.switch_position_mode(category="linear",symbol=self.symbol, mode=mode_to_set)
            print(f"[{self.nombre_bot}] Modo de posición para {self.symbol} configurado a: {'Cobertura' if self.modo_cobertura else 'Unilateral'}.")
            self.session.set_leverage(category="linear", symbol=self.symbol, buyLeverage=str(self.apalancamiento), sellLeverage=str(self.apalancamiento))
            print(f"[{self.nombre_bot}] Apalancamiento para {self.symbol} configurado a: {self.apalancamiento}x.")
        except Exception as e:
            print(f"[{self.nombre_bot}] ERROR en _initial_exchange_setup ({self.symbol}): {e}")

    def _get_instrument_info(self):
        """Obtiene y almacena la información detallada del instrumento (símbolo) de Bybit."""
        try:
            response = self.session.get_instruments_info(category="linear", symbol=self.symbol)
            if response and response.get('retCode') == 0:
                instrument_list = response.get('result', {}).get('list', [])
                if instrument_list:
                    info = instrument_list[0]
                    self.inf_moneda_raw = info
                    self.pip_precio = info.get('priceFilter', {}).get('tickSize', '0.1') 
                    self.price_scale = info.get('priceScale', None) 
                    self.cant_decimales_precio = int(self.price_scale) if self.price_scale is not None else self._get_decimals_from_value(self.pip_precio)
                    
                    lsf = info.get('lotSizeFilter', {})
                    self.min_qty_compra = lsf.get('minOrderQty', '0.001') 
                    self.max_qty_compra = lsf.get('maxOrderQty', '1000000') 
                    self.qty_step = lsf.get('qtyStep', '0.001') 
                    self.cant_decimales_moneda = self._get_decimals_from_value(self.qty_step)
                    self.min_usdt_compra = lsf.get('minOrderValue', '1') 

                    self.inf_moneda_dict = {
                        "symbol": self.symbol, "pip_precio": self.pip_precio, "price_scale": self.price_scale,
                        "cant_decimales_precio": self.cant_decimales_precio, "min_qty_compra": self.min_qty_compra,
                        "max_qty_compra": self.max_qty_compra, "qty_step": self.qty_step,
                        "cant_decimales_moneda": self.cant_decimales_moneda, "min_usdt_compra": self.min_usdt_compra,
                        "baseCoin": info.get('baseCoin'), "quoteCoin": info.get('quoteCoin'), "status": info.get('status')
                    }
                    print(f"[{self.nombre_bot}] Info. de {self.symbol} cargada: PipPrecio={self.pip_precio}, QtyStep={self.qty_step}")
                    return
            print(f"[{self.nombre_bot}] ERROR _get_instrument_info: {response.get('retMsg') if response else 'No response'}")
        except Exception as e:
            print(f"[{self.nombre_bot}] EXCEPTION _get_instrument_info: {e}")
        
        if not self.pip_precio: self.pip_precio = '0.1'
        if self.price_scale is None : self.price_scale = str(self._get_decimals_from_value(self.pip_precio))
        if self.cant_decimales_precio == 0 and self.pip_precio : self.cant_decimales_precio = self._get_decimals_from_value(self.pip_precio)
        if not self.qty_step: self.qty_step = '0.001'
        if self.cant_decimales_moneda == 0 and self.qty_step : self.cant_decimales_moneda = self._get_decimals_from_value(self.qty_step)
        if not self.min_qty_compra: self.min_qty_compra = '0.001'
        print(f"[{self.nombre_bot}] WARNING: Usando valores por defecto para info. del instrumento {self.symbol} debido a error.")

    def _get_decimals_from_value(self, value_str: str) -> int:
        value_str = str(value_str); return len(value_str.split('.')[1].rstrip('0')) if '.' in value_str else 0
    def get_pip_precio(self) -> float: return float(self.pip_precio) if self.pip_precio else 0.0
    def get_cant_deci_precio(self) -> int: return int(self.price_scale) if self.price_scale is not None else 0
    def get_pip_moneda(self) -> float: return float(self.qty_step) if self.qty_step else 0.0
    def get_min_usdt(self) -> float: return float(self.min_usdt_compra) if self.min_usdt_compra else 0.0
    def get_min_qty(self) -> float: return float(self.min_qty_compra) if self.min_qty_compra else 0.0
    def get_instrument_details(self) -> dict: 
        if not self.inf_moneda_dict and self.inf_moneda_raw: self._get_instrument_info()
        return self.inf_moneda_dict
    
    def get_balance(self, account_type="UNIFIED", coin_symbol="USDT") -> dict:
        try:
            response = self.session.get_wallet_balance(accountType=account_type, coin=coin_symbol if account_type!="UNIFIED" else None) 
            if response and response.get('retCode') == 0:
                acc_list = response.get('result', {}).get('list', [])
                if not acc_list: return {}
                account_data = acc_list[0] 
                if account_type == "UNIFIED":
                    coins_data = account_data.get('coin', [])
                    for coin_info in coins_data:
                        if coin_info.get('coin') == coin_symbol:
                            return {"asset":coin_symbol, "balance":coin_info.get('walletBalance'), "availableMargin":coin_info.get('availableToWithdraw'), "equity":coin_info.get('equity')}
                    return {"asset":"ACCOUNT_TOTAL", "equity":account_data.get('totalEquity'), "availableMargin":account_data.get('totalAvailableBalance')}
                else: return {"asset":account_data.get('coin'),"balance":account_data.get('walletBalance'),"availableMargin":account_data.get('availableToWithdraw'), "equity":account_data.get('equity')}
            return {}
        except Exception as e: print(f"[{self.nombre_bot}] EXCEPTION get_balance: {e}"); return {}

    def get_current_leverage(self, symbol: str = None) -> float:
        target_symbol = symbol or self.symbol
        try:
            response = self.session.get_positions(category="linear", symbol=target_symbol)
            if response and response.get('retCode') == 0:
                pos_list = response.get('result', {}).get('list', [])
                if pos_list: return float(pos_list[0].get('leverage', self.apalancamiento))
            return float(self.apalancamiento) 
        except Exception: return float(self.apalancamiento)

    def set_leverage(self, leverage_val: int, symbol: str = None) -> dict:
        target_symbol = symbol or self.symbol
        try:
            response = self.session.set_leverage(category="linear", symbol=target_symbol, buyLeverage=str(leverage_val), sellLeverage=str(leverage_val))
            if response and response.get('retCode') == 0 and target_symbol == self.symbol: self.apalancamiento = leverage_val
            return response
        except Exception as e: return {"retCode": 99999, "retMsg": str(e), "result": {}}

    def _place_order_internal(self, symbol:str, order_type:str, side:str, qty_str:str, price_str:str=None, 
                                position_side_param:str=None, sl_price_str:str=None, tp_price_str:str=None, 
                                trigger_price_str:str=None, client_order_id:str=None, reduce_only_flag:bool=False) -> dict:
        params = {"category":"linear", "symbol":symbol, "side":side, "orderType":order_type, "qty":qty_str}
        if order_type == "Limit":
            if not price_str: return {"retCode":-1,"retMsg":"Precio para Limit requerido","result":{}}
            params["price"] = price_str
        
        target_pos_side_for_idx = position_side_param or self.positionside 
        if self.modo_cobertura:
            params["positionIdx"] = 1 if target_pos_side_for_idx == "LONG" else 2 if target_pos_side_for_idx == "SHORT" else 0
        else: params["positionIdx"] = 0
        
        if sl_price_str: params["stopLoss"] = sl_price_str
        if tp_price_str: params["takeProfit"] = tp_price_str
        if trigger_price_str: 
            params["triggerPrice"] = trigger_price_str
            # triggerDirection: 1-Rise, 2-Fall
            current_market_price = self.last_price # Use last known price for better trigger direction logic
            if current_market_price:
                if side == "Buy": # Buy Stop (trigger > market) or Buy TP (trigger < market)
                    params["triggerDirection"] = 1 if float(trigger_price_str) > current_market_price else 2
                else: # Sell Stop (trigger < market) or Sell TP (trigger > market)
                    params["triggerDirection"] = 2 if float(trigger_price_str) < current_market_price else 1
            else: # Fallback if no market price known (less accurate)
                params["triggerDirection"] = 1 if side == "Buy" else 2


        if reduce_only_flag: params["reduceOnly"] = True
        if client_order_id: params["orderLinkId"] = client_order_id
        
        # print(f"[{self.nombre_bot}] Enviando orden: {params}") # Verbose, uncomment for deep debug
        try: 
            response = self.session.place_order(**params)
            print(f"[{self.nombre_bot}] Respuesta orden ({response.get('retCode')} {response.get('retMsg')}): ID {response.get('result',{}).get('orderId')}")
            return response
        except Exception as e: 
            print(f"[{self.nombre_bot}] EXCEPTION _place_order_internal: {e}")
            return {"retCode": 99998, "retMsg": f"Excepción: {str(e)}", "result": {}}

    def _limit_market_order(self, symbol:str, positionside:str, quantity:float, price:float=None, order_type_param:str="MARKET", 
                            client_order_id:str=None, sl_val:float=None, tp_val:float=None) -> dict:
        order_side = "Buy" if positionside == "LONG" else "Sell"
        if not self.qty_step or not self.pip_precio: self._get_instrument_info() 
        if not self.qty_step or not self.pip_precio: return {"retCode":-1,"retMsg":"Falta info precisión en _limit_market_order","result":{}}
        
        qty_str = mgo.redondeo(quantity, self.qty_step, self.cant_decimales_moneda, "str")
        price_str = mgo.redondeo(price, self.pip_precio, self.cant_decimales_precio, "str") if order_type_param.upper() == "LIMIT" and price else None
        sl_price_str = mgo.redondeo(sl_val, self.pip_precio, self.cant_decimales_precio, "str") if sl_val else None
        tp_price_str = mgo.redondeo(tp_val, self.pip_precio, self.cant_decimales_precio, "str") if tp_val else None
        
        return self._place_order_internal(symbol, order_type_param.upper(), order_side, qty_str, price_str, positionside, 
                                        sl_price_str, tp_price_str, None, client_order_id, False)

    def set_take_profit(self, symbol:str, positionside:str, quantity:float, stop_price:float, order_type:str="Market", 
                        client_order_id:str=None, reduce_only:bool=True) -> dict: 
        tp_side = "Sell" if positionside == "LONG" else "Buy"
        if not self.qty_step or not self.pip_precio: return {"retCode":-1,"retMsg":"Falta info precisión TP","result":{}}
        qty_str = mgo.redondeo(quantity, self.qty_step, self.cant_decimales_moneda, "str")
        tp_price_str = mgo.redondeo(stop_price, self.pip_precio, self.cant_decimales_precio, "str")
        limit_price_str = tp_price_str if order_type.upper() == "LIMIT" else None
        cid = client_order_id or f"tp_{symbol[:3].lower()}{positionside[0].lower()}_{int(time.time()*100)%10000}"
        return self._place_order_internal(symbol, order_type.upper(), tp_side, qty_str, limit_price_str, positionside, 
                                        None, None, tp_price_str, cid, reduce_only)

    def set_stop_loss(self, symbol:str, positionside:str, quantity:float, stop_price:float, order_type:str="Market", 
                    client_order_id:str=None, reduce_only:bool=True) -> dict:
        sl_side = "Sell" if positionside == "LONG" else "Buy"
        if not self.qty_step or not self.pip_precio: return {"retCode":-1,"retMsg":"Falta info precisión SL","result":{}}
        qty_str = mgo.redondeo(quantity, self.qty_step, self.cant_decimales_moneda, "str")
        sl_price_str = mgo.redondeo(stop_price, self.pip_precio, self.cant_decimales_precio, "str")
        limit_price_str = sl_price_str if order_type.upper() == "LIMIT" else None
        cid = client_order_id or f"sl_{symbol[:3].lower()}{positionside[0].lower()}_{int(time.time()*100)%10000}"
        return self._place_order_internal(symbol, order_type.upper(), sl_side, qty_str, limit_price_str, positionside, 
                                        None, None, sl_price_str, cid, reduce_only)

    def _cancel_order(self, symbol:str, order_id:str=None, client_order_id:str=None) -> dict:
        if not order_id and not client_order_id: return {"retCode":-1,"retMsg":"ID de orden requerido para cancelar.","result":{}}
        params = {"category":"linear", "symbol":symbol}
        if order_id: params["orderId"] = order_id
        if client_order_id: params["orderLinkId"] = client_order_id
        try: return self.session.cancel_order(**params)
        except Exception as e: return {"retCode":99997,"retMsg":f"Excepción _cancel_order: {str(e)}","result":{}}

    def set_cancel_all_orders(self, symbol:str=None, order_filter:str="Order", stop_order_type:str=None) -> dict:
        target_symbol = symbol or self.symbol
        params = {"category":"linear", "symbol":target_symbol, "orderFilter":order_filter}
        if order_filter == "StopOrder" and stop_order_type: params["stopOrderType"] = stop_order_type
        final_response = {"retCode":0,"retMsg":"Éxito (parcial)","result":{"list":[]}} # Init with success
        try:
            resp1 = self.session.cancel_all_orders(**params)
            if resp1.get("retCode")==0 and resp1.get("result",{}).get("list"): final_response["result"]["list"].extend(resp1["result"]["list"])
            elif resp1.get("retCode")!=0 : final_response=resp1 # Store first error

            if order_filter=="Order" and (final_response["retCode"]==0 or not final_response["result"]["list"]): 
                params["orderFilter"]="StopOrder"; params.pop("stopOrderType",None)
                resp2 = self.session.cancel_all_orders(**params)
                if resp2.get("retCode")==0 and resp2.get("result",{}).get("list"): final_response["result"]["list"].extend(resp2["result"]["list"])
                elif resp2.get("retCode")!=0 and final_response["retCode"]==0 : final_response=resp2
            return final_response
        except Exception as e: return {"retCode":99996,"retMsg":f"Excepción set_cancel_all_orders: {str(e)}","result":{}}

    def get_open_position(self, symbol:str=None) -> dict:
        target_symbol = symbol or self.symbol; L,S={},{}
        try:
            response = self.session.get_positions(category="linear", symbol=target_symbol)
            if response and response.get('retCode') == 0:
                for pos_data in response.get('result', {}).get('list', []):
                    if float(pos_data.get("size", "0")) > 0:
                        details = {"avgPrice":pos_data.get("avgPrice","0"), "positionAmt":float(pos_data.get("size","0"))}
                        if self.modo_cobertura:
                            if int(pos_data.get("positionIdx",0)) == 1: L = details
                            elif int(pos_data.get("positionIdx",0)) == 2: S = details
                        else:
                            if pos_data.get("side") == "Buy": L = details
                            elif pos_data.get("side") == "Sell": S = details
        except Exception as e: print(f"[{self.nombre_bot}] EXCEPTION get_open_position: {e}")
        return {"LONG":L, "SHORT":S}

    def monedas_de_entrada(self, positionside_to_check:str) -> dict:
        """Calculates initial order quantity and planned re-entries using mgo."""
        pos_handler = self.PosLong if positionside_to_check == "LONG" else self.PosShort
        precio_ref = self.precio_entrada_referencia 
        if not precio_ref or precio_ref <= 0:
            try:
                ticker_data = self.session.get_tickers(category="linear", symbol=self.symbol)
                if ticker_data and ticker_data.get('retCode')==0 and ticker_data.get('result',{}).get('list'):
                    precio_ref = float(ticker_data['result']['list'][0]['lastPrice'])
                    if not precio_ref or precio_ref <=0 : raise ValueError("Precio de mercado inválido.")
                else: return {"monedas":0,"cant_ree":0,"error":f"Fallo al obtener precio de mercado: {ticker_data.get('retMsg')}"}
            except Exception as e_pr: return {"monedas":0,"cant_ree":0,"error":f"Excepción obteniendo precio: {e_pr}"}

        qty_calculated = self.cantidad_a_operar_inicial 
        if qty_calculated == 0: 
            if self.usdt_entrada_inicial > 0: qty_calculated = self.usdt_entrada_inicial / precio_ref
            elif self.monto_sl_base > 0 and self.dist_ree > 0:
                sl_calc_price = precio_ref * (1 - self.dist_ree/100) if positionside_to_check=="LONG" else precio_ref * (1 + self.dist_ree/100)
                if abs(precio_ref - sl_calc_price) < 1e-9: return {"monedas":0,"cant_ree":0,"error":"SL y precio ref. muy cercanos"}
                qty_calculated = pos_handler.vol_monedas(self.monto_sl_base, precio_ref, sl_calc_price)
                if self.cant_ree > 0: qty_calculated /= (self.cant_ree + 1) 
            else: return {"monedas":0,"cant_ree":0,"error":"No se puede determinar cantidad de entrada."}
        
        if qty_calculated <=0: return {"monedas":0,"cant_ree":0, "error":f"Cantidad calculada es <=0: {qty_calculated}"}
        
        try:
            re_data = pos_handler.recompras(precio_ref,self.monto_sl_base,self.cant_ree,self.dist_ree,qty_calculated,self.porcentaje_vol_ree,self.usdt_entrada_inicial,self.gestion_vol)
            num_effective_reentries = len(re_data.get("prices",[]))
            return {"monedas":float(qty_calculated), "cant_ree":num_effective_reentries}
        except Exception as e_mgo_re: 
            print(f"[{self.nombre_bot}] EXCEPTION mgo.recompras: {e_mgo_re}")
            return {"monedas":float(qty_calculated),"cant_ree":0,"error":f"mgo.recompras exc: {e_mgo_re}"}

    def get_current_open_orders(self, symbol:str=None, order_type_filter:str=None, side_filter_param:str=None) -> dict:
        """Fetches and filters open orders (active & conditional)."""
        target_symbol = symbol or self.symbol
        L_ids,L_amts,L_prcs, S_ids,S_amts,S_prcs, PrcIds = [],[],[], [],[],[], set()
        
        # Active Orders
        try:
            resp = self.session.get_open_orders(category="linear",symbol=target_symbol)
            if resp and resp.get('retCode')==0:
                for o in resp.get('result',{}).get('list',[]):
                    oid=o.get("orderId"); api_ot=o.get("orderType","").upper()
                    if oid in PrcIds: continue
                    match_type=True
                    if order_type_filter:
                        f=order_type_filter.upper()
                        if f in ["STOP","TAKEPROFIT","STOPLOSS","TAKE_PROFIT_MARKET","STOP_MARKET","TRIGGER_MARKET","TRIGGER_LIMIT"]: match_type=False
                        elif api_ot!=f: match_type=False
                    if not match_type: continue
                    order_side,qty,price,pos_idx = o.get("side"),float(o.get("qty",0)),float(o.get("price",0)),int(o.get("positionIdx",0))
                    belongs_to = "LONG" if (self.modo_cobertura and pos_idx==1) or (not self.modo_cobertura and order_side=="Buy") else \
                                "SHORT" if (self.modo_cobertura and pos_idx==2) or (not self.modo_cobertura and order_side=="Sell") else None
                    if side_filter_param and side_filter_param.upper()!=belongs_to: continue
                    if belongs_to=="LONG": L_ids.append(oid);L_amts.append(qty);L_prcs.append(price)
                    elif belongs_to=="SHORT": S_ids.append(oid);S_amts.append(qty);S_prcs.append(price)
                    if belongs_to: PrcIds.add(oid)
        except Exception as e: print(f"[{self.nombre_bot}] EXCEPTION get_open_orders (active): {e}")

        # Conditional Orders
        if not order_type_filter or order_type_filter.upper() not in ["LIMIT","MARKET"]:
            try:
                resp = self.session.get_open_orders(category="linear",symbol=target_symbol,orderFilter="StopOrder")
                if resp and resp.get('retCode')==0:
                    for o in resp.get('result',{}).get('list',[]):
                        oid=o.get("orderId"); sot=o.get("stopOrderType","").upper(); et=o.get("orderType","").upper()
                        if oid in PrcIds: continue
                        eff_type = f"{sot}_{et}" if sot in ["TAKEPROFIT","STOPLOSS","STOP"] and et=="MARKET" else sot
                        if order_type_filter and order_type_filter.upper() not in [eff_type, sot]: continue
                        order_side,qty,trig_price,pos_idx,reduce_only = o.get("side"),float(o.get("qty",0)),float(o.get("triggerPrice",0)),int(o.get("positionIdx",0)),o.get("reduceOnly",False)
                        belongs_to = "LONG" if (self.modo_cobertura and pos_idx==1) or \
                                    (not self.modo_cobertura and ((reduce_only and order_side=="Sell") or (not reduce_only and order_side=="Buy"))) else \
                                    "SHORT" if (self.modo_cobertura and pos_idx==2) or \
                                    (not self.modo_cobertura and ((reduce_only and order_side=="Buy") or (not reduce_only and order_side=="Sell"))) else None
                        if side_filter_param and side_filter_param.upper()!=belongs_to: continue
                        if belongs_to=="LONG": L_ids.append(oid);L_amts.append(qty);L_prcs.append(trig_price)
                        elif belongs_to=="SHORT": S_ids.append(oid);S_amts.append(qty);S_prcs.append(trig_price)
                        if belongs_to: PrcIds.add(oid)
            except Exception as e: print(f"[{self.nombre_bot}] EXCEPTION get_open_orders (conditional): {e}")
            
        return {"symbol":target_symbol,"long_orders_id":L_ids,"long_amt_orders":L_amts,"long_price_orders":L_prcs,
                "short_orders_id":S_ids,"short_amt_orders":S_amts,"short_price_orders":S_prcs,
                "long_total":len(L_ids),"short_total":len(S_ids)}

    def dynamic_sl_manager(self, symbol:str=None, positionside_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.positionside
        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt, avg_px = float(pos_info.get("positionAmt",0)), float(pos_info.get("avgPrice",0))

        if pos_amt > 0 and avg_px > 0:
            orders = self.get_current_open_orders(target_symbol, "StopLoss", target_ps)
            if orders.get(f"{target_ps.lower()}_total",0) == 0: 
                orders = self.get_current_open_orders(target_symbol, "Stop", target_ps)
            
            handler = self.PosLong if target_ps=="LONG" else self.PosShort
            sl_px = handler.stop_loss(avg_px, self.monto_sl_base, pos_amt) 
            if not sl_px or sl_px <= 0: 
                print(f"[{self.nombre_bot}] Invalid SL price ({sl_px}) for {target_ps} {target_symbol}.")
                return

            if orders.get(f"{target_ps.lower()}_total",0) == 0:
                print(f"[{self.nombre_bot}] {target_ps}: No SL. Placing SL @{sl_px} (Type:{self.tipo_orden_sl_tp})...")
                self.set_stop_loss(target_symbol, target_ps, pos_amt, sl_px, self.tipo_orden_sl_tp)
            else: 
                curr_sl_id = orders[f"{target_ps.lower()}_orders_id"][0]
                curr_sl_qty = orders[f"{target_ps.lower()}_amt_orders"][0]
                curr_sl_trig_px = orders[f"{target_ps.lower()}_price_orders"][0]
                qty_ok = abs(curr_sl_qty - pos_amt) < float(self.qty_step or 1e-8)
                price_ok = abs(curr_sl_trig_px - sl_px) < float(self.pip_precio or 1e-8) * 2 
                if not qty_ok or not price_ok:
                    print(f"[{self.nombre_bot}] {target_ps}: SL incorrect (Qty:{curr_sl_qty} vs {pos_amt}, Trig:{curr_sl_trig_px} vs {sl_px}). Replacing...")
                    self._cancel_order(target_symbol, curr_sl_id); time.sleep(0.3) 
                    self.set_stop_loss(target_symbol, target_ps, pos_amt, sl_px, self.tipo_orden_sl_tp)
    
    def dynamic_tp_manager(self, symbol:str=None, positionside_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.positionside
        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt, avg_px = float(pos_info.get("positionAmt",0)), float(pos_info.get("avgPrice",0))

        if pos_amt > 0 and avg_px > 0:
            orders = self.get_current_open_orders(target_symbol, "TakeProfit", target_ps)
            
            handler = self.PosLong if target_ps=="LONG" else self.PosShort
            tp_px = handler.take_profit(self.gestion_take_profit, avg_px, self.monto_sl_base, pos_amt, self.ratio_beneficio_perdida)
            if not tp_px or tp_px <= 0: 
                print(f"[{self.nombre_bot}] Invalid TP price ({tp_px}) for {target_ps} {target_symbol}.")
                return

            if orders.get(f"{target_ps.lower()}_total",0) == 0:
                print(f"[{self.nombre_bot}] {target_ps}: No TP. Placing TP @{tp_px} (Type:{self.tipo_orden_sl_tp})...")
                self.set_take_profit(target_symbol, target_ps, pos_amt, tp_px, self.tipo_orden_sl_tp)
            else: 
                curr_tp_id = orders[f"{target_ps.lower()}_orders_id"][0]
                curr_tp_qty = orders[f"{target_ps.lower()}_amt_orders"][0]
                curr_tp_trig_px = orders[f"{target_ps.lower()}_price_orders"][0]
                qty_ok = abs(curr_tp_qty - pos_amt) < float(self.qty_step or 1e-8)
                price_ok = abs(curr_tp_trig_px - tp_px) < float(self.pip_precio or 1e-8) * 5 
                if not qty_ok or not price_ok:
                    print(f"[{self.nombre_bot}] {target_ps}: TP incorrect (Qty:{curr_tp_qty} vs {pos_amt}, Trig:{curr_tp_trig_px} vs {tp_px}). Replacing...")
                    self._cancel_order(target_symbol, curr_tp_id); time.sleep(0.3)
                    self.set_take_profit(target_symbol, target_ps, pos_amt, tp_px, self.tipo_orden_sl_tp)

    def dynamic_reentradas_manager(self, symbol:str=None, positionside_param:str=None, modo_gestion_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.positionside
        target_mg = modo_gestion_param or self.modo_gestion
        if target_mg not in ["REENTRADAS","SNOW BALL"]: return

        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt = float(pos_info.get("positionAmt", 0))
        
        if pos_amt > 0: 
            monedas_info = self.monedas_de_entrada(target_ps) 
            if monedas_info.get("error"): 
                print(f"[{self.nombre_bot}] Error in dynamic_reentradas_manager (monedas_de_entrada): {monedas_info['error']}")
                return
            
            monedas_base_exp = monedas_info.get("monedas",0)
            cant_ree_exp = monedas_info.get("cant_ree",0)
            if cant_ree_exp == 0: return 

            qty_match_base = abs(pos_amt - monedas_base_exp) < float(self.qty_step or 1e-9) 
            
            order_type_ree = "Limit" if target_mg == "REENTRADAS" else "Stop" 
            open_ree_orders = self.get_current_open_orders(target_symbol, order_type_ree, target_ps)
            num_ree_abiertas = open_ree_orders.get(f"{target_ps.lower()}_total",0)

            if qty_match_base and num_ree_abiertas != cant_ree_exp: # Only adjust if current pos is ~base and re-entries are wrong
                print(f"[{self.nombre_bot}] {target_ps} ({target_mg}): Reentradas {num_ree_abiertas} vs esp {cant_ree_exp}. Ajustando...")
                for oid in open_ree_orders.get(f"{target_ps.lower()}_orders_id",[]):
                    self._cancel_order(target_symbol, order_id=oid); time.sleep(0.25)
                
                # set_limit_market_order should place ONLY re-entries if initial order already exists/filled.
                # This implies set_limit_market_order needs to know if the initial order part is done.
                # The current logic in set_limit_market_order might re-place initial if pos_qty_actual is small.
                # For re-entry manager, we assume initial order is filled and we are managing subsequent orders.
                print(f"[{self.nombre_bot}]  Llamando a set_limit_market_order para (re)colocar reentradas para {target_ps} modo {target_mg}")
                self.set_limit_market_order(target_symbol, target_ps, target_mg, f"ree_{target_ps[:3].lower()}")

    def set_limit_market_order(self, symbol:str, positionside:str, modo_gestion:str, client_order_id_prefix:str="entrada")->dict:
        target_symbol, target_ps, target_mg = symbol or self.symbol, positionside or self.positionside, modo_gestion or self.modo_gestion
        print(f"[{self.nombre_bot}] Iniciando set_limit_market_order para {target_symbol}-{target_ps}, Modo: {target_mg}")

        monedas_info = self.monedas_de_entrada(target_ps)
        if monedas_info.get("error"):
            print(f"[{self.nombre_bot}] Error (monedas_de_entrada): {monedas_info['error']}")
            return {"retCode":-1,"retMsg":monedas_info["error"],"result":{}}
        
        qty_inicial_calculada = monedas_info.get("monedas",0)
        num_ree_plan = monedas_info.get("cant_ree",0)

        if qty_inicial_calculada <= 0:
            return {"retCode":-1,"retMsg":f"Qty inicial inválida: {qty_inicial_calculada}","result":{}}
        
        self.cantidad_a_operar_inicial = qty_inicial_calculada 
        tipo_orden_inicial = self.tipo_orden_entrada
        precio_lmt_orden_inicial = self.precio_entrada_referencia if tipo_orden_inicial=="LIMIT" else None

        current_pos_data = self.get_open_position(target_symbol)
        pos_qty_actual = float(current_pos_data.get(target_ps.upper(),{}).get("positionAmt",0))
        
        resp_primera_orden = None
        
        # Place initial order only if no significant position exists for this side
        min_comparable_qty = float(self.min_qty_compra or 0.000001) # Ensure it's float
        if pos_qty_actual < min_comparable_qty: 
            print(f"[{self.nombre_bot}] Colocando orden INICIAL {target_ps}: Qty={self.cantidad_a_operar_inicial}, Tipo={tipo_orden_inicial}, PrecioLMT={precio_lmt_orden_inicial or 'N/A'}")
            cid_inicial = f"{client_order_id_prefix}_{target_symbol[:3]}_{int(time.time()*1000)%10000}"
            
            sl_adjunto, tp_adjunto = None, None
            if target_mg == "DINAMICO":
                precio_ref_sltp = precio_lmt_orden_inicial 
                if tipo_orden_inicial == "MARKET" or not precio_ref_sltp or precio_ref_sltp <= 0:
                    try:
                        ticker_data = self.session.get_tickers(category="linear", symbol=target_symbol)
                        if ticker_data and ticker_data.get('retCode')==0 and ticker_data.get('result',{}).get('list'):
                            precio_ref_sltp = float(ticker_data['result']['list'][0]['lastPrice'])
                        else: precio_ref_sltp = 0 
                    except Exception: precio_ref_sltp = 0
                if precio_ref_sltp and precio_ref_sltp > 0:
                    handler = self.PosLong if target_ps=="LONG" else self.PosShort
                    sl_adjunto = handler.stop_loss(precio_ref_sltp, self.monto_sl_base, self.cantidad_a_operar_inicial)
                    if sl_adjunto: tp_adjunto = handler.take_profit_ratio(precio_ref_sltp, sl_adjunto, self.ratio_beneficio_perdida)
            
            resp_primera_orden = self._limit_market_order(target_symbol,target_ps,self.cantidad_a_operar_inicial,precio_lmt_orden_inicial,tipo_orden_inicial,cid_inicial,sl_adjunto,tp_adjunto)
            if resp_primera_orden.get("retCode")!=0: return resp_primera_orden 
            
            if tipo_orden_inicial=="LIMIT" and precio_lmt_orden_inicial: self.precio_entrada_referencia = precio_lmt_orden_inicial
            if target_mg == "DINAMICO": return resp_primera_orden 
        else:
            print(f"[{self.nombre_bot}] Posición {target_ps} ya existente (Qty: {pos_qty_actual}). Omitiendo orden inicial.")
            self.precio_entrada_referencia = float(current_pos_data.get(target_ps.upper(),{}).get("avgPrice", self.precio_entrada_referencia))

        # --- Place Re-entry or Snowball orders ---
        if num_ree_plan > 0 and target_mg in ["REENTRADAS", "SNOW BALL"]:
            precio_base_re = self.precio_entrada_referencia 
            if not precio_base_re or precio_base_re <= 0 :
                try:
                    ticker_data = self.session.get_tickers(category="linear", symbol=target_symbol)
                    if ticker_data and ticker_data.get('retCode')==0 and ticker_data.get('result',{}).get('list'):
                        precio_base_re = float(ticker_data['result']['list'][0]['lastPrice'])
                    else: raise ValueError(f"No price for re-entry calc: {ticker_data.get('retMsg')}")
                except Exception as e_re_price:
                    print(f"[{self.nombre_bot}] EXCEPTION obteniendo precio para base de reentradas: {e_re_price}")
                    return resp_primera_orden or {"retCode":-1, "retMsg":f"Excepción precio reentradas: {e_re_price}","result":{}}

            print(f"[{self.nombre_bot}] Preparando {num_ree_plan} órdenes de {target_mg} para {target_ps} desde precio base {precio_base_re}...")
            handler = self.PosLong if target_ps=="LONG" else self.PosShort
            data_ree_fn = handler.recompras if target_mg=="REENTRADAS" else handler.snow_ball
            
            params_ree=data_ree_fn(precio_base_re, self.monto_sl_base, num_ree_plan, self.dist_ree, 
                                    self.cantidad_a_operar_inicial, 
                                    self.porcentaje_vol_ree, self.usdt_entrada_inicial, self.gestion_vol)
            
            if params_ree and params_ree.get("prices"):
                tipo_orden_ree = "Limit" if target_mg=="REENTRADAS" else "Market" 
                trigger_based = (target_mg == "SNOW BALL") 

                for i, (price_re, qty_re) in enumerate(zip(params_ree["prices"], params_ree["quantitys"])):
                    if qty_re <=0 or price_re <=0: 
                        print(f"[{self.nombre_bot}] Advertencia: Reentrada {i+1} con datos inválidos (Qty:{qty_re}, Prc:{price_re}). Saltando.")
                        continue
                    
                    cid_r = f"ree{i+1}_{target_symbol[:3].lower()}_{int(time.time()*1000+i)%10000}"
                    print(f"[{self.nombre_bot}]   Reentrada {i+1}: Qty={qty_re}, Precio={price_re}, Tipo={tipo_orden_ree}{' (Trigger)' if trigger_based else ''}")
                    
                    self._place_order_internal(
                        symbol=target_symbol, order_type=tipo_orden_ree, 
                        side="Buy" if target_ps=="LONG" else "Sell", 
                        qty_str=str(qty_re), price_str=str(price_re) if tipo_orden_ree=="Limit" else None,
                        position_side_param=target_ps, trigger_price_str=str(price_re) if trigger_based else None,
                        client_order_id=cid_r, reduce_only_flag=False
                    )
                    time.sleep(0.25) 
            else: print(f"[{self.nombre_bot}] No se generaron datos para órdenes de {target_mg} desde mgo.")
        
        return resp_primera_orden or {"retCode":0, "retMsg":"Proceso de órdenes completado (ver logs).","result":{}}

    # --- WebSocket Methods ---
    def get_last_candles(self, symbol:str=None, interval:str=None, limit:int=1) -> list:
        ts, ti = symbol or self.symbol, interval or self.temporalidad
        try:
            r = self.session.get_kline(category="linear",symbol=ts,interval=ti,limit=limit)
            if r and r.get('retCode')==0:
                raw_k = r.get('result',{}).get('list',[])
                if not raw_k: return [{"s":ts,"t":ti}] 
                fmt_k = [{"ts":int(k[0]),"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4]),"v":float(k[5]),"to":float(k[6])} for k in reversed(raw_k)]
                return [{"s":ts,"t":ti}] + fmt_k
            else: print(f"[{self.nombre_bot}] Error get_last_candles: {r.get('retMsg') if r else 'No response'}")
        except Exception as e: print(f"[{self.nombre_bot}] EXCEPTION get_last_candles: {e}")
        return [{"s":ts,"t":ti}] 

    def on_message_websocket_kline(self, message:dict):
        if message and isinstance(message,dict) and 'data' in message:
            k_list = message.get('data',[])
            if k_list and isinstance(k_list,list) and k_list[0]:
                k_point = k_list[0]
                if isinstance(k_point,dict) and 'close' in k_point:
                    self.last_price = float(k_point['close'])
                    self.check_strategy(self.last_price)
                    if self.position_opened_by_strategy:
                        print(f"[{self.nombre_bot}] Posición abierta por check_strategy. Deteniendo WS de entrada.")
                        self.stop_websocket() 
                        self.position_opened_by_strategy = False 
    
    def start_websocket(self):
        if self.ws_running: print(f"[{self.nombre_bot}] WS ya en ejecución."); return
        if not self.ws_should_run: print(f"[{self.nombre_bot}] WS no debe correr (ws_should_run=False)."); return
        
        print(f"[{self.nombre_bot}] Iniciando WS para {self.symbol} kline {self.temporalidad}...")
        self.ws_running = True
        try:
            self.ws = PybitWebSocket(testnet=self.testnet, channel_type="linear")
            self.ws.subscribe(topic=f"kline.{self.temporalidad}.{self.symbol}", callback=self.on_message_websocket_kline)
            print(f"[{self.nombre_bot}] WS suscrito a kline.{self.temporalidad}.{self.symbol}. Esperando mensajes...")
        except Exception as e:
            print(f"[{self.nombre_bot}] EXCEPTION al iniciar WS: {e}")
            self.ws_running = False
            self.__reconnect_websocket()

    def __reconnect_websocket(self):
        if self.ws_should_run:
            print(f"[{self.nombre_bot}] Intentando reconectar WS en {self.ws_reconnect_delay}s...")
            time.sleep(self.ws_reconnect_delay)
            print(f"[{self.nombre_bot}] Reconectando WS...")
            self.start_websocket()
        else: print(f"[{self.nombre_bot}] WS no debe correr, no se reconectará.")
            
    def stop_websocket(self):
        print(f"[{self.nombre_bot}] Deteniendo WS intencionalmente...")
        self.ws_should_run = False 
        if self.ws and self.ws_running:
            try: self.ws.exit()
            except Exception as e_ws_exit: print(f"[{self.nombre_bot}] Excepción al cerrar WS: {e_ws_exit}")
        self.ws_running = False
        print(f"[{self.nombre_bot}] WS detenido.")

    # --- Main Strategy Logic & Monitoring ---
    def check_strategy(self, current_price:float):
        current_pos = self.get_open_position(self.symbol)
        if self.positionside == "LONG":
            if current_pos.get("LONG",{}).get("positionAmt",0) > 0: return 
            if self.precio_entrada_long > 0 and current_price <= self.precio_entrada_long:
                print(f"[{self.nombre_bot}] SEÑAL LONG: Precio {current_price} <= Trigger {self.precio_entrada_long}. Ejecutando entrada...")
                result = self.set_limit_market_order(self.symbol, "LONG", self.modo_gestion)
                if result.get("retCode") == 0 and result.get("result",{}).get("orderId"):
                    self.position_opened_by_strategy = True 
                    print(f"[{self.nombre_bot}] Orden LONG colocada por señal. ID: {result['result']['orderId']}")
                else: print(f"[{self.nombre_bot}] Fallo al colocar orden LONG por señal: {result.get('retMsg')}")
        elif self.positionside == "SHORT":
            if current_pos.get("SHORT",{}).get("positionAmt",0) > 0: return 
            if self.precio_entrada_short > 0 and current_price >= self.precio_entrada_short:
                print(f"[{self.nombre_bot}] SEÑAL SHORT: Precio {current_price} >= Trigger {self.precio_entrada_short}. Ejecutando entrada...")
                result = self.set_limit_market_order(self.symbol, "SHORT", self.modo_gestion)
                if result.get("retCode") == 0 and result.get("result",{}).get("orderId"):
                    self.position_opened_by_strategy = True
                    print(f"[{self.nombre_bot}] Orden SHORT colocada por señal. ID: {result['result']['orderId']}")
                else: print(f"[{self.nombre_bot}] Fallo al colocar orden SHORT por señal: {result.get('retMsg')}")

    def monitor_open_positions(self):
        print(f"[{self.nombre_bot}] Iniciando monitoreo para {self.symbol} - {self.positionside}, Modo: {self.modo_gestion}")
        self._iniciar_monitor_memoria()
        
        MAX_HTTP_REQUESTS_PER_INTERVAL = 15 
        HTTP_INTERVAL_SECONDS = int(self.dict_config.get("segundos_monitoreo_http", 60)) 
        http_request_count = 0; last_http_cycle_time = time.time()
        
        self.ws_should_run = True 

        while self.ws_should_run: 
            try:
                now = time.time()
                if now - last_http_cycle_time < HTTP_INTERVAL_SECONDS and http_request_count >= MAX_HTTP_REQUESTS_PER_INTERVAL:
                    time.sleep(1) # Short sleep if waiting for interval end but requests are maxed
                    continue
                if now - last_http_cycle_time >= HTTP_INTERVAL_SECONDS:
                    http_request_count = 0 # Reset counter for new interval
                    last_http_cycle_time = now

                current_pos_data = self.get_open_position(self.symbol); http_request_count +=1
                
                active_pos_side_to_manage = None
                if self.positionside == "LONG" and current_pos_data.get("LONG",{}).get("positionAmt",0) > 0:
                    active_pos_side_to_manage = "LONG"
                elif self.positionside == "SHORT" and current_pos_data.get("SHORT",{}).get("positionAmt",0) > 0:
                    active_pos_side_to_manage = "SHORT"
                elif self.positionside == "BOTH": 
                    if current_pos_data.get("LONG",{}).get("positionAmt",0) > 0 :
                        print(f"[{self.nombre_bot}] (BOTH) Gestionando lado LONG...")
                        self.dynamic_sl_manager(symbol=self.symbol, positionside_param="LONG"); http_request_count+=1
                        self.dynamic_tp_manager(symbol=self.symbol, positionside_param="LONG"); http_request_count+=1
                        self.dynamic_reentradas_manager(symbol=self.symbol, positionside_param="LONG"); http_request_count+=1
                    if current_pos_data.get("SHORT",{}).get("positionAmt",0) > 0 :
                        print(f"[{self.nombre_bot}] (BOTH) Gestionando lado SHORT...")
                        self.dynamic_sl_manager(symbol=self.symbol, positionside_param="SHORT"); http_request_count+=1
                        self.dynamic_tp_manager(symbol=self.symbol, positionside_param="SHORT"); http_request_count+=1
                        self.dynamic_reentradas_manager(symbol=self.symbol, positionside_param="SHORT"); http_request_count+=1
                    if not current_pos_data.get("LONG") and not current_pos_data.get("SHORT"):
                        if not self.ws_running : self.start_websocket() 
                
                if active_pos_side_to_manage: 
                    if self.ws_running: self.stop_websocket() 
                    print(f"[{self.nombre_bot}] Gestionando posición {active_pos_side_to_manage} para {self.symbol}...")
                    self.dynamic_sl_manager(symbol=self.symbol, positionside_param=active_pos_side_to_manage); http_request_count+=1
                    self.dynamic_tp_manager(symbol=self.symbol, positionside_param=active_pos_side_to_manage); http_request_count+=1
                    self.dynamic_reentradas_manager(symbol=self.symbol, positionside_param=active_pos_side_to_manage); http_request_count+=1
                
                elif self.positionside != "BOTH" and not active_pos_side_to_manage: 
                    if not self.ws_running: self.start_websocket() 
                
                # Main loop sleep based on whether WS is active or HTTP polling is dominant
                if self.ws_running: time.sleep(1) # WS active, main loop can sleep shorter
                else: time.sleep(max(1, HTTP_INTERVAL_SECONDS // MAX_HTTP_REQUESTS_PER_INTERVAL if MAX_HTTP_REQUESTS_PER_INTERVAL > 0 else HTTP_INTERVAL_SECONDS))


            except KeyboardInterrupt: 
                print(f"[{self.nombre_bot}] KeyboardInterrupt en monitor_open_positions.")
                self.ws_should_run = False; break 
            except Exception as e:
                print(f"[{self.nombre_bot}] ERROR en bucle monitor_open_positions: {e}"); import traceback; traceback.print_exc()
                time.sleep(20) 
        
        print(f"[{self.nombre_bot}] Saliendo de monitor_open_positions.")
        self.stop_websocket() 
        self._detener_monitor_memoria()

    def _monitor_memoria(self):
        proceso = psutil.Process(os.getpid())
        while not self._detener_monitor_mem.is_set():
            memoria = proceso.memory_info().rss / 1024**2 
            print(f"[{self.nombre_bot}][MONITOR MEM] Uso: {memoria:.2f} MB")
            if self._detener_monitor_mem.wait(self.segundos_monitoreo_mem): break 
    def _iniciar_monitor_memoria(self):
        if self.segundos_monitoreo_mem > 0 and (not self._hilo_monitor_mem or not self._hilo_monitor_mem.is_alive()):
            self._detener_monitor_mem.clear()
            self._hilo_monitor_mem = threading.Thread(target=self._monitor_memoria, daemon=True)
            self._hilo_monitor_mem.start()
            print(f"[{self.nombre_bot}] Monitor de memoria iniciado (cada {self.segundos_monitoreo_mem}s).")
    def _detener_monitor_memoria(self):
        if self._hilo_monitor_mem and self._hilo_monitor_mem.is_alive():
            self._detener_monitor_mem.set()
            self._hilo_monitor_mem.join(timeout=2) 
            print(f"[{self.nombre_bot}] Monitor de memoria detenido.")


if __name__ == "__main__":
    print("--- INICIO DE PRUEBA DEL BOT BYBIT ---")
    
    # --- Configuración de Ejemplo para Pruebas ---
    # IMPORTANTE: Ajustar 'symbol', 'precio_entrada_long', 'precio_entrada_short' a valores REALISTAS
    # para el mercado actual del símbolo elegido en TESTNET para que las pruebas de entrada sean efectivas.
    config_test = {
        "nombre_bot": "BybitBot01", 
        "testnet": False, 
        "symbol": "DOGE", # Ej: "BTC", "ETH", "SOL" (sin "-USDT")
        "positionside": "LONG",  # "LONG" o "SHORT". "BOTH" activa gestión para ambos lados pero no señales de entrada.
        "modo_cobertura": False, # False = One-Way (recomendado para empezar), True = Hedge Mode.
        
        "apalancamiento": 10, 
        "riesgo_por_operacion_porcentaje": 1.0, # % de equity para cálculos de riesgo si se usa mgo.
        "monto_sl_base": 20.0, # USDT de riesgo para cálculos de SL por mgo, o SL fijo para modo GAFAS.

        "modo_gestion_de_ordenes": "DINAMICO", # Opciones: "DINAMICO", "REENTRADAS", "SNOW BALL", "GAFAS"
        "tipo_de_orden_entrada": "MARKET",  # "MARKET" o "LIMIT" para la orden de entrada inicial.
        "precio_entrada_referencia": 0, # Para orden LMT inicial. Si 0 y tipo_orden_entrada="LIMIT", la estrategia debe fijarlo o usará precio de mercado.
        
        # --- Precios de activación para la estrategia de entrada por WebSocket (check_strategy) ---
        # Estos deben ser precios que esperas que el mercado alcance para probar la lógica de entrada.
        "precio_entrada_long": 0.1900,  # Ej: Si BTCUSDT está a 60000, poner 59000 para probar entrada LONG.
        "precio_entrada_short": 0.4000, # Ej: Si BTCUSDT está a 60000, poner 61000 para probar entrada SHORT.

        # --- Configuración para Modos de Gestión Específicos ---
        # Para DINAMICO (Ratio Beneficio/Perdida):
        "gestion_take_profit": "RATIO BENEFICIO/PERDIDA", # Opciones: "RATIO BENEFICIO/PERDIDA", "% TAKE PROFIT" (requeriría lógica mgo adicional)
        "ratio_beneficio_perdida": 1.5, # Ej: TP es 1.5 veces el riesgo del SL.
        "tipo_orden_sl_tp": "Market", # "Market" o "Limit" para las órdenes SL/TP que colocan los gestores dinámicos.

        # Para REENTRADAS / SNOW BALL:
        "cantidad_a_operar_inicial": 0, # Cantidad base de la orden inicial (en la moneda del símbolo, ej. BTC). Si 0, se calcula.
        "usdt_entrada_inicial": 0,      # Si >0 y cantidad_a_operar_inicial=0, se usa para calcularla.
                                        # Si ambas son 0, se calcula por monto_sl_base y dist_ree.
        "cant_ree": 3,                  # Número de reentradas deseadas.
        "dist_ree": 0.5,                # % de distancia entre reentradas. También usado para calcular SL si cantidad_a_operar_inicial=0 y usdt_entrada_inicial=0.
        "gestion_vol": "FIJO",          # "FIJO", "MARTINGALA", "AGRESIVO" para el volumen de las reentradas.
        "porcentaje_vol_ree": 0,        # % de incremento para MARTINGALA/AGRESIVO (ej. 50 para 50% más). No usado si "FIJO".
        
        # --- Configuración del Monitoreo ---
        "segundos_monitoreo_http": 30, # Intervalo (segundos) para el bucle de monitoreo HTTP de posiciones.
        "segundos_monitoreo_memoria": 0, # 0 para desactivar. Si >0, intervalo para log de memoria.
        "temporalidad": "1m"             # Intervalo de Klines para WebSocket (ej. "1m", "5m", "1H").
    }
    
    print(f"\n[MAIN CONFIG: Bot '{config_test['nombre_bot']}' para {config_test['symbol']}USDT en modo {config_test['positionside']}]")
    print(f"  - Modo Gestión Órdenes: {config_test['modo_gestion_de_ordenes']}")
    print(f"  - Señal Entrada LONG si precio <= {config_test['precio_entrada_long']}")
    print(f"  - Señal Entrada SHORT si precio >= {config_test['precio_entrada_short']}")
    print(f"  - Testnet: {'Sí' if config_test['testnet'] else 'No (MAINNET - CUIDADO!)'}")
    print(f"  - (Descomentar llamadas a funciones de trading real en __main__ solo para pruebas activas)")

    bybit_bot_main_instance = None
    try:
        bybit_bot_main_instance = Bybit(dict_config=config_test)
        
        # --- Pruebas de Información (Descomentar selectivamente para verificar) ---
        print(f"  Detalles del Instrumento ({bybit_bot_main_instance.symbol}): {bybit_bot_main_instance.get_instrument_details()}")
        balance_info = bybit_bot_main_instance.get_balance(coin_symbol='USDT') # O la moneda de colateral que uses
        print(f"  Balance (USDT o colateral): {balance_info}")
        print(f"  Apalancamiento Configurado: {bybit_bot_main_instance.apalancamiento}x (Actual en exchange puede variar si hay pos: {bybit_bot_main_instance.get_current_leverage()}x)")
        print(f"  Posiciones Abiertas Actuales: {bybit_bot_main_instance.get_open_position()}")
        print(f"  Órdenes Abiertas (Limit): {bybit_bot_main_instance.get_current_open_orders(order_type_filter='Limit')}")
        print(f"  Última Vela ({bybit_bot_main_instance.temporalidad}): {bybit_bot_main_instance.get_last_candles(limit=1)}")

        # --- Iniciar el ciclo principal del bot ---
        # Esto iniciará el monitoreo de posiciones o el WebSocket para esperar señales de entrada.
        # ¡ASEGÚRATE DE ESTAR EN TESTNET O DE ENTENDER LAS IMPLICACIONES EN MAINNET!
        # bybit_bot_main_instance.monitor_open_positions() # DESCOMENTAR PARA EJECUTAR EL BOT

        print("\n[MAIN] Bot instanciado. Para ejecutar el monitoreo, descomenta la línea 'bybit_bot_main_instance.monitor_open_positions()' en __main__.")
        print("[MAIN] Asegúrate de que los precios de entrada ('precio_entrada_long', 'precio_entrada_short') son realistas para tu prueba.")


    except KeyboardInterrupt:
        print("\n[MAIN] Bot detenido manualmente por el usuario (KeyboardInterrupt).")
    except Exception as e_main:
        print(f"\n[MAIN] Error CRÍTICO durante la ejecución del bot: {e_main}")
        import traceback
        traceback.print_exc()
    finally:
        if bybit_bot_main_instance:
            print("[MAIN] Finalizando bot y limpiando recursos...")
            bybit_bot_main_instance.ws_should_run = False 
            bybit_bot_main_instance.stop_websocket()      
            bybit_bot_main_instance._detener_monitor_memoria() 
            
            # Ejemplo de limpieza de órdenes (USAR CON PRECAUCIÓN)
            # print("[MAIN] Limpieza final: Cancelando órdenes para el símbolo del bot (ejemplo)...")
            # cancel_response = bybit_bot_main_instance.set_cancel_all_orders(symbol=bybit_bot_main_instance.symbol)
            # print(f"  Respuesta cancelación total: {cancel_response.get('retMsg')}")
            
        print("[MAIN] Proceso de prueba del bot finalizado.")
            
    print("\n--- FIN DE PRUEBA DEL BOT BYBIT ---")
