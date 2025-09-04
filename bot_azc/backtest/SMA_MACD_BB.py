""" MODULO ESTRATEGIA SMA + MACD + BB """
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
    condicion3 = False
    ventana = 0

    # Logs para debug de trades
    logs_trades = []

    """ Parámetros de los indicadores """
    # Serie de datos
    serie_sma = "Close" # avg_price - Close
    serie_bb = "Close" # ext_bb - avg_price - Close

    # SMA
    sma_period = 100        # 0 - 200 Periodo de la media movil simple

    # MACD
    macd_fast = 10          # 0 - 12 Periodo rápido del MACD
    macd_slow = 20          # 0 - 26 Periodo lento del MACD
    macd_signal = 10        # 0 - 10 Periodo de la señal del MACD

    # Bandas de Bollinger menor
    bb_period = 20          # 0 - 100 Periodo de las bandas de Bollinger menor
    bb_std_dev = 1          # 0 - 2 Desviación estándar para las bandas de Bollinger menor
    # Bandas de Bollinger Mayor
    bb_period_mayor = 20   # 0 - 100 Periodo de las bandas de Bollinger mayor
    bb_std_dev_mayor = 2    # 0 - 2 Desviación estándar para las bandas de Bollinger Mayor

    # Parámetros de gestión de riesgo
    pip_moneda = 1
    pip_precio = 0.00001
    dist_min = 0.25         # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
    sep_min = 25           # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
    ratio = 2              # Take profit = riesgo * 2 ej: beneficio/riesgo 2:1
    riesgo_pct = 0.001      # % del capital por operación, 0.001 EQUIVALE A 1 USD PARA UN CAPITAL DE 1000 USD

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

        # Definiendo series Bandas de Bollinger
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

        # Bandas de Bollinger menor
        self.bb_hband = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_hband().values,
            serie_bb_menor)

        self.bb_middle = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_mavg().values,
            serie_bb_menor)

        self.bb_lband = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_lband().values,
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

        self.logs_trades = []

    def next(self):
        # Esperar hasta la vela correspondiente al inicio de la SMA
        if len(self.data.Close) < self.sma_period:
            return

        # Valida que no existan posiciones abiertas
        if self.position:
            return  # No abrir nueva si ya hay una activa

        """ Paso 1: Valida que el precio actual NO esté dentro de las bandas de Bollinger mayor """
        if self.bb_lband_mayor[-1] > self.sma[-1]:
            self.condicion1 = True
        else:
            return

        """ Paso 2: Cruce MACD, Activar señal MACD si corresponde """
        if self.condicion1 and tap.crossover1(self.macd, self.macd_signal):
            self.condicion2 = True
        else:
            return

        """ Paso 3: Confirmar toque de la banda """
        if self.condicion1 and self.condicion2 and (self.ventana <= self.bb_period):
            if self.data.High[-1] >= self.bb_hband[-1]:
                min_price = min(self.data.Low[-self.bb_period:])
                # Serie de datos
                if self.serie_bb == "Close":
                    serie_bb_menor = self.data.Close
                elif self.serie_bb == "avg_price":
                    serie_bb_menor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
                else: # self.serie_bb == "ext_bb"
                    serie_bb_menor = self.data.High
                precios_hist = pd.Series(serie_bb_menor[-(self.bb_period - 1):].tolist())
                precio = self.data.Low[-1]
                tope = self.data.High[-1]
                entry_price = None

                # Bucle de fuerza bruta para conseguir el precio igual o inmediatamente superior al de la banda de bollinger.
                while precio <= tope:

                    # Calcular banda de Bollinger superior para el precio iterado
                    serie = pd.concat([precios_hist, pd.Series([precio])], ignore_index=True)
                    bb = ta.volatility.BollingerBands(
                        serie,
                        window = self.bb_period,
                        window_dev = self.bb_std_dev
                        )
                    bb_val = bb.bollinger_hband().iloc[-1]

                    # Comprobación del precio iterado para cerra el bucle
                    if bb_val >= precio:
                        entry_price = mgo.redondeo(precio, self.pip_precio)
                        break

                    # Si no se cumple, incrementar el precio iterado
                    precio += self.pip_precio

                if entry_price is not None:
                    # Validar estructura (distancia al mínimo)
                    dist_val = mgo.dist_valida_sl(entry_price, min_price, self.dist_min, self.sep_min, self.ratio, 'long')
                    if dist_val["dist_valida"]:
                        self.condicion3 = True
                else:
                    self.ventana += 1
                    return  # No se encontró cruce válido

                if self.condicion1 and self.condicion2 and self.condicion3:
                    # Calcular SL, TP, tamaño
                    stop_take = mgo.dist_valida_sl(entry_price, min_price, self.dist_min, self.sep_min, self.ratio, 'long')
                    if stop_take["stop_loss"] is not None:
                        stop_price = mgo.redondeo(stop_take["stop_loss"], self.pip_precio)
                        take_profit = mgo.redondeo(stop_take["take_profit"], self.pip_precio)
                        cant_mon = mgo.redondeo(self.equity * self.riesgo_pct / abs(entry_price - stop_price), self.pip_moneda)

                        self.buy(
                                size=cant_mon,
                                sl=stop_price,
                                tp=take_profit,
                                market=entry_price
                                )

                        self.logs_trades.append({
                                                'bar_index': len(self.data.Close),
                                                'entry_price': entry_price,
                                                'sma': self.sma[-1],
                                                'macd': self.macd[-1],
                                                'macd_signal': self.macd_signal[-1],
                                                'bb_upper': self.bb_hband[-1],
                                                'bb_upper_mayor': self.bb_hband_mayor[-1],
                                                'min_price': min_price,
                                                'stop': stop_price,
                                                'tp': take_profit,
                                                'size': cant_mon
                                                })

        elif self.ventana >= self.bb_period:
            self.condicion1 = False
            self.condicion2 = False
            self.condicion3 = False
            self.ventana = 0

    def on_trade_exit(self, trade):
        self.condicion1 = False
        self.condicion2 = False
        self.condicion3 = False
        self.ventana = 0


class SHORT(Strategy):

    # Flags de lógica
    condicion1 = False
    condicion2 = False
    condicion3 = False
    ventana = 0

    # Logs para debug de trades
    logs_trades = []

    """ Parámetros de los indicadores """
    # Serie de datos
    serie_sma = "Close" # avg_price - Close
    serie_bb = "Close" # ext_bb - avg_price - Close

    # SMA
    sma_period = 100        # 0 - 200 Periodo de la media movil simple

    # MACD
    macd_fast = 10          # 0 - 12 Periodo rápido del MACD
    macd_slow = 20          # 0 - 26 Periodo lento del MACD
    macd_signal = 10        # 0 - 10 Periodo de la señal del MACD

    # Bandas de Bollinger menor
    bb_period = 20          # 0 - 100 Periodo de las bandas de Bollinger menor
    bb_std_dev = 1          # 0 - 2 Desviación estándar para las bandas de Bollinger menor
    # Bandas de Bollinger Mayor
    bb_period_mayor = 20   # 0 - 100 Periodo de las bandas de Bollinger mayor
    bb_std_dev_mayor = 2    # 0 - 2 Desviación estándar para las bandas de Bollinger Mayor

    # Parámetros de gestión de riesgo
    pip_moneda = 1
    pip_precio = 0.00001
    dist_min = 0.25         # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
    sep_min = 25           # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
    ratio = 2              # Take profit = riesgo * 2 ej: beneficio/riesgo 2:1
    riesgo_pct = 0.001      # % del capital por operación, 0.001 EQUIVALE A 1 USD PARA UN CAPITAL DE 1000 USD

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

        # Definiendo series Bandas de Bollinger
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

        # Bandas de Bollinger menor
        self.bb_hband = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_hband().values,
            serie_bb_menor)

        self.bb_middle = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_mavg().values,
            serie_bb_menor)

        self.bb_lband = self.I(
            lambda x: ta.volatility.BollingerBands(pd.Series(x), window = self.bb_period, window_dev = self.bb_std_dev).bollinger_lband().values,
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

        self.logs_trades = []

    def next(self):
        # Esperar hasta la vela correspondiente al inicio de la SMA
        if len(self.data.Close) < self.sma_period:
            return

        # Valida que no existan posiciones abiertas
        if self.position:
            return  # No abrir nueva si ya hay una activa

        """ Paso 1: Valida que el precio actual NO esté dentro de las bandas de Bollinger mayor """
        if self.bb_hband_mayor[-1] < self.sma[-1]:
            self.condicion1 = True
        else:
            return

        """ Paso 2: Cruce MACD, Activar señal MACD si corresponde """
        if self.condicion1 and tap.crossunder1(self.macd, self.macd_signal):
            self.condicion2 = True
        else:
            return

        """ Paso 3: Confirmar toque de la banda """
        if self.condicion1 and self.condicion2 and (self.ventana <= self.bb_period):
            if self.data.Low[-1] >= self.bb_lband[-1]:
                max_price = max(self.data.High[-self.bb_period:])
                # Serie de datos
                if self.serie_bb == "Close":
                    serie_bb_menor = self.data.Close
                elif self.serie_bb == "avg_price":
                    serie_bb_menor = (self.data.Close + self.data.Open + self.data.High + self.data.Low) / 4
                else: # self.serie_bb == "ext_bb"
                    serie_bb_menor = self.data.High
                precios_hist = pd.Series(serie_bb_menor[-(self.bb_period - 1):].tolist())
                precio = self.data.High[-1]
                tope = self.data.Low[-1]
                entry_price = None

                # Bucle de fuerza bruta para conseguir el precio igual o inmediatamente superior al de la banda de bollinger.
                while precio <= tope:

                    # Calcular banda de Bollinger superior para el precio iterado
                    serie = pd.concat([precios_hist, pd.Series([precio])], ignore_index=True)
                    bb = ta.volatility.BollingerBands(
                        serie,
                        window = self.bb_period,
                        window_dev = self.bb_std_dev
                        )
                    bb_val = bb.bollinger_lband().iloc[-1]

                    # Comprobación del precio iterado para cerra el bucle
                    if bb_val <= precio:
                        entry_price = mgo.redondeo(precio, self.pip_precio)
                        break

                    # Si no se cumple, incrementar el precio iterado
                    precio += self.pip_precio

                if entry_price is not None:
                    # Validar estructura (distancia al mínimo)
                    dist_val = mgo.dist_valida_sl(entry_price, max_price, self.dist_min, self.sep_min, self.ratio, 'short')
                    if dist_val["dist_valida"]:
                        self.condicion3 = True
                else:
                    self.ventana += 1
                    return  # No se encontró cruce válido

                if self.condicion1 and self.condicion2 and self.condicion3:
                    # Calcular SL, TP, tamaño
                    stop_take = mgo.dist_valida_sl(entry_price, max_price, self.dist_min, self.sep_min, self.ratio, 'short')
                    if stop_take["stop_loss"] is not None:
                        stop_price = mgo.redondeo(stop_take["stop_loss"], self.pip_precio)
                        take_profit = mgo.redondeo(stop_take["take_profit"], self.pip_precio)
                        cant_mon = mgo.redondeo(self.equity * self.riesgo_pct / abs(entry_price - stop_price), self.pip_moneda)

                        self.sell(
                                size=cant_mon,
                                sl=stop_price,
                                tp=take_profit,
                                market=entry_price
                                )

                        self.logs_trades.append({
                                                'bar_index': len(self.data.Close),
                                                'entry_price': entry_price,
                                                'sma': self.sma[-1],
                                                'macd': self.macd[-1],
                                                'macd_signal': self.macd_signal[-1],
                                                'bb_lower': self.bb_lband[-1],
                                                'bb_lower_mayor': self.bb_lband_mayor[-1],
                                                'max_price': max_price,
                                                'stop': stop_price,
                                                'tp': take_profit,
                                                'size': cant_mon
                                                })

        elif self.ventana >= self.bb_period:
            self.condicion1 = False
            self.condicion2 = False
            self.condicion3 = False
            self.ventana = 0

    def on_trade_exit(self, trade):
        self.condicion1 = False
        self.condicion2 = False
        self.condicion3 = False
        self.ventana = 0
