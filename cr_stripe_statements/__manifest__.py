# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Advanced Stripe Bank Statement Connector – Real-Time Sync & Automated Accounting",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    Automatically sync Stripe transactions, fees, refunds, and payouts into Odoo bank statements in real time using webhooks. Accurate, fast, and error-free.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Advanced Stripe Bank Statement Connector for Odoo</h1>

        <p class="lead">
        The #1 professional solution to <b>automatically sync Stripe transactions with Odoo bank statements</b>.
        Eliminate manual imports, reduce accounting errors, and keep your Stripe payments perfectly aligned with Odoo in real time.
        </p>

        <blockquote>
        Designed for businesses that demand accuracy, automation, and enterprise-grade accounting integration between Stripe and Odoo.
        </blockquote>

        <h2>Overview</h2>
        <p>
        The <b>Advanced Stripe Bank Statement Connector</b> provides a seamless and reliable integration between Stripe and Odoo.
        Using real-time webhooks, this module captures every Stripe activity—payments, refunds, fees, and payouts—and converts them into clean, structured Odoo bank statement lines automatically.
        </p>

        <p>
        Unlike manual imports or delayed synchronizations, this Stripe to Odoo integration ensures your accounting data is always up to date.
        Stripe fees are recorded separately, payouts are reconciled through internal transfers, and your finance team saves hours of repetitive work.
        </p>

        <h2>Key Features</h2>
        <ul>
        <li><i class="fa fa-check"></i> <b>Real-Time Stripe Sync</b> via secure webhooks</li>
        <li><i class="fa fa-check"></i> <b>Automatic Bank Statement Creation</b> in Odoo</li>
        <li><i class="fa fa-check"></i> <b>Separate Fee Line Handling</b> for precise accounting</li>
        <li><i class="fa fa-check"></i> <b>Charge, Refund & Payout Support</b></li>
        <li><i class="fa fa-check"></i> <b>Auto Internal Transfer Generation</b> for Stripe payouts</li>
        <li><i class="fa fa-check"></i> <b>Seamless Stripe to Odoo Integration</b></li>
        </ul>

        <h2>Detailed Features</h2>
        <ul>
        <li>
            <b>Real-Time Transaction Import:</b>
            Every Stripe event triggers a webhook that instantly syncs data into Odoo without delays or manual actions.
        </li>
        <li>
            <b>Structured Bank Statements:</b>
            Each Stripe transaction is converted into a clean bank statement line, ensuring easy reconciliation.
        </li>
        <li>
            <b>Accurate Fee Accounting:</b>
            Stripe processing fees are recorded as separate lines, giving you full financial transparency.
        </li>
        <li>
            <b>Automated Payout Reconciliation:</b>
            When Stripe deposits funds into your bank, the module automatically creates internal transfers in Odoo.
        </li>
        <li>
            <b>Simple Configuration:</b>
            Quick setup with minimal configuration—no technical complexity.
        </li>
        </ul>

        <h3>FAQs</h3>
        <ul>
        <li>
            <b>Does this module support refunds?</b><br/>
            Yes, Stripe refunds are automatically imported and reflected correctly in Odoo bank statements.
        </li>
        <li>
            <b>Are Stripe fees recorded separately?</b><br/>
            Absolutely. Fees are created as individual statement lines for accurate accounting.
        </li>
        <li>
            <b>Is this real-time or manual sync?</b><br/>
            This module uses Stripe webhooks for real-time synchronization.
        </li>
        <li>
            <b>Does it work with Stripe payouts?</b><br/>
            Yes, payouts are handled automatically with internal transfer creation in Odoo.
        </li>
        </ul>

        <h2>Why Choose Us?</h2>
        <ul>
        <li><i class="fa fa-check"></i> Enterprise-grade accounting accuracy</li>
        <li><i class="fa fa-check"></i> Competes with and enhances Odoo Enterprise workflows</li>
        <li><i class="fa fa-check"></i> Clean code, optimized performance</li>
        <li><i class="fa fa-check"></i> Regular updates & professional support</li>
        <li><i class="fa fa-check"></i> Trusted Stripe & Odoo integration expertise</li>
        </ul>

        <hr/>

        <p>
        For custom Odoo integrations and CRM enhancements, visit 
        <a href="#">Creyox Technologies</a>
        </p>

        <p>
        Watch the youtube video, visit 
        <a href="#">Creyox Technologies YouTube Videos</a>
        </p>

        <p>
        Read our blog post, visit 
        <a href="#">Creyox Technologies Blogs</a>
        </p>

        <p>
        Visit Our Linkedin Page 
        <a href="#">Creyox Technologies Linkedin Page</a>
        </p>

    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/payment_provider.xml",
        "views/account_payment.xml",
        "views/res_config_settings.xml",
    ],
    "external_dependencies": {"python": ["stripe"]},
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 275,
    "currency": "USD",
}
