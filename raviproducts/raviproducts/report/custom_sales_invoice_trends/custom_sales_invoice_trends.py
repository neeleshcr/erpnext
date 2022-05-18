# Copyright (c) 2022, VPS Consultancy and contributors
# For license information, please see license.txt

import frappe

# from erpnext.controllers.trends import 
from raviproducts.custom_trend import get_data,get_columns

def execute(filters=None):
	if not filters:
		filters = {}
	data = []
	conditions = get_columns(filters, "Sales Invoice")
	data = get_data(filters, conditions)

	return conditions["columns"], data
