# Historical README snapshot

Preserved before the repository layout cleanup on 2026-10-23.
This is historical evidence; use the current root README for entry points.

# GTA SA OC — port experimental a WebAssembly

**[Galavic](https://github.com/Galavic) — principal contribuidor y responsable de GTA SA OC.**

Investigación para ejecutar el código original de GTA San Andreas de PC en
el navegador, conservando su lógica, misiones, animaciones, física y audio.

**Estado: el usuario confirma la partida de la compilación actual en web,
con CJ en la BMX; la captura muestra 18 FPS y se está midiendo el rendimiento.**
No hay una conversión completa ni una versión 1:1 verificada.

## Recreación Three.js

Se continuó el prototipo local con **El regreso**: montar una BMX, seguir
marcadores hacia Grove Street y llegar a casa. Incluye guardado y reinicio.
Es un objetivo independiente, no la primera misión original completa.
La carga de recursos y el recorrido pasan pruebas en CPU; la partida
interactiva en navegador todavía está pendiente de comprobar.
Consulta [preparación y controles](../../web/recreation/README.md).

Con los recursos locales ya preparados:

```powershell
npm --prefix web/recreation start
```

## Avance comprobado

La tabla conserva resultados históricos del análisis inicial del 14 de
octubre. La variante reconciliada se regeneró el 22 de octubre de 2026;
su Wasm pasa V8 y coincide con el entregado por HTTP. Falta repetir la
partida en navegador con ese artefacto; véase [el estado actual](../STATUS.md).

| Comprobación | Resultado |
| --- | --- |
| Análisis inicial de Ghidra | 20.823 funciones, 1.230.152 instrucciones exportadas |
| Traducción estricta inicial (14 de octubre) | 10 funciones fallidas en esa pasada |
| Traducción estricta de la variante reconciliada (22 de octubre) | Cero fallos reportados; no verifica gameplay |
| Referencias de llamada/salto sin destino (14 de octubre) | 147 en esa pasada histórica |
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
encima de los parches históricos parciales. Véase [patches/README.md](../../patches/README.md).

La compilación del juego requiere además Emscripten, CMake, Ninja, Ghidra,
un JDK compatible y los análisis privados regenerados a partir de la imagen
correcta. Los scripts rechazan hashes distintos. No hay todavía un comando
que produzca un GTA jugable verificado desde una instalación cualquiera.

La variante actual se prepara con `tools/prepare_singleplayer.py`; `GTASA_GAME_DIR`
permite indicar la instalación local. `tools/resume_singleplayer.py` reutiliza el
análisis existente. `tools/finish_singleplayer_pipeline.py` solo continúa a la
compilación si pasa la traducción estricta y coinciden los módulos de audio.

## Documentación

La configuración y los análisis bajo `variants/` son privados y están
excluidos de Git. Un `git pull` actualiza el runtime, pero no incorpora por sí
solo sus contratos de llamadas ni los puntos de entrada observados. Con la
variante y sus análisis ya preparados, reconstruir estos datos antes de
regenerar el código:

```powershell
.venv/Scripts/python.exe tools/audit_allbytes_call_thunks.py --game-dir variants/singleplayer
.venv/Scripts/python.exe tools/apply_call_thunk_contracts.py --game-dir variants/singleplayer --entries-file config/singleplayer-entry-points.json
```

La auditoría comprueba las formas completas sobre los bytes originales; la
aplicación comprueba el hash del ejecutable y conserva una copia de los dos
archivos de configuración anteriores. El archivo de entradas contiene solo
metadatos escritos a mano para la imagen verificada. Después se ejecuta el
build web con `--regenerate` y se valida el Wasm con
`tools/prepare_browser_wasm.py --game-dir variants/singleplayer`. Las comprobaciones
de traducción y compilación no sustituyen la prueba en navegador.

- [Estado actual y próximos bloqueos](../STATUS.md)
- [Datos de avance](../progress.json)
- [Registro histórico, con resultados de otras imágenes](../HISTORY.md)
- [Diagnósticos anteriores del navegador](BROWSER_STATUS.md)
- [Dependencias y atribución](../../THIRD_PARTY.md)

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
# Local launcher screen

The local server restores the launcher from `tools/web/launcher/` when it starts.
After a web rebuild, run `python -c "from tools.serve_variant import stage_launcher; stage_launcher()"`
to restore that screen without restarting the server or touching the Wasm build.
Existing optional background images in the generated site are kept locally;
the user-selected PNG logo is staged from its private cache. Status checks offer a retry after an error
without requiring another import.

The menu lettering uses the prepared installation's `models/fonts.txd` and
`data/fonts.dat`. With Node available, launcher staging exports those locally to
the ignored site's `original-menu/` directory. Only the exporter and renderer
belong in Git; the decoded font rasters and metrics remain private local assets.

Prepare the selected launcher logo locally with `python tools/prepare_launcher_logo.py`,
then restore the launcher with `stage_launcher()` as described above. The PNG stays under ignored `build/`.

The launcher generates its private CSS font with FontTools. Install the helper dependency with
`python -m pip install -r tools/web/launcher/requirements.txt` before staging. This applies the
local menu glyphs to all launcher text, including paragraphs and live status messages.
