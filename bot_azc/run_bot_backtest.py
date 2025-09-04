""" MODULO PARA EJECUTAR BACKTESTING DE ESTRATEGIAS DE TRADING """
# ===== IMPORTS =====
#import pprint
import pandas as pd
from extraer_velas import exportar_trades
from backtesting_custom import Backtest

""" Importar las estrategias de trading """
#from backtest.CRUCE_BB import LONG, SHORT
from backtest.SMA_MACD_BB import LONG, SHORT
#from backtest.TOQUE_BB_RSI import LONG, SHORT


""" ===== Ejecución del BACKTESTING ===== """

# Datos de velas
data = pd.read_csv("Proyecto-PYTHON-main/data_velas/BingX/ADA-USDT/1m/BingX_ADA-USDT_1m_2025-07-26_velas.csv",
                    parse_dates=['Time'], index_col='Time')

""" Ejecución del backtest LONG """
#"""
bt = Backtest(data, LONG, cash=1000)
stats = bt.run()
print(f"\n\n======== Estrategia: {LONG.__module__.split('.')[-1]} - {LONG.__name__} ========\n<<< Datos SMA: {LONG.serie_sma} - Datos BB: {LONG.serie_bb} >>>\n")
print(stats)

# Obtener los datos de trades
data_trades = stats['_trades']
data_trades = data_trades.iloc[:, :12] # elimina las columnas innecesarias
print(data_trades)

# Función para exportar los trades a un archivo CSV
#exportar_trades(bt, stats, nombre_base="NEAR_LONG_1m", carpeta="resultados")
#bt.plot()(filename='grafico_long.html')

# Aplicando Optimize
"""
bt.optimize(
            ratio=[1, 1.5, 2, 2.5, 3],
            dist_min=[0, 0.25, 0.5, 0.75, 1],
            sep_min=[0, 25, 50, 75, 100]
            )

"""

""" Ejecución del backtest SHORT """
#"""
bt = Backtest(data, SHORT, cash=1000)
print(f"\n\n======== Estrategia: {SHORT.__module__.split('.')[-1]} - {SHORT.__name__} ========\n<<< Datos SMA: {SHORT.serie_sma} - Datos BB: {SHORT.serie_bb} >>>\n")
stats = bt.run()
print(stats)

# Obtener los datos de trades
data_trades = stats['_trades']
data_trades = data_trades.iloc[:, :12] # elimina las columnas innecesarias
print(data_trades)

# Función para exportar los trades a un archivo CSV
#exportar_trades(bt, stats, nombre_base="NEAR_LONG_1m", carpeta="resultados")
#bt.plot()(filename='grafico_long.html')

# Aplicando Optimize
"""
bt.optimize(
            ratio=[1, 1.5, 2, 2.5, 3],
            dist_min=[0, 0.25, 0.5, 0.75, 1],
            sep_min=[0, 25, 50, 75, 100]
            )

#"""