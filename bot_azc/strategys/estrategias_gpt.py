import pandas as pd
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands

""" === Funciones de condición reutilizables === """

def distancia_valida(last_price, referencia, dist_min):
    dist_pct = abs((last_price - referencia) / referencia) * 100
    return dist_pct >= dist_min, dist_pct

def calcular_stop_loss(last_price, referencia, sep_min, direccion='long'):
    delta = abs(last_price - referencia) * (1 + sep_min / 100)
    return last_price - delta if direccion == 'long' else last_price + delta


""" === Clase estrategia SMA + MACD + BB === """

class SMA_MACD_BB:
    def __init__(
        self,
        df: pd.DataFrame,
        last_price: float,
        decimales: int = 2,
        sma_window: int = 100,
        bb_window: int = 20,
        bb_dev: float = 2.0,
        macd_fast: int = 10,
        macd_slow: int = 20,
        macd_signal: int = 10,
        dist_min: float = 0.5,
        sep_min: int = 25
    ):
        self.df = df.copy().reset_index(drop=True)
        self.df_vista = df.copy().reset_index()
        self.df_vista.rename(columns={'index': 'Time'}, inplace=True)

        self.last_price = last_price
        self.decimales = decimales
        self.sma_window = sma_window
        self.bb_window = bb_window
        self.bb_dev = bb_dev
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.dist_min = dist_min
        self.sep_min = sep_min

        self._calcular_indicadores()

        if self.decimales is not None:
            for col in ['Close', 'sma', 'bb_lower', 'bb_upper', 'macd', 'macd_signal']:
                self.df[col] = self.df[col].round(self.decimales)
                self.df_vista[col] = self.df_vista[col].round(self.decimales)

        print("\n📊 Últimos datos con indicadores (SMA_MACD_BB):")
        print(self.df_vista[['Time', "Close", "sma", "bb_lower", "bb_upper", "macd", "macd_signal"]].tail(5).to_string(index=False))

    def _calcular_indicadores(self):
        close = self.df['Close']
        self.df['sma'] = SMAIndicator(close, window=self.sma_window).sma_indicator()
        bb = BollingerBands(close, window=self.bb_window, window_dev=self.bb_dev)
        self.df['bb_lower'] = bb.bollinger_lband()
        self.df['bb_upper'] = bb.bollinger_hband()

        macd = MACD(
            close,
            window_slow=self.macd_slow,
            window_fast=self.macd_fast,
            window_sign=self.macd_signal
        )
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()

    def evaluar_entrada_long(self):
        for i in range(max(self.sma_window, self.bb_window), len(self.df) - 1):

            if not self.df['bb_lower'][i - 1] >= self.df['sma'][i - 1]:
                continue

            if not self.df['macd'][i - 1] > self.df['macd_signal'][i - 1]:
                continue

            # Recalcular BB con precio actual incluido
            df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
            bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
            bb_upper = round(bb_temp.bollinger_hband().iloc[-1], self.decimales)

            if self.last_price >= bb_upper:
                continue

            min_price = self.df['Low'][i - self.bb_window:i].min()
            es_valida, dist_pct = distancia_valida(self.last_price, min_price, self.dist_min)
            if not es_valida:
                continue

            stop_loss = calcular_stop_loss(self.last_price, min_price, self.sep_min, 'long')
            return {
                "estrategia_valida": True,
                "precio_entrada": self.last_price,
                "stop_loss": stop_loss,
                "tipo": "long"
            }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        for i in range(max(self.sma_window, self.bb_window), len(self.df) - 1):

            if not bb_sobre_sma(self.df['bb_upper'][i - 1], self.df['sma'][i - 1]):
                continue

            if not cruce_macd(self.df['macd'][i - 1], self.df['macd_signal'][i - 1]):
                continue

            # Recalcular BB con precio actual incluido
            df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
            bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
            bb_lower = round(bb_temp.bollinger_lband().iloc[-1], self.decimales)

            if not ruptura_banda_en_tiempo_real(self.last_price, bb_lower, 'short'):
                continue

            max_price = self.df['High'][i - self.bb_window:i].max()
            es_valida, dist_pct = distancia_valida(max_price, self.last_price, self.dist_min)
            if not es_valida:
                continue

            stop_loss = calcular_stop_loss(self.last_price, max_price, self.sep_min, 'short')
            return {
                "estrategia_valida": True,
                "precio_entrada": self.last_price,
                "stop_loss": stop_loss,
                "tipo": "short"
            }

        return {"estrategia_valida": False}


""" === Clase estrategia SMA + BB sin MACD === """

class SMA_BB:
    def __init__(
        self,
        df: pd.DataFrame,
        last_price: float,
        decimales: int = 2,
        sma_window: int = 100,
        bb_window: int = 20,
        bb_dev: float = 2.0,
        dist_min: float = 0.5,
        sep_min: int = 25
    ):
        self.df = df.copy().reset_index(drop=True)
        self.df_vista = df.copy().reset_index()
        self.df_vista.rename(columns={'index': 'Time'}, inplace=True)

        self.last_price = last_price
        self.decimales = decimales
        self.sma_window = sma_window
        self.bb_window = bb_window
        self.bb_dev = bb_dev
        self.dist_min = dist_min
        self.sep_min = sep_min

        self._calcular_indicadores()

        if self.decimales is not None:
            for col in ['Close', 'sma', 'bb_lower', 'bb_upper']:
                self.df[col] = self.df[col].round(self.decimales)
                self.df_vista[col] = self.df_vista[col].round(self.decimales)

        print("\n📊 Últimos datos con indicadores (SMA_BB):")
        print(self.df_vista[['Time', "Close", "sma", "bb_lower", "bb_upper"]].tail(5).to_string(index=False))

    def _calcular_indicadores(self):
        close = self.df['Close']
        self.df['sma'] = SMAIndicator(close, window=self.sma_window).sma_indicator()
        bb = BollingerBands(close, window=self.bb_window, window_dev=self.bb_dev)
        self.df['bb_lower'] = bb.bollinger_lband()
        self.df['bb_upper'] = bb.bollinger_hband()

    def evaluar_entrada_long(self):
        for i in range(max(self.sma_window, self.bb_window), len(self.df) - 1):
            if not bb_sobre_sma(self.df['bb_lower'][i - 1], self.df['sma'][i - 1]):
                continue

            df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
            bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
            bb_upper = round(bb_temp.bollinger_hband().iloc[-1], self.decimales)

            if not ruptura_banda_en_tiempo_real(self.last_price, bb_upper, 'long'):
                continue

            min_price = self.df['Low'][i - self.bb_window:i].min()
            es_valida, dist_pct = distancia_valida(self.last_price, min_price, self.dist_min)
            if not es_valida:
                continue

            stop_loss = calcular_stop_loss(self.last_price, min_price, self.sep_min, 'long')
            return {
                "estrategia_valida": True,
                "precio_entrada": self.last_price,
                "stop_loss": stop_loss,
                "tipo": "long"
            }

        return {"estrategia_valida": False}

    def evaluar_entrada_short(self):
        for i in range(max(self.sma_window, self.bb_window), len(self.df) - 1):
            if not bb_sobre_sma(self.df['bb_upper'][i - 1], self.df['sma'][i - 1]):
                continue

            df_temp = pd.concat([self.df, self.df.iloc[[-1]]], ignore_index=True)
            df_temp.at[len(df_temp) - 1, 'Close'] = self.last_price
            bb_temp = BollingerBands(df_temp['Close'], window=self.bb_window, window_dev=self.bb_dev)
            bb_lower = round(bb_temp.bollinger_lband().iloc[-1], self.decimales)

            if not ruptura_banda_en_tiempo_real(self.last_price, bb_lower, 'short'):
                continue

            max_price = self.df['High'][i - self.bb_window:i].max()
            es_valida, dist_pct = distancia_valida(max_price, self.last_price, self.dist_min)
            if not es_valida:
                continue

            stop_loss = calcular_stop_loss(self.last_price, max_price, self.sep_min, 'short')
            return {
                "estrategia_valida": True,
                "precio_entrada": self.last_price,
                "stop_loss": stop_loss,
                "tipo": "short"
            }

        return {"estrategia_valida": False}
