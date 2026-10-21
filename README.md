# GTA SA OC — port experimental a WebAssembly

**[Galavic](https://github.com/Galavic) — principal contribuidor y responsable de GTA SA OC.**

Investigación para ejecutar el código original de GTA San Andreas de PC en
el navegador, conservando su lógica, misiones, animaciones, física y audio.

**Estado: el motor original todavía no arranca ni es jugable en web.**
No hay una conversión completa ni una versión 1:1 verificada.

## Recreación Three.js

Se continuó el prototipo local con **El regreso**: montar una BMX, seguir
marcadores hacia Grove Street y llegar a casa. Incluye guardado y reinicio.
Es un objetivo independiente, no la primera misión original completa.
La carga de recursos y el recorrido pasan pruebas en CPU; la partida
interactiva en navegador todavía está pendiente de comprobar.
Consulta [preparación y controles](web/recreation/README.md).

Con los recursos locales ya preparados:

```powershell
npm --prefix web/recreation start
```

## Avance comprobado

Última pasada del ejecutable actual: `2026-10-14T03:31:06.407545+00:00`.

| Comprobación | Resultado |
| --- | --- |
| Análisis inicial de Ghidra | 20.823 funciones, 1.230.152 instrucciones exportadas |
| Traducción estricta completa | Pendiente: 10 funciones fallidas |
| Referencias de llamada/salto sin destino | 147 referencias pendientes |
| Cuatro tablas de salto interpretadas en la imagen equivocada | Auditadas y corregidas como buffers de PE almacenados |
| Pruebas del driver tras mejorar sus diagnósticos | 163 pasan |
| Pruebas de preservación de datos de PE almacenados | 4 pasan |
| Última ejecución de tests del proyecto, driver y SEH | 309 pasan |
| Menú, intro y gameplay del motor original en web | Verificado: menú, intro y CJ caminando por Los Santos (`docs/STATUS.md`); misiones sin verificar |
| Física original de vehículos en web | Sin verificar |

No publicamos un porcentaje de conversión completa: el número de funciones
exportadas, descubiertas o compiladas no mide cuánto del juego funciona.
Tampoco es comparable con el porcentaje de ingeniería inversa manual de
otros proyectos. Los resultados históricos de otro ejecutable y de la demo
que carga recursos se documentan por separado.

## Qué contiene este repositorio

- Herramientas de análisis, auditoría de bytes y preparación de entradas.
- Herramientas de traducción, compilación y diagnóstico de arranque.
- Pruebas de semántica x86/Wasm y de contratos de control de flujo.
- Una revisión fijada de `recomp-kit` y el parche acumulado del runtime.
- Documentación del avance, limitaciones e investigaciones anteriores.

Los ejecutables, DLL del juego, recursos, disassemblies, traducciones
generadas, volcados de memoria y binarios Wasm permanecen locales y excluidos
de Git. Cada persona necesita sus propios archivos compatibles del juego.

## Preparación del código

```powershell
git clone --recurse-submodules https://github.com/Galavic/Gta-SA-OC.git
cd Gta-SA-OC
git -C vendor/recomp-kit apply --check ../../patches/current-vendor.patch
git -C vendor/recomp-kit apply ../../patches/current-vendor.patch
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest -q tests vendor/recomp-kit/tools/recomp/tests/test_translate_driver.py vendor/recomp-kit/tools/recomp/tests/test_translate_seh.py
```

El parche se aplica una sola vez sobre la revisión fijada; no se aplica
encima de los parches históricos parciales. Véase [patches/README.md](patches/README.md).

La compilación del juego requiere además Emscripten, CMake, Ninja, Ghidra,
un JDK compatible y los análisis privados regenerados a partir de la imagen
correcta. Los scripts rechazan hashes distintos. No hay todavía un comando
que produzca un GTA jugable verificado desde una instalación cualquiera.

La variante actual se prepara con `prepare_singleplayer.py`; `GTASA_GAME_DIR`
permite indicar la instalación local. `resume_singleplayer.py` reutiliza el
análisis existente. `finish_singleplayer_pipeline.py` solo continúa a la
compilación si pasa la traducción estricta y coinciden los módulos de audio.

## Documentación

- [Estado actual y próximos bloqueos](docs/STATUS.md)
- [Datos de avance](docs/progress.json)
- [Registro histórico, con resultados de otras imágenes](docs/HISTORY.md)
- [Diagnósticos anteriores del navegador](BROWSER_STATUS.md)
- [Dependencias y atribución](THIRD_PARTY.md)

## Proyectos relacionados

[gta-reversed](https://github.com/gta-reversed/gta-reversed) reconstruye
funciones originales en C++ y es una referencia útil. Actualmente genera
una DLL que depende del ejecutable original; no equivale a una versión
independiente completa lista para Wasm.

[SanAndreasUnity](https://github.com/in0finite/SanAndreasUnity) es una
reimplementación incompleta en Unity. Se estudió como alternativa, pero no
demuestra equivalencia 1:1 con la historia y la física originales.

Este proyecto no está afiliado con Rockstar Games ni anuncia una conversión
completa o la primera conversión completa del juego.
