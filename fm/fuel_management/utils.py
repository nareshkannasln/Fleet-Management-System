import frappe
import re
import random
import string
from frappe import _
def create_wallet_account(*, erp_company, company_name, wallet_id):
    account_name = f"Wallet - {company_name}"

    # Check if account already exists
    if frappe.db.exists("Account", {"account_name": account_name, "company": erp_company}):
        return account_name

    account = frappe.new_doc("Account")
    account.account_name = account_name
    account.parent_account = f"159894594624 - Fleet Wallets - BPCL"  # Uses passed company name
    account.is_group = 0
    account.account_type = "Cash"
    account.company = erp_company
    account.insert(ignore_permissions=True)

    return account.name



def create_fleet_card(*, erp_company, company_name, wallet_id):
    account_name = f"Fleet Card - {company_name}"

    # Check if account already exists
    if frappe.db.exists("Account", {"account_name": account_name, "company": erp_company}):
        return account_name

    account = frappe.new_doc("Account")
    account.account_name = account_name
    account.parent_account = f"159894594624 - Fleet Wallets - BPCL"  # Uses passed company name
    account.is_group = 0
    account.account_type = "Cash"
    account.company = erp_company
    account.insert(ignore_permissions=True)

    return account.name



def is_valid_vehicle_no(vehicle_no):
    pattern = r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$"
    return bool(re.match(pattern, vehicle_no))


def generate_card_no():
    return ''.join(random.choices(string.digits, k=16))


def generate_pin():
    return ''.join(random.choices(string.digits, k=4))