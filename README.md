# Ticker de dos monedas con gráficas simultáneas en tiempo real

Aplicación en **Python** que muestra en tiempo real el valor de dos monedas (USD/EUR y USD/JPY) en **gráficas independientes** que se actualizan cada 2 segundos.  
La interfaz gráfica está construida con **PySide6** y **PyQtGraph**, y el sistema usa **concurrencia asíncrona (asyncio)** para que la interfaz nunca se bloquee, incluso cuando se consultan datos en línea.

---

## ✨ Características

- **Actualización en tiempo real** de dos pares de divisas.
- **Botones Pausar/Reanudar** para controlar cada gráfica de forma independiente.
- **Concurrencia asíncrona** con `asyncio` y `aiohttp` para consultas no bloqueantes.
- **Interfaz de escritorio** con PySide6 y gráficos dinámicos con PyQtGraph.
- **API pública gratuita** para obtener datos de Forex.

---

## 📦 Requisitos

Antes de comenzar, instala las dependencias con:

```bash
pip install -r requirements.txt
```

Si no tienes el archivo `requirements.txt`, crea uno con este contenido:

```
PySide6
pyqtgraph
qasync
aiohttp
```

---

## 🚀 Ejecución

1. Clona el repositorio:

```bash
git clone https://github.com/TU_USUARIO/Ticker-de-dos-monedas-con-graficas-simultaneas-en-tiempo-real.git
cd Ticker-de-dos-monedas-con-graficas-simultaneas-en-tiempo-real
```

2. Instala las dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecuta la aplicación:

```bash
python app.py
```

---

## 🖼 Capturas de pantalla

*(Agrega aquí imágenes del programa en ejecución)*

---

## 🛠 Tecnologías utilizadas

- [Python 3.10+](https://www.python.org/)
- [PySide6](https://pypi.org/project/PySide6/)
- [PyQtGraph](https://www.pyqtgraph.org/)
- [qasync](https://pypi.org/project/qasync/)
- [aiohttp](https://docs.aiohttp.org/en/stable/)

---

## 📈 Próximas mejoras

- Soporte para **WebSockets** con datos en tiempo real para criptomonedas.
- Agregar **tercer gráfica** para ratio o spread entre divisas.
- Exportar datos a **CSV** para análisis posterior.

---

## 👨‍💻 Autor

Desarrollado por **Salvador Zeledón** como proyecto académico de programación concurrente y visualización en tiempo real.
