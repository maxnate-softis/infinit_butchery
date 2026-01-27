"""
Feature flags utilities for Infinit Butchery v3.0
Simplified to 5 core feature flags per the v3.0 architecture
"""

import frappe
from frappe import _
import functools
from .tenant import get_current_tenant


# ===========================================
# V3.0 SIMPLIFIED FEATURE FLAGS
# Only 5 core flags - everything else uses ERPNext standard config
# ===========================================

# Company-level feature flags (tenant-scoped)
COMPANY_FEATURES = {
    "enable_butchery_module": {
        "field": "custom_enable_butchery_module",
        "default": True,
        "description": "Master switch for butchery module"
    },
    "weight_pricing": {
        "field": "custom_enable_weight_pricing",
        "default": True,
        "description": "Sell by weight with scale integration"
    },
    "batch_tracing": {
        "field": "custom_enable_batch_tracing",
        "default": True,
        "description": "Full carcass-to-sale traceability"
    },
    "online_store": {
        "field": "custom_enable_online_store",
        "default": False,
        "description": "Website + e-commerce functionality"
    },
}

# Business type affects which features are available
BUSINESS_TYPES = {
    "Retail": {
        "description": "Single retail shop",
        "default_features": ["weight_pricing"]
    },
    "Wholesale": {
        "description": "B2B distribution",
        "default_features": ["weight_pricing", "batch_tracing"]
    },
    "Processing": {
        "description": "Meat processing facility",
        "default_features": ["weight_pricing", "batch_tracing"]
    },
    "Online": {
        "description": "E-commerce focused",
        "default_features": ["weight_pricing", "online_store"]
    },
    "Multi-Outlet": {
        "description": "Multiple branches",
        "default_features": ["weight_pricing", "batch_tracing"]
    }
}


def get_company_feature(feature_code: str, company: str = None) -> bool:
    """Check if a feature is enabled for a company (v3.0 simplified)"""
    if feature_code not in COMPANY_FEATURES:
        return False
    
    company = company or frappe.defaults.get_user_default("Company")
    if not company:
        return COMPANY_FEATURES[feature_code]["default"]
    
    field = COMPANY_FEATURES[feature_code]["field"]
    value = frappe.db.get_value("Company", company, field)
    
    if value is None:
        return COMPANY_FEATURES[feature_code]["default"]
    
    return bool(value)


def is_feature_enabled(feature_code: str, tenant: str = None) -> bool:
    """Check if a feature is enabled (v3.0 - uses Company custom fields)"""
    # Master switch must be on
    if feature_code != "enable_butchery_module":
        if not get_company_feature("enable_butchery_module", tenant):
            return False
    
    return get_company_feature(feature_code, tenant)


def require_feature(feature_code: str):
    """Decorator to require a feature for an API endpoint (v3.0)"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not is_feature_enabled(feature_code):
                feature_name = COMPANY_FEATURES.get(feature_code, {}).get(
                    "description", feature_code
                )
                frappe.throw(
                    _("Feature is not enabled for your business"),
                    frappe.PermissionError
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_business_type(company: str = None) -> str:
    """Get the business type for a company"""
    company = company or frappe.defaults.get_user_default("Company")
    if not company:
        return "Retail"
    
    return frappe.db.get_value("Company", company, "custom_butchery_business_type") or "Retail"


@frappe.whitelist()
def get_tenant_features(tenant: str = None):
    """Get all features and their status for a tenant (v3.0 simplified)"""
    company = tenant or frappe.defaults.get_user_default("Company")
    business_type = get_business_type(company)
    
    features = {}
    
    for code, config in COMPANY_FEATURES.items():
        features[code] = {
            "enabled": is_feature_enabled(code, company),
            "description": config["description"],
            "field": config["field"],
            "default": config["default"]
        }
    
    return {
        "features": features,
        "business_type": business_type,
        "total_enabled": sum(1 for f in features.values() if f["enabled"])
    }


@frappe.whitelist()
def set_tenant_feature(tenant: str, feature_code: str, enabled: bool):
    """Super Admin: Enable/disable feature for a tenant (v3.0)"""
    from .tenant import is_super_admin
    
    if not is_super_admin():
        frappe.throw(_("Only Super Admins can manage tenant features"))
    
    if feature_code not in COMPANY_FEATURES:
        frappe.throw(_("Unknown feature"))
    
    field = COMPANY_FEATURES[feature_code]["field"]
    frappe.db.set_value("Company", tenant, field, 1 if enabled else 0)
    frappe.db.commit()
    
    return {"success": True, "feature": feature_code, "enabled": enabled}


# Legacy compatibility - map old feature codes to new v3.0 codes
LEGACY_FEATURE_MAP = {
    "batch_traceability": "batch_tracing",
    "weight_based_pricing": "weight_pricing",
    "online_ordering": "online_store",
    "carcass_tracking": "batch_tracing",
    "cutting_yield": "batch_tracing",
}


def configure_tenant_feature(feature_code: str, enabled: bool, config: dict = None):
    """Legacy compatibility wrapper"""
    new_code = LEGACY_FEATURE_MAP.get(feature_code, feature_code)
    return set_tenant_feature(
        frappe.defaults.get_user_default("Company"),
        new_code,
        enabled
    )
