# -*- coding: utf-8 -*-
# Copyright 2015 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, _, api


class FatturaPAAttachment(models.Model):

    _inherit = 'fatturapa.attachment.out'

    fatturapa_notes = fields.Text('Notes')
