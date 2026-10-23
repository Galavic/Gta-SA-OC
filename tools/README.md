# Herramientas del proyecto

Ejecuta los comandos desde la raiz del repositorio. Los scripts antes sueltos en
la raiz estan ahora en esta carpeta; sus entradas, resultados y directorios de
trabajo permanecen en la raiz. No se han eliminado auditorias ni comprobaciones.

## Flujo de la variante singleplayer

La preparacion completa necesita el runtime parcheado, los SDK y los archivos
locales compatibles. `--help` explica las opciones de cada comando.

| Tarea | Herramienta |
| --- | --- |
| Preparar la copia local y el analisis | `prepare_singleplayer.py` |
| Reanudar traduccion existente | `resume_singleplayer.py` |
| Continuar la compilacion de la variante | `finish_singleplayer_pipeline.py` |
| Verificar y preparar Wasm para navegador | `prepare_browser_wasm.py` |
| Servir el launcher y la variante local | `serve_variant.py` |
| Restaurar la pantalla del launcher | `serve_variant.stage_launcher()` |
| Guardar el parche completo del runtime | `snapshot_runtime_patch.py` |
| Revisar el contenido preparado para publicar | `check_publication.py` |

Para reconciliar contratos y entradas antes de regenerar, cuando ya existen
los analisis privados y la configuracion correspondiente:

```powershell
.venv/Scripts/python.exe tools/audit_allbytes_call_thunks.py --game-dir variants/singleplayer
.venv/Scripts/python.exe tools/apply_call_thunk_contracts.py --game-dir variants/singleplayer
```

Los scripts `build.py`, `analyze.py` y varias auditorias corresponden al flujo
historico de la configuracion de la raiz. Para la variante actual utiliza los
comandos singleplayer y su propio `game.toml`. No mezcles imagenes o hashes.

## Investigacion y diagnostico

| Nombre | Uso |
| --- | --- |
| `audit*.py`, `imports_audit.py` | Auditar bytes, entradas, imports y contratos |
| `curate*.py`, `repair*.py`, `sweep*.py` | Preparar y reconciliar analisis |
| `verify*.py`, `trace*.py`, `probe*.py` | Verificacion y diagnostico |
| `perf*.py`, `benchmark*.py` | Experimentos de rendimiento |
| `*audio*.py`, `prepare_install.ps1` | Herramientas de las pruebas anteriores de audio |
| `web/launcher/` | HTML, CSS, sonidos y generacion local de fuentes del launcher |
| `tests/` | Pruebas de herramientas y reproductor |

Estas herramientas pueden depender de entradas privadas o de una version concreta.
Una auditoria historica no demuestra gameplay ni rendimiento de la compilacion actual.

## Pruebas y publicacion

```powershell
.venv/Scripts/python.exe -m pytest -q tests tools/tests
.venv/Scripts/python.exe tools/check_publication.py
```

El segundo comando revisa el indice de Git; debe ejecutarse antes de publicar.
No incluyas recursos del juego ni artefactos generados. Conserva el gitlink fijado
del runtime y registra sus cambios en `patches/current-vendor.patch`.

El launcher usa recursos extraidos localmente. Instala su dependencia auxiliar
con `python -m pip install -r tools/web/launcher/requirements.txt` si esa pantalla
esta disponible en tu revision. La fuente, el fondo y el audio original permanecen locales.
