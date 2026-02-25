# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Advanced Odoo Stripe Fees Extension – Automatic Domestic & International Fee Management",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    Automatically apply Stripe payment fees in Odoo for domestic & international transactions with smart rules and fee-free limits.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Advanced Stripe Fees Extension for Odoo</h1>

        <p class="lead">
        The <b>#1 Odoo Stripe Fees Extension</b> to automatically calculate, apply, and manage payment processing fees with complete transparency. 
        Optimize revenue, reduce accounting errors, and automate Stripe fee handling in Odoo — effortlessly.
        </p>

        <h2>Overview</h2>
        <p>
        The <b>Odoo Stripe Fees Extension</b> is an industry-standard solution designed to automate Stripe payment fee calculation inside Odoo. 
        This advanced module intelligently applies <b>domestic and international Stripe fees</b> during checkout, ensuring accurate invoices and a seamless payment experience.
        </p>
        <p>
        With built-in automation, configurable rules, and smart fee-free limits, this <b>Stripe Fees Extension for Odoo</b> eliminates manual effort and brings enterprise-grade payment transparency to your business.
        </p>

        <h2>Key Features</h2>
        <ul>
        <li><i class="fa fa-check"></i> <b>Domestic & International Fees:</b> Apply different Stripe fees based on customer location.</li>
        <li><i class="fa fa-check"></i> <b>Automatic Fee Calculation:</b> Fees are computed instantly during checkout.</li>
        <li><i class="fa fa-check"></i> <b>Free Fee Above Limit:</b> Automatically waive fees for high-value orders.</li>
        <li><i class="fa fa-check"></i> <b>Transparent Payment Process:</b> Clear fee visibility for customers and accounting teams.</li>
        <li><i class="fa fa-check"></i> <b>Configurable Fee Settings:</b> Fully customizable rules based on business needs.</li>
        <li><i class="fa fa-check"></i> <b>Simple Setup & Use:</b> Plug-and-play configuration, no technical complexity.</li>
        </ul>

        <h2>Detailed Features</h2>
        <ul>
        <li><b>Smart Location-Based Fee Logic:</b> Automatically detects domestic or international transactions.</li>
        <li><b>Threshold-Based Fee Exemption:</b> Set order limits to offer fee-free payments for premium customers.</li>
        <li><b>Accurate Invoicing:</b> Stripe fees are reflected correctly in Odoo invoices and accounting.</li>
        <li><b>Zero Manual Intervention:</b> Completely automated fee management saves time and prevents errors.</li>
        <li><b>Enterprise-Ready:</b> Designed to outperform standard Odoo payment fee handling.</li>
        </ul>

        <h3>FAQs</h3>
        <p><b>Q1: Does this module support both domestic and international Stripe fees?</b><br/>
        Yes. The module automatically applies different fees based on the customer’s country.</p>

        <p><b>Q2: Can I remove Stripe fees for high-value orders?</b><br/>
        Absolutely. You can define a threshold amount above which no fees are applied.</p>

        <p><b>Q3: Is the Stripe fee calculation automatic?</b><br/>
        Yes. Fees are calculated in real-time during checkout with zero manual effort.</p>

        <p><b>Q4: Is this compatible with standard Odoo Stripe payments?</b><br/>
        Yes. It integrates seamlessly with Odoo’s native Stripe payment workflow.</p>

        <h2>Why Choose Us?</h2>
        <ul>
        <li><i class="fa fa-star"></i> Enterprise-grade quality trusted by Odoo professionals</li>
        <li><i class="fa fa-star"></i> Clean, optimized, and future-ready code</li>
        <li><i class="fa fa-star"></i> Regular updates and long-term compatibility</li>
        <li><i class="fa fa-star"></i> Expert Odoo support from industry specialists</li>
        </ul>

        <hr/>

        <p>
        For custom Odoo integrations and CRM enhancements, visit 
        <a href="https://creyox.com" target="_blank">Creyox Technologies</a>
        </p>

        <p>
        Watch the youtube video, visit 
        <a href="https://www.youtube.com/@CreyoxTechnologies" target="_blank">Creyox Technologies YouTube Videos</a>
        </p>

        <p>
        Read our blog post, visit 
        <a href="https://creyox.com/blogs" target="_blank">Creyox Technologies Blogs</a>
        </p>

        <p>
        Visit Our Linkedin Page 
        <a href="https://www.linkedin.com/company/creyox-technologies" target="_blank">
        Creyox Technologies Linkedin Page
        </a>
        </p>

    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
        "views/stripe_payment_fees_badge.xml",
    ],
    'assets': {
        'web.assets_frontend': [
            'cr_stripe_fees_extension/static/src/js/payment_fees_badge.js',
            'cr_stripe_fees_extension/static/src/css/payment_fees_badge.css',
        ],
    },

    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 29,
    "currency": "USD",
}
