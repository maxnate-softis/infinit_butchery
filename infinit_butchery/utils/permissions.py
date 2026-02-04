"""
Infinit Butchery - Permission Query Conditions
Enforces READ isolation for multi-tenant data access.

This module provides permission_query_conditions for all Butchery DocTypes,
preventing users from READING data belonging to other tenants.

Combined with doc_events in hooks.py (validate_tenant_access),
this provides complete tenant isolation:
- doc_events: WRITE protection (before_insert, validate)
- permission_query_conditions: READ protection (get_list, get_count, search)

Note: Butchery uses "tenant" field for isolation on core DocTypes,
while configuration DocTypes may use "company".
"""

import frappe
from frappe import _


def _get_user_tenant(user=None):
    """Get the tenant assigned to the user."""
    if not user:
        user = frappe.session.user
    
    if user == "Administrator":
        return None
    
    # Check custom_tenant field on user
    tenant = frappe.db.get_value("User", user, "custom_tenant")
    if tenant:
        return tenant
    
    # Fallback to company default
    company = frappe.defaults.get_user_default("Company", user=user)
    return company


def _permission_query(doctype, user=None, tenant_field="tenant"):
    """
    Generic permission query condition generator.
    
    Args:
        doctype: The DocType name for table prefix
        user: The user to check permissions for
        tenant_field: Field name used for tenant isolation (default: "tenant")
    
    Returns:
        SQL WHERE clause string or empty string for Administrator
    """
    if not user:
        user = frappe.session.user
    
    if user == "Administrator":
        return ""
    
    tenant = _get_user_tenant(user)
    if not tenant:
        # No tenant = no access to any records
        return "1=0"
    
    # Escape tenant name to prevent SQL injection
    safe_tenant = frappe.db.escape(tenant)
    
    # Use backticks for table/field names
    table_name = f"tab{doctype}".replace(" ", " ")
    return f"(`{table_name}`.`{tenant_field}` = {safe_tenant})"


def _has_permission(doc, user=None, tenant_field="tenant"):
    """
    Generic has_permission check.
    
    Args:
        doc: The document to check
        user: The user to check permissions for
        tenant_field: Field name used for tenant isolation
    
    Returns:
        True if user has permission, False otherwise
    """
    if not user:
        user = frappe.session.user
    
    if user == "Administrator":
        return True
    
    tenant = _get_user_tenant(user)
    if not tenant:
        return False
    
    doc_tenant = getattr(doc, tenant_field, None)
    if not doc_tenant:
        # Document has no tenant - allow if user has tenant
        return True
    
    return doc_tenant == tenant


# =============================================================================
# BUTCHERY CORE DOCTYPES - Use "tenant" field
# =============================================================================

def order_query(user=None):
    """Permission query for Butchery Order doctype."""
    return _permission_query("Butchery Order", user, "tenant")


def has_order_permission(doc, user=None, permission_type=None):
    """Has permission check for Butchery Order doctype."""
    return _has_permission(doc, user, "tenant")


def order_item_query(user=None):
    """Permission query for Butchery Order Item (child table)."""
    return _permission_query("Butchery Order Item", user, "tenant")


def payment_query(user=None):
    """Permission query for Payment Transaction doctype."""
    return _permission_query("Payment Transaction", user, "tenant")


def has_payment_permission(doc, user=None, permission_type=None):
    """Has permission check for Payment Transaction doctype."""
    return _has_permission(doc, user, "tenant")


def meat_category_query(user=None):
    """Permission query for Meat Category doctype."""
    return _permission_query("Meat Category", user, "tenant")


def has_meat_category_permission(doc, user=None, permission_type=None):
    """Has permission check for Meat Category doctype."""
    return _has_permission(doc, user, "tenant")


def delivery_zone_query(user=None):
    """Permission query for Delivery Zone doctype."""
    return _permission_query("Delivery Zone", user, "tenant")


def has_delivery_zone_permission(doc, user=None, permission_type=None):
    """Has permission check for Delivery Zone doctype."""
    return _has_permission(doc, user, "tenant")


# =============================================================================
# PAYMENT GATEWAY DOCTYPES - Use "tenant" field
# =============================================================================

def payment_gateway_query(user=None):
    """Permission query for Payment Gateway doctype."""
    return _permission_query("Payment Gateway", user, "tenant")


def has_payment_gateway_permission(doc, user=None, permission_type=None):
    """Has permission check for Payment Gateway doctype."""
    return _has_permission(doc, user, "tenant")


def tenant_payment_method_query(user=None):
    """Permission query for Tenant Payment Method doctype."""
    return _permission_query("Tenant Payment Method", user, "tenant")


def has_tenant_payment_method_permission(doc, user=None, permission_type=None):
    """Has permission check for Tenant Payment Method doctype."""
    return _has_permission(doc, user, "tenant")


# =============================================================================
# FEATURE FLAG DOCTYPES - Use "tenant" field
# =============================================================================

def tenant_feature_flag_query(user=None):
    """Permission query for Tenant Feature Flag doctype."""
    return _permission_query("Tenant Feature Flag", user, "tenant")


def has_tenant_feature_flag_permission(doc, user=None, permission_type=None):
    """Has permission check for Tenant Feature Flag doctype."""
    return _has_permission(doc, user, "tenant")
