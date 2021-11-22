# -*- coding: utf-8 -*-
# Copyright 2018 Apulia Software s.r.l. (<info@apuliasoftware.it>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import os
import subprocess
import base64

import requests
from odoo import _
import pdfkit


def get_alive(odoo_class, company=False):
    if not company:
        company = odoo_class.env.user.company_id
    url = "{}/alive".format(company.afe_api_url)
    try:
        response = requests.get(url)
    except Exception as e:
        raise Warning(_('Server Error\nSorry! Operation error!\n'
                        'Please try later\n%s') % e)
    if response.status_code != 200:
        raise Warning(_('Server Unreachable\n''Please try later'))


def openssl_subprocess(filename):
    # ----- Use OpenSSL to extract XML from P7M
    if filename.lower().endswith('.p7m.b64.p7m'):
        extracted_filename = filename[:-12]
    elif filename.lower().endswith('.b64.p7m'):
        extracted_filename = filename[:-8]
    elif filename.lower().endswith('.p7m'):
        extracted_filename = filename[:-4]
    else:
        extracted_filename = filename[:-4]
    try:
        subprocess.check_output([
            'openssl', 'cms', '-decrypt', '-verify', '-inform', 'DER',
            '-in', filename, '-noverify', '-nosigs', '-out',
            extracted_filename])
    except:
        extracted_filename = False
    return extracted_filename

def extract_xml_from_p7m(filename):
    extracted_filename = openssl_subprocess(filename)
    # ----- Some files contain not the p7m but the base64 econding
    #       of the p7m content. So we need to try to extract xml
    #       and if this fails we need to convert content and then extract it
    if not extracted_filename:
        # ----- Convert base64 contento to file
        with open(filename, 'rb') as base64_encoded_file:
            # base64_decoded_content = base64_encoded_file.read().decode('base64')
            base64_decoded_content = base64.b64decode(
                base64_encoded_file.read())
            base64_decoded_file_p7m_filename = '%s.b64.p7m' % filename
            base64_decoded_file_p7m = open(base64_decoded_file_p7m_filename,
                                           'wb')
            base64_decoded_file_p7m.write(base64_decoded_content)
            base64_decoded_file_p7m.close()
            # ----- Extract XML from P7M
            extracted_filename = openssl_subprocess(
                base64_decoded_file_p7m_filename)
            # ----- Remove file used to read xml data
            os.remove(base64_decoded_file_p7m_filename)
    if not extracted_filename:
        raise Warning(_(
            'Error in extraction of XML from P7M file %s' % filename))
        return extracted_filename
    if not os.path.isfile(extracted_filename):
        raise Warning(_(
            'XML not extracted from P7M file %s' % filename))
        extracted_filename = False
    return extracted_filename


def apply_xsl_to_xml(file_xml, file_xls, file_output=None):
    output_filename = file_output if file_output else '%s.html' % file_xml
    try:
        # xsltproc file.xsl file.xml -o file.html
        subprocess.check_output([
            'xsltproc', file_xls, file_xml, '-o', output_filename])
    # ----- Manage bad application of XSL
    except Exception as error_text:
        if not os.path.isfile(output_filename):
            raise Warning(
                _('Error in application of XLS %s to XML file %s\n\n%s') % (
                    file_xls, file_xml, error_text))
    if not os.path.isfile(output_filename):
            raise Warning(
                _('Error in application of XLS %s to XML file %s\n\n%s') % (
                    file_xls, file_xml, error_text))
    return output_filename


def convert_html_to_pdf(file_html, file_pdf):
    pdfkit.from_file(file_html, file_pdf)
    return file_pdf
