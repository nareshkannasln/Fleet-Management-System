import frappe
from frappe.utils import validate_email_address
from frappe.utils.password import update_password
import random



@frappe.whitelist(allow_guest=True)
def onboard_transport_company(company_name, email, phone):
    validate_email_address(email.strip(), throw=True)

    if frappe.db.exists("User", {"email": email}):
        return {
            "status": "exists",
            "message": "User already exists",
            "user_email": email
        }

    default_password = frappe.generate_hash(length=8)

    user = frappe.new_doc("User")
    user.update({
        "email": email,
        "send_welcome_email": 0,
        "first_name": company_name,
        "mobile_no": phone
    })
    user.append("roles", {"role": "Transport Company User"})
    user.insert(ignore_permissions=True)

    update_password(user.name, default_password)

    last_wallet_id = frappe.db.get_value(
        "Transport Company", {}, "wallet_id", order_by="creation desc"
    )
    if last_wallet_id and last_wallet_id.startswith("FLID"):
        new_number = int(last_wallet_id[4:]) + 1
    else:
        new_number = 1
    wallet_id = f"FLID{new_number:04d}"

    company = frappe.new_doc("Transport Company")
    company.update({
        "company_name": company_name,  # changed from name1
        "email": email,
        "phone": phone,
        "user": email,
        "wallet_id": wallet_id,
        "password": default_password
    })
    company.insert(ignore_permissions=True)

    return {
        "status": "success",
        "message": "Transport Company and User created",
        "company_name": company_name,  # updated key
        "email": email,
        "phone": phone,
        "wallet_id": wallet_id,
        "company_id": company.name,
        "password": default_password
    }





@frappe.whitelist()
def create_fleet_card(company_id, vehicle_list, card_list=None, pin_list=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in to perform this action."))

    if not isinstance(vehicle_list, list):
        frappe.throw(_("vehicle_list must be a list."))

    transport_company = frappe.db.get_value(
        "Transport Company",
        {"name": company_id},
        "name" 
    )

    if not transport_company:
        frappe.throw(_("Invalid company_id: No such Transport Company found."))

    doc = frappe.new_doc("Fleet Card")
    doc.transport_company = transport_company

    for i, vehicle_no in enumerate(vehicle_list):
        card_no = (
            card_list[i] if card_list and i < len(card_list)
            else str(random.randint(10**15, 10**16 - 1))
        )
        pin = (
            pin_list[i] if pin_list and i < len(pin_list)
            else str(random.randint(1000, 9999))
        )

        doc.append("card_details", {
            "vehicle_no": vehicle_no,
            "card_no": card_no,
            "pin": pin
        })

    doc.insert()

    return {
        "status": "success",
        "fleet_card_id": doc.name,
        "transport_company": transport_company,
        "card_details": [
            {
                "vehicle_no": row.vehicle_no,
                "card_no": row.card_no,
                "pin": row.pin
            } for row in doc.card_details
        ]
    }


@frappe.whitelist()
def change_fleet_card_pin(card_no, old_pin, new_pin):
    if frappe.session.user == "Guest":
        frappe.throw("You must be logged in to perform this action.")

    if not card_no or not old_pin or not new_pin:
        frappe.throw("card_no, old_pin, and new_pin are all required.")

    # Fetch the Fleet Card Detail with the provided card number
    card = frappe.get_all("Fleet Card Detail", filters={"card_no": card_no}, fields=["name", "parent", "pin"])
    if not card:
        frappe.throw("Invalid card number.")

    # Verify old PIN
    if card[0].pin != old_pin:
        frappe.throw("Old PIN is incorrect.")

    # Update new PIN
    card_doc = frappe.get_doc("Fleet Card", card[0].parent)
    for row in card_doc.card_details:
        if row.card_no == card_no:
            row.pin = new_pin
            break

    card_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": "PIN changed successfully",  
        "card_no": card_no
    }
