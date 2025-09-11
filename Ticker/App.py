import sys
import asyncio
from collections import deque
from datetime import datetime, timezone

from typing import Deque, Dict, Tuple

import aiohttp
from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
from qasync import QEventLoop, asyncSlot

# ---- Recomendado en Windows para compatibilidad con qasync/aiohttp ----
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass


# --------- Config ----------
POLL_INTERVAL_SEC = 2
BUFFER_POINTS = 300  # ~10 min si actualizas cada 2 s
PAIRS = [
    ("USD", "EUR"),
    ("USD", "JPY"),
]

# --------- Estado en memoria ----------
class SeriesState:
    def __init__(self, label: str, color: str = None):
        self.label = label
        self.ts: Deque[float] = deque(maxlen=BUFFER_POINTS)
        self.values: Deque[float] = deque(maxlen=BUFFER_POINTS)
        self.paused = False
        self.color = color

SERIES: Dict[Tuple[str, str], SeriesState] = {
    pair: SeriesState(label=f"{pair[0]}/{pair[1]}")
    for pair in PAIRS
}

# --------- Networking ----------
def build_url_convert(base: str, quote: str) -> str:
    # Endpoint con clave 'result'
    return f"https://api.exchangerate.host/convert?from={base}&to={quote}"

def build_url_frankfurter(base: str, quote: str) -> str:
    # Fallback con clave 'rates'
    return f"https://api.frankfurter.app/latest?from={base}&to={quote}"

async def fetch_rate(session: aiohttp.ClientSession, base: str, quote: str) -> float:
    # 1) Intento: exchangerate.host/convert  -> data['result']
    try:
        url = build_url_convert(base, quote)
        async with session.get(url, timeout=10) as r:
            r.raise_for_status()
            # content_type=None por si el server manda content-type raro
            data = await r.json(content_type=None)
            if isinstance(data, dict) and "result" in data and data["result"] is not None:
                return float(data["result"])
            # si llegó pero sin 'result', forzamos except para fallback
            raise KeyError("result")
    except Exception as e1:
        # 2) Fallback: frankfurter.app/latest -> data['rates'][quote]
        try:
            url = build_url_frankfurter(base, quote)
            async with session.get(url, timeout=10) as r:
                r.raise_for_status()
                data = await r.json(content_type=None)
                if isinstance(data, dict) and "rates" in data and quote in data["rates"]:
                    return float(data["rates"][quote])
                raise KeyError("rates/quote")
        except Exception as e2:
            # Re-lanzamos con un mensaje útil para ver qué devolvió el server
            snippet = ""
            try:
                snippet = str(data)[:200]  # lo que alcanzamos a ver
            except Exception:
                pass
            raise RuntimeError(
                f"Respuesta inesperada para {base}/{quote}. "
                f"Primario: {type(e1).__name__}, Fallback: {type(e2).__name__}. "
                f"Snippet: {snippet}"
            )


async def poll_symbol(pair: tuple[str, str]):
    base, quote = pair
    state = SERIES[pair]
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                if not state.paused:
                    price = await fetch_rate(session, base, quote)
                    
                    # Nueva forma recomendada para timestamps en UTC
                    now = datetime.now(timezone.utc).timestamp()
                    
                    state.ts.append(now)
                    state.values.append(price)
                    print(f"[{base}/{quote}] {price}")
                
                await asyncio.sleep(POLL_INTERVAL_SEC)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WARN] {base}/{quote}: {e}")
                await asyncio.sleep(2)


# --------- UI ----------
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ticker USD/EUR y USD/JPY (async, 2s)")
        self.resize(900, 600)

        self.plot1 = pg.PlotWidget(title="USD/EUR")
        self.plot2 = pg.PlotWidget(title="USD/JPY")
        for p in (self.plot1, self.plot2):
            p.showGrid(x=True, y=True, alpha=0.3)
            p.setLabel("bottom", "Tiempo (UTC)")
            p.setLabel("left", "Precio")

        self.curve1 = self.plot1.plot([], [], pen=pg.mkPen(width=2))
        self.curve2 = self.plot2.plot([], [], pen=pg.mkPen(width=2))

        self.btn_usdeur = QtWidgets.QPushButton("Pausar USD/EUR")
        self.btn_usdjpy = QtWidgets.QPushButton("Pausar USD/JPY")

        self.btn_usdeur.clicked.connect(self.toggle_usdeur)
        self.btn_usdjpy.clicked.connect(self.toggle_usdjpy)

        plots = QtWidgets.QHBoxLayout()
        plots.addWidget(self.plot1, 1)
        plots.addWidget(self.plot2, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.btn_usdeur)
        buttons.addWidget(self.btn_usdjpy)
        buttons.addStretch(1)

        root = QtWidgets.QVBoxLayout(self)
        root.addLayout(plots, 1)
        root.addLayout(buttons)

        # Refresco visual independiente del polling (suave, 1 s)
        self.ui_timer = QtCore.QTimer(self)
        self.ui_timer.setInterval(2000)
        self.ui_timer.timeout.connect(self.redraw)
        self.ui_timer.start()

    @asyncSlot()
    async def toggle_usdeur(self):
        pair = ("USD", "EUR")
        SERIES[pair].paused = not SERIES[pair].paused
        self.btn_usdeur.setText("Reanudar USD/EUR" if SERIES[pair].paused else "Pausar USD/EUR")

    @asyncSlot()
    async def toggle_usdjpy(self):
        pair = ("USD", "JPY")
        SERIES[pair].paused = not SERIES[pair].paused
        self.btn_usdjpy.setText("Reanudar USD/JPY" if SERIES[pair].paused else "Pausar USD/JPY")

    def redraw(self):
        s1 = SERIES[("USD", "EUR")]
        if s1.ts:
            x = list(s1.ts); y = list(s1.values)
            t0 = x[0]; xr = [xi - t0 for xi in x]
            self.curve1.setData(xr, y)

        s2 = SERIES[("USD", "JPY")]
        if s2.ts:
            x = list(s2.ts); y = list(s2.values)
            t0 = x[0]; xr = [xi - t0 for xi in x]
            self.curve2.setData(xr, y)

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Integramos Qt con asyncio
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = MainWindow()
    win.show()

    # >>> CREA LAS TAREAS EN ESTE LOOP <<<
    tasks = [loop.create_task(poll_symbol(pair)) for pair in PAIRS]

    # Cancelar tareas al salir
    def _cleanup():
        for t in tasks:
            t.cancel()

    app.aboutToQuit.connect(_cleanup)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
