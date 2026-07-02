# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import base64
from odoo import models, fields, api
import secrets


class GoogleSheetConnectorConfig(models.Model):
    _name = "cr.google.sheet.connector.config"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Google Sheet Connector Configuration"

    cr_connector_url = fields.Char(
        "Connector Url",
        default=lambda self: self.env["ir.config_parameter"]
        .sudo()
        .get_param("web.base.url"),
        readonly=False,
        required=True,
    )
    cr_access_token = fields.Char("Access Token", readonly=False)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    def generate_token(self):
        """Generate a new API token."""
        token = secrets.token_hex(16)
        self.cr_access_token = token
        return token

    def generate_app_script(self):
        "Generates App Script."
        attachment = self.env["ir.attachment"].create(
            {
                "name": "google_script",
                "type": "binary",
                "datas": base64.b64encode(
                    b"""
function onOpen() {
  try {
    const ui = SpreadsheetApp.getUi();
    ui.createMenu('Odoo Connector')
      .addItem('Set URL and Token', 'setUrl')
      .addItem('Select Tables and Fetch Data', 'launchTableSelection')
      .addSeparator()
      .addItem('Setup Automatic Import Refresh', 'setupAutoRefresh')
      .addItem('Setup Automatic Export Refresh', 'setupAutoExport')
      .addItem('Refresh Now', 'refreshNow')
      .addSeparator()
      .addItem('Send Data To Odoo', 'showExportDialog')
      .addToUi();
  } catch (e) {
    console.warn('Failed to create menu (likely running in a context without UI): ' + e.message);
  }
}

function launchTableSelection() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = spreadsheet.getSheets();
  
  const preSelectedTables = [];
  const preSelectedFields = {};
  
  sheets.forEach(sheet => {
    const sheetName = sheet.getName();
    
    const lastCol = sheet.getLastColumn();
    if (lastCol > 0) {
      const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
      const validHeaders = headers.map(h => h && h.toString().trim()).filter(Boolean);
      if (validHeaders.length > 0) {
        preSelectedFields[sheetName] = validHeaders;
      }
    }
  });
  
  showTableSelectionDialog(preSelectedTables, preSelectedFields);
}

// REST OF THE APPS SCRIPT
function setUrl() {
  const url = Browser.inputBox('Enter Odoo API URL');
  if (url === 'cancel' || !url.trim()) {
    Browser.msgBox('URL configuration cancelled or is empty. API URL must be provided.');
    return;
  }
  
  const trimmedUrl = url.trim();
  if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
    Browser.msgBox('Invalid URL. The URL must start with http:// or https://');
    return;
  }

  const token = Browser.inputBox('Enter Odoo API Token');
  if (token === 'cancel' || !token.trim()) {
    Browser.msgBox('Token configuration cancelled or is empty. API Token must be provided.');
    return;
  }

  PropertiesService.getScriptProperties().setProperty('odooUrl', trimmedUrl.replace(/\/$/, ''));
  PropertiesService.getScriptProperties().setProperty('odootoken', token.trim());
  Browser.msgBox('API Url and Token Set successfully.');
}

function showExportDialog(preSelectedSheets = [], preSelectedColumns = {}) {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();

  let htmlContent = '';
  htmlContent += '<form id="sheetSelectionForm">';

  sheets.forEach(sheet => {
    htmlContent += `
      <input type="checkbox" name="sheets" value="${sheet.getName()}"
  ${preSelectedSheets.includes(sheet.getName()) ? 'checked' : ''}>${sheet.getName()}<br>
    `;
  });

  htmlContent += `
    <div class="button-container">
    <input type="button" value="Next: Select Columns" onclick="proceedToExportColumns()" class="fixed-button">
    </div>
  </form>
  `;

  htmlContent += `
  <script>
    const PRE_SELECTED_COLUMNS = ${JSON.stringify(preSelectedColumns)};
  </script>
  `;

  htmlContent += `
    <style>
      .fixed-button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
        cursor: pointer;
        position: fixed;
        bottom: 10px;
        right: 10px;
        border-radius: 5px;
      }
    </style>

    <script>
      function proceedToExportColumns() {
        const checkboxes = document.querySelectorAll('input[name="sheets"]:checked');
        const selectedSheets = Array.from(checkboxes).map(checkbox => checkbox.value);

        if (selectedSheets.length === 0) {
            alert("Please select at least one sheet.");
            return;
        }

        google.script.run
          .withSuccessHandler(() => google.script.host.close())
          .showExportColumnSelectionDialog(selectedSheets, PRE_SELECTED_COLUMNS);
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(400)
    .setHeight(300);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 1: Select Sheets to Export');
}

function showExportColumnSelectionDialog(selectedSheets, preSelectedColumns = {}) {
    let htmlContent = '';
    htmlContent += '<input type="text" id="exportColumnSearch" placeholder="Search columns..." style="width: 100%; box-sizing: border-box; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;">';
    htmlContent += '<form id="exportColumnSelectionForm">';

    selectedSheets.forEach(sheetName => {
        const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
        let headers = [];
        if (sheet) {
            const lastCol = sheet.getLastColumn();
            if (lastCol > 0) {
                headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
            }
        }

        htmlContent += `<div class="table-section">`;
        htmlContent += `<input type="hidden" class="selected-sheet-name" value="${sheetName}">`;
        const initialSelectedCount = preSelectedColumns[sheetName] ? preSelectedColumns[sheetName].length : 0;

        htmlContent += `<h4>${sheetName}
          <span id="count-export-${sheetName}" style="font-size: 0.9em; font-weight: normal; color: #555;">
            (${initialSelectedCount} selected)
          </span>
        </h4>`; 

        htmlContent += `
        <label style="font-weight:bold;">
            <input type="checkbox" onchange="toggleAllExport(this, '${sheetName}')"> Select All Columns
        </label><br>
        `;

        htmlContent += `<div class="fields-container" id="container-${sheetName}" style="max-height: 150px; overflow-y: auto; border: 1px solid #eee; padding: 5px;">`;

        if (headers && headers.length) {
            headers.forEach(header => {
              const checked =
                preSelectedColumns[sheetName] &&
                preSelectedColumns[sheetName].includes(header)
                  ? 'checked'
                  : '';

              htmlContent += `
                <div class="field-item">
                  <label>
                    <input type="checkbox"
                           name="columns-${sheetName}"
                           value="${header}"
                           ${checked}
                           onchange="updateExportCount('${sheetName}')">
                    ${header}
                  </label>
                </div>
              `;
            });
        } else {
             htmlContent += `No headers found in row 1.`;
        }
        htmlContent += `</div></div><hr>`;
    });

    htmlContent += '<div class="button-container">';
    htmlContent += '<input type="button" value="Back" onclick="goBack()" class="back-button">';
    htmlContent += '<input type="button" value="Export Data" onclick="exportDataFinal()" class="fixed-button">';
    htmlContent += '</div>';
    htmlContent += '</form>';

    htmlContent += `
    <style>
      .fixed-button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 15px 30px;
        font-size: 16px;
        cursor: pointer;
        position: fixed;  
        bottom: 10px;  
        left: 50%;
        transform: translateX(-50%); 
        z-index: 9999; 
        border-radius: 5px;
      }

      .back-button {
        background-color: #999;
        color: white;
        border: none;
        padding: 12px 25px;
        font-size: 15px;
        cursor: pointer;
        position: fixed;
        bottom: 10px;
        left: 10px;
        border-radius: 5px;
      }

      #exportColumnSelectionForm { margin-bottom: 70px; }
      .table-section { margin-bottom: 15px; }
    </style>
    <script>
        document.getElementById('exportColumnSearch').addEventListener('keyup', function() {
            var input = this.value.toLowerCase();
            var items = document.getElementsByClassName('field-item');
            for (var i = 0; i < items.length; i++) {
              var text = items[i].textContent || items[i].innerText;
              if (text.toLowerCase().indexOf(input) > -1) {
                items[i].style.display = "";
              } else {
                items[i].style.display = "none";
              }
            }
        });

        function toggleAllExport(source, sheetName) {
            const checkboxes = document.querySelectorAll('input[name="columns-' + sheetName + '"]');
            for(var i=0, n=checkboxes.length;i<n;i++) {
                checkboxes[i].checked = source.checked;
            }
            updateExportCount(sheetName);
        }

        function updateExportCount(sheetName) {
            const checkboxes = document.querySelectorAll('input[name="columns-' + sheetName + '"]:checked');
            const count = checkboxes.length;
            const span = document.getElementById('count-export-' + sheetName);
            if(span) {
                span.innerText = '(' + count + ' selected)';
            }
        }

        function exportDataFinal() {
            const sheetsData = {};

            const sheetInputs = document.querySelectorAll('.selected-sheet-name');
            sheetInputs.forEach(input => {
               sheetsData[input.value] = [];
            });

            const inputs = document.querySelectorAll('input[type="checkbox"]:checked');

            inputs.forEach(input => {
                if (input.name.startsWith("columns-")) {
                    const sheetName = input.name.substring(8);
                    if (!sheetsData[sheetName]) {
                        sheetsData[sheetName] = [];
                    }
                    sheetsData[sheetName].push(input.value);
                }
            });

            google.script.run
              .withSuccessHandler(() => {
                google.script.host.close();
              })
              .exportDataWithColumns(sheetsData);
        }

        function getSelectedColumns() {
            const data = {};

            document.querySelectorAll('.selected-sheet-name').forEach(el => {
              data[el.value] = [];
            });

            document
              .querySelectorAll('input[type="checkbox"]:checked')
              .forEach(cb => {
                if (cb.name.startsWith('columns-')) {
                  const sheet = cb.name.replace('columns-', '');
                  data[sheet].push(cb.value);
                }
              });

            return data;
        }

        function goBack() {
            const sheets = [];
            document.querySelectorAll('.selected-sheet-name').forEach(el => {
              sheets.push(el.value);
            });

            const columns = getSelectedColumns();

            google.script.run
              .withSuccessHandler(() => google.script.host.close())
              .showExportDialogWithColumns(sheets, columns);
        }
    </script>
    `;

    const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
        .setWidth(600)
        .setHeight(700);

    SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 2: Select Columns to Export');
}

function showExportDialogWithColumns(preSelectedSheets, preSelectedColumns) {
  showExportDialog(preSelectedSheets, preSelectedColumns);
}


function setupAutoExport() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();
  const sheetNames = sheets.map(s => s.getName());

  let html = `<form id="autoExportForm">`;

  sheetNames.forEach(name => {
    html += `
      <div style="margin-bottom:10px;">
        <input type="checkbox" name="sheet" value="${name}">
        <b>${name}</b>
        <input type="number"
               name="interval-${name}"
               placeholder="Hours"
               min="1"
               style="width:80px; margin-left:10px;">
      </div>
    `;
  });

  html += `
    <br>
    <input type="button" value="Create Export Schedulers" onclick="submitForm()">
  </form>

  <script>
    function submitForm() {
      const result = {};
      document.querySelectorAll('input[name="sheet"]:checked').forEach(cb => {
        const intervalInput = document.querySelector(
          'input[name="interval-' + cb.value + '"]'
        );
        const interval = parseInt(intervalInput.value, 10);
        if (!interval || interval <= 0) {
          alert('Invalid interval for ' + cb.value);
          return;
        }
        result[cb.value] = interval;
      });

      if (Object.keys(result).length === 0) {
        alert('Select at least one sheet.');
        return;
      }

      google.script.run
        .withSuccessHandler(() => google.script.host.close())
        .createExportSheetSchedulers(result);
    }
  </script>
  `;

  SpreadsheetApp.getUi().showModalDialog(
    HtmlService.createHtmlOutput(html).setWidth(450).setHeight(400),
    'Automatic Export Refresh'
  );
}

function createExportSheetSchedulers(sheetIntervals) {
  const props = PropertiesService.getScriptProperties();

  const config = {};

  Object.keys(sheetIntervals).forEach(sheetName => {
    config[sheetName] = {
      interval: sheetIntervals[sheetName], // hours
      lastRun: 0
    };
  });

  props.setProperty('AUTO_EXPORT_SCHEDULE', JSON.stringify(config));

  // Ensure only ONE export trigger exists
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'autoExportScheduler') {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger('autoExportScheduler')
    .timeBased()
    .everyHours(1) // base heartbeat
    .create();

  SpreadsheetApp.getActiveSpreadsheet().toast(
    'Auto export refresh configured'
  );
}

function autoExportScheduler() {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('AUTO_EXPORT_SCHEDULE');
  if (!raw) return;

  const config = JSON.parse(raw);
  const now = Date.now();

  Object.keys(config).forEach(sheetName => {
    const entry = config[sheetName];
    const intervalMs = entry.interval * 60 * 60 * 1000;

    if (!entry.lastRun || now - entry.lastRun >= intervalMs) {
      try {
        const sheetMap = buildSheetColumnMap([sheetName]);

        if (sheetMap[sheetName]) {
          exportDataWithColumns(sheetMap);
          entry.lastRun = now;
          console.log('Auto exported:', sheetName);
        } else {
          console.warn('No valid columns for auto export:', sheetName);
        }
      } catch (e) {
        console.error('Auto export failed:', sheetName, e);
      }
    }
  });

  props.setProperty('AUTO_EXPORT_SCHEDULE', JSON.stringify(config));
}

function buildSheetColumnMap(sheetNames) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const map = {};

  sheetNames.forEach(sheetName => {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet) return;

    const lastCol = sheet.getLastColumn();
    if (!lastCol) return;

    const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    const validHeaders = headers
      .map(h => h && h.toString().trim())
      .filter(Boolean);

    if (validHeaders.length) {
      map[sheetName] = validHeaders;
    }
  });

  return map;
}

function fetchAvailableTables(url) {
  const urli = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const token = PropertiesService.getScriptProperties().getProperty('odootoken');
  const dbListUrl = urli + '/ht';

  const response = UrlFetchApp.fetch(dbListUrl, {
      method: 'get',
      headers: {
        'X-Odoo-Access-Token': token
      },
      muteHttpExceptions: true
  });

  const dbList = JSON.parse(response.getContentText());
  return dbList;
}

function fetchModelFields(model) {
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const token = PropertiesService.getScriptProperties().getProperty('odootoken');
  const payload = { model: model };
  const options = {
      method: 'post',
      contentType: 'text/plain',
      headers: {
        'X-Odoo-Access-Token': token
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
  };

  try {
      const response = UrlFetchApp.fetch(url + '/get_model_fields', options);
      return JSON.parse(response.getContentText());
  } catch (e) {
      return [];
  }
}

function showTableSelectionDialog(preSelectedTables = [], preSelectedFields = {}) {
  if (typeof preSelectedFields === 'string') {
    try {
      preSelectedFields = JSON.parse(preSelectedFields);
    } catch (e) {
      preSelectedFields = {};
    }
  }
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');

  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }

  const tables = fetchAvailableTables();

  if (!tables) {
    return;
  }

  let htmlContent = '';
  htmlContent += '<input type="text" id="tableSearch" placeholder="Search tables..." style="width: 100%; box-sizing: border-box; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;">';
  htmlContent += '<form id="tableSelectionForm">';
  htmlContent += '<div class="button-container">';
  htmlContent += '<input type="button" value="Next: Select Columns" onclick="proceedToColumns()" class="fixed-button">';
  htmlContent += '</div>';

  Object.keys(tables).forEach(table => {
    htmlContent += `
      <div class="checkbox-item" style="margin-bottom: 5px;">
        <input type="checkbox" name="tables" value="${table}"
  ${preSelectedTables.includes(table) ? 'checked' : ''}> ${tables[table]}
      </div>
    `;
  });

  htmlContent += '</form>';

  htmlContent += `
    <script>
      const PRE_SELECTED_FIELDS = ${JSON.stringify(preSelectedFields)};
    </script>
    `;

   htmlContent += `
    <style>
      .fixed-button {
        background-color: #6a4c9c;
        color: white;
        border: none;
        padding: 15px 30px;
        font-size: 16px;
        cursor: pointer;
        position: fixed;  
        bottom: 10px;  
        left: 80%;
        transform: translateX(-50%); 
        z-index: 9999; 
        border-radius: 5px;
      }

      #tableSelectionForm {
        margin-bottom: 80px; 
        max-height: 400px; 
        overflow-y: auto;
        padding: 10px;
      }
    </style>

    <script>
      document.getElementById('tableSearch').addEventListener('keyup', function() {
        var input = this.value.toLowerCase();
        var items = document.getElementsByClassName('checkbox-item');
        for (var i = 0; i < items.length; i++) {
          var text = items[i].textContent || items[i].innerText;
          if (text.toLowerCase().indexOf(input) > -1) {
            items[i].style.display = "";
          } else {
            items[i].style.display = "none";
          }
        }
      });

      function proceedToColumns() {
        const checkboxes = document.querySelectorAll('input[name="tables"]:checked');
        const selectedTables = Array.from(checkboxes).map(checkbox => checkbox.value);

        if (selectedTables.length === 0) {
            alert("Please select at least one table.");
            return;
        }

        google.script.run
          .withSuccessHandler(() => {
          })
          .showColumnSelectionDialog(selectedTables, JSON.stringify(PRE_SELECTED_FIELDS));
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(500)
    .setHeight(600);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 1: Select Tables');
}

function showColumnSelectionDialog(selectedTables, preSelectedFields = {}) {
    if (typeof preSelectedFields === 'string') {
        try {
            preSelectedFields = JSON.parse(preSelectedFields);
        } catch (e) {
            preSelectedFields = {};
        }
    }
    let htmlContent = '';
    htmlContent += '<input type="text" id="columnSearch" placeholder="Search fields..." style="width: 100%; box-sizing: border-box; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;">';
    htmlContent += '<form id="columnSelectionForm">';

    selectedTables.forEach(table => {
        const fields = fetchModelFields(table);
        htmlContent += `<div class="table-section">`;
        htmlContent += `<input type="hidden" class="selected-table-name" value="${table}">`;

        const initialCount = preSelectedFields[table]
          ? preSelectedFields[table].length
          : 0;
        htmlContent += `<h4>${table} <span id="count-${table}" style="font-size: 0.9em; font-weight: normal; color: #555;">(${initialCount} selected)</span></h4>`;

        htmlContent += `
        <label style="font-weight:bold;">
            <input type="checkbox" onchange="toggleAll(this, '${table}')"> Select All Fields
        </label><br>
        `;

        htmlContent += `<div class="fields-container" id="container-${table}" style="max-height: 150px; overflow-y: auto; border: 1px solid #eee; padding: 5px;">`;

        if (fields && fields.length) {
            fields.forEach(f => {
                const checked =
                  preSelectedFields[table] &&
                  preSelectedFields[table].includes(f.name)
                    ? 'checked'
                    : '';

                htmlContent += `
                  <div class="field-item">
                    <label>
                      <input type="checkbox"
                             name="fields-${table}"
                             value="${f.name}"
                             ${checked}
                             onchange="updateCount('${table}')">
                      ${f.label} (${f.name})
                    </label>
                  </div>
                `;
            });
        } else {
             htmlContent += `No fields found or error fetching fields.`;
        }
        htmlContent += `</div></div><hr>`;
    });

    htmlContent += '<div class="button-container">';
    htmlContent += '<input type="button" value="Back" onclick="goBack()" class="back-button">';
    htmlContent += '<input type="button" value="Fetch Data" onclick="fetchDataFinal()" class="fixed-button">';
    htmlContent += '</div>';
    htmlContent += '</form>';

    htmlContent += `
    <style>
      .fixed-button {
        background-color: #6a4c9c;
        color: white;
        border: none;
        padding: 15px 30px;
        font-size: 16px;
        cursor: pointer;
        position: fixed;  
        bottom: 10px;  
        left: 50%;
        transform: translateX(-50%); 
        z-index: 9999; 
        border-radius: 5px;
      }

      .back-button {
        background-color: #999;
        color: white;
        border: none;
        padding: 12px 25px;
        font-size: 15px;
        cursor: pointer;
        position: fixed;
        bottom: 10px;
        left: 10px;
        border-radius: 5px;
      }

      #columnSelectionForm { margin-bottom: 70px; }
      .table-section { margin-bottom: 15px; }
    </style>
    <script>
        document.getElementById('columnSearch').addEventListener('keyup', function() {
            var input = this.value.toLowerCase();
            var items = document.getElementsByClassName('field-item');
            for (var i = 0; i < items.length; i++) {
              var text = items[i].textContent || items[i].innerText;
              if (text.toLowerCase().indexOf(input) > -1) {
                items[i].style.display = "";
              } else {
                items[i].style.display = "none";
              }
            }
        });

        function toggleAll(source, table) {
            const checkboxes = document.querySelectorAll('input[name="fields-' + table + '"]');
            for(var i=0, n=checkboxes.length;i<n;i++) {
                checkboxes[i].checked = source.checked;
            }
            updateCount(table);
        }

        function updateCount(table) {
            const checkboxes = document.querySelectorAll('input[name="fields-' + table + '"]:checked');
            const count = checkboxes.length;
            const span = document.getElementById('count-' + table);
            if(span) {
                span.innerText = '(' + count + ' selected)';
            }
        }

        function fetchDataFinal() {
            const tablesData = {};

            const tableInputs = document.querySelectorAll('.selected-table-name');
            tableInputs.forEach(input => {
               tablesData[input.value] = [];
            });

            const inputs = document.querySelectorAll('input[type="checkbox"]:checked');
            inputs.forEach(input => {
                if (input.name.startsWith("fields-")) {
                    const table = input.name.substring(7);
                    if (!tablesData[table]) {
                        tablesData[table] = [];
                    }
                    tablesData[table].push(input.value);
                }
            });

            google.script.run
              .withSuccessHandler(() => {
                google.script.host.close();
              })
              .fetchDataWithColumns(tablesData);
        }

        function goBack() {
          const tables = [];
          document.querySelectorAll('.selected-table-name').forEach(el => {
            tables.push(el.value);
          });

          const fields = getSelectedFields();

          google.script.run
            .withSuccessHandler(() => google.script.host.close())
            .showTableSelectionDialog(tables, JSON.stringify(fields));
        }

        function getSelectedFields() {
          const data = {};

          document.querySelectorAll('.selected-table-name').forEach(el => {
            data[el.value] = [];
          });

          document.querySelectorAll('input[type="checkbox"]:checked')
            .forEach(cb => {
              if (cb.name.startsWith('fields-')) {
                const table = cb.name.replace('fields-', '');
                data[table].push(cb.value);
              }
            });

          return data;
        }
    </script>
    `;

    const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
        .setWidth(600)
        .setHeight(700);

    SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 2: Select Columns');
}

function fetchDataWithColumns(tablesAndFields) {
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }

  const tables = Object.keys(tablesAndFields);
  const BATCH_SIZE = 10000;

  tables.forEach(function (table, index) {
    const fields = tablesAndFields[table];
    let offset = 0;
    let hasMore = true;
    let firstBatch = true;

    SpreadsheetApp.getActiveSpreadsheet().toast('Fetching ' + table + '...');

    while (hasMore) {
        try {
            const data = fetchTableDataFromOdoo(url, table, fields, BATCH_SIZE, offset);

            if (data && data.error) {
                 SpreadsheetApp.getActiveSpreadsheet().toast('Error fetching ' + table + ': ' + data.error);
                 console.error('Error fetching ' + table + ': ' + data.error);
                 hasMore = false;
                 break;
            }

            if (Array.isArray(data) && data.length > 0) {
                writeDataToSheet(table, data, !firstBatch);
                offset += data.length;

                if (data.length < BATCH_SIZE) {
                    hasMore = false;
                }
                firstBatch = false;
                SpreadsheetApp.getActiveSpreadsheet().toast('Fetched ' + offset + ' records for ' + table);
            } else {
                if (firstBatch) {
                     SpreadsheetApp.getActiveSpreadsheet().toast('No data available for table ' + table);
                }
                hasMore = false;
            }
        } catch (error) {
            SpreadsheetApp.getActiveSpreadsheet().toast('Exception fetching ' + table + ': ' + error.message);
            console.error('Exception fetching ' + table + ':', error);
            hasMore = false;
            break;
        }
    }
  });
  SpreadsheetApp.getActiveSpreadsheet().toast('Process Completed.');
}

function fetchTableDataFromOdoo(url, table, fields, limit, offset) {
   if (!url) {
       console.error('No URL provided');
       return {error: 'No URL configured'};
   }

   const token = PropertiesService.getScriptProperties().getProperty('odootoken');
   const payload = {};
   if (fields && fields.length > 0) {
       payload['fields'] = fields;
   }
   if (limit) payload['limit'] = limit;
   if (offset !== undefined) payload['offset'] = offset;

   try {
       console.log('Fetching from: ' + url + '/get_table/' + table);
       console.log('Payload: ' + JSON.stringify(payload));

       const response = UrlFetchApp.fetch(url + '/get_table/' + table, {
         method: 'post',
         contentType: 'text/plain',
         headers: {
           'X-Odoo-Access-Token': token
         },
         payload: JSON.stringify(payload),
         muteHttpExceptions: true
       });

       const responseCode = response.getResponseCode();
       const responseText = response.getContentText();

       console.log('Response code: ' + responseCode);
       console.log('Response: ' + responseText.substring(0, 200));

       if (responseCode !== 200) {
           console.error('HTTP Error ' + responseCode + ': ' + responseText);
           return {error: 'HTTP ' + responseCode + ': ' + responseText};
       }

       const result = JSON.parse(responseText);
       return result;
   } catch (e) {
       console.error('Exception in fetchTableDataFromOdoo: ' + e.message);
       return {error: e.message};
   }
}

function writeDataToSheet(table, data, append) {
  let sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(table);
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet(table);
  }

  if (!append) {
      sheet.clear();
      sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).clearFormat().setNumberFormat("General");
  }

  if (data && data.error) {
     SpreadsheetApp.getActiveSpreadsheet().toast('Error writing ' + table + ': ' + data.error);
     console.error('Error writing ' + table + ': ' + data.error);
     return;
  }

  if (Array.isArray(data) && data.length > 0) {
    const headers = Object.keys(data[0]);

    if (!append) {
        sheet.appendRow(headers);  
    }

    const rows = data.map(row => headers.map(header => row[header] || ''));

    const startRow = sheet.getLastRow() + 1;
    sheet.getRange(startRow, 1, rows.length, headers.length).setValues(rows);

    SpreadsheetApp.getActiveSpreadsheet().toast('Written ' + rows.length + ' rows to ' + table);
  } else if (!append) {
    SpreadsheetApp.getActiveSpreadsheet().toast('No data available for table ' + table);
  }
}

function fetchData(selectedTables) {
   const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
   const BATCH_SIZE = 10000;

   selectedTables.forEach(function (table) {
     let fields = null;
     const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(table);

     if (sheet) {
        const lastCol = sheet.getLastColumn();
        if (lastCol > 0) {
            const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
            const validHeaders = headers.filter(h => h && h.toString().trim() !== "");
            if (validHeaders.length > 0) {
                fields = validHeaders;
            }
        }
     }

    let offset = 0;
    let hasMore = true;
    let firstBatch = true;

    SpreadsheetApp.getActiveSpreadsheet().toast('Auto-refreshing ' + table + '...');

    while (hasMore) {
         const data = fetchTableDataFromOdoo(url, table, fields, BATCH_SIZE, offset);

         if (data && data.error) {
             console.error('Error auto-refreshing ' + table + ': ' + data.error);
             hasMore = false;
             break;
         }

         if (Array.isArray(data) && data.length > 0) {
             writeDataToSheet(table, data, !firstBatch);
             offset += data.length;
             if (data.length < BATCH_SIZE) {
                 hasMore = false;
             }
             firstBatch = false;
         } else {
             hasMore = false;
         }
    }
   });
}

function exportDataWithColumns(sheetsAndColumns) {
  PropertiesService.getScriptProperties().setProperty(
      'AUTO_EXPORT_SELECTIONS',
      JSON.stringify(sheetsAndColumns)
  );

  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const token = PropertiesService.getScriptProperties().getProperty('odootoken');
  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }

  const sheetNames = Object.keys(sheetsAndColumns);
  const BATCH_SIZE = 10000;
  sheetNames.forEach(sheetName => {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
    if (!sheet) return;

    const fullData = sheet.getDataRange().getValues();
    if (fullData.length <= 1) return;

    const allHeaders = fullData[0];
    let selectedHeaders = sheetsAndColumns[sheetName];

    if (!selectedHeaders || selectedHeaders.length === 0) {
        selectedHeaders = allHeaders;
    }

    const idIndex = allHeaders.indexOf('id');
    if (idIndex !== -1) {
      if (!selectedHeaders.includes('id')) {
        selectedHeaders = ['id'].concat(selectedHeaders);
        SpreadsheetApp.getActiveSpreadsheet().toast('Auto-added "id" column for ' + sheetName);
      }
    } else {
      SpreadsheetApp.getActiveSpreadsheet().toast('Warning: No "id" column found in ' + sheetName + '. Updates may fail.');
      console.warn('No "id" column found in sheet: ' + sheetName);
    }

    const totalRows = fullData.length - 1;
    let processedCount = 0;

    SpreadsheetApp.getActiveSpreadsheet().toast('Exporting ' + sheetName + ': 0/' + totalRows);
    for (let i = 1; i < fullData.length; i += BATCH_SIZE) {
        const end = Math.min(i + BATCH_SIZE, fullData.length);
        const batchRows = fullData.slice(i, end);

        const filteredData = [];
        filteredData.push(selectedHeaders);

        batchRows.forEach(row => {
            const newRow = [];
            selectedHeaders.forEach(header => {
                const index = allHeaders.indexOf(header);
                if (index !== -1) {
                    newRow.push(row[index]);
                } else {
                    newRow.push('');
                }
            });
            filteredData.push(newRow);
        });

        const payload = {
          table: sheetName,
          data: filteredData
        };
        const token = PropertiesService.getScriptProperties().getProperty('odootoken');
        const options = {
          method: 'post',
          contentType: 'text/plain',
          headers: {
            'X-Odoo-Access-Token': token
          },
          muteHttpExceptions: true,
          payload: JSON.stringify(payload)
        };
        try {
          const response = UrlFetchApp.fetch(url + '/send_data', options);
          const responseCode = response.getResponseCode();
          if (responseCode !== 200) {
              const resText = response.getContentText();
              console.error('Export failed for batch ' + i + ': ' + resText);
              SpreadsheetApp.getActiveSpreadsheet().toast('Failed batch ' + i + '-' + end);
          } else {
              processedCount += batchRows.length;
              SpreadsheetApp.getActiveSpreadsheet().toast('Exporting ' + sheetName + ': ' + processedCount + '/' + totalRows);
          }
        } catch (error) {
          SpreadsheetApp.getActiveSpreadsheet().toast('Error exporting batch. Check logs.');
          console.error(error);
        }
    }
    SpreadsheetApp.getActiveSpreadsheet().toast('Export Completed for ' + sheetName);
  });
}

function setupAutoRefresh() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();
  const sheetNames = sheets.map(s => s.getName());

  let html = `<form id="autoRefreshForm">`;

  sheetNames.forEach(name => {
    html += `
      <div style="margin-bottom:10px;">
        <input type="checkbox" name="sheet" value="${name}">
        <b>${name}</b>
        <input type="number"
               name="interval-${name}"
               placeholder="Hours"
               min="1"
               style="width:80px; margin-left:10px;">
      </div>
    `;
  });

  html += `
    <br>
    <input type="button" value="Create Schedulers" onclick="submitForm()">
  </form>

  <script>
    function submitForm() {
      const result = {};
      document.querySelectorAll('input[name="sheet"]:checked').forEach(cb => {
        const intervalInput = document.querySelector(
          'input[name="interval-' + cb.value + '"]'
        );
        const interval = parseInt(intervalInput.value, 10);
        if (!interval || interval <= 0) {
          alert('Invalid interval for ' + cb.value);
          return;
        }
        result[cb.value] = interval;
      });

      if (Object.keys(result).length === 0) {
        alert('Select at least one sheet.');
        return;
      }

      google.script.run
        .withSuccessHandler(() => google.script.host.close())
        .createSheetSchedulers(result);
    }
  </script>
  `;

  SpreadsheetApp.getUi().showModalDialog(
    HtmlService.createHtmlOutput(html).setWidth(450).setHeight(400),
    'Automatic Import Refresh'
  );
}

function createSheetSchedulers(sheetIntervals) {
  const props = PropertiesService.getScriptProperties();
  const now = Date.now();

  const config = {};

  Object.keys(sheetIntervals).forEach(sheetName => {
    config[sheetName] = {
      interval: sheetIntervals[sheetName], // hours
      lastRun: 0
    };
  });

  props.setProperty('AUTO_IMPORT_CONFIG', JSON.stringify(config));

  // Ensure only ONE trigger exists
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'autoImportScheduler') {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger('autoImportScheduler')
    .timeBased()
    .everyHours(1) // base heartbeat
    .create();

  SpreadsheetApp.getActiveSpreadsheet().toast(
    'Auto import refresh configured'
  );
}

function autoImportScheduler() {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('AUTO_IMPORT_CONFIG');

  if (!raw) return;

  const config = JSON.parse(raw);
  const now = Date.now();

  Object.keys(config).forEach(sheetName => {
    const entry = config[sheetName];
    const intervalMs = entry.interval * 60 * 60 * 1000;

    if (!entry.lastRun || now - entry.lastRun >= intervalMs) {
      try {
        fetchData([sheetName]);
        entry.lastRun = now;
        console.log('Auto imported:', sheetName);
      } catch (e) {
        console.error('Auto import failed:', sheetName, e);
      }
    }
  });

  props.setProperty('AUTO_IMPORT_CONFIG', JSON.stringify(config));
}

function refreshNow() {
  showRefreshSelectionDialog();   
} 

function showRefreshSelectionDialog() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();

  let html = '<form id="refreshForm">';
  html += '<h3>Select sheets to refresh</h3>';

  sheets.forEach(sheet => {
    html += `
      <div style="margin-bottom:6px;">
        <input type="checkbox" name="sheets" value="${sheet.getName()}">
        ${sheet.getName()}
      </div>
    `;
  });

  html += `
    <div style="margin-top:15px;">
      <input type="button" value="Refresh Selected"
        onclick="refreshSelected()"
        style="padding:10px 20px;">
    </div>
  </form>

  <script>
    function refreshSelected() {
      const selected = [];
      document.querySelectorAll('input[name="sheets"]:checked')
        .forEach(cb => selected.push(cb.value));

      if (selected.length === 0) {
        alert('Please select at least one sheet.');
        return;
      }

      google.script.run
        .withSuccessHandler(() => google.script.host.close())
        .refreshSelectedSheets(selected);
    }
  </script>
  `;

  SpreadsheetApp.getUi().showModalDialog(
    HtmlService.createHtmlOutput(html).setWidth(350).setHeight(400),
    'Refresh Selected Sheets'
  );
}

function refreshSelectedSheets(selectedSheets) {
  if (!selectedSheets || selectedSheets.length === 0) {
    return;
  }
  fetchData(selectedSheets);
}

               """
                ).decode("utf-8"),
                "mimetype": "application/javascript",
            }
        )
        self.message_post(
            body="Here is the generated Google Apps Script.",
            attachment_ids=[attachment.id],
        )
