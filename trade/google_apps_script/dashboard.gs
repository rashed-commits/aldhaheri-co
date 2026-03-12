/**
 * Trading Bot Dashboard — Google Apps Script
 * ============================================
 * Builds a 5-tab analytics dashboard inside your "Trading Bot Log" spreadsheet.
 *
 * HOW TO INSTALL
 * --------------
 *   1. Open "Trading Bot Log" in Google Sheets
 *   2. Extensions → Apps Script
 *   3. Delete any existing code, paste this entire file, Save (Ctrl+S)
 *   4. Select function: buildDashboard → Run
 *   5. Approve the permissions popup (needs Spreadsheet access only)
 *
 * HOW TO REFRESH
 * --------------
 *   After new rows are appended to Daily Log:
 *     Select function: refreshAllDerivedSheets → Run
 *
 * EXPECTED DAILY LOG COLUMNS (appended daily by the pipeline)
 * ---------------------------------------------------
 *   A  Date
 *   B  Action             ("TRADE" or "NO TRADE")
 *   C  Universe           (integer — total tickers scanned)
 *   D  Passed TA          (integer — passed all 4 TA filters)
 *   E  Passed ML          (integer — passed ML threshold)
 *   F  Signals (JSON)     (array of signal objects, JSON-stringified)
 *   G  No Trade Reason    (string or blank)
 *   H  Portfolio Value    (float — from Phase 5 performance JSON;
 *                          leave column blank if Phase 5 data is not yet wired)
 *
 * NOTE: For full Filter Analytics, add these columns to Daily Log
 * by expanding the filters_summary object in the pipeline output:
 *   I  Passed EMA200   J  Passed RSI   K  Passed Volume   L  Passed MACD
 * The dashboard will auto-populate those charts once the data arrives.
 */

'use strict';

// ── constants ──────────────────────────────────────────────────────────────────

const STARTING_CAPITAL = 50000;
const ML_THRESHOLD     = 0.55;

// 0-based column indices inside Daily Log data arrays
const DL = {
  DATE:       0,   // A
  ACTION:     1,   // B
  UNIVERSE:   2,   // C
  PASSED_TA:  3,   // D
  PASSED_ML:  4,   // E
  SIGNALS:    5,   // F
  NO_TRADE:   6,   // G
  PORTFOLIO:  7,   // H — optional
  EMA200:     8,   // I — optional (per-stage counts)
  RSI:        9,   // J — optional
  VOLUME:    10,   // K — optional
  MACD:      11,   // L — optional
};

// Colours
const C = {
  NAVY:       '#1c4587',
  WHITE:      '#ffffff',
  TRADE:      '#d9ead3',   // light green
  NO_TRADE:   '#f3f3f3',   // light grey
  PROB_HIGH:  '#b7e1cd',   // green  > 0.60
  PROB_MID:   '#fce8b2',   // yellow  0.55–0.60
  BLUE:       '#4285f4',
  GREEN:      '#34a853',
  YELLOW:     '#fbbc04',
  RED:        '#ea4335',
  ORANGE:     '#ff6d00',
  SECTION_BG: '#e8f0fe',
  PENDING:    '#cc0000',
};


// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC ENTRY POINTS
// ═══════════════════════════════════════════════════════════════════════════════

/** Run once to build every tab. Safe to re-run — clears and rebuilds. */
function buildDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  _setupDailyLog(ss);
  _buildEquityCurve(ss);
  _buildTradeLog(ss);
  _buildPerformanceSummary(ss);
  _buildFilterAnalytics(ss);

  // Put Daily Log first in tab order
  ss.setActiveSheet(ss.getSheetByName('Daily Log'));
  _reorderSheets(ss);

  SpreadsheetApp.getUi().alert(
    '✅  Dashboard built successfully!\n\n' +
    'Tabs ready:\n' +
    '  1 · Daily Log\n' +
    '  2 · Equity Curve\n' +
    '  3 · Trade Log\n' +
    '  4 · Performance Summary\n' +
    '  5 · Filter Analytics\n\n' +
    'Run refreshAllDerivedSheets() each time new rows are added to Daily Log.'
  );
}

/** Refresh derived tabs after new Daily Log rows arrive. */
function refreshAllDerivedSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  _buildEquityCurve(ss);
  _buildTradeLog(ss);
  _buildPerformanceSummary(ss);
  _buildFilterAnalytics(ss);
  Logger.log('All derived sheets refreshed.');
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1 — DAILY LOG  (format only; pipeline owns the data)
// ═══════════════════════════════════════════════════════════════════════════════

function _setupDailyLog(ss) {
  const sheet = _getOrCreate(ss, 'Daily Log');

  // Write headers only if row 1 is blank
  const firstCell = sheet.getRange('A1').getValue().toString().trim();
  if (firstCell === '') {
    sheet.getRange(1, 1, 1, 8).setValues([[
      'Date', 'Action', 'Universe', 'Passed TA', 'Passed ML',
      'Signals (JSON)', 'No Trade Reason', 'Portfolio Value'
    ]]);
  }

  _styleHeaderRow(sheet, 8);

  // Column widths
  const widths = { 1: 105, 2: 90, 3: 80, 4: 80, 5: 80, 6: 360, 7: 260, 8: 130 };
  Object.entries(widths).forEach(([col, w]) => sheet.setColumnWidth(Number(col), w));

  // Conditional formatting (applies to all data rows; grows automatically)
  const maxRow = Math.max(sheet.getMaxRows(), 2);
  const range  = sheet.getRange(2, 1, maxRow - 1, 8);

  const tradeRule = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=$B2="TRADE"')
    .setBackground(C.TRADE)
    .setRanges([range])
    .build();

  const noTradeRule = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=$B2="NO TRADE"')
    .setBackground(C.NO_TRADE)
    .setRanges([range])
    .build();

  sheet.setConditionalFormatRules([tradeRule, noTradeRule]);

  // Number formats
  const lastData = Math.max(sheet.getLastRow(), 2);
  sheet.getRange(2, 1, lastData - 1, 1).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(2, 3, lastData - 1, 3).setNumberFormat('#,##0');
  sheet.getRange(2, 8, lastData - 1, 1).setNumberFormat('$#,##0.00');
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2 — EQUITY CURVE
// ═══════════════════════════════════════════════════════════════════════════════

function _buildEquityCurve(ss) {
  const src   = ss.getSheetByName('Daily Log');
  const sheet = _getOrCreate(ss, 'Equity Curve');
  _clearSheet(sheet);

  // Headers
  const headers = ['Date', 'Portfolio Value', 'Baseline ($50k)', 'Return %', 'Cumulative Return %'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  _styleHeaderRow(sheet, headers.length);
  _setColumnWidths(sheet, [110, 140, 130, 100, 170]);

  const lastRow = src.getLastRow();
  if (lastRow < 2) {
    sheet.getRange('A2').setValue('No data yet — Daily Log is empty.')
      .setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  // Pull all rows from Daily Log
  const raw = src.getRange(2, 1, lastRow - 1, Math.max(src.getLastColumn(), 8)).getValues();

  // Filter to rows that have a date (skip truly blank rows)
  const rows = raw.filter(r => r[DL.DATE] !== '');

  if (rows.length === 0) {
    sheet.getRange('A2').setValue('No data rows found in Daily Log.')
      .setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  // Write data
  const data = rows.map(r => [
    r[DL.DATE],
    r[DL.PORTFOLIO] !== '' ? r[DL.PORTFOLIO] : null,  // May be blank
    STARTING_CAPITAL,
    null,   // Return % — formula below
    null,   // Cumulative % — formula below
  ]);
  sheet.getRange(2, 1, data.length, 5).setValues(data);

  // Write formulas for return columns
  const end = data.length + 1;
  for (let r = 2; r <= end; r++) {
    sheet.getRange(r, 4).setFormula(
      `=IFERROR(IF(B${r}="","", (B${r}-${STARTING_CAPITAL})/${STARTING_CAPITAL}),"")`
    );
    sheet.getRange(r, 5).setFormula(
      r === 2
        ? `=IFERROR(D${r},"")`
        : `=IFERROR(IF(D${r}="","",E${r - 1}+D${r}),"")`
    );
  }

  // Number formats
  sheet.getRange(`A2:A${end}`).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(`B2:C${end}`).setNumberFormat('"$"#,##0.00');
  sheet.getRange(`D2:E${end}`).setNumberFormat('0.00%');

  // Note if Portfolio Value column is empty
  const hasPV = rows.some(r => r[DL.PORTFOLIO] !== '');
  if (!hasPV) {
    sheet.getRange(end + 2, 1).setValue(
      '⚠  Portfolio Value (column H of Daily Log) is not yet populated. ' +
      'Configure your pipeline to also send Phase 5 performance data ' +
      '(output/performance_YYYY-MM-DD.json) to this sheet. The chart will appear automatically once data arrives.'
    ).setFontColor(C.PENDING).setFontSize(9).setWrap(true);
    sheet.setRowHeight(end + 2, 46);
    return;   // No chart without data
  }

  // Line chart
  const chart = sheet.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(sheet.getRange(1, 1, end, 1))   // Date (X axis)
    .addRange(sheet.getRange(1, 2, end, 1))   // Portfolio Value
    .addRange(sheet.getRange(1, 3, end, 1))   // Baseline
    .setPosition(end + 3, 1, 0, 0)
    .setOption('title', 'Portfolio Value vs $50,000 Baseline')
    .setOption('titleTextStyle', { fontSize: 14, bold: true })
    .setOption('hAxis', {
      title: 'Date',
      format: 'MMM d',
      slantedText: true,
      slantedTextAngle: 45,
    })
    .setOption('vAxis', { title: 'Value ($)', format: '"$"#,##0' })
    .setOption('series', {
      0: { color: C.BLUE,  lineWidth: 2, pointSize: 4 },
      1: { color: C.RED,   lineWidth: 2, lineDashStyle: 'LONG_DASH' },
    })
    .setOption('legend', { position: 'bottom' })
    .setOption('curveType', 'function')
    .setOption('width', 860)
    .setOption('height', 400)
    .build();

  sheet.insertChart(chart);
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB 3 — TRADE LOG  (JSON parse + expand)
// ═══════════════════════════════════════════════════════════════════════════════

function _buildTradeLog(ss) {
  const src   = ss.getSheetByName('Daily Log');
  const sheet = _getOrCreate(ss, 'Trade Log');
  _clearSheet(sheet);

  // Headers
  const headers = [
    'Date', 'Ticker', 'Action', 'Probability',
    'RSI', 'MACD Hist', 'Volume Ratio', 'Above EMA200',
    'Signal Rank', 'Position Size %',
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  _styleHeaderRow(sheet, headers.length);
  _setColumnWidths(sheet, [110, 80, 70, 110, 70, 100, 115, 115, 105, 130]);

  const lastRow = src.getLastRow();
  if (lastRow < 2) {
    sheet.getRange('A2').setValue('No data yet.').setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  // Parse every TRADE row's Signals JSON
  const raw = src.getRange(2, 1, lastRow - 1, 7).getValues();
  const tradeRows = [];

  raw.forEach(r => {
    const d       = r[DL.DATE];
    const action  = r[DL.ACTION];
    const jsonStr = r[DL.SIGNALS];

    if (!d || action !== 'TRADE' || !jsonStr || jsonStr.toString().trim() === '') return;

    let signals;
    try {
      signals = JSON.parse(jsonStr.toString());
    } catch (e) {
      Logger.log('JSON parse error for date ' + d + ': ' + e);
      return;
    }

    if (!Array.isArray(signals) || signals.length === 0) return;

    signals.forEach(s => {
      tradeRows.push([
        d,
        s.ticker             ?? '',
        s.action             ?? 'BUY',
        s.probability        ?? '',
        s.rsi                ?? '',
        s.macd_hist          ?? '',
        s.volume_ratio       ?? '',
        s.above_ema200 != null ? (s.above_ema200 ? 'TRUE' : 'FALSE') : '',
        s.signal_rank        ?? '',
        s.position_size_pct  ?? '',
      ]);
    });
  });

  if (tradeRows.length === 0) {
    sheet.getRange('A2').setValue('No TRADE signals found in Daily Log yet.')
      .setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  sheet.getRange(2, 1, tradeRows.length, headers.length).setValues(tradeRows);

  const end = tradeRows.length + 1;

  // Number formats
  sheet.getRange(`A2:A${end}`).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(`D2:D${end}`).setNumberFormat('0.0000');   // Probability
  sheet.getRange(`E2:E${end}`).setNumberFormat('0.00');     // RSI
  sheet.getRange(`F2:F${end}`).setNumberFormat('0.0000');   // MACD Hist
  sheet.getRange(`G2:G${end}`).setNumberFormat('0.00');     // Volume Ratio
  sheet.getRange(`J2:J${end}`).setNumberFormat('0"%"');     // Position Size

  // Conditional formatting on Probability column
  const probRange = sheet.getRange(`D2:D${end}`);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(0.60)
      .setBackground(C.PROB_HIGH)
      .setRanges([probRange])
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(0.55, 0.60)
      .setBackground(C.PROB_MID)
      .setRanges([probRange])
      .build(),
  ];
  sheet.setConditionalFormatRules(rules);
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB 4 — PERFORMANCE SUMMARY
// ═══════════════════════════════════════════════════════════════════════════════

function _buildPerformanceSummary(ss) {
  const sheet = _getOrCreate(ss, 'Performance Summary');
  _clearSheet(sheet);

  // Title
  sheet.getRange('A1').setValue('TRADING BOT — PERFORMANCE SUMMARY')
    .setFontSize(15).setFontWeight('bold').setFontColor(C.NAVY);
  sheet.getRange('A2')
    .setValue('All metrics auto-calculated from Daily Log & Trade Log.  Refresh: run refreshAllDerivedSheets()')
    .setFontColor('#888888').setFontSize(9);
  sheet.setRowHeight(1, 30);

  _setColumnWidths(sheet, [280, 170, 320]);

  let row = 4;

  // ── Section helper ──
  const section = (title) => {
    sheet.getRange(row, 1, 1, 3)
      .setValue(title).setFontWeight('bold').setFontSize(10)
      .setBackground(C.NAVY).setFontColor(C.WHITE);
    sheet.getRange(row, 2, 1, 2).setBackground(C.NAVY);
    row++;
  };

  const metric = (label, formula, fmt, note) => {
    sheet.getRange(row, 1).setValue(label).setFontWeight('bold');
    if (formula.startsWith('=')) {
      sheet.getRange(row, 2).setFormula(formula);
    } else {
      sheet.getRange(row, 2).setValue(formula);
    }
    if (fmt) sheet.getRange(row, 2).setNumberFormat(fmt);
    if (note) sheet.getRange(row, 3).setValue(note).setFontColor('#888888').setFontSize(9);

    // Zebra stripe
    if (row % 2 === 0) sheet.getRange(row, 1, 1, 3).setBackground('#f8f9fa');
    row++;
  };

  const spacer = () => { row++; };

  // ── Trade Activity ─────────────────────────────────────────────────────────
  section('TRADE ACTIVITY');
  metric('Total trading days logged',
    "=COUNTA('Daily Log'!B2:B)",
    '#,##0');
  metric('TRADE days',
    "=COUNTIF('Daily Log'!B2:B,\"TRADE\")",
    '#,##0');
  metric('NO TRADE days',
    "=COUNTIF('Daily Log'!B2:B,\"NO TRADE\")",
    '#,##0');
  metric('TRADE rate',
    `=IFERROR(COUNTIF('Daily Log'!B2:B,"TRADE")/COUNTA('Daily Log'!B2:B),0)`,
    '0.0%',
    'TRADE days ÷ total days');
  metric('Total signals generated',
    "=COUNTA('Trade Log'!B2:B)",
    '#,##0',
    'One row per signal in Trade Log');
  metric('Avg signals per TRADE day',
    `=IFERROR(COUNTA('Trade Log'!B2:B)/COUNTIF('Daily Log'!B2:B,"TRADE"),0)`,
    '0.0');
  spacer();

  // ── Signal Quality ─────────────────────────────────────────────────────────
  section('SIGNAL QUALITY');
  metric('Avg probability — all signals',
    "=IFERROR(AVERAGE('Trade Log'!D2:D),0)",
    '0.0000');
  metric('Avg probability — high-conf only (>0.60)',
    `=IFERROR(AVERAGEIF('Trade Log'!D2:D,">0.60",'Trade Log'!D2:D),0)`,
    '0.0000');
  metric('High-confidence signals (>0.60)',
    `=COUNTIF('Trade Log'!D2:D,">0.60")`,
    '#,##0');
  metric('Mid-confidence signals (0.55 – 0.60)',
    `=COUNTIFS('Trade Log'!D2:D,">=0.55",'Trade Log'!D2:D,"<=0.60")`,
    '#,##0');
  metric('Avg RSI on entry signals',
    "=IFERROR(AVERAGE('Trade Log'!E2:E),0)",
    '0.00');
  metric('Avg volume ratio on entry signals',
    "=IFERROR(AVERAGE('Trade Log'!G2:G),0)",
    '0.00');
  spacer();

  // ── Win Rate (placeholder) ─────────────────────────────────────────────────
  section('WIN RATE  (exit data required)');

  const pending = (label, note) => {
    sheet.getRange(row, 1).setValue(label).setFontWeight('bold');
    sheet.getRange(row, 2).setValue('—').setFontColor('#999999');
    sheet.getRange(row, 3).setValue(note).setFontColor(C.PENDING).setFontSize(9);
    if (row % 2 === 0) sheet.getRange(row, 1, 1, 3).setBackground('#f8f9fa');
    row++;
  };

  pending('Win rate',            'Requires exit price data from Phase 5 in Daily Log');
  pending('Avg gain on winners', 'Requires exit price data from Phase 5');
  pending('Avg loss on losers',  'Requires exit price data from Phase 5');
  pending('Profit factor',       'Requires exit price data from Phase 5');
  spacer();

  // ── TA Filter Stats ────────────────────────────────────────────────────────
  section('TA FILTER PIPELINE AVERAGES');
  metric('Avg universe size',
    "=IFERROR(AVERAGE('Daily Log'!C2:C),0)",
    '#,##0.0');
  metric('Avg tickers passing all TA filters',
    "=IFERROR(AVERAGE('Daily Log'!D2:D),0)",
    '#,##0.0');
  metric('Avg tickers passing ML threshold',
    "=IFERROR(AVERAGE('Daily Log'!E2:E),0)",
    '#,##0.0');
  metric('Avg TA pass rate (Passed TA ÷ Universe)',
    "=IFERROR(AVERAGE('Daily Log'!D2:D)/AVERAGE('Daily Log'!C2:C),0)",
    '0.0%');
  metric('Avg ML pass rate (Passed ML ÷ Passed TA)',
    "=IFERROR(AVERAGE('Daily Log'!E2:E)/AVERAGE('Daily Log'!D2:D),0)",
    '0.0%');
  spacer();

  // ── Most Signaled Tickers ──────────────────────────────────────────────────
  section('MOST FREQUENTLY SIGNALED TICKERS  (top 10)');

  // Sub-header row
  sheet.getRange(row, 1, 1, 3).setValues([['Ticker', 'Signal Count', 'Avg Probability']])
    .setFontWeight('bold').setBackground(C.SECTION_BG);
  row++;

  // QUERY pulls ranked ticker list directly from Trade Log
  sheet.getRange(row, 1).setFormula(
    "=IFERROR(" +
    "QUERY('Trade Log'!B2:D," +
    "\"SELECT B, COUNT(B), AVG(D) " +
    "WHERE B <> '' " +
    "GROUP BY B " +
    "ORDER BY COUNT(B) DESC " +
    "LIMIT 10 " +
    "LABEL B '', COUNT(B) '', AVG(D) ''\",0)," +
    "\"No trade signal data yet\")"
  );
  sheet.getRange(row, 3).setNumberFormat('0.0000');
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB 5 — FILTER ANALYTICS
// ═══════════════════════════════════════════════════════════════════════════════

function _buildFilterAnalytics(ss) {
  const src   = ss.getSheetByName('Daily Log');
  const sheet = _getOrCreate(ss, 'Filter Analytics');
  _clearSheet(sheet);

  // Headers
  const headers = [
    'Date',
    'Universe',
    'Passed EMA200', 'Passed RSI', 'Passed Volume', 'Passed MACD',
    'Passed ML',
    'EMA200 %', 'RSI %', 'Volume %', 'MACD %', 'ML %',
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  _styleHeaderRow(sheet, headers.length);
  _setColumnWidths(sheet, [110, 80, 115, 95, 110, 105, 85, 90, 70, 80, 80, 70]);

  const lastRow = src.getLastRow();
  if (lastRow < 2) {
    sheet.getRange('A2').setValue('No data yet — Daily Log is empty.')
      .setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  // Fetch all available columns from Daily Log (up to col L = index 11)
  const totalDLCols = Math.min(src.getLastColumn(), 12);
  const raw = src.getRange(2, 1, lastRow - 1, totalDLCols).getValues();
  const rows = raw.filter(r => r[DL.DATE] !== '');

  if (rows.length === 0) {
    sheet.getRange('A2').setValue('No data rows found in Daily Log.')
      .setFontColor(C.PENDING).setFontStyle('italic');
    return;
  }

  // Write raw columns A–G
  const rawData = rows.map(r => [
    r[DL.DATE],
    r[DL.UNIVERSE]  !== '' ? r[DL.UNIVERSE]  : null,
    r[DL.EMA200]    !== '' ? r[DL.EMA200]    : null,  // I (optional)
    r[DL.RSI]       !== '' ? r[DL.RSI]       : null,  // J (optional)
    r[DL.VOLUME]    !== '' ? r[DL.VOLUME]    : null,  // K (optional)
    r[DL.MACD]      !== '' ? r[DL.MACD]      : null,  // L (optional); fallback to Passed TA
    r[DL.PASSED_ML] !== '' ? r[DL.PASSED_ML] : null,
  ]);

  // If per-stage columns (I–L) are missing, use Passed TA for MACD col (last stage)
  const hasPerStage = rows.some(r => r[DL.EMA200] !== '');
  if (!hasPerStage) {
    rawData.forEach((row, i) => {
      row[5] = rows[i][DL.PASSED_TA] !== '' ? rows[i][DL.PASSED_TA] : null; // MACD ≈ Passed TA
    });
  }

  sheet.getRange(2, 1, rawData.length, 7).setValues(rawData);

  const end = rawData.length + 1;

  // Pass-rate formulas (H–L)
  for (let r = 2; r <= end; r++) {
    // EMA200 %: C/B
    sheet.getRange(r, 8).setFormula(`=IFERROR(C${r}/B${r},"")`);
    // RSI %: D/C  (or D/B if C is blank)
    sheet.getRange(r, 9).setFormula(`=IFERROR(IF(C${r}<>"",D${r}/C${r},D${r}/B${r}),"")`);
    // Volume %: E/D
    sheet.getRange(r, 10).setFormula(`=IFERROR(IF(D${r}<>"",E${r}/D${r},E${r}/B${r}),"")`);
    // MACD %: F/B (F = last TA stage)
    sheet.getRange(r, 11).setFormula(`=IFERROR(F${r}/B${r},"")`);
    // ML %: G/F
    sheet.getRange(r, 12).setFormula(`=IFERROR(G${r}/F${r},"")`);
  }

  // Number formats
  sheet.getRange(`A2:A${end}`).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(`B2:G${end}`).setNumberFormat('#,##0');
  sheet.getRange(`H2:L${end}`).setNumberFormat('0.0%');

  // Conditional formatting on pass-rate columns: green > 30%, yellow > 15%
  const rateRange = sheet.getRange(`H2:L${end}`);
  sheet.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(0.30).setBackground('#d9ead3').setRanges([rateRange]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(0.15, 0.30).setBackground('#fce8b2').setRanges([rateRange]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0.15).setBackground('#f4cccc').setRanges([rateRange]).build(),
  ]);

  // Note if per-stage data is missing
  if (!hasPerStage) {
    const noteRow = end + 2;
    sheet.getRange(noteRow, 1).setValue(
      '⚠  Columns C–F (EMA200 / RSI / Volume / MACD per-stage counts) will auto-populate once ' +
      'they are sent as columns I–L of Daily Log.  Currently showing only aggregate Passed TA ' +
      '(last filter stage) and Passed ML.  To add per-stage data, map ' +
      'filters_summary.passed_ema200, .passed_rsi, .passed_volume, .passed_macd.'
    ).setFontColor(C.PENDING).setFontSize(9).setWrap(true);
    sheet.setRowHeight(noteRow, 56);
    sheet.getRange(noteRow, 1, 1, 6).merge();
  }

  // ── Line chart: filter funnel over time ────────────────────────────────────
  if (rows.length >= 2) {
    // Series: Universe (B), Passed TA/MACD (F), Passed ML (G)
    const chart = sheet.newChart()
      .setChartType(Charts.ChartType.LINE)
      .addRange(sheet.getRange(1, 1, end, 1))   // Date
      .addRange(sheet.getRange(1, 2, end, 1))   // Universe
      .addRange(sheet.getRange(1, 6, end, 1))   // Passed TA (MACD col)
      .addRange(sheet.getRange(1, 7, end, 1))   // Passed ML
      .setPosition(end + (hasPerStage ? 3 : 8), 1, 0, 0)
      .setOption('title', 'Daily TA & ML Filter Funnel')
      .setOption('titleTextStyle', { fontSize: 14, bold: true })
      .setOption('hAxis', {
        title: 'Date',
        format: 'MMM d',
        slantedText: true,
        slantedTextAngle: 45,
      })
      .setOption('vAxis', { title: 'Ticker Count', minValue: 0 })
      .setOption('series', {
        0: { color: C.BLUE,   lineWidth: 2, pointSize: 3 },   // Universe
        1: { color: C.GREEN,  lineWidth: 2, pointSize: 3 },   // Passed TA
        2: { color: C.YELLOW, lineWidth: 2, pointSize: 3 },   // Passed ML
      })
      .setOption('legend', { position: 'bottom' })
      .setOption('curveType', 'function')
      .setOption('width', 860)
      .setOption('height', 400)
      .build();
    sheet.insertChart(chart);
  }

  // ── Bar chart: pass-rate % comparison ─────────────────────────────────────
  if (rows.length >= 2) {
    const rateChart = sheet.newChart()
      .setChartType(Charts.ChartType.AREA)
      .addRange(sheet.getRange(1, 1, end, 1))    // Date
      .addRange(sheet.getRange(1, 11, end, 1))   // MACD %
      .addRange(sheet.getRange(1, 12, end, 1))   // ML %
      .setPosition(end + (hasPerStage ? 30 : 35), 1, 0, 0)
      .setOption('title', 'TA → ML Pass Rates Over Time')
      .setOption('titleTextStyle', { fontSize: 14, bold: true })
      .setOption('hAxis', { title: 'Date', format: 'MMM d', slantedText: true })
      .setOption('vAxis', { title: 'Pass Rate', format: '0%', minValue: 0, maxValue: 1 })
      .setOption('series', {
        0: { color: C.GREEN,  lineWidth: 2, areaOpacity: 0.15 },
        1: { color: C.ORANGE, lineWidth: 2, areaOpacity: 0.15 },
      })
      .setOption('legend', { position: 'bottom' })
      .setOption('isStacked', false)
      .setOption('width', 860)
      .setOption('height', 380)
      .build();
    sheet.insertChart(rateChart);
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// SHARED UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════

function _getOrCreate(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function _clearSheet(sheet) {
  sheet.clearContents();
  sheet.clearFormats();
  sheet.clearConditionalFormatRules();
  sheet.getCharts().forEach(c => sheet.removeChart(c));
  const merges = sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).getMergedRanges();
  merges.forEach(m => m.breakApart());
}

function _styleHeaderRow(sheet, numCols) {
  const header = sheet.getRange(1, 1, 1, numCols);
  header
    .setBackground(C.NAVY)
    .setFontColor(C.WHITE)
    .setFontWeight('bold')
    .setFontSize(10)
    .setVerticalAlignment('middle')
    .setWrap(false);
  sheet.setFrozenRows(1);
  sheet.setRowHeight(1, 30);
}

function _setColumnWidths(sheet, widths) {
  widths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));
}

function _reorderSheets(ss) {
  const order = ['Daily Log', 'Equity Curve', 'Trade Log', 'Performance Summary', 'Filter Analytics'];
  order.reverse().forEach(name => {
    const s = ss.getSheetByName(name);
    if (s) ss.moveActiveSheet && ss.setActiveSheet(s) && ss.moveActiveSheet(1);
  });
  // Simpler approach: move each sheet to its target index
  order.forEach((name, idx) => {
    const s = ss.getSheetByName(name);
    if (s) {
      try { ss.moveActiveSheet(idx + 1); } catch(e) {}
    }
  });
}
