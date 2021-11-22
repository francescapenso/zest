# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3 or later (https://www.gnu.org/licenses/agpl-3.0).

{
    'name': 'AFE - Fatturazione elettronica export verso il consulente',
    'summary': 'Invia e ricevi le fatture elettroniche al tuo consulente,'
               'ogni fattura elettronica viene inserita in un archivio zip'
               'ed inviata agli indirizzi email configurati',
    'version': '14.0.1.0.0',
    'category': 'Account',
    'price': 0,
    'currency': 'EUR',
    'author': 'Apulia Software s.r.l.',
    'website': 'https://www.apuliasoftware.it',
    'license': 'AGPL-3',
    'support': 'afesupport@apuliasoftware.org',
    'depends': [
        'account',
        'afe_odoo_connector',
    ],
    'data': [
        'views/company_view.xml',
        'views/account_view.xml',
        'wizard/export_zip_view.xml',
        'data/cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'images': ['static/description/main_screenshot.png'],
    'installable': False,
}
