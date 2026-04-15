/** @odoo-module **/

import { DocumentsSearchModel } from "@documents/views/search/documents_search_model";
import { patch } from "@web/core/utils/patch";

patch(DocumentsSearchModel.prototype, {
    toggleCategoryValue(sectionId, valueId) {
        // Clear name/search filters when navigating into a folder
        this.query = [];
        super.toggleCategoryValue(sectionId, valueId);
    }
});