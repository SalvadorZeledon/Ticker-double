"""
Proyecto Final – Dual Ticker (Qt + pyqtgraph, Binance)
-----------------------------------------------------
Este script muestra en **una sola ventana** dos gráficos en vivo con los precios de
2 activos de Binance (por defecto, BTCUSDT y ETHUSDT). La idea es que el equipo
pueda **estudiar y defender** el proyecto leyendo comentarios simples, sin mucho
tecnicismo.

Resumen rápido de cómo funciona:
1) La interfaz (ventana y gráficos) se hace con **Qt** (PySide6) y **pyqtgraph**.
2) Creamos **dos tareas asíncronas** (una por activo) que consultan el precio
   cada N segundos (2s) usando **aiohttp**.
3) Cada tarea guarda los puntos en memoria (tiempo + precio). La ventana tiene
   un temporizador para **redibujar** la pantalla cada 2s sin trabarse.
4) Hay un **botón por activo** para pausar/reanudar su actualización sin afectar
   al otro.
5) Si la red falla, esperamos un poco y volvemos a intentar (con una espera que
   crece hasta un límite). Al cerrar la ventana se cancelan bien las tareas.
"""

import sys
import time  # usado para calcular el desfase horario local si queremos ver hora local
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List

import aiohttp
from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
from qasync import QEventLoop

# ===============================
# Compatibilidad con Windows
# -------------------------------
# En algunas PCs con Windows, qasync funciona mejor con esta política
# de loop. Si no aplica, no pasa nada.
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# ===============================
# Parámetros editables (cambien aquí)
# -------------------------------
POLL_INTERVAL_SEC = 2                        # Cada cuánto pedimos precio a Binance
BUFFER_POINTS = 300                          # Cuántos puntos guardamos (para no gastar memoria)
SYMBOLS: List[str] = ["BTCUSDT", "ETHUSDT"]  # Activos a mostrar
REQUEST_TIMEOUT = 10                         # Tiempo máx. de espera en la petición HTTP (seg)

# Endpoint público de Binance para precio spot de un símbolo
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
HEADERS = {"User-Agent": "DualTickerQt/1.0"}

# ===============================
# Estructura simple para guardar datos de cada serie
# -------------------------------
class SeriesState:
    """Guarda el estado de un activo: sus puntos y si está pausado."""
    def __init__(self, symbol: str):
        self.symbol = symbol
        # Guardamos el tiempo como "epoch" (segundos desde 1970) en UTC.
        # Deque con límite: cuando se llena, lo más antiguo se descarta solo.
        self.ts: Deque[float] = deque(maxlen=BUFFER_POINTS)
        self.values: Deque[float] = deque(maxlen=BUFFER_POINTS)
        self.paused: bool = False  # si está en True, esa serie no agrega nuevos puntos

# Un diccionario: símbolo -> estado
SERIES: Dict[str, SeriesState] = {s: SeriesState(s) for s in SYMBOLS}

# ===============================
# Pedir precio a Binance
# -------------------------------
async def fetch_price(session: aiohttp.ClientSession, symbol: str) -> float:
    """Consulta el precio spot en Binance para un símbolo (p.ej., BTCUSDT).

    De Binance esperamos algo como: {"symbol": "BTCUSDT", "price": "109345.12"}
    Devolvemos el precio como número (float).
    """
    url = BINANCE_URL.format(symbol=symbol)
    async with session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT) as r:
        r.raise_for_status()                 # si hay error HTTP, lanza excepción
        data = await r.json(content_type=None)
        return float(data["price"])         # si falta la clave, lanza KeyError (nos avisa)


async def poll_symbol(symbol: str, stop_event: asyncio.Event):
    """Bucle que corre "para siempre" (hasta que se cierre la app).

    - Si la serie NO está pausada, pide el precio, lo guarda con su tiempo.
    - Espera POLL_INTERVAL_SEC y repite.
    - Si algo falla (red, etc.), espera un poco y lo intenta de nuevo con
      una espera que crece hasta 10s como máximo (backoff).
    """
    state = SERIES[symbol]
    async with aiohttp.ClientSession() as session:
        next_delay = POLL_INTERVAL_SEC  # tiempo de espera en caso de error (empieza bajito)
        while not stop_event.is_set():
            try:
                if not state.paused:
                    price = await fetch_price(session, symbol)
                    # Guardamos el instante actual en UTC (hora mundial)
                    now = datetime.now(timezone.utc).timestamp()
                    state.ts.append(now)
                    state.values.append(price)
                # Esperamos el siguiente ciclo manteniendo el ritmo
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SEC)
                next_delay = POLL_INTERVAL_SEC  # si todo fue bien, reseteamos el backoff
            except asyncio.TimeoutError:
                # Timeout del wait_for: significa que terminó el período normal de espera
                # y seguimos al próximo ciclo.
                continue
            except asyncio.CancelledError:
                # Al cerrar la app cancelamos esta tarea: salimos del bucle.
                break
            except Exception as e:
                # Si hay un problema (por ejemplo, internet se cae), no rompemos la app.
                # Mostramos un aviso y volvemos a intentar con una espera un poco mayor.
                print(f"[WARN] {symbol}: {e}")
                await asyncio.sleep(min(10, next_delay))
                next_delay = min(10, next_delay * 2)  # la espera crece hasta 10s

# ===============================
# Ventana principal (Qt + pyqtgraph)
# -------------------------------
class MainWindow(QtWidgets.QWidget):
    def __init__(self, stop_event: asyncio.Event):
        super().__init__()
        self.stop_event = stop_event

        # Título de la ventana (se puede cambiar libremente)
        self.setWindowTitle("Ticker Dual – Proyecto Arquitectura de computadoras")
        self.resize(1000, 620)

        # --- Ejes de tiempo ---
        # Por defecto usábamos UTC (utcOffset=0). Si prefieren ver **hora local** en el eje,
        # se puede calcular el desfase así:
        #   local_offset = -time.timezone
        # y usarlo abajo. Si prefieren seguir con UTC, dejen utcOffset=0.
        # OJO: time.timezone no considera horario de verano. Para exactitud total
        # pueden seguir en UTC.
        local_offset = -time.timezone  # segundos respecto a UTC
        date_axis_left = pg.DateAxisItem(orientation="bottom", utcOffset=local_offset)
        date_axis_right = pg.DateAxisItem(orientation="bottom", utcOffset=local_offset)


        # Dos gráficos: uno para cada símbolo
        self.plot_left = pg.PlotWidget(title=SYMBOLS[0], axisItems={"bottom": date_axis_left})
        self.plot_right = pg.PlotWidget(title=SYMBOLS[1], axisItems={"bottom": date_axis_right})
        for p in (self.plot_left, self.plot_right):
            p.showGrid(x=True, y=True, alpha=0.3)     # rejilla suave para leer mejor
            p.setLabel("left", "Precio (USDT)")
            p.setLabel("bottom", "Tiempo (UTC)")    # si usan local_offset, pueden cambiar el texto

        # Las curvas que vamos a ir actualizando
        self.curve_left = self.plot_left.plot([], [], pen=pg.mkPen(width=2))
        self.curve_right = self.plot_right.plot([], [], pen=pg.mkPen(width=2))

        # Botones: un toggle por activo (cambia entre Pausar/Reanudar)
        self.btn_left = QtWidgets.QPushButton(f"Pausar {SYMBOLS[0]}")
        self.btn_right = QtWidgets.QPushButton(f"Pausar {SYMBOLS[1]}")
        self.btn_left.clicked.connect(self.toggle_left)
        self.btn_right.clicked.connect(self.toggle_right)

        # Armamos el layout (dos gráficos arriba, botones abajo)
        plots = QtWidgets.QHBoxLayout()
        plots.addWidget(self.plot_left, 1)
        plots.addWidget(self.plot_right, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.btn_left)
        buttons.addWidget(self.btn_right)
        buttons.addStretch(1)  # empuja los botones a la izquierda

        root = QtWidgets.QVBoxLayout(self)
        root.addLayout(plots, 1)
        root.addLayout(buttons)

        # Temporizador de la **interfaz**: cada 2s redibuja con los últimos datos.
        # Esto NO bloquea la ventana. Es independiente del polling.
        self.ui_timer = QtCore.QTimer(self)
        self.ui_timer.setInterval(int(POLL_INTERVAL_SEC * 1000))
        self.ui_timer.timeout.connect(self.redraw)
        self.ui_timer.start()

    # Cambia el estado de la serie izquierda (pausa/activa)
    def toggle_left(self):
        s = SERIES[SYMBOLS[0]]
        s.paused = not s.paused
        self.btn_left.setText(("Reanudar " if s.paused else "Pausar ") + SYMBOLS[0])

    # Cambia el estado de la serie derecha (pausa/activa)
    def toggle_right(self):
        s = SERIES[SYMBOLS[1]]
        s.paused = not s.paused
        self.btn_right.setText(("Reanudar " if s.paused else "Pausar ") + SYMBOLS[1])

    # Dibuja los puntos más recientes en pantalla
    def redraw(self):
        left = SERIES[SYMBOLS[0]]
        if left.ts:
            self.curve_left.setData(list(left.ts), list(left.values))

        right = SERIES[SYMBOLS[1]]
        if right.ts:
            self.curve_right.setData(list(right.ts), list(right.values))

# ===============================
# Puesta en marcha
# -------------------------------

def main():
    # Creamos la app de Qt
    app = QtWidgets.QApplication(sys.argv)

    # Integramos Qt con asyncio (qasync): un solo loop para todo
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Evento para avisar a las tareas que hay que parar (cuando cerramos la app)
    stop_event = asyncio.Event()

    # Ventana principal
    win = MainWindow(stop_event)
    win.show()

    # Creamos una tarea de polling por símbolo (BTCUSDT, ETHUSDT, ...)
    tasks = [loop.create_task(poll_symbol(symbol, stop_event)) for symbol in SYMBOLS]

    # Al cerrar la app: avisamos a las tareas y las cancelamos
    def _cleanup():
        stop_event.set()
        for t in tasks:
            t.cancel()

    app.aboutToQuit.connect(_cleanup)

    # Arrancamos el loop y nos quedamos aquí hasta cerrar la ventana
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
