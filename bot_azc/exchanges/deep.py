# Añade estas propiedades en el __init__ de tu clase:
def __init__(self, ...):
    # ... (código existente)
    self.throttle_active = False
    self.throttle_expiration = None
    self.pending_orders = {}  # {symbol: {"side": "LONG/SHORT", "price": float, "time": timestamp}}
    self.order_cooldown = 60  # Segundos de bloqueo tras una señal (ajustable)
    
    
def on_message(ws, message):
    try:
        # ... (tu código existente de procesamiento de vela)

        # 1. Verificar si estamos en período de throttling
        current_time = time.time()
        if self.throttle_active and self.throttle_expiration and current_time < self.throttle_expiration:
            print(f"⏳ Throttling activo. Ignorando señales hasta: {self.throttle_expiration}")
            return

        # ... (tu código existente)

        resultado = self.estrategia_instancia.evaluar_entrada()
        if resultado.get("estrategia_valida", False):
            # 2. Obtener precio de entrada desde la estrategia
            entry_price = resultado.get("precio_entrada", self.last_price)  # Asegúrate que la estrategia devuelve esto
            
            # 3. Verificar si ya existe orden pendiente similar
            tolerance = 0.001  # 0.1% de tolerancia para mismo precio
            if self.symbol in self.pending_orders:
                existing_order = self.pending_orders[self.symbol]
                price_diff = abs(entry_price - existing_order["price"]) / entry_price
                
                # Comprobar misma dirección y precio similar
                if (existing_order["side"] == self.positionside and 
                    price_diff < tolerance and
                    current_time - existing_order["time"] < self.order_cooldown):
                    print(f"🔄 Orden similar ya pendiente: {existing_order}")
                    return
            
            # 4. Registrar nueva orden pendiente
            self.pending_orders[self.symbol] = {
                "side": self.positionside,
                "price": entry_price,
                "time": current_time
            }
            
            # 5. Activar throttling
            self.throttle_active = True
            self.throttle_expiration = current_time + self.order_cooldown
            
            # Llamada a la función para colocar la orden
            self.set_limit_market_order(self.symbol, self.positionside, self.modo_gestion, resultado)
            print(f"📤 Orden enviada - Throttling activado por {self.order_cooldown}s")
            
            # ... (el resto de tu código existente)
            
# metodo para limpiar ordenes antiguas
def clean_pending_orders(self):
    current_time = time.time()
    expired_orders = []
    
    for symbol, order in self.pending_orders.items():
        # Eliminar órdenes más viejas que el cooldown
        if current_time - order["time"] > self.order_cooldown:
            expired_orders.append(symbol)
    
    for symbol in expired_orders:
        print(f"🧹 Eliminando orden pendiente expirada: {symbol}")
        del self.pending_orders[symbol]
        
        # Si no quedan órdenes pendientes, desactivar throttling
        if not self.pending_orders:
            self.throttle_active = False
            self.throttle_expiration = None

# Llamar la limpieza periódicamente (en on_message):
def on_message(ws, message):
    try:
        # ... (código existente)
        
        # Limpiar órdenes pendientes antes de procesar nueva vela
        self.clean_pending_orders()
        
        # ... (resto del código)
        
#Modificación en la verificación de posición abierta:
# ... después de enviar la orden

positions = self.get_open_position()
position_opened = False

if self.positionside == "LONG":
    long_amt = float(positions["LONG"].get("positionAmt", 0))
    if long_amt > 0:
        position_opened = True
elif self.positionside == "SHORT":
    short_amt = float(positions["SHORT"].get("positionAmt", 0))
    if short_amt > 0:
        position_opened = True

if position_opened:
    print(f"✅ Posición abierta - Limpiando estado")
    self.position_opened_by_strategy = True
    # Limpiar orden pendiente específica
    if self.symbol in self.pending_orders:
        del self.pending_orders[self.symbol]
    ws.close()
    
""" SuegerenciaS:"""
# Tiempo de cooldown:
# En __init__ ajusta según temporalidad
if interval.endswith('m'):
    minutes = int(interval[:-1])
    self.order_cooldown = max(60, minutes * 60)  # Mínimo 1 minuto
elif interval.endswith('h'):
    self.order_cooldown = int(interval[:-1]) * 3600
    
# Log extendido:
print(f"📊 Estado órdenes: Activas={self.throttle_active}, Expira={self.throttle_expiration}")
print(f"📋 Pendientes: {len(self.pending_orders)}")

# Gestión de errores en set_limit_market_order:
try:
    self.set_limit_market_order(...)
except Exception as e:
    print(f"❌ Error en orden: {e}")
    # Limpiar estado si falla
    if self.symbol in self.pending_orders:
        del self.pending_orders[self.symbol]