"""
Butchery Order DocType
"""

import frappe
from frappe.model.document import Document
from frappe import _


class ButcheryOrder(Document):
    def before_insert(self):
        """Set tenant from current context if not provided"""
        if not self.tenant:
            from infinit_butchery.utils import get_current_tenant
            self.tenant = get_current_tenant()
        
        if not self.order_date:
            self.order_date = frappe.utils.now()
    
    def validate(self):
        """Validate the order"""
        self.calculate_totals()
        self.validate_delivery()
    
    def calculate_totals(self):
        """Calculate order totals"""
        self.subtotal = 0
        for item in self.items:
            item.amount = (item.qty or 0) * (item.rate or 0)
            self.subtotal += item.amount
        
        # Calculate tax (configurable per tenant)
        tax_rate = frappe.db.get_value("Tenant", self.tenant, "tax_rate") or 0
        self.tax_amount = self.subtotal * (tax_rate / 100)
        
        # Calculate grand total
        self.grand_total = (
            self.subtotal 
            - (self.discount_amount or 0) 
            + (self.delivery_fee or 0) 
            + self.tax_amount
        )
    
    def validate_delivery(self):
        """Validate delivery requirements"""
        if self.requires_delivery:
            if not self.delivery_address:
                frappe.throw(_("Delivery address is required for delivery orders"))
            if self.delivery_status == "Not Required":
                self.delivery_status = "Pending"
        else:
            self.delivery_status = "Not Required"
    
    def on_update(self):
        """Handle status changes"""
        if self.status == "Completed" and not self.completed_at:
            self.db_set("completed_at", frappe.utils.now())
        
        # Notify customer on status change
        if self.has_value_changed("status"):
            self.send_status_notification()
    
    def send_status_notification(self):
        """Send notification on status change"""
        if not self.customer_phone and not self.customer_email:
            return
        
        # Create notification record (can be extended to send SMS/email)
        frappe.publish_realtime(
            "order_status_changed",
            {
                "order_id": self.name,
                "status": self.status,
                "customer": self.customer_name
            },
            user=frappe.session.user
        )
    
    def confirm_order(self):
        """Confirm the order"""
        if self.status != "Draft":
            frappe.throw(_("Only draft orders can be confirmed"))
        
        self.status = "Confirmed"
        self.save()
        return self
    
    def cancel_order(self, reason: str = None):
        """Cancel the order"""
        if self.status in ["Completed", "Cancelled"]:
            frappe.throw(_("Cannot cancel a {0} order").format(self.status.lower()))
        
        self.status = "Cancelled"
        if reason:
            self.notes = (self.notes or "") + f"\n\nCancellation reason: {reason}"
        self.save()
        return self


def on_update(doc, method):
    """Document event handler"""
    pass


@frappe.whitelist()
def create_order(order_data: dict) -> dict:
    """Create a new butchery order"""
    from infinit_butchery.utils import get_current_tenant
    
    tenant = get_current_tenant()
    if not tenant:
        frappe.throw(_("Tenant context required"))
    
    order = frappe.get_doc({
        "doctype": "Butchery Order",
        "tenant": tenant,
        "order_type": order_data.get("order_type", "Online"),
        "customer": order_data.get("customer"),
        "customer_name": order_data.get("customer_name"),
        "customer_phone": order_data.get("customer_phone"),
        "customer_email": order_data.get("customer_email"),
        "requires_delivery": order_data.get("requires_delivery", False),
        "delivery_zone": order_data.get("delivery_zone"),
        "delivery_address": order_data.get("delivery_address"),
        "delivery_date": order_data.get("delivery_date"),
        "delivery_time_slot": order_data.get("delivery_time_slot"),
        "notes": order_data.get("notes"),
        "items": order_data.get("items", [])
    })
    
    order.insert(ignore_permissions=True)
    
    return {
        "order_id": order.name,
        "status": order.status,
        "grand_total": order.grand_total
    }


@frappe.whitelist()
def get_order_status(order_id: str) -> dict:
    """Get order status and details"""
    from infinit_butchery.utils import get_current_tenant
    
    tenant = get_current_tenant()
    order = frappe.get_doc("Butchery Order", order_id)
    
    if order.tenant != tenant:
        frappe.throw(_("Order not found"), frappe.DoesNotExistError)
    
    return {
        "order_id": order.name,
        "status": order.status,
        "payment_status": order.payment_status,
        "delivery_status": order.delivery_status,
        "grand_total": order.grand_total,
        "items": [
            {
                "item_name": item.item_name,
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount
            }
            for item in order.items
        ]
    }
