# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from . import controllers
from . import models
from . import wizard

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    setup_provider(env, "eupago_mbref")
    setup_provider(env, "eupago_mbway")
    setup_provider(env, "eupago_cc")

    # Initialize amount limits and redirect form view on install/upgrade
    mbref = env["payment.provider"].search([("code", "=", "eupago_mbref")], limit=1)
    mbway = env["payment.provider"].search([("code", "=", "eupago_mbway")], limit=1)
    cc = env["payment.provider"].search([("code", "=", "eupago_cc")], limit=1)

    redirect_view = env.ref("cr_payment_eupago.redirect_form", raise_if_not_found=False)

    import base64
    from odoo.tools.misc import file_open

    # Load icons
    mb_img, mbway_img, cc_img = False, False, False
    try:
        with file_open("payment/static/img/multibanco.png", "rb") as f:
            mb_img = base64.b64encode(f.read())
        with file_open("payment/static/img/mbway.png", "rb") as f:
            mbway_img = base64.b64encode(f.read())
        with file_open("payment/static/img/card.png", "rb") as f:
            cc_img = base64.b64encode(f.read())
    except Exception:
        pass

    from odoo import Command

    pm_mb = env.ref("payment.payment_method_multibanco", raise_if_not_found=False)
    pm_mw = env.ref("payment.payment_method_mbway", raise_if_not_found=False)
    pm_cc = env.ref("payment.payment_method_card", raise_if_not_found=False)

    if mbref:
        values = {
            "cr_eupago_min_amount": 1.0,
            "cr_eupago_max_amount": 99999.0,
        }
        if redirect_view:
            values["redirect_form_view_id"] = redirect_view.id
        if mb_img:
            values["image_128"] = mb_img
        if pm_mb:
            values["payment_method_ids"] = [Command.set([pm_mb.id])]
        mbref.write(values)
        if pm_mb:
            pm_mb.supported_country_ids = [Command.clear()]

    if mbway:
        values = {
            "cr_eupago_min_amount": 0.1,
            "cr_eupago_max_amount": 99999.0,
        }
        if redirect_view:
            values["redirect_form_view_id"] = redirect_view.id
        if mbway_img:
            values["image_128"] = mbway_img
        if pm_mw:
            values["payment_method_ids"] = [Command.set([pm_mw.id])]
        mbway.write(values)
        if pm_mw:
            pm_mw.supported_country_ids = [Command.clear()]

    if cc:
        values = {
            "cr_eupago_min_amount": 1.0,
            "cr_eupago_max_amount": 3999.0,
        }
        if redirect_view:
            values["redirect_form_view_id"] = redirect_view.id
        if cc_img:
            values["image_128"] = cc_img
        if pm_cc:
            values["payment_method_ids"] = [Command.set([pm_cc.id])]
        cc.write(values)
        if pm_cc:
            pass


def uninstall_hook(env):
    reset_payment_provider(env, "eupago_mbref")
    reset_payment_provider(env, "eupago_mbway")
    reset_payment_provider(env, "eupago_cc")
