'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { startTui } = require('./hanna-tui');

// Ensure calibration is used
process.env.CALIBRATED = '1';

// We could also apply extra logic here if needed, 
// but startTui in hanna-tui.js already handles 
// process.env.CALIBRATED === '1' and loads config.calibrated.json.

console.log('🚀 Launching HANNA TUI with user calibration...');

try {
  startTui();
} catch (err) {
  console.error('Failed to launch calibrated TUI:', err);
  process.exit(1);
}
