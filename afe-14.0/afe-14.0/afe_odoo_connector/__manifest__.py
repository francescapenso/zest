# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3 or later (https://www.gnu.org/licenses/agpl-3.0).

{
    'name': 'AFE - Fatturazione elettronica attraverso SDI',
    'summary': 'Invia e ricevi fatture elettroniche con Odoo,'
               'tieni il controllo di ogni singola fattura elettronica',
    'version': '14.0.1.0.0',
    'category': 'Account',
    'author': 'Apulia Software s.r.l.',
    'website': 'https://www.apuliasoftware.it',
    'license': 'AGPL-3',
    'support': 'afesupport@apuliasoftware.org',
    'price': '500.00',
    'currency': 'EUR',
    'depends': [
        'account',
        'l10n_it_fatturapa',
        'l10n_it_fatturapa_out',
        'l10n_it_fatturapa_in',
        'sale',
        'web',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/company_view.xml',
        'views/attachment_view.xml',
        'wizard/send_invoice_view.xml',
        'views/account_view.xml',
        'data/cron.xml',
    ],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
}
