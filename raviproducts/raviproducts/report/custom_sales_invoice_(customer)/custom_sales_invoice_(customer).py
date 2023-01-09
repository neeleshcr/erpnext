# Copyright (c) 2022, VPS Consultancy and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

def execute(filters=None):
	dd = get_period_date_ranges_columns(filters.get("period"),filters.get("fiscal_year"))
	fiscal = frappe.get_doc("Fiscal Year",filters.get("fiscal_year"))
	
	value = ""
	if filters.get("value_quantity") == "QuantityWscheme":
		value = "and  sii.item_code NOT LIKE '%Scheme%'"
		

	data = frappe.db.sql(f""" SELECT 
							sii.item_code, 
							sii.item_name,
							sum(sii.stock_qty) as qty, 
							Sum(sii.stock_qty * sii.weight_per_unit) AS weight_per_unit, 
							si.customer as customer,
							si.customer_group as customer_group,

							{dd[1]}



							DATE_FORMAT(si.posting_date, '%Y-%m') as dd 
			

							FROM 
							`tabSales Invoice Item` sii 
							LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name 
							LEFT JOIN `tabSales Invoice Item` sjun ON sii.name = sjun.name 
							and si.posting_date between '2022-06-01' 
							and '2022-06-30' 

							{dd[2]}


							WHERE 
							si.docstatus = 1 and 
							si.company = '{filters.get("company")}' and 
							si.posting_date between '{fiscal.year_start_date}' 
							and '{fiscal.year_end_date}'  {value} 
							GROUP BY 
							si.customer, 
							sii.item_code 
							ORDER BY 
							si.customer ASC;
							""",as_dict=1)
	columns=[
		{
			"fieldname": "customer",
			"label": "<b>Customer</b>",
			"fieldtype": "Data",
			"width":  200
		},
		{
			"fieldname": "customer_group",
			"label": "<b>Customer Group</b>",
			"fieldtype": "Data",
			"width":  200
		},
		{
			"fieldname": "item_code",
			"label": "<b>Item Code</b>",
			"fieldtype": "Data",
			"width":  130
		},
		{
			"fieldname": "item_name",
			"label": "<b>Item Name</b>",
			"fieldtype": "Data",
			"width":  130
		},	

	]
	for i in dd[0]:
		columns.append(i)
	# columns.append(		
	# 		{
	# 			"fieldname": "qty",
	# 			"label": "<b>Total</b>",
	# 			"fieldtype": "Float",
	# 			"width":  150
	# 		}
	# 	)
	columns.append(
			{
				"fieldname": "weight_per_unit",
				"label": "<b>Total UOM</b>",
				"fieldtype": "Float",
				"default" :0.00,
				"width":  150
			})

	return columns, data



@frappe.whitelist(allow_guest=True)
def get_period_date_ranges_columns(period, fiscal_year=None, year_start_date=None):
	from dateutil.relativedelta import relativedelta

	if not year_start_date:
		year_start_date, year_end_date = frappe.db.get_value(
			"Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"]
		)

	increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(period)

	period_date_ranges = []
	query = ''
	row = ''
	colm = []
	for i in range(1, 13, increment):
		period_end_date = getdate(year_start_date) + relativedelta(months=increment, days=-1)
		if period_end_date > getdate(year_end_date):
			period_end_date = year_end_date
		period_date_ranges.append([year_start_date, period_end_date])
		start = getdate(year_start_date).strftime("%b%y") 
		end   = getdate(period_end_date).strftime("%b%y")

		# row += f'''
		# 							sum({start}.qty) as  {start}, 
		# 				Sum({start}.qty * {start}.weight_per_unit) AS {start}UOM,			
		# 		''' 
		row += f'''
				Sum({start}.stock_qty * {start}.weight_per_unit) AS {start}UOM,
				''' 
		# colm.append(
		# 			{'fieldname': f'{start}','label': f'{start} (Qty)','fieldtype': 'Float','default' :0.00,'width':  150}
		# 		)
		colm.append(
					{'fieldname': f'{start}UOM','label': f'{start} (UOM)','fieldtype': 'Float','default' :0.00,'width':  150}
				)


		query += f""" \n
				LEFT JOIN `tabSales Invoice Item` {start} ON sii.name = {start}.name 
				and si.posting_date between '{year_start_date}' 
				and '{period_end_date}' 
				   """

		year_start_date = period_end_date + relativedelta(days=1)
		if period_end_date == year_end_date:
			break
	return [colm,row,query]
