""" ESTRUCTURA BASE PARA ESTRATEGIAS LONG - MODULAR Y REUTILIZABLE """
import pandas as pd
import Modos_de_gestion_operativa as mgo
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands

"""
Descripcion de la estrategia Media movil simple (SMA) + MACD + Bandas de Bollinger (BB):

"""

class SMA_MACD_BB:

    def __init__(self,
                df: pd.DataFrame,
                last_price: float = None,
                avg_price: float = None ,
                decimales: int = None,
                indicator: str = None,
                positionside: str = None,
                monto_sl: float = None,
                ratio: float = None
                ):
        self.df = df.copy()             # Copia del DataFrame para evitar modificaciones externas
        self.df1 = df.copy()            # Copia adicional para uso en preparación de DataFrame
        self.last_price = last_price
        self.avg_price = avg_price
        self.decimales = decimales
        self.indicator = indicator
        self.positionside = positionside
        self.monto_sl = monto_sl
        self.ratio = ratio
        self.dist_min = 0.25            # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
        self.sep_sl = 25                # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
        self.klines = 2
        self._estado = {"websocket": True}
        self._ventana = 1
        self.params = {
                        # Serie de datos
                        "serie_sma": "Close",        # avg_price - Close
                        "serie_bb": "Close",         # ext_bb - avg_price - Close
                        "ventana_max": 5,
                        # Parametros SMA
                        "sma_window": 100,
                        # Parametros para Bandas de Bollinger
                        "bb1_window": 20,
                        "bb1_dev": 2.0,
                        "bb2_window": 20,
                        "bb2_dev": 1.0,
                        # Parametros MACD
                        "macd_fast": 10,
                        "macd_slow": 20,
                        "macd_signal": 10,
                        }

    def _calcular_indicadores(self):
        """ Calcula los indicadores SMA, MACD y Bandas de Bollinger """

        # Serie datos para seleccionar del DataFrame sma - macd
        if self.params["serie_sma"] == "Close":
            valorsma = self.df['Close']
        else:
            valorsma = self.df['Avg_price']

        # Calculo de la media movil simple (SMA)
        self.df['sma'] = SMAIndicator(valorsma, window=self.params["sma_window"]).sma_indicator()

        # Calculo de MACD
        macd = MACD(
                    valorsma,
                    window_slow=self.params["macd_slow"],
                    window_fast=self.params["macd_fast"],
                    window_sign=self.params["macd_signal"]
                    )
        self.df['macd_line'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()

        # Serie de datos para seleccionar del DataFrame Bandas de bollinger
        if self.params["serie_bb"] == "Close":
            valorbbupper = self.df['Close']
            valorbblower = self.df['Close']
        elif self.params["serie_bb"] == "Avg_price":
            valorbbupper = self.df['Avg_price']
            valorbblower = self.df['Avg_price']
        else: # self.serie_bb == "ext_bb"
            valorbbupper = self.df['High']
            valorbblower = self.df['Low']

        # Calculo de Bandas de Bollinger
        bb1 = BollingerBands(valorbbupper, window=self.params["bb1_window"], window_dev=self.params["bb1_dev"])
        self.df['bb1_upper'] = bb1.bollinger_hband()
        bb1 = BollingerBands(valorbblower, window=self.params["bb1_window"], window_dev=self.params["bb1_dev"])
        self.df['bb1_lower'] = bb1.bollinger_lband()

        bb2 = BollingerBands(valorbbupper, window=self.params["bb2_window"], window_dev=self.params["bb2_dev"])
        self.df['bb2_upper'] = bb2.bollinger_hband()
        bb2 = BollingerBands(valorbblower, window=self.params["bb2_window"], window_dev=self.params["bb2_dev"])
        self.df['bb2_lower'] = bb2.bollinger_lband()
        
        # Redondear los valores a los decimales especificados
        if self.decimales is not None:
            for col in [
                        "Close",
                        "Avg_price",
                        "sma",
                        "bb1_lower",
                        "bb1_upper",
                        "bb2_lower",
                        "bb2_upper",
                        "macd_line",
                        "macd_signal"
                        ]:
                self.df[col] = self.df[col].round(self.decimales)
        # Impresión del Dataframe para ensayo
        #print(f"DataFrame sin indicadores:\n{self.df1.tail(5).to_string(index=True)}")
        # Mostrar el DataFrame con indicadores al instanciar la clase
        print(f"\n{self.indicator} ESTRATEGIA - DataFrame dinamico con indicadores calculados de las ultimas {self.klines} velas cerradas:")
        print(self.df[[
                "Time",
                "Close",
                "Avg_price",
                "sma",
                "bb1_lower",
                "bb1_upper",
                "bb2_lower",
                "bb2_upper",
                "macd_line",
                "macd_signal"
                ]].tail(self.klines).to_string(index=True))

    def condiciones_sin_websocket(self):
        """ Evaluación de condiciones sin WebSocket """

        if self._ventana >= self.params['ventana_max']:
            print("⏳ Ventana de oportunidad caducada")
            self.reiniciar_condiciones()
            return {"estrategia_valida": False}

        i = len(self.df) - 1

        if self.positionside == "LONG":
            # Validación de estructura - BB inferior > SMA
            if self.df['bb1_lower'].iloc[i] >= self.df['sma'].iloc[i]:
                self._estado['cond_1'] = True
                print(f"✅ Condicón 1: BB inferior está por encima de SMA {self.indicator} - {self.positionside}")
            # Validación de cruce MACD
            if self._estado.get('cond_1', False) and (self.df['macd_line'].iloc[i-1] <= self.df['macd_signal'].iloc[i-1] and self.df['macd_line'].iloc[i] > self.df['macd_signal'].iloc[i]):
                self._estado['cond_2'] = True
                print(f"✅✅ Condición 2: Cruce MACD alcista detectado {self.indicator} - {self.positionside}")

        elif self.positionside == "SHORT":
            # Validación de estructura - BB superior < SMA
            if self.df['bb1_upper'].iloc[i] <= self.df['sma'].iloc[i]:
                self._estado['cond_1'] = True
                print(f"✅ Condicón 1: BB superior está por debajo de SMA {self.indicator} - {self.positionside}")
            # Validación de cruce MACD
            if self._estado.get('cond_1', False) and (self.df['macd_line'].iloc[i-1] >= self.df['macd_signal'].iloc[i-1] and self.df['macd_line'].iloc[i] < self.df['macd_signal'].iloc[i]):
                self._estado['cond_2'] = True
                print(f"✅✅ Condición 2: Cruce MACD bajista detectado {self.indicator} - {self.positionside}")

    def activar_websocket(self):
        """ Verifica si se requiere WebSocket para la estrategia """
        return self._estado.get('cond_1', False) and self._estado.get('cond_2', False) and self._estado.get('websocket', False)

    def evaluar_entrada(self, df_temp: pd.DataFrame):

        if self._ventana >= self.params['ventana_max']:
            print("⏳ Ventana de oportunidad caducada")
            self.reiniciar_condiciones()
            return {"estrategia_valida": False}

        print(f"\n{self.indicator} ESTRATEGIA - DataFrame preparado para evaluación de entrada:\n")
        #print(df_temp.tail(self.klines).to_string(index=True))
        print(df_temp.tail(self.klines))

        # Selección entre last_price y avg_price
        if self.params["serie_bb"] == "Avg_price":
            df_temp.at[len(df_temp) - 1, 'Avg_price'] = self.avg_price
            close_temp = df_temp['Avg_price']
            price = self.avg_price

        else: # self.params["serie_bb"] == "Close" or "ext_bb"
            df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
            close_temp = df_temp['Close']
            price = self.last_price

        # Recalculo de Bandas de Bollinger con el último precio
        bb2_recalc = BollingerBands(close_temp, window=self.params["bb2_window"], window_dev=self.params["bb2_dev"])
        bb_upper = bb2_recalc.bollinger_hband().iloc[-1]
        bb_lower = bb2_recalc.bollinger_lband().iloc[-1]

        if self.positionside == "LONG":
            # Condición de entrada para LONG
            if price > bb_upper:
                min_price = self.df['Low'].iloc[-self.params["bb2_window"]:].min()
                dist_valid = mgo.dist_valida_sl(price, min_price, self.dist_min, self.sep_sl, self.monto_sl, self.ratio, 'long')
                stop_loss = dist_valid.get("stop_loss", None)
                cant_mon = dist_valid.get("cant_mon", None)
                if stop_loss:
                    print("✅✅✅ Condición 3 cumplida: Ruptura y SL válido")
                    #return {"estrategia_valida": False}
                    #"""
                    return {
                            "precio_entrada": price,
                            "stop_loss": stop_loss,
                            "ref_price":min_price,
                            "cant_mon": cant_mon,
                            "estrategia_valida": True
                            }
                    #"""
            return {"estrategia_valida": False}

        elif self.positionside == "SHORT":
            # Condición de entrada para SHORT
            if price < bb_lower:
                max_price = self.df['High'].iloc[-self.params["bb2_window"]:].max()
                dist_valid = mgo.dist_valida_sl(price, max_price, self.dist_min, self.sep_sl, self.monto_sl, self.ratio, 'short')
                stop_loss = dist_valid.get("stop_loss", None)
                cant_mon = dist_valid.get("cant_mon", None)
                if stop_loss:
                    print("✅✅✅ Condición 3 cumplida: Ruptura y SL válido")
                    #return {"estrategia_valida": False}
                    #"""
                    return {
                            "precio_entrada": price,
                            "stop_loss": stop_loss,
                            "ref_price":max_price,
                            "cant_mon": cant_mon,
                            "estrategia_valida": True
                            }
                    #"""
            return {"estrategia_valida": False}

    def reiniciar_condiciones(self):
        # Reinicia las condiciones del estado
        self._estado = {"websocket": True}
        self._ventana = 1
        print(f"🔄 Condiciones reiniciadas {self.indicator} - {self.positionside}")

    def incrementar_ventana(self):
        # Incrementa la ventana de oportunidad
        self._ventana += 1
        print(f"🔼 Ventana incrementada a {self._ventana}, {self.indicator} - {self.positionside}")

    def requiere_websocket(self):
        return self._estado.get('websocket', False)
