"""
Infinit Butchery v3.0 Hooks
Simplified architecture: 8 doctypes, 5 feature flags
"""

app_name = "infinit_butchery"
app_title = "Infinit Butchery"
app_publisher = "Maxnate Africa"
app_description = "Butchery Industry Module for Maxnate Infinit Engine v3.0"
app_email = "dev@maxnate.com"
app_license = "MIT"
app_version = "3.0.0"

# Required Apps
required_apps = ["frappe", "erpnext"]

# V3.0 Doctypes (8 total)
# =======================
# Core: butchery_order, butchery_order_item, meat_category
# Payments: payment_gateway, payment_transaction, tenant_payment_method
# Config: delivery_zone, tenant_feature_flag

# V3.0 Feature Flags (5 total)
# ============================
# enable_butchery_module, weight_pricing, batch_tracing, online_store, business_type

# Includes in <head>
# ------------------
app_include_css = "/assets/infinit_butchery/css/butchery.css"
app_include_js = "/assets/infinit_butchery/js/butchery.js"

# Home Pages
# ----------
# home_page = "login"

# Website (only if online_store feature enabled)
# website_generators = ["Meat Category"]

# Desk Notifications
notification_config = "infinit_butchery.notifications.get_notification_config"

# Permissions - Tenant Isolation (READ protection)
# ------------------------------------------------
# These conditions filter all list/report queries by tenant,
# preventing users from READING other tenants' data.
# ALL 8 DocTypes must be covered for complete isolation.
permission_query_conditions = {
    # Core Order DocTypes
    "Butchery Order": "infinit_butchery.utils.permissions.order_query",
    "Butchery Order Item": "infinit_butchery.utils.permissions.order_item_query",
    # Inventory DocTypes
    "Meat Category": "infinit_butchery.utils.permissions.meat_category_query",
    # Delivery DocTypes
    "Delivery Zone": "infinit_butchery.utils.permissions.delivery_zone_query",
    # Payment DocTypes
    "Payment Gateway": "infinit_butchery.utils.permissions.payment_gateway_query",
    "Payment Transaction": "infinit_butchery.utils.permissions.payment_query",
    "Tenant Payment Method": "infinit_butchery.utils.permissions.tenant_payment_method_query",
    # Feature Flag DocTypes
    "Tenant Feature Flag": "infinit_butchery.utils.permissions.tenant_feature_flag_query",
}

has_permission = {
    "Butchery Order": "infinit_butchery.utils.permissions.has_order_permission",
    "Meat Category": "infinit_butchery.utils.permissions.has_meat_category_permission",
    "Delivery Zone": "infinit_butchery.utils.permissions.has_delivery_zone_permission",
    "Payment Gateway": "infinit_butchery.utils.permissions.has_payment_gateway_permission",
    "Payment Transaction": "infinit_butchery.utils.permissions.has_payment_permission",
    "Tenant Payment Method": "infinit_butchery.utils.permissions.has_tenant_payment_method_permission",
    "Tenant Feature Flag": "infinit_butchery.utils.permissions.has_tenant_feature_flag_permission",
}

# Document Events (v3.0 simplified)
doc_events = {
    "*": {
        "before_insert": "infinit_butchery.utils.tenant.validate_tenant_access",
        "validate": "infinit_butchery.utils.tenant.validate_tenant_access",
    },
    "Butchery Order": {
        "on_update": "infinit_butchery.doctype.butchery_order.butchery_order.on_update",
        "on_submit": "infinit_butchery.doctype.butchery_order.butchery_order.on_submit",
    },
    "Payment Transaction": {
        "on_submit": "infinit_butchery.doctype.payment_transaction.payment_transaction.on_submit",
    },
}

# Scheduled Tasks (v3.0 simplified)
scheduler_events = {
    "daily": [
        "infinit_butchery.tasks.daily_cleanup",
    ],
    "weekly": [
        "infinit_butchery.tasks.weekly_reports",
    ],
}

# Fixtures
fixtures = [
    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Butchery Super Admin",
            "Butchery Tenant Admin",
            "Butchery Manager",
            "Butchery Staff",
            "Butchery Customer"
        ]]]
    },
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Infinit Butchery"]]
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "=", "Infinit Butchery"]]
    },
]

# Installation
after_install = "infinit_butchery.install.after_install"
after_sync = "infinit_butchery.install.after_sync"

# Uninstallation
before_uninstall = "infinit_butchery.uninstall.before_uninstall"

# Payment Gateway Handlers
payment_gateway_handlers = {
    "mpesa": "infinit_butchery.gateways.mpesa.MpesaGateway",
    "stripe": "infinit_butchery.gateways.stripe.StripeGateway",
    "manual": "infinit_butchery.gateways.manual.ManualGateway",
}

# Jinja Methods (for website if online_store enabled)
jinja = {
    "methods": [
        "infinit_butchery.utils.jinja_helpers.get_meat_categories",
        "infinit_butchery.utils.jinja_helpers.format_weight",
    ],
}

# Override ERPNext methods for butchery integration
override_whitelisted_methods = {
    "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note": 
        "infinit_butchery.overrides.make_butchery_delivery_note"
}

# Custom fields added to Company doctype for feature flags
# custom_enable_butchery_module, custom_enable_weight_pricing,
# custom_enable_batch_tracing, custom_enable_online_store,
# custom_butchery_business_type
