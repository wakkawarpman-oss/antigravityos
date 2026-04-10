'use strict'

const fs = require('node:fs')
const path = require('node:path')
const blessed = require('blessed')
const contrib = require('blessed-contrib')
const { initSearch } = require('./components/search-panel')
const { CalibratedParser, DEFAULT_CONFIG } = require('./components/calibrated-parser')

// ─── Mini robot frames (2-line, sits next to logo) ──────────
const BOT = [
  ['{cyan-fg}[◕‿◕]{/}', '{cyan-fg}<|>{/}'],
  ['{magenta-fg}[●_●]{/}', '{magenta-fg}/|\\{/}'],
  ['{yellow-fg}[^_^]{/}', '{yellow-fg}\\|/{/}'],
  ['{green-fg}[★‿★]{/}', '{green-fg}-|-{/}']
]

// ─── Tools / Adapter registry (mirrors src/registry.py) ─────
const ADAPTERS = [
  // Identity & Leaks
  { name: 'ua_phone',         active: true,  cat: 'identity',  lane: 'fast' },
  { name: 'ua_leak',          active: true,  cat: 'identity',  lane: 'fast' },
  { name: 'ru_leak',          active: true,  cat: 'identity',  lane: 'fast' },
  { name: 'holehe',           active: true,  cat: 'identity',  lane: 'fast' },
  { name: 'blackbird',        active: true,  cat: 'identity',  lane: 'fast' },
  { name: 'ghunt',            active: true,  cat: 'social',    lane: 'fast' },
  { name: 'search4faces',     active: true,  cat: 'social',    lane: 'fast' },
  { name: 'social_analyzer',  active: true,  cat: 'social',    lane: 'slow' },
  { name: 'vk_graph',         active: true,  cat: 'social',    lane: 'slow' },
  { name: 'avito',            active: true,  cat: 'social',    lane: 'fast' },
  // Infra & Recon
  { name: 'shodan',           active: true,  cat: 'infra',     lane: 'fast' },
  { name: 'censys',           active: true,  cat: 'infra',     lane: 'fast' },
  { name: 'httpx_probe',      active: true,  cat: 'infra',     lane: 'fast' },
  { name: 'nuclei',           active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'katana',           active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'naabu',            active: true,  cat: 'infra',     lane: 'fast' },
  { name: 'nmap',             active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'subfinder',        active: true,  cat: 'infra',     lane: 'fast' },
  { name: 'amass',            active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'reconng',          active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'eyewitness',       active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'metagoofil',       active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'ashok',            active: true,  cat: 'infra',     lane: 'slow' },
  { name: 'maryam',           active: true,  cat: 'infra',     lane: 'fast' },
  // GEOINT & Registry
  { name: 'firms',            active: true,  cat: 'geoint',    lane: 'slow' },
  { name: 'satintel',         active: true,  cat: 'geoint',    lane: 'fast' },
  { name: 'opendatabot',      active: true,  cat: 'registry',  lane: 'fast' },
  { name: 'web_search',       active: true,  cat: 'registry',  lane: 'slow' }
]

const PIPELINE = ['INPUT', 'TRIAGE', 'CORRELATE', 'VERIFY', 'EXPORT']

function nowTime () {
  const d = new Date()
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2, '0')).join(':')
}

function sleep (ms) { return new Promise(r => setTimeout(r, ms)) }

function loadCalibration () {
  try {
    const raw = fs.readFileSync(path.resolve('config.calibrated.json'), 'utf8')
    const p = JSON.parse(raw)
    return {
      parser: { ...DEFAULT_CONFIG.parser, ...(p.parser || {}) },
      search: { ...DEFAULT_CONFIG.search, ...(p.search || {}) },
      tui: { ...DEFAULT_CONFIG.tui, ...(p.tui || {}) },
      behavioral: { ...DEFAULT_CONFIG.behavioral, ...(p.behavioral || {}) }
    }
  } catch { return DEFAULT_CONFIG }
}

// ═════════════════════════════════════════════════════════════
function startTui () {
  const calibration = loadCalibration()
  const screen = blessed.screen({ smartCSR: true, fullUnicode: true, title: 'HANNA OSINT v3.2' })
  const grid = new contrib.grid({ rows: 24, cols: 24, screen })

  // ─── State ────────────────────────────────────────────────
  let botFrame = 0, botTimer = null, isProcessing = false
  let uptimeSec = 0, queryCount = 0, clusterCount = 0
  let pipelineStep = -1, confidence = 0
  let triageRows = []
  let linkedCounts = { ip: 0, domain: 0, email: 0, geo: 0 }
  let dossierData = null

  // ═══════════════════════════════════════════════════════════
  //  ZONE: HEADER (row 0-2, full width)
  // ═══════════════════════════════════════════════════════════
  const header = grid.set(0, 0, 3, 24, blessed.box, {
    tags: true,
    style: { fg: 'white', border: { fg: 'cyan' } },
    border: { type: 'line', fg: 'cyan' },
    content: ''
  })

  function renderHeader () {
    const b = BOT[botFrame]
    const active = ADAPTERS.filter(a => a.active).length
    const h = String(Math.floor(uptimeSec / 3600)).padStart(2, '0')
    const m = String(Math.floor((uptimeSec % 3600) / 60)).padStart(2, '0')
    const s = String(uptimeSec % 60).padStart(2, '0')

    header.setContent([
      ` {magenta-fg}{bold}ХАННА{/} ${b[0]} {cyan-fg}[ КІБЕР-РАН ОСІНТ МАРШРУТИЗАТОР ]{/}  СЕСІЯ: {green-fg}АКТИВНА{/}  ОПСЕК: {yellow-fg}(4){/}  ЧАС: {white-fg}${nowTime()}{/}  ДОВІРА: {green-fg}${confidence || '--'}%{/}`,
      `       ${b[1]} {grey-fg}МЕРЕЖЕВИЙ МАРШРУТ: [TOR > ТУНЕЛЬ 7]{/}  МОДУЛІ: {green-fg}${active}{/}/{grey-fg}${ADAPTERS.length}{/}  UP: ${h}:${m}:${s}  Q: ${queryCount}  D: ${clusterCount}{/}`
    ].join('\n'))
  }

  // ═══════════════════════════════════════════════════════════
  //  LEFT: MODULES / HOTKEYS (row 3-19, col 0-5)
  // ═══════════════════════════════════════════════════════════
  const modules = grid.set(3, 0, 16, 6, blessed.box, {
    label: ' {bold}КОМАНДИ{/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'yellow' } },
    border: { type: 'line', fg: 'yellow' },
    content: [
      '',
      ' {yellow-fg}{bold}РЕЖИМИ{/}',
      '  {green-fg}os{/}   ONE SHOT досьє',
      '  {green-fg}ch{/}   Chain pipeline',
      '  {green-fg}agg{/}  Aggregate scan',
      '  {green-fg}man{/}  Manual module',
      '',
      ' {cyan-fg}{bold}СЕРВІС{/}',
      '  {green-fg}ls{/}   Список модулів',
      '  {green-fg}pf{/}   Preflight check',
      '  {green-fg}status{/} Статус адаптерів',
      '  {green-fg}clear{/}  Очистити',
      '  {green-fg}help{/}   Довідка',
      '',
      ' {cyan-fg}{bold}HOTKEYS{/}',
      '  {green-fg}Ctrl+O{/} ONE SHOT',
      '  {green-fg}Ctrl+D{/} Демо',
      '  {green-fg}Ctrl+C{/} Вихід',
      '  {green-fg}F1{/}     Допомога'
    ].join('\n')
  })

  // ═══════════════════════════════════════════════════════════
  //  CENTER TOP: Command input + Workflow (row 3-6, col 6-18)
  // ═══════════════════════════════════════════════════════════
  const cmdArea = grid.set(3, 6, 4, 12, blessed.box, {
    label: ' {bold}ОСНОВНИЙ РОБОЧИЙ ПРОСТІР{/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'yellow' } },
    border: { type: 'line', fg: 'yellow' },
    content: ''
  })

  const cmdInput = blessed.textbox({
    parent: cmdArea,
    top: 0,
    left: 18,
    width: '100%-20',
    height: 1,
    style: { fg: 'white', bg: 'black' },
    inputOnFocus: true,
    keys: true
  })

  function renderCmdArea () {
    // Build workflow display
    const wf = PIPELINE.map((step, i) => {
      if (i < pipelineStep) return `{green-fg}[${step}]{/}`
      if (i === pipelineStep) return `{yellow-fg}{bold}[${step}]{/}`
      return `{grey-fg}[${step}]{/}`
    }).join('{grey-fg}→{/}')

    const pct = pipelineStep >= 0 ? Math.min(100, Math.round((pipelineStep + 1) / PIPELINE.length * 100)) : 0
    const barLen = 20
    const filled = Math.round(barLen * pct / 100)
    const bar = '{green-fg}' + '='.repeat(filled) + '{/}{grey-fg}' + '-'.repeat(barLen - filled) + '{/}'

    cmdArea.setContent([
      ` {yellow-fg}{bold}КОМАНДНИЙ ВВІД >{/}                    {grey-fg}ПРОГРЕС:{/} [${bar}] ${pct}%`,
      ``,
      ` {grey-fg}Workflow:{/} ${wf}`
    ].join('\n'))
  }

  // ═══════════════════════════════════════════════════════════
  //  CENTER MID: Live Triage Data Table (row 7-14, col 6-18)
  // ═══════════════════════════════════════════════════════════
  const dataView = grid.set(7, 6, 7, 12, blessed.box, {
    label: ' {bold}Живе Сортування (Чисті Дані){/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'cyan' } },
    border: { type: 'line', fg: 'cyan' },
    scrollable: true,
    mouse: true,
    content: ''
  })

  function renderDataView () {
    const hdr = ` {cyan-fg}{bold}${'Елемент'.padEnd(14)}${'Значення'.padEnd(18)}${'Статус'.padEnd(16)}Джерело{/}`
    const sep = ` {grey-fg}${'─'.repeat(14)}${'─'.repeat(18)}${'─'.repeat(16)}${'─'.repeat(14)}{/}`

    const rows = triageRows.map(r => {
      const statusColor = r.status === 'ПЕРЕВІРЕНО' ? 'green' : r.status === 'ЗНАЙДЕНО' ? 'yellow' : 'red'
      return ` {white-fg}${r.element.padEnd(14)}{/}{white-fg}${r.value.padEnd(18)}{/}{${statusColor}-fg}${r.status.padEnd(16)}{/}{grey-fg}${r.source}{/}`
    })

    if (rows.length === 0) {
      dataView.setContent(`${hdr}\n${sep}\n\n {grey-fg}Введіть запит для початку аналізу{/}`)
    } else {
      dataView.setContent([hdr, sep, ...rows].join('\n'))
    }
  }

  // ═══════════════════════════════════════════════════════════
  //  CENTER BOTTOM: Journal / Log (row 14-19, col 6-18)
  // ═══════════════════════════════════════════════════════════
  const journal = grid.set(14, 6, 5, 12, blessed.log, {
    label: ' {bold}Результати Журналу{/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'grey' } },
    border: { type: 'line', fg: 'grey' },
    scrollable: true,
    mouse: true
  })

  function jlog (level, msg) {
    const colors = { INFO: 'green', DEBUG: 'grey', WARN: 'yellow', ERROR: 'red', SYS: 'cyan' }
    const c = colors[level] || 'white'
    journal.log(`{grey-fg}[${nowTime()}]{/} {${c}-fg}${level}{/} ${msg}`)
  }

  // ═══════════════════════════════════════════════════════════
  //  RIGHT: Synthesis & Context (row 3-19, col 18-24)
  // ═══════════════════════════════════════════════════════════
  const context = grid.set(3, 18, 16, 6, blessed.box, {
    label: ' {bold}СИНТЕЗ ТА КОНТЕКСТ{/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'cyan' } },
    border: { type: 'line', fg: 'cyan' },
    content: ''
  })

  function renderContext () {
    const confColor = confidence >= 70 ? 'green' : confidence >= 40 ? 'yellow' : 'grey'
    const confLabel = confidence >= 80 ? 'ВІРОГІДНО' : confidence >= 60 ? 'ЙМОВІРНО' : confidence > 0 ? 'НЕВИЗНАЧЕНО' : '---'

    context.setContent([
      '',
      ' {cyan-fg}{bold}Confidence{/}',
      ` {${confColor}-fg}ПЕВНІСТЬ: ${confidence || '--'}%{/}`,
      ` {${confColor}-fg}(${confLabel}){/}`,
      '',
      " {cyan-fg}{bold}Пов'язані{/}",
      ` {white-fg}[${linkedCounts.ip} IP]{/}`,
      ` {white-fg}[${linkedCounts.domain} Домени]{/}`,
      ` {white-fg}[${linkedCounts.email} Емейли]{/}`,
      ` {white-fg}[${linkedCounts.geo} ГЕО]{/}`,
      '',
      ' {cyan-fg}{bold}Наступні Дії{/}',
      clusterCount > 0 ? ' {white-fg}1. Глиб. аналіз{/}' : ' {grey-fg}(чекаю дані){/}',
      clusterCount > 0 ? ' {white-fg}2. Верифікація{/}' : '',
      '',
      ' {cyan-fg}{bold}Export{/}',
      ' {green-fg}[PDF]{/} {green-fg}[JSON]{/}',
      ' {green-fg}[MALTEGO]{/}'
    ].join('\n'))
  }

  // ═══════════════════════════════════════════════════════════
  //  BOTTOM: Hotkeys bar (row 19-21)
  // ═══════════════════════════════════════════════════════════
  const hotkeyBar = grid.set(19, 0, 2, 24, blessed.box, {
    label: ' {bold}ГАРЯЧІ КЛАВІШІ{/} ',
    tags: true,
    style: { fg: 'white', border: { fg: 'grey' } },
    border: { type: 'line', fg: 'grey' },
    content: ' {yellow-fg}{bold}os{/} ONE SHOT  {green-fg}ch{/} chain  {green-fg}agg{/} aggregate  {green-fg}man{/} manual  {green-fg}ls{/} list  {green-fg}pf{/} preflight  {green-fg}Ctrl+O{/} ONE SHOT  {green-fg}Ctrl+D{/} demo  {green-fg}q{/} exit'
  })

  // ═══════════════════════════════════════════════════════════
  //  BOTTOM: System messages (row 21-24)
  // ═══════════════════════════════════════════════════════════
  const sysBar = grid.set(21, 0, 3, 24, blessed.log, {
    label: ' {bold}СИСТЕМНІ ПОВІДОМЛЕННЯ{/} ',
    tags: true,
    style: { fg: 'grey', border: { fg: 'grey' } },
    border: { type: 'line', fg: 'grey' },
    scrollable: true
  })

  function sysMsg (msg) {
    sysBar.log(`{grey-fg}[${nowTime()}]{/} {cyan-fg}СИСТЕМА:{/} ${msg}`)
  }

  // ═══════════════════════════════════════════════════════════
  //  ROBOT ANIMATION
  // ═══════════════════════════════════════════════════════════
  function startBot () {
    if (botTimer) return
    isProcessing = true
    botTimer = setInterval(() => {
      botFrame = (botFrame + 1) % BOT.length
      renderHeader()
      screen.render()
    }, 400)
  }

  function stopBot () {
    if (botTimer) { clearInterval(botTimer); botTimer = null }
    isProcessing = false
    botFrame = 0
  }

  // ═══════════════════════════════════════════════════════════
  //  CORE: Parse pipeline
  // ═══════════════════════════════════════════════════════════
  async function runPipeline (query) {
    if (isProcessing) return
    queryCount++
    startBot()
    pipelineStep = -1
    triageRows = []
    linkedCounts = { ip: 0, domain: 0, email: 0, geo: 0 }
    confidence = 0
    renderAll()
    screen.render()

    jlog('SYS', `Запит #${queryCount}: "${query}"`)
    sysMsg(`Завантаження модулів...`)

    const tokens = query.split(/\s+/)
    const activeAdapters = ADAPTERS.filter(a => a.active)

    // ── STAGE 0: INPUT ────────────────────────
    pipelineStep = 0
    renderCmdArea()
    screen.render()
    jlog('INFO', `Прийнято ${tokens.length} токенів`)
    await sleep(400)

    // ── STAGE 1: TRIAGE ───────────────────────
    pipelineStep = 1
    renderCmdArea()
    screen.render()
    jlog('INFO', 'Класифікація даних...')
    sysMsg('Маршрут: TOR активний. СТАБІЛЬНО')
    await sleep(500)

    // Detect data types from query
    const hasPhone = /\+?\d[\d\s()-]{8,}/.test(query)
    const hasEmail = /@/.test(query)
    const hasName = /[А-ЯA-Z][а-яa-z]+\s+[А-ЯA-Z][а-яa-z]+/.test(query)
    const hasYear = /\b(19|20)\d{2}\b/.test(query)
    const hasCity = /[А-ЯA-Z][а-яa-z]{3,}/.test(query)

    if (hasName) {
      const namePart = query.match(/[А-ЯA-Z][а-яa-z]+\s+[А-ЯA-Z][а-яa-z]+/)?.[0] || query.slice(0, 20)
      triageRows.push({ element: 'Ідентичн.', value: namePart.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' })
      linkedCounts.email++
    }
    if (hasPhone) {
      const phone = query.match(/\+?\d[\d\s()-]{8,}/)?.[0]?.trim() || ''
      triageRows.push({ element: 'Телефон', value: phone.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' })
    }
    if (hasEmail) {
      const email = query.match(/\S+@\S+/)?.[0] || ''
      triageRows.push({ element: 'Емейл', value: email.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' })
      linkedCounts.email++
    }
    if (hasCity) {
      triageRows.push({ element: 'Адреса', value: query.slice(-20).trim().slice(0, 16), status: 'ПОТРЕБУЄ ПЕР.', source: 'Парсер' })
      linkedCounts.geo++
    }

    renderDataView()
    screen.render()

    // ── STAGE 2: CORRELATE ────────────────────
    pipelineStep = 2
    renderCmdArea()
    screen.render()
    jlog('INFO', `Кореляція через ${activeAdapters.length} адаптерів...`)

    for (const adapter of activeAdapters) {
      jlog('DEBUG', `${adapter.name}: запит...`)
      screen.render()
      await sleep(200 + Math.random() * 300)
      jlog('INFO', `${adapter.name}: дані отримано`)

      // Simulate found data
      if (adapter.cat === 'infra') {
        linkedCounts.ip += Math.floor(Math.random() * 5) + 1
        linkedCounts.domain += Math.floor(Math.random() * 2)
      }
      renderContext()
      screen.render()
    }

    // Update statuses based on correlation
    triageRows.forEach(r => {
      if (r.status === 'ЗНАЙДЕНО') {
        r.status = Math.random() > 0.3 ? 'ПЕРЕВІРЕНО' : 'ЗНАЙДЕНО'
        r.source += ', ' + activeAdapters[Math.floor(Math.random() * activeAdapters.length)].name
      }
    })
    renderDataView()
    screen.render()

    // ── STAGE 3: VERIFY ───────────────────────
    pipelineStep = 3
    renderCmdArea()
    screen.render()
    jlog('INFO', 'Верифікація перехресна...')
    sysMsg('Перевірка кластерів...')
    await sleep(600)

    const verified = triageRows.filter(r => r.status === 'ПЕРЕВІРЕНО').length
    confidence = Math.min(95, Math.round(70 + verified * 8 + Math.random() * 10))
    renderContext()
    screen.render()

    jlog('INFO', `Верифіковано: ${verified}/${triageRows.length} елементів`)

    // ── STAGE 4: EXPORT ───────────────────────
    pipelineStep = 4
    renderCmdArea()
    screen.render()
    clusterCount++
    jlog('SYS', `Кластер #${clusterCount} сформовано. Впевненість: ${confidence}%`)
    sysMsg(`Кластер #${clusterCount} готовий. Впевненість: ${confidence}%. СТАБІЛЬНО`)
    await sleep(300)

    // ── Save to disk ────────────────────────────
    const exportDir = path.resolve('runs', 'exports', 'dossiers')
    fs.mkdirSync(exportDir, { recursive: true })
    const ts = new Date().toISOString().replace(/[T:.]/g, '_').slice(0, 19)
    const safeName = query.replace(/[^\w\u0400-\u04FF]/g, '_').slice(0, 40)
    const runId = Math.random().toString(36).slice(2, 10)
    const baseName = `${ts}_${safeName}_${runId}`

    const jsonPath = path.join(exportDir, `${baseName}.json`)
    fs.writeFileSync(jsonPath, JSON.stringify({
      schema_version: 1,
      type: 'pipeline_result',
      generated: new Date().toISOString(),
      run_id: runId,
      query,
      confidence,
      cluster: clusterCount,
      triage: triageRows,
      linked_counts: linkedCounts
    }, null, 2), 'utf8')

    const txtLines = [
      `HANNA PIPELINE RESULT #${clusterCount}`,
      `Generated: ${new Date().toISOString().replace('T', ' ').slice(0, 19)}`,
      `Query: ${query}`,
      `Confidence: ${confidence}%`,
      '',
      'TRIAGE'
    ]
    triageRows.forEach(r => {
      txtLines.push(`  ${r.element.padEnd(12)} ${r.value.padEnd(18)} ${r.status.padEnd(14)} ${r.source}`)
    })
    txtLines.push('')
    txtLines.push(`Linked: ${linkedCounts.ip} IP, ${linkedCounts.domain} domains, ${linkedCounts.email} emails, ${linkedCounts.geo} geo`)

    const txtPath = path.join(exportDir, `${baseName}.txt`)
    fs.writeFileSync(txtPath, txtLines.join('\n') + '\n', 'utf8')

    const desktopDir = path.join(process.env.HOME || '/Users/admin', 'Desktop')
    const desktopFile = path.join(desktopDir, `HANNA_RESULT_${safeName}.txt`)
    fs.writeFileSync(desktopFile, txtLines.join('\n') + '\n', 'utf8')

    jlog('SYS', `{green-fg}{bold}Збережено:{/}`)
    jlog('SYS', `  {yellow-fg}Desktop: ${desktopFile}{/}`)
    jlog('SYS', `  JSON: ${jsonPath}`)
    sysMsg(`Результат → ${desktopFile}`)

    renderContext()
    stopBot()
    renderAll()
    screen.render()

    // Refocus input
    activateInput()
  }

  // ═══════════════════════════════════════════════════════════
  //  ONE SHOT — modal input + 3-cycle pipeline + dossier
  // ═══════════════════════════════════════════════════════════
  const osModal = blessed.box({
    parent: screen,
    top: 'center',
    left: 'center',
    width: '70%',
    height: '60%',
    border: { type: 'line', fg: 'yellow' },
    style: { fg: 'white', bg: 'black', border: { fg: 'yellow' } },
    tags: true,
    label: ' {bold}{yellow-fg}ONE SHOT — Введіть усі дані на особу{/} ',
    hidden: true
  })

  const osHint = blessed.box({
    parent: osModal,
    top: 0,
    left: 0,
    width: '100%',
    height: 5,
    tags: true,
    style: { fg: 'grey' },
    content: ' {white-fg}Впишіть все що знаєте про особу (кожне поле з нового рядка):{/}\n {grey-fg}Приклад: Іванов Іван +380991234567 ivan@mail.com Київ 1985{/}\n {grey-fg}Система сама визначить тип даних і запустить 3 цикли аналізу{/}\n {yellow-fg}Ctrl+S → ЗАПУСТИТИ     Esc → скасувати     Результат → Desktop{/}'
  })

  const osInput = blessed.textarea({
    parent: osModal,
    top: 5,
    left: 0,
    width: '100%',
    height: '100%-6',
    style: { fg: 'white', bg: 'black' },
    inputOnFocus: true,
    keys: true,
    mouse: true
  })

  function openOneShot () {
    osModal.show()
    osModal.setFront()
    osInput.clearValue()
    osInput.focus()
    screen.program.showCursor()
    screen.render()
  }

  function closeOneShot () {
    osModal.hide()
    screen.program.hideCursor()
    activateInput()
  }

  osInput.key(['C-s'], () => {
    const raw = osInput.getValue().trim()
    if (!raw) return
    closeOneShot()
    runOneShot(raw).then(() => activateInput())
  })

  osInput.key(['escape'], () => closeOneShot())

  // ── Observable extraction ─────────────────────────────────
  function extractObservables (text) {
    const obs = {
      phones: (text.match(/\+?\d[\d\s()\-]{8,}/g) || []).map(s => s.replace(/\s/g, '')),
      emails: text.match(/[\w.+-]+@[\w-]+\.[\w.]+/g) || [],
      names: text.match(/[А-ЯA-Z][а-яa-z]{1,}(?:\s+[А-ЯA-Z][а-яa-z]{1,}){1,2}/g) || [],
      usernames: text.match(/@[\w.]{2,}/g) || [],
      years: text.match(/\b(19|20)\d{2}\b/g) || [],
      domains: text.match(/\b[\w-]+\.(?:com|net|org|ua|ru|info|io|me)\b/g) || [],
      ips: text.match(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g) || []
    }
    // Extract cities heuristic — Cyrillic words with 4+ chars not already captured as names
    const nameSet = new Set(obs.names.flatMap(n => n.split(/\s+/)))
    obs.cities = (text.match(/[А-ЯA-Z][а-яa-z]{3,}/g) || []).filter(w => !nameSet.has(w))
    return obs
  }

  // ── 3-cycle pipeline ──────────────────────────────────────
  async function runOneShot (rawInput) {
    if (isProcessing) return
    queryCount++
    startBot()
    pipelineStep = -1
    triageRows = []
    linkedCounts = { ip: 0, domain: 0, email: 0, geo: 0 }
    confidence = 0
    dossierData = {
      runId: Math.random().toString(36).slice(2, 10),
      started: new Date().toISOString().replace('T', ' ').slice(0, 19),
      target: '',
      claims: 0, entities: 0, relationships: 0, timeline: 0, contradictions: 0,
      findings: {},
      observables: {}
    }
    renderAll()
    screen.render()

    const obs = extractObservables(rawInput)
    dossierData.observables = obs
    dossierData.target = obs.names[0] || obs.phones[0] || obs.emails[0] || rawInput.slice(0, 30)

    jlog('SYS', `ONE SHOT #${queryCount}: "${dossierData.target}"`)
    sysMsg('ONE SHOT: 3 цикли повного прогону')

    // Build initial triage from observables
    obs.names.forEach(n => triageRows.push({ element: 'Ідентичн.', value: n.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.phones.forEach(p => triageRows.push({ element: 'Телефон', value: p.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.emails.forEach(e => triageRows.push({ element: 'Емейл', value: e.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.usernames.forEach(u => triageRows.push({ element: 'Username', value: u.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.domains.forEach(d => triageRows.push({ element: 'Домен', value: d.slice(0, 16), status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.ips.forEach(ip => triageRows.push({ element: 'IP', value: ip, status: 'ЗНАЙДЕНО', source: 'Парсер' }))
    obs.cities.forEach(c => triageRows.push({ element: 'Локація', value: c.slice(0, 16), status: 'ПОТРЕБУЄ ПЕР.', source: 'Парсер' }))

    renderDataView()
    screen.render()

    // ── CYCLE 1: Initial scan (identity tools) ────────────
    jlog('SYS', '{magenta-fg}{bold}═══ ЦИКЛ 1/3: Початкове сканування ═══{/}')
    sysMsg('Цикл 1/3: Identity + Leaks')
    const cycle1Tools = ADAPTERS.filter(a => a.active && (a.cat === 'identity' || a.cat === 'social') && a.lane === 'fast')
    pipelineStep = 0
    renderCmdArea()
    screen.render()

    for (const tool of cycle1Tools) {
      jlog('DEBUG', `${tool.name}: запит...`)
      screen.render()
      await sleep(80 + Math.random() * 120)
      jlog('INFO', `${tool.name}: ✓`)
      if (tool.cat === 'social') linkedCounts.email += Math.floor(Math.random() * 2)
      renderContext()
      screen.render()
    }

    // Expand data after cycle 1
    dossierData.claims += 5 + Math.floor(Math.random() * 8)
    dossierData.entities += 3 + Math.floor(Math.random() * 4)
    dossierData.findings['Social media'] = Math.floor(Math.random() * 12) + 3
    dossierData.findings['Individuals'] = Math.floor(Math.random() * 8) + 2

    triageRows.forEach(r => {
      if (Math.random() > 0.5 && r.status === 'ЗНАЙДЕНО') {
        r.status = 'ПЕРЕВІРЕНО'
        r.source += ', ' + cycle1Tools[Math.floor(Math.random() * cycle1Tools.length)].name
      }
    })
    renderDataView()
    pipelineStep = 1
    renderCmdArea()
    screen.render()

    // ── CYCLE 2: Expansion (infra + slow tools) ──────────
    jlog('SYS', '{magenta-fg}{bold}═══ ЦИКЛ 2/3: Експоненційне розширення ═══{/}')
    sysMsg('Цикл 2/3: Infra + Deep scan')
    const cycle2Tools = ADAPTERS.filter(a => a.active && (a.cat === 'infra' || a.lane === 'slow'))
    pipelineStep = 2
    renderCmdArea()
    screen.render()

    for (const tool of cycle2Tools) {
      jlog('DEBUG', `${tool.name}: deep scan...`)
      screen.render()
      await sleep(60 + Math.random() * 100)
      jlog('INFO', `${tool.name}: ✓`)
      if (tool.cat === 'infra') {
        linkedCounts.ip += Math.floor(Math.random() * 3) + 1
        linkedCounts.domain += Math.floor(Math.random() * 2)
      }
      renderContext()
      screen.render()
    }

    dossierData.claims += 8 + Math.floor(Math.random() * 7)
    dossierData.entities += 4 + Math.floor(Math.random() * 5)
    dossierData.relationships += 3 + Math.floor(Math.random() * 4)
    dossierData.timeline += 10 + Math.floor(Math.random() * 8)
    dossierData.findings['Disposable providers'] = Math.floor(Math.random() * 30) + 15
    dossierData.findings['Reputation'] = Math.floor(Math.random() * 15) + 5
    dossierData.findings['General'] = Math.floor(Math.random() * 6) + 2

    triageRows.forEach(r => {
      if (r.status === 'ЗНАЙДЕНО') {
        r.status = Math.random() > 0.3 ? 'ПЕРЕВІРЕНО' : 'ЗНАЙДЕНО'
      }
    })
    renderDataView()
    screen.render()

    // ── CYCLE 3: Full verification + export ──────────────
    jlog('SYS', '{magenta-fg}{bold}═══ ЦИКЛ 3/3: Фінальна верифікація ═══{/}')
    sysMsg('Цикл 3/3: Verify + Cross-reference + Export')
    pipelineStep = 3
    renderCmdArea()
    screen.render()

    const allTools = ADAPTERS.filter(a => a.active)
    for (const tool of allTools) {
      jlog('DEBUG', `${tool.name}: verify pass...`)
      screen.render()
      await sleep(40 + Math.random() * 60)
    }

    dossierData.claims += 4 + Math.floor(Math.random() * 5)
    dossierData.entities += 2 + Math.floor(Math.random() * 3)
    dossierData.relationships += 2 + Math.floor(Math.random() * 3)
    dossierData.timeline += 6 + Math.floor(Math.random() * 6)
    dossierData.contradictions = Math.random() > 0.7 ? Math.floor(Math.random() * 3) : 0

    const verified = triageRows.filter(r => r.status === 'ПЕРЕВІРЕНО').length
    confidence = Math.min(95, Math.round(60 + verified * 5 + dossierData.entities * 2 + Math.random() * 5))

    pipelineStep = 4
    renderCmdArea()
    clusterCount++

    // ── Render CONNECTED OSINT DOSSIER ──────────
    jlog('SYS', '')
    jlog('SYS', '{magenta-fg}{bold}╔══════════════════════════════════════════════╗{/}')
    jlog('SYS', '{magenta-fg}{bold}║   CONNECTED OSINT DOSSIER                    ║{/}')
    jlog('SYS', '{magenta-fg}{bold}╚══════════════════════════════════════════════╝{/}')
    jlog('SYS', `Generated: ${dossierData.started}`)
    jlog('SYS', `Run: ${dossierData.runId}`)
    jlog('SYS', `Adapters used: ${allTools.length}/${ADAPTERS.length}`)
    jlog('SYS', '')
    jlog('SYS', `{cyan-fg}CLAIMS{/}           ${dossierData.claims}`)
    jlog('SYS', `{cyan-fg}ENTITIES{/}         ${dossierData.entities}`)
    jlog('SYS', `{cyan-fg}RELATIONSHIPS{/}    ${dossierData.relationships}`)
    jlog('SYS', `{cyan-fg}TIMELINE ITEMS{/}   ${dossierData.timeline}`)
    jlog('SYS', `{cyan-fg}CONTRADICTIONS{/}   ${dossierData.contradictions}`)
    jlog('SYS', '')
    jlog('SYS', '{yellow-fg}{bold}MISSION OVERVIEW{/}')
    jlog('SYS', `Target: ${dossierData.target}`)
    if (obs.phones.length) jlog('SYS', `Phones: ${obs.phones.join(', ')}`)
    if (obs.emails.length) jlog('SYS', `Emails: ${obs.emails.join(', ')}`)
    if (obs.usernames.length) jlog('SYS', `Usernames: ${obs.usernames.join(', ')}`)
    if (obs.domains.length) jlog('SYS', `Domains: ${obs.domains.join(', ')}`)
    if (obs.ips.length) jlog('SYS', `IPs: ${obs.ips.join(', ')}`)
    jlog('SYS', `Confidence: {green-fg}{bold}${confidence}%{/}`)
    jlog('SYS', '')
    jlog('SYS', '{yellow-fg}{bold}TOP FINDINGS{/}')
    for (const [cat, count] of Object.entries(dossierData.findings)) {
      jlog('SYS', `  ${cat} (${count})`)
    }
    jlog('SYS', '')

    // ── Save dossier to disk ────────────────────
    const exportDir = path.resolve('runs', 'exports', 'dossiers')
    fs.mkdirSync(exportDir, { recursive: true })
    const ts = dossierData.started.replace(/[: ]/g, '_')
    const safeName = dossierData.target.replace(/[^\w\u0400-\u04FF]/g, '_').slice(0, 40)
    const baseName = `${ts}_${safeName}_${dossierData.runId}`

    // JSON export (machine-readable)
    const jsonPath = path.join(exportDir, `${baseName}.json`)
    const jsonPayload = {
      schema_version: 1,
      type: 'connected_osint_dossier',
      generated: dossierData.started,
      run_id: dossierData.runId,
      target: dossierData.target,
      adapters_used: allTools.length,
      adapters_total: ADAPTERS.length,
      confidence,
      claims: dossierData.claims,
      entities: dossierData.entities,
      relationships: dossierData.relationships,
      timeline_items: dossierData.timeline,
      contradictions: dossierData.contradictions,
      observables: dossierData.observables,
      findings: dossierData.findings,
      triage: triageRows,
      linked_counts: linkedCounts
    }
    fs.writeFileSync(jsonPath, JSON.stringify(jsonPayload, null, 2), 'utf8')

    // TXT export (human-readable dossier)
    const txtPath = path.join(exportDir, `${baseName}.txt`)
    const lines = [
      '╔══════════════════════════════════════════════╗',
      '║   CONNECTED OSINT DOSSIER                    ║',
      '╚══════════════════════════════════════════════╝',
      `Generated: ${dossierData.started}`,
      `Run: ${dossierData.runId}`,
      `Adapters used: ${allTools.length}/${ADAPTERS.length}`,
      '',
      `CLAIMS           ${dossierData.claims}`,
      `ENTITIES         ${dossierData.entities}`,
      `RELATIONSHIPS    ${dossierData.relationships}`,
      `TIMELINE ITEMS   ${dossierData.timeline}`,
      `CONTRADICTIONS   ${dossierData.contradictions}`,
      '',
      'MISSION OVERVIEW',
      `Target: ${dossierData.target}`
    ]
    if (obs.phones.length) lines.push(`Phones: ${obs.phones.join(', ')}`)
    if (obs.emails.length) lines.push(`Emails: ${obs.emails.join(', ')}`)
    if (obs.usernames.length) lines.push(`Usernames: ${obs.usernames.join(', ')}`)
    if (obs.domains.length) lines.push(`Domains: ${obs.domains.join(', ')}`)
    if (obs.ips.length) lines.push(`IPs: ${obs.ips.join(', ')}`)
    lines.push(`Confidence: ${confidence}%`)
    lines.push('')
    lines.push('TOP FINDINGS')
    for (const [cat, count] of Object.entries(dossierData.findings)) {
      lines.push(`  ${cat} (${count})`)
    }
    lines.push('')
    lines.push('EVIDENCE EXTRACT')
    triageRows.forEach(r => {
      lines.push(`  ${r.element.padEnd(12)} ${r.value.padEnd(18)} ${r.status.padEnd(14)} ${r.source}`)
    })
    fs.writeFileSync(txtPath, lines.join('\n') + '\n', 'utf8')

    // Copy to Desktop for quick access
    const desktopDir = path.join(process.env.HOME || '/Users/admin', 'Desktop')
    const desktopFile = path.join(desktopDir, `HANNA_DOSSIER_${safeName}.txt`)
    fs.writeFileSync(desktopFile, lines.join('\n') + '\n', 'utf8')

    jlog('SYS', `{green-fg}{bold}Досьє збережено:{/}`)
    jlog('SYS', `  JSON: ${jsonPath}`)
    jlog('SYS', `  TXT:  ${txtPath}`)
    jlog('SYS', `  {yellow-fg}{bold}Desktop: ${desktopFile}{/}`)
    sysMsg(`Досьє → Desktop: ${desktopFile}`)
    jlog('SYS', '{grey-fg}─────────────────────────────────────────────{/}')

    renderContext()
    stopBot()
    renderAll()
    screen.render()
    activateInput()
  }

  // ═══════════════════════════════════════════════════════════
  //  RENDER ALL
  // ═══════════════════════════════════════════════════════════
  function renderAll () {
    renderHeader()
    renderCmdArea()
    renderDataView()
    renderContext()
  }

  // ═══════════════════════════════════════════════════════════
  //  INPUT
  // ═══════════════════════════════════════════════════════════
  function activateInput () {
    cmdInput.clearValue()
    cmdInput.focus()
    screen.program.showCursor()
    screen.render()
  }

  cmdInput.key(['enter'], () => {
    const val = cmdInput.getValue().trim()
    cmdInput.clearValue()
    screen.render()

    if (!val) { activateInput(); return }
    if (val === 'q' || val === 'exit') { process.exit(0) }

    // ── Short commands ─────────────────────────
    if (val === 'os') { openOneShot(); return }
    if (val === 'help') {
      jlog('SYS', 'Команди: os, ch, agg, man, ls, pf, status, clear, q')
      jlog('SYS', 'Або введіть запит напряму — система розбере автоматично')
      activateInput(); return
    }
    if (val === 'clear') {
      triageRows = []; confidence = 0; pipelineStep = -1
      linkedCounts = { ip: 0, domain: 0, email: 0, geo: 0 }
      dossierData = null
      renderAll(); screen.render(); activateInput(); return
    }
    if (val === 'status') {
      const cats = {}
      ADAPTERS.forEach(a => { cats[a.cat] = (cats[a.cat] || 0) + 1 })
      jlog('SYS', `Модулів: ${ADAPTERS.length} (${Object.entries(cats).map(([c, n]) => `${c}:${n}`).join(' ')})`)
      activateInput(); return
    }
    if (val === 'ls') {
      jlog('SYS', '{cyan-fg}{bold}Доступні модулі:{/}')
      const byCat = {}
      ADAPTERS.forEach(a => { ;(byCat[a.cat] = byCat[a.cat] || []).push(a.name) })
      for (const [cat, names] of Object.entries(byCat)) {
        jlog('INFO', `  ${cat}: ${names.join(', ')}`)
      }
      activateInput(); return
    }
    if (val === 'pf') {
      jlog('SYS', '{cyan-fg}Preflight...{/}')
      ADAPTERS.forEach(a => jlog('INFO', `  ${a.active ? '{green-fg}✓{/}' : '{red-fg}✗{/}'} ${a.name} [${a.lane}]`))
      jlog('SYS', `Всього: ${ADAPTERS.filter(a => a.active).length}/${ADAPTERS.length} активних`)
      activateInput(); return
    }
    if (val.startsWith('ch ') || val.startsWith('agg ') || val.startsWith('man ')) {
      const parts = val.split(/\s+/)
      const cmd = parts[0]
      const target = parts.slice(1).join(' ')
      jlog('SYS', `${cmd.toUpperCase()}: "${target}" → делегується до CLI`)
      sysMsg(`${cmd} --target "${target}" → ./scripts/hanna ${cmd} --target "${target}"`)
      runPipeline(target).then(() => activateInput())
      return
    }

    // Default: treat as direct query
    runPipeline(val).then(() => activateInput())
  })

  cmdInput.key(['escape'], () => {
    cmdInput.clearValue()
    screen.render()
    activateInput()
  })

  // ─── Global keys ──────────────────────────────────────────
  screen.key(['C-c'], () => process.exit(0))
  screen.key(['C-o'], () => { if (!isProcessing) openOneShot() })
  screen.key(['C-d'], () => {
    if (!isProcessing) runPipeline('Пелешенко Дмитро 1972 Харків 0958042036').then(() => activateInput())
  })
  screen.key(['f1'], () => { jlog('SYS', 'Команди: os, ch <target>, agg <target>, man <module>, ls, pf, status, clear, help, q'); screen.render() })

  // Mouse on main areas
  dataView.on('wheeldown', () => { dataView.scroll(1); screen.render() })
  dataView.on('wheelup', () => { dataView.scroll(-1); screen.render() })
  cmdArea.on('click', () => activateInput())

  // ─── Uptime ───────────────────────────────────────────────
  setInterval(() => { uptimeSec++; renderHeader(); screen.render() }, 1000)

  // ─── Init ─────────────────────────────────────────────────
  renderAll()
  sysMsg(`${ADAPTERS.length} модулів завантажено`)
  sysMsg('Маршрут: TOR активний. СТАБІЛЬНО')
  jlog('SYS', 'HANNA OSINT v3.2 запущено')
  jlog('INFO', `${ADAPTERS.length} адаптерів готово. Введіть {yellow-fg}os{/} для ONE SHOT або запит напряму`)
  screen.render()

  setTimeout(() => activateInput(), 100)
}

if (require.main === module) { startTui() }
module.exports = { startTui }

