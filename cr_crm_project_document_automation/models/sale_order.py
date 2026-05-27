# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, api, _, fields
import logging
import base64
import io
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:
    canvas = False

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

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
                _logger.error(
                    "Error in _copy_folders_to_project for SO %s: %s",
                    order.name,
                    str(e),
                )
        return res

    def _copy_folders_to_project(self):
        self.ensure_one()
        _logger.info("Starting folder copy process for Sale Order: %s", self.name)

        # 1. Identify the linked Opportunity and its document folder
        opportunity = self.opportunity_id
        if not opportunity:
            _logger.warning(
                "No Opportunity linked to SO %s. Skipping folder copy.", self.name
            )
            return

        if not opportunity.document_folder_id:
            _logger.warning(
                "Opportunity '%s' has no document folder. Skipping folder copy.",
                opportunity.name,
            )
            return

        _logger.info(
            "Found Opportunity folder: %s (ID: %s)",
            opportunity.document_folder_id.name,
            opportunity.document_folder_id.id,
        )

        # 2. Find the Project(s) linked to this Sale Order
        projects = self.env["project.project"].search([("sale_order_id", "=", self.id)])
        if not projects and hasattr(self, "project_ids"):
            projects = self.project_ids

        if not projects:
            _logger.warning(
                "No projects found for SO %s. Folder copy cannot proceed.", self.name
            )
            return

        for project in projects:
            _logger.info("Processing Project: %s (ID: %s)", project.name, project.id)

            # 3. Find the Project's document folder
            project_folder = self.env["documents.document"].search(
                [
                    ("name", "=", project.name),
                    ("type", "=", "folder"),
                    ("folder_id.name", "=", "Projects"),
                ],
                limit=1,
            )

            if not project_folder:
                _logger.error(
                    "Project folder '%s' NOT FOUND under 'Projects' workspace. Skipping this project.",
                    project.name,
                )
                continue

            _logger.info("Found Project root folder: %s", project_folder.name)

            # 4. Create "Customer Data - [SO Name] - [Customer Name]" merged folder directly in Project root
            so_folder_name = f"Customer Data - {self.name} - {self.partner_id.name}"
            so_folder = self.env["documents.document"].search(
                [
                    ("name", "=", so_folder_name),
                    ("folder_id", "=", project_folder.id),
                    ("type", "=", "folder"),
                ],
                limit=1,
            )

            if not so_folder:
                so_folder = self.env["documents.document"].create(
                    {
                        "name": so_folder_name,
                        "folder_id": project_folder.id,
                        "type": "folder",
                        "company_id": self.company_id.id,
                        "is_master_folder": True,
                        "sequence": 1,
                    }
                )
                _logger.info(
                    "CREATED merged folder '%s' inside Project folder '%s'",
                    so_folder_name,
                    project_folder.name,
                )
            else:
                if so_folder.sequence != 1:
                    so_folder.write({"sequence": 1})
                _logger.info(
                    "Merged folder '%s' ALREADY EXISTS inside Project folder '%s'",
                    so_folder_name,
                    project_folder.name,
                )

            # --- AUTOMATION: Apply Global Folder Structure ---
            self.env['project.folder.structure'].apply_structure_to_folder(so_folder)
            _logger.info("Automatically applied global folder structure to '%s'", so_folder.name)
            # --------------------------------------------------

            # 6. Copy standard subfolders from Opportunity as shortcuts
            standard_subfolders = [
                "Technical Data",
                "Vendor Quotations",
                "Costing",
                "Quotation",
                "Sales Order",
                "Customer PO",
            ]

            opp_subfolders = self.env["documents.document"].search(
                [
                    ("folder_id", "=", opportunity.document_folder_id.id),
                    ("name", "in", standard_subfolders),
                    ("type", "=", "folder"),
                ]
            )

            _logger.info(
                "Found %s subfolders in Opportunity to copy.", len(opp_subfolders)
            )

            # PRE-GENERATE Placeholder PDF for Shortcuts (Small File Size)
            placeholder_bytes = b''
            if canvas:
                placeholder_output = io.BytesIO()
                c_p = canvas.Canvas(placeholder_output, pagesize=A4)
                c_p.setFont("Helvetica-Bold", 11)
                c_p.drawString(60, 800, "SHORTCUT - Full-quality file is on the main record.")
                c_p.setFont("Helvetica", 9)
                c_p.drawString(60, 784, "This is an automated shortcut to the Opportunity document.")
                c_p.drawString(60, 770, "Use Download / Preview to access the original file.")
                c_p.showPage()
                c_p.save()
                placeholder_bytes = placeholder_output.getvalue()
            else:
                placeholder_bytes = b"SHORTCUT - Full-quality file is on the main record."
            
            compressed_content = base64.b64encode(placeholder_bytes)

            for opp_sub in opp_subfolders:
                # Check if this subfolder already exists in the target SO folder
                target_sub = self.env["documents.document"].search(
                    [
                        ("name", "=", opp_sub.name),
                        ("folder_id", "=", so_folder.id),
                        ("type", "=", "folder"),
                    ],
                    limit=1,
                )

                if not target_sub:
                    # Use copy_data() + create() to perform a NON-RECURSIVE copy.
                    folder_copy_vals = opp_sub.copy_data(
                        default={
                            "folder_id": so_folder.id,
                            "name": opp_sub.name,
                        }
                    )[0]
                    target_sub = self.env["documents.document"].create(folder_copy_vals)
                    _logger.info(
                        "  -> COPIED subfolder metadata '%s' inside '%s'",
                        target_sub.name,
                        so_folder.name,
                    )
                else:
                    _logger.info(
                        "  -> Subfolder '%s' ALREADY EXISTS inside '%s'",
                        target_sub.name,
                        so_folder.name,
                    )

                # Find files (binary documents) in the Opportunity subfolder
                files = self.env["documents.document"].search(
                    [("folder_id", "=", opp_sub.id), ("type", "=", "binary")]
                )

                for file in files:
                    # 1. Search for any existing document with this name in the target folder
                    existing_items = self.env["documents.document"].search(
                        [
                            ("name", "=", file.name),
                            ("folder_id", "=", target_sub.id),
                        ]
                    )

                    # If an actual file or a different shortcut exists with the same name, remove it
                    for item in existing_items:
                        if item.shortcut_document_id.id != file.id:
                            _logger.info(
                                "     * Removing actual file/old item '%s' to replace with shortcut.",
                                item.name,
                            )
                            item.unlink()

                    # 2. Check if the correct shortcut already exists (re-search after cleanup)
                    existing_shortcut = self.env["documents.document"].search(
                        [
                            ("shortcut_document_id", "=", file.id),
                            ("folder_id", "=", target_sub.id),
                        ],
                        limit=1,
                    )

                    if not existing_shortcut:
                        # Mirror Logic: Create a REDUCED SIZE shortcut with URL extension
                        self.env['documents.document'].create({
                            'name': file.name,
                            'folder_id': target_sub.id,
                            'type': 'binary',
                            'datas': compressed_content,
                            'shortcut_document_id': file.id,
                            'file_extension': 'URL',
                            'company_id': self.company_id.id,
                        })
                        _logger.info("     * CREATED REDUCED-SIZE SHORTCUT (URL) for file: %s", file.name)
                    else:
                        _logger.info(
                            "     * Shortcut for '%s' already exists.", file.name
                        )

            _logger.info(
                "FINISH: Successfully completed folder and shortcut creation for SO %s -> Project %s",
                self.name,
                project.name,
            )

    def _get_project_so_folder(self):
        """Helper to find the specific SO folder in the project workspace."""
        self.ensure_one()
        # 1. Find the Project(s) linked to this Sale Order
        project = self.env["project.project"].search(
            [("sale_order_id", "=", self.id)], limit=1
        )
        if not project and hasattr(self, "project_ids") and self.project_ids:
            project = self.project_ids[0]

        if not project:
            return False

        # 2. Find the Project's document folder
        project_folder = self.env["documents.document"].search(
            [
                ("name", "=", project.name),
                ("type", "=", "folder"),
                ("folder_id.name", "=", "Projects"),
            ],
            limit=1,
        )
        if not project_folder:
            return False

        # 3. Find the merged folder "Customer Data - [SO Name] - [Customer Name]" inside Project folder
        so_folder_name = f"Customer Data - {self.name} - {self.partner_id.name}"
        return self.env["documents.document"].search(
            [
                ("name", "=", so_folder_name),
                ("folder_id", "=", project_folder.id),
                ("type", "=", "folder"),
            ],
            limit=1,
        )

    def _compute_document_count(self):
        """Override to count documents in the Project SO folder instead of CRM folder."""
        for order in self:
            so_folder = order._get_project_so_folder()
            if so_folder:
                # Count binary files inside the SO folder and its subfolders
                order.document_count = self.env["documents.document"].search_count(
                    [("folder_id", "child_of", so_folder.id), ("type", "=", "binary")]
                )
            else:
                # Fallback to standard behavior if project folder isn't ready
                super(SaleOrder, order)._compute_document_count()

    def action_open_documents(self):
        """Override to open the Project SO folder with the exact same behavior as the CRM module."""
        self.ensure_one()
        so_folder = self._get_project_so_folder()

        if not so_folder:
            # Fallback if the folder hasn't been created yet
            return super(SaleOrder, self).action_open_documents()

        # Get the list view reference to ensure it's used
        list_view = self.env.ref(
            "documents.documents_view_list", raise_if_not_found=False
        )

        return {
            "name": _("Documents - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "view_mode": "list,kanban,activity",
            "views": [
                (list_view.id if list_view else False, "list"),
                (False, "kanban"),
                (False, "activity"),
            ],
            "context": {
                "default_folder_id": so_folder.id,
                "searchpanel_default_folder_id": so_folder.id,
            },
            # This domain is the key: it shows binary files in the tree
            # AND direct sub-folders as records in the list view.
            "domain": [
                ("folder_id", "child_of", so_folder.id),
                "|",
                ("type", "=", "binary"),
                ("folder_id", "=", so_folder.id),
            ],
            "target": "current",
        }