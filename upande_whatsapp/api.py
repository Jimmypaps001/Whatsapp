"""Endpoints the /whatsapp page calls.

Two things the Cloud API and the site know that the page cannot work out for
itself: what our own business profile looks like, and who a number belongs to
in this ERP.
"""

import frappe
from frappe.integrations.utils import make_get_request

PROFILE_CACHE_KEY = "upande_whatsapp:business_profile"
PROFILE_CACHE_TTL = 6 * 60 * 60  # Meta's picture URL is signed and short-lived


def _account(name=None):
	"""The account to speak for: the one asked for, else the default outgoing."""
	if name and frappe.db.exists("WhatsApp Account", name):
		return frappe.get_doc("WhatsApp Account", name)
	for filters in ({"is_default_outgoing": 1}, {"status": "Active"}, {}):
		found = frappe.get_all("WhatsApp Account", filters=filters, limit=1, pluck="name")
		if found:
			return frappe.get_doc("WhatsApp Account", found[0])
	return None


@frappe.whitelist()
def business_profile(account=None):
	"""Our own WhatsApp profile - the only picture Meta will hand over.

	A contact's own profile photo is never exposed by the Cloud API, so this is
	strictly about how *we* appear.
	"""
	cached = frappe.cache.get_value(PROFILE_CACHE_KEY)
	if cached:
		return cached

	acc = _account(account)
	if not acc or not acc.phone_id:
		return {}

	try:
		token = acc.get_password("token")
	except Exception:
		# an undecryptable token is a site problem, not something to crash the page over
		return {}

	url = "{0}/{1}/{2}/whatsapp_business_profile".format(
		(acc.url or "https://graph.facebook.com").rstrip("/"), acc.version or "v25.0", acc.phone_id
	)
	try:
		res = make_get_request(
			url,
			headers={"Authorization": "Bearer {0}".format(token)},
			params={"fields": "profile_picture_url,about,description,vertical,websites"},
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "upande_whatsapp: business profile")
		return {}

	data = (res or {}).get("data") or []
	profile = data[0] if data else {}
	out = {
		"picture": profile.get("profile_picture_url"),
		"about": profile.get("about"),
		"description": profile.get("description"),
		"account": acc.name,
	}
	frappe.cache.set_value(PROFILE_CACHE_KEY, out, expires_in_sec=PROFILE_CACHE_TTL)
	return out


def _tail(number, n=9):
	"""The last n digits - the part that survives 0712…/254712…/+254 712…."""
	digits = "".join(c for c in str(number or "") if c.isdigit())
	return digits[-n:] if len(digits) >= n else ""


def _contact_index():
	"""{last 9 digits: [contact name, ...]} across every number a Contact holds."""
	index = {}

	def add(number, contact):
		key = _tail(number)
		if key:
			index.setdefault(key, set()).add(contact)

	for row in frappe.get_all("Contact", fields=["name", "mobile_no", "phone"]):
		add(row.get("mobile_no"), row["name"])
		add(row.get("phone"), row["name"])

	for row in frappe.db.sql(
		"""select parent, phone from `tabContact Phone` where parenttype='Contact'""", as_dict=True
	):
		add(row.get("phone"), row.get("parent"))

	return index


@frappe.whitelist()
def link_profiles_to_contacts(relink=False):
	"""Point each WhatsApp Profile at the Contact holding that number.

	Only an unambiguous match is written: if two Contacts share a number there
	is no way to tell which one wrote in, and a wrong name on a customer's
	messages is worse than no name.
	"""
	index = _contact_index()
	filters = {} if frappe.utils.cint(relink) else {"contact": ["in", ["", None]]}
	profiles = frappe.get_all("WhatsApp Profiles", filters=filters, fields=["name", "number", "contact"])

	linked, ambiguous, unmatched = 0, [], 0
	for p in profiles:
		matches = index.get(_tail(p.get("number")), set())
		if len(matches) == 1:
			contact = list(matches)[0]
			if p.get("contact") != contact:
				frappe.db.set_value("WhatsApp Profiles", p["name"], "contact", contact,
				                    update_modified=False)
			linked += 1
		elif len(matches) > 1:
			ambiguous.append({"number": p.get("number"), "contacts": sorted(matches)})
		else:
			unmatched += 1

	frappe.db.commit()
	return {"checked": len(profiles), "linked": linked,
	        "ambiguous": ambiguous[:20], "ambiguous_total": len(ambiguous), "unmatched": unmatched}


def link_one_profile(doc, method=None):
	"""Link a profile the moment it is created, so names appear on their own."""
	if doc.get("contact") or not doc.get("number"):
		return
	matches = _contact_index().get(_tail(doc.get("number")), set())
	if len(matches) == 1:
		doc.contact = list(matches)[0]


@frappe.whitelist()
def contact_directory():
	"""{number: name} for every profile that resolves to someone we know.

	The page falls back to the name the customer set on WhatsApp, which is
	whatever they chose; this prefers the name on our own Contact record.
	"""
	out = {}
	rows = frappe.get_all("WhatsApp Profiles", fields=["number", "profile_name", "contact"])
	contact_names = {}
	wanted = [r["contact"] for r in rows if r.get("contact")]
	if wanted:
		for c in frappe.get_all("Contact", filters={"name": ["in", wanted]},
		                        fields=["name", "first_name", "last_name", "company_name"]):
			label = " ".join(x for x in [c.get("first_name"), c.get("last_name")] if x).strip()
			contact_names[c["name"]] = label or c.get("company_name") or c["name"]

	for r in rows:
		digits = "".join(ch for ch in str(r.get("number") or "") if ch.isdigit())
		if not digits:
			continue
		name = contact_names.get(r.get("contact"))
		if not name:
			continue
		entry = {"name": name, "contact": r.get("contact")}
		out[digits] = entry
		# a profile may hold 0712… while the message carries 254712…, so the
		# page can also look this up by the part that survives either form
		tail = _tail(digits)
		if tail and tail not in out:
			out[tail] = entry
	return out
