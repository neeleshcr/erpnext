# Copyright (c) 2022, VPS Consultancy and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	st = filters.get("from_date")
	ed = filters.get("to_date")

	data = frappe.db.sql(f""" select 
							sei.item_code,
							sei.item_name,
							sei.qty,
							sei.uom,
                         	ite.weight_per_unit * sei.qty as uomqty,
							ip.price_list_rate as rate,
							ip.price_list_rate * sei.qty as net_total,
							se.name as parent,
							se.stock_entry_type,
							se.posting_date,
							se.issued_to
							
							from 
							`tabStock Entry Detail` sei

							left join `tabItem` ite on sei.item_code = ite.item_code
							left join `tabStock Entry` se on se.name = sei.parent
                        	left join `tabItem Price` ip on ip.price_list = 'Banglore Local Distributors' and ip.item_code = sei.item_code 
							
							where se.stock_entry_type = 'Sample Issue' and se.posting_date between '{st}' and '{ed}'	
							group by se.name,sei.item_code

							
								""",as_dict=1)
	columns =  [
		{
			"fieldname": "parent",
			"label": "<b>Doc Name</b>",
			"fieldtype": "Link",
			"options":"Stock Entry",
			"width":  170
		},
		{
			"fieldname": "posting_date",
			"label": "<b>Date</b>",
			"fieldtype": "Data",
			"width":  150
		},
		{
			"fieldname": "issued_to",
			"label": "<b>Issued to</b>",
			"fieldtype": "Data",
			"width":  170
		},
		{
			"fieldname": "item_code",
			"label": "<b>Item Code</b>",
			"fieldtype": "Link",
			"options":"Item",
			"width":  150
		},
		{
			"fieldname": "item_name",
			"label": "<b>Item Name</b>",
			"fieldtype": "Data",
			"width":  200
		},
		{
			"fieldname": "qty",
			"label": "<b>Qty</b>",
			"fieldtype": "Data",
			"width":  130
		},
		{
			"fieldname": "uom",
			"label": "<b>UOM</b>",
			"fieldtype": "Data",
			"width":  130
		},
		{
			"fieldname": "uomqty",
			"label": "<b>Weight uom x qty</b>",
			"fieldtype": "Data",
			"width":  130
		},
		{
			"fieldname": "rate",
			"label": "<b>Bangalore Local Price list</b>",
			"fieldtype": "Data",
			"width":  130
		},
		{
			"fieldname": "net_total",
			"label": "<b>Net Total</b>",
			"fieldtype": "Data",
			"width":  130
		}		
	]
	return columns, data
