import frappe
from frappe.utils.password import get_decrypted_password
from frappe.core.doctype.user.user import generate_keys
import random


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
    user.save()   

    company = frappe.new_doc("Transport Company")
    company.name1 = name1
    company.email = email
    company.phone = phone
    company.user = email  
    company.insert(ignore_permissions=True)
    company.save()        
    try:
        company.save()
        print("Transport Company created successfully")  
    except Exception as e:
        frappe.log_error(str(e), "Transport Company Submit Failed")

    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        generate_keys(user.name)
    finally:
        frappe.set_user(original_user)

    api_key = frappe.db.get_value("User", user.name, "api_key")
    api_secret = get_decrypted_password("User", user.name, "api_secret")
    print(f"API Key: {api_key}, API Secret: {api_secret}, User: {user.name}")

    return {
        "status": "success",
        "message": "User and Transport Company created with API credentials",
        "name1": name1,
        "email": email,
        "phone": phone,
        "transport_company_id": company.name,
        "api_key": api_key,
        "api_secret": api_secret
    }
    


@frappe.whitelist(allow_guest=True)
def create_fleet_card(transport_company, vehicles):
    if not frappe.db.exists("Transport Company", transport_company):
        frappe.throw(f"Transport Company '{transport_company}' not found. Please onboard first.")

    if not isinstance(vehicles, list):
        frappe.throw("Vehicles must be a list of strings")

    doc = frappe.new_doc("Fleet Card")
    doc.transport_company = transport_company

    cards_info = []

    for vehicle in vehicles:
        card_no = str(random.randint(10**15, 10**16 - 1))  
        pin = str(random.randint(1000, 9999))  
        print(f"Creating card for vehicle {vehicle}: Card No: {card_no}, PIN: {pin}")

        doc.append("card_details", {
            "vehicle_no": vehicle,
            "card_no": card_no,
            "pin": pin
        })

        cards_info.append({
            "vehicle_no": vehicle,
            "card_no": card_no,
            "pin": pin
        })

    doc.insert(ignore_permissions=True)
    doc.submit()

    return {
        "status": "success",
        "fleet_card_id": doc.name,
        "cards": cards_info
    }