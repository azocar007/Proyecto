""" Archivo final del bot AZC con control completo desde clase BotRunner. """

from exchanges.BINGX import BingX
from strategys import SMA_MACD_BB, SMA_BB, CRUCE_BB, AUTO_SL_TP, SMA_MACD_BB_GPT
import Modos_de_gestion_operativa as mgo
from threading import Thread
import time
from datetime import datetime
import traceback


""" Datos para la gestión de RIESGO y CAPITAL """

Datos = {
        # Datos para operar en el exchange
        "exchange": "BINGX",                                # Nombre del exchange a utilizar (ejemplo: "BINGX", "BINANCE", "BYBIT", "PHEMEX")
        "symbol": "DOGE",                                    # Símbolo del par a operar (ejemplo: "doge", "btc", "eth")
        "positionside": "LONG",                            # Dirección inicial LONG o SHORT
        "modo_operacion": "SIMULTANEO",                       # "UNICO" - "ALTERNADO" - "SIMULTANEO" - "CARDIACO"
        "type": "LIMIT",                                    # "LIMIT" - "MARKET" - "BBO"
        "temporalidad": "1m",                               # Temporalidad de las velas a utilizar (ejemplo: "1m", "5m", "15m", "1h", "4h", "1d")
        "tiempo_espera": 0,                               # Tiempo de espera entre chequeos de ordenes pendientes (en segundos)
        "cant_velas": 200,                                  # Cantidad de velas a solicitar al exchange para el dataframe dinamico de la estrategia
        # Datos para la gestión STOP LOSS
        "modo_gestion": "RATIO BENEFICIO/PERDIDA",          # "REENTRADAS" - "RATIO BENEFICIO/PERDIDA" - "SNOW BALL"
        "monto_sl": 0.25,                                    # Monto en USDT para el Stop Loss
        "gestion_vol": "MARTINGALA",                        # "% DE REENTRADAS" - "MARTINGALA" - "AGRESIVO"
        "cant_ree": 10,                                      # Cantidad de reentradas
        "dist_ree": 2,                                      # Distancia en porcentaje entre reentradas (ejemplo: 2 = 2%)
        "porcentaje_vol_ree": 0,                            # Porcentaje de volumen para reentradas (ejemplo: 50% del volumen anterior)    
        "monedas": 0,                                      # Cantidad de monedas para la 1ra operación
        "usdt": 0,                                          # Cantidad de USDT para la 1ra operación (si se usa "monedas" se ignora este valor)
        # Datos para la gestion de TAKE PROFIT
        "gestion_take_profit": "RATIO BENEFICIO/PERDIDA",   # "RATIO BENEFICIO/PERDIDA" - "% TAKE PROFIT" - "LCD" (Carga y Descarga todavia no esta definido)
        "ratio": 2                                          # Ratio de beneficio/perdida para el Stop Loss y Take Profit
        }

""" Estrategia a emplear """
Estrategia = SMA_MACD_BB_GPT.SMA_MACD_BB

""" Clase para ejecución del Bot """

class BotRunner:
    def __init__(self, datos, estrategia):
        self.datos = datos
        self.estrategia = estrategia
        self.modo = datos["modo_operacion"].upper()
        self.direccion_inicial = datos["positionside"].upper()
        self.MonitorMemoria = mgo.Monitor_Memoria()
        self._log(f"Inicializando BotRunner | Modo: {self.modo}")

    def iniciar(self):
        try:
            self.MonitorMemoria.iniciar()

            if self.modo == "UNICO":
                self._modo_unico()
            elif self.modo == "ALTERNADO":
                self._modo_alternado()
            elif self.modo == "SIMULTANEO":
                self._modo_simultaneo()
            elif self.modo == "CARDIACO":
                self._modo_cardiaco()
            else:
                raise ValueError("❌ Class BotRunner - Modo no válido.")

        except Exception as e:
            self._log(f"❌ Class BotRunner - Bot detenido por: {e}")
            #traceback.print_exc()

    def _modo_unico(self):
        self._log(f"🎯 Modo ÚNICO | Dirección: {self.direccion_inicial}")
        self.datos["positionside"] = self.direccion_inicial
        bot = BingX(self.estrategia, self.datos)
        bot.master_monitor()

    def _modo_alternado(self):
        self._log("🔁 Modo ALTERNADO entre LONG y SHORT")
        actual = self.direccion_inicial
        bot = BingX(self.estrategia, self.datos)

        while True:
            bot.positionside = actual
            self._log(f"▶️ Ejecutando dirección: {actual}")
            bot.master_monitor()

            while self._existe_posicion_abierta(bot, actual):
                self._log(f"⏳ Esperando cierre de posición {actual}...")
                time.sleep(10)

            actual = "SHORT" if actual == "LONG" else "LONG"
            time.sleep(3)

    def _modo_simultaneo(self):
        self._log("⚔️ Modo SIMULTÁNEO ejecutando LONG y SHORT")

        def run_dir(dir):
            datos_copia = self.datos.copy()
            datos_copia["positionside"] = dir
            bot_local = BingX(self.estrategia, datos_copia)
            while True:
                try:
                    self._log(f"▶️ [{dir}] monitor_open_positions()")
                    bot_local.master_monitor()
                except Exception as e:
                    self._log(f"❌ Class BotRunner - Error en hilo {dir}: {e}")
                    #traceback.print_exc()
                    break
                time.sleep(3)

        t1 = Thread(target=run_dir, args=("LONG",))
        t2 = Thread(target=run_dir, args=("SHORT",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def _modo_simultaneo_2(self):
        self._log("⚔️ Modo SIMULTÁNEO ejecutando LONG y SHORT")

        def run_dir(dir):
            datos_copia = self.datos.copy()
            datos_copia["positionside"] = dir
            bot_local = BingX(self.estrategia, datos_copia)
            bot_local.positionside = dir  # 🔹 Para mantener consistencia en los logs
            while True:
                try:
                    self._log(f"▶️ [{dir}] monitor_open_positions()")
                    bot_local.master_monitor(
                                            symbol=datos_copia["symbol"],
                                            positionside=dir
                                            )
                except Exception as e:
                    self._log(f"❌ Class BotRunner - Error en hilo {dir}: {e}")
                    break
                time.sleep(3)

        t1 = Thread(target=run_dir, args=("LONG",))
        t2 = Thread(target=run_dir, args=("SHORT",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def _modo_cardiaco(self):
        self._log("❤️ Modo CARDIACO ACTIVADO | Gestión dinámica de operaciones manuales")
        estrategy = AUTO_SL_TP.SIN_ESTRATEGIA
        bot = BingX(estrategy, self.datos)
        en_gestion = {}

        def gestionar_posicion(symbol, side):
            self._log(f"🛠️ Iniciando gestión de {symbol} [{side}]")
            try:
                bot_local = BingX(AUTO_SL_TP, self.datos)
                bot_local.positionside = side
                bot_local.symbol = symbol
                bot_local.master_monitor()
            except Exception as e:
                self._log(f"❌ Class BotRunner - Error en posición {symbol} [{side}]: {e}")
                #traceback.print_exc()
            finally:
                self._log(f"✅ Gestión finalizada para {symbol} [{side}]")
                en_gestion.pop((symbol, side), None)

        while True:
            try:
                posiciones = bot.get_all_open_positions()  # lista de dicts: symbol, positionside, precio, monto

                for pos in posiciones:
                    symbol = pos["symbol"]
                    side = pos["positionside"].upper()
                    clave = (symbol, side)

                    if clave not in en_gestion:
                        self._log(f"📡 Detectada nueva posición: {symbol} [{side}]")
                        t = Thread(target=gestionar_posicion, args=(symbol, side))
                        t.start()
                        en_gestion[clave] = t

                time.sleep(3)

            except Exception as e:
                self._log(f"❌ Class BotRunner - Error en monitor de CARDIACO: {e}")
                #traceback.print_exc()
                time.sleep(5)

    def _existe_posicion_abierta(self, bot, direccion):
        posiciones = bot.get_open_position()
        pos = posiciones.get(direccion.upper(), {})
        return bool(pos) and float(pos.get("positionAmt", 0)) != 0

    def _log(self, mensaje):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {mensaje}"
        print(log_line)
        try:
            with open("azc_bot.log", "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception as e:
            print(f"⚠️ Class BotRunner - Error escribiendo en log: {e}")
            #traceback.print_exc()


# Punto de entrada
if __name__ == "__main__":
    runner = BotRunner(Datos, Estrategia)
    runner.iniciar()
