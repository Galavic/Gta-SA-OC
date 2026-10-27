/* San Andreas Web: a desk-side companion for the GTA San Andreas browser port.
 *
 * What this panel does:
 * - Opens the public launcher, the source repository and the current status
 *   document through deska.openUrl, with the person's consent.
 * - Shows a small, dated snapshot of what the project has verified. The
 *   statuses live in index.html and the wording lives in STRINGS below.
 * - Keeps a personal test log in deska.storage. It is explicitly not an
 *   official verification of the port.
 *
 * The panel asks only for open-url and declares no network hosts. It has no
 * timers, so it does no work while hidden.
 */

const PLAY_URL = 'https://gta.galavic.world/'
const REPO_URL = 'https://github.com/Galavic/Gta-SA-OC'
const STATUS_URL = 'https://github.com/Galavic/Gta-SA-OC/blob/main/docs/STATUS.md'
const STORAGE_KEY = 'san-andreas-web'
const STORAGE_VERSION = 1
const NOTE_MS = 4_500

const STRINGS = {
  en: {
    lang: 'en',
    name: 'San Andreas Web',
    eyebrow: 'GTA SA · Browser port',
    subtitle: 'Unofficial community project',
    windowTitle: 'Menu + gameplay local · missions pending',
    play: 'Play in browser',
    hint: 'Opens gta.galavic.world · about 5 GB on first load',
    tabsLabel: 'Panel view',
    tabs: { status: 'Status', checks: 'My checks' },
    statusTitle: 'Project status',
    snapshot: 'Snapshot · Oct 2026',
    status: {
      menu: { label: 'Original menu', detail: 'Confirmed in local builds.' },
      gameplay: { label: 'Browser gameplay', detail: 'Free roam confirmed in local builds.' },
      mission: { label: 'First mission', detail: 'The original mission logic is not verified.' },
      fps: { label: 'Stable 60 FPS', detail: 'Stable 60 FPS is not verified.' },
    },
    chips: { ok: 'Verified', pending: 'Not yet', unknown: 'Unverified' },
    statusNote: 'Verified means confirmed in local builds. No 1:1 or complete-conversion claim.',
    openStatus: 'Open current status →',
    checksTitle: 'My test log',
    checksNote: 'Saved in Deska on this computer. These are your checks, not an official claim.',
    checks: {
      menu: 'Menu and language',
      'free-roam': 'Free roam and driving',
      mission: 'First mission',
      save: 'Save and load',
      audio: 'Audio and radio',
    },
    count: (done, total) => `${done} of ${total}`,
    progressLabel: 'Test log progress',
    clear: 'Clear',
    clearConfirm: 'Clear all?',
    cleared: 'Test log cleared.',
    legal: 'Unofficial community port. Not affiliated with Rockstar Games.',
    source: 'Source',
    waiting: 'Open this panel inside Deska.',
    loadError: 'Could not load saved checks. Starting fresh.',
    saveError: 'Could not save. Changes may not last a reload.',
    openErrors: {
      declined: 'Opening the page was cancelled.',
      not_focused: 'Click the panel first, then try again.',
      rate_limited: 'One page at a time. Try again in a second.',
      permission_denied: 'This panel is not allowed to open links.',
      other: 'Could not open the page.',
    },
  },
  es: {
    lang: 'es',
    name: 'San Andreas Web',
    eyebrow: 'GTA SA · Navegador',
    subtitle: 'Proyecto comunitario no oficial',
    windowTitle: 'Menú + juego local · misiones pendientes',
    play: 'Jugar en el navegador',
    hint: 'Abre gta.galavic.world · ~5 GB la primera vez',
    tabsLabel: 'Vista del panel',
    tabs: { status: 'Estado', checks: 'Mis pruebas' },
    statusTitle: 'Estado del proyecto',
    snapshot: 'Estado · oct. 2026',
    status: {
      menu: { label: 'Menú original', detail: 'Confirmado en compilaciones locales.' },
      gameplay: { label: 'Juego en navegador', detail: 'Juego libre confirmado en compilaciones locales.' },
      mission: { label: 'Primera misión', detail: 'La lógica de la misión original no está verificada.' },
      fps: { label: '60 FPS estables', detail: 'Los 60 FPS estables no están verificados.' },
    },
    chips: { ok: 'Verificado', pending: 'Aún no', unknown: 'Sin verificar' },
    statusNote: 'Verificado significa confirmado en compilaciones locales. Sin afirmar 1:1 ni conversión completa.',
    openStatus: 'Ver estado actual →',
    checksTitle: 'Mis pruebas',
    checksNote: 'Se guarda en Deska, en este equipo. Son tus pruebas, no una afirmación oficial.',
    checks: {
      menu: 'Menú e idioma',
      'free-roam': 'Juego libre y conducción',
      mission: 'Primera misión',
      save: 'Guardar y cargar',
      audio: 'Audio y radio',
    },
    count: (done, total) => `${done} de ${total}`,
    progressLabel: 'Progreso de las pruebas',
    clear: 'Borrar',
    clearConfirm: '¿Borrar todo?',
    cleared: 'Pruebas borradas.',
    legal: 'Port comunitario no oficial. Sin afiliación con Rockstar Games.',
    source: 'Código',
    waiting: 'Abre este panel dentro de Deska.',
    loadError: 'No se pudieron cargar las pruebas guardadas. Se empieza de cero.',
    saveError: 'No se pudo guardar. Los cambios podrían no persistir.',
    openErrors: {
      declined: 'Se canceló la apertura de la página.',
      not_focused: 'Haz clic en el panel y vuelve a intentarlo.',
      rate_limited: 'Una página a la vez. Inténtalo en un segundo.',
      permission_denied: 'Este panel no tiene permiso para abrir enlaces.',
      other: 'No se pudo abrir la página.',
    },
  },
}

const $ = (id) => document.getElementById(id)
const deska = window.deska
const checkInputs = [...document.querySelectorAll('[data-check]')]
const CHECK_IDS = checkInputs.map((input) => input.dataset.check)

const state = {
  view: 'status',
  checks: {},
}

let t = STRINGS.en
let ready = false
let noteTimer = 0
let clearTimer = 0
let clearArmed = false
let saveChain = Promise.resolve()

// Outside Deska, ready() never resolves. Say so instead of waiting forever.
const waitingTimer = setTimeout(() => {
  if (ready) return
  $('waiting').hidden = false
  $('app').setAttribute('aria-busy', 'false')
}, 3_000)

const init = await deska.ready()
ready = true
clearTimeout(waitingTimer)
$('waiting').hidden = true

const locale = String(init.locale || navigator.language || 'en')
t = locale.toLowerCase().startsWith('es') ? STRINGS.es : STRINGS.en

applyCopy()
await loadState()
applyChecks()
setView(state.view, { save: false })
bindEvents()
renderChecksSummary()
$('app').setAttribute('aria-busy', 'false')

deska.setTitle(t.windowTitle).catch(() => {
  // A title is a nicety, not a reason to keep the panel from working.
})

function applyCopy() {
  document.documentElement.lang = t.lang
  document.title = t.name

  $('eyebrow').textContent = t.eyebrow
  $('subtitle').textContent = t.subtitle
  $('play-label').textContent = t.play
  $('hint').textContent = t.hint
  $('tabs').setAttribute('aria-label', t.tabsLabel)
  $('tab-status').textContent = t.tabs.status
  $('tab-checks').textContent = t.tabs.checks
  $('status-title').textContent = t.statusTitle
  $('snapshot').textContent = t.snapshot
  $('status-note').textContent = t.statusNote
  $('open-status').textContent = t.openStatus
  $('checks-title').textContent = t.checksTitle
  $('checks-note').textContent = t.checksNote
  $('progress').setAttribute('aria-label', t.progressLabel)
  $('clear').textContent = t.clear
  $('legal').textContent = t.legal
  $('open-source').textContent = t.source
  $('waiting').textContent = t.waiting

  for (const row of document.querySelectorAll('[data-status]')) {
    const id = row.dataset.status
    const info = t.status[id]
    const chip = row.querySelector('.chip')
    if (!info || !chip) continue
    row.querySelector('.status-label').textContent = info.label
    chip.textContent = t.chips[chip.dataset.tone] || chip.textContent
    row.title = info.detail
    row.setAttribute('aria-label', `${info.label}: ${chip.textContent}`)
  }

  for (const input of checkInputs) {
    const label = input.closest('label')?.querySelector('span')
    if (label) label.textContent = t.checks[input.dataset.check] || label.textContent
  }
}

// --- Saved state -----------------------------------------------------------

async function loadState() {
  let saved = null
  try {
    saved = await deska.storage.get(STORAGE_KEY)
  } catch (err) {
    showNote(t.loadError, true)
    return
  }
  if (!saved || typeof saved !== 'object') return
  if (saved.v !== STORAGE_VERSION) return

  if (saved.view === 'checks' || saved.view === 'status') state.view = saved.view
  if (saved.checks && typeof saved.checks === 'object') {
    for (const id of CHECK_IDS) state.checks[id] = saved.checks[id] === true
  }
}

function saveState() {
  const snapshot = {
    v: STORAGE_VERSION,
    view: state.view,
    checks: Object.fromEntries(CHECK_IDS.filter((id) => state.checks[id]).map((id) => [id, true])),
  }
  saveChain = saveChain.then(async () => {
    try {
      await deska.storage.set(STORAGE_KEY, snapshot)
    } catch (err) {
      showNote(t.saveError, true)
    }
  })
  return saveChain
}

// --- Rendering -------------------------------------------------------------

function applyChecks() {
  for (const input of checkInputs) {
    input.checked = Boolean(state.checks[input.dataset.check])
  }
}

function renderChecksSummary() {
  const done = CHECK_IDS.filter((id) => state.checks[id]).length
  const total = CHECK_IDS.length
  const bar = $('progress')
  bar.setAttribute('aria-valuenow', String(done))
  bar.setAttribute('aria-valuetext', t.count(done, total))
  $('progress-fill').style.transform = `scaleX(${total ? done / total : 0})`
  $('check-count').textContent = t.count(done, total)
}

function showNote(text, isError = false) {
  const line = $('status')
  line.textContent = text
  line.classList.toggle('is-error', isError)
  clearTimeout(noteTimer)
  noteTimer = setTimeout(() => {
    line.textContent = ''
    line.classList.remove('is-error')
  }, NOTE_MS)
}

// --- Tabs ------------------------------------------------------------------

function setView(view, { focus = false, save = true } = {}) {
  if (save) disarmClear()
  state.view = view === 'checks' ? 'checks' : 'status'
  const checks = state.view === 'checks'
  $('view-status').hidden = checks
  $('view-checks').hidden = !checks
  $('tab-status').setAttribute('aria-selected', String(!checks))
  $('tab-checks').setAttribute('aria-selected', String(checks))
  $('tab-status').tabIndex = checks ? -1 : 0
  $('tab-checks').tabIndex = checks ? 0 : -1
  if (checks) renderChecksSummary()
  if (focus) $(checks ? 'tab-checks' : 'tab-status').focus()
  if (save) saveState()
}

function bindEvents() {
  $('play').addEventListener('click', () => openExternal(PLAY_URL))
  $('open-status').addEventListener('click', () => openExternal(STATUS_URL))
  $('open-source').addEventListener('click', () => openExternal(REPO_URL))

  $('tab-status').addEventListener('click', () => setView('status'))
  $('tab-checks').addEventListener('click', () => setView('checks'))
  $('tabs').addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    if (event.key === 'Home') setView('status', { focus: true })
    else if (event.key === 'End') setView('checks', { focus: true })
    else setView(state.view === 'status' ? 'checks' : 'status', { focus: true })
  })

  for (const input of checkInputs) {
    input.addEventListener('change', () => {
      const id = input.dataset.check
      if (input.checked) state.checks[id] = true
      else delete state.checks[id]
      renderChecksSummary()
      saveState()
    })
  }

  $('clear').addEventListener('click', onClear)
}

function onClear() {
  if (!clearArmed) {
    clearArmed = true
    $('clear').classList.add('is-armed')
    $('clear').textContent = t.clearConfirm
    clearTimer = setTimeout(disarmClear, 3_000)
    return
  }

  state.checks = {}
  applyChecks()
  renderChecksSummary()
  saveState()
  disarmClear()
  showNote(t.cleared)
}

function disarmClear() {
  clearTimeout(clearTimer)
  clearArmed = false
  $('clear').classList.remove('is-armed')
  $('clear').textContent = t.clear
}

// --- Links -----------------------------------------------------------------

async function openExternal(url) {
  try {
    // openUrl needs `open-url`, works from a click while this frame has focus,
    // and Deska asks the person for consent the first time for each host.
    await deska.openUrl(url)
  } catch (err) {
    showNote(t.openErrors[err.code] || t.openErrors.other, true)
  }
}
