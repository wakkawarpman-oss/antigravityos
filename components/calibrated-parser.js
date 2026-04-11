const fs = require('fs');
const path = require('path');
const { SafeParser } = require('./search-panel');
const { SmartSearch } = require('./smart-search');

class CalibratedParser {
  constructor(configPath) {
    this.configPath = configPath;
    this.config = this.loadCalibration();
    this.parser = new SafeParser();
    this.smart = new SmartSearch();
    this.applySmartCalibration();
  }

  loadCalibration() {
    const defaults = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
    try {
      const configPath = this.configPath
        ? path.resolve(this.configPath)
        : path.resolve(process.cwd(), 'config.calibrated.json');
      const loaded = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      return {
        ...defaults,
        ...loaded,
        parser: { ...defaults.parser, ...(loaded.parser || {}) },
        search: { ...defaults.search, ...(loaded.search || {}) },
        tui: { ...defaults.tui, ...(loaded.tui || {}) },
        behavioral: { ...defaults.behavioral, ...(loaded.behavioral || {}) }
      };
    } catch {
      return defaults;
    }
  }

  applySmartCalibration() {
    const parserCfg = this.config.parser || DEFAULT_CONFIG.parser;
    const searchCfg = this.config.search || DEFAULT_CONFIG.search;
    this.smart.fuzzyThreshold = Number(parserCfg.fuzziness) || DEFAULT_CONFIG.parser.fuzziness;
    this.smart.boostFactors = {
      ...this.smart.boostFactors,
      fio: Number(searchCfg.boostFio) || DEFAULT_CONFIG.search.boostFio,
      birthYear: Number(searchCfg.boostYear) || DEFAULT_CONFIG.search.boostYear
    };
  }

  parseSearchInput(text) {
    const baseResult = this.parser.parseSearchInput(text);
    
    // Застосовуємо sensitivity
    const calibrated = { ...baseResult };
    calibrated.calibrated = true;
    calibrated.confidence *= (this.config.parser ? this.config.parser.sensitivity : DEFAULT_CONFIG.parser.sensitivity);
    
    // Smart scoring з кастомними вагами
    const searchWeights = this.config.search || DEFAULT_CONFIG.search;
    calibrated.relevance = this.smart.scoreResult(
      calibrated.parsed || {}, 
      text, 
      searchWeights
    );
    
    return calibrated;
  }
}

const DEFAULT_CONFIG = {
  parser: { sensitivity: 0.5, fuzziness: 0.75 },
  search: { boostFio: 3.0, boostYear: 2.5 },
  tui: { fpsTarget: 60, compactMode: false },
  behavioral: { noiseLevel: 0.1 }
};

module.exports = { CalibratedParser, DEFAULT_CONFIG };
