# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import datetime
import requests
import json
import base64

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError


_logger = logging.getLogger('Export ZIP From E-Invoice')


class WizardExportZipFromEinvoice(models.TransientModel):

    _name = "wizard.export.zip.from.einvoice"
    _description = "Generate ZIP with XML from einvoices"

    @api.multi
    def export_einvoice(self):
        invoice_ids = self.env.context.get('active_ids', [])
        model = self.env.context.get('active_model', '')
        for invoice in self.env[model].browse(invoice_ids):
            if invoice.einvoice_export_state != 'not_exported':
                record_name = invoice.name_get()[0][1]
                raise UserError(_(
                    'Error on invoice %s. \n'
                    'Export only invoices not exported, yet!') % record_name)
            invoice.einvoice_export_state = 'to_export'
        return True
