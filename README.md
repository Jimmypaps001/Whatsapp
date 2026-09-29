## Upande WhatsApp

WhatsApp customisations for Upande sites, on top of
[frappe_whatsapp](https://github.com/shridarpatil/frappe_whatsapp), which is a
hard dependency (`required_apps`).

### What it carries

**The WhatsApp dashboard**, as code rather than as rows in a site database:
the `WhatsApp` Workspace (now owned by the `Upande WhatsApp` module), the
`WhatsApp` Custom HTML Block it renders, and the `/whatsapp` Web Page. They
ship as fixtures, so a migrate restores them and a site edit is overwritten -
export the record back into `upande_whatsapp/fixtures/` to keep a desk change.

**WhatsApp number fields** on the documents we send about - Purchase Order,
Purchase Invoice, Sales Order, Sales Invoice, Delivery Note and Material
Request - declared in `whatsapp_fields.py`. A WhatsApp Notification can only
send to a field that exists on its own doctype, which is why each one needs its
own.

### Sites that do not have a doctype

The field list is advisory. `install.sync_whatsapp_number_fields` skips, with a
line in the migrate log and no error, any entry whose doctype is not installed,
whose `fetch_from` link field is missing, or whose `fetch_from` target field
does not exist on the linked doctype - that last one matters because a dangling
`fetch_from` makes every save of the host document throw.

### Number format

Meta rejects a local-format number with a bare `400 Client Error` whose body is
never logged, and frappe_whatsapp's `format_number` only strips a leading `+` -
it never adds a country code. So these fields are rewritten into international
form on save (`normalise.py`). Numbers that already carry another country's
code are left alone.
