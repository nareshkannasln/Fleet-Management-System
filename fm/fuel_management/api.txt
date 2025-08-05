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

    last_wallet_id = frappe.db.get_value("Transport Company", {}, "wallet_id", order_by="creation desc")
    if last_wallet_id and last_wallet_id.startswith("FLID"):
        last_number = int(last_wallet_id[4:])
        new_number = last_number + 1
    else:
        new_number = 1
    wallet_id = f"FLID{new_number:04d}"  

    company = frappe.new_doc("Transport Company")
    company.name1 = name1
    company.email = email
    company.phone = phone
    company.user = email
    company.wallet_id = wallet_id  
    
    


    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        generate_keys(user.name)
    finally:
        frappe.set_user(original_user)

    api_key = frappe.db.get_value("User", user.name, "api_key")
    api_secret = get_decrypted_password("User", user.name, "api_secret")
    company.api_key = api_key
    company.api_secret = api_secret

    company.insert(ignore_permissions=True)

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


# @frappe.whitelist()
# def create_fleet_card(company_id, vehicle_no, card_list=None, pin_list=None):
#     if not isinstance(vehicle_no, list):
#         frappe.throw("vehicle_no must be a list")

#     transport_company = frappe.db.get_value(
#         "Transport Company",
#         {"name": company_id},
#         ["name"],
#         as_dict=True
#     )
#     if not transport_company:
#         frappe.throw("Invalid company_id: No such Transport Company found")

#     doc = frappe.new_doc("Fleet Card")
#     doc.transport_company = transport_company.name
#     for idx, vehicle_no in enumerate(vehicle_no):
#         card_no = (card_list[idx] if card_list and idx < len(card_list)
#                    else str(random.randint(10**15, 10**16 - 1)))
#         pin = (pin_list[idx] if pin_list and idx < len(pin_list)
#                else str(random.randint(1000, 9999)))

#         doc.append("card_details", {
#             "vehicle_no": vehicle_no,
#             "card_no": card_no,
#             "pin": pin
#         })

#     doc.insert(ignore_permissions=True)


#     return {
#         "status": "success",
#         "fleet_card_id": doc.name,
#         "transport_company": transport_company.name,
#         "card_details": [
#             {
#                 "vehicle_no": row.vehicle_no,
#                 "card_no": row.card_no,
#                 "pin": row.pin
#             }
#             for row in doc.card_details
#         ]
#     }

    

@frappe.whitelist(allow_guest=False)
def change_card_pin(card_no, old_pin, new_pin):
    card_row = frappe.db.get_all(
        "Card Details",
        filters={
            "card_no": card_no,
            "pin": old_pin,
            "parenttype": "Fleet Card",
        },
        fields=["name", "parent"]
    )
    print(f"Card Row: {card_row}")  # Debugging line

    for row in card_row:
        # 2. Get the parent Fleet Card to find company
        fleet_card_info = frappe.db.get_value(
            "Fleet Card", 
            {"name": row["parent"]}, 
            ["transport_company"], 
            as_dict=True
        )
        if fleet_card_info:
            # 3. (Optional) Check any business rule for company_id here;
            # Or just proceed with the update, as card_no is unique
            frappe.db.set_value("Card Details", row["name"], "pin", new_pin)
            return {
                "status": "success",
                "message": "PIN changed successfully",
                "company_id": fleet_card_info["transport_company"]
            }

    # No matching card found
    return {
        "status": "failed",
        "message": "Invalid card number or old PIN"
    }

@frappe.whitelist()
def create_fleet_card(vehicle_no, card_list=None, pin_list=None):
    current_user_email = frappe.session.user

    company_name = frappe.db.get_value("Transport Company", {"user": current_user_email}, "name")
    if not company_name:
        frappe.throw("Unauthorized: No Transport Company linked to this user.")

    # Create the Fleet Card for this company
    doc = frappe.new_doc("Fleet Card")
    doc.transport_company = company_name  
    
    idx = 0
    for vno in vehicle_no:
        card_no = (card_list[idx] if card_list and idx < len(card_list)
                else str(random.randint(10**15, 10**16 - 1)))
        pin = (pin_list[idx] if pin_list and idx < len(pin_list)
            else str(random.randint(1000, 9999)))
        doc.append("card_details", {
            "vehicle_no": vno,
            "card_no": card_no,
            "pin": pin
        })
        idx += 1


    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "fleet_card_id": doc.name,
        "company_id": company_name,
        "card_details": [
            {
                "vehicle_no": row.vehicle_no,
                "card_no": row.card_no,
                "pin": row.pin
            }
            for row in doc.card_details
        ]
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
