"""
Multi-tenant utilities for Infinit Butchery
"""

import frappe
from frappe import _
import functools


def get_current_tenant() -> str:
    """Get the current tenant from session or API key"""
    # Check if tenant is set in session
    tenant = frappe.local.get("tenant")
    if tenant:
        return tenant
    
    # Check if user has a tenant assigned
    if frappe.session.user and frappe.session.user != "Guest":
        tenant = frappe.db.get_value("User", frappe.session.user, "custom_tenant")
        if tenant:
            frappe.local.tenant = tenant
            return tenant
    
    # Check API key header
    api_key = frappe.get_request_header("X-Tenant-ID")
    if api_key:
        frappe.local.tenant = api_key
        return api_key
    
    return None


def get_user_tenant(user: str) -> str:
    """Get the tenant assigned to a user"""
    return frappe.db.get_value("User", user, "custom_tenant")


def validate_tenant_access(doc, method=None):
    """Ensure user can only access their tenant's data"""
    # Skip for Administrator
    if frappe.session.user == "Administrator":
        return
    
    # Skip for doctypes without tenant field
    if not hasattr(doc, "tenant"):
        return
    
    # Skip if document is new and tenant not set yet
    if doc.is_new() and not doc.tenant:
        doc.tenant = get_current_tenant()
        return
    
    user_tenant = get_user_tenant(frappe.session.user)
    if not user_tenant:
        return
    
    if doc.tenant and doc.tenant != user_tenant:
        frappe.throw(_("Access Denied: You can only access your own tenant's data"), frappe.PermissionError)


def apply_tenant_filter(doctype: str, filters: dict) -> dict:
    """Auto-filter queries by tenant"""
    if frappe.session.user == "Administrator":
        return filters
    
    user_tenant = get_user_tenant(frappe.session.user)
    if not user_tenant:
        return filters
    
    # Check if doctype has tenant field
    meta = frappe.get_meta(doctype)
    if meta.has_field("tenant"):
        filters["tenant"] = user_tenant
    
    return filters


def is_super_admin() -> bool:
    """Check if current user is a Super Admin"""
    if frappe.session.user == "Administrator":
        return True
    
    return "Butchery Super Admin" in frappe.get_roles(frappe.session.user)


def is_tenant_admin() -> bool:
    """Check if current user is a Tenant Admin"""
    return "Butchery Tenant Admin" in frappe.get_roles(frappe.session.user)


def tenant_required(func):
    """Decorator to require a tenant context"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tenant = get_current_tenant()
        if not tenant:
            frappe.throw(_("Tenant context required"))
        return func(*args, **kwargs)
    return wrapper


def get_tenant_from_request() -> str:
    """Get tenant from API request (for public endpoints)"""
    # Check header
    tenant = frappe.get_request_header("X-Tenant-ID")
    if tenant:
        return tenant
    
    # Check subdomain
    host = frappe.get_request_header("Host", "")
    if host:
        subdomain = host.split(".")[0]
        tenant = frappe.db.get_value("Tenant", {"subdomain": subdomain}, "name")
        if tenant:
            return tenant
    
    return None


def get_tenant_currency(tenant: str) -> str:
    """Get the currency configured for a tenant"""
    currency = frappe.db.get_value("Tenant", tenant, "currency")
    return currency or "USD"
