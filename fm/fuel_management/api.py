import frappe
from frappe import _
from frappe.utils import validate_email_address
from frappe.utils.password import update_password
from fm.fuel_management.utils import (
    create_wallet_account,
    is_valid_vehicle_no,
    generate_card_no,
    generate_pin
)

@frappe.whitelist(allow_guest=True)
def onboard_transport_company(company_name, email, phone):
    try:
        validate_email_address(email.strip(), throw=True)

        if frappe.db.exists("User", {"email": email}):
            return {
                "status": "fail",
                "message": "User already exists"
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
        new_number = int(last_wallet_id[4:]) + 1 if last_wallet_id and last_wallet_id.startswith("FLID") else 1
        wallet_id = f"FLID{new_number:04d}"

        company = frappe.new_doc("Transport Company")
        company.update({
            "company_name": company_name,
            "email": email,
            "phone": phone,
            "user": email,
            "wallet_id": wallet_id,
            "password": default_password  # Remove or mask if needed in production
        })
        company.insert(ignore_permissions=True)

        wallet_account_name = create_wallet_account(
            erp_company="Bharat Petroleum Corporation Ltd",
            company_name=company_name,
            wallet_id=wallet_id
        )
        frappe.db.set_value("Transport Company", company.name, "erp_account", wallet_account_name)

        return {
            "status": "success",
            "message": "Transport Company and User created",
            "data": {
                "company_id": company.name,
                "wallet_id": wallet_id,
                "user_email": email,
                "password": default_password
            }
        }
    except frappe.ValidationError as ve:
        return {"status": "fail", "message": str(ve)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Onboard Transport Company Error")
        return {"status": "error", "message": _("Something went wrong. Please try again later.")}


@frappe.whitelist()
def create_fleet_card(company_id, vehicle_list, card_list=None, pin_list=None):
    try:
        if frappe.session.user == "Guest":
            return {"status": "fail", "message": _("Login required.")}
        
        if not isinstance(vehicle_list, list) or not vehicle_list:
            return {"status": "fail", "message": _("vehicle_list must be a non-empty list.")}

        transport_company = frappe.db.get_value("Transport Company", {"name": company_id}, "name")
        if not transport_company:
            return {"status": "fail", "message": _("Invalid company_id.")}

        invalid_vehicles, duplicate_vehicles = [], []
        fleet_cards = frappe.db.get_all("Fleet Card", filters={"transport_company": company_id}, pluck="name")

        for v in vehicle_list:
            if not is_valid_vehicle_no(v):
                invalid_vehicles.append(v)
            elif frappe.db.exists({
                "doctype": "Card Details",
                "vehicle_no": v,
                "parenttype": "Fleet Card",
                "parent": ["in", fleet_cards]
            }):
                duplicate_vehicles.append(v)

        if invalid_vehicles:
            return {"status": "fail", "message": _("Invalid vehicle number(s): ") + ", ".join(invalid_vehicles)}
        
        # if duplicate_vehicles:
        #     return {"status": "fail", "message": _("Vehicle number(s) already assigned for this company: ") + ", ".join(duplicate_vehicles)}

        doc = frappe.new_doc("Fleet Card")
        doc.transport_company = transport_company

        raw_pin_map = {}
        for i, vehicle_no in enumerate(vehicle_list):
            card_no = card_list[i] if card_list and i < len(card_list) else generate_card_no()
            pin = pin_list[i] if pin_list and i < len(pin_list) else generate_pin()
            doc.append("card_details", {
                "vehicle_no": vehicle_no,
                "card_no": card_no,
                "pin": pin  # Storing raw PIN
            })
            raw_pin_map[vehicle_no] = {"card_no": card_no, "pin": pin}

        doc.save(ignore_permissions=True)

        return {
            "status": "success",
            "message": _("Fleet cards created successfully."),
            "data": {
                "fleet_card_id": doc.name,
                "card_details": [
                    {
                        "vehicle_no": row.vehicle_no,
                        "card_no": raw_pin_map[row.vehicle_no]["card_no"],
                        "pin": raw_pin_map[row.vehicle_no]["pin"]
                    } for row in doc.card_details
                ]
            }
        }
    except frappe.ValidationError as ve:
        return {"status": "fail", "message": str(ve)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Fleet Card Error")
        return {"status": "error", "message": _("Something went wrong. Please try again later.")}


@frappe.whitelist()
def change_card_pin(card_no, old_pin, new_pin):
    if frappe.session.user == "Guest":
        return {"status": "fail", "message": _("Login required to change PIN.")}

    if not card_no or not old_pin or not new_pin:
        return {"status": "fail", "message": _("All fields (card_no, old_pin, new_pin) are required.")}

    card = frappe.db.get_value(
        "Card Details",
        {"card_no": card_no.strip()},
        ["name", "parent"],
        as_dict=True
    )

    if not card:
        return {"status": "fail", "message": _("Invalid card number.")}

    stored_pin = frappe.db.get_value("Card Details", card.name, "pin")
    if old_pin != stored_pin:
        return {"status": "fail", "message": _("Incorrect old PIN.")}

    try:
        frappe.db.set_value("Card Details", card.name, "pin", new_pin)  # Storing raw new PIN
        return {"status": "success", "message": _("PIN updated successfully.")}
    except frappe.ValidationError as e:
        return {"status": "fail", "message": str(e)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Change Card PIN Error")
        return {"status": "error", "message": _("Something went wrong. Please try again later.")}
