# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api, _


class ResCompany(models.Model):

    _inherit = "res.company"

    afe_exported_zip_mail = fields.Char()
