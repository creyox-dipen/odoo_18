# -*- coding: utf-8 -*-
# Part of Creyox Technologies

import base64
from odoo import models, fields, api
import secrets


class GoogleSheetConnectorConfig(models.Model):
    _name = 'cr.google.sheet.connector.config'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Google Sheet Connector Configuration'

    cr_connector_url = fields.Char('Connector Url',
                                   default=lambda self: self.env["ir.config_parameter"].sudo().get_param(
                                       "web.base.url"), readonly=False, required=True)
    cr_access_token = fields.Char('Access Token', readonly=False)

    def generate_token(self):
        """Generate a new API token."""
        token = secrets.token_hex(16)
        self.env["ir.config_parameter"].sudo().set_param("access.token", token)
        self.cr_access_token = token
        return token

    def generate_app_script(self):
        "Generates App Script."
        attachment = self.env['ir.attachment'].create({
            'name': 'google_script',
            'type': 'binary',
            'datas': base64.b64encode(b"""
function onOpen() {
  try {
    const ui = SpreadsheetApp.getUi();
    ui.createMenu('Odoo Connector')
      .addItem('Set URL and Token', 'setUrl')
      .addItem('Select Tables and Fetch Data', 'showTableSelectionDialog')
      .addSeparator()
      .addItem('Setup Automatic Refresh', 'setupAutoRefresh')
      .addItem('Refresh Now', 'refreshNow')
      .addSeparator()
      .addItem('Send Data To Odoo', 'showExportDialog')
      .addToUi();
  } catch (e) {
    console.warn('Failed to create menu (likely running in a context without UI): ' + e.message);
  }
}

function setUrl() {
  const url = Browser.inputBox('Enter Odoo API URL');
  const token = Browser.inputBox('Enter Odoo API Token');
  PropertiesService.getScriptProperties().setProperty('odooUrl', url);
  PropertiesService.getScriptProperties().setProperty('odootoken', token);
  Browser.msgBox('API Url and Token Set successfully.');
}

function showExportDialog() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();

  let htmlContent = '';
  htmlContent += '<form id="sheetSelectionForm">';

  sheets.forEach(sheet => {
    htmlContent += `
      <input type="checkbox" name="sheets" value="${sheet.getName()}">${sheet.getName()}<br>
    `;
  });

  htmlContent += `
    <div class="button-container">
    <input type="button" value="Next: Select Columns" onclick="proceedToExportColumns()" class="fixed-button">
    </div>
  </form>
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
          .withSuccessHandler(() => {
            // google.script.host.close(); // Don't close, let server open next dialog
          })
          .showExportColumnSelectionDialog(selectedSheets);
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(400)
    .setHeight(300);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 1: Select Sheets to Export');
}

function showExportColumnSelectionDialog(selectedSheets) {
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
        htmlContent += `<h4>${sheetName} <span id="count-export-${sheetName}" style="font-size: 0.9em; font-weight: normal; color: #555;">(0 selected)</span></h4>`;
        
        htmlContent += `
        <label style="font-weight:bold;">
            <input type="checkbox" onchange="toggleAllExport(this, '${sheetName}')"> Select All Columns
        </label><br>
        `;
        
        htmlContent += `<div class="fields-container" id="container-${sheetName}" style="max-height: 150px; overflow-y: auto; border: 1px solid #eee; padding: 5px;">`;
        
        if (headers && headers.length) {
            headers.forEach(header => {
                htmlContent += `
                  <div class="field-item">
                  <label>
                    <input type="checkbox" name="columns-${sheetName}" value="${header}" onchange="updateExportCount('${sheetName}')"> ${header}
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
    </script>
    `;
    
    const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
        .setWidth(600)
        .setHeight(700);

    SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 2: Select Columns to Export');
}

function fetchAvailableTables(url) {
  const urli = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const dbListUrl = urli + '/ht';

  const response = UrlFetchApp.fetch(dbListUrl, {
      method: 'get',
      muteHttpExceptions: true
  });

  const dbList = JSON.parse(response.getContentText());
  return dbList;
}

function fetchModelFields(model) {
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const payload = { model: model };
  const options = {
      method: 'post',
      contentType: 'application/json',
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

function showTableSelectionDialog() {
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
        <input type="checkbox" name="tables" value="${table}"> ${tables[table]}
      </div>
    `;
  });

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
          .showColumnSelectionDialog(selectedTables);
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(500)
    .setHeight(600);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Step 1: Select Tables');
}

function showColumnSelectionDialog(selectedTables) {
    let htmlContent = '';
    htmlContent += '<input type="text" id="columnSearch" placeholder="Search fields..." style="width: 100%; box-sizing: border-box; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px;">';
    htmlContent += '<form id="columnSelectionForm">';
    
    selectedTables.forEach(table => {
        const fields = fetchModelFields(table);
        htmlContent += `<div class="table-section">`;
        htmlContent += `<input type="hidden" class="selected-table-name" value="${table}">`;
        htmlContent += `<h4>${table} <span id="count-${table}" style="font-size: 0.9em; font-weight: normal; color: #555;">(0 selected)</span></h4>`;
        
        htmlContent += `
        <label style="font-weight:bold;">
            <input type="checkbox" onchange="toggleAll(this, '${table}')"> Select All Fields
        </label><br>
        `;
        
        htmlContent += `<div class="fields-container" id="container-${table}" style="max-height: 150px; overflow-y: auto; border: 1px solid #eee; padding: 5px;">`;
        
        if (fields && fields.length) {
            fields.forEach(f => {
                htmlContent += `
                  <div class="field-item">
                  <label>
                    <input type="checkbox" name="fields-${table}" value="${f.name}" onchange="updateCount('${table}')"> ${f.label} (${f.name})
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

// SINGLE DEFINITION - No duplicates!
function fetchTableDataFromOdoo(url, table, fields, limit, offset) {
   if (!url) {
       console.error('No URL provided');
       return {error: 'No URL configured'};
   }
   
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
         contentType: 'application/json',
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
    
    // **ALWAYS ENSURE 'id' IS INCLUDED**
    // Check if 'id' exists in the sheet headers
    const idIndex = allHeaders.indexOf('id');
    if (idIndex !== -1) {
      // 'id' column exists in the sheet
      if (!selectedHeaders.includes('id')) {
        // User didn't select it, so add it at the beginning
        selectedHeaders = ['id'].concat(selectedHeaders);
        SpreadsheetApp.getActiveSpreadsheet().toast('Auto-added "id" column for ' + sheetName);
      }
    } else {
      // 'id' column doesn't exist in the sheet - warn the user
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
        const options = {
          method: 'post',
          contentType: 'application/json',
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
  const intervalInput = Browser.inputBox('Enter Refresh Interval', 'Please enter the interval in hours:', Browser.Buttons.OK_CANCEL);

  if (intervalInput === 'cancel') {
    Browser.msgBox('Setup canceled.');
    return;
  }

  const interval = parseInt(intervalInput, 10);

  if (isNaN(interval) || interval <= 0) {
    Browser.msgBox('Please enter a valid positive number for the interval in hours.');
    return;
  }

  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === 'autoFetchData') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('autoFetchData')
    .timeBased()
    .everyHours(interval) 
    .create();

  Browser.msgBox(`Auto-refresh set up successfully for every ${interval} hour(s).`);
}

function autoFetchData() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();
  const selectedTables = sheets.map(sheet => sheet.getName());
  fetchData(selectedTables);  
}

function refreshNow() {
  autoFetchData();   
} 

               """).decode('utf-8'),
            'mimetype': 'application/javascript',
        })
        self.message_post(
            body="Here is the generated Google Apps Script.",
            attachment_ids=[attachment.id],
        )
