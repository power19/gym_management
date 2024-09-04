# gym_management/gym_management/doctype/gym_membership/gym_membership.py

import frappe
from frappe.model.document import Document
from frappe.utils import add_months, getdate, nowdate, add_days
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_invoice

class GymMembership(Document):
    def validate(self):
        self.validate_dates()
        self.set_expiry_date()

    def validate_dates(self):
        if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
            frappe.throw("End Date cannot be before Start Date")

    def set_expiry_date(self):
        if self.start_date and self.membership_type:
            membership_type = frappe.get_doc("Gym Membership Type", self.membership_type)
            self.end_date = add_months(getdate(self.start_date), membership_type.duration)

    def on_update(self):
        self.update_customer_group()
        self.create_invoice()

    def update_customer_group(self):
        if self.member:
            frappe.db.set_value("Customer", self.member, "customer_group", "Gym Member")

    def create_invoice(self):
        if self.docstatus == 1 and not self.invoice:
            membership_type = frappe.get_doc("Gym Membership Type", self.membership_type)
            invoice = make_sales_invoice(
                customer=self.member,
                item_code=membership_type.item,
                qty=1,
                rate=membership_type.price,
                posting_date=self.start_date
            )
            invoice.insert(ignore_permissions=True)
            invoice.submit()
            self.db_set('invoice', invoice.name)

def send_expiry_notifications():
    # Get memberships expiring in the next 7 days
    expiring_memberships = frappe.get_all(
        "Gym Membership",
        filters={
            "end_date": ["between", (nowdate(), add_days(nowdate(), 7))],
            "status": "Active"
        },
        fields=["name", "member", "end_date"]
    )

    for membership in expiring_memberships:
        member = frappe.get_doc("Customer", membership.member)
        frappe.sendmail(
            recipients=[member.email],
            subject=f"Your Gym Membership is Expiring Soon",
            message=f"""
            Dear {member.customer_name},

            Your gym membership (ID: {membership.name}) is set to expire on {membership.end_date}.
            Please renew your membership to continue enjoying our facilities.

            Best regards,
            Your Gym Team
            """
        )

# In gym_management/gym_management/doctype/gym_membership_type/gym_membership_type.py

from frappe.model.document import Document

class GymMembershipType(Document):
    def validate(self):
        self.create_item()

    def create_item(self):
        if not self.item:
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": f"GYM-{self.membership_type}",
                "item_name": f"Gym Membership - {self.membership_type}",
                "item_group": "Services",
                "is_stock_item": 0,
                "include_item_in_manufacturing": 0,
                "is_sales_item": 1
            })
            item.insert(ignore_permissions=True)
            self.item = item.name
