const fs = require('fs');
const { SafeParser } = require('./search-panel');
const { SmartSearch } = require('./smart-search');

class CalibratedParser {
  constructor() {
    this.config = this.loadCalibration();
    this.parser = new SafeParser();
    this.smart = new SmartSearch();
  }

  loadCalibration() {
    try {
      // Use absolute path or handle relative path carefully
      const configPath = require('path').resolve(process.cwd(), 'config.calibrated.json');
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch {
      return { parser: { sensitivity: 0.5 }, search: { boostFio: 3.0, boostYear: 2.5 } };
    }
  }

  parseSearchInput(text) {
    const baseResult = this.parser.parseSearchInput(text);
    
    // Застосовуємо sensitivity
    const calibrated = { ...baseResult };
    calibrated.confidence *= (this.config.parser ? this.config.parser.sensitivity : 0.5);
    
    // Smart scoring з кастомними вагами
    const searchWeights = this.config.search || { boostFio: 3.0, boostYear: 2.5 };
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
