# Copyright (c) 2025, nareshkanna and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FleetCard(Document):
	def autoname(self):
		self.name = self.card_details[0].vehicle_no