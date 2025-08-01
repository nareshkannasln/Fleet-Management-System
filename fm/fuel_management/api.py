import frappe
import random
from frappe.utils.password import check_password
from frappe.utils.password import get_decrypted_password
from frappe.core.doctype.user.user import generate_keys

@frappe.whitelist(allow_guest=True)
def onboard_transport_company(name1, email, phone):
    if frappe.db.exists("User", {"email": email}):
        return {
            "status": "exists",
            "message": "User already exists",
            "user_email": email
        }

    user = frappe.new_doc("User")
    user.update({
        "email": email,
        "send_welcome_email": 0,
        "first_name": name1,
        "mobile_no": phone
    })
    user.append("roles", {"role": "Transport Company User"})
    user.insert(ignore_permissions=True)

        # Auto-generate wallet_id (e.g., FLID0001)
    last_wallet_id = frappe.db.get_value("Transport Company", {}, "wallet_id", order_by="creation desc")
    if last_wallet_id and last_wallet_id.startswith("FLID"):
        last_number = int(last_wallet_id[4:])
        new_number = last_number + 1
    else:
        new_number = 1
    wallet_id = f"FLID{new_number:04d}"  # FLID0001, FLID0002, etc.

    company = frappe.new_doc("Transport Company")
    company.name1 = name1
    company.email = email
    company.phone = phone
    company.user = email
    company.wallet_id = wallet_id  # Set the generated wallet ID
    company.insert(ignore_permissions=True)


    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        generate_keys(user.name)
    finally:
        frappe.set_user(original_user)

    api_key = frappe.db.get_value("User", user.name, "api_key")
    api_secret = get_decrypted_password("User", user.name, "api_secret")

    return {
        "status": "success",
        "message": "User and Transport Company created",
        "name1": name1,
        "email": email,
        "phone": phone,
        "company_id": company.name,
        "api_key": api_key,
        "api_secret": api_secret,
        "wallet_id": company.wallet_id
    }


@frappe.whitelist(allow_guest=False)
def create_fleet_card(company_id, vehicle_no, card=None, pin=None):

    transport_company = frappe.db.get_value(
        "Transport Company",
        {"name": company_id},
        ["name"],
        as_dict=True
    )
    if not transport_company:
        frappe.throw("Invalid company_id: No such Transport Company found")

    doc = frappe.new_doc("Fleet Card")
    doc.transport_company = transport_company.name

    card_no = card or str(random.randint(10**15, 10**16 - 1))
    pin = pin or str(random.randint(1000, 9999))

    doc.append("card_details", {
        "vehicle_no": vehicle_no,
        "card_no": card_no,
        "pin": pin
    })

    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "fleet_card_id": doc.name,
        "transport_company": transport_company.name,
        "vehicle_no": vehicle_no,
        "card_no": card_no,
        "pin": pin
    }




@frappe.whitelist(allow_guest=False)
def change_card_pin(card_no, new_pin):
    if not card_no or not new_pin:
        frappe.throw("card_no and new_pin are required")

    auth_header = frappe.get_request_header("Authorization")
    if not auth_header or not auth_header.startswith("Token "):
        frappe.throw("Missing or invalid Authorization header")

    try:
        token = auth_header.split("Token ")[1]
        api_key, api_secret = token.split(":")
    except Exception:
        frappe.throw("Invalid Authorization token format")

    # Validate credentials and get transport company
    bpcl = frappe.db.get_value("BPCL", {
        "api_key": api_key,
        "api_secret": api_secret
    }, "transport_company")

    if not bpcl:
        frappe.throw("Unauthorized: Invalid API credentials")

    # Find the correct Fleet Card Doc
    card_doc = frappe.get_all("Fleet Card", filters={"transport_company": bpcl}, fields=["name"])

    if not card_doc:
        frappe.throw("No Fleet Card found for this transport company")

    # Find card in child table
    found = False
    for fc in card_doc:
        doc = frappe.get_doc("Fleet Card", fc.name)
        for row in doc.card_details:
            if row.card_no == card_no:
                row.pin = new_pin
                doc.save(ignore_permissions=True)
                found = True
                break
        if found:
            break

    if not found:
        frappe.throw("Card not found under this transport company")

    return {
        "status": "success",
        "message": f"PIN updated for card {card_no}"
    }



# @frappe.whitelist(allow_guest=False)
# def make_transaction(card_number, pin, amount):
#     card = frappe.get_all("Fleet Card Detail", filters={"card_no": card_number, "pin": pin}, fields=["parent"])
#     if not card:
#         return {
#             "status": "failed",
#             "message": "Invalid card number or PIN"
#         }

#     wallet = frappe.get_doc("Wallet", {"card_number": card_number})
#     if wallet.balance < float(amount):
#         return {
#             "status": "failed",
#             "message": "Insufficient balance"
#         }

#     wallet.balance -= float(amount)
#     wallet.save(ignore_permissions=True)

#     return {
#         "status": "success",
#         "message": "Transaction successful",
#         "remaining_balance": wallet.balance
#     }

# @frappe.whitelist(allow_guest=False)
# def get_card_details(transport_company):
#     fleet_cards = frappe.get_all("Fleet Card", filters={"transport_company": transport_company}, fields=["name"])

#     results = []
#     for fc in fleet_cards:
#         doc = frappe.get_doc("Fleet Card", fc.name)
#         for d in doc.card_details:
#             wallet = frappe.db.get_value("Wallet", {"card_number": d.card_no}, "balance")
#             results.append({
#                 "vehicle_no": d.vehicle_no,
#                 "card_no": d.card_no,
#                 "balance": wallet or 0
#             })

#     return {
#         "cards": results
#     }
