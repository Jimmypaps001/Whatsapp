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


WORKSPACE = "WhatsApp"
SIDEBAR_LINKS = [
	("WhatsApp Chat", "URL", "/whatsapp", "message"),
	("Messages", "DocType", "WhatsApp Message", "list"),
	("Recipient Lists", "DocType", "WhatsApp Recipient List", "users"),
	("Bulk Messages", "DocType", "Bulk WhatsApp Message", "send"),
	("Templates", "DocType", "WhatsApp Templates", "file"),
	("Notifications", "DocType", "WhatsApp Notification", "notification"),
	("Accounts", "DocType", "WhatsApp Account", "setting"),
]


def after_install():
	sync_whatsapp_number_fields()
	allow_recipient_list_import()
	put_workspace_on_the_desk()


def after_migrate():
	sync_whatsapp_number_fields()
	allow_recipient_list_import()
	put_workspace_on_the_desk()


def put_workspace_on_the_desk():
	"""Make the workspace reachable, not merely present.

	A Workspace record on its own shows up nowhere: v16 drives the sidebar from
	`Workspace Sidebar` and the app switcher from `Desktop Icon`. Frappe
	generates both after an install, but one badly-formed `add_to_apps_screen`
	in any installed app raises a KeyError that aborts the whole pass
	(desktop_icon.py reads `app_details[0]["logo"]` unguarded), so this app
	creates its own rather than depend on that succeeding.
	"""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	# it used to hang off another app's page, which hides it from the sidebar
	if frappe.db.get_value("Workspace", WORKSPACE, "parent_page"):
		frappe.db.set_value("Workspace", WORKSPACE, "parent_page", "", update_modified=False)

	_ensure_sidebar()
	_ensure_desktop_icon()

	# get_desktop_icons caches its result per user, so anyone with a session
	# from before the install keeps seeing an apps screen without this app on
	# it. Drop the cache so it appears without each person having to do
	# anything.
	for key in ("desktop_icons", "bootinfo"):
		try:
			frappe.cache.delete_key(key)
		except Exception:
			pass


def _ensure_sidebar():
	"""Create the sidebar, or take over the one Frappe generated for us.

	Frappe auto-generates a bare two-item sidebar for any public workspace, and
	on a site where the workspace already existed that sidebar predates this app
	and belongs to whichever module owned the workspace then. Skipping it leaves
	the app's own links permanently missing, so an existing sidebar is adopted
	and refilled rather than left alone.
	"""
	icon = frappe.db.get_value("Workspace", WORKSPACE, "icon") or "message"
	existing = frappe.db.exists("Workspace Sidebar", WORKSPACE)
	if existing:
		doc = frappe.get_doc("Workspace Sidebar", WORKSPACE)
		# a sidebar someone has deliberately built out is left alone
		if len(doc.items) > len(SIDEBAR_LINKS):
			return
		doc.items = []
	else:
		doc = frappe.new_doc("Workspace Sidebar")
	doc.title = WORKSPACE
	doc.header_icon = icon
	doc.module = "Upande WhatsApp"
	doc.app = "upande_whatsapp"
	doc.standard = 0          # a standard sidebar with no file is swept as an orphan
	doc.append("items", {"label": "Home", "link_type": "Workspace", "link_to": WORKSPACE,
	                     "type": "Link", "icon": icon})
	for label, link_type, link_to, item_icon in SIDEBAR_LINKS:
		if link_type == "DocType" and not frappe.db.exists("DocType", link_to):
			continue      # a site without that part of frappe_whatsapp just gets fewer links
		row = {"label": label, "link_type": link_type, "type": "Link", "icon": item_icon}
		if link_type == "URL":
			row["url"] = link_to
		else:
			row["link_to"] = link_to
		doc.append("items", row)
	try:
		doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "upande_whatsapp: could not create the sidebar")


def _ensure_desktop_icon():
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return
	if frappe.db.exists("Desktop Icon", {"icon_type": "App", "app": "upande_whatsapp"}):
		return

	# Desktop Icon is named after its label, and Frappe has usually already made
	# a *Link* icon called "WhatsApp" for the workspace itself. Two icons cannot
	# share a name, so the app tile takes the app's own title instead - which is
	# also what the apps screen would have labelled it.
	label = "WhatsApp"
	if frappe.db.exists("Desktop Icon", label):
		label = frappe.get_hooks("app_title", app_name="upande_whatsapp")[0]
		if frappe.db.exists("Desktop Icon", label):
			return

	try:
		icon = frappe.new_doc("Desktop Icon")
		icon.label = label
		icon.icon_type = "App"
		icon.link_type = "External"
		icon.app = "upande_whatsapp"
		icon.link = "/app/whatsapp"
		icon.logo_url = "/assets/upande_whatsapp/images/logo.svg"
		icon.standard = 0
		icon.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "upande_whatsapp: could not create the app icon")


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
