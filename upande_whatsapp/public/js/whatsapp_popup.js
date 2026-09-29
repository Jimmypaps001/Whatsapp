// Desk-wide toast for inbound WhatsApp messages.
// Deliberately the same alert the chat list raises (same sound, same shape,
// same 24-character preview) so it reads as one feature rather than two.
frappe.provide("upande.whatsapp");

$(document).on("app_ready", function () {
	if (upande.whatsapp._bound) return;

	// frappe.realtime.on() is a silent no-op while frappe.realtime.socket is
	// undefined - socketio_client.js drops the listener instead of queueing it -
	// and app_ready can win the race against realtime init. So wait for the
	// socket rather than registering into the void.
	var tries = 0;
	var timer = setInterval(function () {
		tries += 1;
		if (!frappe.realtime || !frappe.realtime.socket) {
			// ~60s, then give up: realtime is switched off on this site
			if (tries > 120) clearInterval(timer);
			return;
		}
		clearInterval(timer);
		if (upande.whatsapp._bound) return;
		upande.whatsapp._bound = true;
		frappe.realtime.on("upande_whatsapp_incoming", upande.whatsapp.show);
	}, 500);
});

upande.whatsapp.show = function (res) {
	if (!res) return;

	try {
		frappe.utils.play_sound("chat-message-receive");
	} catch (e) {
		// a missing sound must never cost us the alert
	}

	var name = frappe.utils.escape_html(res.contact_name || "");
	var body = frappe.utils.escape_html(res.content || "");
	var url = "/whatsapp?chat=" + encodeURIComponent(res.number || "");

	frappe.show_alert(
		{
			message:
				'<a href="' + url + '" target="_blank" rel="noopener" ' +
				'style="text-decoration: none; color: inherit;">' +
				"<strong>" + name + "</strong><br>" +
				'<span style="opacity: 0.9;">' + body + "</span>" +
				"</a>",
			indicator: "green",
		},
		5
	);
};
