# -*- coding: utf-8 -*-
# Copyright 2018 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api, _


class ResCompany(models.Model):

    _inherit = "res.company"

    afe_api_url = fields.Char()
    afe_token = fields.Char()
    notify_users = fields.Many2many('res.users')
    afe_active = fields.Boolean(default=True)
    afe_last_status_check = fields.Date()

    def check_einvoice_status(self):
        einvoice_history_model = self.env['einvoice.history']
        for company in self:
            einvoice_history_model.with_context(
                afe_force_check_status_company_id=company.id,
            ).cron_check_new_status()
