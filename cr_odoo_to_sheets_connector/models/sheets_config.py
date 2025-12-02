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
        token = secrets.token_hex(16) # Generates 32 character hex string for access key
        # stores the system parameter of token key value pair
        # So the Google Sheets App Script can retrieve it, and Odoo can validate it whenever Sheets makes API calls.
        self.env["ir.config_parameter"].sudo().set_param("access.token", token)
        self.cr_access_token = token
        return token

    def generate_app_script(self):
        """Generates App Script."""
        # creates script attachment record, Attachments can be files stored in database
        attachment = self.env['ir.attachment'].create({
            'name': 'google_script', # filename
            'type': 'binary', # Indicates that this file is a binary file (not a URL or link).
            'datas': base64.b64encode(b"""
function onOpen() {
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
}

function setUrl() {
  const url = Browser.inputBox('Enter Odoo API URL');
  const token = Browser.inputBox('Enter Odoo API Token');
  PropertiesService.getScriptProperties().setProperty('odooUrl', url);
  PropertiesService.getScriptProperties().setProperty('odootoken', token);
  Browser.msgBox('API Url ANd Token Set successfully.');

}
function showExportDialog() {
  const sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();

  let htmlContent = '<h3>Select Sheets to Export to Odoo</h3>';
  htmlContent += '<form id="sheetSelectionForm">';

  sheets.forEach(sheet => {
    htmlContent += `
      <input type="checkbox" name="sheets" value="${sheet.getName()}">${sheet.getName()}<br>
    `;
  });

  htmlContent += `
    <input type="button" value="Export Data" onclick="exportData()" class="fixed-button">
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
      function exportData() {
        const checkboxes = document.querySelectorAll('input[name="sheets"]:checked');
        const selectedSheets = Array.from(checkboxes).map(checkbox => checkbox.value);

        google.script.run
          .withSuccessHandler(() => {
            google.script.host.close();
          })
          .sendDataToOdoo(selectedSheets);
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(400)
    .setHeight(300);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Export Data to Odoo');
}

function sendDataToOdoo(selectedSheets) {
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  const token = PropertiesService.getScriptProperties().getProperty('odootoken');

  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }

  selectedSheets.forEach(sheetName => {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
    const data = sheet.getDataRange().getValues();
    const payload = {
      table: sheetName,
      data: data
    };
    const options = {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload:JSON.stringify(payload)
    };

    try {
      const response = UrlFetchApp.fetch(url + '/send_data', options);
      const responseCode = response.getResponseCode();

      if (responseCode === 200) {
        SpreadsheetApp.getActiveSpreadsheet().toast(`Data exported for sheet: ${sheetName}`);
      } else {
        SpreadsheetApp.getActiveSpreadsheet().toast(`Failed to export data for sheet: ${sheetName}`);
      }
    } catch (error) {
      SpreadsheetApp.getActiveSpreadsheet().toast('Error exporting data. Check logs.');
    }
  });
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

  let htmlContent = '<h3>Select Tables to Fetch Data</h3>';
  htmlContent += '<form id="tableSelectionForm">';

  htmlContent += '<div class="button-container">';
  htmlContent += '<input type="button" value="Fetch Data" onclick="fetchData()" class="fixed-button">';
  htmlContent += '</div>';

  Object.keys(tables).forEach(table => {
    htmlContent += `
      <input type="checkbox" name="tables" value="${table}">${tables[table]}<br>
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
        padding: 10px;
      }
    </style>

    <script>
      function fetchData() {
        const checkboxes = document.querySelectorAll('input[name="tables"]:checked');
        const selectedTables = Array.from(checkboxes).map(checkbox => checkbox.value);

        google.script.run
          .withSuccessHandler(() => {
            google.script.host.close();  
          })
          .fetchData(selectedTables);
      }
    </script>
  `;

  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(500)
    .setHeight(500);

  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Select Tables');

}


function getSelectedTables() {
  const form = document.getElementById('tableSelectionForm');
  const checkboxes = form.querySelectorAll('input[name="tables"]:checked');
  const selectedTables = Array.from(checkboxes).map(checkbox => checkbox.value);
  return selectedTables;
}

function fetchData(selectedTables) {
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');

  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }
   selectedTables.forEach(function (table, index) {
    const data = fetchTableDataFromOdoo(url, table);  

    if (data) {
      SpreadsheetApp.getActiveSpreadsheet().toast('Data fetched for ' + table);
      writeDataToSheet(table, data);

      if (index === selectedTables.length - 1) {
        SpreadsheetApp.getActiveSpreadsheet().toast('All tables processed successfully.');
      }
    }
  });
}

function fetchTableDataFromOdoo(url, table) {
   if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('from fetch table Set URL first.');
    return;
  }

  const response = UrlFetchApp.fetch(url + '/get_table/' + table, {
    method: 'post',
    muteHttpExceptions: true
  });

  const result = JSON.parse(response.getContentText());
  return result; 
}

function writeDataToSheet(table, data) {
  let sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(table);
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet(table);
  }
  sheet.clear();

  if (data && data.length > 0) {
    const headers = Object.keys(data[0]);
    sheet.appendRow(headers);  

    data.forEach(row => {
      const rowData = headers.map(header => row[header] || '');
      sheet.appendRow(rowData);
    });

    SpreadsheetApp.getActiveSpreadsheet().toast('Data has been written to the sheet');
  } else {
    SpreadsheetApp.getActiveSpreadsheet().toast('No data available to write for table '+ table);
  }
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
  const url = PropertiesService.getScriptProperties().getProperty('odooUrl');
  if (!url) {
    SpreadsheetApp.getActiveSpreadsheet().toast('Set URL first.');
    return;
  }
  autoFetchData();   
}

               """).decode('utf-8'), # Decode to string (because Odoo needs Base64 as text)
            'mimetype': 'application/javascript', # Tells Odoo that this is a JS file
        })
        # Posts a message on the chatter (mail thread of the current record).
        # Attaches the JS file to the message so user can download it.
        self.message_post(
            body="Here is the generated Google Apps Script.",
            attachment_ids=[attachment.id],
        )
