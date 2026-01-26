app_name = "infinit_butchery"
app_title = "Infinit Butchery"
app_publisher = "Maxnate Africa"
app_description = "Butcheries Industry Module for Maxnate Infinit Platform"
app_email = "dev@maxnate.com"
app_license = "MIT"
app_version = "2.0.0"

# Includes in <head>
# ------------------
# app_include_css = "/assets/infinit_butchery/css/infinit_butchery.css"
# app_include_js = "/assets/infinit_butchery/js/infinit_butchery.js"

# Home Pages
# ----------
# home_page = "login"

# Website pages
# -------------
# website_generators = ["Meat Category"]

# Desk Notifications
# ------------------
# notification_config = "infinit_butchery.notifications.get_notification_config"

# Permissions
# -----------
# permission_query_conditions = {
#     "Butchery Order": "infinit_butchery.permissions.order_query",
# }
#
# has_permission = {
#     "Butchery Order": "infinit_butchery.permissions.has_order_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes
# override_doctype_class = {
#     "Item": "infinit_butchery.overrides.CustomItem"
# }

# Document Events
# ---------------
doc_events = {
    "*": {
        "before_insert": "infinit_butchery.utils.tenant.validate_tenant_access",
        "validate": "infinit_butchery.utils.tenant.validate_tenant_access",
    },
    "Carcass Receipt": {
        "on_submit": "infinit_butchery.doctype.carcass_receipt.carcass_receipt.on_submit",
    },
    "Cutting Batch": {
        "on_submit": "infinit_butchery.doctype.cutting_batch.cutting_batch.on_submit",
    },
    "Butchery Order": {
        "on_update": "infinit_butchery.doctype.butchery_order.butchery_order.on_update",
    },
}

# Scheduled Tasks
# ---------------
scheduler_events = {
    "hourly": [
        "infinit_butchery.tasks.check_expiring_batches",
    ],
    "daily": [
        "infinit_butchery.tasks.generate_daily_reports",
        "infinit_butchery.tasks.check_low_stock",
        "infinit_butchery.tasks.expire_old_batches",
    ],
}

# Testing
# -------
# before_tests = "infinit_butchery.install.before_tests"

# Overriding Methods
# ------------------------------
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "infinit_butchery.event.get_events"
# }

# Exempt linked doctypes from being cancelled
# ---------
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Fixtures
# --------
fixtures = [
    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Butchery Super Admin",
            "Butchery Tenant Admin",
            "Butchery Branch Manager",
            "Butchery Staff",
            "Butchery Customer"
        ]]]
    },
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Infinit Butchery"]]
    },
]

# Jinja Environment
# ------------------
# jinja = {
#     "methods": "infinit_butchery.utils.jinja_methods",
# }

# Installation
# ------------
after_install = "infinit_butchery.install.after_install"
after_sync = "infinit_butchery.install.after_sync"

# Uninstallation
# ------------
# before_uninstall = "infinit_butchery.uninstall.before_uninstall"
# after_uninstall = "infinit_butchery.uninstall.after_uninstall"

# Integration Setup
# ------------------
# setup_wizard_complete = "infinit_butchery.install.setup_wizard_complete"

# Payment Gateway Handlers
# ------------------------
payment_gateway_handlers = {
    "mpesa": "infinit_butchery.gateways.mpesa.MpesaGateway",
    "manual": "infinit_butchery.gateways.manual.ManualPaymentGateway",
}

# API Authentication
# -----------------
# auth_hooks = ["infinit_butchery.auth.authenticate_request"]
