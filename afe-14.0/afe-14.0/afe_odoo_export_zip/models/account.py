# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import zipfile
import base64
import io
import logging

from odoo import models, fields, api, _
from datetime import datetime

_logger = logging.getLogger('Export ZIP From E-Invoice')

_einvoice_export_state = [
        ('not_exported', 'Not Exported'),
        ('to_export', 'To Export'),
        ('exported', 'Exported'), ]


class AfeInvoiceExportZip(models.Model):

    _name = 'afe.invoice.export.zip'
    _inherit = ['mail.thread']
    _rec_name = 'zip_file_name'

    date = fields.Datetime(default=datetime.today())
    zip_file_name = fields.Char(copy=False)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    invoices_type = fields.Selection(
        [('in', 'Suppliers Invoices'), ('out', 'Customers Invoices')],
        string='Invoices Type', default='out', copy=False)
    state = fields.Selection(
        [('to_send', 'To Send'), ('to_resend', 'To Resend'), ('sent', 'Sent')],
        string='State', default='to_send', copy=False)
    in_invoices_ids = fields.One2many('afe.einvoice.in', 'afe_export_zip_id',
                                      'Suppliers Invoices', copy=False)
    out_invoices_ids = fields.One2many('account.invoice', 'afe_export_zip_id',
                                       'Customers Invoices', copy=False)
    mail_sending_ids = fields.One2many('mail.mail',
                                       compute='_compute_mail_sending_ids',
                                       string='Mail Sendings')
    company_id = fields.Many2one('res.company', string='Company')

    @api.multi
    def unlink(self):
        # ----- Delete the attachment linked to this class before delete
        #       the records
        for record in self:
            if record.attachment_id:
                record.attachment_id.unlink()
        return super(AfeInvoiceExportZip, self).unlink()

    @api.multi
    def _compute_mail_sending_ids(self):
        mail_model = self.env['mail.mail']
        for record in self:
            record.mail_sending_ids = mail_model.search([
                ('model', '=', record._name),
                ('res_id', '=', record.id), ])

    @api.multi
    def set_to_resend(self):
        for record in self:
            record.state = 'to_resend'

    @api.multi
    def create_zip_from_records(self, records, record_type,
                                xml_attachment_field, xml_file_name_field,
                                company=None):
        if not records:
            return False
        if not company:
            company = self.env.user.company_id
        zip_file_name = '%s.zip' % datetime.now().strftime('%Y%m%d%H%M%s')
        _logger.info(
            'Creating ZIP %s for records: %s' % (zip_file_name, records))
        export_zip_values = {}
        # ----- Create the zip file
        fp = io.BytesIO()
        with zipfile.ZipFile(fp, mode="w") as zip_file:
            for record in records:
                zip_file.writestr(
                    record[xml_file_name_field],
                    base64.b64decode(record[xml_attachment_field]))
        fp.seek(0)
        zip_file_data = fp.read()
        fp.close()
        # ----- Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': zip_file_name,
            'datas': base64.encodestring(zip_file_data),
            'datas_fname': zip_file_name,
            'type': 'binary',
            'res_model': self._name,
            })
        # ----- Register the ZIP export in a odoo model
        export_zip_values = {
            'zip_file_name': zip_file_name,
            'attachment_id': attachment.id,
            'invoices_type': record_type,
            'state': 'to_send',
            'company_id': company.id,
            }
        export_zip = self.create(export_zip_values)
        attachment.res_id = export_zip.id
        return export_zip

    @api.model
    def cron_send_zip_by_mail(self):
        odoo_export_zip_list = self.search([
            ('state', 'in', ('to_send', 'to_resend'))])
        company = self.env.user.company_id
        mail_model = self.env['mail.mail']
        sending_mail = company.afe_exported_zip_mail
        if not sending_mail:
            raise Warning(
                _('Set an email for sending ZIP in company configuration'))
        body = _('''
            {company} sents a ZIP file with XML of invoices inside
            '''.format(company=company.name))
        for odoo_export_zip in odoo_export_zip_list:
            _logger.info('Sending ZIP %s by mail' % odoo_export_zip)
            values = {
                'subject': _(
                    'ZIP with XML from {company}'.format(company=company.name)
                    ),
                'email_from': company.email,
                'email_to': sending_mail,
                'body_html': body,
                'body': body,
                'res_id': odoo_export_zip.id,
                'model': odoo_export_zip._name,
                'attachment_ids': [(6, 0, [odoo_export_zip.attachment_id.id])],
                }
            odoo_mail = mail_model.create(values)
            # ----- Send email
            if odoo_mail:
               odoo_mail.send()
               odoo_export_zip.state = 'sent'


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    einvoice_export_state = fields.Selection(
        _einvoice_export_state, string='E-Invoice Export State',
        default='not_exported', copy=False)
    afe_export_zip_id = fields.Many2one('afe.invoice.export.zip',
                                        string='Export ZIP')

    @api.model
    def cron_afe_export_zip(self):
        for company in self.sudo().env['res.company'].search([]):
            # company = self.env.user.company_id
            invoices = self.search([
                ('einvoice_export_state', '=', 'to_export'),
                ('company_id', '=', company.id),
                ])
            attachments = [invoice.fatturapa_attachment_out_id 
                        for invoice in invoices
                        if invoice.fatturapa_attachment_out_id]
            odoo_zip_export = self.env['afe.invoice.export.zip'].\
                create_zip_from_records(
                    attachments, 'out', 'datas', 'datas_fname', company)
            if odoo_zip_export:
                invoices.write({
                    'einvoice_export_state': 'exported',
                    'afe_export_zip_id': odoo_zip_export.id,
                    })


class AfeEinvoiceIn(models.Model):

    _inherit = "afe.einvoice.in"

    einvoice_export_state = fields.Selection(
        _einvoice_export_state, string='E-Invoice Export State',
        default='not_exported', copy=False)
    afe_export_zip_id = fields.Many2one('afe.invoice.export.zip',
                                        string='Export ZIP')

    @api.model
    def cron_afe_export_zip(self):
        for company in self.sudo().env['res.company'].search([]):
            # company = self.env.user.company_id
            invoices = self.search([
                ('einvoice_export_state', '=', 'to_export'),
                ('company_id', '=', company.id),
                ])
            odoo_zip_export = self.env['afe.invoice.export.zip'].\
                create_zip_from_records(
                    invoices, 'in', 'p7m_file', 'p7m_file_name', company)
            if odoo_zip_export:
                invoices.write({
                    'einvoice_export_state': 'exported',
                    'afe_export_zip_id': odoo_zip_export.id,
                    })
