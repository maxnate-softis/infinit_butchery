"""
Meat Category DocType
"""

import frappe
from frappe.model.document import Document


class MeatCategory(Document):
    def before_insert(self):
        """Set tenant from current context if not provided"""
        if not self.tenant:
            from infinit_butchery.utils import get_current_tenant
            self.tenant = get_current_tenant()
    
    def validate(self):
        """Validate the meat category"""
        self.validate_parent_category()
        self.validate_temperature_range()
    
    def validate_parent_category(self):
        """Ensure parent category belongs to same tenant"""
        if self.parent_category:
            parent_tenant = frappe.db.get_value("Meat Category", self.parent_category, "tenant")
            if parent_tenant != self.tenant:
                frappe.throw("Parent category must belong to the same tenant")
    
    def validate_temperature_range(self):
        """Validate temperature range"""
        if self.storage_temp_min and self.storage_temp_max:
            if self.storage_temp_min > self.storage_temp_max:
                frappe.throw("Min temperature cannot be greater than max temperature")


def get_categories_for_tenant(tenant: str) -> list:
    """Get all active categories for a tenant"""
    return frappe.get_all(
        "Meat Category",
        filters={"tenant": tenant, "is_active": 1},
        fields=["name", "category_name", "category_code", "image", "description", "display_order"],
        order_by="display_order"
    )
