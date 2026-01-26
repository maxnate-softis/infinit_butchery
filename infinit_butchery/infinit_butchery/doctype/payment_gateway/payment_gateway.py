"""
Payment Gateway DocType
"""

import frappe
from frappe import _
from frappe.model.document import Document


class PaymentGateway(Document):
    def before_save(self):
        # Generate webhook URL
        site_url = frappe.utils.get_url()
        self.webhook_url = f"{site_url}/api/method/infinit_butchery.api.payments.payment_callback?gateway={self.gateway_code}"
        
        # Normalize gateway code
        if self.gateway_code:
            self.gateway_code = self.gateway_code.lower().replace(" ", "_")
    
    def validate(self):
        # Ensure handler module exists
        if self.handler_module:
            try:
                frappe.get_attr(self.handler_module)
            except AttributeError:
                frappe.msgprint(
                    _("Handler module '{0}' not found. Make sure it exists.").format(self.handler_module),
                    indicator="orange"
                )
    
    def get_api_url(self) -> str:
        """Get the appropriate API URL based on sandbox mode"""
        if self.sandbox_mode:
            return self.sandbox_url or self.api_base_url
        return self.production_url or self.api_base_url
    
    def get_credentials(self) -> dict:
        """Get gateway credentials for API calls"""
        return {
            "api_key": self.get_password("api_key"),
            "api_secret": self.get_password("api_secret"),
            "oauth_client_id": self.oauth_client_id,
            "oauth_client_secret": self.get_password("oauth_client_secret"),
            "oauth_token_url": self.oauth_token_url,
            "webhook_secret": self.get_password("webhook_secret")
        }


@frappe.whitelist()
def get_active_gateways() -> list:
    """Get all active payment gateways"""
    return frappe.get_all(
        "Payment Gateway",
        filters={"is_active": 1},
        fields=["name", "gateway_name", "gateway_code", "gateway_type", "logo"]
    )
