# Copyright (c) 2022, VPS Consultancy and contributors
# For license information, please see license.txt

# import frappe

import frappe
from frappe import _, scrub
from frappe.utils import add_days, add_to_date, flt, getdate
from six import iteritems

from erpnext.accounts.utils import get_fiscal_year


def execute(filters=None):
	return Analytics(filters).run()


class Analytics(object):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.date_field = (
			"transaction_date"
			if self.filters.doc_type in ["Sales Order", "Purchase Order"]
			else "posting_date"
		)
		self.months = [
			"Jan",
			"Feb",
			"Mar",
			"Apr",
			"May",
			"Jun",
			"Jul",
			"Aug",
			"Sep",
			"Oct",
			"Nov",
			"Dec",
		]
		self.get_period_date_ranges()

	def run(self):
		self.get_columns()
		self.get_data()
		self.get_chart_data()

		# Skipping total row for tree-view reports
		skip_total_row = 0

		if self.filters.tree_type in ["Supplier Group", "Item Group", "Customer Group", "Territory"]:
			skip_total_row = 1

		return self.columns, self.data, None, self.chart, None, skip_total_row

	def get_columns(self):
		self.columns = [
			{
				"label": _(self.filters.tree_type),
				"options": self.filters.tree_type if self.filters.tree_type != "Order Type" else "",
				"fieldname": "entity",
				"fieldtype": "Link" if self.filters.tree_type != "Order Type" else "Data",
				"width": 140 if self.filters.tree_type != "Order Type" else 200,
			}
		]
		if self.filters.tree_type in ["Item"]:
			self.columns.append(
				{
					"label": _(self.filters.tree_type + " Name"),
					"fieldname": "entity_name",
					"fieldtype": "Data",
					"width": 140,
				}
			)
		if self.filters.tree_type in ["Customer", "Supplier"]:
			self.columns.append(
				{
					"label": _(self.filters.tree_type + " Name"),
					"fieldname": "entity_name",
					"fieldtype": "Data",
					"width": 140,
				}
			)
		if self.filters.tree_type == "Item":
			self.columns.append(
				{
					"label": _("UOM"),
					"fieldname": "stock_uom",
					"fieldtype": "Link",
					"options": "UOM",
					"width": 100,
				}
			)

		for end_date in self.periodic_daterange:
			period = self.get_period(end_date)
			self.columns.append(
				{"label": _(period), "fieldname": scrub(period), "fieldtype": "Float", "width": 120}
			)

		self.columns.append(
			{"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "width": 120}
		)

	def get_data(self):
		if self.filters.tree_type in ["Customer", "Supplier"]:
			self.get_sales_transactions_based_on_customers_or_suppliers()
			self.get_rows()

		elif self.filters.tree_type == "Item":
			self.get_sales_transactions_based_on_items()
			self.get_rows()

		elif self.filters.tree_type in ["Customer Group", "Supplier Group", "Territory"]:
			self.get_sales_transactions_based_on_customer_or_territory_group()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Item Group":
			self.get_sales_transactions_based_on_item_group()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Order Type":
			if self.filters.doc_type != "Sales Order":
				self.data = []
				return
			self.get_sales_transactions_based_on_order_type()
			self.get_rows_by_group()

		elif self.filters.tree_type == "Project":
			self.get_sales_transactions_based_on_project()
			self.get_rows()


	def get_sales_transactions_based_on_order_type(self):
		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total"
			self.entries = frappe.db.sql(
				""" select s.order_type as entity, s.{value_field} as value_field, s.{date_field}
				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s and s.{date_field} between %s and %s
				and ifnull(s.order_type, '') != '' order by s.order_type
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)
		elif self.filters["value_quantity"] == "Quantity":
			value_field = "total_qty"
			self.entries = frappe.db.sql(
				""" select s.order_type as entity, s.{value_field} * i.weight_per_unit as value_field, s.{date_field}
				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s and s.{date_field} between %s and %s
				and ifnull(s.order_type, '') != '' order by s.order_type
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)

		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "total_qty"
			self.entries = frappe.db.sql(
				""" select s.order_type as entity, s.{value_field} * i.weight_per_unit as value_field, s.{date_field}
				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s and s.{date_field} between %s and %s
				and ifnull(s.order_type, '') != '' order by s.order_type and s.item_code NOT LIKE %s
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date,'Scheme'),
				as_dict=1,
			)

		self.get_teams()

	def get_sales_transactions_based_on_customers_or_suppliers(self):
		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"

			if self.filters.tree_type == "Customer":
				entity = "customer as entity"
				entity_name = "customer_group as entity_name"
			else:
				entity = "supplier as entity"
				entity_name = "supplier_group as entity_name"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, entity_name, value_field, self.date_field],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)

		elif self.filters["value_quantity"] == "Quantity":
			value_field = "total_qty as value_field"

			if self.filters.tree_type == "Customer":
				entity = "customer as entity"
				entity_name = "customer_group as entity_name"
			else:
				entity = "supplier as entity"
				entity_name = "supplier_group as entity_name"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, entity_name, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']

		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "total_qty as value_field"

			if self.filters.tree_type == "Customer":
				entity = "customer as entity"
				entity_name = "customer_group as entity_name"
			else:
				entity = "supplier as entity"
				entity_name = "supplier_group as entity_name"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, entity_name, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}'  and item_code NOT LIKE '%Scheme%' """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']



		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_sales_transactions_based_on_items(self):

		if self.filters["value_quantity"] == "Value":
			value_field = "base_amount"
			self.entries = frappe.db.sql(
				"""
				select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
				from `tab{doctype} Item` i , `tab{doctype}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = %s
				and s.{date_field} between %s and %s
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)
		elif self.filters["value_quantity"] == "Quantity":
			value_field = "qty"
			self.entries = frappe.db.sql(
				"""
				select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} * i.weight_per_unit as value_field, s.{date_field}
				from `tab{doctype} Item` i , `tab{doctype}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = %s
				and s.{date_field} between %s and %s
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)	


		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "qty"
			self.entries = frappe.db.sql(
				f"""
				select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} * i.weight_per_unit as value_field, s.{self.date_field}
				from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
				and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' and  i.item_code NOT LIKE '%Scheme%'
			""",
			# .format(
			# 		date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
			# 	),
			# 	(self.filters.company, self.filters.from_date, self.filters.to_date,f'Scheme'),
				as_dict=1
			)	





		self.entity_names = {}
		for d in self.entries:
			self.entity_names.setdefault(d.entity, d.entity_name)

	def get_sales_transactions_based_on_customer_or_territory_group(self):
		if self.filters.tree_type == "Customer Group":
			entity_field = "customer_group as entity"
		elif self.filters.tree_type == "Supplier Group":
			entity_field = "supplier as entity"
			self.get_supplier_parent_child_map()
		else:
			entity_field = "territory as entity"

		if self.filters["value_quantity"] == "Value":
			if self.filters.tree_type == "Customer Group":
				entity_field = "customer_group as entity"
			elif self.filters.tree_type == "Supplier Group":
				entity_field = "supplier as entity"
				self.get_supplier_parent_child_map()
			else:
				entity_field = "territory as entity"

			value_field = "base_net_total as value_field"
			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity_field, value_field, self.date_field],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
		elif self.filters["value_quantity"] == "Quantity":
			value_field = "total_qty as value_field"
			if self.filters.tree_type == "Customer Group":
				entity_field = "customer_group as entity"
			elif self.filters.tree_type == "Supplier Group":
				entity_field = "supplier as entity"
				self.get_supplier_parent_child_map()
			else:
				entity_field = "territory as entity"


			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity_field, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']

		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "total_qty as value_field"
			if self.filters.tree_type == "Customer Group":
				entity_field = "customer_group as entity"
			elif self.filters.tree_type == "Supplier Group":
				entity_field = "supplier as entity"
				self.get_supplier_parent_child_map()
			else:
				entity_field = "territory as entity"


			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity_field, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' and item_code NOT LIKE '%Scheme%'   """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']



		self.get_groups()

	def get_sales_transactions_based_on_item_group(self):
		if self.filters["value_quantity"] == "Value":
			value_field = "base_amount"
			# self.entries = frappe.db.sql(
			# 	f"""
			# 	select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.base_amount as value_field, s.{self.date_field}
			# 	from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
			# 	where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
			# 	and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}'
			# 	group by s.name
			# """,
			# # .format(
			# # 		date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
			# # 	),
			# # 	(self.filters.company, self.filters.from_date, self.filters.to_date),
			# 	as_dict=1
			# )

			self.entries = frappe.db.sql(
				"""
				select i.item_group as entity, i.{value_field} as value_field, s.{date_field}
				from `tab{doctype} Item` i , `tab{doctype}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = %s
				and s.{date_field} between %s and %s
			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)





		elif self.filters["value_quantity"] == "Quantity":
			value_field = "qty*i.weight_per_unit)"
			self.entries = frappe.db.sql(
				"""
				select i.item_group as entity, sum(i.{value_field} as value_field, s.{date_field}
				from `tab{doctype} Item` i , `tab{doctype}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = %s
				and s.{date_field} between %s and %s
				group by s.name,i.item_group

			""".format(
					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
				),
				(self.filters.company, self.filters.from_date, self.filters.to_date),
				as_dict=1,
			)
			# self.entries = frappe.db.sql(
			# 	f"""
			# 	select i.item_group as entity,sum(i.{value_field} as value_field, s.{self.date_field},s.name as name
			# 	from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
			# 	where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
			# 	and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}'

			# 	""",as_dict=1,)
			# 	# group by s.name

		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "qty*i.weight_per_unit)"
			
			self.entries = frappe.db.sql(
				f"""
				select i.item_group as entity,sum(i.{value_field} as value_field, s.{self.date_field},s.name as name
				from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
				where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
				and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}'  and  i.item_code NOT LIKE '%Scheme%'
				group by s.name,i.item_group

				""",as_dict=1,)
				# group by s.name

		self.get_groups()

	def get_sales_transactions_based_on_project(self):
		if self.filters["value_quantity"] == "Value":
			value_field = "base_net_total as value_field"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, value_field, self.date_field],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					"project": ["!=", ""],
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)
		elif self.filters["value_quantity"] == "Quantity":
			value_field = "total_qty as value_field"

			entity = "project as entity"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					"project": ["!=", ""],
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)

			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']


		elif self.filters["value_quantity"] == "QuantityWscheme":
			value_field = "total_qty as value_field"

			entity = "project as entity"

			self.entries = frappe.get_all(
				self.filters.doc_type,
				fields=[entity, value_field, self.date_field,"name"],
				filters={
					"docstatus": 1,
					"company": self.filters.company,
					"project": ["!=", ""],
					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
				},
			)

			res2 = [a_dict["name"] for a_dict in self.entries]
			for i in self.entries:
			    ff = frappe.db.sql(f""" select Sum(qty*weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}'  and item_code NOT LIKE '%Scheme%'    """,as_dict=1)
			    index = res2.index(i.name)
			    ff3 = self.entries[index]
			    ff3['value_field'] = ff[0]['yy']


	def get_rows(self):
		self.data = []
		self.get_periodic_data()

		for entity, period_data in iteritems(self.entity_periodic_data):
			row = {
				"entity": entity,
				"entity_name": self.entity_names.get(entity) if hasattr(self, "entity_names") else None,
			}
			total = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				amount = flt(period_data.get(period, 0.0))
				row[scrub(period)] = amount
				total += amount

			row["total"] = total

			if self.filters.tree_type == "Item":
				row["stock_uom"] = period_data.get("stock_uom")

			self.data.append(row)

	def get_rows_by_group(self):
		self.get_periodic_data()
		out = []

		for d in reversed(self.group_entries):
			row = {"entity": d.name, "indent": self.depth_map.get(d.name)}
			total = 0
			for end_date in self.periodic_daterange:
				period = self.get_period(end_date)
				amount = flt(self.entity_periodic_data.get(d.name, {}).get(period, 0.0))
				row[scrub(period)] = amount
				if d.parent and (self.filters.tree_type != "Order Type" or d.parent == "Order Types"):
					self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(period, 0.0)
					self.entity_periodic_data[d.parent][period] += amount
				total += amount

			row["total"] = total
			out = [row] + out

		self.data = out

	def get_periodic_data(self):
		self.entity_periodic_data = frappe._dict()

		for d in self.entries:
			if self.filters.tree_type == "Supplier Group":
				d.entity = self.parent_child_map.get(d.entity)
			period = self.get_period(d.get(self.date_field))
			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault(period, 0.0)
			self.entity_periodic_data[d.entity][period] += flt(d.value_field)

			if self.filters.tree_type == "Item":
				self.entity_periodic_data[d.entity]["stock_uom"] = d.stock_uom

	def get_period(self, posting_date):
		if self.filters.range == "Weekly":
			period = "Week " + str(posting_date.isocalendar()[1]) + " " + str(posting_date.year)
		elif self.filters.range == "Monthly":
			period = str(self.months[posting_date.month - 1]) + " " + str(posting_date.year)
		elif self.filters.range == "Quarterly":
			period = "Quarter " + str(((posting_date.month - 1) // 3) + 1) + " " + str(posting_date.year)
		else:
			year = get_fiscal_year(posting_date, company=self.filters.company)
			period = str(year[0])
		return period

	def get_period_date_ranges(self):
		from dateutil.relativedelta import MO, relativedelta

		from_date, to_date = getdate(self.filters.from_date), getdate(self.filters.to_date)

		increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(
			self.filters.range, 1
		)

		if self.filters.range in ["Monthly", "Quarterly"]:
			from_date = from_date.replace(day=1)
		elif self.filters.range == "Yearly":
			from_date = get_fiscal_year(from_date)[1]
		else:
			from_date = from_date + relativedelta(from_date, weekday=MO(-1))

		self.periodic_daterange = []
		for dummy in range(1, 53):
			if self.filters.range == "Weekly":
				period_end_date = add_days(from_date, 6)
			else:
				period_end_date = add_to_date(from_date, months=increment, days=-1)

			if period_end_date > to_date:
				period_end_date = to_date

			self.periodic_daterange.append(period_end_date)

			from_date = add_days(period_end_date, 1)
			if period_end_date == to_date:
				break

	def get_groups(self):
		if self.filters.tree_type == "Territory":
			parent = "parent_territory"
		if self.filters.tree_type == "Customer Group":
			parent = "parent_customer_group"
		if self.filters.tree_type == "Item Group":
			parent = "parent_item_group"
		if self.filters.tree_type == "Supplier Group":
			parent = "parent_supplier_group"

		self.depth_map = frappe._dict()

		self.group_entries = frappe.db.sql(
			"""select name, lft, rgt , {parent} as parent
			from `tab{tree}` order by lft""".format(
				tree=self.filters.tree_type, parent=parent
			),
			as_dict=1,
		)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_teams(self):
		self.depth_map = frappe._dict()

		self.group_entries = frappe.db.sql(
			""" select * from (select "Order Types" as name, 0 as lft,
			2 as rgt, '' as parent union select distinct order_type as name, 1 as lft, 1 as rgt, "Order Types" as parent
			from `tab{doctype}` where ifnull(order_type, '') != '') as b order by lft, name
		""".format(
				doctype=self.filters.doc_type
			),
			as_dict=1,
		)

		for d in self.group_entries:
			if d.parent:
				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
			else:
				self.depth_map.setdefault(d.name, 0)

	def get_supplier_parent_child_map(self):
		self.parent_child_map = frappe._dict(
			frappe.db.sql(""" select name, supplier_group from `tabSupplier`""")
		)

	def get_chart_data(self):
		length = len(self.columns)

		if self.filters.tree_type in ["Customer", "Supplier"]:
			labels = [d.get("label") for d in self.columns[2 : length - 1]]
		elif self.filters.tree_type == "Item":
			labels = [d.get("label") for d in self.columns[3 : length - 1]]
		else:
			labels = [d.get("label") for d in self.columns[1 : length - 1]]
		self.chart = {"data": {"labels": labels, "datasets": []}, "type": "line"}







# ----------------------------17-may-2022
	# def get_sales_transactions_based_on_order_type(self):
# 		if self.filters["value_quantity"] == "Value":
# 			value_field = "base_net_total"
# 			self.entries = frappe.db.sql(
# 				""" select s.order_type as entity, s.{value_field} as value_field, s.{date_field}
# 				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s and s.{date_field} between %s and %s
# 				and ifnull(s.order_type, '') != '' order by s.order_type
# 			""".format(
# 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 				),
# 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1,
# 			)
# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "total_qty"
# 			self.entries = frappe.db.sql(
# 				""" select s.order_type as entity, s.{value_field} * s.weight_per_unit as value_field, s.{date_field}
# 				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s  and s.{date_field} between %s and %s
# 				and ifnull(s.order_type, '') != '' order by s.order_type
# 			""".format(
# 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 				),
# 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1,
# 			)
# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "total_qty"
# 			self.entries = frappe.db.sql(
# 				""" select s.order_type as entity, s.{value_field} * s.weight_per_unit as value_field, s.{date_field}
# 				from `tab{doctype}` s where s.docstatus = 1 and s.company = %s  and s.{date_field} between %s and %s
# 				and ifnull(s.order_type, '') != '' order by s.order_type and s.item_code NOT LIKE '%Scheme%'
# 			""".format(
# 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 				),
# 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1,
# 			)
# 		self.get_teams()

# 	def get_sales_transactions_based_on_customers_or_suppliers(self):
# 		if self.filters["value_quantity"] == "Value":
# 			value_field = "base_net_total as value_field"

# 			if self.filters.tree_type == "Customer":
# 				entity = "customer as entity"
# 				entity_name = "customer_name as entity_name"
# 			else:
# 				entity = "supplier as entity"
# 				entity_name = "supplier_name as entity_name"

# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity, entity_name, value_field, self.date_field],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 				},
# 			)
# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "total_qty as value_field"

# 			if self.filters.tree_type == "Customer":
# 				entity = "customer as entity"
# 				entity_name = "customer_name as entity_name"
# 			else:
# 				entity = "supplier as entity"
# 				entity_name = "supplier_name as entity_name"


# 			self.entries = frappe.db.sql(f""" select
# 									       s.{entity},
# 									       s.{entity_name},
# 									       s.total_qty*sum(i.weight_per_unit) as value_field,
# 										   s.{self.date_field}
# 										   ,s.name

# 										   from `tab{self.filters.doc_type}` s
# 										   left join `tab{self.filters.doc_type} Item` i
# 										   on i.parent = s.name
# 										   where s.docstatus = 1 and s.company = '{self.filters.company}'
# 										   and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' 

# 										   group by s.customer,s.total_qty,s.{self.date_field},s.customer_name,s.name

# 									                """,as_dict=1)

# 			# self.entries = frappe.get_all(
# 			# 	self.filters.doc_type,
# 			# 	fields=[entity, entity_name, value_field, self.date_field,"name",'total_net_weight'],
# 			# 	filters={
# 			# 		"docstatus": 1,
# 			# 		"company": self.filters.company,
# 			# 		self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 			# 		# "status":("!=",'Return')
# 			# 	},
# 			# )



# 			# res2 = [a_dict["name"] for a_dict in self.entries]
# 			# for i in self.entries:
# 			# 	i['value_field']=i['value_field']*i['total_net_weight']
# 			# 	ff = frappe.db.sql(f""" select weight_per_unit from `tab{self.filters.doc_type} Item` where parent = '{i.name}'""",as_dict=1)
# 			# 	index = res2.index(i.name)
# 			# 	ff3 = self.entries[index]
# 			# 	ff3['value_field'] = ff[0]['Sum(qty)*sum(weight_per_unit)']

# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "total_qty as value_field"

# 			if self.filters.tree_type == "Customer":
# 				entity = "customer as entity"
# 				entity_name = "customer_name as entity_name"
# 			else:
# 				entity = "supplier as entity"
# 				entity_name = "supplier_name as entity_name"

# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity, entity_name, value_field, self.date_field,"name"],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 					# "status":("!=",'Return')
# 				},
# 			)
# 			res2 = [a_dict["name"] for a_dict in self.entries]
# 			for i in self.entries:
# 				ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) from `tab{self.filters.doc_type} Item` where parent = '{i.name}'  and item_name NOT LIKE '%Scheme%' """,as_dict=1)
# 				index = res2.index(i.name)
# 				ff3 = self.entries[index]
# 				ff3['value_field'] = ff[0]['Sum(qty)*sum(weight_per_unit)']

# 		self.entity_names = {}
# 		for d in self.entries:
# 			self.entity_names.setdefault(d.entity, d.entity_name)

# 	def get_sales_transactions_based_on_items(self):
# 		sss = ' '
# 		if self.filters["value_quantity"] == "Value":
# 			value_field = "base_amount"
# 			self.entries = frappe.db.sql(
# 					"""
# 						select i.item_code as entity, i.item_name as entity_name,s.name as name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
# 						from `tab{doctype} Item` i , `tab{doctype}` s
# 						where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 						and s.{date_field} between %s and %s 
# 					""".format(
# 							date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 						),
# 						(self.filters.company, self.filters.from_date, self.filters.to_date),
# 						as_dict=1,
# 					)
# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "qty)*sum(i.weight_per_unit)"
# 			self.entries = frappe.db.sql(
# 					"""
# 						select i.item_code as entity, i.item_name as entity_name,s.name as name, i.stock_uom, sum(i.{value_field} as value_field, s.{date_field}
# 						from `tab{doctype} Item` i , `tab{doctype}` s
# 						where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 						and s.{date_field} between %s and %s 
# 						group by s.name 
# 					""".format(
# 							date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 						),
# 						(self.filters.company, self.filters.from_date, self.filters.to_date),
# 						as_dict=1,
# 					)
# 			# res2 = [a_dict["name"] for a_dict in self.entries]
# 			# for i in self.entries:
# 			# 	ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
# 			# 	index = res2.index(i.name)
# 			# 	ff3 = self.entries[index]
# 			# 	ff3['value_field'] = ff[0]['yy']


# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "qty)*sum(i.weight_per_unit)"
# 			self.entries = frappe.db.sql(
# 					f"""
# 						select i.item_code as entity, i.item_name as entity_name,s.name as name, i.stock_uom, sum(i.{value_field} as value_field, s.{self.date_field}
# 						from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
# 						where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
# 						and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' and  i.item_code NOT LIKE '%Scheme%'
# 						group by s.name 

# 					""",
# 					# .format(
# 						# 	date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 						# ),
# 						# (self.filters.company, self.filters.from_date, self.filters.to_date),
# 						as_dict=1
# 					)
# 			# res2 = [a_dict["name"] for a_dict in self.entries]
# 			# for i in self.entries:
# 			# 	ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' and item_name NOT LIKE '%Scheme%' """,as_dict=1)
# 			# 	index = res2.index(i.name)
# 			# 	ff3 = self.entries[index]
# 			# 	ff3['value_field'] = ff[0]['yy']

# 			# self.entries = frappe.db.sql(
# 			# 	"""
# 			# 	select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
# 			# 	from `tab{doctype} Item` i , `tab{doctype}` s
# 			# 	where s.name = i.parent and i.docstatus = 1 and s.company = %s 
# 			# 	and s.{date_field} between %s and %s
# 			# """.format(
# 			# 		date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 			# 	),
# 			# 	(self.filters.company, self.filters.from_date, self.filters.to_date),
# 			# 	as_dict=1,
# 			# )

# 			# self.entries = frappe.db.sql(
# 			# 	f"""
# 			# 	select i.item_code as entity, i.item_name as entity_name, i.stock_uom,  Sum(i.{value_field})*Sum(i.weight_per_unit) as value_field, s.{self.date_field}
# 			# 	from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
# 			# 	where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'   
# 			# 	and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' group by i.item_name ,s.posting_date,s.name
# 			# """,
# 			# 	as_dict=1,ValueError
# 		# self.entries = {}
# 		# if value_field == "base_amount":*i.weight_per_unit 
# 		# 	self.entries = frappe.db.sql(
# 		# 		"""
# 		# 		select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
# 		# 		from `tab{doctype} Item` i , `tab{doctype}` s
# 		# 		where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 		# 		and s.{date_field} between %s and %s
# 		# 	""".format(
# 		# 			date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 		# 		),
# 		# 		(self.filters.company, self.filters.from_date, self.filters.to_date),
# 		# 		as_dict=1,
# 		# 	)
# 		# elif value_field == "base_amount":
# 		# 	self.entries = frappe.db.sql(
# 		# 		"""
# 		# 		select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field}*i.weight_per_unit as value_field, s.{date_field}
# 		# 		from `tab{doctype} Item` i , `tab{doctype}` s
# 		# 		where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 		# 		and s.{date_field} between %s and %s
# 		# 	""".format(
# 		# 			date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 		# 		),
# 		# 		(self.filters.company, self.filters.from_date, self.filters.to_date),
# 		# 		as_dict=1,
# 		# 	)	
# # saad 28-04-22

# 		self.entity_names = {}
# 		for d in self.entries:
# 			self.entity_names.setdefault(d.entity, d.entity_name)

# 	def get_sales_transactions_based_on_customer_or_territory_group(self):
# 		if self.filters.tree_type == "Customer Group":
# 			entity_field = "customer_group as entity"
# 		elif self.filters.tree_type == "Supplier Group":
# 			entity_field = "supplier as entity"
# 			self.get_supplier_parent_child_map()
# 		else:
# 			entity_field = "territory as entity"
			
# 		if self.filters["value_quantity"] == "Value":
# 			if self.filters.tree_type == "Customer Group":
# 				entity_field = "customer_group as entity"
# 			elif self.filters.tree_type == "Supplier Group":
# 				entity_field = "supplier as entity"
# 				self.get_supplier_parent_child_map()
# 			else:
# 				entity_field = "territory as entity"
				
# 			value_field = "base_net_total as value_field"
# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity_field, value_field, self.date_field],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 				},
# 			)
# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "total_qty as value_field"
# 			if self.filters.tree_type == "Customer Group":
# 				entity_field = "customer_group as entity"
# 			elif self.filters.tree_type == "Supplier Group":
# 				entity_field = "supplier as entity"
# 				self.get_supplier_parent_child_map()
# 			else:
# 				entity_field = "territory as entity"


# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity_field, value_field, self.date_field,"name"],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 					# "status":("!=",'Return')
# 				},
# 			)
# 			res2 = [a_dict["name"] for a_dict in self.entries]
# 			for i in self.entries:
# 				ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit)  from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
# 				index = res2.index(i.name)
# 				ff3 = self.entries[index]
# 				ff3['value_field'] = ff[0]['Sum(qty)*sum(weight_per_unit)']
# 			    # ff3['value_field'] = i.name

# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "total_qty as value_field"
# 			if self.filters.tree_type == "Customer Group":
# 				entity_field = "customer_group as entity"
# 			elif self.filters.tree_type == "Supplier Group":
# 				entity_field = "supplier as entity"
# 				self.get_supplier_parent_child_map()
# 			else:
# 				entity_field = "territory as entity"


# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity_field, value_field, self.date_field,"name"],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 					# "status":("!=",'Return')
# 				},
# 			)
# 			res2 = [a_dict["name"] for a_dict in self.entries]
# 			for i in self.entries:
# 				ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit)  from `tab{self.filters.doc_type} Item` where parent = '{i.name}'  and item_code NOT LIKE '%Scheme%'  """,as_dict=1)
# 				index = res2.index(i.name)
# 				ff3 = self.entries[index]
# 				ff3['value_field'] = ff[0]['Sum(qty)*sum(weight_per_unit)']


# 		self.get_groups()

# 	def get_sales_transactions_based_on_item_group(self):
# 		ssc = " "
# 		if self.filters["value_quantity"] == "Value":
# 			value_field = "base_amount"
# 			self.entries = frappe.db.sql(
# 				"""
# 				select i.item_group as entity, i.{value_field} as value_field, s.{date_field},s.name as name
# 				from `tab{doctype} Item` i , `tab{doctype}` s
# 				where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 				and s.{date_field} between %s and %s 
# 			""".format(
# 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 				),
# 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1,
# 			)


# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "qty)*sum(i.weight_per_unit)"
			
# 			self.entries = frappe.db.sql(
# 				"""
# 				select i.item_group as entity,sum(i.{value_field} as value_field, s.{date_field},s.name as name
# 				from `tab{doctype} Item` i , `tab{doctype}` s
# 				where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 				and s.{date_field} between %s and %s 
# 				group by s.name 

# 			""".format(
# 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 				),
# 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1,
# 			)
# 			# res2 = [a_dict["name"] for a_dict in self.entries]
# 			# for i in self.entries:
# 			# 	ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
# 			# 	index = res2.index(i.name)
# 			# 	ff3 = self.entries[index]
# 			# 	ff3['value_field'] = ff[0]['yy']


			
# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "qty)*sum(weight_per_unit)"

				
# 			self.entries = frappe.db.sql(
# 				f"""
# 				select i.item_group as entity, sum(i.{value_field} as value_field, s.{self.date_field},s.name as name
# 				from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
# 				where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}'
# 				and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}'   and  i.item_code NOT LIKE '%Scheme%'
# 				group by s.name
# 			""",
# 			# format(
# 			# 		date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 			# 	),
# 			# 	(self.filters.company, self.filters.from_date, self.filters.to_date),
# 				as_dict=1
# 			)
# 			# res2 = [a_dict["name"] for a_dict in self.entries]
# 			# for i in self.entries:
# 			# 	ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}'   and item_code NOT LIKE '%Scheme%'  """,as_dict=1)
# 			# 	index = res2.index(i.name)
# 			# 	ff3 = self.entries[index]
# 			# 	ff3['value_field'] = ff[0]['yy']
# 		# self.entries = frappe.db.sql(
# 		# 	f"""

# 		# 	select i.item_group as entity, i.{value_field} as value_field, s.{self.date_field}
# 		# 	from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
# 		# 	where s.name = i.parent and i.docstatus = 1 and s.company = '{self.filters.company}' 
# 		# 	and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' {ssc} 


# 		# """,
# 		# 	as_dict=1,
# 		# )

# 			# select i.item_group as entity, {value_field} as value_field, s.{self.date_field}
# 			# from `tab{self.filters.doc_type} Item` i , `tab{self.filters.doc_type}` s
# 			# where s.name = i.parent and i.docstatus = 1 and s.company ='{self.filters.company}' 
# 			# and s.{self.date_field} between '{self.filters.from_date}' and '{self.filters.to_date}' {ssc}  group by i.item_name ,s.posting_date,s.name
# 		self.get_groups()
# 		# if self.filters["value_quantity"] == "Value":
# 		# 	value_field = "base_amount"
# 		# 	self.entries = frappe.db.sql(
# 		# 		"""
# 		# 		select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
# 		# 		from `tab{doctype} Item` i , `tab{doctype}` s
# 		# 		where s.name = i.parent and i.docstatus = 1 and s.company = %s
# 		# 		and s.{date_field} between %s and %s
# 		# 	""".format(
# 		# 			date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 		# 		),
# 		# 		(self.filters.company, self.filters.from_date, self.filters.to_date),
# 		# 		as_dict=1,
# 		# 	)
# 		# else:
# 		# 	value_field = "total_weight"
# 			# self.entries = frappe.db.sql(
# 			# 	"""
# 			# 	select i.item_code as entity, i.item_name as entity_name, i.stock_uom, 1+1 as value_field, s.{date_field}
# 			# 	from `tab{doctype} Item` i , `tab{doctype}` s
# 			# 	where s.name = i.parent and i.docstatus = 1 and s.company = %s and s.status != 'Return'
# 			# 	and s.{date_field} between %s and %s
# 			# """.format(
# 			# 		date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# 			# 	),
# 			# 	(self.filters.company, self.filters.from_date, self.filters.to_date),
# 			# 	as_dict=1,
# 			# )


# # # saad 28-04-22
# # 		self.entries = {}

# # 		if value_field == "base_amount":i.{value_field} * i.weight_per_unit
# # 			self.entries = frappe.db.sql(
# # 				"""
# # 				select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field} as value_field, s.{date_field}
# # 				from `tab{doctype} Item` i , `tab{doctype}` s
# # 				where s.name = i.parent and i.docstatus = 1 and s.company = %s
# # 				and s.{date_field} between %s and %s
# # 			""".format(
# # 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# # 				),
# # 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# # 				as_dict=1,
# # 			)
# # 		elif value_field == "base_amount":
# # 			self.entries = frappe.db.sql(
# # 				"""
# # 				select i.item_code as entity, i.item_name as entity_name, i.stock_uom, i.{value_field}*i.weight_per_unit as value_field, s.{date_field}
# # 				from `tab{doctype} Item` i , `tab{doctype}` s
# # 				where s.name = i.parent and i.docstatus = 1 and s.company = %s
# # 				and s.{date_field} between %s and %s
# # 			""".format(
# # 					date_field=self.date_field, value_field=value_field, doctype=self.filters.doc_type
# # 				),
# # 				(self.filters.company, self.filters.from_date, self.filters.to_date),
# # 				as_dict=1,
# # 			)	
# # saad 28-04-22
# 		# self.get_groups()

# 	def get_sales_transactions_based_on_project(self):
# 		if self.filters["value_quantity"] == "Value":
# 			value_field = "base_net_total as value_field"

# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity, value_field, self.date_field],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					"project": ["!=", ""],
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 				},
# 			)
# 		elif self.filters["value_quantity"] == "Quantity":
# 			value_field = "total_qty as value_field"

# 			entity = "project as entity"

# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity, value_field, self.date_field,"name"],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					"project": ["!=", ""],
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 					# "status":("!=",'Return')

# 				},
# 			)

# 			res2 = [a_dict["name"] for a_dict in self.entries]
# 			for i in self.entries:
# 				ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' """,as_dict=1)
# 				index = res2.index(i.name)
# 				ff3 = self.entries[index]
# 				ff3['value_field'] = ff[0]['yy']

# 		elif self.filters["value_quantity"] == "QuantityWscheme":
# 			value_field = "total_qty as value_field"

# 			entity = "project as entity"

# 			self.entries = frappe.get_all(
# 				self.filters.doc_type,
# 				fields=[entity, value_field, self.date_field,"name"],
# 				filters={
# 					"docstatus": 1,
# 					"company": self.filters.company,
# 					"project": ["!=", ""],
# 					self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 					# "status":("!=",'Return')

# 				},
# 			)

# 			res2 = [a_dict["name"] for a_dict in self.entries]
# 			for i in self.entries:
# 				ff = frappe.db.sql(f""" select Sum(qty)*sum(weight_per_unit) as yy from `tab{self.filters.doc_type} Item` where parent = '{i.name}' and item_code NOT LIKE '%Scheme%'""",as_dict=1)
# 				index = res2.index(i.name)
# 				ff3 = self.entries[index]
# 				ff3['value_field'] = ff[0]['yy']

# 		# self.entries = frappe.get_all(
# 		# 	self.filters.doc_type,
# 		# 	fields=[entity, entity_name, value_field, self.date_field,"name"],
# 		# 	filters={
# 		# 		"docstatus": 1,
# 		# 		"company": self.filters.company,
# 		# 		self.date_field: ("between", [self.filters.from_date, self.filters.to_date]),
# 		# 	},
# 		# )

# 	def get_rows(self):
# 		self.data = []
# 		self.get_periodic_data()

# 		for entity, period_data in iteritems(self.entity_periodic_data):
# 			row = {
# 				"entity": entity,
# 				"entity_name": self.entity_names.get(entity) if hasattr(self, "entity_names") else None,
# 			}
# 			total = 0
# 			for end_date in self.periodic_daterange:
# 				period = self.get_period(end_date)
# 				amount = flt(period_data.get(period, 0.0))
# 				row[scrub(period)] = amount
# 				total += amount

# 			row["total"] = total

# 			if self.filters.tree_type == "Item":
# 				row["stock_uom"] = period_data.get("stock_uom")

# 			self.data.append(row)

# 	def get_rows_by_group(self):
# 		self.get_periodic_data()
# 		out = []

# 		for d in reversed(self.group_entries):
# 			row = {"entity": d.name, "indent": self.depth_map.get(d.name)}
# 			total = 0
# 			for end_date in self.periodic_daterange:
# 				period = self.get_period(end_date)
# 				amount = flt(self.entity_periodic_data.get(d.name, {}).get(period, 0.0))
# 				row[scrub(period)] = amount
# 				if d.parent and (self.filters.tree_type != "Order Type" or d.parent == "Order Types"):
# 					self.entity_periodic_data.setdefault(d.parent, frappe._dict()).setdefault(period, 0.0)
# 					self.entity_periodic_data[d.parent][period] += amount
# 				total += amount

# 			row["total"] = total
# 			out = [row] + out

# 		self.data = out

# 	def get_periodic_data(self):
# 		self.entity_periodic_data = frappe._dict()

# 		for d in self.entries:
# 			if self.filters.tree_type == "Supplier Group":
# 				d.entity = self.parent_child_map.get(d.entity)
# 			period = self.get_period(d.get(self.date_field))
# 			self.entity_periodic_data.setdefault(d.entity, frappe._dict()).setdefault(period, 0.0)
# 			self.entity_periodic_data[d.entity][period] += flt(d.value_field)

# 			if self.filters.tree_type == "Item":
# 				self.entity_periodic_data[d.entity]["stock_uom"] = d.stock_uom

# 	def get_period(self, posting_date):
# 		if self.filters.range == "Weekly":
# 			period = "Week " + str(posting_date.isocalendar()[1]) + " " + str(posting_date.year)
# 		elif self.filters.range == "Monthly":
# 			period = str(self.months[posting_date.month - 1]) + " " + str(posting_date.year)
# 		elif self.filters.range == "Quarterly":
# 			period = "Quarter " + str(((posting_date.month - 1) // 3) + 1) + " " + str(posting_date.year)
# 		else:
# 			year = get_fiscal_year(posting_date, company=self.filters.company)
# 			period = str(year[0])
# 		return period

# 	def get_period_date_ranges(self):
# 		from dateutil.relativedelta import MO, relativedelta

# 		from_date, to_date = getdate(self.filters.from_date), getdate(self.filters.to_date)

# 		increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(
# 			self.filters.range, 1
# 		)

# 		if self.filters.range in ["Monthly", "Quarterly"]:
# 			from_date = from_date.replace(day=1)
# 		elif self.filters.range == "Yearly":
# 			from_date = get_fiscal_year(from_date)[1]
# 		else:
# 			from_date = from_date + relativedelta(from_date, weekday=MO(-1))

# 		self.periodic_daterange = []
# 		for dummy in range(1, 53):
# 			if self.filters.range == "Weekly":
# 				period_end_date = add_days(from_date, 6)
# 			else:
# 				period_end_date = add_to_date(from_date, months=increment, days=-1)

# 			if period_end_date > to_date:
# 				period_end_date = to_date

# 			self.periodic_daterange.append(period_end_date)

# 			from_date = add_days(period_end_date, 1)
# 			if period_end_date == to_date:
# 				break

# 	def get_groups(self):
# 		if self.filters.tree_type == "Territory":
# 			parent = "parent_territory"
# 		if self.filters.tree_type == "Customer Group":
# 			parent = "parent_customer_group"
# 		if self.filters.tree_type == "Item Group":
# 			parent = "parent_item_group"
# 		if self.filters.tree_type == "Supplier Group":
# 			parent = "parent_supplier_group"

# 		self.depth_map = frappe._dict()

# 		self.group_entries = frappe.db.sql(
# 			"""select name, lft, rgt , {parent} as parent
# 			from `tab{tree}` order by lft""".format(
# 				tree=self.filters.tree_type, parent=parent
# 			),
# 			as_dict=1,
# 		)

# 		for d in self.group_entries:
# 			if d.parent:
# 				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
# 			else:
# 				self.depth_map.setdefault(d.name, 0)

# 	def get_teams(self):
# 		self.depth_map = frappe._dict()

# 		self.group_entries = frappe.db.sql(
# 			""" select * from (select "Order Types" as name, 0 as lft,
# 			2 as rgt, '' as parent union select distinct order_type as name, 1 as lft, 1 as rgt, "Order Types" as parent
# 			from `tab{doctype}` where ifnull(order_type, '') != '') as b order by lft, name
# 		""".format(
# 				doctype=self.filters.doc_type
# 			),
# 			as_dict=1,
# 		)

# 		for d in self.group_entries:
# 			if d.parent:
# 				self.depth_map.setdefault(d.name, self.depth_map.get(d.parent) + 1)
# 			else:
# 				self.depth_map.setdefault(d.name, 0)

# 	def get_supplier_parent_child_map(self):
# 		self.parent_child_map = frappe._dict(
# 			frappe.db.sql(""" select name, supplier_group from `tabSupplier`""")
# 		)

# 	def get_chart_data(self):
# 		length = len(self.columns)

# 		if self.filters.tree_type in ["Customer", "Supplier"]:
# 			labels = [d.get("label") for d in self.columns[2 : length - 1]]
# 		elif self.filters.tree_type == "Item":
# 			labels = [d.get("label") for d in self.columns[3 : length - 1]]
# 		else:
# 			labels = [d.get("label") for d in self.columns[1 : length - 1]]
# 		self.chart = {"data": {"labels": labels, "datasets": []}, "type": "line"}
