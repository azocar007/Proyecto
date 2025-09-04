""" MODULO PARA IMPORTAR FUNCIONES DE BACKTESTING """
# ===== IMPORTS ===== #
#import pprint
import os
import time
import datetime as dt
import pandas as pd
import time
from exchanges.BingX import BingX
from run_class import Datos
from strategys import AUTO_SL_TP


""" === Función para obtener y guardar velas en CSV desde un exchange === """

def get_velas_df(exchange: str, symbol: str, temporalidad: list, cantidad: list):

    def conv_pdataframe_int(velas: list, temp: str):
        df = pd.DataFrame(velas)
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'time': 'Time'
        }, inplace=True)

        df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
        df['Time'] = pd.to_datetime(df['Time'], unit='ms')
        df.set_index('Time', inplace=True)
        df.sort_index(inplace=True)
        df["Avg_price"] = df[["Close", "Open", "High", "Low"]].mean(axis=1)

        base_dir = "Proyecto-PYTHON-main/data_velas"
        ruta = os.path.join(base_dir, exchange, symbol, temp)
        os.makedirs(ruta, exist_ok=True)

        fecha = dt.datetime.now().strftime('%Y-%m-%d')
        nombre_archivo = f"{exchange}_{symbol}_{temp}_{fecha}_velas.csv"
        archivo_completo = os.path.join(ruta, nombre_archivo)

        if os.path.exists(archivo_completo):
            df_existente = pd.read_csv(archivo_completo, parse_dates=['Time'], index_col='Time')
            total_antes = len(df_existente)
            df_total = pd.concat([df_existente, df])
            df_total = df_total[~df_total.index.duplicated(keep='last')]
            df_total.sort_index(inplace=True)
            total_despues = len(df_total)
            nuevas_agregadas = total_despues - total_antes
            df_total.to_csv(archivo_completo)
            print(f"Archivo actualizado: {archivo_completo}")
            print(f"→ Velas nuevas agregadas: {nuevas_agregadas}")
            print(f"→ Total de velas en archivo: {total_despues}")
        else:
            df.to_csv(archivo_completo)
            print(f"Archivo nuevo guardado: {archivo_completo}")
            print(f"→ Velas guardadas: {len(df)}\n")

    # Validación de entradas
    if len(temporalidad) != len(cantidad):
        print("Error: las listas 'temporalidad' y 'cantidad' deben tener la misma longitud.")
        return

    # Lógica por exchange
    if exchange == "BingX":
        bingx = BingX(AUTO_SL_TP, Datos)  # 'entradas' debe estar definida
        symbol = str(symbol).upper() + "-USDT"
        for temp, cant in zip(temporalidad, cantidad):
            velas = bingx.get_last_candles(symbol, temp, cant)
            velas.pop(0)  # Remueve encabezado
            if not velas or not isinstance(velas, list):
                print(f"No se recibieron velas para {temp}")
                continue
            conv_pdataframe_int(velas, temp)
            time.sleep(1)

    elif exchange == "Binance":
        pass
    elif exchange == "OKX":
        pass
    elif exchange == "Bybit":
        pass
    elif exchange == "Phemex":
        pass

def exportar_trades(bt, stats, nombre_base="trades_completo", carpeta="Proyecto-PYTHON-main/resultados"):

    try:
        # Crear carpeta si no existe
        os.makedirs(carpeta, exist_ok=True)

        # Fecha y hora para identificar cada ejecución
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # Construir nombre final del archivo con timestamp
        nombre_archivo = f"{nombre_base}_{timestamp}.csv"
        ruta_final = os.path.join(carpeta, nombre_archivo)

        # Obtener los DataFrames
        df_trades = stats['_trades'].copy()
        df_debug = pd.DataFrame(stats._strategy.logs_trades)

        # Fusionar si hay índices comunes
        if 'EntryBar' in df_trades.columns and 'bar_index' in df_debug.columns:
            df_merged = pd.merge(df_trades, df_debug, left_on='EntryBar', right_on='bar_index', how='left')
        else:
            df_merged = pd.concat([df_trades, df_debug], axis=1)

        # Exportar
        df_merged.to_csv(ruta_final, index=False)
        print(f"\n[OK] Exportado como: {ruta_final} ({len(df_merged)} trades)\n")
    except Exception as e:
        print(f"\n[ERROR] No se pudo exportar: {e}\n")


if __name__ == "__main__":

    """ Datos para la Obtención de velas """

    exchange = "BingX" # BingX - Binance - OKX - Bybit - Phemex
    symbol = "XRP"
    temporalidad = ["1m", "3m", "5m"]
    cantidad = [1440, 680, 580]
    get_velas_df(exchange, symbol, temporalidad, cantidad)

    exchange = "BingX"
    symbol = "near"
    temporalidad = ["1m", "3m", "5m"]
    cantidad = [1440, 680, 580]
    #get_velas_df(exchange, symbol, temporalidad, cantidad)