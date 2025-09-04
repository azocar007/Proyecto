### ENTRADA DE DATOS ###
import pprint

# FUNCIONES ANIDADAS PARA LA ENTRADA DE DATOS

# Funciones para aceptar solo numeros int y float
def validar_numero(mensaje:str = "Ingresa el valor: "):
    while True:
        user_input = input(mensaje)
        try:
            valor = abs(float(user_input))  # Intentamos convertir el input a float
            if (
                valor.is_integer()
            ):  # Si el valor es un número entero, lo convertimos a int
                return int(valor)
            else:
                return valor  # Si tiene decimales, lo dejamos como float
        except ValueError:
            print("Entrada no válida. Por favor, ingresa un número.")

# Función para aceptar solo numeros int
def validar_numero_entero(mensaje: str = "Ingresa el valor: "):
    while True:
        user_input = input(mensaje)
        try:
            valor = abs(int(user_input))  # Intentamos convertir el input a int
            return valor  # valor solo int
        except ValueError:
            print("Entrada no válida. Por favor, ingresa un número entero.")

# Funcíon para aceptar numeros devolviendo un string
def validar_numero_str(mensaje: str = "Ingresa el valor: "):
    while True:
        user_input = input(mensaje)
        try:
            float(user_input)  # Intentamos convertir el input a float
            return user_input
        except ValueError:
            print("Entrada no válida. Por favor, ingresa un número.")

# Función para calcular la cantidad de decimales de una variable
def contar_decimales(numero: float):
    numero_str = str(numero)
    if "." in numero_str:
        return len(numero_str.split(".")[1])
    else:
        return 0

# Función para seleccionar opciones de un menú
def seleccionar_opcion(opciones: dict, mensaje: str):
    """Función genérica para validar opciones de menú"""
    opciones_formateadas = "\n".join([f"{clave}: {valor}" for clave, valor in opciones.items()])

    while True:
        seleccion = input(f"\n📌 Opciones disponibles:\n{opciones_formateadas}\n{mensaje} ").strip()
        if seleccion in opciones:
            return opciones[seleccion]
        print("\n❌ Opción inválida. Intente de nuevo.")


# FUNCIONES PRINCIPALES PARA LA ENTRADA DE DATOS

# Función para seleccionar el exchange y el activo
def seleccion_de_exchange_y_moneda():
    while True:

        print("\nBIENVENIDO AL BOT DE TRADING AZC 1.0")

        # SELECCIÓN DEL EXCHANGE Y ACTIVO
        opciones_de_exchanges = {
            "1": "BINANCE",
            "2": "BYBIT",
            "3": "PHEMEX",
            "4": "BING X",
            "5": "OKX",
            "6": "BITGET",
        }

        exchange_seleccionado = seleccionar_opcion(opciones_de_exchanges, "Seleccione el exchange (1-6):")

        # Ingreso de moneda o activo a tradear
        moneda = input("\nPor favor introduzca el nombre del activo para TRADING:\n")
        moneda = moneda.upper() + "USDT"
        # ENVIA A PANTALLA LOS DATOS INGRESADOS
        print(
            f"""\nLOS DATOS INGRESADOS SON LOS SIGUIENTES:\n
        Exchange seleccionado: {exchange_seleccionado}
        Activo: {moneda}"""
        )

        # Diccionario para almacenar los datos calculados
        datos_seleccionados = {"simbol" : moneda, "exchange": exchange_seleccionado}
        datoscorrectos = input(
            "\n¿Esta conforme con el exchange y la moneda?\n(si/no): ").lower()
        
        if datoscorrectos == "s" or datoscorrectos == "si":
            return datos_seleccionados

# Función para la entrada de datos
def entrada_de_datos():
    while True:

        print("\nINGRESO DE DATOS PARA LA OPERACIÓN")

        # SELECCIÓN DEL TIPO DE GESTION, DOBLE TAP, UNIDERECCIONAL LONG, UNIDERECCIONAL SHORT, SNOW BALL Ó RATIO PERDIDA:BENEFICIO
        opciones_de_gestion = {
            "1": "DOBLE TAP",
            "2": "UNIDIRECCIONAL LONG",
            "3": "UNIDIRECCIONAL SHORT",
            "4": "SNOW BALL",
            "5": "RATIO BENEFICIO/PERDIDA LONG",
            "6": "RATIO BENEFICIO/PERDIDA SHORT",
        }
        gestion_seleccionada = seleccionar_opcion(opciones_de_gestion, "Seleccione el tipo de gestión (1-6):")

        # SELECCIÓN DE TIPO DE ENTRADA
        opciones_de_entrada = {
            "1": "MERCADO",
            "2": "BBO",
            "3": "LIMITE"
        }
        gestion_de_entrada = seleccionar_opcion(opciones_de_entrada, "Seleccione el tipo de entrada (1-3):")

        # VALORES PARA LAS ENTRADAS
        if gestion_de_entrada == "MERCADO" or gestion_de_entrada == "BBO":
            if (gestion_seleccionada == "UNIDIRECCIONAL SHORT" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA SHORT"):
                entrada_long = "N/A"
                entrada_short = gestion_de_entrada
            elif (gestion_seleccionada == "UNIDIRECCIONAL LONG" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA LONG"):
                entrada_long = gestion_de_entrada
                entrada_short = "N/A"
            else:
                entrada_long = gestion_de_entrada
                entrada_short = gestion_de_entrada
        else: # gestion_de_entrada == "LIMITE":
            if (gestion_seleccionada == "UNIDIRECCIONAL SHORT" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA SHORT"):
                entrada_long = "N/A"
                print("\nPrecio de entrada SHORT")
                entrada_short = validar_numero()
            elif (gestion_seleccionada == "UNIDIRECCIONAL LONG" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA LONG"):
                print("\nPrecio de entrada LONG")
                entrada_long = validar_numero()
                entrada_short = "N/A"
            else:
                print("\nPrecio de entrada LONG")
                entrada_long = validar_numero()
                print("\nPrecio de entrada SHORT")
                entrada_short = validar_numero()

# Definiciones iniciales del capital de entrada
        cantidad_usdt_long = "N/A"
        cantidad_usdt_short = "N/A"
        cantidad_monedas_long = "N/A"
        cantidad_monedas_short = "N/A"
        valor_pips = "N/A"
        cantidad_decimales_monedas = "N/A"

        # VALORES PARA LA GESTION DE REENTRADAS RATIO BENEFICIO/PERDIDA LONG y SHORT

        if gestion_seleccionada == "RATIO BENEFICIO/PERDIDA LONG":
            print("\nPrecio de Stop Loss, debe ser menor al precio de entrada LONG")
            entrada_stoploss = validar_numero()
            # Validar que el precio de stop loss sea menor al precio de entrada
            while gestion_de_entrada == "LIMITE" and entrada_stoploss >= entrada_long:
                print("\nValor incorrecto, el precio de Stop Loss debe ser menor al precio de entrada LONG")
                entrada_stoploss = validar_numero()

        elif gestion_seleccionada == "RATIO BENEFICIO/PERDIDA SHORT":
            print("\nPrecio de Stop Loss, debe ser mayor al precio de entrada SHORT")
            entrada_stoploss = validar_numero()
            # Validar que el precio de stop loss sea mayor al precio de entrada
            while gestion_de_entrada == "LIMITE" and entrada_stoploss <= entrada_short:
                print("\nValor incorrecto, el precio de Stop Loss debe ser mayor al precio de entrada SHORT")
                entrada_stoploss = validar_numero()

        else: # VALORES PARA LA GESTION DEL VOLUMEN DE MONEDAS y % DISTANCIA DE REENTRADAS
            print("\nPorcentaje de distancia de reentradas")
            porcentaje_dist_reentradas = validar_numero()

            print("\nCantidad de USDT ó MONEDAS para entrada inicial")
            capital_de_entrada = validar_numero_str()
            cantidad_decimales_monedas = contar_decimales(capital_de_entrada)
            capital_de_entrada = abs(float(capital_de_entrada))
            opcion_de_volumen = {
                "1": "USDT",
                "2": "MONEDAS"}
            modo_seleccion_volumen = seleccionar_opcion(opcion_de_volumen, "Seleccione el identificador de volumen (1-2):")

            if modo_seleccion_volumen == "USDT":
                if gestion_seleccionada == "UNIDIRECCIONAL SHORT":
                    cantidad_usdt_short = capital_de_entrada
                elif gestion_seleccionada == "UNIDIRECCIONAL LONG":
                    cantidad_usdt_long = capital_de_entrada
                elif gestion_seleccionada == "DOBLE TAP" or gestion_seleccionada == "SNOW BALL":
                    cantidad_usdt_long = capital_de_entrada
                    cantidad_usdt_short = capital_de_entrada

            else: # modo_seleccion_volumen == "MONEDAS":
                if gestion_seleccionada == "UNIDIRECCIONAL SHORT":
                    cantidad_monedas_short = capital_de_entrada
                elif gestion_seleccionada == "UNIDIRECCIONAL LONG":
                    cantidad_monedas_long = capital_de_entrada
                elif gestion_seleccionada == "DOBLE TAP" or gestion_seleccionada == "SNOW BALL":
                    cantidad_monedas_long = capital_de_entrada
                    cantidad_monedas_short = capital_de_entrada

            # Selección de modo de gestión de volumen (% DE REENTRADAS, MARTINGALA, AGRESIVO)
            opciones_de_modo_volumen = {
                "1": "% DE REENTRADAS",
                "2": "MARTINGALA",
                "3": "AGRESIVO"
            }
            modo_seleccionado = seleccionar_opcion(opciones_de_modo_volumen, "Seleccione el modo de gestión de volumen (1-3):")
            # Porcentaje de volumen para gestión de reentradas
            print("\nPorcentaje de volumen para gestión de reentradas")
            porcentaje_vol_reentrada = validar_numero()
            # Cantidad de entradas
            print("\nCantidad de entradas")
            cantidad_de_entradas = validar_numero_entero()
            entrada_stoploss = "N/A"

        # VALORES PARA LA GESTION DE RIESGO
        # Monto de Stop Loss
        print("\nMonto para Stop Loss o Cobertura")
        monto_de_sl = validar_numero_str()
        cant_decimales_monto_sl = contar_decimales(monto_de_sl)
        monto_de_sl = float(monto_de_sl)

        # CALCULOS INICIALES BASICOS PARA LA ENTRADA DE DATOS #
        # Cantidad de decimales del precio
        cant_decimales_long = contar_decimales(entrada_long)
        cant_decimales_short = contar_decimales(entrada_short)
        cant_decimales_sl = contar_decimales(entrada_stoploss)
        list_cant_dec_precio = [cant_decimales_long, cant_decimales_short, cant_decimales_sl]
        cantidad_decimales_precio = max(list_cant_dec_precio)

        if gestion_de_entrada == "LIMITE":
            if entrada_long == "N/A":
                entrada_short = round(float(entrada_short), cantidad_decimales_precio)
            elif entrada_short == "N/A":
                entrada_long = round(float(entrada_long), cantidad_decimales_precio)
            else:
                entrada_long = round(float(entrada_long), cantidad_decimales_precio)
                entrada_short = round(float(entrada_short), cantidad_decimales_precio)
            valor_pips = round(10 ** (cantidad_decimales_precio * -1), cantidad_decimales_precio)

        # SELECCIÓN DE USDT Ó MONEDAS - CALCULO DE CANTIDAD DE DECIMALES DE MONEDA - CANTIDAD DE MONEDAS
        if (gestion_seleccionada == "RATIO BENEFICIO/PERDIDA LONG" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA SHORT"):
            entrada_stoploss = round(float(entrada_stoploss), cantidad_decimales_precio)
            cantidad_decimales_monedas = cant_decimales_monto_sl
            valor_pips = round(10 ** (cantidad_decimales_precio * -1), cantidad_decimales_precio)
            # Variables que no aplican en la gestion ratio beneficio/perdida
            cantidad_de_entradas = "N/A"
            porcentaje_dist_reentradas = "N/A"
            modo_seleccionado="N/A"
            porcentaje_vol_reentrada = "N/A"

        # Solicitud de datos para gestion de Take profit

        if "RATIO" in gestion_seleccionada:
            print("\nFactor multiplicador para el RATIO BENEFICIO/PERDIDA")
            gestion_take_profit = "RATIO BENEFICIO/PERDIDA"
        else: # Gestion con recompras (DOBLE TAP, SNOW BALL, UNIDIRECCIONAL)
            opciones_gestion_take_profit = {
                "1": "% TAKE PROFIT",
                "2": "LCD (Carga y Descarga)"
            }
            gestion_take_profit = seleccionar_opcion(opciones_gestion_take_profit, "Seleccione el tipo de gestión de Take Profit (1-2):")
            print("\nPorcentaje de distancia para el Take Profit")

        ratio = validar_numero()
        ratio = round(float(ratio), 1)

        # ENVIA A PANTALLA LOS DATOS INGRESADOS

        if (gestion_seleccionada == "RATIO BENEFICIO/PERDIDA LONG" or gestion_seleccionada == "RATIO BENEFICIO/PERDIDA SHORT"):
            # Gestion RATIO BENEFICIO/PERDIDA LONG y SHORT
            print(
                f"""\nLOS DATOS INGRESADOS SON LOS SIGUIENTES:\n\n
            Tipo de gestión: {gestion_seleccionada}
            Tipo de entrada: {gestion_de_entrada}
            
            Precio de entrada LONG: {entrada_long}
            Precio de entrada SHORT: {entrada_short}
            
            Volumen de entrada inicial:
            LONG: {cantidad_monedas_long} MONEDAS => {cantidad_usdt_long} USDT
            SHORT: {cantidad_monedas_short} MONEDAS => {cantidad_usdt_short} USDT
            
            Factor RATIO BENEFICIO/PERDIDA: {ratio}
            Monto de STOP LOSS ó COBERTURA: {monto_de_sl} USDT
            Precio de Stop Loss: {entrada_stoploss}\n"""
            )
        else: # Gestion con recompras
            print(
                f"""\nLOS DATOS INGRESADOS SON LOS SIGUIENTES:\n\n
            Tipo de gestión: {gestion_seleccionada}
            Tipo de entrada: {gestion_de_entrada}
            
            Precio de entrada LONG: {entrada_long}
            Precio de entrada SHORT: {entrada_short}
            Porcentaje de distancia de reentradas: {porcentaje_dist_reentradas}%\n
            
            Volumen de entrada inicial:
            LONG: {cantidad_monedas_long} MONEDAS => {cantidad_usdt_long} USDT
            SHORT: {cantidad_monedas_short} MONEDAS => {cantidad_usdt_short} USDT
            
            Modo gestión de volumen: {modo_seleccionado}
            Porcentaje de volumen para gestión de reentradas: {porcentaje_vol_reentrada}%
            Cantidad de entradas: {cantidad_de_entradas}
            
            Monto de STOP LOSS ó COBERTURA: {monto_de_sl} USDT
            Gestion de Take Profit: {gestion_take_profit}
            Porcentaje de distancia para TAKE PROFIT: {ratio}%\n"""
            )

        # Dicionario para almacenar los datos calculados
        datos_calculados = {
            "gestion_seleccionada": gestion_seleccionada,
            "gestion_de_entrada": gestion_de_entrada,
            "entrada_long": entrada_long,
            "entrada_short": entrada_short,
            "porcentaje_dist_reentradas": porcentaje_dist_reentradas,
            "cantidad_usdt_long" : cantidad_usdt_long,
            "cantidad_usdt_short" : cantidad_usdt_short,
            "cantidad_monedas_long": cantidad_monedas_long,
            "cantidad_monedas_short": cantidad_monedas_short,
            "modo_seleccionado": modo_seleccionado,
            "porcentaje_vol_reentrada": porcentaje_vol_reentrada,
            "monto_de_sl": monto_de_sl,
            "entrada_stoploss": entrada_stoploss,
            "cantidad_de_reentradas": cantidad_de_entradas,
            "cantidad_decimales_monedas": cantidad_decimales_monedas,
            "cantidad_decimales_precio": cantidad_decimales_precio,
            "valor_pips": valor_pips,
            "gestion_take_profit": gestion_take_profit,
            "ratio": ratio
            }

        datoscorrectos = input("\n¿Esta conforme con los datos ingresados?\n(si/no): ").lower()
        if datoscorrectos == "s"or datoscorrectos == "si":
            return datos_calculados


# COMPROBACIÓN DEL MODULO
exchange_y_moneda = seleccion_de_exchange_y_moneda()
#datos_de_entrada = entrada_de_datos()
# print(f"EL exchange y la moneda seleccionada son:\n{exchange_y_moneda}")
# pprint.pprint(f"Diccionario de datos ingresados:\n{datos_de_entrada}")
# git push origin main --force comando en la terminal para forzar la subida al repositorio
