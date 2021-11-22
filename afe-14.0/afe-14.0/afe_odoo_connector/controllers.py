# -*- coding: utf-8 -*-
# Copyright 2019 Apulia Software srl

import os
import odoo.http as http
from odoo.http import request


class AfeInvoiceInController(http.Controller):

    @http.route('/web/export/afe_invoice_in', type='http', auth='user')
    def export_afe_invoice_in_as_pdf(self, debug=None, ir=None):
        #print '====================', ir
        # if '.b64.p7m' in ir:
        pdf_file = '/tmp/afe_invoice_in_pdf/%s.xml.pdf' % ir
        pf = open(pdf_file, "rb")
        result = request.make_response(
            pf.read(),
            headers=[
                ('Content-Disposition', 'attachment; filename="%s.pdf"'
                    % ir),
                ('Content-Type', 'application/pdf')
            ], )
        pf.close()
        os.remove(pdf_file)
        return result
