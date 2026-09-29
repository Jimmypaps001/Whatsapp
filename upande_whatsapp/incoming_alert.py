import frappe

ROLE = "WhatsApp Manager"
EVENT = "upande_whatsapp_incoming"
PREVIEW_LIMIT = 24


def notify_incoming(doc, method=None):
	"""Toast the WhatsApp managers whenever a customer writes in.

	The chat list already raises this alert, but only for whoever happens to
	have the chat page open. The inbox is watched from all over the desk, so
	the alert is pushed to each user holding the role instead of being
	broadcast site-wide - a customer's message is not for everyone to read.
	"""
	if (doc.get("type") or "").lower() != "incoming":
		return

	users = get_whatsapp_managers()
	if not users:
		return

	payload = {
		"name": doc.name,
		"contact_name": doc.get("profile_name") or doc.get("from") or "Unknown",
		"number": doc.get("from") or "",
		"content": get_preview(doc),
	}

	for user in users:
		# after_commit so nothing is announced that a failed insert rolls back
		frappe.publish_realtime(EVENT, payload, user=user, after_commit=True)


def get_preview(doc):
	"""A short plain-text line for the toast, whatever the message carries."""
	content_type = (doc.get("content_type") or "text").lower()
	if content_type and content_type != "text":
		return "[{0}]".format(content_type)

	text = frappe.utils.strip_html(doc.get("message") or "").strip()
	if not text:
		return "[{0}]".format(content_type or "message")

	text = " ".join(text.split())
	if len(text) > PREVIEW_LIMIT:
		text = text[:PREVIEW_LIMIT] + "..."
	return text


def get_whatsapp_managers():
	"""Enabled desk users holding the role, however the role reached them.

	Roles on these sites are granted through Role Profiles rather than edited
	on the user, but either route writes the same `Has Role` rows, so reading
	those covers both.
	"""
	holders = frappe.get_all(
		"Has Role",
		filters={"role": ROLE, "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	if not holders:
		return []

	return frappe.get_all(
		"User",
		filters={"name": ["in", holders], "enabled": 1, "user_type": "System User"},
		pluck="name",
	)
