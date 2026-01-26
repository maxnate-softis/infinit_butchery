"""
Feature flags utilities for Infinit Butchery
"""

import frappe
from frappe import _
import functools
from .tenant import get_current_tenant


# Default feature configurations
CORE_FEATURES = {
    "product_management": {"default": True, "description": "Basic product catalog management"},
    "pos_sales": {"default": True, "description": "Point of sale functionality"},
    "basic_inventory": {"default": True, "description": "Stock tracking and management"},
    "customer_management": {"default": True, "description": "Customer database and history"},
    "basic_reporting": {"default": True, "description": "Sales and inventory reports"},
}

STANDARD_FEATURES = {
    "carcass_tracking": {"default": False, "description": "Track whole carcass receipts"},
    "cutting_yield": {"default": False, "description": "Track yield percentages"},
    "batch_traceability": {"default": True, "description": "Full batch-to-sale traceability"},
    "cold_chain_monitoring": {"default": False, "description": "Temperature logging"},
    "weight_based_pricing": {"default": True, "description": "Sell by weight with scale"},
    "online_ordering": {"default": False, "description": "E-commerce website"},
    "delivery_management": {"default": False, "description": "Delivery zones and tracking"},
    "wholesale_pricing": {"default": False, "description": "B2B customer tiers"},
    "processing_orders": {"default": False, "description": "Value-add processing"},
    "multi_outlet": {"default": False, "description": "Multiple branches"},
    "loyalty_program": {"default": False, "description": "Customer points"},
    "halal_tracking": {"default": False, "description": "Halal certification"},
    "scale_integration": {"default": False, "description": "Hardware scale"},
}

ADVANCED_FEATURES = {
    "advanced_analytics": {"tier": "Premium", "description": "AI-powered insights"},
    "api_access": {"tier": "Business", "description": "External API"},
    "white_label": {"tier": "Enterprise", "description": "Remove branding"},
    "custom_workflows": {"tier": "Enterprise", "description": "Custom approvals"},
    "multi_currency": {"tier": "Business", "description": "Multiple currencies"},
    "franchise_management": {"tier": "Enterprise", "description": "Franchise features"},
}


def is_feature_enabled(feature_code: str, tenant: str = None) -> bool:
    """Check if a feature is enabled for the current/specified tenant"""
    tenant = tenant or get_current_tenant()
    
    # Core features are always enabled
    if feature_code in CORE_FEATURES:
        return True
    
    if not tenant:
        # Return default for standard features
        if feature_code in STANDARD_FEATURES:
            return STANDARD_FEATURES[feature_code]["default"]
        return False
    
    # Check tenant feature flag
    flag = frappe.db.get_value(
        "Tenant Feature Flag",
        {"tenant": tenant, "feature_code": feature_code},
        ["enabled_by_platform", "enabled_by_tenant"],
        as_dict=True
    )
    
    if not flag:
        # Return default if no flag exists
        if feature_code in STANDARD_FEATURES:
            return STANDARD_FEATURES[feature_code]["default"]
        return False
    
    # Feature must be enabled by BOTH platform AND tenant
    return flag.enabled_by_platform and flag.enabled_by_tenant


def require_feature(feature_code: str):
    """Decorator to require a feature for an API endpoint"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not is_feature_enabled(feature_code):
                frappe.throw(
                    _("Feature '{0}' is not enabled for your subscription").format(feature_code),
                    frappe.PermissionError
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


@frappe.whitelist()
def get_tenant_features(tenant: str = None):
    """Get all features and their status for a tenant"""
    tenant = tenant or get_current_tenant()
    
    features = {}
    
    # Add core features (always enabled)
    for code, config in CORE_FEATURES.items():
        features[code] = {
            "enabled": True,
            "category": "core",
            "description": config["description"],
            "configurable": False
        }
    
    # Add standard features
    for code, config in STANDARD_FEATURES.items():
        features[code] = {
            "enabled": is_feature_enabled(code, tenant),
            "category": "standard",
            "description": config["description"],
            "configurable": True,
            "default": config["default"]
        }
    
    # Add advanced features
    for code, config in ADVANCED_FEATURES.items():
        features[code] = {
            "enabled": is_feature_enabled(code, tenant),
            "category": "advanced",
            "description": config["description"],
            "tier": config["tier"],
            "configurable": False
        }
    
    return features


@frappe.whitelist()
def set_tenant_feature(tenant: str, feature_code: str, enabled: bool):
    """Super Admin: Enable/disable feature for a tenant"""
    from .tenant import is_super_admin
    
    if not is_super_admin():
        frappe.throw(_("Only Super Admins can manage tenant features"))
    
    # Check if flag exists
    existing = frappe.db.exists(
        "Tenant Feature Flag",
        {"tenant": tenant, "feature_code": feature_code}
    )
    
    if existing:
        frappe.db.set_value(
            "Tenant Feature Flag",
            existing,
            {
                "enabled_by_platform": enabled,
                "enabled_date": frappe.utils.now() if enabled else None,
                "disabled_date": None if enabled else frappe.utils.now()
            }
        )
    else:
        flag = frappe.get_doc({
            "doctype": "Tenant Feature Flag",
            "tenant": tenant,
            "feature_code": feature_code,
            "enabled_by_platform": enabled,
            "enabled_by_tenant": enabled,  # Auto-enable for tenant too
            "enabled_date": frappe.utils.now() if enabled else None
        })
        flag.insert(ignore_permissions=True)
    
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def configure_tenant_feature(feature_code: str, enabled: bool, config: dict = None):
    """Tenant Admin: Configure an enabled feature"""
    tenant = get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Tenant context required"))
    
    # Check if platform has enabled this feature
    platform_enabled = frappe.db.get_value(
        "Tenant Feature Flag",
        {"tenant": tenant, "feature_code": feature_code},
        "enabled_by_platform"
    )
    
    if not platform_enabled:
        frappe.throw(_("Feature '{0}' is not available for your subscription").format(feature_code))
    
    # Update tenant configuration
    frappe.db.set_value(
        "Tenant Feature Flag",
        {"tenant": tenant, "feature_code": feature_code},
        {
            "enabled_by_tenant": enabled,
            "configuration": frappe.as_json(config) if config else None
        }
    )
    
    frappe.db.commit()
    return {"success": True}
