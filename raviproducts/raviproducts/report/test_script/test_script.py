# Copyright (c) 2022, VPS Consultancy and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	dd = get_period_date_ranges_columns(filters.get("period"),filters.get("fiscal_year"))
	fiscal = frappe.get_doc("Fiscal Year",filters.get("fiscal_year"))
	data = frappe.db.sql(f""" SELECT 
							sii.item_code, 
							sii.item_name,
							sum(sii.qty) as qty, 
							Sum(sii.qty * sii.weight_per_unit) AS weight_per_unit, 
							si.customer as customer, 

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
							and '{fiscal.year_end_date}' 
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
			"fieldname": "item_code",
			"label": "<b>Item Code</b>",
			"fieldtype": "Data",
			"width":  130
		},	

	]
	for i in dd[0]:
		columns.append(i)
	columns.append(		
			{
				"fieldname": "qty",
				"label": "<b>Total</b>",
				"fieldtype": "Float",
				"width":  150
			}
		)
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

		row += f'''
									sum({start}.qty) as  {start}, 
						Sum({start}.qty * {start}.weight_per_unit) AS {start}UOM,			
				''' 
		colm.append(
					{'fieldname': f'{start}','label': f'{start} (Qty)','fieldtype': 'Float','default' :0.00,'width':  150}
				)
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




							# sum(sjun.qty) as  june, 
							# sum(sjly.qty) as jly ,
							# sum(saug.qty) as saug,


							# LEFT JOIN `tabSales Invoice Item` sjly ON sii.name = sjly.name 
							# and si.posting_date between '2022-07-01' 
							# and '2022-07-31' 

							# LEFT JOIN `tabSales Invoice Item` saug ON sii.name = saug.name 
							# and si.posting_date between '2022-08-01' 
							# and '2022-08-30' 
							

	# dd = frappe.db.sql(f"""  select customer from `tabSales Invoice` where docstatus = 1 group by customer  """,as_dict=1)


	# for i  in dd:
	# 	# data.append(i)
	# 	cu = i['customer']
	# 	i['weight_per_unit2'] = None
	# 	i['weight_per_unit'] = None
	# 	dd2 = frappe.db.sql(f"""  
	# 			SELECT 
	# 				sii.item_code,
	# 				sum(sii.qty) as qty,
	# 				sum(sii.amount) as amount,
	# 				Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit,
	# 				Sum(sii.qty) * Sum(sii.weight_per_unit) AS weight_per_unit2,
	# 				si.customer as cc,
	# 				DATE_FORMAT(si.posting_date, '%Y-%m') as dd
					
	# 			FROM   `tabSales Invoice Item` sii
	# 				LEFT JOIN `tabSales Invoice` si
	# 						ON sii.parent = si.name
	# 			WHERE  si.docstatus = 1
	# 				AND si.customer = "{cu}"
	# 			GROUP  BY si.customer,
	# 					sii.item_code
	# 			ORDER  BY si.customer DESC; 
				
	# 				""",as_dict=1)
	# 	for j in dd2:
	# 		ss = j['item_code']
	# 		ddw =  frappe.db.sql(f""" 
	# 				select 
	# 					sum(sii.qty) as qty,
	# 					Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit

	# 				FROM   `tabSales Invoice Item` sii
	# 					LEFT JOIN `tabSales Invoice` si
	# 							ON sii.parent = si.name
	# 				WHERE  si.docstatus = 1 and si.posting_date between '2022-04-01' and '2022-04-30'
	# 					AND si.customer ="{cu}" and sii.item_code = "{ss}"
	# 				GROUP  BY si.customer,
	# 						sii.item_code
	# 				ORDER  BY si.customer DESC;
					
	# 				""",as_list=1)
					
	# 		ddw2 =  frappe.db.sql(f""" 
	# 				select 
	# 					sum(sii.qty) as qty,
	# 					Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit
	# 				FROM   `tabSales Invoice Item` sii
	# 					LEFT JOIN `tabSales Invoice` si
	# 							ON sii.parent = si.name
	# 				WHERE  si.docstatus = 1 and si.posting_date between '2022-05-01' and '2022-05-31'
	# 					AND si.customer ="{cu}" and sii.item_code = "{ss}"
	# 				GROUP  BY si.customer,
	# 						sii.item_code
	# 				ORDER  BY si.customer DESC;
					
	# 				""",as_list=1)
					
	# 		ddw3 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-06-01' and '2022-06-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	
					   
	# 		ddw4 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-07-01' and '2022-07-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw5 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-08-01' and '2022-08-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw6 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-09-01' and '2022-09-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw7 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-10-01' and '2022-10-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	
					   
	# 		ddw8 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-11-01' and '2022-11-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw9 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-12-01' and '2022-12-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	


	# 		if len(ddw) == 1:
	# 			j['2022-04'] = ddw[0][0]
	# 			j['2022-04(uom)'] = ddw[0][1]

	# 		if len(ddw2) == 1:
	# 			j['2022-05'] = ddw2[0][0]
	# 			j['2022-05(uom)'] = ddw2[0][1]

	# 		if len(ddw3) == 1:
	# 			j['2022-06'] = ddw3[0][0]
	# 			j['2022-06(uom)'] = ddw3[0][1]

	# 		if len(ddw4) == 1:
	# 			j['2022-07'] = ddw4[0][0]
	# 			j['2022-07(uom)'] = ddw4[0][1]

	# 		if len(ddw5) == 1:
	# 			j['2022-08'] = ddw5[0][0]
	# 			j['2022-08(uom)'] = ddw5[0][1]

	# 		if len(ddw6) == 1:
	# 			j['2022-09'] = ddw6[0][0]
	# 			j['2022-09(uom)'] = ddw6[0][1]

	# 		if len(ddw7) == 1:
	# 			j['2022-10'] = ddw7[0][0]
	# 			j['2022-10(uom)'] = ddw7[0][1]

	# dd = frappe.db.sql(f"""  select customer from `tabSales Invoice` where docstatus = 1 group by customer  """,as_dict=1)


	# for i  in dd:
	# 	# data.append(i)
	# 	cu = i['customer']
	# 	i['weight_per_unit2'] = None
	# 	i['weight_per_unit'] = None
	# 	dd2 = frappe.db.sql(f"""  
	# 			SELECT 
	# 				sii.item_code,
	# 				sum(sii.qty) as qty,
	# 				sum(sii.amount) as amount,
	# 				Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit,
	# 				Sum(sii.qty) * Sum(sii.weight_per_unit) AS weight_per_unit2,
	# 				si.customer as cc,
	# 				DATE_FORMAT(si.posting_date, '%Y-%m') as dd
					
	# 			FROM   `tabSales Invoice Item` sii
	# 				LEFT JOIN `tabSales Invoice` si
	# 						ON sii.parent = si.name
	# 			WHERE  si.docstatus = 1
	# 				AND si.customer = "{cu}"
	# 			GROUP  BY si.customer,
	# 					sii.item_code
	# 			ORDER  BY si.customer DESC; 
				
	# 				""",as_dict=1)
	# 	for j in dd2:
	# 		ss = j['item_code']
	# 		ddw =  frappe.db.sql(f""" 
	# 				select 
	# 					sum(sii.qty) as qty,
	# 					Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit

	# 				FROM   `tabSales Invoice Item` sii
	# 					LEFT JOIN `tabSales Invoice` si
	# 							ON sii.parent = si.name
	# 				WHERE  si.docstatus = 1 and si.posting_date between '2022-04-01' and '2022-04-30'
	# 					AND si.customer ="{cu}" and sii.item_code = "{ss}"
	# 				GROUP  BY si.customer,
	# 						sii.item_code
	# 				ORDER  BY si.customer DESC;
					
	# 				""",as_list=1)
					
	# 		ddw2 =  frappe.db.sql(f""" 
	# 				select 
	# 					sum(sii.qty) as qty,
	# 					Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit
	# 				FROM   `tabSales Invoice Item` sii
	# 					LEFT JOIN `tabSales Invoice` si
	# 							ON sii.parent = si.name
	# 				WHERE  si.docstatus = 1 and si.posting_date between '2022-05-01' and '2022-05-31'
	# 					AND si.customer ="{cu}" and sii.item_code = "{ss}"
	# 				GROUP  BY si.customer,
	# 						sii.item_code
	# 				ORDER  BY si.customer DESC;
					
	# 				""",as_list=1)
					
	# 		ddw3 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-06-01' and '2022-06-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	
					   
	# 		ddw4 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-07-01' and '2022-07-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw5 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-08-01' and '2022-08-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw6 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-09-01' and '2022-09-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw7 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-10-01' and '2022-10-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	
					   
	# 		ddw8 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-11-01' and '2022-11-31' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	

	# 		ddw9 =  frappe.db.sql(f""" select sum(sii.qty) as qty,Sum(sii.qty *sii.weight_per_unit) AS weight_per_unit  FROM   `tabSales Invoice Item` sii LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
	# 				   WHERE  si.docstatus = 1 and si.posting_date between '2022-12-01' and '2022-12-30' AND si.customer ="{cu}" and sii.item_code = "{ss}" GROUP  BY si.customer, sii.item_code ORDER  BY si.customer DESC;
	# 				   """,as_list=1)	


	# 		if len(ddw) == 1:
	# 			j['2022-04'] = ddw[0][0]
	# 			j['2022-04(uom)'] = ddw[0][1]

	# 		if len(ddw2) == 1:
	# 			j['2022-05'] = ddw2[0][0]
	# 			j['2022-05(uom)'] = ddw2[0][1]

	# 		if len(ddw3) == 1:
	# 			j['2022-06'] = ddw3[0][0]
	# 			j['2022-06(uom)'] = ddw3[0][1]

	# 		if len(ddw4) == 1:
	# 			j['2022-07'] = ddw4[0][0]
	# 			j['2022-07(uom)'] = ddw4[0][1]

	# 		if len(ddw5) == 1:
	# 			j['2022-08'] = ddw5[0][0]
	# 			j['2022-08(uom)'] = ddw5[0][1]

	# 		if len(ddw6) == 1:
	# 			j['2022-09'] = ddw6[0][0]
	# 			j['2022-09(uom)'] = ddw6[0][1]

	# 		if len(ddw7) == 1:
	# 			j['2022-10'] = ddw7[0][0]
	# 			j['2022-10(uom)'] = ddw7[0][1]

	# 		if len(ddw8) == 1:
	# 			j['2022-11'] = ddw8[0][0]
	# 			j['2022-11(uom)'] = ddw8[0][1]

	# 		if len(ddw9) == 1:
	# 			j['2022-12'] = ddw9[0][0]
	# 			j['2022-12(uom)'] = ddw9[0][1]

	# 		if len(ddw8) == 1:
	# 			j['2022-11'] = ddw8[0][0]
	# 			j['2022-11(uom)'] = ddw8[0][1]

	# 		if len(ddw9) == 1:
	# 			j['2022-12'] = ddw9[0][0]
	# 			j['2022-12(uom)'] = ddw9[0][1]


			# data.append(j)











					# (CASE
					# 	WHEN
					# 		si.posting_date BETWEEN '2022-08-01' AND '2022-08-30' THEN sum(sii.qty)
					# 	WHEN
					# 		si.posting_date BETWEEN '2022-07-01' AND '2022-07-31' THEN sum(sii.qty)
					# 	ELSE 
					# 		NULL
					# END )AS wqwqw,



