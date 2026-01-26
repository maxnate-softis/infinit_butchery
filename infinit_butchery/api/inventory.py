"""
Inventory API for Infinit Butchery
"""

import frappe
from frappe import _
from infinit_butchery.utils import get_tenant_from_request, get_current_tenant


@frappe.whitelist(allow_guest=True)
def get_products(
    category: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    include_out_of_stock: bool = False
):
    """
    Get products for storefront
    
    Args:
        category: Filter by meat category
        search: Search term for product name
        page: Page number (1-indexed)
        page_size: Items per page
        include_out_of_stock: Whether to include out-of-stock items
    
    Returns:
        dict: List of products with pagination info
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request - tenant not found"))
    
    filters = {
        "disabled": 0,
        "custom_website_visible": 1
    }
    
    # Add tenant filter via custom field or item group
    # In multi-tenant setup, items are filtered by tenant
    
    if category:
        filters["custom_meat_category"] = category
    
    if search:
        filters["item_name"] = ["like", f"%{search}%"]
    
    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=[
            "name", "item_name", "item_code",
            "custom_meat_category", "custom_cut_type",
            "custom_price_per_kg", "custom_sell_by_weight",
            "custom_weight_options", "custom_is_premium",
            "custom_certification_type", "description",
            "image"
        ],
        order_by="custom_is_premium desc, item_name",
        start=(page - 1) * page_size,
        page_length=page_size
    )
    
    # Add stock information
    for item in items:
        stock = get_item_stock(item["name"], tenant)
        item["in_stock"] = stock > 0
        item["stock_qty"] = stock if include_out_of_stock else None
        
        # Parse weight options if available
        if item.get("custom_weight_options"):
            try:
                item["weight_options"] = frappe.parse_json(item["custom_weight_options"])
            except:
                item["weight_options"] = []
    
    if not include_out_of_stock:
        items = [i for i in items if i["in_stock"]]
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": len(items) == page_size
    }


@frappe.whitelist(allow_guest=True)
def get_product_detail(item_code: str):
    """
    Get detailed product information
    
    Args:
        item_code: Item code or name
    
    Returns:
        dict: Product details
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    item = frappe.get_doc("Item", item_code)
    
    if item.disabled or not item.custom_website_visible:
        frappe.throw(_("Product not found"), frappe.DoesNotExistError)
    
    stock = get_item_stock(item.name, tenant)
    
    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "description": item.description,
        "image": item.image,
        "category": item.custom_meat_category,
        "cut_type": item.custom_cut_type,
        "price_per_kg": item.custom_price_per_kg,
        "sell_by_weight": item.custom_sell_by_weight,
        "weight_options": frappe.parse_json(item.custom_weight_options) if item.custom_weight_options else [],
        "is_premium": item.custom_is_premium,
        "certification": item.custom_certification_type,
        "in_stock": stock > 0,
        "stock_qty": stock
    }


@frappe.whitelist(allow_guest=True)
def get_categories():
    """
    Get product categories for storefront
    
    Returns:
        list: List of categories with product counts
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request - tenant not found"))
    
    categories = frappe.get_all(
        "Meat Category",
        filters={"tenant": tenant, "is_active": 1},
        fields=["name", "category_name", "category_code", "image", "description", "display_order"],
        order_by="display_order"
    )
    
    # Add product count
    for cat in categories:
        cat["product_count"] = frappe.db.count(
            "Item",
            {
                "custom_meat_category": cat["name"],
                "disabled": 0,
                "custom_website_visible": 1
            }
        )
    
    return categories


@frappe.whitelist(allow_guest=True)
def check_stock(item_code: str, qty: float = 1):
    """
    Check if item has sufficient stock
    
    Args:
        item_code: Item code
        qty: Required quantity
    
    Returns:
        dict: Stock availability info
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    stock = get_item_stock(item_code, tenant)
    
    return {
        "item_code": item_code,
        "available_qty": stock,
        "requested_qty": qty,
        "is_available": stock >= qty
    }


@frappe.whitelist(allow_guest=True)
def get_batch_info(batch_id: str):
    """
    Get batch traceability information
    
    Args:
        batch_id: Batch ID or Meat Batch name
    
    Returns:
        dict: Batch information for traceability
    """
    from infinit_butchery.utils import is_feature_enabled
    
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not is_feature_enabled("batch_traceability", tenant):
        frappe.throw(_("Batch traceability feature is not enabled"))
    
    # Try to find meat batch
    batch = frappe.db.get_value(
        "Meat Batch",
        {"name": batch_id, "tenant": tenant},
        ["name", "batch_id", "meat_category", "supplier", "receipt_date", 
         "slaughter_date", "expiry_date", "certification_type", "status"],
        as_dict=True
    )
    
    if not batch:
        frappe.throw(_("Batch not found"), frappe.DoesNotExistError)
    
    return {
        "batch_id": batch.batch_id or batch.name,
        "category": batch.meat_category,
        "supplier": batch.supplier,
        "receipt_date": batch.receipt_date,
        "slaughter_date": batch.slaughter_date,
        "expiry_date": batch.expiry_date,
        "certification": batch.certification_type,
        "status": batch.status
    }


def get_item_stock(item_code: str, tenant: str = None) -> float:
    """
    Get available stock for an item
    
    Args:
        item_code: Item code
        tenant: Tenant name (for warehouse filtering)
    
    Returns:
        float: Available quantity
    """
    # Get warehouse(s) for tenant
    warehouses = []
    if tenant:
        warehouses = frappe.get_all(
            "Warehouse",
            filters={"custom_tenant": tenant, "is_group": 0},
            pluck="name"
        )
    
    if not warehouses:
        # Get all non-group warehouses
        warehouses = frappe.get_all(
            "Warehouse",
            filters={"is_group": 0},
            pluck="name"
        )
    
    total_qty = 0
    for warehouse in warehouses:
        qty = frappe.db.get_value(
            "Bin",
            {"item_code": item_code, "warehouse": warehouse},
            "actual_qty"
        ) or 0
        total_qty += qty
    
    return total_qty
