"""Keep WhatsApp number fields in the form Meta will accept.

frappe_whatsapp hands the stored value straight to the Graph API - its
`format_number` only strips a leading "+" - and Meta rejects anything without a
country code with a bare "400 Client Error" whose body is never logged. A
local-format number therefore fails silently and permanently, so the numbers
are corrected as they are written rather than left to fail at send time.
"""

import frappe

from upande_whatsapp.whatsapp_fields import fieldnames_by_doctype

DEFAULT_COUNTRY_CODE = "254"


def to_msisdn(value, country_code=None):
	"""Return `value` as digits with a country code, or "" if it isn't a number.

	Anything already carrying a country code is left alone, so a supplier
	abroad is never rewritten into a Kenyan number.
	"""
	digits = "".join(c for c in str(value or "") if c.isdigit())
	if not digits:
		return ""

	code = country_code or _country_code()

	if digits.startswith(code):
		return digits
	if digits.startswith("0"):
		return code + digits[1:]
	# a bare national number, e.g. 7xxxxxxxx
	if len(digits) == 9:
		return code + digits
	# already international for somewhere else - leave it be
	return digits


def normalise_number_fields(doc, method=None):
	for fieldname in fieldnames_by_doctype().get(doc.doctype, []):
		current = doc.get(fieldname)
		if not current:
			continue
		cleaned = to_msisdn(current)
		if cleaned and cleaned != current:
			doc.set(fieldname, cleaned)


def _country_code():
	code = frappe.db.get_single_value("Upande WhatsApp Settings", "default_country_code") \
		if frappe.db.exists("DocType", "Upande WhatsApp Settings") else None
	return (code or DEFAULT_COUNTRY_CODE).lstrip("+")


def normalise_recipient_list(doc, method=None):
	"""Correct the numbers in a recipient list as it is saved.

	frappe_whatsapp builds these rows straight from a source doctype and only
	strips non-digits, so a list imported from Employee inherits whatever
	format the HR data happens to be in. One bad row is one silent 400 per
	send, so they are fixed here rather than discovered a broadcast later.
	"""
	for row in doc.get("recipients") or []:
		current = row.get("mobile_number")
		if not current:
			continue
		cleaned = to_msisdn(current)
		if cleaned and cleaned != current:
			row.mobile_number = cleaned
