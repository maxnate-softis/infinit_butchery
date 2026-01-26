"""
Tenant Payment Method DocType
"""

import frappe
from frappe import _
from frappe.model.document import Document


class TenantPaymentMethod(Document):
    def validate(self):
        # Validate limits
        if self.min_amount and self.max_amount:
            if self.min_amount > self.max_amount:
                frappe.throw(_("Minimum amount cannot be greater than maximum amount"))
    
    def before_save(self):
        # Fetch gateway type if not set
        if not self.gateway_type and self.payment_gateway:
            self.gateway_type = frappe.db.get_value(
                "Payment Gateway", self.payment_gateway, "gateway_type"
            )
    
    def get_credentials(self) -> dict:
        """
        Get credentials for this payment method.
        Returns tenant-specific overrides if set, otherwise falls back to gateway defaults.
        """
        gateway = frappe.get_doc("Payment Gateway", self.payment_gateway)
        creds = gateway.get_credentials()
        
        # Override with tenant-specific values if set
        if self.api_key_override:
            creds["api_key"] = self.get_password("api_key_override")
        if self.api_secret_override:
            creds["api_secret"] = self.get_password("api_secret_override")
        
        # Add merchant info
        creds["merchant_id"] = self.merchant_id
        creds["merchant_code"] = self.merchant_code
        
        return creds


@frappe.whitelist()
def get_tenant_payment_methods(tenant: str) -> list:
    """
    Get enabled payment methods for a tenant
    
    Args:
        tenant: Tenant (Company) name
    
    Returns:
        list: Enabled payment methods
    """
    methods = frappe.get_all(
        "Tenant Payment Method",
        filters={"tenant": tenant, "is_enabled": 1},
        fields=["payment_gateway", "display_name", "gateway_type",
                "supports_mobile", "min_amount", "max_amount"],
        order_by="display_order"
    )
    
    # Add gateway logo
    for method in methods:
        method["logo"] = frappe.db.get_value(
            "Payment Gateway", method["payment_gateway"], "logo"
        )
    
    return methods


@frappe.whitelist()
def setup_default_payment_methods(tenant: str):
    """
    Setup default payment methods for a new tenant
    
    Args:
        tenant: Tenant (Company) name
    """
    # Get all active gateways
    gateways = frappe.get_all(
        "Payment Gateway",
        filters={"is_active": 1},
        fields=["name", "gateway_name", "gateway_type"]
    )
    
    for gateway in gateways:
        # Check if already exists
        if frappe.db.exists("Tenant Payment Method", {
            "tenant": tenant, "payment_gateway": gateway.name
        }):
            continue
        
        # Create with Cash on Delivery enabled by default
        enabled = gateway.gateway_type == "cash"
        
        doc = frappe.new_doc("Tenant Payment Method")
        doc.tenant = tenant
        doc.payment_gateway = gateway.name
        doc.display_name = gateway.gateway_name
        doc.is_enabled = enabled
        doc.insert(ignore_permissions=True)
    
    frappe.db.commit()
