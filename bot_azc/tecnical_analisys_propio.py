# indicadores_personalizados.py
import pandas as pd

""" Funciones de condición de Analisis Tecnico """
# Devuelve True si serie1 cruza hacia arriba a serie2.
def crossover1(serie1, serie2):
    return (serie1[-2] < serie2[-2]) and (serie1[-1] > serie2[-1])

# Devuelve True si serie1 cruza hacia abajo a serie2.
def crossunder1(serie1, serie2):
    return (serie1[-2] > serie2[-2]) and (serie1[-1] < serie2[-1])

# Devuelve True si serie1 es mayor o igual que serie2.
def mayor_igual_que(serie1, serie2):
    return serie1[-1] >= serie2[-1]

# Devuelve True si serie1 es mayor o igual que serie2.
def menor_igual_que(serie1, serie2):
    return serie1[-1] <= serie2[-1]


""" Calcula la media móvil simple (SMA) """
def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


""" Calcula la media móvil exponencial (EMA) """
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


""" Calcula el RSI (Índice de Fuerza Relativa) """
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi_value = 100 - (100 / (1 + rs))
    return rsi_value


""" Calcula el Estocástico """
def stochastic(series: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3):
    min_val = series.rolling(window=period).min()
    max_val = series.rolling(window=period).max()
    k = ((series - min_val) / (max_val - min_val)) * 100
    k = k.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k, d


""" Calcula el ADX (Índice Direccional Promedio) """
def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx_value = dx.rolling(window=period).mean()
    return adx_value, plus_di, minus_di


""" Calcula el ATR (Rango Verdadero Promedio) """
def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ], axis=1).max(axis=1)
    atr_value = tr.rolling(window=period).mean()
    return atr_value


""" Calcula el CCI (Índice de Canal de Materias Primas) """
def cci(series: pd.Series, period: int = 20):
    sma_ = sma(series, period)
    mad = (series - sma_).abs().rolling(window=period).mean()
    cci_value = (series - sma_) / (0.015 * mad)
    return cci_value


""" Calcula el Williams %R """
def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
    min_val = low.rolling(window=period).min()
    max_val = high.rolling(window=period).max()
    wr = ((max_val - close) / (max_val - min_val)) * -100
    return wr


""" Calcula el Aroon """
def aroon(series: pd.Series, period: int = 14):
    aroon_up = ((period - (series.rolling(window=period).apply(lambda x: x.argmax() + 1))) / period) * 100
    aroon_down = ((period - (series.rolling(window=period).apply(lambda x: x.argmin() + 1))) / period) * 100
    return aroon_up, aroon_down


""" Calcula el Momentum """
def momentum(series: pd.Series, period: int = 10):
    return series.diff(periods=period)


""" Calcula el Parabolic SAR """
def parabolic_sar(high: pd.Series, low: pd.Series, close: pd.Series, af: float = 0.02, max_af: float = 0.2):
    sar = pd.Series(index=close.index)
    sar.iloc[0] = close.iloc[0]
    trend = 1  # 1 = alcista, -1 = bajista
    ep = high.iloc[0]  # Punto extremo
    af_ = af  # Factor de aceleración
    for i in range(1, len(close)):
        sar.iloc[i] = sar.iloc[i - 1] + af_ * (ep - sar.iloc[i - 1])
        if trend == 1:
            if high.iloc[i] > ep:
                ep = high.iloc[i]
                af_ = min(af_ + af, max_af)
            if low.iloc[i] < sar.iloc[i]:
                trend = -1
                sar.iloc[i] = ep
                ep = low.iloc[i]
                af_ = af
        else:
            if low.iloc[i] < ep:
                ep = low.iloc[i]
                af_ = min(af_ + af, max_af)
            if high.iloc[i] > sar.iloc[i]:
                trend = 1
                sar.iloc[i] = ep
                ep = high.iloc[i]
                af_ = af
    return sar


""" Calcula las bandas de Bollinger (superior, media, inferior) """
def bollinger_bands(series: pd.Series, period: int = 20, dev: float = 2):
    sma_ = sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma_ + (std * dev)
    lower = sma_ - (std * dev)
    return upper, sma_, lower


""" Calcula el MACD, la línea de señal y el histograma """
def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


""" Calcula el OBV (On-Balance Volume) """
def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    obv_series = pd.Series(index=close.index)
    obv_series.iloc[0] = 0  # El primer valor es 0
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv_series.iloc[i] = obv_series.iloc[i - 1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i - 1]:
            obv_series.iloc[i] = obv_series.iloc[i - 1] - volume.iloc[i]
        else:
            obv_series.iloc[i] = obv_series.iloc[i - 1]
    return obv_series


""" Calcula el VWAP (Precio Medio Ponderado por Volumen) """
def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    vwap_value = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap_value

""" Calcula el Chaikin Oscillator """
def chaikin_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, short_period: int = 3, long_period: int = 10) -> pd.Series:
    adl = ((close - low) - (high - close)) / (high - low) * volume
    adl_cumsum = adl.cumsum()
    short_ma = adl_cumsum.ewm(span=short_period, adjust=False).mean()
    long_ma = adl_cumsum.ewm(span=long_period, adjust=False).mean()
    chaikin_osc = short_ma - long_ma
    return chaikin_osc


""" Calcula el Force Index """
def force_index(close: pd.Series, volume: pd.Series, period: int = 13) -> pd.Series:
    force = close.diff() * volume
    force_index = force.rolling(window=period).sum()
    return force_index


""" Calcula el Keltner Channel """
def keltner_channel(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20, atr_multiplier: float = 1.5):
    middle_band = sma(close, period)
    atr_value = atr(high, low, close, period)
    upper_band = middle_band + (atr_value * atr_multiplier)
    lower_band = middle_band - (atr_value * atr_multiplier)
    return upper_band, middle_band, lower_band