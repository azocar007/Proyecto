""" ESTRATEGIA MEDIA MOVIL + BANDAS DE BOLLINER """
import pandas as pd
import Modos_de_gestion_operativa as mgo
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands


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
            dist_valid = dist_valida_sl(last_price, min_price, self.dist_min, self.sep_sl, 'long')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_2 = True
                print("✅✅ Condición 2: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio minimo: {min_price}")
                """
                return {
                        "precio_entrada": last_price,
                        "stop_loss": stop_loss,
                        "estrategia_valida": True
                        }
                """
        if self.condicion_1 and self.condicion_2:
            self.condicion_1 = False
            self.condicion_2 = False
            return {
                    "precio_entrada": last_price,
                    "stop_loss": stop_loss,
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
            dist_valid = dist_valida_sl(last_price, max_price, self.dist_min, self.sep_sl, 'short')
            stop_loss = dist_valid.get("stop_loss", None)
            if stop_loss is None:
                self.condicion_1 = False
                return {"estrategia_valida": False}
            else:
                self.condicion_2 = True
                print("✅✅ Condición 2: Ruptura dinámica confirmada con precio actual")
                print(f"Precio de entrada: {last_price}, Stop Loss: {stop_loss}, precio maximo: {max_price}")
                """
                return {
                        "precio_entrada": last_price,
                        "stop_loss": stop_loss,
                        "estrategia_valida": True
                        }
                """
        if self.condicion_1 and self.condicion_2:
            self.condicion_1 = False
            self.condicion_2 = False
            return {
                    "precio_entrada": last_price,
                    "stop_loss": stop_loss,
                    "estrategia_valida": False
                    }

        return {"estrategia_valida": False}
