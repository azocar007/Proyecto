""" Archivo para correr atributos del las clases de los exchanges """

from exchanges.BINGX import BingX
from RUN_CLASS import Datos
from strategys import SMA_MACD_BB, SMA_BB, CRUCE_BB, AUTO_SL_TP
import Modos_de_gestion_operativa as mgo


""" Datos de configuración del bot de trading. """

Datos1 = {
        # Datos para operar en el exchange
        "exchange": "BINGX",                                # Nombre del exchange a utilizar (ejemplo: "BINGX", "BINANCE", "BYBIT", "PHEMEX")
        "symbol": "sui",                                    # Símbolo del par a operar (ejemplo: "doge", "btc", "eth")
        "positionside": "SHORT",                            # Dirección inicial LONG o SHORT
        "modo_operacion": "CARDIACO",                       # "UNICO" - "ALTERNADO" - "SIMULTANEO" - "CARDIACO"
        "type": "LIMIT",                                    # "LIMIT" - "MARKET" - "BBO"
        "temporalidad": "5m",                               # Temporalidad de las velas a utilizar (ejemplo: "1m", "5m", "15m", "1h", "4h", "1d")
        "cant_velas": 200,                                  # Cantidad de velas a solicitar al exchange para el dataframe dinamico de la estrategia
        "segundos": 10,                                     # Segundos entre chequeos de posición en monitor_open_positions()
        # Datos para la gestión STOP LOSS
        "modo_gestion": "RATIO BENEFICIO/PERDIDA",          # "RECOMPRAS" - "RATIO BENEFICIO/PERDIDA" - "SNOW BALL"
        "monto_sl": 1.0,                                    # Monto en USDT para el Stop Loss
        "precio_entrada": 0,                                # Precio de entrada para la orden LIMIT en caso de ser necesario
        "gestion_vol": "MARTINGALA",                        # "% DE REENTRADAS" - "MARTINGALA" - "AGRESIVO"
        "cant_ree": 6,                                      # Cantidad de reentradas
        "dist_ree": 2,                                      # Distancia en porcentaje entre reentradas (ejemplo: 2 = 2%)
        "porcentaje_vol_ree": 0,                            # Porcentaje de volumen para reentradas (ejemplo: 50% del volumen anterior)    
        "monedas": 40,                                      # Cantidad de monedas para la 1ra operación
        "usdt": 0,                                          # Cantidad de USDT para la 1ra operación (si se usa "monedas" se ignora este valor)
        # Datos para la gestion de TAKE PROFIT
        "gestion_take_profit": "RATIO BENEFICIO/PERDIDA",   # "RATIO BENEFICIO/PERDIDA" - "% TAKE PROFIT" - "LCD" (Carga y Descarga todavia no esta definido)
        "ratio": 2                                          # Ratio de beneficio/perdida para el Stop Loss y Take Profit
        }

# Estrategia a utilizar en el bot de trading.
Estrategia = CRUCE_BB

# Inicializa el bot de trading con la estrategia y los datos.
Bot = BingX(Estrategia, Datos)
MonitorMemoria = mgo.Monitor_Memoria()

def main():

    """ Función principal para iniciar el bot de trading. """
    try:
        # Inicia monitor de memoria RAM
        #MonitorMemoria.iniciar()

        # Inicia el bot de trading
        #Bot.monitor_open_positions()
        #Bot.get_all_open_positions()

        """ Solicitar información de la cuenta y monedas """
        #print("Balance de la cuenta:", bingx.get_balance()["availableMargin"]) # Margen disponible para operar
        #pprint.pprint({"Activo": symbol, "Información" : bingx.inf_moneda(symbol)})
        #print("Pip del precio:", bingx.pip_precio())
        #print("Cantidad de decimales del precio:", bingx.cant_deci_precio(symbol))
        #print("Monto mínimo moneda (pip de moneda):", bingx.pip_moneda())
        #print("Monto mínimo USDT:", bingx.min_usdt(symbol))
        #bingx.max_apalancamiento(symbol)

        """ Operaciones en la cuenta """
        #bingx.get_open_position()
        velas = Bot.get_last_candles("SUI-USDT","5m", 4)
        print(velas)
        #bingx.start_websocket()
        #bingx.get_current_open_orders(type = "limit")
        #bingx.set_cancel_order(type = "LIMIT") # Cancelar ordenes LIMIT, MARKET, TRIGGER
        #bingx.set_limit_market_order() # Enviar ordenes
        #bingx.dynamic_reentradas_manager("DOGE-USDT", entradas["positionside"], entradas["modo_gestion"])
        #bingx._limit_market_order("DOGE-USDT", "LONG", 40, 0.15, "LIMIT")

    except Exception as e:
        print("\n❌ Bot detenido por:")
        print(e)

if __name__ == "__main__":
    main()
