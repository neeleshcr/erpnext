from erpnext.controllers.queries import get_match_cond
import frappe

@frappe.whitelist()
def get_batch(warehouse=None,item_code=None):
    filters = {
        'warehouse':warehouse,
        'item_code':item_code,
        'posting_date':frappe.utils.getdate()
    }
    if get_batch_no(doctype='Batch',filters=filters):
        return get_batch_no(doctype='Batch',filters=filters)[0][0]
    else:
        return None


@frappe.whitelist()
def get_batch_no(doctype,  filters):
	doctype = "Batch"
	cond = ""
	if filters.get("posting_date"):
		cond = "and (batch.expiry_date is null or batch.expiry_date >= %(posting_date)s)"

	batch_nos = None
	args = {
		"item_code": filters.get("item_code"),
		"warehouse": filters.get("warehouse"),
		"posting_date": filters.get("posting_date"),
	}

	having_clause = "having sum(sle.actual_qty) > 0"
	if filters.get("is_return"):
		having_clause = ""

	meta = frappe.get_meta(doctype, cached=True)

	search_columns = ""
	search_cond = ""


	if args.get("warehouse"):

		batch_nos = frappe.db.sql(
			"""select sle.batch_no, round(sum(sle.actual_qty),2), sle.stock_uom,
				concat('MFG-',batch.manufacturing_date), concat('EXP-',batch.expiry_date)
				{search_columns}
			from `tabStock Ledger Entry` sle
				INNER JOIN `tabBatch` batch on sle.batch_no = batch.name
			where
				batch.disabled = 0
				and sle.is_cancelled = 0
				and sle.item_code = %(item_code)s
				and sle.warehouse = %(warehouse)s
				and batch.docstatus < 2
				{cond}
				{match_conditions}
			group by batch_no {having_clause}
			order by batch.manufacturing_date
			""".format(
				search_columns=search_columns,
				cond=cond,
				match_conditions=get_match_cond(doctype),
				having_clause=having_clause,
				search_cond=search_cond,
			),
			args,
		)

		return batch_nos
	else:
		return frappe.db.sql(
			"""select name, concat('MFG-', manufacturing_date), concat('EXP-',expiry_date)
			{search_columns}
			from `tabBatch` batch
			where batch.disabled = 0
			and item = %(item_code)s
			and docstatus < 2
			{0}
			{match_conditions}

			order by manufacturing_date
			""".format(
				cond,
				search_columns=search_columns,
				search_cond=search_cond,
				match_conditions=get_match_cond(doctype),
			),
			args,
		)
