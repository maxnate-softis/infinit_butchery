"""
Delivery Zone DocType
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowtime, get_datetime, getdate


class DeliveryZone(Document):
    def validate(self):
        # Validate custom days format
        if self.delivery_days == "Custom" and self.custom_days:
            valid_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            days = [d.strip() for d in self.custom_days.split(",")]
            for day in days:
                if day not in valid_days:
                    frappe.throw(_("Invalid day: {0}. Use: {1}").format(day, ", ".join(valid_days)))
        
        # Normalize zone code
        if self.zone_code:
            self.zone_code = self.zone_code.upper().replace(" ", "-")
    
    def is_delivery_available_today(self) -> bool:
        """Check if delivery is available today"""
        from datetime import datetime
        
        today = datetime.now()
        day_name = today.strftime("%a")  # Mon, Tue, etc.
        
        if self.delivery_days == "Daily":
            return True
        elif self.delivery_days == "Weekdays Only":
            return day_name in ["Mon", "Tue", "Wed", "Thu", "Fri"]
        elif self.delivery_days == "Weekends Only":
            return day_name in ["Sat", "Sun"]
        elif self.delivery_days == "Custom" and self.custom_days:
            allowed_days = [d.strip() for d in self.custom_days.split(",")]
            return day_name in allowed_days
        
        return False
    
    def is_within_cutoff(self) -> bool:
        """Check if current time is within order cutoff"""
        if not self.cutoff_time:
            return True
        
        current_time = nowtime()
        return current_time <= str(self.cutoff_time)
    
    def covers_area(self, area: str) -> bool:
        """Check if this zone covers a specific area"""
        if not self.areas:
            return False
        
        covered_areas = [a.strip().lower() for a in self.areas.split("\n") if a.strip()]
        return area.lower() in covered_areas
    
    def covers_postal_code(self, postal_code: str) -> bool:
        """Check if this zone covers a specific postal code"""
        if not self.postal_codes:
            return False
        
        covered_codes = [c.strip() for c in self.postal_codes.split("\n") if c.strip()]
        return postal_code in covered_codes


@frappe.whitelist()
def get_zone_for_area(tenant: str, area: str) -> dict:
    """
    Find delivery zone that covers an area
    
    Args:
        tenant: Tenant name
        area: Area/suburb name
    
    Returns:
        dict: Zone info or None
    """
    zones = frappe.get_all(
        "Delivery Zone",
        filters={"tenant": tenant, "is_active": 1},
        fields=["name", "zone_name", "delivery_fee", "min_order_amount",
                "cutoff_time", "estimated_delivery_hours", "areas"]
    )
    
    for zone in zones:
        if zone.areas:
            covered_areas = [a.strip().lower() for a in zone.areas.split("\n") if a.strip()]
            if area.lower() in covered_areas:
                return {
                    "zone": zone.name,
                    "zone_name": zone.zone_name,
                    "delivery_fee": zone.delivery_fee,
                    "min_order_amount": zone.min_order_amount,
                    "estimated_hours": zone.estimated_delivery_hours
                }
    
    return None


@frappe.whitelist()
def get_available_zones(tenant: str, order_amount: float = 0) -> list:
    """
    Get available delivery zones for a tenant
    
    Args:
        tenant: Tenant name
        order_amount: Order amount to check minimum requirements
    
    Returns:
        list: Available zones
    """
    filters = {"tenant": tenant, "is_active": 1}
    
    zones = frappe.get_all(
        "Delivery Zone",
        filters=filters,
        fields=["name", "zone_name", "zone_code", "delivery_fee",
                "min_order_amount", "delivery_days", "cutoff_time",
                "estimated_delivery_hours"]
    )
    
    result = []
    for zone in zones:
        zone_doc = frappe.get_doc("Delivery Zone", zone.name)
        
        available = True
        reason = None
        
        # Check minimum order
        if zone.min_order_amount and order_amount < zone.min_order_amount:
            available = False
            reason = f"Minimum order {zone.min_order_amount}"
        
        # Check if delivery is available today
        if not zone_doc.is_delivery_available_today():
            available = False
            reason = "No delivery today"
        
        # Check cutoff time
        if not zone_doc.is_within_cutoff():
            reason = "Order cutoff passed"
        
        result.append({
            **zone,
            "available": available,
            "reason": reason
        })
    
    return result
