import threading
import time
import queue
from datetime import datetime
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button
import matplotlib.animation as animation

INTERVALO_CONSULTA = 2.0   
MAX_PUNTOS = 300            
ACTIVO_A = "BTCUSDT"       
ACTIVO_B = "ETHUSDT"       

cola_a, cola_b = queue.Queue(), queue.Queue()

pausado_a = threading.Event()
pausado_b = threading.Event()
detener_hilos = threading.Event()


def obtener_precio_binance(simbolo: str) -> float:

    url = f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return float(resp.json()['price'])


def hilo_precios(simbolo: str, cola_salida: queue.Queue, evento_pausa: threading.Event):

    while not detener_hilos.is_set():
        if evento_pausa.is_set():
            time.sleep(0.2)
            continue

        momento = datetime.now()

        try:
            precio = obtener_precio_binance(simbolo)
        except Exception as ex:
            print(f"[{simbolo}] Error API: {ex}")
            time.sleep(INTERVALO_CONSULTA)
            continue

        cola_salida.put((momento, precio))

        transcurrido = 0.0
        while transcurrido < INTERVALO_CONSULTA and not detener_hilos.is_set():
            time.sleep(0.1)
            transcurrido += 0.1


def crear_grafico():

    plt.style.use('seaborn-v0_8')
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    fig.suptitle(f"Comparación en vivo: {ACTIVO_A} vs {ACTIVO_B} (cada {INTERVALO_CONSULTA}s)")

    linea_a, = ax1.plot([], [], '-', linewidth=1.2, label=ACTIVO_A)
    ax1.set_ylabel("Precio (USDT)")
    ax1.legend(loc='upper left')
    ax1.grid(True)

    linea_b, = ax2.plot([], [], '-', linewidth=1.2, label=ACTIVO_B)
    ax2.set_ylabel("Precio (USDT)")
    ax2.legend(loc='upper left')
    ax2.grid(True)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    plt.subplots_adjust(bottom=0.18, hspace=0.08)

    return fig, ax1, ax2, linea_a, linea_b


def crear_botones(fig):

    axpausar_a = plt.axes([0.15, 0.05, 0.15, 0.06])
    axreanudar_a = plt.axes([0.32, 0.05, 0.15, 0.06])
    axpausar_b = plt.axes([0.55, 0.05, 0.15, 0.06])
    axreanudar_b = plt.axes([0.72, 0.05, 0.15, 0.06])

    btn_pausar_a = Button(axpausar_a, 'Pausar A')
    btn_reanudar_a = Button(axreanudar_a, 'Reanudar A')
    btn_pausar_b = Button(axpausar_b, 'Pausar B')
    btn_reanudar_b = Button(axreanudar_b, 'Reanudar B')

    btn_pausar_a.on_clicked(lambda e: (pausado_a.set(), print(f"[{ACTIVO_A}] Pausado")))
    btn_reanudar_a.on_clicked(lambda e: (pausado_a.clear(), print(f"[{ACTIVO_A}] Reanudado")))
    btn_pausar_b.on_clicked(lambda e: (pausado_b.set(), print(f"[{ACTIVO_B}] Pausado")))
    btn_reanudar_b.on_clicked(lambda e: (pausado_b.clear(), print(f"[{ACTIVO_B}] Reanudado")))

    return [btn_pausar_a, btn_reanudar_a, btn_pausar_b, btn_reanudar_b]


def iniciar_hilos():
    t_a = threading.Thread(target=hilo_precios, args=(ACTIVO_A, cola_a, pausado_a), daemon=True)
    t_b = threading.Thread(target=hilo_precios, args=(ACTIVO_B, cola_b, pausado_b), daemon=True)
    t_a.start()
    t_b.start()

def principal():
    iniciar_hilos()

    fig, ax1, ax2, linea_a, linea_b = crear_grafico()
    crear_botones(fig)

    tiempos_a, precios_a = [], []
    tiempos_b, precios_b = [], []

    def actualizar(frame):
        nonlocal tiempos_a, precios_a, tiempos_b, precios_b

        while not cola_a.empty():
            ts, precio = cola_a.get_nowait()
            tiempos_a.append(ts)
            precios_a.append(precio)

        while not cola_b.empty():
            ts, precio = cola_b.get_nowait()
            tiempos_b.append(ts)
            precios_b.append(precio)

        tiempos_a, precios_a = tiempos_a[-MAX_PUNTOS:], precios_a[-MAX_PUNTOS:]
        tiempos_b, precios_b = tiempos_b[-MAX_PUNTOS:], precios_b[-MAX_PUNTOS:]

        if tiempos_a:
            linea_a.set_data(mdates.date2num(tiempos_a), precios_a)
            ax1.relim()
            ax1.autoscale_view()

        if tiempos_b:
            linea_b.set_data(mdates.date2num(tiempos_b), precios_b)
            ax2.relim()
            ax2.autoscale_view()

        return linea_a, linea_b
        
    anim = animation.FuncAnimation(fig, actualizar, interval=1000, blit=False, cache_frame_data=False)

    def al_cerrar(evento):
        detener_hilos.set()
        time.sleep(0.2)

    fig.canvas.mpl_connect('close_event', al_cerrar)

    plt.show()


if __name__ == "__main__":
    try:
        principal()
    except KeyboardInterrupt:
        detener_hilos.set()
        print("Interrumpido por usuario.")
