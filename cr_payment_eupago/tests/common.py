# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from odoo.addons.payment.tests.common import PaymentCommon


class PaymentEupagoCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.api_key = "mock-eupago-api-key-12345"

        # Find and prepare payment providers for each code
        cls.provider_mbref = cls._prepare_provider(
            "eupago_mbref",
            update_values={
                "cr_eupago_api_key": cls.api_key,
            },
        )
        cls.provider_mbway = cls._prepare_provider(
            "eupago_mbway",
            update_values={
                "cr_eupago_api_key": cls.api_key,
            },
        )
        cls.provider_cc = cls._prepare_provider(
            "eupago_cc",
            update_values={
                "cr_eupago_api_key": cls.api_key,
            },
        )

        # Set default values for tests
        cls.provider = cls.provider_mbref
        cls.amount = 100.00
        cls.currency = cls.currency_euro
        cls.partner = cls.default_partner
