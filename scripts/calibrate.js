#!/usr/bin/env node
const readline = require('node:readline');
const { SafeParser } = require('../components/search-panel');
const { SmartSearch } = require('../components/smart-search');
const fs = require('node:fs');

class CalibrationWizard {
  constructor() {
    this.config = this.loadConfig();
    this.calibrationData = {
      parser: { sensitivity: 0.5, fuzziness: 0.75 },
      search: { boostFio: 3.0, boostYear: 2.5 },
      tui: { fpsTarget: 60, compactMode: false },
      behavioral: { noiseLevel: 0.1 }
    };
  }

  async run() {
    console.clear();
    console.log('🎛️  HANNA v3.3.1 — CALIBRATION WIZARD\n');
    
    await this.calibrateParser();
    await this.calibrateSearch();
    await this.calibrateTUI();
    await this.calibrateBehavioral();
    
    this.saveConfig();
    console.log('\n✅ CALIBRATION COMPLETE!');
    console.log('🔄 Restart: npm run tui:calibrated');
  }

  async calibrateParser() {
    console.log('\n1️⃣ PARSER SENSITIVITY (0.1-1.0)');
    console.log('   Налаштуй чутливість до ФІО/адрес');
    
    const testCases = [
      'Пелешенко Дмитро Валерійович 1972',
      '0958042036 ул. Широнинцев 49',
      'Коваленко Петро ФОП Київ Сумська'
    ];

    for (let i = 0; i < testCases.length; i++) {
      const result = new SafeParser().parseSearchInput(testCases[i]);
      console.log(`${i+1}. ${testCases[i].slice(0,30)}... → ${result.confidence}/6`);
    }

    this.calibrationData.parser.sensitivity = await this.promptFloat('Sensitivity (0.3=default): ', 0.3);
  }

  async calibrateSearch() {
    console.log('\n2️⃣ SEARCH RELEVANCE WEIGHTS');
    console.log('   Налаштуй пріоритети полів');
    
    this.calibrationData.search.boostFio = await this.promptFloat('FIO boost (3.0=default): ', 3.0);
    this.calibrationData.search.boostYear = await this.promptFloat('Birth year boost (2.5): ', 2.5);
  }

  async calibrateTUI() {
    console.log('\n3️⃣ TUI PERFORMANCE');
    console.log('   FPS, layout, responsiveness');
    
    this.calibrationData.tui.fpsTarget = await this.promptInt('FPS target (30/60): ', 60, 30, 120);
    this.calibrationData.tui.compactMode = await this.promptYesNo('Compact mode (small screens): ', false);
  }

  async calibrateBehavioral() {
    console.log('\n4️⃣ BEHAVIORAL METRICS');
    console.log('   Engagement hooks intensity');
    
    this.calibrationData.behavioral.noiseLevel = await this.promptFloat('Organic noise (0.05-0.2): ', 0.1);
  }

  // 🔧 UTILITY METHODS
  prompt(question, def) {
    return new Promise(resolve => {
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      rl.question(question, answer => {
        rl.close();
        resolve(answer || def);
      });
    });
  }

  async promptFloat(question, def, min=0, max=1) {
    return parseFloat(await this.prompt(question, String(def))) || def;
  }

  async promptInt(question, def, min=0, max=100) {
    return parseInt(await this.prompt(question, String(def))) || def;
  }

  async promptYesNo(question, def) {
    const res = await this.prompt(question, def ? 'y' : 'n');
    return res.toLowerCase().startsWith('y');
  }

  loadConfig() {
    try {
      return JSON.parse(fs.readFileSync('config.calibrated.json', 'utf8'));
    } catch {
      return {};
    }
  }

  saveConfig() {
    fs.writeFileSync('config.calibrated.json', JSON.stringify(this.calibrationData, null, 2));
    console.log('💾 Saved: config.calibrated.json');
  }
}

new CalibrationWizard().run();
