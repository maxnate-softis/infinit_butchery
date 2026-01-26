"""
Admin API for Infinit Butchery
Super Admin and Tenant Admin endpoints
"""

import frappe
from frappe import _
from frappe.utils import nowdate


@frappe.whitelist()
def get_tenant_dashboard(tenant: str = None) -> dict:
    """
    Get dashboard data for tenant admin
    
    Args:
        tenant: Tenant name (auto-detected if not provided)
    
    Returns:
        dict: Dashboard statistics
    """
    from infinit_butchery.utils import get_current_tenant, validate_tenant_access
    
    tenant = tenant or get_current_tenant()
    validate_tenant_access(tenant)
    
    today = nowdate()
    
    # Orders today
    orders_today = frappe.db.count(
        "Butchery Order",
        {"tenant": tenant, "order_date": today}
    )
    
    # Pending orders
    pending_orders = frappe.db.count(
        "Butchery Order",
        {"tenant": tenant, "status": "Pending"}
    )
    
    # Revenue today
    revenue_today = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabButchery Order`
        WHERE tenant = %s AND order_date = %s AND payment_status = 'Paid'
    """, (tenant, today))[0][0]
    
    # Active products
    active_products = frappe.db.count(
        "Item",
        {"custom_website_visible": 1, "disabled": 0}
    )
    
    # Recent orders
    recent_orders = frappe.get_all(
        "Butchery Order",
        filters={"tenant": tenant},
        fields=["name", "customer_name", "status", "grand_total", "order_date", "order_type"],
        order_by="creation desc",
        limit=10
    )
    
    return {
        "summary": {
            "orders_today": orders_today,
            "pending_orders": pending_orders,
            "revenue_today": revenue_today,
            "active_products": active_products
        },
        "recent_orders": recent_orders
    }


@frappe.whitelist()
def get_tenant_settings(tenant: str = None) -> dict:
    """
    Get tenant settings and configuration
    
    Args:
        tenant: Tenant name
    
    Returns:
        dict: Tenant settings
    """
    from infinit_butchery.utils import get_current_tenant, validate_tenant_access
    
    tenant = tenant or get_current_tenant()
    validate_tenant_access(tenant)
    
    company = frappe.get_doc("Company", tenant)
    
    # Get enabled features
    features = frappe.get_all(
        "Tenant Feature Flag",
        filters={"tenant": tenant},
        fields=["feature_code", "feature_name", "is_enabled", "feature_category"]
    )
    
    # Get payment methods
    payment_methods = frappe.get_all(
        "Tenant Payment Method",
        filters={"tenant": tenant},
        fields=["payment_gateway", "display_name", "is_enabled", "gateway_type"]
    )
    
    # Get delivery zones
    delivery_zones = frappe.get_all(
        "Delivery Zone",
        filters={"tenant": tenant},
        fields=["name", "zone_name", "delivery_fee", "is_active"]
    )
    
    return {
        "company": {
            "name": company.name,
            "company_name": company.company_name,
            "default_currency": company.default_currency,
            "country": company.country
        },
        "features": features,
        "payment_methods": payment_methods,
        "delivery_zones": delivery_zones
    }


@frappe.whitelist()
def update_order_status(order_id: str, status: str, notes: str = None) -> dict:
    """
    Update order status (for staff)
    
    Args:
        order_id: Order ID
        status: New status
        notes: Optional notes
    
    Returns:
        dict: Updated order info
    """
    from infinit_butchery.utils import get_current_tenant, validate_tenant_access
    
    tenant = get_current_tenant()
    
    order = frappe.get_doc("Butchery Order", order_id)
    validate_tenant_access(order.tenant)
    
    valid_transitions = {
        "Pending": ["Confirmed", "Cancelled"],
        "Confirmed": ["Preparing", "Cancelled"],
        "Preparing": ["Ready", "Cancelled"],
        "Ready": ["Out for Delivery", "Completed", "Cancelled"],
        "Out for Delivery": ["Completed", "Cancelled"],
    }
    
    allowed = valid_transitions.get(order.status, [])
    if status not in allowed:
        frappe.throw(_("Cannot change status from {0} to {1}").format(order.status, status))
    
    order.status = status
    if notes:
        order.add_comment("Comment", notes)
    
    order.save()
    
    # Send notification to customer
    try:
        from infinit_butchery.api.orders import send_order_notification
        send_order_notification(order.name, "status_changed")
    except Exception as e:
        frappe.log_error(f"Notification error: {e}")
    
    return {
        "order_id": order.name,
        "status": order.status,
        "message": _("Status updated successfully")
    }


@frappe.whitelist()
def get_orders_list(
    tenant: str = None,
    status: str = None,
    order_type: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    Get orders list with filters
    
    Args:
        tenant: Tenant name
        status: Filter by status
        order_type: Filter by order type
        date_from: Start date
        date_to: End date
        page: Page number
        page_size: Items per page
    
    Returns:
        dict: Orders list with pagination
    """
    from infinit_butchery.utils import get_current_tenant, validate_tenant_access
    
    tenant = tenant or get_current_tenant()
    validate_tenant_access(tenant)
    
    filters = {"tenant": tenant}
    
    if status:
        filters["status"] = status
    if order_type:
        filters["order_type"] = order_type
    if date_from:
        filters["order_date"] = [">=", date_from]
    if date_to:
        if "order_date" in filters:
            filters["order_date"] = ["between", [date_from, date_to]]
        else:
            filters["order_date"] = ["<=", date_to]
    
    orders = frappe.get_all(
        "Butchery Order",
        filters=filters,
        fields=[
            "name", "customer_name", "customer_phone",
            "status", "payment_status", "order_type",
            "grand_total", "order_date", "order_time"
        ],
        order_by="creation desc",
        start=(page - 1) * page_size,
        page_length=page_size
    )
    
    total = frappe.db.count("Butchery Order", filters)
    
    return {
        "orders": orders,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def create_meat_category(
    tenant: str,
    category_name: str,
    category_code: str = None,
    parent_category: str = None,
    description: str = None
) -> dict:
    """
    Create a new meat category
    
    Args:
        tenant: Tenant name
        category_name: Category name
        category_code: Optional code (auto-generated if not provided)
        parent_category: Optional parent category
        description: Optional description
    
    Returns:
        dict: Created category info
    """
    from infinit_butchery.utils import validate_tenant_access
    
    validate_tenant_access(tenant)
    
    if not category_code:
        # Generate code from name
        category_code = category_name.upper()[:10].replace(" ", "-")
    
    category = frappe.new_doc("Meat Category")
    category.tenant = tenant
    category.category_name = category_name
    category.category_code = category_code
    category.parent_category = parent_category
    category.description = description
    category.is_active = 1
    category.insert()
    
    return {
        "name": category.name,
        "category_name": category.category_name,
        "message": _("Category created successfully")
    }


@frappe.whitelist()
def get_reports_summary(
    tenant: str = None,
    period: str = "today"
) -> dict:
    """
    Get reports summary
    
    Args:
        tenant: Tenant name
        period: "today", "week", "month", "custom"
    
    Returns:
        dict: Reports data
    """
    from infinit_butchery.utils import get_current_tenant, validate_tenant_access
    from frappe.utils import add_days, get_first_day, get_last_day
    
    tenant = tenant or get_current_tenant()
    validate_tenant_access(tenant)
    
    today = nowdate()
    
    if period == "today":
        date_from = today
        date_to = today
    elif period == "week":
        date_from = add_days(today, -7)
        date_to = today
    elif period == "month":
        date_from = get_first_day(today)
        date_to = today
    else:
        date_from = today
        date_to = today
    
    # Orders count by status
    status_breakdown = frappe.db.sql("""
        SELECT status, COUNT(*) as count
        FROM `tabButchery Order`
        WHERE tenant = %s AND order_date BETWEEN %s AND %s
        GROUP BY status
    """, (tenant, date_from, date_to), as_dict=True)
    
    # Revenue by day
    daily_revenue = frappe.db.sql("""
        SELECT order_date, SUM(grand_total) as revenue, COUNT(*) as orders
        FROM `tabButchery Order`
        WHERE tenant = %s AND order_date BETWEEN %s AND %s AND payment_status = 'Paid'
        GROUP BY order_date
        ORDER BY order_date
    """, (tenant, date_from, date_to), as_dict=True)
    
    # Top products
    top_products = frappe.db.sql("""
        SELECT 
            item.item_name,
            SUM(item.qty) as total_qty,
            SUM(item.amount) as total_revenue
        FROM `tabButchery Order Item` item
        JOIN `tabButchery Order` o ON item.parent = o.name
        WHERE o.tenant = %s AND o.order_date BETWEEN %s AND %s
        GROUP BY item.item
        ORDER BY total_qty DESC
        LIMIT 10
    """, (tenant, date_from, date_to), as_dict=True)
    
    return {
        "period": {
            "from": date_from,
            "to": date_to,
            "type": period
        },
        "status_breakdown": status_breakdown,
        "daily_revenue": daily_revenue,
        "top_products": top_products
    }
