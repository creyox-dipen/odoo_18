# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Statement Collection | Stripe Auto Bank Statements | Stripe Auto Import Transactions | Auto Sync Stripe Transactions",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    This module enables you to automatically import Stripe transactions into Odoo, using webhook responses. Whenever a charge, refund, or payout occurs in Stripe, the module listens for the event and creates corresponding bank statement lines in Odoo. At the same time, it also records fees as separate lines, links them to a Stripe fee partner, and readies everything for reconciliation with existing payments.

    It further supports payout handling by creating internal transfers in the designated journal when Stripe sends money into your bank account, thus making reconciliation smoother. With minimal setup (just configure Stripe as a provider and map journals/accounts), the module streamlines the flow from Stripe → statements → reconciliation, reducing manual import.
    """,
    "license": "OPL-1",
    "version": "18.0.0.3",
    "description": """
    <h1>Stripe Statement Collection for Odoo</h1>

    <p class="lead">
    The <b>Stripe Statement Collection</b> for Odoo. Instantly sync Stripe payments, refunds, fees, and payouts into Odoo bank statements with full reconciliation readiness.Stop manual imports. Eliminate reconciliation errors. Let Stripe transactions flow into Odoo accounting automatically.The <b>Stripe Statement Collection for Odoo</b> is a professional-grade accounting automation module that listens to Stripe webhooks and automatically creates clean, reconciliation-ready bank statement lines in Odoo.
    </p>

    <h2>Key Features</h2>

    <ul>
        <li>Real-time Stripe sync through webhooks.</li>
        <li>Automatic Stripe statement collection</li>
        <li>Separate line for fees</li>
        <li>Handles charge, refund, and payout</li>
        <li>Auto internal transfer creation</li>
        <li>Stripe to Odoo integration</li>
    </ul>

    <h2>Benefits</h2>
    <ul>
        <li>Automatically imports Stripe statements directly into Odoo.</li>
        <li>Creates separate lines for Stripe processing fees.</li>
        <li>Generates bank statements ready for quick reconciliation.</li>
        <li>Accurately maps Stripe transactions to corresponding accounts.</li>
        <li>Keeps accounting records clean, accurate, and fully automated.</li>
        <li>Integrates Stripe payment data seamlessly with Odoo journals.</li>
    </ul>

    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_stripe_statements">Stripe Statement Collection</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_payment_stripe_ext">Payment Stripe Extension in Odoo</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_stripe_ach">Stripe ACH Invoice Integration</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_stripe_fees_extension">Stripe Fees Extension</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_stripe_refund_payment">Stripe Refund Invoice Payment</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_ent_stripe_statements">Stripe Statement Collection Enterprise</a></li>
    </ul>

    <h3>FAQs</h3>

    <p><b>Q1: What does this module do?</b><br/>
    This module automatically imports and syncs Stripe statements into Odoo through webhook responses. It creates bank statements, separates fees, and handles charges, refunds, and payouts.
    </p>

    <p><b>Q2: Do I need to upload Stripe statements manually?</b><br/>
    No, the module automatically imports statements in real time once Stripe webhook is configured.
    </p>

    <p><b>Q3: Will Stripe fees be tracked separately?</b><br/>
    Yes, the module creates a separate line for each Stripe fee so it’s easy to reconcile and report.
    </p>

    <p><b>Q4: Is this compatible with Odoo Accounting & Enterprise workflows?</b><br/>
    Yes. The module is built to work seamlessly with Odoo Accounting, reconciliation widgets, and enterprise-grade finance processes.
    </p>

    <h2>Why Choose Us?</h2>

    <ul>
      <li>Built by <b>Stripe & Odoo Accounting Experts</b></li>
      <li>Enterprise-grade performance & clean data models</li>
      <li>Optimized for high-volume Stripe transactions</li>
      <li>Clean, upgrade-safe & well-documented code</li>
      <li>Professional support & regular updates</li>
    </ul>

    <hr/>

    <p>For custom Odoo payment integrations, visit <a href="https://creyox.com">creyox.com</a></p>
    <p>Watch the YouTube video: <a href="https://youtu.be/z8x2s7jk0sc">Stripe Statement Collection</a></p>
    <p>Read our blog: <a href="https://creyox.com/blog">https://creyox.com/blog</a></p>
    """,
    "depends": ["base", "payment_stripe", "accountant", "account_asset"],
    "external_dependencies": {"python": ["stripe"]},
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/payment_provider.xml",
        "views/account_payment.xml",
        # "views/res_config_settings.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 275,
    "currency": "USD",
}
