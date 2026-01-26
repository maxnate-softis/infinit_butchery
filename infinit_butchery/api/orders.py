"""
Orders API for Infinit Butchery
"""

import frappe
from frappe import _
from frappe.utils import nowdate, nowtime, add_days, getdate
from infinit_butchery.utils import get_tenant_from_request, get_current_tenant


@frappe.whitelist(allow_guest=True)
def create_order(
    items: list,
    customer_name: str,
    customer_phone: str,
    customer_email: str = None,
    order_type: str = "Pickup",
    delivery_address: str = None,
    delivery_zone: str = None,
    preferred_date: str = None,
    preferred_time: str = None,
    notes: str = None
):
    """
    Create a new order from storefront
    
    Args:
        items: List of order items [{"item_code": "x", "qty": 1, "weight_kg": 0.5}]
        customer_name: Customer full name
        customer_phone: Customer phone number
        customer_email: Optional email
        order_type: "Pickup" or "Delivery"
        delivery_address: Address if delivery
        delivery_zone: Delivery zone if delivery
        preferred_date: Preferred pickup/delivery date
        preferred_time: Preferred time slot
        notes: Customer notes
    
    Returns:
        dict: Created order info
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request"))
    
    # Validate items
    if not items or len(items) == 0:
        frappe.throw(_("No items in order"))
    
    # Create order
    order = frappe.new_doc("Butchery Order")
    order.tenant = tenant
    order.order_type = order_type
    order.order_date = nowdate()
    order.order_time = nowtime()
    order.customer_name = customer_name
    order.customer_phone = customer_phone
    order.customer_email = customer_email
    order.notes = notes
    
    # Delivery details
    if order_type == "Delivery":
        if not delivery_address:
            frappe.throw(_("Delivery address is required"))
        order.delivery_address = delivery_address
        order.delivery_zone = delivery_zone
        order.delivery_date = preferred_date or add_days(nowdate(), 1)
        order.delivery_time_slot = preferred_time
    else:
        order.pickup_date = preferred_date or nowdate()
        order.pickup_time = preferred_time
    
    # Add items
    for item_data in items:
        item_code = item_data.get("item_code")
        qty = item_data.get("qty", 1)
        weight_kg = item_data.get("weight_kg", 0)
        
        # Get item details
        item = frappe.get_doc("Item", item_code)
        
        # Calculate rate based on selling by weight or unit
        if item.custom_sell_by_weight and weight_kg:
            rate = item.custom_price_per_kg * weight_kg
        else:
            rate = item.standard_rate or 0
        
        order.append("items", {
            "item": item_code,
            "item_name": item.item_name,
            "qty": qty,
            "uom": item.stock_uom,
            "weight_kg": weight_kg,
            "rate": rate,
            "amount": rate * qty,
            "notes": item_data.get("notes")
        })
    
    # Calculate delivery fee if applicable
    if order_type == "Delivery" and delivery_zone:
        delivery_fee = get_delivery_fee(delivery_zone, tenant)
        order.delivery_fee = delivery_fee
    
    order.insert(ignore_permissions=True)
    
    # Send notification
    try:
        send_order_notification(order.name, "created")
    except Exception as e:
        frappe.log_error(f"Failed to send order notification: {e}")
    
    return {
        "order_id": order.name,
        "status": order.status,
        "total": order.grand_total,
        "message": _("Order created successfully")
    }


@frappe.whitelist(allow_guest=True)
def get_order_status(order_id: str, phone: str = None):
    """
    Get order status for customer tracking
    
    Args:
        order_id: Order ID
        phone: Customer phone for verification
    
    Returns:
        dict: Order status and details
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    filters = {"name": order_id}
    if tenant:
        filters["tenant"] = tenant
    if phone:
        filters["customer_phone"] = phone
    
    order = frappe.get_value(
        "Butchery Order",
        filters,
        ["name", "status", "payment_status", "order_type",
         "delivery_date", "delivery_time_slot", "delivery_address",
         "pickup_date", "pickup_time", "grand_total",
         "customer_name", "order_date"],
        as_dict=True
    )
    
    if not order:
        frappe.throw(_("Order not found"), frappe.DoesNotExistError)
    
    return {
        "order_id": order.name,
        "customer_name": order.customer_name,
        "order_date": order.order_date,
        "status": order.status,
        "payment_status": order.payment_status,
        "order_type": order.order_type,
        "total": order.grand_total,
        "delivery": {
            "date": order.delivery_date,
            "time": order.delivery_time_slot,
            "address": order.delivery_address
        } if order.order_type == "Delivery" else None,
        "pickup": {
            "date": order.pickup_date,
            "time": order.pickup_time
        } if order.order_type == "Pickup" else None
    }


@frappe.whitelist(allow_guest=True)
def get_order_history(phone: str, page: int = 1, page_size: int = 10):
    """
    Get order history for a customer
    
    Args:
        phone: Customer phone number
        page: Page number
        page_size: Items per page
    
    Returns:
        list: List of orders
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    filters = {"customer_phone": phone}
    if tenant:
        filters["tenant"] = tenant
    
    orders = frappe.get_all(
        "Butchery Order",
        filters=filters,
        fields=["name", "order_date", "status", "payment_status",
                "order_type", "grand_total"],
        order_by="order_date desc, creation desc",
        start=(page - 1) * page_size,
        page_length=page_size
    )
    
    return {
        "orders": orders,
        "page": page,
        "page_size": page_size,
        "has_more": len(orders) == page_size
    }


@frappe.whitelist(allow_guest=True)
def cancel_order(order_id: str, phone: str, reason: str = None):
    """
    Cancel an order (if allowed)
    
    Args:
        order_id: Order ID
        phone: Customer phone for verification
        reason: Cancellation reason
    
    Returns:
        dict: Cancellation result
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    filters = {"name": order_id, "customer_phone": phone}
    if tenant:
        filters["tenant"] = tenant
    
    if not frappe.db.exists("Butchery Order", filters):
        frappe.throw(_("Order not found"), frappe.DoesNotExistError)
    
    order = frappe.get_doc("Butchery Order", order_id)
    
    # Only pending orders can be cancelled
    if order.status not in ["Pending", "Confirmed"]:
        frappe.throw(_("Order cannot be cancelled at this stage"))
    
    order.status = "Cancelled"
    order.cancellation_reason = reason
    order.save(ignore_permissions=True)
    
    return {
        "order_id": order.name,
        "status": order.status,
        "message": _("Order cancelled successfully")
    }


@frappe.whitelist(allow_guest=True)
def get_delivery_zones():
    """
    Get available delivery zones with fees
    
    Returns:
        list: List of delivery zones
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request"))
    
    zones = frappe.get_all(
        "Delivery Zone",
        filters={"tenant": tenant, "is_active": 1},
        fields=["name", "zone_name", "delivery_fee", "min_order_amount",
                "delivery_days", "cutoff_time"],
        order_by="zone_name"
    )
    
    return zones


@frappe.whitelist(allow_guest=True)
def get_time_slots(order_type: str = "Pickup", date: str = None):
    """
    Get available time slots for pickup or delivery
    
    Args:
        order_type: "Pickup" or "Delivery"
        date: Date to get slots for (default: today/tomorrow)
    
    Returns:
        list: Available time slots
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not date:
        date = nowdate() if order_type == "Pickup" else add_days(nowdate(), 1)
    
    # Get business hours from tenant settings
    # For now, return default slots
    slots = [
        {"slot": "08:00 - 10:00", "available": True},
        {"slot": "10:00 - 12:00", "available": True},
        {"slot": "12:00 - 14:00", "available": True},
        {"slot": "14:00 - 16:00", "available": True},
        {"slot": "16:00 - 18:00", "available": True},
    ]
    
    return {
        "date": date,
        "order_type": order_type,
        "slots": slots
    }


def get_delivery_fee(zone: str, tenant: str) -> float:
    """Get delivery fee for a zone"""
    fee = frappe.db.get_value(
        "Delivery Zone",
        {"name": zone, "tenant": tenant},
        "delivery_fee"
    )
    return fee or 0


def send_order_notification(order_id: str, event: str):
    """Send order notification to customer and staff"""
    order = frappe.get_doc("Butchery Order", order_id)
    
    # Get tenant notification settings
    # For now, just log
    frappe.logger().info(f"Order {event}: {order_id}")
    
    # TODO: Implement SMS/WhatsApp/Email notifications
    # This would integrate with notification service
