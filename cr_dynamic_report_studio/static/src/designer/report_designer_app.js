/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ReportDesignerApp extends Component {
    static template = "cr_dynamic_report_studio.ReportDesignerApp";
    
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        
        this.history = [];
        this.isHistoryRestoring = false;
        
        // Extract parameters from the action
        this.templateId = this.props.action?.params?.template_id;
        
        // Fallback 1: Context active_id
        if (!this.templateId && this.props.action?.context?.active_id) {
            this.templateId = this.props.action.context.active_id;
        }
        
        // Fallback 2: Session Storage (survives F5 refresh)
        if (!this.templateId) {
            const stored = sessionStorage.getItem('report_designer_template_id');
            if (stored) {
                this.templateId = parseInt(stored, 10);
            }
        } else {
            sessionStorage.setItem('report_designer_template_id', this.templateId);
        }
        
        this.state = useState({
            pageWidth: 595,
            pageHeight: 842,
            rulerOffsetX: 48, // Default 48px padding
            marginTop: 10,
            marginBottom: 10,
            marginLeft: 10,
            marginRight: 10,
            headerEnabled: false,
            headerHeight: 50,
            headerPrintOn: 'all',
            footerEnabled: false,
            footerHeight: 50,
            footerPrintOn: 'all',
            activeTab: 'components',
            activePageId: 1,
            activeElementId: null,
            elementsCounter: 0,
            pages: [
                { id: 1, name: "Page 1", elements: [] }
            ],
            // History
            historyIndex: -1,
            historyLength: 0,
            // For dragging existing elements smoothly
            draggingElementId: null,
            dragStartX: 0,
            dragStartY: 0,
            dragInitX: 0,
            dragInitY: 0,
            snapLines: { x: null, y: null },
            // Zoom
            zoomLevel: 100,
            scrollLeft: 0,
            scrollTop: 0,
            // Preview Modal
            showPreviewPopup: false,
            previewSelectedRecords: [],
            previewRecords: [],
            previewSearchQuery: '',
            previewError: null,
            previewErrorNode: null,
            previewErrorSuggestion: null,
            // Field Selector Modal
            showFieldPopup: false,
            showInsertMenu: false,
            availableFields: [],
            filteredFields: [],
            fieldSearchQuery: '',
            modelId: null,
            modelName: '',
            selectedField: null,
            // Color Picker state
            showColorPicker: false,
            colorPickerTarget: 'color',
            colorPickerValue: '#ffffff',
            libraryImages: [],
            selectedToolboxShape: 'rectangle',
            showShapeMenu: false,
            fieldPopupTab: 'fields',
            selectedVariable: null,
            showExpressionPopup: false,
            expressionValue: '',
            expressionPopupTab: 'fields',
            expressionError: '',
            expressionSuggestion: '',
            isValidatingExpression: false,
            functionSearchQuery: '',
            expandedFunctionCategory: 'String Functions',
            showExpressionDropdown: false,
            activeColumnId: null,
            activeColumnDropdownId: null,
            showMoreSizes: false,
            paperSizeSearchQuery: '',
            paperType: 'standard', // 'standard' or 'receipt'
            unit: 'pt', // 'pt', 'mm', 'in'
            orientation: 'portrait', // 'portrait' or 'landscape'
            editingPageId: null, // ID of page currently being renamed
            sidebarRootFields: [],
            sidebarVisibleFields: [],
            sidebarFieldSearchQuery: '',
        });

        onWillStart(async () => {
            await this.loadLibraryImages();
            if (this.templateId) {
                // Fetch template data
                const template = await this.orm.read("report.designer.template", [this.templateId], [
                    "paper_width", "paper_height", "margin_top", "margin_bottom", "margin_left", "margin_right", "template_json", "model_id", "model_name", "orientation"
                ]);
                if (template.length > 0) {
                    const data = template[0];
                    const MM_TO_PT = 2.83465;
                    this.state.pageWidth = Math.round((data.paper_width || 210) * MM_TO_PT);
                    this.state.pageHeight = Math.round((data.paper_height || 297) * MM_TO_PT);
                    if (data.orientation) {
                        this.state.orientation = data.orientation;
                    }
                    this.state.marginTop = Math.round((data.margin_top || 0) * MM_TO_PT);
                    this.state.marginBottom = Math.round((data.margin_bottom || 0) * MM_TO_PT);
                    this.state.marginLeft = Math.round((data.margin_left || 0) * MM_TO_PT);
                    this.state.marginRight = Math.round((data.margin_right || 0) * MM_TO_PT);
                    if (data.model_id) {
                        this.state.modelId = data.model_id[0];
                        this.state.modelName = data.model_name || data.model_id[1] || '';
                        this.templateModelId = data.model_id[0];
                        this.templateModelName = this.state.modelName;
                        
                        try {
                            const fields = await this.orm.searchRead(
                                'ir.model.fields',
                                [['model_id', '=', this.state.modelId]],
                                ['name', 'field_description', 'ttype', 'relation'],
                                { order: 'field_description asc', limit: 1000 }
                            );
                            this.state.sidebarRootFields = fields.map(f => ({
                                ...f,
                                level: 0,
                                parentPath: '',
                                fullPath: f.name,
                                isExpanded: false,
                                children: null,
                                relationLoaded: false
                            }));
                            this.rebuildSidebarVisibleFields();
                        } catch (e) {
                            console.error("Failed to fetch sidebar fields", e);
                            this.state.sidebarRootFields = [];
                            this.rebuildSidebarVisibleFields();
                        }
                    }
                    
                    if (data.template_json) {
                        try {
                            const parsedData = JSON.parse(data.template_json);
                            if (parsedData.paperType) {
                                this.state.paperType = parsedData.paperType;
                                if (this.state.paperType === 'receipt') {
                                    this.state.pageWidth = 226.7;
                                    this.state.pageHeight = 396.8;
                                    this.state.marginTop = 0;
                                    this.state.marginBottom = 0;
                                    this.state.marginLeft = 0;
                                    this.state.marginRight = 0;
                                }
                            }
                            if (parsedData.unit) {
                                this.state.unit = parsedData.unit;
                            }
                            if (parsedData.headerEnabled !== undefined) {
                                this.state.headerEnabled = parsedData.headerEnabled;
                                this.state.headerHeight = parsedData.headerHeight || 50;
                                this.state.headerPrintOn = parsedData.headerPrintOn || 'all';
                            }
                            if (parsedData.footerEnabled !== undefined) {
                                this.state.footerEnabled = parsedData.footerEnabled;
                                this.state.footerHeight = parsedData.footerHeight || 50;
                                this.state.footerPrintOn = parsedData.footerPrintOn || 'all';
                            }
                            if (parsedData.pages && parsedData.pages.length > 0) {
                                this.state.pages = parsedData.pages;
                                this.state.pages.forEach(p => {
                                    p.elements.forEach(e => {
                                        if (e.type === 'text' || e.type === 'field') {
                                            e.style = Object.assign({
                                                fontSize: 12,
                                                fontFamily: 'Helvetica',
                                                textAlign: 'left',
                                                verticalAlign: 'middle',
                                                textWrap: 'wrap',
                                                overflow: 'visible',
                                                bold: false,
                                                italic: false,
                                                underline: false,
                                                lineHeight: 1.2,
                                                color: '#000000',
                                                backgroundColor: e.type === 'field' ? '#f8f9fa' : '#ffffff'
                                            }, e.style || {});
                                        }
                                    });
                                });
                                // Reset counter to avoid duplicate IDs
                                let maxElId = 0;
                                this.state.pages.forEach(p => {
                                    p.elements.forEach(e => {
                                        if (e.id && typeof e.id === 'string' && e.id.startsWith('el_')) {
                                            const num = parseInt(e.id.split('_')[1]);
                                            if (num > maxElId) maxElId = num;
                                        }
                                    });
                                });
                                this.state.elementsCounter = maxElId;
                            }
                        } catch (e) {
                            console.error("Failed to parse template JSON", e);
                        }
                    }
                }
            }
            
            // Init history
            this.pushHistory();
        });

        onMounted(() => {
            this.updateRulerOffset();
            this.resizeObserver = new ResizeObserver(() => this.updateRulerOffset());
            const wrapper = document.querySelector('.o_designer_canvas_wrapper');
            const canvas = document.querySelector('.o_designer_page_container');
            if (wrapper) this.resizeObserver.observe(wrapper);
            if (canvas) this.resizeObserver.observe(canvas);
        });

        onWillUnmount(() => {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
        });
    }

    updateRulerOffset() {
        const wrapper = document.querySelector('.o_designer_canvas_wrapper');
        const canvas = document.querySelector('.o_designer_page_container');
        const rulerH = document.querySelector('.o_designer_ruler_h');
        if (wrapper && canvas && rulerH) {
            const canvasRect = canvas.getBoundingClientRect();
            const rulerRect = rulerH.getBoundingClientRect();
            const offsetX = canvasRect.left - rulerRect.left + wrapper.scrollLeft;
            if (this.state.rulerOffsetX !== offsetX) {
                this.state.rulerOffsetX = offsetX;
            }
        }
    }

    syncWatermarks() {
        // Find all unique watermark IDs across all pages
        const watermarkIds = new Set();
        this.state.pages.forEach(p => {
            if (p.elements) {
                p.elements.forEach(el => {
                    if (el.type === 'watermark') {
                        watermarkIds.add(el.id);
                    }
                });
            }
        });

        const activePage = this.state.pages.find(p => p.id === this.state.activePageId);

        watermarkIds.forEach(id => {
            // Find the master source for this watermark ID.
            // Priority 1: Check if it exists on the active page.
            let masterEl = activePage && activePage.elements 
                ? activePage.elements.find(el => el.id === id && el.type === 'watermark')
                : null;

            // Priority 2: Find the first page that has it
            if (!masterEl) {
                for (const p of this.state.pages) {
                    if (p.elements) {
                        const found = p.elements.find(el => el.id === id && el.type === 'watermark');
                        if (found) {
                            masterEl = found;
                            break;
                        }
                    }
                }
            }

            // Propagate to all pages
            if (masterEl) {
                this.state.pages.forEach(p => {
                    if (!p.elements) p.elements = [];
                    const existing = p.elements.find(el => el.id === id);
                    if (existing) {
                        // Sync all properties to match masterEl
                        Object.assign(existing, JSON.parse(JSON.stringify(masterEl)));
                    } else {
                        // Copy element to this page
                        p.elements.push(JSON.parse(JSON.stringify(masterEl)));
                    }
                });
            }
        });
    }

    pushHistory() {
        if (this.isHistoryRestoring) return;
        this.syncWatermarks();
        
        // Enforce section and pagebreak dimensions based on current margins
        this.state.pages.forEach(page => {
            if (page && page.elements) {
                page.elements.forEach(el => {
                    if (el.type === 'pagebreak') {
                        el.x = this.state.marginLeft;
                        el.width = this.state.pageWidth - this.state.marginLeft - this.state.marginRight;
                    } else if (el.type === 'section') {
                        if (el.x < this.state.marginLeft + 2) {
                            el.x = this.state.marginLeft + 2;
                        }
                        if (el.x + el.width > this.state.pageWidth - this.state.marginRight - 2) {
                            el.width = this.state.pageWidth - this.state.marginRight - 2 - el.x;
                        }
                    }
                });
            }
        });
        
        // Remove future redo states if we made a new action
        if (this.state.historyIndex < this.history.length - 1) {
            this.history = this.history.slice(0, this.state.historyIndex + 1);
        }
        
        const snapshot = JSON.parse(JSON.stringify({
            pages: this.state.pages,
            activePageId: this.state.activePageId,
            activeElementId: this.state.activeElementId,
            elementsCounter: this.state.elementsCounter
        }));
        
        this.history.push(snapshot);
        this.state.historyIndex = this.history.length - 1;
        this.state.historyLength = this.history.length;
    }

    onClickUndo() {
        if (this.state.historyIndex > 0) {
            this.isHistoryRestoring = true;
            this.state.historyIndex--;
            this.restoreSnapshot(this.history[this.state.historyIndex]);
            this.isHistoryRestoring = false;
        }
    }

    onClickRedo() {
        if (this.state.historyIndex < this.history.length - 1) {
            this.isHistoryRestoring = true;
            this.state.historyIndex++;
            this.restoreSnapshot(this.history[this.state.historyIndex]);
            this.isHistoryRestoring = false;
        }
    }

    restoreSnapshot(snapshot) {
        this.state.pages = JSON.parse(JSON.stringify(snapshot.pages));
        this.state.activePageId = snapshot.activePageId;
        this.state.activeElementId = snapshot.activeElementId;
        this.state.elementsCounter = snapshot.elementsCounter;
    }

    onClickDelete() {
        if (!this.state.activeElementId) return;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        if (page) {
            const elToDelete = page.elements.find(e => e.id === this.state.activeElementId);
            const isWatermark = elToDelete && elToDelete.type === 'watermark';

            page.elements = page.elements.filter(e => e.id !== this.state.activeElementId);
            
            if (isWatermark) {
                const targetId = this.state.activeElementId;
                this.state.pages.forEach(p => {
                    if (p.elements) {
                        p.elements = p.elements.filter(e => e.id !== targetId);
                    }
                });
            }

            this.state.activeElementId = null;
            this.pushHistory();
        }
    }

    generateThumbnailBase64() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 350;
            canvas.height = 495;
            const ctx = canvas.getContext('2d');
            
            // White page background
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            const pages = this.state.pages || [];
            if (pages.length === 0) return null;
            
            // We draw the first page as the thumbnail
            const firstPage = pages[0];
            const elements = firstPage.elements || [];
            
            // Use actual pageWidth/pageHeight from state (default to A4 points: 595 x 842)
            const pageWidth = this.state.pageWidth || 595;
            const pageHeight = this.state.pageHeight || 842;
            const scaleX = 350 / pageWidth;
            const scaleY = 495 / pageHeight;

            // Sort elements: background watermarks and large background images are drawn first
            const sortedElements = [...elements].sort((a, b) => {
                const aIsBg = a.type === 'watermark' || (a.type === 'image' && (a.width || 0) > pageWidth * 0.7);
                const bIsBg = b.type === 'watermark' || (b.type === 'image' && (b.width || 0) > pageWidth * 0.7);
                if (aIsBg && !bIsBg) return -1;
                if (!aIsBg && bIsBg) return 1;
                return 0;
            });
            
            for (const el of sortedElements) {
                const x = (el.x || 0) * scaleX;
                const y = (el.y || 0) * scaleY;
                const w = (el.width || 100) * scaleX;
                const h = (el.height || 50) * scaleY;
                const style = el.style || {};
                
                if (el.type === 'shape' || el.type === 'rectangle') {
                    ctx.fillStyle = style.backgroundColor || '#3b82f6';
                    ctx.fillRect(x, y, w, h);
                    if (style.borderWidth) {
                        ctx.strokeStyle = style.borderColor || '#1d4ed8';
                        ctx.lineWidth = Math.max(1, parseFloat(style.borderWidth) * scaleX);
                        ctx.strokeRect(x, y, w, h);
                    }
                } else if (el.type === 'line') {
                    ctx.strokeStyle = style.color || '#000000';
                    ctx.lineWidth = Math.max(1, (style.height || style.borderWidth || 2) * scaleY);
                    ctx.beginPath();
                    ctx.moveTo(x, y + h/2);
                    ctx.lineTo(x + w, y + h/2);
                    ctx.stroke();
                } else if (el.type === 'table') {
                    // Draw table header block
                    ctx.fillStyle = '#eff6ff';
                    ctx.fillRect(x, y, w, h * 0.25);
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(x, y + h * 0.25, w, h * 0.75);
                    
                    ctx.strokeStyle = '#cbd5e1';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, y, w, h);
                    const rows = 4;
                    for (let i = 1; i < rows; i++) {
                        ctx.beginPath();
                        ctx.moveTo(x, y + (h / rows) * i);
                        ctx.lineTo(x + w, y + (h / rows) * i);
                        ctx.stroke();
                    }
                } else if (el.type === 'barcode' || el.type === 'qrcode') {
                    ctx.fillStyle = '#f8fafc';
                    ctx.fillRect(x, y, w, h);
                    ctx.strokeStyle = '#e2e8f0';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, y, w, h);
                    ctx.fillStyle = '#000000';
                    const barWidth = 1.5;
                    const spacing = 3;
                    for (let bx = x + 4; bx < x + w - 4; bx += spacing + barWidth) {
                        ctx.fillRect(bx, y + 4, barWidth, h - 8);
                    }
                } else if (el.type === 'image') {
                    const isLargeBackground = (el.width || 0) > pageWidth * 0.7;
                    ctx.fillStyle = isLargeBackground ? 'rgba(241, 245, 249, 0.15)' : '#f1f5f9';
                    ctx.fillRect(x, y, w, h);
                    ctx.strokeStyle = isLargeBackground ? 'rgba(203, 213, 225, 0.2)' : '#cbd5e1';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, y, w, h);
                    
                    if (!isLargeBackground) {
                        ctx.fillStyle = '#94a3b8';
                        ctx.beginPath();
                        ctx.arc(x + w*0.3, y + h*0.3, Math.min(w, h)*0.15, 0, 2*Math.PI);
                        ctx.fill();
                        ctx.beginPath();
                        ctx.moveTo(x + w*0.1, y + h*0.85);
                        ctx.lineTo(x + w*0.5, y + h*0.4);
                        ctx.lineTo(x + w*0.9, y + h*0.85);
                        ctx.fill();
                    }
                } else {
                    ctx.fillStyle = el.type === 'field' ? '#f0fdf4' : 'transparent';
                    if (el.type === 'field') {
                        ctx.fillRect(x, y, w, h);
                    }
                    if (style.backgroundColor && style.backgroundColor !== 'transparent') {
                        ctx.fillStyle = style.backgroundColor;
                        ctx.fillRect(x, y, w, h);
                    }
                    
                    ctx.fillStyle = style.color || '#475569';
                    const fontSize = Math.max(4, (style.fontSize || 12) * scaleY * 0.7);
                    ctx.font = `${style.bold ? 'bold' : ''} ${fontSize}px Helvetica`.trim();
                    const label = el.content !== undefined && el.content !== null ? String(el.content) : (el.type === 'field' ? '[Field]' : '');
                    if (label) {
                        ctx.fillText(label.substring(0, 15), x + 2, y + h/2 + fontSize/3);
                    } else {
                        ctx.fillRect(x + 4, y + h/2 - 2, w - 8, 3);
                    }
                }
            }
            
            return canvas.toDataURL('image/png').split(',')[1];
        } catch (e) {
            console.error("Failed to generate client-side thumbnail", e);
            return null;
        }
    }

    async onClickSave() {
        if (this.templateId) {
            const MM_TO_PT = 2.83465;
            const saveData = {
                pages: this.state.pages,
                paperType: this.state.paperType,
                unit: this.state.unit,
                headerEnabled: this.state.headerEnabled,
                headerHeight: this.state.headerHeight,
                headerPrintOn: this.state.headerPrintOn,
                footerEnabled: this.state.footerEnabled,
                footerHeight: this.state.footerHeight,
                footerPrintOn: this.state.footerPrintOn
            };
            const thumbnail = this.generateThumbnailBase64();
            const vals = {
                'template_json': JSON.stringify(saveData),
                'paper_width': this.state.pageWidth / MM_TO_PT,
                'paper_height': this.state.pageHeight / MM_TO_PT,
                'margin_top': this.state.marginTop / MM_TO_PT,
                'margin_bottom': this.state.marginBottom / MM_TO_PT,
                'margin_left': this.state.marginLeft / MM_TO_PT,
                'margin_right': this.state.marginRight / MM_TO_PT,
                'orientation': this.state.orientation
            };
            if (thumbnail) {
                vals['thumbnail'] = thumbnail;
            }
            await this.orm.write('report.designer.template', [this.templateId], vals);
            console.log("Template saved successfully.");
        }
    }

    get activeElement() {
        if (!this.state.activeElementId) return null;
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        if (!page) return null;
        return page.elements.find(e => e.id === this.state.activeElementId);
    }

    selectPage(pageId) {
        this.syncWatermarks();
        this.state.activePageId = pageId;
    }

    addPage() {
        const nextId = Math.max(...this.state.pages.map(p => p.id), 0) + 1;
        this.state.pages.push({
            id: nextId,
            name: `Page ${this.state.pages.length + 1}`,
            elements: []
        });
        this.state.activePageId = nextId;
        this.pushHistory();
    }

    duplicatePage(pageId) {
        const index = this.state.pages.findIndex(p => p.id === pageId);
        if (index === -1) return;
        
        const pageToDuplicate = this.state.pages[index];
        const nextId = Math.max(...this.state.pages.map(p => p.id), 0) + 1;
        const newPage = JSON.parse(JSON.stringify(pageToDuplicate));
        newPage.id = nextId;
        newPage.name = `${pageToDuplicate.name} (Copy)`;
        
        newPage.elements.forEach(el => {
            this.state.elementsCounter++;
            el.id = `el_${this.state.elementsCounter}`;
        });
        
        this.state.pages.splice(index + 1, 0, newPage);
        
        this.state.activePageId = nextId;
        this.pushHistory();
    }

    deletePage(pageId) {
        if (this.state.pages.length <= 1) return;
        
        const index = this.state.pages.findIndex(p => p.id === pageId);
        if (index === -1) return;
        
        this.state.pages.splice(index, 1);
        
        if (this.state.activePageId === pageId) {
            const nextActiveIndex = Math.min(index, this.state.pages.length - 1);
            this.state.activePageId = this.state.pages[nextActiveIndex].id;
        }
        
        this.pushHistory();
    }

    movePageUp(pageId) {
        const index = this.state.pages.findIndex(p => p.id === pageId);
        if (index <= 0) return;
        
        const temp = this.state.pages[index];
        this.state.pages[index] = this.state.pages[index - 1];
        this.state.pages[index - 1] = temp;
        
        this.pushHistory();
    }

    movePageDown(pageId) {
        const index = this.state.pages.findIndex(p => p.id === pageId);
        if (index === -1 || index >= this.state.pages.length - 1) return;
        
        const temp = this.state.pages[index];
        this.state.pages[index] = this.state.pages[index + 1];
        this.state.pages[index + 1] = temp;
        
        this.pushHistory();
    }

    startEditPageName(pageId) {
        this.state.editingPageId = pageId;
        // Auto-focus the input after OWL renders it
        setTimeout(() => {
            const input = document.querySelector('.o_designer_page_tree input[type="text"]');
            if (input) {
                input.focus();
                input.select();
            }
        }, 50);
    }

    finishEditPageName(pageId, ev) {
        const newName = ev.target.value.trim();
        if (newName) {
            const page = this.state.pages.find(p => p.id === pageId);
            if (page) {
                page.name = newName;
            }
        }
        this.state.editingPageId = null;
        this.pushHistory();
    }

    onPageNameKeyDown(pageId, ev) {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            this.finishEditPageName(pageId, ev);
        } else if (ev.key === 'Escape') {
            this.state.editingPageId = null;
        }
    }

    // Toolbox Drag & Drop (Creating new elements)
    onDragStartToolbox(ev, type, field = null) {
        ev.dataTransfer.setData("application/report-designer-type", type);
        if (field && field.name) {
            ev.dataTransfer.setData("application/report-designer-field", field.name);
        }
        ev.dataTransfer.effectAllowed = "copy";
    }

    onDragOverCanvas(ev) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
    }

    onDropOnCanvas(ev, pageId) {
        ev.preventDefault();
        const type = ev.dataTransfer.getData("application/report-designer-type");
        const fieldName = ev.dataTransfer.getData("application/report-designer-field");
        if (!type) return;

        const rect = ev.currentTarget.getBoundingClientRect();
        // Calculate coordinates relative to the paper, accounting for zoom
        const Z = this.state.zoomLevel / 100;
        const x = (ev.clientX - rect.left) / Z;
        const y = (ev.clientY - rect.top) / Z;

        this.state.elementsCounter++;
        const newElement = {
            id: `el_${this.state.elementsCounter}`,
            type: type,
            x: (type === 'pagebreak') ? this.state.marginLeft : (type === 'section' ? this.state.marginLeft + 2 : x),
            y: y,
            width: this.getDefaultWidth(type),
            height: this.getDefaultHeight(type),
            rotation: 0,
            content: (type === 'field' && fieldName) ? `{{${fieldName}}}` : this.getDefaultContent(type),
            shapeType: type === 'shape' ? (this.state.selectedToolboxShape || 'rectangle') : undefined,
            imageSourceMode: type === 'image' ? 'resource' : undefined,
            resourceId: type === 'image' ? null : undefined,
            expression: type === 'image' ? '' : undefined,
            symbology: type === 'barcode' ? 'Code 128' : undefined,
            showBarcodeText: type === 'barcode' ? true : undefined,
            barcodeTextPosition: type === 'barcode' ? 'Bottom' : undefined,
            barWidth: type === 'barcode' ? '2.0' : undefined,
            showHeader: type === 'table' ? true : undefined,
            headerHeight: type === 'table' ? 24 : undefined,
            showFooter: type === 'table' ? false : undefined,
            repeatNewPage: type === 'table' ? true : undefined,
            style: type === 'text' || type === 'field' ? {
                fontSize: 12,
                fontFamily: 'Helvetica',
                textAlign: 'left',
                verticalAlign: 'middle',
                textWrap: 'wrap',
                overflow: 'visible',
                bold: false,
                italic: false,
                underline: false,
                lineHeight: 1.2,
                color: '#000000',
                backgroundColor: type === 'field' ? '#f8f9fa' : '#ffffff'
            } : (type === 'image' ? {
                objectFit: 'contain',
                backgroundColor: '',
                borderWidth: 0,
                borderColor: '#000000',
                borderRadius: 0
            } : (type === 'line' ? {
                color: '#000000',
                borderWidth: 1,
                borderStyle: 'solid'
            } : (type === 'shape' ? {
                fillColor: 'transparent',
                fillOpacity: 1.0,
                strokeColor: '#2C3E50',
                strokeWidth: 1,
                strokeStyle: 'solid',
                cornerRadius: 0
            } : {})))
        };

        const page = this.state.pages.find(p => p.id === pageId);
        if (page) {
            page.elements.push(newElement);
            this.state.activeElementId = newElement.id;
            this.pushHistory();
        }
    }

    onDblClickToolbox(type) {
        // Calculate middle coordinates of the page
        const x = (this.state.pageWidth - this.getDefaultWidth(type)) / 2;
        const y = (this.state.pageHeight - this.getDefaultHeight(type)) / 2;
        
        this.state.elementsCounter++;
        const newElement = {
            id: `el_${this.state.elementsCounter}`,
            type: type,
            x: (type === 'pagebreak') ? this.state.marginLeft : (type === 'section' ? this.state.marginLeft + 2 : x),
            y: y,
            width: this.getDefaultWidth(type),
            height: this.getDefaultHeight(type),
            rotation: 0,
            content: this.getDefaultContent(type),
            shapeType: type === 'shape' ? (this.state.selectedToolboxShape || 'rectangle') : undefined,
            imageSourceMode: type === 'image' ? 'resource' : undefined,
            resourceId: type === 'image' ? null : undefined,
            expression: type === 'image' ? '' : undefined,
            symbology: type === 'barcode' ? 'Code 128' : undefined,
            showBarcodeText: type === 'barcode' ? true : undefined,
            barcodeTextPosition: type === 'barcode' ? 'Bottom' : undefined,
            barWidth: type === 'barcode' ? '2.0' : undefined,
            showHeader: type === 'table' ? true : undefined,
            headerHeight: type === 'table' ? 24 : undefined,
            showFooter: type === 'table' ? false : undefined,
            repeatNewPage: type === 'table' ? true : undefined,
            style: type === 'text' || type === 'field' ? {
                fontSize: 12,
                fontFamily: 'Helvetica',
                textAlign: 'left',
                verticalAlign: 'middle',
                textWrap: 'wrap',
                overflow: 'visible',
                bold: false,
                italic: false,
                underline: false,
                lineHeight: 1.2,
                color: '#000000',
                backgroundColor: type === 'field' ? '#f8f9fa' : '#ffffff'
            } : (type === 'image' ? {
                objectFit: 'contain',
                backgroundColor: '',
                borderWidth: 0,
                borderColor: '#000000',
                borderRadius: 0
            } : (type === 'line' ? {
                color: '#000000',
                borderWidth: 1,
                borderStyle: 'solid'
            } : (type === 'shape' ? {
                fillColor: 'transparent',
                fillOpacity: 1.0,
                strokeColor: '#2C3E50',
                strokeWidth: 1,
                strokeStyle: 'solid',
                cornerRadius: 0
            } : {})))
        };

        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        if (page) {
            page.elements.push(newElement);
            this.state.activeElementId = newElement.id;
            this.pushHistory();
        }
    }

    getDefaultWidth(type) {
        switch(type) {
            case 'text': return 200;
            case 'field': return 150;
            case 'image': return 100;
            case 'line': return 300;
            case 'barcode': return 150;
            case 'table': return 400;
            case 'shape': return 100;
            case 'section': return this.state.pageWidth - this.state.marginLeft - this.state.marginRight - 4;
            default: return 100;
        }
    }

    getDefaultHeight(type) {
        switch(type) {
            case 'line': return 2;
            case 'image': return 100;
            case 'barcode': return 50;
            case 'table': return 100;
            case 'shape': return 100;
            case 'pagebreak': return 20;
            default: return 30;
        }
    }

    getDefaultContent(type) {
        switch(type) {
            case 'text': return "Text";
            case 'field': return "{{field_name}}";
            case 'table': return [
                { id: 'col1', header: 'Column 1', footer: '', contentType: 'text', contentExpression: '', widthType: 'percent', widthValue: 50 },
                { id: 'col2', header: 'Column 2', footer: '', contentType: 'text', contentExpression: '', widthType: 'percent', widthValue: 50 }
            ];
            default: return "";
        }
    }

    // (Removed get filteredSidebarFields as we use rebuildSidebarVisibleFields)

    get horizontalTicks() {
        const ticks = [];
        const maxTick = Math.ceil(this.state.pageWidth / 100) * 100 + 100;
        for (let i = -300; i <= maxTick; i += 10) {
            ticks.push(i);
        }
        return ticks;
    }

    get verticalTicks() {
        const ticks = [];
        const maxTick = Math.ceil(this.state.pageHeight / 100) * 100 + 100;
        for (let i = -200; i <= maxTick; i += 10) {
            ticks.push(i);
        }
        return ticks;
    }

    // Moving existing elements smoothly
    onElementMouseDown(ev, elementId) {
        ev.stopPropagation();
        this.state.activeElementId = elementId;
        this.state.draggingElementId = elementId;
        this.state.dragStartX = ev.clientX;
        this.state.dragStartY = ev.clientY;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === elementId);
        this.state.dragInitX = el.x;
        this.state.dragInitY = el.y;

        // Bind global mouse listeners to handle dragging outside the element
        this._onMouseMove = this.onElementMouseMove.bind(this);
        this._onMouseUp = this.onElementMouseUp.bind(this);
        document.addEventListener('mousemove', this._onMouseMove);
        document.addEventListener('mouseup', this._onMouseUp);
    }

    onElementMouseMove(ev) {
        if (!this.state.draggingElementId) return;
        
        const Z = this.state.zoomLevel / 100;
        const dx = (ev.clientX - this.state.dragStartX) / Z;
        const dy = (ev.clientY - this.state.dragStartY) / Z;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === this.state.draggingElementId);
        if (el) {
            if (el.type === 'pagebreak') {
                el.x = this.state.marginLeft;
                el.width = this.state.pageWidth - this.state.marginLeft - this.state.marginRight;
                let newY = this.state.dragInitY + dy;
                
                const snapTargetsY = [
                    this.state.pageHeight / 2,
                    this.state.marginTop,
                    this.state.pageHeight - this.state.marginBottom
                ];
                page.elements.forEach(otherEl => {
                    if (otherEl.id !== el.id) {
                        snapTargetsY.push(otherEl.y, otherEl.y + otherEl.height, otherEl.y + otherEl.height / 2);
                    }
                });
                
                let bestSnapY = null;
                let minDiffY = 5;
                const elCentersY = [newY, newY + el.height, newY + el.height / 2];
                for (let target of snapTargetsY) {
                    for (let center of elCentersY) {
                        if (Math.abs(center - target) < minDiffY) {
                            minDiffY = Math.abs(center - target);
                            bestSnapY = target;
                            newY += (target - center);
                        }
                    }
                }
                
                el.y = newY;
                this.state.snapLines.y = bestSnapY;
                this.state.snapLines.x = null;
            } else {
                let newX = this.state.dragInitX + dx;
                let newY = this.state.dragInitY + dy;
                
                const snapTargetsX = [
                    this.state.pageWidth / 2,
                    this.state.marginLeft,
                    this.state.pageWidth - this.state.marginRight
                ];
                const snapTargetsY = [
                    this.state.pageHeight / 2,
                    this.state.marginTop,
                    this.state.pageHeight - this.state.marginBottom
                ];
                
                page.elements.forEach(otherEl => {
                    if (otherEl.id !== el.id) {
                        snapTargetsX.push(otherEl.x, otherEl.x + otherEl.width, otherEl.x + otherEl.width / 2);
                        snapTargetsY.push(otherEl.y, otherEl.y + otherEl.height, otherEl.y + otherEl.height / 2);
                    }
                });
                
                let bestSnapX = null;
                let minDiffX = 5;
                const elCentersX = [newX, newX + el.width, newX + el.width / 2];
                for (let target of snapTargetsX) {
                    for (let center of elCentersX) {
                        if (Math.abs(center - target) < minDiffX) {
                            minDiffX = Math.abs(center - target);
                            bestSnapX = target;
                            newX += (target - center);
                        }
                    }
                }
                
                let bestSnapY = null;
                let minDiffY = 5;
                const elCentersY = [newY, newY + el.height, newY + el.height / 2];
                for (let target of snapTargetsY) {
                    for (let center of elCentersY) {
                        if (Math.abs(center - target) < minDiffY) {
                            minDiffY = Math.abs(center - target);
                            bestSnapY = target;
                            newY += (target - center);
                        }
                    }
                }
                
                if (el.type === 'section') {
                    if (newX < this.state.marginLeft + 2) {
                        newX = this.state.marginLeft + 2;
                    }
                    if (newX + el.width > this.state.pageWidth - this.state.marginRight - 2) {
                        newX = this.state.pageWidth - this.state.marginRight - 2 - el.width;
                    }
                }

                el.x = newX;
                el.y = newY;
                this.state.snapLines.x = bestSnapX;
                this.state.snapLines.y = bestSnapY;
            }
        }
    }

    onElementMouseUp(ev) {
        this.state.draggingElementId = null;
        this.state.snapLines.x = null;
        this.state.snapLines.y = null;
        document.removeEventListener('mousemove', this._onMouseMove);
        document.removeEventListener('mouseup', this._onMouseUp);
        // We push history on mouse up to capture the final dragged position
        this.pushHistory();
    }

    onResizeMouseDown(ev, elementId) {
        ev.stopPropagation();
        ev.preventDefault();
        
        this.state.activeElementId = elementId;
        this.resizingElementId = elementId;
        this.resizeStartX = ev.clientX;
        this.resizeStartY = ev.clientY;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === elementId);
        this.resizeInitWidth = el.width;
        this.resizeInitHeight = el.height;

        this._onResizeMouseMove = this.onResizeMouseMove.bind(this);
        this._onResizeMouseUp = this.onResizeMouseUp.bind(this);
        document.addEventListener('mousemove', this._onResizeMouseMove);
        document.addEventListener('mouseup', this._onResizeMouseUp);
    }

    onResizeMouseMove(ev) {
        if (!this.resizingElementId) return;
        
        const Z = this.state.zoomLevel / 100;
        const dx = (ev.clientX - this.resizeStartX) / Z;
        const dy = (ev.clientY - this.resizeStartY) / Z;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === this.resizingElementId);
        if (el) {
            el.width = Math.max(10, this.resizeInitWidth + dx);
            el.height = Math.max(2, this.resizeInitHeight + dy);
        }
        this.updateReceiptRollHeight();
    }

    onResizeMouseUp(ev) {
        this.resizingElementId = null;
        document.removeEventListener('mousemove', this._onResizeMouseMove);
        document.removeEventListener('mouseup', this._onResizeMouseUp);
        this.pushHistory();
    }

    onSectionResizeMouseDown(ev, elementId, handle) {
        ev.stopPropagation();
        ev.preventDefault();
        
        this.state.activeElementId = elementId;
        this.resizingElementId = elementId;
        this.resizeHandleType = handle; // 'top' or 'bottom'
        this.resizeStartX = ev.clientX;
        this.resizeStartY = ev.clientY;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === elementId);
        this.resizeInitHeight = el.height;
        this.resizeInitY = el.y;

        this._onSectionResizeMouseMove = this.onSectionResizeMouseMove.bind(this);
        this._onSectionResizeMouseUp = this.onSectionResizeMouseUp.bind(this);
        document.addEventListener('mousemove', this._onSectionResizeMouseMove);
        document.addEventListener('mouseup', this._onSectionResizeMouseUp);
    }

    onSectionResizeMouseMove(ev) {
        if (!this.resizingElementId) return;
        
        const Z = this.state.zoomLevel / 100;
        const dy = (ev.clientY - this.resizeStartY) / Z;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        const el = page.elements.find(e => e.id === this.resizingElementId);
        if (el) {
            if (this.resizeHandleType === 'top') {
                const newHeight = this.resizeInitHeight - dy;
                if (newHeight > 10) {
                    el.y = this.resizeInitY + dy;
                    el.height = newHeight;
                }
            } else {
                el.height = Math.max(10, this.resizeInitHeight + dy);
            }
        }
        this.updateReceiptRollHeight();
    }

    onSectionResizeMouseUp(ev) {
        this.resizingElementId = null;
        document.removeEventListener('mousemove', this._onSectionResizeMouseMove);
        document.removeEventListener('mouseup', this._onSectionResizeMouseUp);
        this.pushHistory();
    }

    onClickLayer(action) {
        if (!this.state.activeElementId) return;
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        if (!page) return;
        
        const index = page.elements.findIndex(e => e.id === this.state.activeElementId);
        if (index === -1) return;
        
        // Remove the element from array
        const el = page.elements.splice(index, 1)[0];
        
        if (action === 'back') {
            page.elements.unshift(el);
        } else if (action === 'backward') {
            page.elements.splice(Math.max(0, index - 1), 0, el);
        } else if (action === 'forward') {
            page.elements.splice(Math.min(page.elements.length, index + 1), 0, el);
        } else if (action === 'front') {
            page.elements.push(el);
        }
        
        this.pushHistory();
    }

    toggleStyle(property) {
        const el = this.activeElement;
        if (el && el.style) {
            el.style[property] = !el.style[property];
            this.pushHistory();
        }
    }

    setAlignment(align) {
        this.setStyle('textAlign', align);
    }

    setStyle(property, value) {
        const el = this.activeElement;
        if (el && el.style) {
            el.style[property] = value;
            this.pushHistory();
        }
    }

    onCanvasClick(ev) {
        // Deselect if clicking on empty canvas
        this.state.activeElementId = null;
    }

    onCanvasScroll(ev) {
        this.state.scrollLeft = ev.target.scrollLeft;
        this.state.scrollTop = ev.target.scrollTop;
        this.updateRulerOffset();
    }

    onClickBack() {
        this.actionService.restore();
    }
    
    // Zoom Handlers
    onClickZoomIn() {
        if (this.state.zoomLevel < 300) {
            this.state.zoomLevel += 10;
        }
    }
    
    onClickZoomOut() {
        if (this.state.zoomLevel > 10) {
            this.state.zoomLevel -= 10;
        }
    }

    // Preview Handlers
    async onClickPreview() {
        this.state.previewSelectedRecords = [];
        this.state.previewSearchQuery = '';
        await this.loadPreviewRecords();
        this.state.showPreviewPopup = true;
    }

    async loadPreviewRecords() {
        if (!this.state.modelName) return;
        try {
            const domain = [];
            if (this.state.previewSearchQuery) {
                domain.push(['display_name', 'ilike', this.state.previewSearchQuery]);
            }
            const records = await this.orm.searchRead(
                this.state.modelName,
                domain,
                ['display_name'],
                { limit: 100 }
            );
            this.state.previewRecords = records.map(r => ({
                id: r.id,
                name: r.display_name || r.name || `Record #${r.id}`
            }));
        } catch (e) {
            console.error("Failed to load preview records", e);
            this.state.previewRecords = [];
        }
    }

    async onSearchPreview(ev) {
        this.state.previewSearchQuery = ev.target.value;
        await this.loadPreviewRecords();
    }
    
    onClosePreview() {
        this.state.showPreviewPopup = false;
        this.state.previewSelectedRecords = [];
        this.state.previewSearchQuery = '';
    }

    async confirmPreview() {
        if (this.state.previewSelectedRecords.length > 0) {
            this.state.previewError = null;
            this.state.previewErrorNode = null;
            this.state.previewErrorSuggestion = null;
            try {
                const action = await this.orm.call(
                    'report.designer.template',
                    'action_preview_pdf',
                    [[this.templateId]],
                    { res_ids: this.state.previewSelectedRecords }
                );
                if (action) {
                    if (action.error) {
                        this.state.previewError = action.message;
                        this.state.previewErrorNode = action.node;
                        this.state.previewErrorSuggestion = action.suggestion;
                    } else {
                        this.actionService.doAction(action);
                        this.closePreview();
                    }
                }
            } catch (e) {
                console.error("Failed to execute preview report action", e);
            }
        }
    }

    closePreview() {
        this.state.showPreviewPopup = false;
    }

    toggleRecordSelection(recordId) {
        const index = this.state.previewSelectedRecords.indexOf(recordId);
        if (index === -1) {
            this.state.previewSelectedRecords.push(recordId);
        } else {
            this.state.previewSelectedRecords.splice(index, 1);
        }
    }

    // Field Selector Methods
    get builtInVariables() {
        return [
            { name: "Page Number", code: "page_number", desc: "Current page number" },
            { name: "Page Count", code: "page_count", desc: "Total number of pages" },
            { name: "Current Date", code: "current_date", desc: "Current date" },
            { name: "Current Time", code: "current_time", desc: "Current time" },
            { name: "Current DateTime", code: "current_datetime", desc: "Current date and time" },
            { name: "Base URL", code: "base_url", desc: "Base URL passed to the report" }
        ];
    }

    get filteredVariables() {
        const q = this.state.fieldSearchQuery.toLowerCase();
        
        // Built-ins
        const builtIns = this.builtInVariables.map(v => ({
            ...v,
            isBuiltIn: true,
            ttype: 'VAR'
        }));
        
        // Model variables
        const modelVars = this.state.availableFields.map(f => ({
            name: `${f.field_description} (${f.name})`,
            code: `doc.${f.name}`,
            desc: `Variable of field '${f.name}' from current record`,
            isBuiltIn: false,
            ttype: f.ttype
        }));
        
        const all = [...builtIns, ...modelVars];
        if (!q) return all;
        return all.filter(v =>
            v.name.toLowerCase().includes(q) ||
            v.code.toLowerCase().includes(q) ||
            v.desc.toLowerCase().includes(q)
        );
    }

    async getRelationModelInfo(modelId, path) {
        if (!path) return null;
        const parts = path.split('.');
        let currentModelId = modelId;
        let currentRelation = null;
        let modelName = null;
        for (const part of parts) {
            const fields = await this.orm.searchRead(
                'ir.model.fields',
                [['model_id', '=', currentModelId], ['name', '=', part]],
                ['relation']
            );
            if (fields.length > 0 && fields[0].relation) {
                currentRelation = fields[0].relation;
                const models = await this.orm.searchRead(
                    'ir.model',
                    [['model', '=', currentRelation]],
                    ['id', 'name']
                );
                if (models.length > 0) {
                    currentModelId = models[0].id;
                    modelName = models[0].name;
                } else {
                    return null;
                }
            } else {
                return null;
            }
        }
        return currentRelation ? { id: currentModelId, name: modelName || currentRelation } : null;
    }

    async openFieldSelector(activeTab = 'fields', activeColumnId = null) {
        this.state.showInsertMenu = false;
        this.state.activeColumnId = activeColumnId;
        const activeEl = this.activeElement;
        if (activeEl && (activeEl.type === 'section' || activeEl.type === 'table')) {
            activeTab = 'fields';
        }
        this.state.fieldPopupTab = activeTab;
        this.state.selectedField = null;
        this.state.selectedVariable = null;
        this.state.fieldSearchQuery = '';
        
        let modelId = this.state.modelId;
        let modelName = this.state.modelName;
        if (activeEl && activeEl.type === 'table' && activeColumnId && activeEl.dataSource) {
            const relInfo = await this.getRelationModelInfo(this.state.modelId, activeEl.dataSource);
            if (relInfo) {
                modelId = relInfo.id;
                modelName = relInfo.name;
            }
        }
        this.state.modelId = modelId;
        this.state.modelName = modelName;

        if (this.state.modelId) {
            const domain = [['model_id', '=', this.state.modelId]];
            if (activeEl && activeEl.type === 'image') {
                domain.push(['ttype', 'in', ['binary', 'many2one']]);
            } else if (activeEl && activeEl.type === 'barcode') {
                domain.push(['ttype', 'in', ['char', 'text']]);
            } else if (activeEl && (activeEl.type === 'text' || activeEl.type === 'field')) {
                domain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
            } else if (activeEl && (activeEl.type === 'section' || activeEl.type === 'table')) {
                if (activeEl.type === 'table' && activeColumnId) {
                    const col = activeEl.content.find(c => c.id === activeColumnId);
                    if (col && col.contentType === 'image') {
                        domain.push(['ttype', 'in', ['binary', 'many2one']]);
                    } else if (col && col.contentType === 'barcode') {
                        domain.push(['ttype', 'in', ['char', 'text']]);
                    } else {
                        domain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
                    }
                } else {
                    domain.push(['ttype', 'in', ['one2many', 'many2many']]);
                }
            }
            const fields = await this.orm.searchRead(
                'ir.model.fields',
                domain,
                ['name', 'field_description', 'ttype', 'relation'],
                { order: 'field_description asc', limit: 500 }
            );
            this.state.availableFields = fields;
            this.state.rootFields = fields.map(f => ({
                ...f,
                level: 0,
                parentPath: '',
                fullPath: f.name,
                isExpanded: false,
                children: null,
                relationLoaded: false
            }));
            this.rebuildVisibleFields();
        }
        this.state.showFieldPopup = true;
    }

    async toggleFieldExpand(field) {
        field.isExpanded = !field.isExpanded;
        if (field.isExpanded && !field.relationLoaded && field.relation) {
            try {
                const relationModels = await this.orm.searchRead(
                    'ir.model',
                    [['model', '=', field.relation]],
                    ['id', 'name']
                );
                if (relationModels.length > 0) {
                    const subDomain = [['model_id', '=', relationModels[0].id]];
                    const activeEl = this.activeElement;
                    if (activeEl && activeEl.type === 'image') {
                        subDomain.push(['ttype', 'in', ['binary', 'many2one']]);
                    } else if (activeEl && activeEl.type === 'barcode') {
                        subDomain.push(['ttype', 'in', ['char', 'text']]);
                    } else if (activeEl && (activeEl.type === 'text' || activeEl.type === 'field')) {
                        subDomain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
                    } else if (activeEl && (activeEl.type === 'section' || activeEl.type === 'table')) {
                        if (activeEl.type === 'table' && this.state.activeColumnId) {
                            const col = activeEl.content.find(c => c.id === this.state.activeColumnId);
                            if (col && col.contentType === 'image') {
                                subDomain.push(['ttype', 'in', ['binary', 'many2one']]);
                            } else if (col && col.contentType === 'barcode') {
                                subDomain.push(['ttype', 'in', ['char', 'text']]);
                            } else {
                                subDomain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
                            }
                        } else {
                            subDomain.push(['ttype', 'in', ['one2many', 'many2many']]);
                        }
                    }
                    const subFields = await this.orm.searchRead(
                        'ir.model.fields',
                        subDomain,
                        ['name', 'field_description', 'ttype', 'relation'],
                        { order: 'field_description asc', limit: 500 }
                    );
                    field.children = subFields.map(sf => ({
                        ...sf,
                        level: field.level + 1,
                        parentPath: field.parentPath ? `${field.parentPath}.${field.name}` : field.name,
                        fullPath: field.parentPath ? `${field.parentPath}.${field.name}.${sf.name}` : `${field.name}.${sf.name}`,
                        isExpanded: false,
                        children: null,
                        relationLoaded: false
                    }));
                    field.relationLoaded = true;
                }
            } catch (e) {
                console.error("Failed to load sub-fields", e);
            }
        }
        this.rebuildVisibleFields();
    }

    rebuildVisibleFields() {
        const list = [];
        const traverse = (fieldsArray) => {
            for (const f of fieldsArray) {
                list.push(f);
                if (f.isExpanded && f.children) {
                    traverse(f.children);
                }
            }
        };
        traverse(this.state.rootFields || []);
        
        const q = this.state.fieldSearchQuery.toLowerCase();
        if (!q) {
            this.state.filteredFields = list;
        } else {
            this.state.filteredFields = list.filter(f =>
                f.field_description.toLowerCase().includes(q) ||
                f.name.toLowerCase().includes(q) ||
                f.fullPath.toLowerCase().includes(q)
            );
        }
    }

    async toggleSidebarFieldExpand(field) {
        field.isExpanded = !field.isExpanded;
        if (field.isExpanded && !field.relationLoaded && field.relation) {
            try {
                const relationModels = await this.orm.searchRead(
                    'ir.model',
                    [['model', '=', field.relation]],
                    ['id', 'name']
                );
                if (relationModels.length > 0) {
                    const subFields = await this.orm.searchRead(
                        'ir.model.fields',
                        [['model_id', '=', relationModels[0].id]],
                        ['name', 'field_description', 'ttype', 'relation'],
                        { order: 'field_description asc', limit: 500 }
                    );
                    field.children = subFields.map(sf => ({
                        ...sf,
                        level: field.level + 1,
                        parentPath: field.parentPath ? `${field.parentPath}.${field.name}` : field.name,
                        fullPath: field.parentPath ? `${field.parentPath}.${field.name}.${sf.name}` : `${field.name}.${sf.name}`,
                        isExpanded: false,
                        children: null,
                        relationLoaded: false
                    }));
                    field.relationLoaded = true;
                }
            } catch (e) {
                console.error("Failed to load sub-fields for sidebar", e);
            }
        }
        this.rebuildSidebarVisibleFields();
    }

    rebuildSidebarVisibleFields() {
        const list = [];
        const traverse = (fieldsArray) => {
            for (const f of fieldsArray) {
                list.push(f);
                if (f.isExpanded && f.children) {
                    traverse(f.children);
                }
            }
        };
        traverse(this.state.sidebarRootFields || []);
        
        const q = this.state.sidebarFieldSearchQuery.toLowerCase();
        if (!q) {
            this.state.sidebarVisibleFields = list;
        } else {
            this.state.sidebarVisibleFields = list.filter(f =>
                (f.field_description && f.field_description.toLowerCase().includes(q)) ||
                (f.name && f.name.toLowerCase().includes(q)) ||
                (f.fullPath && f.fullPath.toLowerCase().includes(q))
            );
        }
    }

    onSearchSidebarField(ev) {
        this.state.sidebarFieldSearchQuery = ev.target.value;
        this.rebuildSidebarVisibleFields();
    }

    onSearchField(ev) {
        const q = ev.target.value.toLowerCase();
        this.state.fieldSearchQuery = q;
        this.rebuildVisibleFields();
    }

    onSelectField(field) {
        this.state.selectedField = field;
    }

    onSelectVariable(variable) {
        this.state.selectedVariable = variable;
    }

    confirmInsertField() {
        const el = this.activeElement;
        if (!el) return;
        
        if (this.state.fieldPopupTab === 'fields') {
            const field = this.state.selectedField;
            if (!field) return;
            const path = field.fullPath || field.name;
            if (this.state.activeColumnId) {
                const col = el.content.find(c => c.id === this.state.activeColumnId);
                if (col) {
                    col.contentExpression = path;
                }
                this.state.activeColumnId = null;
            } else {
                if (el.type === 'image') {
                    el.expression = path;
                } else if (el.type === 'section') {
                    el.content = path;
                } else if (el.type === 'table') {
                    el.dataSource = path;
                } else {
                    el.content = (el.content || '') + '{{' + path + '}}';
                }
            }
        } else {
            const variable = this.state.selectedVariable;
            if (!variable) return;
            if (this.state.activeColumnId) {
                const col = el.content.find(c => c.id === this.state.activeColumnId);
                if (col) {
                    col.contentExpression = variable.code;
                }
                this.state.activeColumnId = null;
            } else {
                el.content = (el.content || '') + '{{' + variable.code + '}}';
            }
        }
        this.pushHistory();
        this.closeFieldSelector();
    }

    async loadLibraryImages() {
        try {
            const resources = await this.orm.searchRead(
                'report.designer.resource',
                [],
                ['id', 'name', 'mime_type', 'file_size']
            );
            this.state.libraryImages = resources;
        } catch (e) {
            console.error("Failed to load library images", e);
            this.state.libraryImages = [];
        }
    }

    openUploadImageWizard() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'Upload Image to Library',
            res_model: 'report.designer.resource',
            views: [[false, 'form']],
            target: 'new',
            context: {},
        }, {
            onClose: async () => {
                await this.loadLibraryImages();
            }
        });
    }

    closeFieldSelector() {
        this.state.showFieldPopup = false;
        this.state.selectedField = null;
        this.state.selectedVariable = null;
        this.state.fieldSearchQuery = '';
        if (this.templateModelName) {
            this.state.modelId = this.templateModelId;
            this.state.modelName = this.templateModelName;
        }
    }

    // Field type badge label helper
    getFieldTypeBadge(ttype) {
        const map = {
            'integer': 'INT', 'float': 'FLO', 'monetary': 'MON',
            'char': 'CHA', 'text': 'TXT', 'html': 'HTM',
            'boolean': 'BOO', 'date': 'DAT', 'datetime': 'DTM',
            'selection': 'SEL', 'many2one': 'M2O', 'one2many': 'O2M',
            'many2many': 'M2M', 'binary': 'BIN', 'reference': 'REF',
        };
        return map[ttype] || ttype.substring(0, 3).toUpperCase();
    }

    // Field type badge color helper
    getFieldTypeBadgeColor(ttype) {
        const map = {
            'integer': '#4d6ef5', 'float': '#4d6ef5', 'monetary': '#4d6ef5',
            'boolean': '#7c5cbf', 'date': '#0891b2', 'datetime': '#0891b2',
            'selection': '#b45309', 'many2one': '#047857', 'one2many': '#047857', 'many2many': '#047857',
            'char': '#374151', 'text': '#374151', 'html': '#374151',
        };
        return map[ttype] || '#6b7280';
    }

    // Color Picker methods
    get presetColors() {
        return [
            'transparent', '#000000', '#374151', '#4b5563', '#9ca3af', '#e5e7eb', '#ffffff',
            '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16', '#22c55e',
            '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef',
            '#ec4899', '#f43f5e', '#3b427b', '#714B67', '#0f172a', '#1e293b'
        ];
    }

    openColorPicker(target) {
        this.state.colorPickerTarget = target;
        const el = this.activeElement;
        let currentVal = '#ffffff';
        if (el && el.style) {
            currentVal = el.style[target] || (target === 'color' ? '#000000' : '#ffffff');
        }
        this.state.colorPickerValue = currentVal;
        this.state.showColorPicker = true;
    }

    closeColorPicker() {
        this.state.showColorPicker = false;
    }

    selectPresetColor(color) {
        this.state.colorPickerValue = color;
    }

    applyColorPicker() {
        const el = this.activeElement;
        if (el && el.style) {
            el.style[this.state.colorPickerTarget] = this.state.colorPickerValue;
            this.pushHistory();
        }
        this.closeColorPicker();
    }

    async openExpressionEditor(activeColumnId = null) {
        this.state.expressionError = '';
        this.state.expressionSuggestion = '';
        this.state.isValidatingExpression = false;
        this.state.activeColumnId = activeColumnId;
        const el = this.activeElement;
        if (activeColumnId && el && el.type === 'table') {
            const col = el.content.find(c => c.id === activeColumnId);
            this.state.expressionValue = col ? (col.contentExpression || '') : '';
        } else {
            this.state.expressionValue = el ? (el.content || '') : '';
        }
        this.state.showExpressionPopup = true;
        this.state.expressionPopupTab = 'fields';
        this.state.functionSearchQuery = '';
        this.state.expandedFunctionCategory = 'String Functions';
        this.state.fieldSearchQuery = '';
        
        let modelId = this.state.modelId;
        let modelName = this.state.modelName;
        if (el && el.type === 'table' && activeColumnId && el.dataSource) {
            const relInfo = await this.getRelationModelInfo(this.state.modelId, el.dataSource);
            if (relInfo) {
                modelId = relInfo.id;
                modelName = relInfo.name;
            }
        }
        this.state.modelId = modelId;
        this.state.modelName = modelName;
        
        // Pre-load field/variable data
        if (this.state.modelId) {
            const domain = [['model_id', '=', this.state.modelId]];
            if (el && el.type === 'image') {
                domain.push(['ttype', 'in', ['binary', 'many2one']]);
            } else if (el && el.type === 'barcode') {
                domain.push(['ttype', 'in', ['char', 'text']]);
            } else if (el && (el.type === 'text' || el.type === 'field')) {
                domain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
            } else if (el && (el.type === 'section' || el.type === 'table')) {
                if (el.type === 'table' && activeColumnId) {
                    const col = el.content.find(c => c.id === activeColumnId);
                    if (col && col.contentType === 'image') {
                        domain.push(['ttype', 'in', ['binary', 'many2one']]);
                    } else if (col && col.contentType === 'barcode') {
                        domain.push(['ttype', 'in', ['char', 'text']]);
                    } else {
                        domain.push(['ttype', 'in', ['char', 'text', 'html', 'integer', 'float', 'monetary', 'selection', 'date', 'datetime', 'boolean', 'many2one']]);
                    }
                } else {
                    domain.push(['ttype', 'in', ['many2one', 'one2many', 'many2many']]);
                }
            }
            const fields = await this.orm.searchRead(
                'ir.model.fields',
                domain,
                ['name', 'field_description', 'ttype', 'relation'],
                { order: 'field_description asc', limit: 500 }
            );
            this.state.availableFields = fields;
            this.state.rootFields = fields.map(f => ({
                ...f,
                level: 0,
                parentPath: '',
                fullPath: f.name,
                isExpanded: false,
                children: null,
                relationLoaded: false
            }));
            this.rebuildVisibleFields();
        }
    }

    closeExpressionEditor() {
        this.state.showExpressionPopup = false;
        this.state.expressionValue = '';
        this.state.expressionError = '';
        this.state.expressionSuggestion = '';
        this.state.isValidatingExpression = false;
        if (this.templateModelName) {
            this.state.modelId = this.templateModelId;
            this.state.modelName = this.templateModelName;
        }
    }

    async confirmExpression() {
        this.state.expressionError = '';
        this.state.expressionSuggestion = '';
        this.state.isValidatingExpression = true;

        try {
            const result = await this.orm.call(
                'report.designer.template',
                'action_validate_expression',
                [],
                {
                    expression: this.state.expressionValue,
                    model_name: this.state.modelName || null
                }
            );

            this.state.isValidatingExpression = false;

            if (result && !result.valid) {
                this.state.expressionError = result.error || 'Invalid syntax';
                this.state.expressionSuggestion = result.suggestion || '';
                return; // Stop confirmation
            }
        } catch (err) {
            this.state.isValidatingExpression = false;
            console.error("Expression validation call failed:", err);
        }

        const el = this.activeElement;
        if (el) {
            if (this.state.activeColumnId) {
                const col = el.content.find(c => c.id === this.state.activeColumnId);
                if (col) {
                    col.contentExpression = this.state.expressionValue;
                }
                this.state.activeColumnId = null;
            } else {
                el.content = this.state.expressionValue;
            }
            this.pushHistory();
        }
        this.closeExpressionEditor();
    }

    insertIntoExpression(text) {
        const textarea = document.getElementById('expressionTextarea');
        if (textarea) {
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const currentVal = this.state.expressionValue || '';
            this.state.expressionValue = currentVal.substring(0, start) + text + currentVal.substring(end);
            setTimeout(() => {
                textarea.focus();
                textarea.selectionStart = textarea.selectionEnd = start + text.length;
            }, 0);
        } else {
            this.state.expressionValue = (this.state.expressionValue || '') + text;
        }
    }

    onDblClickField(field) {
        const path = field.fullPath || field.name;
        this.insertIntoExpression(`doc.${path}`);
    }

    onDblClickVariable(variable) {
        this.insertIntoExpression(variable.code);
    }

    get functionCategories() {
        return [
            {
                name: "String Functions",
                functions: [
                    { name: "len", code: "len()", desc: "Length of a string or list" },
                    { name: "upper", code: "upper()", desc: "Convert string to uppercase (Use: doc.name.upper())" },
                    { name: "lower", code: "lower()", desc: "Convert string to lowercase (Use: doc.name.lower())" },
                    { name: "str", code: "str()", desc: "Convert value to string" },
                    { name: "format", code: "format()", desc: "Format string" },
                    { name: "strip", code: "strip()", desc: "Remove leading/trailing whitespaces (Use: doc.name.strip())" },
                    { name: "split", code: "split()", desc: "Split string by delimiter (Use: doc.name.split(','))" },
                    { name: "join", code: "join()", desc: "Join list of strings (Use: ','.join(list))" },
                    { name: "startswith", code: "startswith()", desc: "Check prefix (Use: doc.name.startswith('A'))" },
                    { name: "endswith", code: "endswith()", desc: "Check suffix (Use: doc.name.endswith('B'))" },
                    { name: "find", code: "find()", desc: "Find index of substring (Use: doc.name.find('A'))" },
                    { name: "replace", code: "replace()", desc: "Replace substring (Use: doc.name.replace('A', 'B'))" }
                ]
            },
            {
                name: "Math Functions",
                functions: [
                    { name: "abs", code: "abs()", desc: "Absolute value of a number" },
                    { name: "round", code: "round()", desc: "Round a floating point number" },
                    { name: "sum", code: "sum()", desc: "Sum of a list of numbers" },
                    { name: "max", code: "max()", desc: "Maximum value in a list" },
                    { name: "min", code: "min()", desc: "Minimum value in a list" },
                    { name: "int", code: "int()", desc: "Convert value to integer" },
                    { name: "float", code: "float()", desc: "Convert value to float" },
                    { name: "pow", code: "pow()", desc: "Raise a number to power" }
                ]
            },
            {
                name: "Type Conversion",
                functions: [
                    { name: "str", code: "str()", desc: "Convert to string" },
                    { name: "int", code: "int()", desc: "Convert to integer" },
                    { name: "float", code: "float()", desc: "Convert to float" },
                    { name: "bool", code: "bool()", desc: "Convert to boolean" },
                    { name: "list", code: "list()", desc: "Convert to list" },
                    { name: "dict", code: "dict()", desc: "Convert to dictionary" }
                ]
            },
            {
                name: "List Functions",
                functions: [
                    { name: "len", code: "len()", desc: "Get length of list" },
                    { name: "sum", code: "sum()", desc: "Sum of list elements" },
                    { name: "max", code: "max()", desc: "Get maximum element" },
                    { name: "min", code: "min()", desc: "Get minimum element" },
                    { name: "sorted", code: "sorted()", desc: "Return sorted list" },
                    { name: "reversed", code: "reversed()", desc: "Return reversed iterator" },
                    { name: "enumerate", code: "enumerate()", desc: "Enumerate list items" },
                    { name: "zip", code: "zip()", desc: "Zip multiple lists" }
                ]
            },
            {
                name: "Date & Time",
                functions: [
                    { name: "datetime", code: "datetime.datetime", desc: "Datetime class" },
                    { name: "date", code: "datetime.date", desc: "Date class" },
                    { name: "time", code: "datetime.time", desc: "Time class" },
                    { name: "strftime", code: "strftime()", desc: "Format datetime as string" },
                    { name: "strptime", code: "strptime()", desc: "Parse string to datetime" },
                    { name: "today", code: "datetime.date.today()", desc: "Get today's date" },
                    { name: "now", code: "datetime.datetime.now()", desc: "Get current date and time" }
                ]
            },
            {
                name: "Operators",
                functions: [
                    { name: "+", code: " + ", desc: "Addition / Concatenation" },
                    { name: "-", code: " - ", desc: "Subtraction" },
                    { name: "*", code: " * ", desc: "Multiplication" },
                    { name: "/", code: " / ", desc: "Division" },
                    { name: "%", code: " % ", desc: "Modulo" },
                    { name: "==", code: " == ", desc: "Equal to" },
                    { name: "!=", code: " != ", desc: "Not equal to" },
                    { name: "<", code: " < ", desc: "Less than" },
                    { name: ">", code: " > ", desc: "Greater than" },
                    { name: "<=", code: " <= ", desc: "Less than or equal to" },
                    { name: ">=", code: " >= ", desc: "Greater than or equal to" },
                    { name: "and", code: " and ", desc: "Logical AND" },
                    { name: "or", code: " or ", desc: "Logical OR" },
                    { name: "not", code: " not ", desc: "Logical NOT" },
                    { name: "if else", code: "A if condition else B", desc: "Conditional expression" }
                ]
            }
        ];
    }

    get filteredFunctionCategories() {
        const q = (this.state.functionSearchQuery || '').toLowerCase();
        if (!q) return this.functionCategories;
        
        return this.functionCategories.map(cat => {
            const filtered = cat.functions.filter(f => 
                f.name.toLowerCase().includes(q) || 
                f.desc.toLowerCase().includes(q)
            );
            return {
                ...cat,
                functions: filtered
            };
        }).filter(cat => cat.functions.length > 0);
    }

    deleteColumn(colId) {
        const el = this.activeElement;
        if (el && el.type === 'table') {
            el.content = el.content.filter(c => c.id !== colId);
            const percentCols = el.content.filter(c => c.widthType === 'percent');
            if (percentCols.length > 0) {
                const equalWidth = Math.floor(100 / percentCols.length);
                percentCols.forEach(c => {
                    c.widthValue = equalWidth;
                });
                const remainder = 100 - (equalWidth * percentCols.length);
                if (remainder > 0) {
                    percentCols[percentCols.length - 1].widthValue += remainder;
                }
            }
            this.pushHistory();
        }
    }

    addColumn() {
        const el = this.activeElement;
        if (el && el.type === 'table') {
            const nextIndex = el.content.length + 1;
            el.content.push({
                id: `col_${Date.now()}_${nextIndex}`,
                header: `Column ${nextIndex}`,
                footer: '',
                contentType: 'text',
                contentExpression: '',
                widthType: 'percent',
                widthValue: 0
            });
            const percentCols = el.content.filter(c => c.widthType === 'percent');
            if (percentCols.length > 0) {
                const equalWidth = Math.floor(100 / percentCols.length);
                percentCols.forEach(c => {
                    c.widthValue = equalWidth;
                });
                const remainder = 100 - (equalWidth * percentCols.length);
                if (remainder > 0) {
                    percentCols[percentCols.length - 1].widthValue += remainder;
                }
            }
            this.pushHistory();
        }
    }

    setPaperSize(widthMm, heightMm) {
        const MM_TO_PT = 2.83465;
        let w = widthMm;
        let h = heightMm;
        
        // Adjust for current orientation
        if (this.state.orientation === 'landscape') {
            w = Math.max(widthMm, heightMm);
            h = Math.min(widthMm, heightMm);
        } else {
            w = Math.min(widthMm, heightMm);
            h = Math.max(widthMm, heightMm);
        }
        
        if (widthMm === 80 || widthMm === 58) {
            this.state.paperType = 'receipt';
            this.state.pageWidth = 226.7;
            this.state.pageHeight = 396.8;
            this.state.marginTop = 0;
            this.state.marginBottom = 0;
            this.state.marginLeft = 0;
            this.state.marginRight = 0;
        } else {
            this.state.paperType = 'standard';
            this.state.pageWidth = Math.round(w * MM_TO_PT);
            this.state.pageHeight = Math.round(h * MM_TO_PT);
        }
        this.pushHistory();
    }

    updateReceiptRollHeight() {
        if (this.state.paperType !== 'receipt') return;
        
        const page = this.state.pages.find(p => p.id === this.state.activePageId);
        if (!page || !page.elements || page.elements.length === 0) {
            this.state.pageHeight = 300; // minimum default height
            return;
        }
        
        let maxBottom = 0;
        page.elements.forEach(el => {
            const bottom = el.y + el.height;
            if (bottom > maxBottom) {
                maxBottom = bottom;
            }
        });
        
        const computedHeight = Math.max(300, Math.ceil(maxBottom + 40));
        if (this.state.pageHeight !== computedHeight) {
            this.state.pageHeight = computedHeight;
        }
    }

    onChangePaperType(ev) {
        this.state.paperType = ev.target.value;
        if (this.state.paperType === 'receipt') {
            this.state.pageWidth = 226.7;
            this.state.pageHeight = 396.8;
            this.state.marginTop = 0;
            this.state.marginBottom = 0;
            this.state.marginLeft = 0;
            this.state.marginRight = 0;
        }
        this.pushHistory();
    }

    onChangeOrientation(ev) {
        this.state.orientation = ev.target.value;
        const w = this.state.pageWidth;
        const h = this.state.pageHeight;
        if ((this.state.orientation === 'landscape' && w < h) || (this.state.orientation === 'portrait' && w > h)) {
            this.state.pageWidth = h;
            this.state.pageHeight = w;
        }
        this.pushHistory();
    }

    onChangeUnit(ev) {
        this.state.unit = ev.target.value;
        this.pushHistory();
    }

    get pageWidthDisplay() {
        const val = this.state.pageWidth;
        if (this.state.unit === 'mm') {
            return parseFloat((val / 2.83465).toFixed(1));
        } else if (this.state.unit === 'in') {
            return parseFloat((val / 72.0).toFixed(2));
        }
        return parseFloat(val.toFixed(1));
    }

    onChangePageWidth(ev) {
        const val = parseFloat(ev.target.value) || 0;
        if (this.state.unit === 'mm') {
            this.state.pageWidth = val * 2.83465;
        } else if (this.state.unit === 'in') {
            this.state.pageWidth = val * 72.0;
        } else {
            this.state.pageWidth = val;
        }
        this.pushHistory();
    }

    get pageHeightDisplay() {
        const val = this.state.pageHeight;
        if (this.state.unit === 'mm') {
            return parseFloat((val / 2.83465).toFixed(1));
        } else if (this.state.unit === 'in') {
            return parseFloat((val / 72.0).toFixed(2));
        }
        return parseFloat(val.toFixed(1));
    }

    onChangePageHeight(ev) {
        const val = parseFloat(ev.target.value) || 0;
        if (this.state.unit === 'mm') {
            this.state.pageHeight = val * 2.83465;
        } else if (this.state.unit === 'in') {
            this.state.pageHeight = val * 72.0;
        } else {
            this.state.pageHeight = val;
        }
        this.pushHistory();
    }

    get marginTopDisplay() {
        return this.formatMarginDisplay(this.state.marginTop);
    }
    get marginBottomDisplay() {
        return this.formatMarginDisplay(this.state.marginBottom);
    }
    get marginLeftDisplay() {
        return this.formatMarginDisplay(this.state.marginLeft);
    }
    get marginRightDisplay() {
        return this.formatMarginDisplay(this.state.marginRight);
    }

    get headerHeightDisplay() {
        return this.formatMarginDisplay(this.state.headerHeight || 50);
    }

    get footerHeightDisplay() {
        return this.formatMarginDisplay(this.state.footerHeight || 50);
    }

    onChangeHeaderFooter(ev, propertyName) {
        const val = parseFloat(ev.target.value) || 0;
        let ptVal = val;
        if (this.state.unit === 'mm') {
            ptVal = val * 2.83465;
        } else if (this.state.unit === 'in') {
            ptVal = val * 72.0;
        }
        this.state[propertyName] = ptVal;
        this.pushHistory();
    }

    formatMarginDisplay(val) {
        if (this.state.unit === 'mm') {
            return parseFloat((val / 2.83465).toFixed(1));
        } else if (this.state.unit === 'in') {
            return parseFloat((val / 72.0).toFixed(2));
        }
        return parseFloat(val.toFixed(1));
    }

    onChangeMargin(ev, marginName) {
        const val = parseFloat(ev.target.value) || 0;
        let ptVal = val;
        if (this.state.unit === 'mm') {
            ptVal = val * 2.83465;
        } else if (this.state.unit === 'in') {
            ptVal = val * 72.0;
        }
        this.state[marginName] = ptVal;
        this.pushHistory();
    }

    get paperSizes() {
        return [
            { name: 'A0', width: 841, height: 1189 },
            { name: 'A1', width: 594, height: 841 },
            { name: 'A2', width: 420, height: 594 },
            { name: 'A3', width: 297, height: 420 },
            { name: 'A4', width: 210, height: 297 },
            { name: 'A5', width: 148, height: 210 },
            { name: 'A6', width: 105, height: 148 },
            { name: 'A7', width: 74, height: 105 },
            { name: 'A8', width: 52, height: 74 },
            { name: 'A9', width: 37, height: 52 },
            { name: 'B0', width: 1000, height: 1414 },
            { name: 'B1', width: 707, height: 1000 },
            { name: 'B2', width: 500, height: 707 },
            { name: 'B3', width: 353, height: 500 },
            { name: 'B4', width: 250, height: 353 },
            { name: 'B5', width: 176, height: 250 },
            { name: 'B10', width: 31, height: 44 },
            { name: 'C5E', width: 163, height: 229 },
            { name: 'Comm10E', width: 105, height: 241 },
            { name: 'DLE', width: 110, height: 220 },
            { name: 'Executive', width: 191, height: 254 },
            { name: 'Folio', width: 210, height: 330 },
            { name: 'Ledger', width: 432, height: 279 },
            { name: 'Legal', width: 216, height: 356 },
            { name: 'Tabloid', width: 279, height: 432 },
        ];
    }

    get filteredPaperSizes() {
        const q = (this.state.paperSizeSearchQuery || '').toLowerCase();
        if (!q) return this.paperSizes;
        return this.paperSizes.filter(s => 
            s.name.toLowerCase().includes(q) || 
            `${s.width}`.includes(q) || 
            `${s.height}`.includes(q)
        );
    }

    convertToTable() {
        const el = this.activeElement;
        if (el && el.type === 'section') {
            el.type = 'table';
            el.dataSource = el.content || '';
            el.content = [
                { id: 'col1', header: 'Column 1', footer: '', contentType: 'text', contentExpression: '', widthType: 'percent', widthValue: 50 },
                { id: 'col2', header: 'Column 2', footer: '', contentType: 'text', contentExpression: '', widthType: 'percent', widthValue: 50 }
            ];
            el.showHeader = true;
            el.headerHeight = 24;
            el.showFooter = false;
            el.repeatNewPage = true;
            this.pushHistory();
        }
    }
}

registry.category("actions").add("report_designer_action", ReportDesignerApp);
