from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """
        Override action_confirm to trigger the folder copying logic
        after the project and its folder are created.
        """
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            try:
                order._copy_folders_to_project()
            except Exception as e:
                _logger.error("Error in _copy_folders_to_project for SO %s: %s", order.name, str(e))
        return res

    def _copy_folders_to_project(self):
        self.ensure_one()
        _logger.info("Starting folder copy process for Sale Order: %s", self.name)
        
        # 1. Identify the linked Opportunity and its document folder
        opportunity = self.opportunity_id
        if not opportunity:
            _logger.warning("No Opportunity linked to SO %s. Skipping folder copy.", self.name)
            return
        
        if not opportunity.document_folder_id:
            _logger.warning("Opportunity '%s' has no document folder. Skipping folder copy.", opportunity.name)
            return

        _logger.info("Found Opportunity folder: %s (ID: %s)", opportunity.document_folder_id.name, opportunity.document_folder_id.id)

        # 2. Find the Project(s) linked to this Sale Order
        projects = self.env['project.project'].search([('sale_order_id', '=', self.id)])
        if not projects and hasattr(self, 'project_ids'):
            projects = self.project_ids

        if not projects:
            _logger.warning("No projects found for SO %s. Folder copy cannot proceed.", self.name)
            return

        for project in projects:
            _logger.info("Processing Project: %s (ID: %s)", project.name, project.id)

            # 3. Find the Project's document folder
            project_folder = self.env['documents.document'].search([
                ('name', '=', project.name),
                ('type', '=', 'folder'),
                ('folder_id.name', '=', 'Projects')
            ], limit=1)

            if not project_folder:
                _logger.error("Project folder '%s' NOT FOUND under 'Projects' workspace. Skipping this project.", project.name)
                continue

            _logger.info("Found Project root folder: %s", project_folder.name)

            # 4. Create "Customer Data" folder inside the Project folder
            customer_data_folder = self.env['documents.document'].search([
                ('name', '=', 'Customer Data'),
                ('folder_id', '=', project_folder.id),
                ('type', '=', 'folder')
            ], limit=1)
            
            if not customer_data_folder:
                customer_data_folder = self.env['documents.document'].create({
                    'name': 'Customer Data',
                    'folder_id': project_folder.id,
                    'type': 'folder',
                    'company_id': self.company_id.id,
                    'is_master_folder': True,
                })
                _logger.info("CREATED folder 'Customer Data' inside Project folder '%s'", project_folder.name)
            else:
                _logger.info("Folder 'Customer Data' ALREADY EXISTS inside Project folder '%s'", project_folder.name)

            # 5. Create "[SO Name] - [Customer Name]" folder inside "Customer Data"
            so_folder_name = f"{self.name} - {self.partner_id.name}"
            so_folder = self.env['documents.document'].search([
                ('name', '=', so_folder_name),
                ('folder_id', '=', customer_data_folder.id),
                ('type', '=', 'folder')
            ], limit=1)

            if not so_folder:
                so_folder = self.env['documents.document'].create({
                    'name': so_folder_name,
                    'folder_id': customer_data_folder.id,
                    'type': 'folder',
                    'company_id': self.company_id.id,
                    'is_master_folder': True,
                })
                _logger.info("CREATED SO folder '%s' inside 'Customer Data'", so_folder_name)
            else:
                _logger.info("SO folder '%s' ALREADY EXISTS inside 'Customer Data'", so_folder_name)

            # 6. Copy standard subfolders from Opportunity as shortcuts
            standard_subfolders = ['Technical Data', 'Vendor Quotations', 'Costing', 'Quotation', 'Sales Order', 'Customer PO']
            
            opp_subfolders = self.env['documents.document'].search([
                ('folder_id', '=', opportunity.document_folder_id.id),
                ('name', 'in', standard_subfolders),
                ('type', '=', 'folder')
            ])

            _logger.info("Found %s subfolders in Opportunity to copy.", len(opp_subfolders))

            for opp_sub in opp_subfolders:
                # Check if this subfolder already exists in the target SO folder
                target_sub = self.env['documents.document'].search([
                    ('name', '=', opp_sub.name),
                    ('folder_id', '=', so_folder.id),
                    ('type', '=', 'folder')
                ], limit=1)

                if not target_sub:
                    # Use copy_data() + create() to perform a NON-RECURSIVE copy.
                    # This copies all folder settings (fixing the JS error) but keeps it empty.
                    folder_copy_vals = opp_sub.copy_data(default={
                        'folder_id': so_folder.id,
                        'name': opp_sub.name,
                    })[0]
                    target_sub = self.env['documents.document'].create(folder_copy_vals)
                    _logger.info("  -> COPIED subfolder metadata '%s' inside '%s'", target_sub.name, so_folder.name)
                else:
                    _logger.info("  -> Subfolder '%s' ALREADY EXISTS inside '%s'", target_sub.name, so_folder.name)

                # Find files (binary documents) in the Opportunity subfolder
                files = self.env['documents.document'].search([
                    ('folder_id', '=', opp_sub.id),
                    ('type', '=', 'binary')
                ])
                
                for file in files:
                    # Check if this file already exists in the target subfolder
                    existing_file = self.env['documents.document'].search([
                        ('name', '=', file.name),
                        ('folder_id', '=', target_sub.id),
                        ('type', '=', 'binary')
                    ], limit=1)

                    if not existing_file:
                        # Use copy() to create a new document record.
                        # Explicitly set the name to avoid "(copy)" suffix.
                        file.copy(default={
                            'folder_id': target_sub.id,
                            'name': file.name,
                        })
                        _logger.info("     * Copied file: %s", file.name)
                    else:
                        _logger.info("     * File '%s' already exists, skipping copy.", file.name)
            
            _logger.info("FINISH: Successfully completed folder and shortcut creation for SO %s -> Project %s", self.name, project.name)
