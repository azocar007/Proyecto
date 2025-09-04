""" MODULO ESTRATEGIA CRUCE_BB """
# ===== IMPORTS =====
import pandas as pd
import ta
import ta.trend
import ta.volatility
import tecnical_analisys_propio as tap
import Modos_de_gestion_operativa as mgo
from backtesting_custom import Strategy
#from backtesting_custom.lib import crossover


""" CLASES DE ESTRATEGIA PARA BACKTESTING viejo con libreria ta"""

class LONG(Strategy):

    # Flags de lógica
    condicion1 = False
    condicion2 = False

    # Logs para debug de trades
    logs_trades = []

    """ Parámetros de los indicadores """
    # Serie de datos
    serie_sma = "Close" # avg_price - Close
    serie_bb = "Close" # ext_bb - avg_price - Close
    
    # Media movil
    sma_period = 40                # 0 - 200 Periodo de la media movil simple
    # MACD
    macd_fast = 10                  # 0 - 12 Periodo rápido del MACD
    macd_slow = 20                  # 0 - 26 Periodo lento del MACD
    macd_signal = 10                # 0 - 10 Periodo de la señal del MACD
    # Bandas de Bollinger Menor
    bb_period_menor = 20            # 0 - 100 Periodo de las bandas de Bollinger
    bb_std_dev_menor = 2            # 0 - 2 Desviación estándar para las bandas de Bollinger
    # Bandas de Bollinger Mayor
    bb_period_mayor = 40            # 0 - 100 Periodo de las bandas de Bollinger mayor
    bb_std_dev_mayor = 2            # 0 - 2 Desviación estándar para las bandas de Bollinger Mayor

    # Parámetros de gestión de riesgo
    pip_moneda = 1
    pip_precio = 0.0001
    dist_min = 0.25                  # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
    sep_min = 25                    # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
    ratio = 2                       # Take profit = riesgo * 2 ej: beneficio/riesgo 2:1
    riesgo_pct = 0.001              # % del capital por operación, 0.001 EQUIVALE A 1 USD PARA UN CAPITAL DE 1000 USD

    def init(self):
        """Indicadores de la estrategia"""
        # Media movil
        # Serie de datos
        if self.serie_sma == "Close":
            serie_datos = self.data.Close
        else:
            serie_datos = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4

        self.sma = self.I(lambda x: ta.trend.SMAIndicator(pd.Series(x), window = self.sma_period).sma_indicator().values, serie_datos)

        # MACD
        self.macd, self.macd_signal = self.I(
            lambda x: (
                ta.trend.MACD(pd.Series(x), window_slow = self.macd_slow, window_fast = self.macd_fast, window_sign = self.macd_signal).macd().values,
                ta.trend.MACD(pd.Series(x), window_slow = self.macd_slow, window_fast = self.macd_fast, window_sign = self.macd_signal).macd_signal().values
            ), serie_datos)

        # definiendo series Bandas de Bollinger
        # Serie de datos
        if self.serie_bb == "Close":
            serie_bb_menor = self.data.Close
            serie_bb_mayor = self.data.Close
        elif self.serie_bb == "avg_price":
            serie_bb_menor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
            serie_bb_mayor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
        else: # self.serie_bb == "ext_bb"
            serie_bb_menor = self.data.High
            serie_bb_mayor = self.data.High

        # Bandas de Bollinger Menor
        self.bb_hband_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_hband().values,
            serie_bb_menor)

        self.bb_middle_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_mavg().values,
            serie_bb_menor)

        self.bb_lband_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_lband().values,
            serie_bb_menor)

        # Bandas de Bollinger Mayor
        self.bb_hband_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_hband().values,
            serie_bb_mayor)

        self.bb_middle_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_mavg().values,
            serie_bb_mayor)

        self.bb_lband_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_lband().values,
            serie_bb_mayor)

        # contador de señal MACD activa
        self.macd_crossed = 0
        self.logs_trades = []

    def next(self):

        # Valida que existan mas de 20 velas para evitar errores
        if len(self.data) < self.bb_period_mayor: #self.sma_period:
            return

        # Valida que no existan posiciones abiertas
        if self.position:
            return # No abrir nueva si ya hay una activa

        # Valida que la distancia entre la banda de bollinger mayor superior y la media mayor sea superior a la dist_min
        dist_val = mgo.dist_valida_sl(self.bb_hband_mayor[-1], self.sma[-1], self.dist_min, self.sep_min, self.ratio, 'long')
        if dist_val["dist_valida"] and (self.data.Close[-1] > self.sma[-1]):
            self.condicion1 = True
        else:
            return

        # Valida cruce de la banda de bollinger menor superior con la banda de bollinger mayor superior
        if self.condicion1 and tap.crossover1(self.bb_hband_menor, self.bb_hband_mayor):
        #if self.condicion1 and crossover(self.bb_hband_menor, self.bb_hband_mayor):
            self.condicion2 = True
        else:
            self.condicion1 = False
            return
        
        if self.condicion1 and self.condicion2:
            # Calcular SL, TP, tamaño, prcio de entrada
            entry_price = self.data.Close[-1]
            stop_take = mgo.dist_valida_sl(entry_price, self.sma[-1], self.dist_min, self.sep_min, self.ratio, 'long')
            if stop_take["stop_loss"] is not None:
                stop_price = mgo.redondeo(stop_take["stop_loss"], self.pip_precio)
                take_profit = mgo.redondeo(stop_take["take_profit"], self.pip_precio)
                cant_mon = mgo.redondeo(self.equity * self.riesgo_pct / abs(entry_price - stop_price), self.pip_moneda)

                self.buy(
                        size=cant_mon,
                        sl=stop_price,
                        tp=take_profit,
                        )
                #"""
                self.logs_trades.append({
                            'bar_index': len(self.data.Close),
                            'entry_price': entry_price,
                            'sma': self.sma[-1],
                            'macd': self.macd[-1],
                            'macd_signal': self.macd_signal[-1],
                            'bb_upper_menor': self.bb_hband_menor[-1],
                            'bb_upper_mayor': self.bb_hband_mayor[-1],
                            'stop_loss': stop_price,
                            'take_profit': take_profit,
                            'size': cant_mon
                            })
                #"""
            else:
                self.condicion1 = False
                self.condicion2 = False

    def on_trade_exit(self, trade):
        self.condicion1 = False
        self.condicion2 = False


class SHORT(Strategy):

    # Flags de lógica
    condicion1 = False
    condicion2 = False

    # Logs para debug de trades
    logs_trades = []

    """ Parámetros de los indicadores """
    # Serie de datos
    serie_sma = "Close" # avg_price - Close
    serie_bb = "Close" # ext_bb - avg_price - Close

    # Media movil
    sma_period = 100                # 0 - 200 Periodo de la media movil simple
    # MACD
    macd_fast = 10                  # 0 - 12 Periodo rápido del MACD
    macd_slow = 20                  # 0 - 26 Periodo lento del MACD
    macd_signal = 10                # 0 - 10 Periodo de la señal del MACD
    # Bandas de Bollinger Menor
    bb_period_menor = 20            # 0 - 100 Periodo de las bandas de Bollinger
    bb_std_dev_menor = 2            # 0 - 2 Desviación estándar para las bandas de Bollinger
    # Bandas de Bollinger Mayor
    bb_period_mayor = 40            # 0 - 100 Periodo de las bandas de Bollinger mayor
    bb_std_dev_mayor = 2            # 0 - 2 Desviación estándar para las bandas de Bollinger Mayor

    # Parámetros de gestión de riesgo
    pip_moneda = 1
    pip_precio = 0.0001
    dist_min = 0.25                  # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
    sep_min = 25                    # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
    ratio = 2                       # Take profit = riesgo * 2 ej: beneficio/riesgo 2:1
    riesgo_pct = 0.001              # % del capital por operación, 0.001 EQUIVALE A 1 USD PARA UN CAPITAL DE 1000 USD

    def init(self):
        """Indicadores de la estrategia"""
        # Media movil
        # Serie de datos
        if self.serie_sma == "Close":
            serie_datos = self.data.Close
        else:
            serie_datos = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4

        self.sma = self.I(lambda x: ta.trend.SMAIndicator(pd.Series(x), window = self.sma_period).sma_indicator().values, serie_datos)

        # MACD
        self.macd, self.macd_signal = self.I(
            lambda x: (
                ta.trend.MACD(pd.Series(x), window_slow = self.macd_slow, window_fast = self.macd_fast, window_sign = self.macd_signal).macd().values,
                ta.trend.MACD(pd.Series(x), window_slow = self.macd_slow, window_fast = self.macd_fast, window_sign = self.macd_signal).macd_signal().values
            ), serie_datos)

        # definiendo series Bandas de Bollinger
        # Serie de datos
        if self.serie_bb == "Close":
            serie_bb_menor = self.data.Close
            serie_bb_mayor = self.data.Close
        elif self.serie_bb == "avg_price":
            serie_bb_menor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
            serie_bb_mayor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
        else: # self.serie_bb == "ext_bb"
            serie_bb_menor = self.data.Low
            serie_bb_mayor = self.data.Low

        # Bandas de Bollinger Menor
        self.bb_hband_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_hband().values,
            serie_bb_menor)

        self.bb_middle_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_mavg().values,
            serie_bb_menor)

        self.bb_lband_menor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_menor, window_dev = self.bb_std_dev_menor).bollinger_lband().values,
            serie_bb_menor)

        # Bandas de Bollinger Mayor
        self.bb_hband_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_hband().values,
            serie_bb_mayor)

        self.bb_middle_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_mavg().values,
            serie_bb_mayor)

        self.bb_lband_mayor = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period_mayor, window_dev = self.bb_std_dev_mayor).bollinger_lband().values,
            serie_bb_mayor)

        # contador de señal MACD activa
        self.macd_crossed = 0
        self.logs_trades = []

    def next(self):

        # Valida que existan mas de 20 velas para evitar errores
        if len(self.data) < self.bb_period_mayor: #self.sma_period:
            return

        # Valida que no existan posiciones abiertas
        if self.position:
            return # No abrir nueva si ya hay una activa

        # Valida que la distancia entre la banda de bollinger mayor superior y la media mayor sea superior a la dist_min
        dist_val = mgo.dist_valida_sl(self.bb_lband_mayor[-1], self.bb_middle_mayor[-1], self.dist_min, self.sep_min, self.ratio, 'short')
        if dist_val["dist_valida"] and (self.data.Close[-1] < self.bb_middle_mayor[-1]):
            self.condicion1 = True
        else:
            return

        # Valida cruce de la banda de bollinger menor superior con la banda de bollinger mayor superior
        if self.condicion1 and tap.crossunder1(self.bb_lband_menor, self.bb_lband_mayor):
        #if self.condicion1 and crossover(self.bb_hband_menor, self.bb_hband_mayor):
            self.condicion2 = True
        else:
            self.condicion1 = False
            return
        
        if self.condicion1 and self.condicion2:
            # Calcular SL, TP, tamaño, prcio de entrada
            entry_price = self.data.Close[-1]
            stop_take = mgo.dist_valida_sl(entry_price, self.bb_middle_mayor[-1], self.dist_min, self.sep_min, self.ratio, 'short')
            if stop_take["stop_loss"] is not None:
                stop_price = mgo.redondeo(stop_take["stop_loss"], self.pip_precio)
                take_profit = mgo.redondeo(stop_take["take_profit"], self.pip_precio)
                cant_mon = mgo.redondeo(self.equity * self.riesgo_pct / abs(entry_price - stop_price), self.pip_moneda)

                self.sell(
                        size=cant_mon,
                        sl=stop_price,
                        tp=take_profit,
                        )
                #"""
                self.logs_trades.append({
                            'bar_index': len(self.data.Close),
                            'entry_price': entry_price,
                            'sma': self.sma[-1],
                            'macd': self.macd[-1],
                            'macd_signal': self.macd_signal[-1],
                            'bb_lower_menor': self.bb_lband_menor[-1],
                            'bb_lower_mayor': self.bb_lband_mayor[-1],
                            'stop_loss': stop_price,
                            'take_profit': take_profit,
                            'size': cant_mon
                            })
                #"""
            else:
                self.condicion1 = False
                self.condicion2 = False

    def on_trade_exit(self, trade):
        self.condicion1 = False
        self.condicion2 = False
