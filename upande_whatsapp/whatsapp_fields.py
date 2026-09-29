"""The WhatsApp number fields this app puts on other doctypes.

A WhatsApp Notification can only send to a field that exists on the document
it fires from, so every doctype we want to message about needs a field holding
the recipient's number. They are declared here rather than created by hand on
each site, and `install.sync_whatsapp_number_fields` skips any doctype the
site does not have.

`fetch_from` keeps the number in step with the party record. Note that Meta
rejects a local-format number outright, with a bare "400 Client Error" and no
explanation, so `normalise.py` rewrites these fields into international form
on save.
"""

# Fields are Data (not Phone) so the stored value is exactly what is sent.
WHATSAPP_NUMBER_FIELDS = [
	{
		"doctype": "Purchase Order",
		"fieldname": "custom_supplier_whatsapp_no",
		"label": "Supplier WhatsApp No.",
		"insert_after": "supplier_name",
		"fetch_from": "supplier.mobile_no",
	},
	{
		"doctype": "Purchase Invoice",
		"fieldname": "custom_supplier_whatsapp_no",
		"label": "Supplier WhatsApp No.",
		"insert_after": "supplier_name",
		"fetch_from": "supplier.mobile_no",
	},
	{
		"doctype": "Sales Order",
		"fieldname": "custom_customer_whatsapp_no",
		"label": "Customer WhatsApp No.",
		"insert_after": "customer_name",
		"fetch_from": "customer.mobile_no",
	},
	{
		"doctype": "Sales Invoice",
		"fieldname": "custom_customer_whatsapp_no",
		"label": "Customer WhatsApp No.",
		"insert_after": "customer_name",
		"fetch_from": "customer.mobile_no",
	},
	{
		"doctype": "Delivery Note",
		"fieldname": "custom_customer_whatsapp_no",
		"label": "Customer WhatsApp No.",
		"insert_after": "customer_name",
		"fetch_from": "customer.mobile_no",
	},
	{
		"doctype": "Material Request",
		"fieldname": "custom_requester_whatsapp_no",
		"label": "Requester WhatsApp No.",
		"insert_after": "material_request_type",
	},
]


def fieldnames_by_doctype():
	"""{doctype: [fieldname, ...]} - used by the save-time normaliser."""
	out = {}
	for spec in WHATSAPP_NUMBER_FIELDS:
		out.setdefault(spec["doctype"], []).append(spec["fieldname"])
	return out
