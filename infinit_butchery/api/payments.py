"""
Payments API for Infinit Butchery
Pluggable payment gateway integration
"""

import frappe
from frappe import _
from frappe.utils import nowdate, nowtime
from infinit_butchery.utils import get_tenant_from_request, get_current_tenant, is_feature_enabled


@frappe.whitelist(allow_guest=True)
def get_payment_methods():
    """
    Get available payment methods for tenant
    
    Returns:
        list: List of enabled payment methods
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request"))
    
    methods = frappe.get_all(
        "Tenant Payment Method",
        filters={"tenant": tenant, "is_enabled": 1},
        fields=["payment_gateway", "display_name", "gateway_type",
                "supports_mobile", "min_amount", "max_amount"],
        order_by="display_order"
    )
    
    # Group by type for frontend
    result = {
        "mobile_money": [],
        "card": [],
        "cash": [],
        "bank": []
    }
    
    for method in methods:
        gateway_type = method.get("gateway_type", "other")
        if gateway_type in result:
            result[gateway_type].append({
                "code": method["payment_gateway"],
                "name": method["display_name"],
                "supports_mobile": method["supports_mobile"],
                "min_amount": method["min_amount"],
                "max_amount": method["max_amount"]
            })
    
    return result


@frappe.whitelist(allow_guest=True)
def initiate_payment(
    order_id: str,
    payment_method: str,
    phone: str = None,
    amount: float = None,
    return_url: str = None
):
    """
    Initiate payment for an order
    
    Args:
        order_id: Butchery Order ID
        payment_method: Payment gateway code
        phone: Mobile money phone number (if applicable)
        amount: Payment amount (default: order total)
        return_url: URL to redirect after payment
    
    Returns:
        dict: Payment initiation result
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    if not tenant:
        frappe.throw(_("Invalid request"))
    
    # Validate order
    order = frappe.get_doc("Butchery Order", order_id)
    if order.tenant != tenant:
        frappe.throw(_("Order not found"), frappe.DoesNotExistError)
    
    if order.payment_status == "Paid":
        frappe.throw(_("Order is already paid"))
    
    # Get payment method configuration
    method = frappe.get_doc("Tenant Payment Method", {
        "tenant": tenant,
        "payment_gateway": payment_method,
        "is_enabled": 1
    })
    
    if not method:
        frappe.throw(_("Payment method not available"))
    
    # Get gateway configuration
    gateway = frappe.get_doc("Payment Gateway", method.payment_gateway)
    
    # Calculate amount
    payment_amount = amount or order.grand_total
    
    # Create payment transaction record
    transaction = frappe.new_doc("Payment Transaction")
    transaction.tenant = tenant
    transaction.reference_doctype = "Butchery Order"
    transaction.reference_name = order_id
    transaction.payment_gateway = payment_method
    transaction.amount = payment_amount
    transaction.currency = frappe.get_value("Company", {"is_default": 1}, "default_currency") or "ZMW"
    transaction.status = "Initiated"
    transaction.customer_phone = phone or order.customer_phone
    transaction.insert(ignore_permissions=True)
    
    # Call gateway-specific initiation
    try:
        result = call_payment_gateway(
            gateway=gateway,
            action="initiate",
            transaction_id=transaction.name,
            amount=payment_amount,
            phone=phone or order.customer_phone,
            reference=order_id,
            return_url=return_url
        )
        
        # Update transaction with gateway response
        transaction.gateway_reference = result.get("reference")
        transaction.gateway_response = frappe.as_json(result)
        transaction.status = "Pending"
        transaction.save(ignore_permissions=True)
        
        return {
            "success": True,
            "transaction_id": transaction.name,
            "gateway_reference": result.get("reference"),
            "redirect_url": result.get("redirect_url"),
            "ussd_code": result.get("ussd_code"),
            "message": result.get("message", _("Payment initiated"))
        }
        
    except Exception as e:
        transaction.status = "Failed"
        transaction.error_message = str(e)
        transaction.save(ignore_permissions=True)
        
        frappe.log_error(f"Payment initiation failed: {e}", "Payment Error")
        frappe.throw(_("Payment initiation failed. Please try again."))


@frappe.whitelist(allow_guest=True)
def verify_payment(transaction_id: str):
    """
    Verify payment status
    
    Args:
        transaction_id: Payment Transaction ID
    
    Returns:
        dict: Payment verification result
    """
    tenant = get_tenant_from_request() or get_current_tenant()
    
    transaction = frappe.get_doc("Payment Transaction", transaction_id)
    
    if tenant and transaction.tenant != tenant:
        frappe.throw(_("Transaction not found"), frappe.DoesNotExistError)
    
    # If already completed or failed, return current status
    if transaction.status in ["Completed", "Failed", "Refunded"]:
        return {
            "transaction_id": transaction.name,
            "status": transaction.status,
            "amount": transaction.amount,
            "reference": transaction.reference_name
        }
    
    # Query gateway for status
    gateway = frappe.get_doc("Payment Gateway", transaction.payment_gateway)
    
    try:
        result = call_payment_gateway(
            gateway=gateway,
            action="verify",
            transaction_id=transaction.name,
            gateway_reference=transaction.gateway_reference
        )
        
        if result.get("status") == "success":
            transaction.status = "Completed"
            transaction.completed_at = nowdate() + " " + nowtime()
            transaction.save(ignore_permissions=True)
            
            # Update order payment status
            update_order_payment_status(transaction.reference_name, "Paid")
            
            return {
                "success": True,
                "transaction_id": transaction.name,
                "status": "Completed",
                "message": _("Payment successful")
            }
        
        elif result.get("status") == "failed":
            transaction.status = "Failed"
            transaction.error_message = result.get("message")
            transaction.save(ignore_permissions=True)
            
            return {
                "success": False,
                "transaction_id": transaction.name,
                "status": "Failed",
                "message": result.get("message", _("Payment failed"))
            }
        
        else:
            return {
                "success": None,
                "transaction_id": transaction.name,
                "status": "Pending",
                "message": _("Payment is being processed")
            }
            
    except Exception as e:
        frappe.log_error(f"Payment verification failed: {e}", "Payment Error")
        return {
            "success": None,
            "transaction_id": transaction.name,
            "status": transaction.status,
            "message": _("Could not verify payment status")
        }


@frappe.whitelist()
def payment_callback():
    """
    Handle payment gateway callback/webhook
    
    This endpoint is called by payment gateways to notify of payment status
    """
    data = frappe.request.get_json() or frappe.form_dict
    
    gateway_code = data.get("gateway") or frappe.request.args.get("gateway")
    
    if not gateway_code:
        frappe.throw(_("Gateway not specified"))
    
    gateway = frappe.get_doc("Payment Gateway", gateway_code)
    
    try:
        # Verify callback authenticity
        if not verify_callback_signature(gateway, data):
            frappe.throw(_("Invalid callback signature"))
        
        # Process callback
        result = call_payment_gateway(
            gateway=gateway,
            action="callback",
            data=data
        )
        
        if result.get("transaction_id"):
            transaction = frappe.get_doc("Payment Transaction", result["transaction_id"])
            
            if result.get("status") == "success":
                transaction.status = "Completed"
                transaction.completed_at = nowdate() + " " + nowtime()
                update_order_payment_status(transaction.reference_name, "Paid")
            elif result.get("status") == "failed":
                transaction.status = "Failed"
                transaction.error_message = result.get("message")
            
            transaction.callback_data = frappe.as_json(data)
            transaction.save(ignore_permissions=True)
            frappe.db.commit()
        
        return {"status": "ok"}
        
    except Exception as e:
        frappe.log_error(f"Payment callback error: {e}\nData: {data}", "Payment Callback Error")
        return {"status": "error", "message": str(e)}


def call_payment_gateway(gateway, action: str, **kwargs):
    """
    Call payment gateway handler
    
    Args:
        gateway: Payment Gateway doc
        action: "initiate", "verify", or "callback"
        **kwargs: Additional parameters
    
    Returns:
        dict: Gateway response
    """
    handler_path = gateway.handler_module
    
    if not handler_path:
        frappe.throw(_("Payment gateway handler not configured"))
    
    try:
        handler = frappe.get_attr(handler_path)
        
        if action == "initiate":
            return handler.initiate_payment(gateway, **kwargs)
        elif action == "verify":
            return handler.verify_payment(gateway, **kwargs)
        elif action == "callback":
            return handler.process_callback(gateway, **kwargs)
        else:
            frappe.throw(_("Invalid payment action"))
            
    except AttributeError:
        frappe.throw(_("Payment gateway handler not found"))


def verify_callback_signature(gateway, data) -> bool:
    """Verify callback authenticity using gateway-specific method"""
    handler_path = gateway.handler_module
    
    if not handler_path:
        return False
    
    try:
        handler = frappe.get_attr(handler_path)
        return handler.verify_signature(gateway, data)
    except:
        return False


def update_order_payment_status(order_id: str, status: str):
    """Update order payment status after successful payment"""
    frappe.db.set_value("Butchery Order", order_id, "payment_status", status)
    
    # If paid, confirm the order
    if status == "Paid":
        order = frappe.get_doc("Butchery Order", order_id)
        if order.status == "Pending":
            order.status = "Confirmed"
            order.save(ignore_permissions=True)


# ============================================================
# Payment Gateway Handlers
# These would typically be in separate files per gateway
# ============================================================

class BasePaymentHandler:
    """Base class for payment gateway handlers"""
    
    @staticmethod
    def initiate_payment(gateway, **kwargs):
        raise NotImplementedError
    
    @staticmethod
    def verify_payment(gateway, **kwargs):
        raise NotImplementedError
    
    @staticmethod
    def process_callback(gateway, **kwargs):
        raise NotImplementedError
    
    @staticmethod
    def verify_signature(gateway, data):
        return True


# ============================================================
# Cash on Delivery Handler
# ============================================================

class CashOnDeliveryHandler(BasePaymentHandler):
    """Handler for cash on delivery payments"""
    
    @staticmethod
    def initiate_payment(gateway, **kwargs):
        return {
            "status": "pending",
            "reference": kwargs.get("transaction_id"),
            "message": "Pay cash on delivery/pickup"
        }
    
    @staticmethod
    def verify_payment(gateway, **kwargs):
        return {"status": "pending"}
    
    @staticmethod
    def process_callback(gateway, **kwargs):
        return {}


# Register handlers
PAYMENT_HANDLERS = {
    "cash_on_delivery": "infinit_butchery.api.payments.CashOnDeliveryHandler"
}
