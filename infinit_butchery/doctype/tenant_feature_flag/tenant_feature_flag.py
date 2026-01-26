"""
Tenant Feature Flag DocType
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class TenantFeatureFlag(Document):
    def before_save(self):
        # Track enable/disable changes
        if self.has_value_changed("is_enabled"):
            if self.is_enabled:
                self.enabled_date = now()
                self.enabled_by = frappe.session.user
                self.disabled_date = None
            else:
                self.disabled_date = now()
    
    def validate(self):
        # Validate feature code format
        if self.feature_code:
            self.feature_code = self.feature_code.lower().replace(" ", "_")
        
        # Validate JSON config
        if self.config_json:
            try:
                frappe.parse_json(self.config_json)
            except:
                frappe.throw(_("Invalid JSON in configuration"))


@frappe.whitelist()
def get_tenant_features(tenant: str) -> dict:
    """
    Get all feature flags for a tenant
    
    Args:
        tenant: Tenant (Company) name
    
    Returns:
        dict: Feature codes with their enabled status
    """
    features = frappe.get_all(
        "Tenant Feature Flag",
        filters={"tenant": tenant},
        fields=["feature_code", "is_enabled", "config_json"]
    )
    
    result = {}
    for f in features:
        result[f.feature_code] = {
            "enabled": bool(f.is_enabled),
            "config": frappe.parse_json(f.config_json) if f.config_json else {}
        }
    
    return result


@frappe.whitelist()
def set_feature_flag(tenant: str, feature_code: str, enabled: bool, config: dict = None):
    """
    Set feature flag for a tenant
    
    Args:
        tenant: Tenant (Company) name
        feature_code: Feature code
        enabled: Whether to enable
        config: Optional configuration
    """
    existing = frappe.db.exists("Tenant Feature Flag", {
        "tenant": tenant,
        "feature_code": feature_code
    })
    
    if existing:
        doc = frappe.get_doc("Tenant Feature Flag", existing)
        doc.is_enabled = enabled
        if config:
            doc.config_json = frappe.as_json(config)
        doc.save()
    else:
        doc = frappe.new_doc("Tenant Feature Flag")
        doc.tenant = tenant
        doc.feature_code = feature_code
        doc.feature_name = feature_code.replace("_", " ").title()
        doc.is_enabled = enabled
        if config:
            doc.config_json = frappe.as_json(config)
        doc.insert()
    
    return doc.name


@frappe.whitelist()
def initialize_tenant_features(tenant: str, tier: str = "Standard"):
    """
    Initialize default features for a new tenant based on subscription tier
    
    Args:
        tenant: Tenant (Company) name
        tier: Subscription tier (Basic, Standard, Premium, Enterprise)
    """
    from infinit_butchery.utils.features import CORE_FEATURES, STANDARD_FEATURES, ADVANCED_FEATURES
    
    # Core features are always enabled
    for code, name in CORE_FEATURES.items():
        if not frappe.db.exists("Tenant Feature Flag", {"tenant": tenant, "feature_code": code}):
            doc = frappe.new_doc("Tenant Feature Flag")
            doc.tenant = tenant
            doc.feature_code = code
            doc.feature_name = name
            doc.feature_category = "Core"
            doc.subscription_tier = "Basic"
            doc.is_enabled = 1
            doc.insert(ignore_permissions=True)
    
    # Standard features for Standard+ tiers
    if tier in ["Standard", "Premium", "Enterprise"]:
        for code, name in STANDARD_FEATURES.items():
            if not frappe.db.exists("Tenant Feature Flag", {"tenant": tenant, "feature_code": code}):
                doc = frappe.new_doc("Tenant Feature Flag")
                doc.tenant = tenant
                doc.feature_code = code
                doc.feature_name = name
                doc.feature_category = "Standard"
                doc.subscription_tier = "Standard"
                doc.is_enabled = 1
                doc.insert(ignore_permissions=True)
    
    # Advanced features for Premium+ tiers
    if tier in ["Premium", "Enterprise"]:
        for code, name in ADVANCED_FEATURES.items():
            if not frappe.db.exists("Tenant Feature Flag", {"tenant": tenant, "feature_code": code}):
                doc = frappe.new_doc("Tenant Feature Flag")
                doc.tenant = tenant
                doc.feature_code = code
                doc.feature_name = name
                doc.feature_category = "Advanced"
                doc.subscription_tier = "Premium"
                doc.is_enabled = 1
                doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
