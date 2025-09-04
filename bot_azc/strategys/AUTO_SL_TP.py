""" CODIGO PARA MOSTRAR INDICADORES Y/O ESTRATEGIAS DURANTE EJECUCIÓN DE SL Y TP AUTOMATICO """
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
                decimales: int = None,
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
                dist_min: float = 0.5,         # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
                sep_sl: int = 25            # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
                ):
                self.last_price = last_price
                self.decimales = decimales
                self.df = df.copy().reset_index(drop=True)
                self.df2 = df.copy()
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

                self._calcular_indicadores(self.df)
                self._calcular_indicadores(self.df2)
                self.condicion_1 = False
                self.condicion_2 = False
                self.condicion_3 = False

                # Redondear los valores a los decimales especificados
                if self.decimales is not None:
                    for col in ["Close", "sma", "bb1_lower", "bb1_upper", "bb2_lower", "bb2_upper", "macd_line", "macd_signal"]:
                        self.df[col] = self.df[col].round(self.decimales)
                        self.df2[col] = self.df2[col].round(self.decimales)

                # Mostrar el DataFrame con indicadores al inicializar la clase
                velas = 5
                print(f"\n📊 DataFrame dinamico con indicadores calculados de las ultimas {velas} cerradas:")
                print(self.df2[["Close", "sma", "bb1_lower", "bb1_upper", "bb2_lower", "bb2_upper", "macd_line", "macd_signal"]].tail(velas).to_string(index=True))

    def _calcular_indicadores(self, df: pd.DataFrame = None):
        valorsma = df['Close']
        #valorsma = df['Avg_price']

        # calculo de la media movil simple (SMA)
        df['sma'] = SMAIndicator(valorsma, window=self.sma_window).sma_indicator()

        # Calculo de MACD
        macd = MACD(valorsma, window_slow=self.macd_slow, window_fast=self.macd_fast, window_sign=self.macd_signal)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        # Calculo de las bandas de Bollinger
        valorbb1 = df['Close']
        #valorbb1 = df['Avg_price']
        #valorbb1 = df['High']
        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_upper'] = bb1.bollinger_hband()

        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_lower'] = bb1.bollinger_lband()

        valorbb2 = df['Close']
        #valorbb2 = df['Avg_price']
        #valorbb2 = df['Low']
        bb2 = BollingerBands(valorbb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_upper'] = bb2.bollinger_hband()

        bb2 = BollingerBands(valorbb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_lower'] = bb2.bollinger_lband()

    def evaluar_entrada_long(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price

        # Validación de estructura - BB inferior > SMA
        if df['bb1_lower'].iloc[i] >= df['sma'].iloc[i]:
            print("✅ Condicón 1: BB inferior está por encima de SMA")
            self.condicion_1 = True
            return {"estrategia_valida": False}

        # Validación de cruce MACD
        if self.condicion_1 and ((df['macd_line'].iloc[i - 1] < df['macd_signal'].iloc[i - 1] and df['macd_line'].iloc[i] > df['macd_signal'].iloc[i])):
            print("✅✅ Condición 2: Cruce MACD detectado")
            self.condicion_2 = True
        else:
            self.condicion_1 = False
            return {"estrategia_valida": False}

        # Validación de ruptura por encima de la BB superior usando last_price
        df_temp = df.copy()
        df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
        df_temp.at[len(df_temp) - 1, 'Close'] = last_price

        close_temp = df_temp['Close']
        bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
        bb2_upper = bb2_recalc.bollinger_hband().iloc[-1]

        print(f"🔍 last_price={last_price} vs nueva BB superior={bb2_upper}")

        if last_price > bb2_upper:
            min_price = df['Low'].iloc[i - self.bb2_window:i].min()
            dist_valid = mgo.dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, 'long')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                self.condicion_2 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_3 = True
                print("✅✅✅ Condición 3: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price

        # Validación de estructura - BB inferior > SMA
        if df['bb1_upper'].iloc[i] <= df['sma'].iloc[i]:
            print("✅ Condicón 1: BB superior está por debajo de SMA")
            self.condicion_1 = True
            return {"estrategia_valida": False}

        # Validación de cruce MACD
        if self.condicion_1 and ((df['macd_line'].iloc[i - 1] > df['macd_signal'].iloc[i - 1] and df['macd_line'].iloc[i] < df['macd_signal'].iloc[i])):
            print("✅✅ Condición 2: Cruce MACD detectado")
            self.condicion_2 = True
        else:
            self.condicion_1 = False
            return {"estrategia_valida": False}

        # Validación de ruptura por encima de la BB superior usando last_price
        df_temp = df.copy()
        df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
        df_temp.at[len(df_temp) - 1, 'Close'] = last_price

        close_temp = df_temp['Close']
        bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
        bb2_lower = bb2_recalc.bollinger_lband().iloc[-1]

        print(f"🔍 last_price={last_price} vs nueva BB inferior={bb2_lower}")

        if last_price < bb2_lower:
            max_price = df['High'].iloc[i - self.bb2_window:i].max()
            dist_valid = mgo.dist_valida_sl(last_price, max_price, self.dist_min, self.sep_sl, 'short')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                self.condicion_2 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_3 = True
                print("✅✅✅ Condición 3: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio maximo: {max_price}")

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}


"""=== Clase estrategia Media Movil + Bandas de bollinger ==="""
class SMA_BB:
    def __init__(
                self,
                df: pd.DataFrame,
                last_price: float = None,
                decimales: float = None,
                # Parametros SMA
                sma_window: int = 300,
                # Parametros para Bandas de Bollinger
                bb_window: int = 20,
                bb_dev: float = 2.0,
                # Parámetros para gestion de riesgo
                dist_min: float = 0.5,       # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
                sep_sl: int = 25            # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
                ):
        self.last_price = last_price
        self.decimales = decimales
        self.df = df.copy().reset_index(drop=True)
        self.df2 = df.copy()
        self.sma_window = sma_window
        self.bb_window = bb_window
        self.bb_dev = bb_dev
        self.dist_min = dist_min
        self.sep_sl = sep_sl

        self._calcular_indicadores(self.df)
        self._calcular_indicadores(self.df2)
        self.condicion_1 = False
        self.condicion_2 = False

        # Redondear los valores a los decimales especificados
        if self.decimales is not None:
            for col in ['Close', 'sma', 'bb_lower', 'bb_middle', 'bb_upper']:
                self.df[col] = self.df[col].round(self.decimales)
                self.df2[col] = self.df2[col].round(self.decimales)

        # Mostrar el DataFrame con indicadores al inicializar la clase
        velas = 5
        print(f"\n📊 DataFrame dinamico con indicadores calculados de las {velas} cerradas:")
        print(self.df2[["Close", "sma", "bb_lower", "bb_middle", "bb_upper"]].tail(velas).to_string(index=True))

    def _calcular_indicadores(self, df: pd.DataFrame = None):

        # Calculo de la media movil simple (SMA)
        close = df['Close']
        #close = df['Avg_price']
        df['sma'] = SMAIndicator(close, window=self.sma_window).sma_indicator()

        # Calculo de las bandas de Bollinger

        # Banda inferior
        low = df["Close"]
        #low = df["Low"]
        bb_lower = BollingerBands(low, window=self.bb_window, window_dev=self.bb_dev)
        df['bb_lower'] = bb_lower.bollinger_lband()

        # Banda media
        bb_middle = BollingerBands(close, window=self.bb_window, window_dev=self.bb_dev)
        df['bb_middle'] = bb_middle.bollinger_mavg()

        # Banda superior
        high = df["Close"]
        #high = df["High"]
        bb_upper = BollingerBands(high, window=self.bb_window, window_dev=self.bb_dev)
        df['bb_upper'] = bb_upper.bollinger_hband()

    def evaluar_entrada_long(self):
        # Asignando valores a variables
        df = self.df
        df2 = self.df2
        i = len(df) - 1
        last_price = self.last_price
        last_printed = None

        # Validación de estructura - BB inferior > SMA
        if df['bb_lower'].iloc[i] >= df['sma'].iloc[i]:
            self.condicion_1 = True
            df2 = df2.reset_index()
            print(f"✅ Condición 1: hora: {df2['Time'].iloc[i]} BB inferior {df['bb_lower'].iloc[i]} está por encima de SMA {df['sma'].iloc[i]}")
            return {"estrategia_valida": False}

        # Calculo de la ultima Banda de bollinger inferior
        df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
        df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
        bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
        bb_lower = round(bb_temp.bollinger_lband().iloc[-1], self.decimales)

        current = (last_price, bb_lower)
        if last_printed != current:
            print(f"🔍 last_price= {last_price} vs nueva BB inferior = {bb_lower}")
            last_printed = current

        if last_price <= bb_lower and self.condicion_1:
            min_price = df['Low'].iloc[i - self.bb_window:i].min()
            dist_valid = mgo.dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, 'long')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_2 = True
                print("✅✅ Condición 2: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")

        if self.condicion_1 and self.condicion_2:
            self.condicion_1 = False
            self.condicion_2 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        # Asignando valores a variables
        df = self.df
        df2 = self.df2
        i = len(df) - 1
        last_price = self.last_price
        last_printed = None

        # Validación de estructura - BB superior > SMA
        if df['bb_upper'].iloc[i] <= df['sma'].iloc[i]:
            self.condicion_1 = True
            df2 = df2.reset_index()
            print(f"✅ Condición 1: hora: {df2['Time'].iloc[i]} BB superior {df['bb_upper'].iloc[i]} está por encima de SMA {df['sma'].iloc[i]}")
            return {"estrategia_valida": False}

        # Calculo de la ultima Banda de bollinger superior
        df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
        df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
        bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
        bb_upper = round(bb_temp.bollinger_hband().iloc[-1], self.decimales)

        current = (last_price, bb_upper)
        if last_printed != current:
            print(f"🔍 last_price= {last_price} vs nueva BB superior = {bb_upper}")
            last_printed = current

        if last_price <= bb_upper and self.condicion_1:
            max_price = df['High'].iloc[i - self.bb_window:i].max()
            dist_valid = mgo.dist_valida_sl(last_price, max_price, self.dist_min, self.sep_sl, 'short')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_2 = True
                print("✅✅ Condición 2: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio maximo: {max_price}")
        if self.condicion_1 and self.condicion_2:
            self.condicion_1 = False
            self.condicion_2 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}


"""=== Clase estrategia Cruce de Bandas de Bollinger ==="""
class CRUCE_BB:
    def __init__(
                self,
                df: pd.DataFrame,
                last_price: float = None,
                decimales: int = None,
                indicator: str = None,
                # Parametros SMA
                sma_window: int = 100,
                # Parametros para Bandas de Bollinger
                bb1_window: int = 20,   # Ventana de la primera banda de Bollinger menor
                bb1_dev: float = 2.0,   # Desviación estándar de la primera banda de Bollinger
                bb2_window: int = 40,   # Ventana de la segunda banda de Bollinger mayor
                bb2_dev: float = 2.0,   # Desviación estándar de la segunda banda de Bollinger
                # Parametros para MACD
                macd_fast: int = 10,
                macd_slow: int = 20,
                macd_signal: int = 10,
                # Parámetros para gestion de riesgo
                dist_min: float = 0.5,         # % 0 - 1 Distancia mínima entre el precio de entrada y el stop loss
                sep_sl: int = 25               # % de 0 - 100 ampliación de dist entre min_price y precio de entrada
                ):
        self.last_price = last_price
        self.decimales = decimales
        self.indicator = indicator
        self.df = df.copy().reset_index(drop=True)
        self.df2 = df.copy()
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

        self._calcular_indicadores(self.df)
        self._calcular_indicadores(self.df2)
        self.condicion_1 = False
        self.condicion_2 = False
        self.condicion_3 = False

        # Redondear los valores a los decimales especificados
        if self.decimales is not None:
            for col in ["Close", "sma", "bb1_middle", "bb1_lower", "bb1_upper", "bb2_middle", "bb2_upper", "bb2_lower"]:
                self.df[col] = self.df[col].round(self.decimales)
                self.df2[col] = self.df2[col].round(self.decimales)

        # Mostrar el DataFrame con indicadores al inicializar la clase
        velas = 2
        print(f"\n📊 {self.indicator} DataFrame dinamico con indicadores calculados de las ultimas {velas} cerradas:")
        print(self.df2[["Close", "bb1_middle", "bb1_lower", "bb1_upper", "bb2_middle", "bb2_upper", "bb2_lower"]].tail(velas).to_string(index=True))

    def _calcular_indicadores(self, df: pd.DataFrame = None):
        valorsma = df['Close']
        #valorsma = df['Avg_price']

        # calculo de la media movil simple (SMA)
        df['sma'] = SMAIndicator(valorsma, window=self.sma_window).sma_indicator()

        # Calculo de MACD
        macd = MACD(valorsma, window_slow=self.macd_slow, window_fast=self.macd_fast, window_sign=self.macd_signal)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        # Calculo de las bandas de Bollinger menor
        valorbb1 = df['Close']
        #valorbb1 = df['Avg_price']
        #valorbb1 = df['High']
        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_upper'] = bb1.bollinger_hband()

        valormidle_bb1 = df['Close']
        #valormidle = df['Avg_price']
        bb1 = BollingerBands(valormidle_bb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_middle'] = bb1.bollinger_mavg()

        valorbb1 = df['Close']
        #valorbb1 = df['Avg_price']
        #valorbb1 = df['Low']
        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_lower'] = bb1.bollinger_lband()

        # Calculo de las bandas de Bollinger mayor
        valorbb2 = df['Close']
        #valorbb2 = df['Avg_price']
        #valorbb2 = df['High']
        bb2 = BollingerBands(valorbb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_upper'] = bb2.bollinger_hband()

        valormidle_bb2 = df['Close']
        #valormidle = df['Avg_price']
        bb2 = BollingerBands(valormidle_bb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_middle'] = bb2.bollinger_mavg()

        valorbb2 = df['Close']
        #valorbb2 = df['Avg_price']
        #valorbb2 = df['Low']
        bb2 = BollingerBands(valorbb2, window=self.bb2_window, window_dev=self.bb2_dev)
        df['bb2_lower'] = bb2.bollinger_lband()

    def evaluar_entrada_long(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price

        # Validación de separación minima entre BB superior y SMA
        dist_valida = dist_valida_sl(df["bb2_upper"].iloc[i], df["bb2_middle"].iloc[i], self.dist_min, self.sep_sl, 'long')
        dist_valida = dist_valida.get("dist_valida", False)
        if (last_price > df["bb2_middle"].iloc[i]) and dist_valida:
            print("✅ 🟢 Condicón 1: Distancia entre BB superior y SMA es válida")
            self.condicion_1 = True
        else:
            return {"estrategia_valida": False}

        # Validación de cruce de Bandas de Bollinger
        if self.condicion_1:
            df_temp = df.copy()
            df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = last_price

            close_temp = df_temp['Close']
            bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
            bb2_upper = bb2_recalc.bollinger_hband().iloc[-1]
            bb1_recalc = BollingerBands(close_temp, window=self.bb1_window, window_dev=self.bb1_dev)
            bb1_upper = bb1_recalc.bollinger_hband().iloc[-1]
            print(f"🔍 last_price {last_price} - BB Mayor upper {round(bb2_upper, self.decimales)} - BB Menor upper {round(bb1_upper, self.decimales)}")

        if self.condicion_1 and (df["bb2_upper"].iloc[i] > df["bb1_upper"].iloc[i] and bb2_upper < bb1_upper):
            print("✅✅ 🟢 Condición 2: Cruce de Bandas de Bollinger superiores detectada")
            print(f"🔍 last_price {last_price} vs nuevas BB Mayor superior {round(bb2_upper, self.decimales)} - BB Menor superior {round(bb1_upper, self.decimales)}")
            self.condicion_2 = True
        else:
            self.condicion_1 = False
            return {"estrategia_valida": False}

        # Validando la distancia entre el precio de entrada y el precio de la SMA mayor
        if self.condicion_2:
            min_price = df['bb2_middle'].iloc[i]
            dist_valid = mgo.dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, 'long')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                self.condicion_2 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_3 = True
                print("✅✅ 🟢 Condición 3: Distancia al Stop Loss validada")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        df = self.df
        i = len(df) - 1
        last_price = self.last_price

        # Validación de separación minima entre BB superior y SMA
        dist_valida = dist_valida_sl(df["bb2_lower"].iloc[i], df["bb2_middle"].iloc[i], self.dist_min, self.sep_sl, 'short')
        dist_valida = dist_valida.get("dist_valida", False)
        if (last_price < df["bb2_middle"].iloc[i]) and dist_valida:
            print("✅ 🔴 Condicón 1: Distancia entre BB inferior y SMA es válida")
            self.condicion_1 = True
            return {"estrategia_valida": False}

        # Validación de cruce de Bandas de Bollinger
        if self.condicion_1:
            df_temp = df.copy()
            df_temp = pd.concat([df_temp, df_temp.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = last_price

            close_temp = df_temp['Close']
            bb2_recalc = BollingerBands(close_temp, window=self.bb2_window, window_dev=self.bb2_dev)
            bb2_lower = bb2_recalc.bollinger_lband().iloc[-1]
            bb1_recalc = BollingerBands(close_temp, window=self.bb1_window, window_dev=self.bb1_dev)
            bb1_lower = bb1_recalc.bollinger_lband().iloc[-1]

        if self.condicion_1 and (df["bb2_lower"].iloc[i] < df["bb1_lower"].iloc[i] and bb2_lower > bb1_lower):
            print("✅✅ 🔴 Condición 2: Cruce de Bandas de Bollinger inferiores detectada")
            print(f"🔍 last_price {last_price} vs nuevas BB Mayor inferior {round(bb2_lower, self.decimales)} - BB Menor inferior {round(bb1_lower, self.decimales)}")
            self.condicion_2 = True
        else:
            self.condicion_1 = False
            return {"estrategia_valida": False}

        # Validando la distancia entre el precio de entrada y el precio de la SMA mayor
        if self.condicion_2:
            min_price = df['bb2_middle'].iloc[i]
            dist_valid = mgo.dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, 'short')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                self.condicion_2 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_3 = True
                print("✅✅ 🔴 Condición 3: Cruce dinámico confirmado con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")

        if self.condicion_1 and self.condicion_2 and self.condicion_3:
            self.condicion_1 = False
            self.condicion_2 = False
            self.condicion_3 = False
            return {
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}


"""=== Clase para asignar Stop Loss y Take Profit automaticamente ==="""
class SIN_ESTRATEGIA:
    def __init__(
                self,
                df: pd.DataFrame,
                last_price: float = None,
                decimales: int = None,
                # Parametros SMA
                sma_window: int = 100,
                # Parametros para Bandas de Bollinger
                bb1_window: int = 20,
                bb1_dev: float = 2.0,
                # Parametros para MACD
                macd_fast: int = 10,
                macd_slow: int = 20,
                macd_signal: int = 10,
                ):
        self.last_price = last_price
        self.decimales = decimales
        self.df = df.copy().reset_index(drop=True)
        self.df2 = df.copy()
        self.sma_window = sma_window
        self.bb1_window = bb1_window
        self.bb1_dev = bb1_dev
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

        self._calcular_indicadores(self.df2)

        # Redondear los valores a los decimales especificados
        if self.decimales is not None:
            for col in ["Close", "sma", "bb1_lower", "bb1_upper", "bb2_lower", "bb2_upper", "macd_line", "macd_signal"]:
                self.df2[col] = self.df2[col].round(self.decimales)

        # Mostrar el DataFrame con indicadores al inicializar la clase
        velas = 5
        print(f"\n📊 DataFrame dinamico con indicadores calculados de las ultimas {velas} cerradas:")
        print(self.df2[["Close", "sma", "bb1_lower", "bb1_upper", "macd_line", "macd_signal"]].tail(velas).to_string(index=True))

    def _calcular_indicadores(self, df: pd.DataFrame = None):
        valorsma = df['Close']
        #valorsma = df['Avg_price']

        # calculo de la media movil simple (SMA)
        df['sma'] = SMAIndicator(valorsma, window=self.sma_window).sma_indicator()

        # Calculo de MACD
        macd = MACD(valorsma, window_slow=self.macd_slow, window_fast=self.macd_fast, window_sign=self.macd_signal)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        # Calculo de las bandas de Bollinger
        valorbb1 = df['Close']
        #valorbb1 = df['Avg_price']
        #valorbb1 = df['High']
        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_upper'] = bb1.bollinger_hband()

        bb1 = BollingerBands(valorbb1, window=self.bb1_window, window_dev=self.bb1_dev)
        df['bb1_lower'] = bb1.bollinger_lband()

    def evaluar_entrada_long(self):
        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        return {"estrategia_valida": False}
