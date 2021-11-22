# -*- coding: utf-8 -*-
# Copyright 2018 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


import logging
import datetime
import requests
import json
import base64

from odoo.addons.afe_odoo_connector.afe import get_alive

from odoo import models, fields, api, _
from odoo.exceptions import Warning


_logger = logging.getLogger('Sending E-Invoice')


class WizardSendInvoice(models.TransientModel):

    _name = "wizard.send.invoice"
    _description = "Wizard For Sending E-Invoice"

    def _check_invoices_before_sending(self, invoices):
        errors = []
        for invoice in invoices:
            if not invoice.partner_id.electronic_invoice_subjected:
                errors.append((
                    invoice.partner_id.name,
                    _('Partner is not electronic invoice subjected')))
            if not invoice.journal_id.e_invoice:
                errors.append((invoice.name, _('Selected journal is '
                                                 'incorrect.'
                                                 '\nIs not E-invoice')))
            elif invoice.state in ('draft', 'cancel'):
                errors.append((invoice.name, _('is not validate')))
            elif invoice.einvoice_state in ('sending', 'sent', 'done'):
                errors.append((invoice.name, _('has already been processed')))
        if errors:
            text = u'The following invoices have errors:\n'
            for error in errors:
                text = text + u'{n} - {e}\n'.format(n=error[0], e=error[1])
            raise Warning(_(text))

    def set_invoices_to_send(self):
        invoice_ids = self.env.context.get('active_ids', [])
        if not invoice_ids:
            raise Warning('No invoices to send')
        invoice_model = self.env['account.move']
        invoices = invoice_model.browse(invoice_ids)
        self._check_invoices_before_sending(invoices)
        company = self.env.user.company_id
        for invoice in invoices:
            # ----- Try to generate documents (PDF or XML) to send
            try:
                file_name = '%s%s' % (
                    invoice.company_id.partner_id.vat,
                    invoice.name.replace('/', '_'))
                wiz_exp = self.env['wizard.export.fatturapa'].create({})
                if wiz_exp._fields.get('include_ddt_data', False):
                    wiz_exp.include_ddt_data = 'dati_ddt'
                wiz_exp.with_context(
                    active_ids=[invoice.id, ]).exportFatturaPA()
                if not invoice.fatturapa_attachment_out_id:
                    raise Warning(_('XML is not ready'))
            except Exception as invoice_error:
                error_text = _('Error in invoice %s:\n\n%s') % (
                    invoice.name, invoice_error)
                raise Warning(error_text)
            # ----- Update history log and state
            note = 'Fattura in preparazione ' \
                   'per essere inviata in data {}'.format(
                        datetime.datetime.strftime(
                            datetime.datetime.now(),
                            "%d-%m-%Y %H:%M:%S"))
            history_val = {
                'name': invoice.id,
                'date': datetime.datetime.now(),
                'note': note,
                'status_code': 'afe_sending',
                'status_desc': 'INVOICE AFE SENDING',
                'uuid_afe': None,
                'type': 'positive',
                }
            invoice.history_change = [(0, 0, history_val)]
            invoice.einvoice_state = 'sending'
        return {'type': 'ir.actions.act_window_close'}
