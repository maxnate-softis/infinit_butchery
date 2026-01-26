"""
Install/Setup functions for Infinit Butchery
"""

import frappe
from frappe import _


def after_install():
    """
    Called after app installation
    Sets up initial data, roles, and configurations
    """
    setup_roles()
    setup_payment_gateways()
    setup_custom_fields()
    frappe.db.commit()
    print("Infinit Butchery installed successfully!")


def after_sync():
    """
    Called after database sync (bench migrate)
    Updates fixtures and configurations
    """
    update_fixtures()


def setup_roles():
    """Create custom roles for multi-tenant setup"""
    roles = [
        {
            "role_name": "Tenant Admin",
            "desk_access": 1,
            "is_custom": 1
        },
        {
            "role_name": "Branch Manager",
            "desk_access": 1,
            "is_custom": 1
        },
        {
            "role_name": "Butchery Staff",
            "desk_access": 1,
            "is_custom": 1
        },
        {
            "role_name": "Delivery Staff",
            "desk_access": 0,
            "is_custom": 1
        }
    ]
    
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            role = frappe.new_doc("Role")
            role.update(role_data)
            role.insert(ignore_permissions=True)
            print(f"Created role: {role_data['role_name']}")


def setup_payment_gateways():
    """Setup default payment gateways"""
    gateways = [
        {
            "gateway_name": "Cash on Delivery",
            "gateway_code": "cash_on_delivery",
            "gateway_type": "cash",
            "is_active": 1,
            "handler_module": "infinit_butchery.api.payments.CashOnDeliveryHandler"
        },
        {
            "gateway_name": "Cash on Pickup",
            "gateway_code": "cash_on_pickup",
            "gateway_type": "cash",
            "is_active": 1,
            "handler_module": "infinit_butchery.api.payments.CashOnDeliveryHandler"
        },
        {
            "gateway_name": "Airtel Money",
            "gateway_code": "airtel_money",
            "gateway_type": "mobile_money",
            "is_active": 0,
            "handler_module": "infinit_butchery.payments.airtel_money.AirtelMoneyHandler"
        },
        {
            "gateway_name": "MTN MoMo",
            "gateway_code": "mtn_momo",
            "gateway_type": "mobile_money",
            "is_active": 0,
            "handler_module": "infinit_butchery.payments.mtn_momo.MTNMoMoHandler"
        },
        {
            "gateway_name": "Visa/Mastercard",
            "gateway_code": "card_payment",
            "gateway_type": "card",
            "is_active": 0,
            "handler_module": "infinit_butchery.payments.card.CardPaymentHandler"
        }
    ]
    
    for gateway_data in gateways:
        if not frappe.db.exists("Payment Gateway", gateway_data["gateway_code"]):
            gateway = frappe.new_doc("Payment Gateway")
            gateway.update(gateway_data)
            gateway.insert(ignore_permissions=True)
            print(f"Created payment gateway: {gateway_data['gateway_name']}")


def setup_custom_fields():
    """
    Setup custom fields on standard ERPNext DocTypes
    These enable multi-tenant filtering and butchery-specific data
    """
    custom_fields = {
        "Item": [
            {
                "fieldname": "butchery_section",
                "label": "Butchery Details",
                "fieldtype": "Section Break",
                "insert_after": "description"
            },
            {
                "fieldname": "custom_meat_category",
                "label": "Meat Category",
                "fieldtype": "Link",
                "options": "Meat Category",
                "insert_after": "butchery_section"
            },
            {
                "fieldname": "custom_cut_type",
                "label": "Cut Type",
                "fieldtype": "Data",
                "insert_after": "custom_meat_category"
            },
            {
                "fieldname": "custom_price_per_kg",
                "label": "Price per Kg",
                "fieldtype": "Currency",
                "insert_after": "custom_cut_type"
            },
            {
                "fieldname": "custom_sell_by_weight",
                "label": "Sell by Weight",
                "fieldtype": "Check",
                "insert_after": "custom_price_per_kg"
            },
            {
                "fieldname": "custom_weight_options",
                "label": "Weight Options (JSON)",
                "fieldtype": "Code",
                "options": "JSON",
                "insert_after": "custom_sell_by_weight"
            },
            {
                "fieldname": "custom_is_premium",
                "label": "Is Premium",
                "fieldtype": "Check",
                "insert_after": "custom_weight_options"
            },
            {
                "fieldname": "custom_certification_type",
                "label": "Certification",
                "fieldtype": "Select",
                "options": "\nHalal\nKosher\nOrganic\nGrass-Fed\nFree-Range",
                "insert_after": "custom_is_premium"
            },
            {
                "fieldname": "custom_website_visible",
                "label": "Show on Website",
                "fieldtype": "Check",
                "insert_after": "custom_certification_type"
            }
        ],
        "Warehouse": [
            {
                "fieldname": "custom_tenant",
                "label": "Tenant",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "company"
            },
            {
                "fieldname": "custom_is_cold_storage",
                "label": "Is Cold Storage",
                "fieldtype": "Check",
                "insert_after": "custom_tenant"
            },
            {
                "fieldname": "custom_storage_type",
                "label": "Storage Type",
                "fieldtype": "Select",
                "options": "\nChilled\nFrozen\nDry",
                "depends_on": "eval:doc.custom_is_cold_storage",
                "insert_after": "custom_is_cold_storage"
            }
        ],
        "Branch": [
            {
                "fieldname": "custom_tenant",
                "label": "Tenant",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "company"
            },
            {
                "fieldname": "custom_is_outlet",
                "label": "Is Outlet/Shop",
                "fieldtype": "Check",
                "insert_after": "custom_tenant"
            },
            {
                "fieldname": "custom_outlet_type",
                "label": "Outlet Type",
                "fieldtype": "Select",
                "options": "\nRetail\nWholesale\nBoth",
                "depends_on": "eval:doc.custom_is_outlet",
                "insert_after": "custom_is_outlet"
            }
        ]
    }
    
    for doctype, fields in custom_fields.items():
        for field_data in fields:
            field_name = f"{doctype}-{field_data['fieldname']}"
            if not frappe.db.exists("Custom Field", field_name):
                cf = frappe.new_doc("Custom Field")
                cf.dt = doctype
                cf.update(field_data)
                cf.insert(ignore_permissions=True)
                print(f"Created custom field: {field_name}")


def update_fixtures():
    """Update fixtures after migration"""
    # Re-apply permissions
    setup_roles()
    
    # Ensure payment gateways exist
    setup_payment_gateways()


def before_uninstall():
    """Called before app uninstallation"""
    print("Preparing to uninstall Infinit Butchery...")
    # Add cleanup logic if needed
