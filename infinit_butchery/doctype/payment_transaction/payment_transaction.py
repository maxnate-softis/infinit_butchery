"""
Payment Transaction DocType
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now


class PaymentTransaction(Document):
    def before_insert(self):
        self.initiated_at = now()
    
    def validate(self):
        # Validate refund amount
        if self.refund_amount and self.refund_amount > self.amount:
            frappe.throw(_("Refund amount cannot be greater than transaction amount"))
    
    def on_update(self):
        # Update reference document payment status
        if self.reference_doctype and self.reference_name:
            if self.has_value_changed("status"):
                self.update_reference_status()
    
    def update_reference_status(self):
        """Update payment status on the reference document"""
        if self.status == "Completed":
            payment_status = "Paid"
        elif self.status == "Refunded":
            payment_status = "Refunded"
        elif self.status == "Failed":
            payment_status = "Failed"
        else:
            return
        
        try:
            # Try to update payment_status field on reference doc
            frappe.db.set_value(
                self.reference_doctype,
                self.reference_name,
                "payment_status",
                payment_status,
                update_modified=False
            )
        except Exception:
            # Reference doc might not have payment_status field
            pass


@frappe.whitelist()
def get_transaction_status(transaction_id: str) -> dict:
    """
    Get transaction status
    
    Args:
        transaction_id: Payment Transaction name
    
    Returns:
        dict: Transaction status info
    """
    transaction = frappe.get_doc("Payment Transaction", transaction_id)
    
    return {
        "transaction_id": transaction.name,
        "status": transaction.status,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "gateway": transaction.payment_gateway,
        "gateway_reference": transaction.gateway_reference,
        "reference": transaction.reference_name,
        "initiated_at": transaction.initiated_at,
        "completed_at": transaction.completed_at
    }


@frappe.whitelist()
def get_transactions_by_reference(doctype: str, docname: str) -> list:
    """
    Get all transactions for a reference document
    
    Args:
        doctype: Reference DocType
        docname: Reference document name
    
    Returns:
        list: List of transactions
    """
    return frappe.get_all(
        "Payment Transaction",
        filters={
            "reference_doctype": doctype,
            "reference_name": docname
        },
        fields=["name", "status", "amount", "payment_gateway",
                "gateway_reference", "initiated_at", "completed_at"],
        order_by="creation desc"
    )


@frappe.whitelist()
def initiate_refund(transaction_id: str, amount: float = None, reason: str = None) -> dict:
    """
    Initiate a refund for a completed transaction
    
    Args:
        transaction_id: Payment Transaction name
        amount: Refund amount (default: full amount)
        reason: Refund reason
    
    Returns:
        dict: Refund result
    """
    transaction = frappe.get_doc("Payment Transaction", transaction_id)
    
    if transaction.status != "Completed":
        frappe.throw(_("Can only refund completed transactions"))
    
    refund_amount = amount or transaction.amount
    
    if refund_amount > transaction.amount:
        frappe.throw(_("Refund amount cannot exceed transaction amount"))
    
    # Check if gateway supports refund
    gateway = frappe.get_doc("Payment Gateway", transaction.payment_gateway)
    if not gateway.supports_refund:
        frappe.throw(_("This payment gateway does not support refunds"))
    
    # Call gateway refund handler
    try:
        handler = frappe.get_attr(gateway.handler_module)
        result = handler.process_refund(gateway, {
            "transaction_id": transaction.name,
            "gateway_reference": transaction.gateway_reference,
            "amount": refund_amount,
            "reason": reason
        })
        
        if result.get("success"):
            transaction.status = "Refunded"
            transaction.refund_amount = refund_amount
            transaction.refunded_at = now()
            transaction.save(ignore_permissions=True)
            
            return {
                "success": True,
                "transaction_id": transaction.name,
                "refund_amount": refund_amount,
                "message": _("Refund processed successfully")
            }
        else:
            return {
                "success": False,
                "message": result.get("message", _("Refund failed"))
            }
            
    except Exception as e:
        frappe.log_error(f"Refund failed: {e}", "Refund Error")
        return {
            "success": False,
            "message": str(e)
        }
