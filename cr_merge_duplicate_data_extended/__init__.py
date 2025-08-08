# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from . import models

# def create_global_server_actions(env):
#     models = env["ir.model"].search([])
#     for model in models:
#         env['ir.actions.server'].create({
#             'name': 'Find Duplicate Data',
#             'model_id': model.id,
#             'binding_model_id': model.id,
#             'binding_view_types': 'list',
#             'state': 'code',
#             'code': """
# model_name = model._name
# record_ids = records.ids
# action = env['find.duplicate'].open_duplicate_data_wizard(model_name, record_ids)
#             """,
#         })
