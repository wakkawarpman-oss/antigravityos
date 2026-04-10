#!/usr/bin/env node
const fs = require('fs');
const { CalibratedParser } = require('../components/calibrated-parser');

try {
  const config = JSON.parse(fs.readFileSync('config.calibrated.json'));
  const parser = new CalibratedParser();

  const testCases = [
    'Пелешенко Дмитро Валерійович 1972',
    '0958042036 Харків Широнинцев',
    'ФОП Коваленко вул Сумська'
  ];

  console.log('🔍 HANNA CALIBRATION VALIDATION\n');
  
  testCases.forEach((input, i) => {
    const result = parser.parseSearchInput(input);
    const confidence = result.confidence || 0;
    const score = (result.relevance && result.relevance.score) ? result.relevance.score : 0;
    
    console.log(`${i+1}. "${input}" → Conf: ${confidence.toFixed(1)} | Relevance: ${score.toFixed(1)}`);
  });

  console.log(`\n✅ Current Config:`);
  console.log(JSON.stringify(config, null, 2));

} catch (err) {
  console.error('❌ Validation failed. Ensure config.calibrated.json exists.');
  console.error(err.message);
  process.exit(1);
}
