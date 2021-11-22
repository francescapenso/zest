# -*- coding: utf-8 -*-
# Copyright 2018 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import json
import logging
import os
import re
from datetime import datetime
from pdb import Pdb

import lxml.etree as ET
import requests

from odoo import _, api, fields, models
from odoo.exceptions import Warning, UserError
from odoo.addons.afe_odoo_connector.afe import (apply_xsl_to_xml,
                                                   convert_html_to_pdf,
                                                   extract_xml_from_p7m,
                                                   get_alive)

_logger = logging.getLogger('E-Invoice Management')

try:
    from asn1crypto import cms
except (ImportError, IOError) as err:
    _logger.debug(err)


'''re_base64 = re.compile(
    br'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$')

def is_base64(s):
    s = s or b""
    s = s.replace(b"\r", b"").replace(b"\n", b"")
    return re_base64.match(s)'''


TYPES = {
    'out_invoice': 'invoice_out',
    'in_invoice': 'invoice_in',
    'out_refund': 'refund_out',
    'in_refund': 'refund_in'
}


class AccountMove(models.Model):

    _inherit = "account.move"

    _einvoice_state = [
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('error', 'Error'),
        ('done', 'Complete')]

    _complete_einvoice_status_codes = (
        'INVIATO_IN_CONSERVAZIONE',
        )

    history_ftpa = fields.Text(string='Storico Trasmissione', copy=False)
    sdi_file_name = fields.Char('Sdi File Name', size=128, copy=False)
    xml_p7m_file = fields.Binary(copy=False)
    xml_p7m_file_name = fields.Char(copy=False)
    einvoice_state = fields.Selection(_einvoice_state,
                                      string='E-Invoice State',
                                      default='draft', copy=False)
    history_change = fields.One2many('einvoice.history', 'name',
                                     string='Historic Change', copy=False)
    uuid_afe = fields.Char(copy=False)
    einvoice_pdf_file = fields.Binary(copy=False)
    einvoice_pdf_file_name = fields.Char(copy=False)

    def _get_state_led_einvoice(self):
        for invoice in self:
            if invoice.einvoice_state in ('sending', 'sent', 'done'):
                invoice.state_led = True
            else:
                invoice.state_led = False
    state_led = fields.Boolean(compute='_get_state_led_einvoice')

    def view_preview_invoice_file(self):
        if self.state_led:
            url = self.fatturapa_attachment_out_id.ftpa_preview_link
            return {
                'name'     : 'preview XML',
                'res_model': 'ir.actions.act_url',
                'type'     : 'ir.actions.act_url',
                'target'   : 'current',
                'url'      : url,
            }
        else:
            if self.state == 'open':
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.send.invoice',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                }

    def api_send_invoice(self):
        self.ensure_one()
        invoice = self
        company = invoice.company_id
        get_alive(self, company=company)
        file_type = 'xml'
        xml_file_obj = self.env['fatturapa.attachment.out']
        id_xml_file = invoice.fatturapa_attachment_out_id.id
        inv_file = xml_file_obj.browse(id_xml_file).datas
        inv_file = bytes.decode(inv_file)
        url = "{}/invoices/send".format(company.afe_api_url)
        token = company.afe_token
        payload = '{' \
            '"file_type": "%s",'\
            '"source": "odoo",' \
            '"invoice_type": "%s",' \
            '"partner_vat": "%s",' \
            '"invoice_number": "%s",' \
            '"invoice_content": "%s",' \
            '"invoice_date": "%s 00:00:00"' \
            '}' % (file_type,
                   TYPES[invoice.move_type],
                   invoice.company_id.vat,
                   invoice.name,
                   inv_file,
                   invoice.invoice_date
                   )
        headers = {
            'Authorization': "Token {t}".format(t=token),
            'Content-Type': "application/json"
            }
        response = requests.post(url, data=payload, headers=headers)
        response_data = json.loads(response.text)
        # ----- If response doesn't contain status_code 200,
        # -----there is some error
        if response.status_code != 200:
            text_error = response_data['error']
            raise Warning(_(u'{c}.\n{t}'.format(c=response.status_code,
                                               t=text_error)))
        return response_data

    def api_resend_invoice(self):
        self.ensure_one()
        invoice = self
        company = invoice.company_id
        get_alive(self, company=company)
        file_type = 'xml'
        xml_file_obj = self.env['fatturapa.attachment.out']
        id_xml_file = invoice.fatturapa_attachment_out_id.id
        inv_file = xml_file_obj.browse(id_xml_file).datas
        inv_file = bytes.decode(inv_file)
        url = "{}/invoices/resend".format(company.afe_api_url)
        token = company.afe_token
        payload = '{' \
            '"file_type": "%s",'\
            '"source": "odoo",' \
            '"invoice_type": "%s",' \
            '"partner_vat": "%s",' \
            '"invoice_number": "%s",' \
            '"invoice_content": "%s",' \
            '"invoice_date": "%s 00:00:00",' \
            '"uuid": "%s"' \
            '}' % (file_type,
                   TYPES[invoice.move_type],
                   invoice.company_id.vat,
                   invoice.name,
                   inv_file,
                   invoice.invoice_date,
                   invoice.uuid_afe
                   )
        headers = {
            'Authorization': "Token {t}".format(t=token),
            'Content-Type': "application/json"
            }
        response = requests.post(url, data=payload, headers=headers)
        response_data = json.loads(response.text)
        # ----- If response doesn't contain status_code 200,
        # -----there is some error
        if response.status_code != 200:
            text_error = response_data['error']
            raise Warning(_(u'{c}.\n{t}'.format(c=response.status_code,
                                               t=text_error)))
        return response_data

    def send_einvoice(self):
        self.ensure_one()
        invoice = self
        company = invoice.company_id
        _logger.info("Sending Invoice {invoice} of company {company}".format(
            invoice=invoice.name, company=company.name))
        get_alive(self, company=company)
        if invoice.uuid_afe:
            invoice.api_resend_invoice()
        else:
            resp = invoice.api_send_invoice()
            invoice.uuid_afe = resp['invoice']['uuid']
        # ----- Update history log
        note = 'Fattura inviata in data {}'.format(
            datetime.strftime(datetime.now(), "%d-%m-%Y %H:%M:%S"))
        history_val = {
            'name': invoice.id,
            'date': datetime.now(),
            'note': note,
            'status_code': 'afe_sent',
            'status_desc': 'INVOICE AFE SENT',
            'uuid_afe': None,
            'type': 'positive',
        }
        invoice.history_change = [(0, 0, history_val)]
        invoice.einvoice_state = 'sent'
        return True

    def convert_timestamp(self, value):
        return datetime.fromtimestamp(
            int(value)/1e3).strftime('%Y-%m-%d %H:%M:%S')

    def download_remote_invoice_file(self, uuid_file):
        get_alive(self)
        url = "{url}/file/{uuid}/download".format(
            url=self.env.user.company_id.afe_api_url,
            uuid=uuid_file
        )
        token = self.env.user.company_id.afe_token
        headers = {
            'Authorization': "Token {t}".format(t=token),
            }
        response = requests.get(url, headers=headers)
        # ----- If response doesn't contain status_code 200,
        # ----- there is some error
        if response.status_code != 200:
            text_error = response.reason
            raise Warning(_(u'Download File:\n'
                            '{c}.\n{t}'.format(
                c=response.status_code, t=text_error)
            ))
        return response._content

    def check_einvoice_remote_file(self, company_id=False):
        if not company_id:
            company_id = self.env.user.company_id
        get_alive(self, company_id)
        url = "{url}/invoice/{uuid}/files".format(
            url=company_id.afe_api_url,
            uuid=self.uuid_afe
        )
        token = company_id.afe_token
        headers = {
            'Authorization': "Token {t}".format(t=token),
            }
        response = requests.get(url, headers=headers)
        response_data = json.loads(response.text)
        # ----- If response doesn't contain status_code 200,
        # ----- there is some error
        if response.status_code != 200:
            text_error = response_data['error']
            raise Warning(_(u'Remote File:\n'
                            '{c}.\n{t}'.format(
                c=response.status_code, t=text_error)
            ))
        # ----- download last file of invoice
        if response_data['files'] and len(response_data['files']) > 0:
            file = response_data['files'][0]
            file_content = self.download_remote_invoice_file(file['uuid'])
            self.xml_p7m_file = base64.b64encode(file_content)
            self.xml_p7m_file_name = file['name']

    def send_notify_error_invoice(self, company_id=False):
        if not company_id:
            company_id = self.env.user.company_id
        odoobot = self.env.user.browse(1)
        partner_ids = [u.partner_id.id for u in company_id.notify_users]
        body = _('''
        You have an error on invoice number {n}. 
        View history status of invoice to have more information.
        '''.format(n=self.name))
        if partner_ids:
            self.message_post(
                body=body, 
                partner_ids=partner_ids,
                author_id=odoobot.partner_id.id,
                subtype_id=self.env.ref('mail.mt_note').id,
                subject=_("Error State Invoice"),
                record_name=self.name
                )

    def check_einvoice_status(self):
        for invoice in self:
            einvoice_history_model = self.env['einvoice.history']
            einvoice_history_model.with_context(
                afe_force_check_status_invoice_id=invoice.id,
            ).cron_check_new_status()

    def cron_send_einvoice(self):
        # ----- Get one by one invoice to send
        invoice = self.env['account.move'].sudo().search([
            ('einvoice_state', '=', 'sending')], limit=1)
        if invoice:
            # ----- Try to send invoice and register errors if we get them
            try:
                invoice.send_einvoice()
            except Exception as sending_error:
                note = 'Fattura non inviata per errore: {}'.format(
                    sending_error)
                history_val = {
                    'name': invoice.id,
                    'date': datetime.now(),
                    'note': note,
                    'status_code': 'afe_sent_error',
                    'status_desc': 'INVOICE AFE SENT ERROR',
                    'uuid_afe': None,
                    'type': 'error',
                    }
                invoice.history_change = [(0, 0, history_val)]
                invoice.einvoice_state = 'error'

    def cron_complete_einvoice(self):
        # ----- Get all invoices in sent state and move them to complete 
        #       if there is at least one complete set state
        invoices = self.env['account.move'].sudo().search([
            ('einvoice_state', '=', 'sent')])
        for invoice in invoices:
            if not invoice.history_change:
                continue
            history_changes = invoice.history_change.filtered(
                lambda r:
                r.status_code in invoice._complete_einvoice_status_codes)
            if history_changes:
                status_descriptions = ','.join([
                    hc.status_desc for hc in history_changes])
                invoice.einvoice_state = 'done'
                _logger.info('E-Invoice %s completed for states: %s' % (
                    invoice.name, status_descriptions))

    def button_draft(self):
        if self.filtered(lambda inv: inv.einvoice_state in ['sent', 'done']):
            raise Warning(_("Can't not cancel sent invoice"))
        return super(AccountMove, self).button_draft()


class AccountJournal(models.Model):

    _inherit = "account.journal"

    e_invoice = fields.Boolean(
        string='Electronic Invoice',
        help="Check this box to determine that each entry of this journal\
            will be managed with Italian Electronical Invoice.", default=False)

    def get_journal_dashboard_datas(self):
        """
        Inherit for add in dashboard of account number of einvoice to sent
        and einvoice in error
        """
        res = super(AccountJournal, self).get_journal_dashboard_datas()
        number_einvoice_error = number_einvoice_draft = 0
        if self.type == 'sale':
            (query, query_args) = self._get_sent_error_ebills_query()
            self.env.cr.execute(query, query_args)
            query_einvoice_error = self.env.cr.dictfetchall()

            (query, query_args) = self._get_draft_ebills_query()
            self.env.cr.execute(query, query_args)
            query_einvoice_draft = self.env.cr.dictfetchall()

            curr_cache = {}
            (number_einvoice_error) = self._count_results_einvoice_error(query_einvoice_error, curr_cache=curr_cache)
            (number_einvoice_draft) = self._count_results_einvoice_draft(query_einvoice_draft, curr_cache=curr_cache)
 
            res.update({
                'number_einvoice_error': number_einvoice_error,
                'number_einvoice_draft': number_einvoice_draft,
                })
        return res

    def _get_sent_error_ebills_query(self):
        """
        Returns a tuple containing as its first element the SQL query used to
        gather the ebills in error state, and the arguments
        dictionary to use to run it as its second.
        """
        return ('''
            SELECT
                move.move_type,
                move.invoice_date,
                move.company_id
            FROM account_move move
            WHERE move.journal_id = %(journal_id)s
            AND move.einvoice_state = 'error'
            AND move.move_type IN ('out_invoice', 'out_refund');
        ''', {'journal_id': self.id})

    def _count_results_einvoice_error(self, results_dict, curr_cache=None):
        """ 
        Loops on a query result to count the total number of e-invoices
        in error state of sent
        """
        rslt_count = 0
        curr_cache = {} if curr_cache is None else curr_cache
        for result in results_dict:
            company = self.env['res.company'].browse(result.get('company_id')) or self.env.company
            rslt_count += 1
            date = result.get('invoice_date') or fields.Date.context_today(self)
        return (rslt_count)

    def _get_draft_ebills_query(self):
        """
        Returns a tuple containing as its first element the SQL query used to
        gather the e-bills in draft state, and the arguments
        dictionary to use to run it as its second.
        """
        return ('''
            SELECT
                move.move_type,
                move.invoice_date,
                move.company_id
            FROM account_move move
            WHERE move.journal_id = %(journal_id)s
            AND move.einvoice_state = 'draft'
            AND move.state = 'posted'
            AND move.move_type IN ('out_invoice', 'out_refund');
        ''', {'journal_id': self.id})

    def _count_results_einvoice_draft(self, results_dict, curr_cache=None):
        """ 
        Loops on a query result to count the total number of invoices
        confirmed to send which electronic invoice
        """
        rslt_count = 0
        curr_cache = {} if curr_cache is None else curr_cache
        for result in results_dict:
            company = self.env['res.company'].browse(result.get('company_id')) or self.env.company
            rslt_count += 1
            date = result.get('invoice_date') or fields.Date.context_today(self)
        return (rslt_count)


class EinvoiceHistory(models.Model):

    _name = "einvoice.history"
    _order = 'date'

    name = fields.Many2one('account.move', required=True,
                           ondelete='cascade')
    date = fields.Datetime(string='Date Action', required=True)
    note = fields.Text()
    status_code = fields.Char(size=25)
    status_desc = fields.Text()
    xml_content = fields.Text()
    uuid_afe = fields.Char()
    type = fields.Selection([
        ('positive', 'OK'),
        ('error', 'ERROR')
    ])

    def cron_check_new_status(self):
        # ----- Check all new status of invoices from the last check date
        company_model = self.env['res.company']
        invoice_model = self.env['account.move']
        # ----- It's possibile to force check only for one company by passing
        #       its id through context
        force_invoice = False
        if self.env.context.get('afe_force_check_status_company_id', False):
            companies = [company_model.browse(
                self.env.context['afe_force_check_status_company_id']), ]
        elif self.env.context.get('afe_force_check_status_invoice_id', False):
            force_invoice = invoice_model.browse(
                self.env.context['afe_force_check_status_invoice_id'])
            companies = [force_invoice.company_id, ]
        else:
            companies = company_model.search([('afe_active', '=', True)])
        today = datetime.today().strftime('%Y-%m-%d')
        # ----- Cron can be executed from admin user so it's better to check 
        #       all the companies datas
        for company in companies:
            # ----- Get alive for every company to check the company datas
            get_alive(self, company)
            _logger.info("Check invoices status for {c}".format(
                c=company.name))
            if force_invoice:
                url = "{url}/invoice/{uuid}/states".format(
                    url=company.afe_api_url,
                    uuid=force_invoice.uuid_afe
                )
            else:
                url = "{url}/states/{date}".format(
                    url=company.afe_api_url,
                    date=company.afe_last_status_check
                    if company.afe_last_status_check else '2018-01-01')
            token = company.afe_token
            headers = {
                'Authorization': "Token {t}".format(t=token),
                }
            response = requests.get(url, headers=headers)
            response_data = json.loads(response.text)
            # ----- Check error from API call
            if response.status_code != 200:
                text_error = response_data['error']
                _logger.warning(
                    "Check invoices status error for company {company}: " \
                    "[{code}] {t}".format(
                        company=company.name,
                        code=response.status_code,
                        t=text_error))
                continue
            for state in response_data['states']:
                # ----- If state already exixts, do nothing
                if self.search([('uuid_afe', '=', state['uuid'])]):
                    continue
                elif not force_invoice and not state.get('invoice', ''):
                    continue
                else:
                    invoice = invoice_model.search([
                        ('uuid_afe', '=', state['invoice'])]) \
                        if not force_invoice else force_invoice
                    if not invoice:
                        _logger.warning(
                            "No invoice for status {uuid}: " \
                            "[{code}] {desc}".format(
                                uuid=state['uuid'],
                                code=state['code'],
                                desc=state['description']))
                        continue
                    # ----- Crate the state linked to invoice
                    self.create({
                        'name': invoice.id,
                        'date': state['date'],
                        'note': state['note'],
                        'status_code': state['code'],
                        'status_desc': state['description'],
                        'uuid_afe': state['uuid'],
                        'type': state['type'], })
                    _logger.info(
                        "Status {uuid} created for invoice {inv}: ".format(
                            uuid=state['uuid'],
                            inv=invoice.name,
                            ))
                    # ----- Send message to company notify email
                    #       if there is an error
                    if state['type'] == 'error':
                        invoice.einvoice_state = 'error'
                        invoice.send_notify_error_invoice(company)
            # ----- Set the date for the future checks
            company.afe_last_status_check = today


class FatturaPAAttachmentIn(models.Model):
    
    _inherit = "fatturapa.attachment.in"
    
    uuid_afe = fields.Char()
    supp_number = fields.Char()
    date_in_invoice = fields.Date(compute="_inverse_get_date", store=True, readonly=0)

    @api.depends('invoices_date')
    def _inverse_get_date(self):
        for attach_in in self:
            if not attach_in.invoices_date and attach_in.date_in_invoice:
                attach_in.write({
                    "invoices_date": datetime.strftime(
                    attach_in.date_in_invoice, "%Y-%m-%d")})
            elif attach_in.invoices_date and not attach_in.date_in_invoice:
                datas = attach_in.invoices_date.split(',')
                attach_in.date_in_invoice = datetime.strptime(
                    datas[0], "%d/%m/%Y")

    def download_remote_invoice_file(self, uuid_file, company_id=False):
        if not company_id:
            company_id = self.env.user.company_id
        get_alive(self, company_id)
        url = "{url}/file/{uuid}/download".format(
            url=company_id.afe_api_url,
            uuid=uuid_file
        )
        token = company_id.afe_token
        headers = {
            'Authorization': "Token {t}".format(t=token),
            }
        response = requests.get(url, headers=headers)
        # ----- If response doesn't contain status_code 200,
        # ----- there is some error
        if response.status_code != 200:
            text_error = response.reason
            raise Warning(_(u'Download File:\n'
                            '{c}.\n{t}'.format(
                c=response.status_code, t=text_error)
            ))
        return response._content

    def check_einvoice_remote_file(self, env_in_uuid, company_id):
        if not company_id:
            company_id = self.env.user.company_id
        get_alive(self, company_id)
        url = "{url}/invoice/{uuid}/files".format(
            url=company_id.afe_api_url,
            uuid=env_in_uuid
        )
        token = company_id.afe_token
        headers = {
            'Authorization': "Token {t}".format(t=token),
            }
        response = requests.get(url, headers=headers)
        response_data = json.loads(response.text)
        # ----- If response doesn't contain status_code 200,
        # ----- there is some error
        if response.status_code != 200:
            text_error = response_data['error']
            raise Warning(_(u'Remote File:\n'
                            '{c}.\n{t}'.format(
                                c=response.status_code, t=text_error)))
        return response_data
    
    def send_notify_mail_incoming_invoice(self, einv_in):
        company = einv_in.company_id
        odoobot = self.env.user.browse(1)
        partner_ids = [u.partner_id.id for u in company.notify_users]
        body = _('''
        You have a new invoice incoming number {n}!
        The new invoice it was stored in your system with file name {f}
        '''.format(n=einv_in.supp_number,
                   f=einv_in.name))
        if partner_ids:
            einv_in.message_post(
                body=body, 
                partner_ids=partner_ids,
                author_id=odoobot.partner_id.id,
                subtype_id=self.env.ref('mail.mt_note').id,
                subject=_("New Incoming Invoice"),
                record_name=einv_in.supp_number
                )

    def _get_incoming_invoice(self, filters=[], company_id=False):
        company_model = self.env['res.company']
        if not company_id:
            company_ids = company_model.search([('afe_active', '=', True)])
        else:
            company_ids = [company_id, ]
        for company in company_ids:
            get_alive(self, company)
            _logger.info("check incoming invoices for {c}".format(
                c=company.name))
            url = "{url}/invoices/in".format(
                url=company.afe_api_url
            )
            token = company.afe_token
            headers = {
                'Authorization': "Token {t}".format(t=token)
                }
            response = requests.get(url, headers=headers)
            response_data = json.loads(response.text)
            # ----- If response doesn't contain status_code 200,
            # ----- there is some error
            if response.status_code != 200:
                text_error = response_data['error']
                raise Warning(_(u'Invoice In:\n'
                                '{c}.\n{t}'.format(
                    c=response.status_code, t=text_error)
                ))
            for einv_in in response_data['invoices']:
                if self.search([('uuid_afe', '=', einv_in['uuid'])]):
                    continue
                for file in self.check_einvoice_remote_file(
                        einv_in['uuid'], company)['files']:
                    file_content = self.download_remote_invoice_file(
                        file['uuid'], company)
                    p7m_file = base64.b64encode(file_content)
                    p7m_file_name = file['name']
                    try:
                        einvoice_in = self.create({
                            'datas': p7m_file,
                            'att_name': p7m_file_name,
                            'name': p7m_file_name,
                            'supp_number': einv_in['number'],
                            'date_in_invoice': einv_in['date'],
                            'uuid_afe': einv_in['uuid'],
                            'company_id': company.id,
                            'e_invoice_received_date': einv_in.get(
                                'receiving_date', False) or False,
                        })
                        _logger.info("AFE Import Supplier Invoice - INVOICE {c} - {f}".format(
                            c=einv_in['number'], f=einv_in['partner_vat']))
                        self.send_notify_mail_incoming_invoice(einvoice_in)
                    except UserError as error:
                        _logger.info("AFE Import Supplier Invoice - NO imported INVOICE {c} - {f} - {err}".format(
                            c=einv_in['number'], f=einv_in['partner_vat'], err=error))
                        pass
                    except Exception as error:
                        _logger.info("AFE Import Supplier Invoice - NO imported INVOICE {c} - {f}".format(
                            c=einv_in['number'], f=einv_in['partner_vat']))
                        continue
                    einvoice_in._inverse_get_date()

    def get_incoming_invoice(self, filters=[], company_id=False):
        self._get_incoming_invoice(filters=filters, company_id=company_id)

    def cron_get_incoming_invoice(self):
        self._get_incoming_invoice()
