"""Install-time and migrate-time setup.

Everything here is written to survive a site that does not have the doctype in
question. These sites run different app sets - one has no Buying module at all
- so a missing Purchase Order must be a quiet no-op, never an install failure.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from upande_whatsapp.whatsapp_fields import WHATSAPP_NUMBER_FIELDS

DEFAULTS = {"fieldtype": "Data", "read_only": 1, "no_copy": 1, "translatable": 0}


def after_install():
	sync_whatsapp_number_fields()
	allow_recipient_list_import()


def after_migrate():
	sync_whatsapp_number_fields()
	allow_recipient_list_import()


def allow_recipient_list_import():
	"""Let recipient lists be built with the Data Import tool.

	frappe_whatsapp ships `WhatsApp Recipient List` with Allow Import off, so
	the tool refuses it. A Property Setter turns it on without editing their
	app, and survives an update of it.
	"""
	doctype = "WhatsApp Recipient List"
	if not frappe.db.exists("DocType", doctype):
		return

	make_property_setter(
		doctype,
		None,
		"allow_import",
		1,
		"Check",
		for_doctype=True,
		validate_fields_for_doctype=False,
	)


def sync_whatsapp_number_fields():
	"""Create the number fields, skipping anything this site cannot support."""
	wanted = {}
	skipped = []

	for spec in WHATSAPP_NUMBER_FIELDS:
		doctype = spec["doctype"]

		if not frappe.db.exists("DocType", doctype):
			skipped.append("{0} (doctype not installed)".format(doctype))
			continue

		field = {k: v for k, v in spec.items() if k != "doctype"}
		for key, value in DEFAULTS.items():
			field.setdefault(key, value)

		problem = _unusable_reason(doctype, field)
		if problem:
			skipped.append("{0}.{1} ({2})".format(doctype, field["fieldname"], problem))
			continue

		wanted.setdefault(doctype, []).append(field)

	if wanted:
		create_custom_fields(wanted, ignore_validate=True)

	if skipped:
		# visible in the migrate log without stopping it
		print("upande_whatsapp: skipped " + ", ".join(skipped))

	return {"created": wanted, "skipped": skipped}


def _unusable_reason(doctype, field):
	"""Why this field cannot be added here, or None if it can.

	A `fetch_from` pointing at a field that does not exist makes every save of
	the host document throw, which is a far worse failure than not having the
	field at all.
	"""
	fetch_from = field.get("fetch_from")
	if not fetch_from:
		return None

	if "." not in fetch_from:
		return "malformed fetch_from"

	link_fieldname, source_fieldname = fetch_from.split(".", 1)

	meta = frappe.get_meta(doctype)
	link_field = meta.get_field(link_fieldname)
	if not link_field:
		return "no field " + link_fieldname
	if link_field.fieldtype != "Link" or not link_field.options:
		return link_fieldname + " is not a Link"

	target = link_field.options
	if not frappe.db.exists("DocType", target):
		return target + " not installed"
	if not frappe.get_meta(target).get_field(source_fieldname):
		return "{0} has no {1}".format(target, source_fieldname)

	if meta.get_field(field["fieldname"]):
		return None

	insert_after = field.get("insert_after")
	if insert_after and not meta.get_field(insert_after):
		# harmless on its own - the field just lands at the end
		field.pop("insert_after", None)

	return None
