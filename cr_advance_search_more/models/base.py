# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    """Abstract model extending base to support advance search modes and multi-word searching on name_search."""

    _inherit = "base"

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Override name_search to support multi-word search based on active search_mode across all Odoo models."""
        _logger.info(
            "Executing custom name_search for model %s with query: %s", self._name, name
        )

        if name and isinstance(name, str) and operator in ("ilike", "=ilike", "like"):
            search_mode = self.env.context.get("cr_search_mode", "or")
            keywords = [word for word in name.strip().split() if word]

            if search_mode == "not" and keywords:
                _logger.info(
                    "NOT mode name_search on model %s for keywords: %s",
                    self._name,
                    keywords,
                )
                excluded_ids = set()
                for keyword in keywords:
                    res = super(Base, self).name_search(
                        name=keyword, args=args, operator=operator, limit=limit
                    )
                    for rec in res:
                        excluded_ids.add(rec[0])

                not_domain = (args or []) + [("id", "not in", list(excluded_ids))]
                return super(Base, self).name_search(
                    name="", args=not_domain, operator=operator, limit=limit
                )

            if len(keywords) > 1:
                _logger.info(
                    "Multi-word name_search on model %s with mode %s for keywords: %s",
                    self._name,
                    search_mode,
                    keywords,
                )

                if search_mode == "default":
                    return super(Base, self).name_search(
                        name=name, args=args, operator=operator, limit=limit
                    )

                elif search_mode == "and":
                    result_sets = []
                    for keyword in keywords:
                        res = super(Base, self).name_search(
                            name=keyword, args=args, operator=operator, limit=limit
                        )
                        result_sets.append({rec[0]: rec for rec in res})

                    if result_sets:
                        common_ids = set(result_sets[0].keys())
                        for res_dict in result_sets[1:]:
                            common_ids &= set(res_dict.keys())

                        final_results = []
                        for rec in result_sets[0].values():
                            if rec[0] in common_ids:
                                final_results.append(rec)
                                common_ids.remove(rec[0])
                        return final_results[:limit]
                else:
                    # OR mode
                    seen_ids = set()
                    final_results = []
                    for keyword in keywords:
                        res = super(Base, self).name_search(
                            name=keyword, args=args, operator=operator, limit=limit
                        )
                        for rec in res:
                            if rec[0] not in seen_ids:
                                seen_ids.add(rec[0])
                                final_results.append(rec)
                                if limit and len(final_results) >= limit:
                                    break
                        if limit and len(final_results) >= limit:
                            break
                    return final_results

        return super(Base, self).name_search(
            name=name, args=args, operator=operator, limit=limit
        )
