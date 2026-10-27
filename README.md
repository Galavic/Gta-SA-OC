# GTA SA OC

**[Open the web launcher](https://gta.galavic.world/)** - the hosted prepared game files download automatically on first use (about 5 GB).

Port experimental de **GTA San Andreas para navegador**, basado en el motor
original de PC y WebAssembly/WebGPU. Proyecto no oficial de la comunidad.

El usuario ha confirmado el menu y gameplay en compilaciones locales. Las
misiones completas, la equivalencia 1:1 y los 60 FPS estables siguen sin verificar.
Los resultados de cada compilacion y sus hashes estan en [Estado actual](docs/STATUS.md).

## Empezar

```powershell
git clone --recurse-submodules https://github.com/Galavic/Gta-SA-OC.git
cd Gta-SA-OC
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

El runtime lleva una revision fijada y un parche completo. Antes de compilar,
consulta [como aplicar el parche](patches/README.md). Cada persona necesita su
propia copia compatible del juego; este repositorio no incluye el juego ni sus
recursos. La preparacion requiere Emscripten, CMake, Ninja, Ghidra y un JDK.
El proceso completo aun depende de analisis locales; clonar no basta para jugar.

Con la variante y la compilacion local ya preparadas:

```powershell
.venv/Scripts/python.exe tools/serve_variant.py --port 8771
```

Abre **http://127.0.0.1:8771/** e importa los archivos de tu copia local.
Consulta las [herramientas de preparacion y comprobacion](tools/README.md).

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `tools/` | Preparacion, compilacion, servidor, auditorias y launcher |
| `tests/` | Regresiones del proyecto |
| `docs/` | Estado actual, evidencias e historial |
| `docs/archive/` | Informes y guias anteriores, separados del estado actual |
| `patches/` | Parche completo del runtime y licencia preservada |
| `vendor/recomp-kit/` | Dependencia fijada; cambios locales en el parche |
| `config/` | Metadatos de entrada escritos a mano, cuando estan disponibles |
| `web/` | Prototipos anteriores y herramientas compartidas de recursos |
| `deska/` | Panel de escritorio para Deska; no forma parte del runtime |

`build/`, `variants/`, `analysis/`, `original/` y `prepared/` son datos locales
ignorados por Git. No se publican ejecutables, recursos originales, Wasm generado,
volcados privados ni rutas personales.

## Documentacion

- [Estado y limitaciones](docs/STATUS.md)
- [Datos de progreso](docs/progress.json)
- [Panel de Deska](deska/README.md)
- [Herramientas y comandos](tools/README.md)
- [Historial de investigacion](docs/HISTORY.md)
- [Archivo de informes anteriores](docs/archive/README.md)
- [Dependencias y atribucion](THIRD_PARTY.md)

[Contribuidores](https://github.com/Galavic/Gta-SA-OC/graphs/contributors):
[Galavic](https://github.com/Galavic) y la comunidad del proyecto.
No afiliado a Rockstar Games.
