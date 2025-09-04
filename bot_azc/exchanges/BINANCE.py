### Modulo Binance ###
import os
import time
import threading
# import hmac
# import hashlib
import json
# import gzip
# import io
import psutil 
# import requests

from binance.um_futures import UMFutures 
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient # Correcto para UMFutures
from binance.error import ClientError, ServerError 

import Modos_de_gestion_operativa as mgo

# Instancias de MGO
PosLong = mgo.PosicionLong()
PosShort = mgo.PosicionShort()

class Binance:
    def __init__(self, dict_config: dict):
        self.bot_name = dict_config.get("bot_name", "BinanceBot")
        print(f"[{self.bot_name}] Inicializando...")

        self.api_key = dict_config.get("api_key", "") 
        self.api_secret = dict_config.get("api_secret", "")
        self.testnet = dict_config.get("testnet", True)
        
        self.base_url_http = "https://testnet.binancefuture.com" if self.testnet else "https://fapi.binance.com"
        
        try:
            self.client = UMFutures(key=self.api_key, secret=self.api_secret, base_url=self.base_url_http)
            print(f"[{self.bot_name}] Sesión HTTP para Binance {'Testnet' if self.testnet else 'Mainnet'} creada.")
        except Exception as e:
            print(f"[{self.bot_name}] CRITICAL: Fallo al inicializar cliente UMFutures: {e}")
            raise

        self.symbol = str(dict_config.get("symbol", "BTCUSDT")).upper() 
        self.logic_positionside = str(dict_config.get("positionside", "BOTH")).upper() 
        self.binance_hedge_mode = dict_config.get("modo_cobertura", False) 

        if self.binance_hedge_mode:
            if self.logic_positionside == "LONG": self.binance_api_position_side_for_entry = "LONG"
            elif self.logic_positionside == "SHORT": self.binance_api_position_side_for_entry = "SHORT"
            else: self.binance_api_position_side_for_entry = "BOTH" 
        else: self.binance_api_position_side_for_entry = "BOTH" 
        
        self.apalancamiento = int(dict_config.get("apalancamiento", 20))
        
        self.modo_gestion = str(dict_config.get("modo_gestion", "DINAMICO")).upper()
        self.monto_sl_base = float(dict_config.get("monto_sl_base", 10.0)) 
        self.precio_entrada_referencia = float(dict_config.get("precio_entrada_referencia", 0.0)) 
        self.precio_entrada_long = float(dict_config.get("precio_entrada_long", 0.0)) 
        self.precio_entrada_short = float(dict_config.get("precio_entrada_short", 0.0))
        
        self.gestion_take_profit = str(dict_config.get("gestion_take_profit", "RATIO BENEFICIO/PERDIDA")).upper()
        self.ratio_beneficio_perdida = float(dict_config.get("ratio_beneficio_perdida", 1.5))
        
        self.gestion_vol = str(dict_config.get("gestion_vol", "MARTINGALA")).upper()
        self.cant_ree = int(dict_config.get("cant_ree", 0))
        self.dist_ree = float(dict_config.get("dist_ree", 1.0)) 
        self.porcentaje_vol_ree = float(dict_config.get("porcentaje_vol_ree", 0))
        
        self.cantidad_a_operar_inicial = float(dict_config.get("cantidad_a_operar_inicial", 0.0)) 
        self.usdt_entrada_inicial = float(dict_config.get("usdt_entrada_inicial", 0.0))
        
        self.tipo_orden_entrada = str(dict_config.get("tipo_de_orden_entrada", "MARKET")).upper()
        self.tipo_orden_sl_tp_config = str(dict_config.get("tipo_orden_sl_tp", "MARKET")).upper()

        self.last_price = None; self.position_opened_by_strategy = False
        self.ws_reconnect_delay = 10; self.ws_running = False; self.ws_should_run = True
        self.ws_client = None # Renombrado de self.ws para UMFuturesWebsocketClient
        self.temporalidad = str(dict_config.get("temporalidad", "1m"))
        
        self.segundos_monitoreo_http = int(dict_config.get("segundos_monitoreo_http", 60))
        self.MAX_REQUESTS_PER_MINUTE = 1000 
        self.request_count = 0; self.request_start_time = time.time()
        self._hilo_monitor_memoria = None; self._detener_monitor_memoria = threading.Event()
        self.segundos_monitoreo_mem = int(dict_config.get("segundos_monitoreo_memoria", 0))

        self.inf_moneda_raw = None; self.pip_precio = None; self.min_usdt_compra = None; self.price_scale = None;
        self.cant_decimales_precio = 0; self.cant_decimales_moneda = 0; self.min_qty_compra = None;
        self.max_qty_compra = None; self.qty_step = None; self.inf_moneda_dict = {} 

        self._get_instrument_info() 
        self._initial_account_setup() 

        if self.cantidad_a_operar_inicial == 0 and self.usdt_entrada_inicial > 0:
            ref_price_for_qty_calc = self.precio_entrada_referencia
            if not ref_price_for_qty_calc or ref_price_for_qty_calc <= 0 :
                ref_price_for_qty_calc = self.get_current_market_price()
            if ref_price_for_qty_calc > 0 : self.cantidad_a_operar_inicial = self.usdt_entrada_inicial / ref_price_for_qty_calc
            else: print(f"[{self.bot_name}] ADVERTENCIA: No se pudo calcular cantidad_a_operar_inicial.")
            if self.cantidad_a_operar_inicial > 0: print(f"[{self.bot_name}] Cantidad inicial calculada: {self.cantidad_a_operar_inicial:.{self.cant_decimales_moneda if self.cant_decimales_moneda else 3}f} {self.symbol[:-4] if self.symbol.endswith('USDT') else self.symbol}")
        
        print(f"[{self.bot_name}] Bot Binance inicializado. Símbolo: {self.symbol}, Testnet: {self.testnet}")

    def _get_instrument_info(self):
        try:
            exchange_info = self.client.exchange_info()
            for item in exchange_info['symbols']:
                if item['symbol'] == self.symbol:
                    self.inf_moneda_raw = item
                    self.price_scale = int(item['pricePrecision'])
                    self.cant_decimales_precio = int(item['pricePrecision'])
                    for f_item in item['filters']:
                        if f_item['filterType'] == 'PRICE_FILTER': self.pip_precio = float(f_item['tickSize'])
                        elif f_item['filterType'] == 'LOT_SIZE':
                            self.qty_step = float(f_item['stepSize'])
                            self.min_qty_compra = float(f_item['minQty'])
                            self.max_qty_compra = float(f_item['maxQty'])
                            self.cant_decimales_moneda = self._get_decimals_from_value(f_item['stepSize'])
                        elif f_item['filterType'] == 'MIN_NOTIONAL': self.min_usdt_compra = float(f_item.get('notional', '5.0'))
                    if self.pip_precio is None: self.pip_precio = 1 / (10**self.price_scale) 
                    self.inf_moneda_dict = {"symbol": self.symbol, "pip_precio": str(self.pip_precio), 
                                            "price_scale": self.price_scale, "cant_decimales_precio": self.cant_decimales_precio, 
                                            "min_qty_compra": str(self.min_qty_compra), "max_qty_compra": str(self.max_qty_compra), 
                                            "qty_step": str(self.qty_step), "cant_decimales_moneda": self.cant_decimales_moneda, 
                                            "min_usdt_compra": str(self.min_usdt_compra), "baseAsset": item.get('baseAsset'), 
                                            "quoteAsset": item.get('quoteAsset'), "status": item.get('status')}
                    # print(f"[{self.bot_name}] Info de {self.symbol} cargada: TickPrecio={self.pip_precio}, StepQty={self.qty_step}")
                    return True
            print(f"[{self.bot_name}] ERROR _get_instrument_info: Símbolo {self.symbol} no encontrado.")
        except (ClientError, ServerError, Exception) as e: print(f"[{self.bot_name}] EXCEPTION _get_instrument_info: {e}")
        if self.pip_precio is None: self.pip_precio = 0.01; self.price_scale = self.cant_decimales_precio if self.cant_decimales_precio else 2
        if self.qty_step is None: self.qty_step = 0.001; self.cant_decimales_moneda = self.cant_decimales_moneda if self.cant_decimales_moneda else 3
        if self.min_qty_compra is None: self.min_qty_compra = 0.001
        if self.min_usdt_compra is None: self.min_usdt_compra = 5.0
        # print(f"[{self.bot_name}] WARNING: Usando valores por defecto para info. del instrumento {self.symbol}.")
        return False

    def _initial_account_setup(self):
        try:
            self.client.change_leverage(symbol=self.symbol, leverage=self.apalancamiento, recvWindow=5000)
            print(f"[{self.bot_name}] Apalancamiento para {self.symbol} configurado a {self.apalancamiento}x.")
            # current_pos_mode = self.client.get_position_mode(recvWindow=5000) 
            # is_hedge_api = current_pos_mode.get('dualSidePosition') 
            # if self.binance_hedge_mode != is_hedge_api:
            #    self.client.change_position_mode(dualSidePosition=self.binance_hedge_mode, recvWindow=5000)
            #    print(f"[{self.bot_name}] Modo de posición cambiado a {'HEDGE' if self.binance_hedge_mode else 'ONE_WAY'}.")
            return True
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] ERROR en _initial_account_setup: {e}")
            return False
            
    def _get_decimals_from_value(self, value_str: str) -> int:
        value_str = str(value_str); return len(value_str.split('.')[1].rstrip('0')) if '.' in value_str else 0

    def get_pip_precio(self) -> float: return float(self.pip_precio) if self.pip_precio else 0.0
    def get_cant_deci_precio(self) -> int: return int(self.price_scale) if self.price_scale is not None else self.cant_decimales_precio
    def get_pip_moneda(self) -> float: return float(self.qty_step) if self.qty_step else 0.0
    def get_min_usdt(self) -> float: return float(self.min_usdt_compra) if self.min_usdt_compra else 0.0
    def get_min_qty(self) -> float: return float(self.min_qty_compra) if self.min_qty_compra else 0.0
    def get_instrument_details(self) -> dict: 
        if not self.inf_moneda_dict and self.inf_moneda_raw is None: self._get_instrument_info()
        return self.inf_moneda_dict

    def get_balance(self, coin_symbol="USDT") -> dict:
        try:
            balances = self.client.balance(recvWindow=5000) 
            for asset_balance in balances:
                if asset_balance['asset'] == coin_symbol:
                    return {"asset": asset_balance['asset'], "balance": asset_balance['balance'], 
                            "availableBalance": asset_balance['availableBalance']}
            # print(f"[{self.bot_name}] ADVERTENCIA: No se encontró balance para {coin_symbol}.")
            return {} 
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION get_balance: {e}"); return {}

    def get_current_leverage(self, symbol: str = None) -> float:
        target_symbol = symbol or self.symbol
        try:
            positions_risk_info = self.client.get_position_risk(symbol=target_symbol, recvWindow=5000)
            if positions_risk_info and isinstance(positions_risk_info, list):
                for pos_info in positions_risk_info: 
                    if pos_info.get('symbol') == target_symbol:
                        return float(pos_info.get('leverage', self.apalancamiento))
            return float(self.apalancamiento) 
        except (ClientError, ServerError, Exception) as e:
            # print(f"[{self.bot_name}] EXCEPTION get_current_leverage: {e}")
            return float(self.apalancamiento)

    def get_current_market_price(self, symbol: str = None) -> float:
        target_symbol = symbol or self.symbol
        try:
            ticker = self.client.ticker_price(symbol=target_symbol)
            if ticker and 'price' in ticker: return float(ticker['price'])
            return 0.0
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION get_current_market_price: {e}"); return 0.0
            
    def _place_order_internal(self, symbol:str, order_side_api:str, order_type_api:str, quantity_str:str, 
                            price_str:str=None, position_side_for_api:str=None, 
                            stop_price_str:str=None, reduce_only_bool:bool=False, 
                            client_order_id:str=None, time_in_force_str:str=None) -> dict:
        params = {"symbol": symbol, "side": order_side_api, "type": order_type_api, "quantity": quantity_str}
        params["positionSide"] = self.binance_api_position_side_for_entry if not self.binance_hedge_mode else position_side_for_api
        if order_type_api == "LIMIT" or (order_type_api in ["STOP", "TAKE_PROFIT"] and price_str):
            if not price_str: return {"code":-1, "msg":f"Precio para {order_type_api} requerido"}
            params["price"] = price_str
        if stop_price_str: params["stopPrice"] = stop_price_str
        if reduce_only_bool: params["reduceOnly"] = "true"
        if client_order_id: params["newClientOrderId"] = client_order_id
        if time_in_force_str and order_type_api == "LIMIT": params["timeInForce"] = time_in_force_str
        try:
            response = self.client.new_order(**params, recvWindow=6000)
            # print(f"[{self.bot_name}] Respuesta orden Binance: {response}")
            return response 
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION _place_order_internal: {e}")
            if isinstance(e, ClientError): return {"orderId":0, "code": e.err_code, "msg": e.err_message}
            return {"orderId":0, "code": -1, "msg": str(e)}

    def _format_quantity(self, quantity:float) -> str:
        if self.cant_decimales_moneda is None: self._get_instrument_info() 
        return "{:0.{}f}".format(mgo.redondeo(quantity, self.qty_step, self.cant_decimales_moneda), self.cant_decimales_moneda)
    
    def _format_price(self, price:float) -> str:
        if self.cant_decimales_precio is None: self._get_instrument_info()
        return "{:0.{}f}".format(mgo.redondeo(price, self.pip_precio, self.cant_decimales_precio), self.cant_decimales_precio)

    def _limit_market_order(self, symbol:str, logic_positionside_param:str, quantity:float, price:float=None, 
                            order_type_entry_param:str="MARKET", client_order_id:str=None) -> dict:
        order_side_api = "BUY" if logic_positionside_param == "LONG" else "SELL"
        api_pos_side_for_order = self.binance_api_position_side_for_entry
        if self.binance_hedge_mode: api_pos_side_for_order = logic_positionside_param
        if not self.qty_step or not self.pip_precio: self._get_instrument_info()
        if not self.qty_step or not self.pip_precio: return {"code":-1, "msg":"Falta info de precisión en _limit_market_order"}
        qty_str = self._format_quantity(quantity)
        price_str = None
        if order_type_entry_param.upper() == "LIMIT":
            if not price or price <=0: return {"code":-1, "msg":"Precio requerido y > 0 para orden LIMIT"}
            price_str = self._format_price(price)
        return self._place_order_internal(symbol=symbol, order_side_api=order_side_api, order_type_api=order_type_entry_param.upper(), 
                                        quantity_str=qty_str, price_str=price_str, position_side_for_api=api_pos_side_for_order,
                                        client_order_id=client_order_id)

    def set_take_profit(self, symbol:str, logic_positionside_param:str, quantity:float, tp_price:float, client_order_id:str=None) -> dict:
        order_side_api = "SELL" if logic_positionside_param == "LONG" else "BUY" 
        api_pos_side_for_order = self.binance_api_position_side_for_entry
        if self.binance_hedge_mode: api_pos_side_for_order = logic_positionside_param
        if not self.qty_step or not self.pip_precio: return {"code":-1, "msg":"Falta info precisión TP"}
        qty_str = self._format_quantity(quantity)
        tp_price_str = self._format_price(tp_price)
        binance_order_type = "TAKE_PROFIT_MARKET" if self.tipo_orden_sl_tp_config == "MARKET" else "TAKE_PROFIT"
        price_param_for_limit = tp_price_str if binance_order_type == "TAKE_PROFIT" else None
        cid = client_order_id or f"tp_{symbol[:3].lower()}{logic_positionside_param[0].lower()}_{int(time.time()*100)%10000}"
        return self._place_order_internal(symbol=symbol, order_side_api=order_side_api, order_type_api=binance_order_type,
                                        quantity_str=qty_str, price_str=price_param_for_limit, 
                                        position_side_for_api=api_pos_side_for_order, stop_price_str=tp_price_str, 
                                        reduce_only_bool=True, client_order_id=cid)

    def set_stop_loss(self, symbol:str, logic_positionside_param:str, quantity:float, sl_price:float, client_order_id:str=None) -> dict:
        order_side_api = "SELL" if logic_positionside_param == "LONG" else "BUY"
        api_pos_side_for_order = self.binance_api_position_side_for_entry
        if self.binance_hedge_mode: api_pos_side_for_order = logic_positionside_param
        if not self.qty_step or not self.pip_precio: return {"code":-1, "msg":"Falta info precisión SL"}
        qty_str = self._format_quantity(quantity)
        sl_price_str = self._format_price(sl_price)
        binance_order_type = "STOP_MARKET" if self.tipo_orden_sl_tp_config == "MARKET" else "STOP"
        price_param_for_limit = sl_price_str if binance_order_type == "STOP" else None
        cid = client_order_id or f"sl_{symbol[:3].lower()}{logic_positionside_param[0].lower()}_{int(time.time()*100)%10000}"
        return self._place_order_internal(symbol=symbol, order_side_api=order_side_api, order_type_api=binance_order_type,
                                        quantity_str=qty_str, price_str=price_param_for_limit, 
                                        position_side_for_api=api_pos_side_for_order, stop_price_str=sl_price_str, 
                                        reduce_only_bool=True, client_order_id=cid)

    def _cancel_order(self, symbol:str, order_id:str=None, client_order_id:str=None) -> dict:
        target_symbol = symbol or self.symbol
        if not order_id and not client_order_id: return {"code":-1, "msg":"ID de orden requerido para cancelar."}
        try:
            if order_id: response = self.client.cancel_order(symbol=target_symbol, orderId=int(order_id), recvWindow=5000)
            else: response = self.client.cancel_order(symbol=target_symbol, origClientOrderId=client_order_id, recvWindow=5000)
            # print(f"[{self.bot_name}] Respuesta cancelación Binance: {response}")
            return response
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION _cancel_order: {e}")
            if isinstance(e, ClientError): return {"code": e.err_code, "msg": e.err_message}
            return {"code":-1, "msg":str(e)}

    def set_cancel_all_orders(self, symbol:str=None) -> dict:
        target_symbol = symbol or self.symbol
        try:
            response = self.client.cancel_open_orders(symbol=target_symbol, recvWindow=5000)
            # print(f"[{self.bot_name}] Respuesta cancelar todas para {target_symbol}: {response}")
            return response
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION set_cancel_all_orders: {e}")
            if isinstance(e, ClientError): return {"code": e.err_code, "msg": e.err_message}
            return {"code":-1, "msg":str(e)}
    
    def get_open_position(self, symbol: str = None) -> dict:
        target_symbol = symbol or self.symbol
        long_pos, short_pos = {}, {}
        try:
            positions_risk = self.client.get_position_risk(symbol=target_symbol, recvWindow=5000)
            for pos_data in positions_risk:
                if pos_data['symbol'] == target_symbol:
                    pos_amt_val = float(pos_data.get('positionAmt', '0'))
                    if abs(pos_amt_val) > 1e-9: 
                        avg_price = pos_data.get('entryPrice', '0')
                        details = {"avgPrice": avg_price, "positionAmt": abs(pos_amt_val)}
                        current_pos_side_api = pos_data.get('positionSide') 
                        if self.binance_hedge_mode:
                            if current_pos_side_api == "LONG": long_pos = details
                            elif current_pos_side_api == "SHORT": short_pos = details
                        else: 
                            if pos_amt_val > 0: long_pos = details
                            elif pos_amt_val < 0: short_pos = details
            return {"LONG": long_pos, "SHORT": short_pos}
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION get_open_position: {e}")
            return {"LONG": {}, "SHORT": {}}

    def monedas_de_entrada(self, positionside_to_check:str) -> dict:
        pos_handler = PosLong if positionside_to_check == "LONG" else PosShort
        precio_ref = self.precio_entrada_referencia 
        if not precio_ref or precio_ref <= 0:
            precio_ref = self.get_current_market_price()
            if not precio_ref or precio_ref <= 0:
                return {"monedas":0,"cant_ree":0,"error":"Fallo al obtener precio de mercado para monedas_de_entrada"}

        qty = self.cantidad_a_operar_inicial
        if qty == 0: 
            if self.usdt_entrada_inicial > 0: qty = self.usdt_entrada_inicial / precio_ref
            elif self.monto_sl_base > 0 and self.dist_ree > 0:
                sl_calc_price = precio_ref * (1 - self.dist_ree/100) if positionside_to_check=="LONG" else precio_ref * (1 + self.dist_ree/100)
                if abs(precio_ref - sl_calc_price) < float(self.pip_precio or 1e-9): 
                    return {"monedas":0,"cant_ree":0,"error":"SL y precio ref. muy cercanos para cálculo de vol."}
                qty = pos_handler.vol_monedas(self.monto_sl_base, precio_ref, sl_calc_price)
                if self.cant_ree > 0 and qty > 0: qty /= (self.cant_ree + 1) 
            else: return {"monedas":0,"cant_ree":0,"error":"No se puede determinar cantidad de entrada (USDT o MontoSL/DistRee)."}
        
        if qty <=0: return {"monedas":0,"cant_ree":0, "error":f"Cantidad calculada es <=0: {qty}"}
        
        qty_formateada = mgo.redondeo(qty, self.qty_step, self.cant_decimales_moneda) if self.qty_step and self.cant_decimales_moneda is not None else qty

        try:
            re_data = pos_handler.recompras(precio_ref, self.monto_sl_base, self.cant_ree, self.dist_ree, 
                                            qty_formateada, self.porcentaje_vol_ree, self.usdt_entrada_inicial, self.gestion_vol)
            return {"monedas":float(qty_formateada), "cant_ree":len(re_data.get("prices",[]))}
        except Exception as e_mgo: 
            print(f"[{self.bot_name}] EXCEPTION mgo.recompras: {e_mgo}")
            return {"monedas":float(qty_formateada),"cant_ree":0,"error":f"mgo.recompras exc: {e_mgo}"}

    def get_current_open_orders(self, symbol:str=None, order_type_filter_str:str=None, side_filter_logic:str=None) -> dict:
        target_symbol = symbol or self.symbol
        L_ids,L_amts,L_prcs, S_ids,S_amts,S_prcs = [],[],[], [],[],[]
        try:
            open_orders = self.client.get_open_orders(symbol=target_symbol, recvWindow=5000)
            for o in open_orders:
                api_order_type = o.get("type","").upper() 
                api_order_side = o.get("side","").upper() 
                api_pos_side_from_order = o.get("positionSide","").upper()
                is_reduce_only_api = o.get("reduceOnly", False)

                if order_type_filter_str:
                    filter_upper = order_type_filter_str.upper()
                    is_sl_type_api = api_order_type in ["STOP", "STOP_MARKET"]
                    is_tp_type_api = api_order_type in ["TAKE_PROFIT", "TAKE_PROFIT_MARKET"]
                    
                    if filter_upper == "STOPLOSS" and not is_sl_type_api: continue
                    elif filter_upper == "TAKEPROFIT" and not is_tp_type_api: continue
                    elif filter_upper not in ["STOPLOSS", "TAKEPROFIT"] and filter_upper != api_order_type: continue
                
                order_belongs_to_logic_side = None
                if self.binance_hedge_mode: 
                    if api_pos_side_from_order == "LONG": order_belongs_to_logic_side = "LONG"
                    elif api_pos_side_from_order == "SHORT": order_belongs_to_logic_side = "SHORT"
                else: 
                    if is_reduce_only_api: 
                        if api_order_side == "SELL": order_belongs_to_logic_side = "LONG" 
                        elif api_order_side == "BUY": order_belongs_to_logic_side = "SHORT" 
                    else: 
                        if api_order_side == "BUY": order_belongs_to_logic_side = "LONG"
                        elif api_order_side == "SELL": order_belongs_to_logic_side = "SHORT"
                
                if side_filter_logic and side_filter_logic.upper() != order_belongs_to_logic_side:
                    continue

                order_id = o.get("orderId")
                qty = float(o.get("origQty",0))
                price = float(o.get("price",0)) if o.get("price") != "0" else float(o.get("stopPrice",0)) 

                if order_belongs_to_logic_side == "LONG":
                    L_ids.append(order_id); Lamt.append(qty); Lprcs.append(price)
                elif order_belongs_to_logic_side == "SHORT":
                    S_ids.append(order_id); Samt.append(qty); Sprcs.append(price)
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION get_current_open_orders: {e}")
            
        return {"symbol":target_symbol,"long_orders_id":L_ids,"long_amt_orders":Lamt,"long_price_orders":Lprcs,
                "short_orders_id":S_ids,"short_amt_orders":Samt,"short_price_orders":Sprcs,
                "long_total":len(L_ids),"short_total":len(S_ids)}

    def dynamic_sl_manager(self, symbol:str=None, positionside_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.logic_positionside
        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt, avg_px = float(pos_info.get("positionAmt",0)), float(pos_info.get("avgPrice",0))

        if pos_amt > 0 and avg_px > 0:
            orders = self.get_current_open_orders(target_symbol, "STOPLOSS", target_ps) 
            
            handler = PosLong if target_ps=="LONG" else PosShort
            sl_px = handler.stop_loss(avg_px, self.monto_sl_base, pos_amt) 
            if not sl_px or sl_px <= 0: 
                print(f"[{self.bot_name}] Invalid SL price ({sl_px}) for {target_ps} {target_symbol}.")
                return

            ordenes_sl_existentes = orders.get(f"{target_ps.lower()}_orders_id", [])
            if not ordenes_sl_existentes:
                print(f"[{self.bot_name}] {target_ps}: No SL. Colocando SL@{sl_px} (Tipo:{self.tipo_orden_sl_tp_config})...")
                self.set_stop_loss(target_symbol, target_ps, pos_amt, sl_px)
            else: 
                sl_correcto_encontrado = False
                for i, sl_id in enumerate(ordenes_sl_existentes):
                    curr_sl_qty = orders[f"{target_ps.lower()}_amt_orders"][i]
                    curr_sl_trig_px = orders[f"{target_ps.lower()}_price_orders"][i]
                    qty_ok = abs(curr_sl_qty - pos_amt) < float(self.qty_step or 1e-8)
                    price_ok = abs(curr_sl_trig_px - sl_px) < float(self.pip_precio or 1e-8) * 2 
                    if qty_ok and price_ok: sl_correcto_encontrado = True; break 
                if not sl_correcto_encontrado:
                    print(f"[{self.bot_name}] {target_ps}: SL no coincide con el calculado ({sl_px}). Reemplazando...")
                    for sl_id_to_cancel in ordenes_sl_existentes:
                        self._cancel_order(target_symbol, order_id=str(sl_id_to_cancel)); time.sleep(0.2)
                    self.set_stop_loss(target_symbol, target_ps, pos_amt, sl_px)
    
    def dynamic_tp_manager(self, symbol:str=None, positionside_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.logic_positionside
        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt, avg_px = float(pos_info.get("positionAmt",0)), float(pos_info.get("avgPrice",0))

        if pos_amt > 0 and avg_px > 0:
            orders = self.get_current_open_orders(target_symbol, "TAKEPROFIT", target_ps)
            handler = PosLong if target_ps=="LONG" else PosShort
            tp_px = handler.take_profit(self.gestion_take_profit, avg_px, self.monto_sl_base, pos_amt, self.ratio_beneficio_perdida)
            if not tp_px or tp_px <= 0: 
                print(f"[{self.bot_name}] Invalid TP price ({tp_px}) for {target_ps} {target_symbol}.")
                return

            ordenes_tp_existentes = orders.get(f"{target_ps.lower()}_orders_id", [])
            if not ordenes_tp_existentes:
                print(f"[{self.bot_name}] {target_ps}: No TP. Colocando TP@{tp_px} (Tipo:{self.tipo_orden_sl_tp_config})...")
                self.set_take_profit(target_symbol, target_ps, pos_amt, tp_px)
            else:
                tp_correcto_encontrado = False
                for i, tp_id in enumerate(ordenes_tp_existentes):
                    curr_tp_qty = orders[f"{target_ps.lower()}_amt_orders"][i]
                    curr_tp_trig_px = orders[f"{target_ps.lower()}_price_orders"][i]
                    qty_ok = abs(curr_tp_qty - pos_amt) < float(self.qty_step or 1e-8)
                    price_ok = abs(curr_tp_trig_px - tp_px) < float(self.pip_precio or 1e-8) * 5
                    if qty_ok and price_ok: tp_correcto_encontrado = True; break
                if not tp_correcto_encontrado:
                    print(f"[{self.bot_name}] {target_ps}: TP no coincide con el calculado ({tp_px}). Reemplazando TPs...")
                    for tp_id_to_cancel in ordenes_tp_existentes:
                        self._cancel_order(target_symbol, order_id=str(tp_id_to_cancel)); time.sleep(0.2)
                    self.set_take_profit(target_symbol, target_ps, pos_amt, tp_px)

    def dynamic_reentradas_manager(self, symbol:str=None, positionside_param:str=None, modo_gestion_param:str=None):
        target_symbol = symbol or self.symbol
        target_ps = positionside_param or self.logic_positionside
        target_mg = modo_gestion_param or self.modo_gestion
        if target_mg not in ["REENTRADAS","SNOW BALL"]: return

        pos_info = self.get_open_position(target_symbol).get(target_ps.upper(), {})
        pos_amt = float(pos_info.get("positionAmt", 0))
        
        if pos_amt > 0: 
            monedas_info = self.monedas_de_entrada(target_ps) 
            if monedas_info.get("error"): 
                print(f"[{self.bot_name}] Error en dynamic_reentradas_manager (monedas_de_entrada): {monedas_info['error']}")
                return
            
            monedas_base_exp = monedas_info.get("monedas",0)
            cant_ree_exp = monedas_info.get("cant_ree",0)
            if cant_ree_exp == 0: return 

            qty_match_base = abs(pos_amt - monedas_base_exp) < float(self.qty_step or 1e-9) 
            
            order_type_ree_filter = "LIMIT" if target_mg == "REENTRADAS" else "STOP_MARKET" 
            
            open_ree_orders = self.get_current_open_orders(target_symbol, order_type_filter_str=order_type_ree_filter, side_filter_logic=target_ps)
            num_ree_abiertas = open_ree_orders.get(f"{target_ps.lower()}_total",0)

            if qty_match_base and num_ree_abiertas != cant_ree_exp: 
                print(f"[{self.bot_name}] {target_ps} ({target_mg}): Reentradas {num_ree_abiertas} vs esp {cant_ree_exp}. Ajustando...")
                for oid in open_ree_orders.get(f"{target_ps.lower()}_orders_id",[]):
                    self._cancel_order(target_symbol, order_id=str(oid)); time.sleep(0.25)
                
                self.set_limit_market_order(target_symbol, target_ps, target_mg, f"ree_{target_ps[:3].lower()}")

    def set_limit_market_order(self, symbol:str, logic_positionside_param:str, modo_gestion_param:str, 
                                client_order_id_prefix:str="entrada")->dict:
        target_symbol = symbol or self.symbol
        target_ps = logic_positionside_param or self.logic_positionside
        target_mg = modo_gestion_param or self.modo_gestion
        print(f"[{self.bot_name}] Iniciando set_limit_market_order para {target_symbol}-{target_ps}, Modo: {target_mg}")

        monedas_info = self.monedas_de_entrada(target_ps)
        if monedas_info.get("error"):
            print(f"[{self.bot_name}] Error (monedas_de_entrada): {monedas_info['error']}")
            return {"code":-1,"msg":monedas_info["error"]}
        
        qty_inicial_calculada = monedas_info.get("monedas",0)
        num_ree_plan = monedas_info.get("cant_ree",0)

        if qty_inicial_calculada <= 0:
            return {"code":-1,"msg":f"Qty inicial inválida: {qty_inicial_calculada}"}
        
        self.cantidad_a_operar_inicial = qty_inicial_calculada 
        tipo_orden_inicial_api = self.tipo_orden_entrada 
        precio_lmt_orden_inicial = self.precio_entrada_referencia if tipo_orden_inicial_api=="LIMIT" else None

        current_pos_data = self.get_open_position(target_symbol)
        pos_qty_actual = float(current_pos_data.get(target_ps.upper(),{}).get("positionAmt",0))
        
        resp_primera_orden = None
        min_comparable_qty = float(self.min_qty_compra or 0.000001) 

        if pos_qty_actual < min_comparable_qty: 
            print(f"[{self.bot_name}] Colocando orden INICIAL {target_ps}: Qty={self.cantidad_a_operar_inicial}, Tipo={tipo_orden_inicial_api}, PrecioLMT={precio_lmt_orden_inicial or 'N/A'}")
            cid_inicial = f"{client_order_id_prefix}_{target_symbol[:3].lower()}_{int(time.time()*1000)%10000}"
            
            resp_primera_orden = self._limit_market_order(target_symbol,target_ps,self.cantidad_a_operar_inicial,precio_lmt_orden_inicial,tipo_orden_inicial_api,cid_inicial)
            
            # Binance no soporta SL/TP adjuntos en la misma orden de entrada. Se colocan después.
            if resp_primera_orden.get("code", 0) != 0 and resp_primera_orden.get("orderId", 0) == 0 : 
                print(f"[{self.bot_name}] Error al colocar orden inicial: {resp_primera_orden.get('msg')}")
                return resp_primera_orden 
            
            if tipo_orden_inicial_api=="LIMIT" and precio_lmt_orden_inicial: self.precio_entrada_referencia = precio_lmt_orden_inicial
            if target_mg == "DINAMICO": return resp_primera_orden 
        else:
            print(f"[{self.bot_name}] Posición {target_ps} ya existente (Qty: {pos_qty_actual}). Omitiendo orden inicial.")
            self.precio_entrada_referencia = float(current_pos_data.get(target_ps.upper(),{}).get("avgPrice", self.precio_entrada_referencia))

        if num_ree_plan > 0 and target_mg in ["REENTRADAS", "SNOW BALL"]:
            precio_base_re = self.precio_entrada_referencia 
            if not precio_base_re or precio_base_re <= 0 :
                precio_base_re = self.get_current_market_price()
                if not precio_base_re or precio_base_re <=0:
                    return resp_primera_orden or {"code":-1, "msg":"Precio base inválido para reentradas"}

            print(f"[{self.bot_name}] Preparando {num_ree_plan} órdenes de {target_mg} para {target_ps} desde precio base {precio_base_re}...")
            handler = PosLong if target_ps=="LONG" else PosShort
            data_ree_fn = handler.recompras if target_mg=="REENTRADAS" else handler.snow_ball
            
            params_ree=data_ree_fn(precio_base_re, self.monto_sl_base, num_ree_plan, self.dist_ree, 
                                    self.cantidad_a_operar_inicial, 
                                    self.porcentaje_vol_ree, self.usdt_entrada_inicial, self.gestion_vol)
            
            if params_ree and params_ree.get("prices"):
                api_pos_side_for_reentry = self.binance_api_position_side_for_entry
                if self.binance_hedge_mode: api_pos_side_for_reentry = target_ps

                for i, (price_re, qty_re) in enumerate(zip(params_ree["prices"], params_ree["quantitys"])):
                    if qty_re <=0 or price_re <=0: 
                        print(f"[{self.bot_name}] Advertencia: Reentrada {i+1} con datos inválidos (Qty:{qty_re}, Prc:{price_re}). Saltando.")
                        continue
                    
                    cid_r = f"ree{i+1}_{target_symbol[:3].lower()}_{int(time.time()*1000+i)%10000}"
                    qty_re_str = self._format_quantity(qty_re)
                    price_re_str = self._format_price(price_re)
                    
                    order_type_re_api, stop_price_re_api = None, None
                    if target_mg == "REENTRADAS": order_type_re_api = "LIMIT"
                    elif target_mg == "SNOW BALL": order_type_re_api = "STOP_MARKET"; stop_price_re_api = price_re_str
                    
                    print(f"[{self.bot_name}]   Reentrada {i+1}: Qty={qty_re_str}, Precio/Trigger={price_re_str}, Tipo={order_type_re_api}")
                    
                    self._place_order_internal(
                        symbol=target_symbol, order_side_api="BUY" if target_ps=="LONG" else "SELL", 
                        order_type_api=order_type_re_api, quantity_str=qty_re_str, 
                        price_str=price_re_str if order_type_re_api=="LIMIT" else None,
                        position_side_for_api=api_pos_side_for_reentry, stop_price_str=stop_price_re_api,
                        client_order_id=cid_r, reduce_only_bool=False
                    )
                    time.sleep(0.25) 
            else: print(f"[{self.bot_name}] No se generaron datos para órdenes de {target_mg} desde mgo.")
        
        return resp_primera_orden or {"code":0, "msg":"Proceso de órdenes completado (ver logs)."}


    # --- Métodos WebSocket y Lógica Principal (Paso 6) ---
    def get_last_candles(self, symbol:str=None, interval:str=None, limit:int=1) -> list:
        target_symbol = symbol or self.symbol
        target_interval = interval or self.temporalidad
        try:
            # Binance klines: [open_time, open, high, low, close, volume, close_time, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore]
            raw_candles = self.client.klines(symbol=target_symbol, interval=target_interval, limit=limit)
            if not raw_candles: return [{"s":target_symbol,"t":target_interval}] 
            
            formatted_candles = []
            for k in raw_candles: # Binance devuelve el más antiguo primero, el más reciente al final
                formatted_candles.append({
                    "timestamp": int(k[0]), "open": float(k[1]), "high": float(k[2]), 
                    "low": float(k[3]), "close": float(k[4]), "volume": float(k[5]), 
                    "turnover": float(k[7]) # quote_asset_volume es turnover
                })
            return [{"s":target_symbol,"t":target_interval}] + formatted_candles # Mantener consistencia con Bybit (header + velas)
        except (ClientError, ServerError, Exception) as e:
            print(f"[{self.bot_name}] EXCEPTION get_last_candles: {e}")
            return [{"s":target_symbol,"t":target_interval}] 

    def on_message_websocket_kline(self, ws_client_obj, message:dict): # ws_client_obj es pasado por UMFuturesWebsocketClient
        # print(f"[{self.bot_name}] WS Mensaje KLINE: {message}") # Debug
        if message and isinstance(message,dict) and message.get('e') == 'kline': # Verificar tipo de evento
            kline_data = message.get('k', {})
            if kline_data:
                self.last_price = float(kline_data.get('c', self.last_price)) # Precio de cierre de la vela
                # print(f"[{self.bot_name}] WS Precio {self.symbol}: {self.last_price}")
                self.check_strategy(self.last_price)
                if self.position_opened_by_strategy:
                    print(f"[{self.bot_name}] Posición abierta por check_strategy. Deteniendo WS de entrada.")
                    self.stop_websocket() 
                    self.position_opened_by_strategy = False 
    
    def start_websocket(self):
        if self.ws_running: print(f"[{self.bot_name}] WS ya en ejecución."); return
        if not self.ws_should_run: print(f"[{self.bot_name}] WS no debe correr (ws_should_run=False)."); return
        
        print(f"[{self.bot_name}] Iniciando WS para {self.symbol} kline {self.temporalidad}...")
        self.ws_running = True
        try:
            # Para UMFuturesWebsocketClient, el on_message es el general, no específico por stream.
            # Se suscribe a streams y el callback general maneja los mensajes.
            self.ws_client = UMFuturesWebsocketClient(on_message=self.on_message_websocket_kline, is_testnet=self.testnet)
            self.ws_client.kline(symbol=self.symbol, interval=self.temporalidad, id=1) # id es opcional pero bueno para identificar
            print(f"[{self.bot_name}] WS suscrito a kline.{self.temporalidad}.{self.symbol}. Esperando mensajes...")
            # El UMFuturesWebsocketClient maneja su propio hilo y reconexiones.
            # No se necesita un bucle while True aquí para mantenerlo vivo si el script principal sigue corriendo.
        except Exception as e:
            print(f"[{self.bot_name}] EXCEPTION al iniciar WS: {e}")
            self.ws_running = False
            self.__reconnect_websocket()

    def __reconnect_websocket(self):
        if self.ws_should_run:
            print(f"[{self.bot_name}] Intentando reconectar WS en {self.ws_reconnect_delay}s...")
            time.sleep(self.ws_reconnect_delay)
            print(f"[{self.bot_name}] Reconectando WS...")
            self.start_websocket()
        else: print(f"[{self.bot_name}] WS no debe correr, no se reconectará.")
            
    def stop_websocket(self):
        print(f"[{self.bot_name}] Deteniendo WS intencionalmente...")
        self.ws_should_run = False 
        if self.ws_client and self.ws_running: # Usar ws_client
            try: self.ws_client.stop() # El método para detener puede variar, consultar docs de python-binance
            except Exception as e_ws_exit: print(f"[{self.bot_name}] Excepción al cerrar WS: {e_ws_exit}")
        self.ws_running = False
        print(f"[{self.bot_name}] WS detenido.")

    def check_strategy(self, current_price:float):
        current_pos = self.get_open_position(self.symbol)
        # Bot está configurado para un lado específico (LONG o SHORT) o para AMBOS (BOTH)
        # Si es BOTH, la estrategia de entrada simple basada en precio_entrada_long/short podría no ser ideal
        # ya que podría intentar abrir LONG y SHORT simultáneamente si las condiciones se dan.
        # Por ahora, si es BOTH, esta función no hará nada para entradas automáticas.
        
        if self.logic_positionside == "LONG":
            if current_pos.get("LONG",{}).get("positionAmt",0) > 0: return 
            if self.precio_entrada_long > 0 and current_price <= self.precio_entrada_long:
                print(f"[{self.bot_name}] SEÑAL LONG: Precio {current_price} <= Trigger {self.precio_entrada_long}. Ejecutando entrada...")
                result = self.set_limit_market_order(self.symbol, "LONG", self.modo_gestion)
                if result.get("orderId"): self.position_opened_by_strategy = True
                else: print(f"[{self.bot_name}] Fallo al colocar orden LONG por señal: {result.get('msg')}")
        elif self.logic_positionside == "SHORT":
            if current_pos.get("SHORT",{}).get("positionAmt",0) > 0: return 
            if self.precio_entrada_short > 0 and current_price >= self.precio_entrada_short:
                print(f"[{self.bot_name}] SEÑAL SHORT: Precio {current_price} >= Trigger {self.precio_entrada_short}. Ejecutando entrada...")
                result = self.set_limit_market_order(self.symbol, "SHORT", self.modo_gestion)
                if result.get("orderId"): self.position_opened_by_strategy = True
                else: print(f"[{self.bot_name}] Fallo al colocar orden SHORT por señal: {result.get('msg')}")

    def monitor_open_positions(self):
        print(f"[{self.bot_name}] Iniciando monitoreo para {self.symbol} - {self.logic_positionside}, Modo: {self.modo_gestion}")
        self._iniciar_monitor_memoria()
        
        MAX_HTTP_REQUESTS_PER_INTERVAL = 15 
        HTTP_INTERVAL_SECONDS = int(self.dict_config.get("segundos_monitoreo_http", 60)) 
        http_request_count = 0; last_http_cycle_time = time.time()
        
        self.ws_should_run = True 

        while self.ws_should_run: 
            try:
                now = time.time()
                if now - last_http_cycle_time < HTTP_INTERVAL_SECONDS and http_request_count >= MAX_HTTP_REQUESTS_PER_INTERVAL :
                    time.sleep(1); continue
                if now - last_http_cycle_time >= HTTP_INTERVAL_SECONDS:
                    http_request_count = 0; last_http_cycle_time = now

                current_pos_data = self.get_open_position(self.symbol); http_request_count +=1
                
                sides_to_manage = []
                if self.logic_positionside == "LONG" and current_pos_data.get("LONG",{}).get("positionAmt",0) > 0:
                    sides_to_manage.append("LONG")
                elif self.logic_positionside == "SHORT" and current_pos_data.get("SHORT",{}).get("positionAmt",0) > 0:
                    sides_to_manage.append("SHORT")
                elif self.logic_positionside == "BOTH": 
                    if current_pos_data.get("LONG",{}).get("positionAmt",0) > 0 : sides_to_manage.append("LONG")
                    if current_pos_data.get("SHORT",{}).get("positionAmt",0) > 0 : sides_to_manage.append("SHORT")
                
                if sides_to_manage:
                    if self.ws_running: self.stop_websocket() 
                    for side in sides_to_manage:
                        print(f"[{self.bot_name}] Gestionando posición {side} para {self.symbol}...")
                        self.dynamic_sl_manager(symbol=self.symbol, positionside_param=side); http_request_count+=1
                        self.dynamic_tp_manager(symbol=self.symbol, positionside_param=side); http_request_count+=1
                        self.dynamic_reentradas_manager(symbol=self.symbol, positionside_param=side); http_request_count+=1
                else: # No positions for the configured logic_positionside (or BOTH and no positions)
                    if not self.ws_running: self.start_websocket() 
                
                if self.ws_running: time.sleep(1) 
                else: time.sleep(max(1, HTTP_INTERVAL_SECONDS // MAX_HTTP_REQUESTS_PER_INTERVAL if MAX_HTTP_REQUESTS_PER_INTERVAL > 0 else HTTP_INTERVAL_SECONDS))

            except KeyboardInterrupt: 
                print(f"[{self.bot_name}] KeyboardInterrupt en monitor_open_positions.")
                self.ws_should_run = False; break 
            except Exception as e:
                print(f"[{self.bot_name}] ERROR en bucle monitor_open_positions: {e}"); import traceback; traceback.print_exc()
                time.sleep(20) 
        
        print(f"[{self.bot_name}] Saliendo de monitor_open_positions.")
        self.stop_websocket() 
        self._detener_monitor_memoria()

    def _monitor_memoria(self):
        proceso = psutil.Process(os.getpid())
        while not self._detener_monitor_mem.is_set():
            memoria = proceso.memory_info().rss / 1024**2 
            print(f"[{self.bot_name}][MONITOR MEM] Uso: {memoria:.2f} MB")
            if self._detener_monitor_mem.wait(self.segundos_monitoreo_mem): break 
    def _iniciar_monitor_memoria(self):
        if self.segundos_monitoreo_mem > 0 and (not self._hilo_monitor_mem or not self._hilo_monitor_mem.is_alive()):
            self._detener_monitor_mem.clear()
            self._hilo_monitor_mem = threading.Thread(target=self._monitor_memoria, daemon=True)
            self._hilo_monitor_mem.start()
            print(f"[{self.bot_name}] Monitor de memoria iniciado (cada {self.segundos_monitoreo_mem}s).")
    def _detener_monitor_memoria(self):
        if self._hilo_monitor_mem and self._hilo_monitor_mem.is_alive():
            self._detener_monitor_mem.set()
            self._hilo_monitor_mem.join(timeout=2) 
            print(f"[{self.bot_name}] Monitor de memoria detenido.")


if __name__ == "__main__":
    print("--- INICIO DE PRUEBA DEL BOT BINANCE ---")
    test_api_key = os.getenv("vNKhE3Q2ha3TryT9eBoEhdB7HDG2jJ9rOXNb4TImjJytTYwxLya9zSVKxe5JNOnP")
    test_api_secret = os.getenv("vbrciyy43fKjJsNajNQHi0qzFEY6J9826JV7orPFnG3el15ur2LF0f2V2mFId8MC")

    if not test_api_key or not test_api_secret:
        print("ERROR: Variables de entorno BINANCE_TESTNET_API_KEY o BINANCE_TESTNET_API_SECRET no encontradas.")
    else:
        config_binance_test = {
            "bot_name": "BinanceTest01", "api_key": test_api_key, "api_secret": test_api_secret, 
            "testnet": True, "symbol": "DOGEUSDT", 
            "positionside": "LONG", # "LONG", "SHORT", o "BOTH" (para la lógica del bot)
            "modo_cobertura": False, # False para ONE_WAY, True para HEDGE en Binance

            "apalancamiento": 10, 
            "monto_sl_base": 10.0, # USDT para cálculos de SL por mgo, o SL fijo GAFAS.

            "modo_gestion_de_ordenes": "REENTRADAS", # "DINAMICO", "REENTRADAS", "SNOW BALL", "GAFAS"
            "tipo_de_orden_entrada": "MARKET",  # "MARKET" o "LIMIT" para la orden de entrada inicial.
            "precio_entrada_referencia": 0, # Para orden LMT inicial. Si 0 y tipo_orden_entrada="LIMIT", se usa precio actual.

            "precio_entrada_long": 0.2100,  # AJUSTAR: Disparar LONG si precio <= este valor
            "precio_entrada_short": 0.4000, # AJUSTAR: Disparar SHORT si precio >= este valor

            "gestion_take_profit": "RATIO BENEFICIO/PERDIDA", 
            "ratio_beneficio_perdida": 1.5, 
            "tipo_orden_sl_tp": "MARKET", # "MARKET" o "LIMIT" para SL/TP dinámicos. Binance usa STOP_MARKET/TAKE_PROFIT_MARKET o STOP/TAKE_PROFIT.

            "cantidad_a_operar_inicial": 0, 
            "usdt_entrada_inicial": 20,    # Si >0 y cantidad_a_operar_inicial=0, se usa para calcularla.

            "cant_ree": 2, "dist_ree": 0.5, "gestion_vol": "FIJO", "porcentaje_vol_ree": 0,

            "segundos_monitoreo_http": 20, 
            "segundos_monitoreo_memoria": 0, # 0 para desactivar
            "temporalidad": "1m"             
        }

        print(f"\n[MAIN CONFIG: Bot '{config_binance_test['bot_name']}' para {config_binance_test['symbol']} en modo {config_binance_test['positionside']}]")
        print(f"  - Modo Gestión Órdenes: {config_binance_test['modo_gestion_de_ordenes']}")
        print(f"  - Señal Entrada LONG si precio <= {config_binance_test['precio_entrada_long']}")
        print(f"  - Señal Entrada SHORT si precio >= {config_binance_test['precio_entrada_short']}")
        print(f"  - Testnet: {'Sí' if config_binance_test['testnet'] else 'No (MAINNET - CUIDADO!)'}")

        binance_bot_main_instance = None
        try:
            binance_bot_main_instance = Binance(dict_config=config_binance_test)

            # --- Pruebas de Información (Descomentar selectivamente para verificar) ---
            print(f"  Detalles del Instrumento ({binance_bot_main_instance.symbol}): {binance_bot_main_instance.get_instrument_details()}")
            balance_info = binance_bot_main_instance.get_balance(coin_symbol='USDT')
            print(f"  Balance (USDT): {balance_info}")
            print(f"  Apalancamiento Actual: {binance_bot_main_instance.get_current_leverage()}x")
            print(f"  Posiciones Abiertas Actuales: {binance_bot_main_instance.get_open_position()}")

            # --- Iniciar el ciclo principal del bot ---
            print("\n[MAIN] Iniciando monitor_open_positions()... (Presiona Ctrl+C para detener)")
            # binance_bot_main_instance.monitor_open_positions() # DESCOMENTAR PARA EJECUTAR EL BOT

            print("\n[MAIN] Bot instanciado. Para ejecutar el monitoreo, descomenta la línea 'binance_bot_main_instance.monitor_open_positions()' en __main__.")
            print("[MAIN] Asegúrate de que los precios de entrada ('precio_entrada_long', 'precio_entrada_short') son realistas para tu prueba.")


        except KeyboardInterrupt:
            print("\n[MAIN] Bot detenido manualmente por el usuario (KeyboardInterrupt).")
        except Exception as e_main:
            print(f"\n[MAIN] Error CRÍTICO durante la ejecución del bot: {e_main}")
            import traceback; traceback.print_exc()
        finally:
            if binance_bot_main_instance:
                print("[MAIN] Finalizando bot y limpiando recursos...")
                binance_bot_main_instance.ws_should_run = False
                binance_bot_main_instance.stop_websocket()
                binance_bot_main_instance._detener_monitor_memoria()
            print("[MAIN] Proceso de prueba del bot finalizado.")

    print("\n--- FIN DE PRUEBA DEL BOT BINANCE ---")
