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
