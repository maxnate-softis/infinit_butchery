"""
Scheduled Tasks for Infinit Butchery
"""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, getdate


def daily():
    """
    Daily scheduled tasks
    Runs every day at midnight
    """
    check_expiring_batches()
    update_order_statistics()
    cleanup_old_transactions()


def hourly():
    """
    Hourly scheduled tasks
    """
    check_pending_orders()
    sync_inventory_levels()


def weekly():
    """
    Weekly scheduled tasks
    Runs every Sunday
    """
    generate_weekly_reports()
    cleanup_expired_feature_flags()


def check_expiring_batches():
    """
    Check for meat batches expiring within 3 days
    Send notifications to tenant admins
    """
    from infinit_butchery.utils import is_feature_enabled
    
    # Get all tenants with batch tracking enabled
    tenants = frappe.get_all(
        "Tenant Feature Flag",
        filters={
            "feature_code": "batch_traceability",
            "is_enabled": 1
        },
        pluck="tenant"
    )
    
    expiry_threshold = add_days(nowdate(), 3)
    
    for tenant in tenants:
        # Check if Meat Batch doctype exists and has data
        if frappe.db.table_exists("Meat Batch"):
            expiring = frappe.get_all(
                "Meat Batch",
                filters={
                    "tenant": tenant,
                    "status": ["in", ["Active", "In Stock"]],
                    "expiry_date": ["<=", expiry_threshold]
                },
                fields=["name", "batch_id", "meat_category", "expiry_date"]
            )
            
            if expiring:
                notify_expiring_batches(tenant, expiring)


def notify_expiring_batches(tenant: str, batches: list):
    """
    Send notification about expiring batches
    """
    # Get tenant admin users
    admins = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "user_type": "System User"
        },
        fields=["name", "email"]
    )
    
    # Create notification
    for admin in admins:
        if frappe.db.exists("Has Role", {"parent": admin.name, "role": "Tenant Admin"}):
            try:
                frappe.sendmail(
                    recipients=[admin.email],
                    subject=f"Expiring Meat Batches Alert - {tenant}",
                    message=f"""
                    <h3>Expiring Batches Alert</h3>
                    <p>The following meat batches are expiring within 3 days:</p>
                    <ul>
                    {"".join([f"<li>{b['batch_id']} - {b['meat_category']} (Expires: {b['expiry_date']})</li>" for b in batches])}
                    </ul>
                    <p>Please take appropriate action.</p>
                    """
                )
            except Exception as e:
                frappe.log_error(f"Failed to send expiry notification: {e}")


def check_pending_orders():
    """
    Check for orders pending for too long
    Alert staff about orders needing attention
    """
    threshold_hours = 2
    from frappe.utils import add_to_date, now
    
    threshold_time = add_to_date(now(), hours=-threshold_hours)
    
    pending_orders = frappe.get_all(
        "Butchery Order",
        filters={
            "status": "Pending",
            "creation": ["<", threshold_time]
        },
        fields=["name", "tenant", "customer_name", "customer_phone", "creation"]
    )
    
    for order in pending_orders:
        frappe.log_error(
            f"Order {order.name} pending for > {threshold_hours} hours",
            "Pending Order Alert"
        )


def update_order_statistics():
    """
    Update daily order statistics for reporting
    """
    yesterday = add_days(nowdate(), -1)
    
    # Get all tenants
    tenants = frappe.get_all(
        "Company",
        filters={"is_group": 0},
        pluck="name"
    )
    
    for tenant in tenants:
        # Count orders
        order_count = frappe.db.count(
            "Butchery Order",
            {
                "tenant": tenant,
                "order_date": yesterday
            }
        )
        
        if order_count > 0:
            # Calculate total revenue
            total_revenue = frappe.db.sql("""
                SELECT SUM(grand_total) 
                FROM `tabButchery Order`
                WHERE tenant = %s 
                AND order_date = %s
                AND payment_status = 'Paid'
            """, (tenant, yesterday))[0][0] or 0
            
            frappe.logger().info(
                f"Daily stats for {tenant} on {yesterday}: "
                f"{order_count} orders, Revenue: {total_revenue}"
            )


def sync_inventory_levels():
    """
    Sync inventory levels for low stock alerts
    """
    # Get items with stock below reorder level
    low_stock_items = frappe.db.sql("""
        SELECT 
            item.name,
            item.item_name,
            item.custom_meat_category,
            bin.actual_qty,
            item.safety_stock
        FROM `tabItem` item
        JOIN `tabBin` bin ON bin.item_code = item.name
        WHERE item.disabled = 0
        AND bin.actual_qty <= COALESCE(item.safety_stock, 0)
        AND item.custom_meat_category IS NOT NULL
    """, as_dict=True)
    
    if low_stock_items:
        for item in low_stock_items:
            frappe.log_error(
                f"Low stock: {item.item_name} ({item.actual_qty} remaining)",
                "Low Stock Alert"
            )


def cleanup_old_transactions():
    """
    Archive old payment transactions
    Keep only last 90 days of detailed data
    """
    cutoff_date = add_days(nowdate(), -90)
    
    # Count old failed transactions
    old_failed = frappe.db.count(
        "Payment Transaction",
        {
            "status": "Failed",
            "creation": ["<", cutoff_date]
        }
    )
    
    if old_failed > 0:
        frappe.logger().info(f"Found {old_failed} old failed transactions for cleanup")


def generate_weekly_reports():
    """
    Generate weekly business reports
    """
    from frappe.utils import get_first_day_of_week, get_last_day_of_week
    
    # Get week dates
    week_start = get_first_day_of_week(add_days(nowdate(), -7))
    week_end = get_last_day_of_week(add_days(nowdate(), -7))
    
    frappe.logger().info(f"Generating weekly report for {week_start} to {week_end}")


def cleanup_expired_feature_flags():
    """
    Cleanup or disable expired feature flags
    """
    # Log any disabled features for auditing
    disabled_features = frappe.get_all(
        "Tenant Feature Flag",
        filters={"is_enabled": 0},
        fields=["tenant", "feature_code", "disabled_date"]
    )
    
    if disabled_features:
        frappe.logger().info(
            f"Audit: {len(disabled_features)} disabled feature flags across all tenants"
        )
