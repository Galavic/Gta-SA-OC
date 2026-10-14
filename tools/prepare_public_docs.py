"""Publish status summaries without copying private game inputs or run dumps."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VARIANT = ROOT / "variants/singleplayer"
blockers = json.loads((VARIANT / "build/recomp/translate-report.blockers.json").read_text(encoding="utf-8"))
status = json.loads((VARIANT / "analysis-status.json").read_text(encoding="utf-8"))
failed = len(blockers["failed_functions"])
dangling = len(blockers["dangling_dispatch"])
public = dict(last_translation_run_utc=status["updated_utc"],
              executable_sha256=status["executable_sha256"],
              translation_complete=False, failed_functions=failed,
              dangling_dispatch_references=dangling,
              full_conversion_percentage=None, browser_gameplay_verified=False,
              original_menu_verified=False, original_intro_verified=False,
              first_original_mission_verified=False,
              original_vehicle_physics_verified=False,
              scope="Current isolated executable; prototype rendering and older-image boot probes are separate evidence")
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs/progress.json").write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
(ROOT / "README.md").write_text(f'''# GTA SA OC — port experimental a WebAssembly

**[Galavic](https://github.com/Galavic) — principal contribuidor y responsable de GTA SA OC.**

Investigación para ejecutar el código original de GTA San Andreas de PC en
el navegador, conservando su lógica, misiones, animaciones, física y audio.

**Estado: el motor original todavía no arranca ni es jugable en web.**
No hay una conversión completa ni una versión 1:1 verificada.

## Avance comprobado

Última pasada del ejecutable actual: `{status['updated_utc']}`.

| Comprobación | Resultado |
| --- | --- |
| Análisis inicial de Ghidra | 20.823 funciones, 1.230.152 instrucciones exportadas |
| Traducción estricta completa | Pendiente: {failed} funciones fallidas |
| Referencias de llamada/salto sin destino | {dangling} referencias pendientes |
| Cuatro tablas de salto interpretadas en la imagen equivocada | Auditadas y corregidas como buffers de PE almacenados |
| Pruebas del driver tras mejorar sus diagnósticos | 163 pasan |
| Pruebas de preservación de datos de PE almacenados | 4 pasan |
| Última ejecución de tests del proyecto, driver y SEH | 309 pasan |
| Menú, intro y primera misión del motor original en web | Sin verificar |
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
''', encoding="utf-8")
(ROOT / "docs/STATUS.md").write_text(f'''# Estado actual

Última traducción: `{status['updated_utc']}`.
Imagen actual: `{status['executable_sha256']}`.

El análisis inicial está conservado y no necesita repetirse para la misma
imagen. La última pasada estricta dejó {failed} funciones fallidas y
{dangling} referencias de dispatch sin destino. El supervisor de compilación
se detuvo para revisión; no hay una compilación nueva jugable en marcha.

Se identificaron cinco archivos PE almacenados dentro del ejecutable. Cuatro
tablas de salto que bloqueaban la pasada pertenecían a esas imágenes, no a
la imagen principal. Sus cabeceras, extents y destinos se comprobaron con los
bytes originales. Sus buffers siguen disponibles como datos; si se invocan,
necesitan carga y reubicación separadas, todavía sin comprobar.

El siguiente trabajo examina los prefijos de llamadas que modifican el
retorno y los bytes que Ghidra interpretó tras esas llamadas. Las herramientas
existentes permiten comparar prefijos originales x86 con Wasm antes de
aceptar contratos. Todavía no se ha aplicado esta corrección a la variante.

## Criterios de aceptación pendientes

- Arranque del ejecutable actual con imports y destinos estrictos.
- Menú original renderizado y operable en el navegador.
- Intro y cinemática originales con audio y sincronización.
- Primera misión original, con sus scripts y condiciones reales.
- CJ animado correctamente y control del jugador.
- Vehículos con comportamiento físico original.
- Entrada, audio y guardado verificados durante juego real.

La demo de recursos y las pruebas con host sin gráficos no satisfacen estos
criterios. El conteo de funciones o una compilación Wasm tampoco los satisface.
''', encoding="utf-8")
history = (ROOT / "README.local-before-publication.md").read_text(encoding="utf-8")
history = "# Registro histórico\n\nEstos resultados incluyen otras imágenes y no sustituyen docs/STATUS.md.\n\n" + history
for filename, text in [("docs/HISTORY.md", history), ("PORT_STATUS.md", (ROOT / "PORT_STATUS.md").read_text(encoding="utf-8"))]:
    text = re.sub(r"C:[/\\]Users[/\\]enric[/\\]Projects[/\\]gtasa-web-port", ".", text)
    text = re.sub(r"C:[/\\]Users[/\\]enric[/\\]Downloads[/\\]GTA San Andreas[/\\]GTA San Andreas", "<local-game-install>", text)
    text = re.sub(r"C:[/\\]Users[/\\]enric", "<user-home>", text)
    (ROOT / filename).write_text(text, encoding="utf-8")
print(f"Published status summaries: {failed} failed functions, {dangling} pending references; no conversion percentage asserted.")
