""" ESTRATEGIA MEDIA MOVIL + MACD + BANDAS DE BOLLINGER """
import pandas as pd
import Modos_de_gestion_operativa as mgo
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands


"""=== Clase estrategia Media Movil + MACD + Bandas de Bollinger ==="""
class SMA_MACD_BB:
    def __init__(
                self,
                df: pd.DataFrame,
                last_price: float = None,
                avg_price: float = None,
                decimales: int = None,
                indicator: str = None,
                # Serie de datos
                serie_sma = "Close",        # avg_price - Close
                serie_bb = "Close",         # ext_bb - avg_price - Close
                # Parametros SMA
                sma_window: int = 100,
                # Parametros para Bandas de Bollinger
                bb1_window: int = 20,
                bb1_dev: float = 2.0,
                bb2_window: int = 20,
                bb2_dev: float = 1.0,
                # Parametros para MACD
                macd_fast: int = 10,
                macd_slow: int = 20,
                macd_signal: int = 10,
                # Parámetros para gestion de riesgo
                dist_min: float = 0.25,     # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
                sep_sl: int = 25,            # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
                ventana_max = 5
                ):
                self.last_price = last_price
                self.avg_price = avg_price
                self.decimales = decimales
                self.indicator = indicator
                self.df = df.copy().reset_index(drop=True)
                self.df2 = df.copy()
                self.serie_sma = serie_sma
                self.serie_bb = serie_bb
                self.sma_window = sma_window
                self.bb1_window = bb1_window
                self.bb1_dev = bb1_dev
                self.bb2_window = bb2_window
                self.bb2_dev = bb2_dev
                self.macd_fast = macd_fast
                self.macd_slow = macd_slow
                self.macd_signal = macd_signal
                self.dist_min = dist_min
                self.sep_sl = sep_sl
                self.ventana_max = ventana_max
                self.ventana_actual = 0 

                self._calcular_indicadores(self.df)
                self._calcular_indicadores(self.df2)

                self.condicion_1 = False
                self.condicion_2 = False
                self.condicion_3 = False
                self.ultima_vela_hash = None

                # Redondear los valores a los decimales especificados
                if self.decimales is not None:
                    for col in ["Close", "Avg_price", "sma", "bb1_lower", "bb1_upper", "bb2_lower", "bb2_upper", "macd_line", "macd_signal"]:
                        self.df[col] = self.df[col].round(self.decimales)
                        self.df2[col] = self.df2[col].round(self.decimales)

                # Mostrar el DataFrame con indicadores al inicializar la clase
                velas = 2
                print(f"\n📊 DataFrame dinamico con indicadores calculados de las ultimas {velas} cerradas {self.indicator}:")
                print(self.df2[["Close", "Avg_price", "sma", "bb1_lower", "bb1_upper", "bb2_lower", "bb2_upper", "macd_line", "macd_signal"]].tail(velas).to_string(index=True))

    def _calcular_indicadores(self, df: pd.DataFrame = None):

        # Serie datos para seleccionar del DataFrame sma - macd
        if self.serie_sma == "Close":
            valorsma = df['Close']
        else:
            valorsma = df['Avg_price']

        # Calculo de la media movil simple (SMA)
        df['sma'] = SMAIndicator(valorsma, window=self.sma_window).sma_indicator()

        # Calculo de MACD
        macd = MACD(valorsma, window_slow=self.macd_slow, window_fast=self.macd_fast, window_sign=self.macd_signal)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        # Serie de datos para seleccionar del DataFrame Bandas de bollinger
        if self.serie_bb == "Close":
            valorbb1 = df['Close']
            valorbb2 = df['Close']
        elif self.serie_bb == "Avg_price":
            valorbb1 = df['Avg_price']
            valorbb2 = df['Avg_price']
        else: # self.serie_bb == "ext_bb"
            valorbb1 = df['High']
            valorbb2 = df['Low']

        # Calculo de Bandas de Bollinger
        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_upper'] = bb1.bollinger_hband()
        bb1 = BollingerBands(valorbb2, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_lower'] = bb1.bollinger_lband()

        bb2 = BollingerBands(valorbb1, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_upper'] = bb2.bollinger_hband()
        bb2 = BollingerBands(valorbb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_lower'] = bb2.bollinger_lband()

    def evaluar_entrada_long(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price
        avg_price = self.avg_price
        new_klines, self.ultima_vela_hash = mgo.vela_nueva(df, self.ultima_vela_hash)

        # Validación de estructura - BB inferior > SMA
        if df['bb1_lower'].iloc[i] >= df['sma'].iloc[i]:
            print(f"✅ Condicón 1: BB inferior está por encima de SMA {self.indicator}")
            self.condicion_1 = True
        else:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            self.ventana_actual = 0
            return {"estrategia_valida": False}

        # Validación de cruce MACD
        if self.condicion_1 and ((df['macd_line'].iloc[i - 1] < df['macd_signal'].iloc[i - 1] and df['macd_line'].iloc[i] > df['macd_signal'].iloc[i])):
            print(f"✅✅ Condición 2: Cruce MACD detectado {self.indicator}")
            self.condicion_2 = True
            self.ventana_actual = 0
        else:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            self.ventana_actual = 0
            return {"estrategia_valida": False}

        # Ruptura de BB
        if self.condicion_2 and new_klines:
            
            self.ventana_actual += 1
            # Selección entre last_price y avg_price
            df_temp = df.copy()
            df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
            if self.serie_bb == "Avg_price":
                df_temp.at[len(df_temp) - 1, 'Avg_price'] = avg_price
                close_temp = df_temp['Avg_price']
                price = avg_price
            else: # self.serie_bb == "Close" or "ext_bb"
                df_temp.at[len(df_temp) - 1, 'Close'] = last_price
                close_temp = df_temp['Close']
                price = last_price
            bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
            bb2_upper = bb2_recalc.bollinger_hband().iloc[-1]
            # Validación de ruptura por encima de la BB superior
            if price > bb2_upper:
                min_price = df['Low'].iloc[i - self.bb2_window:i].min()
                dist_valid = mgo.dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, ratio=2, direccion='long')
                stop_loss = dist_valid.get("stop_loss", None)
                if stop_loss is None:
                    self.condicion_1 = False
                    self.condicion_2 = False
                    return {"estrategia_valida": False}
                else:
                    self.condicion_3 = True
                    stop_loss = round(stop_loss, self.decimales)
                    print(f"✅✅✅ Condición 3: Ruptura dinámica confirmada con precio actual {self.indicator}")
                    print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")

            if self.ventana_actual > self.ventana_max:
                print("❌ Ventana expirada, reiniciando condiciones.")
                self.condicion_1 = False
                self.condicion_2 = False
                self.condicion_3 = False
                self.ventana_actual = 0
                return {"estrategia_valida": False}
        else:
            return {"estrategia_valida": False}

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "precio_entrada": last_price,
                    "stop_loss": stop_loss,
                    "estrategia_valida": True
                    }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price
        avg_price = self.avg_price

        # Validación de estructura - BB inferior > SMA
        if df['bb1_upper'].iloc[i] <= df['sma'].iloc[i]:
            print(f"✅ Condicón 1: BB superior está por debajo de SMA {self.indicator}")
            self.condicion_1 = True
        else:
            return {"estrategia_valida": False}

        # Validación de cruce MACD
        if self.condicion_1 and ((df['macd_line'].iloc[i - 1] > df['macd_signal'].iloc[i - 1] and df['macd_line'].iloc[i] < df['macd_signal'].iloc[i])):
            print(f"✅✅ Condición 2: Cruce MACD detectado {self.indicator}")
            self.condicion_2 = True
        else:
            self.condicion_1 = False
            return {"estrategia_valida": False}

        # Validación de ruptura por encima de la BB superior usando last_price
        df_temp = df.copy()
        df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
        if self.serie_bb == "Avg_price":
            df_temp.at[len(df_temp) - 1, 'Avg_price'] = avg_price
            close_temp = df_temp['Avg_price']
            price = avg_price
        else: # self.serie_bb == "Close" or "ext_bb"
            df_temp.at[len(df_temp) - 1, 'Close'] = last_price
            close_temp = df_temp['Close']
            price = last_price

        bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
        bb2_lower = bb2_recalc.bollinger_lband().iloc[-1]

        print(f"🔍 last_price={last_price} vs nueva BB inferior={bb2_lower}")

        if price < bb2_lower:
            max_price = df['High'].iloc[i - self.bb2_window:i].max()
            dist_valid = mgo.dist_valida_sl(last_price, max_price, self.dist_min, self.sep_sl, ratio=2, direccion='short')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                self.condicion_2 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_3 = True
                print(f"✅✅✅ Condición 3: Ruptura dinámica confirmada con precio actual {self.indicator}")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio maximo: {max_price}")

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "precio_entrada": last_price,
                    "stop_loss": stop_loss,
                    "estrategia_valida": True
                    }

        return {"estrategia_valida": False}
