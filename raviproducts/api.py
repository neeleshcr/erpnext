import frappe
from frappe.utils import getdate
from frappe import _





@frappe.whitelist(allow_guest=True)
def get_mon(dt):
	return getdate(dt).strftime("%b")


@frappe.whitelist(allow_guest=True)
def get_period_date_ranges_columns(period, fiscal_year=None, year_start_date=None):
    from dateutil.relativedelta import relativedelta

    if not year_start_date:
        year_start_date, year_end_date = frappe.db.get_value(
            "Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"]
        )

    increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(period)

    period_date_ranges = []
    for i in range(1, 13, increment):
        period_end_date = getdate(year_start_date) + relativedelta(months=increment, days=-1)
        if period_end_date > getdate(year_end_date):
            period_end_date = year_end_date
        period_date_ranges.append([year_start_date, period_end_date])
        year_start_date = period_end_date + relativedelta(days=1)
        if period_end_date == year_end_date:
            break

    return period_date_ranges

@frappe.whitelist(allow_guest=True)
def get_period_wise_columns(bet_dates, period, pwc):
	if period == "Monthly":
		pwc += [
			_(get_mon(bet_dates[0])) + " (" + _("Qty") + "):Float:120",
			_(get_mon(bet_dates[0])) + " (" + _("Amt") + "):Currency:120",
		]
	else:
		pwc += [
			_(get_mon(bet_dates[0])) + "-" + _(get_mon(bet_dates[1])) + " (" + _("Qty") + "):Float:120",
			_(get_mon(bet_dates[0])) + "-" + _(get_mon(bet_dates[1])) + " (" + _("Amt") + "):Currency:120",
		]

@frappe.whitelist(allow_guest=True)
def period_wise_columns_query(filters, trans):
	query_details = ""
	pwc = []
	bet_dates = get_period_date_ranges_columns(filters.get("period"), filters.get("fiscal_year"))

	if trans in ["Purchase Receipt", "Delivery Note", "Purchase Invoice", "Sales Invoice"]:
		trans_date = "posting_date"
		if filters.period_based_on:
			trans_date = filters.period_based_on
	else:
		trans_date = "transaction_date"

	if filters.get("period") != "Yearly":
		for dt in bet_dates:
			get_period_wise_columns(dt, filters.get("period"), pwc)
			query_details = get_period_wise_query(dt, trans_date, query_details)
	else:
		pwc = [
			_(filters.get("fiscal_year")) + " (" + _("Qty") + "):Float:120",
			_(filters.get("fiscal_year")) + " (" + _("Amt") + "):Currency:120",
		]
		query_details = " SUM(t2.qty*t2.weight_per_unit), SUM(t2.base_net_amount),"

	query_details += "SUM(t2.qty*t2.weight_per_unit), SUM(t2.base_net_amount)"
	return pwc, query_details

@frappe.whitelist(allow_guest=True)
def get_period_month_ranges(period, fiscal_year):
	from dateutil.relativedelta import relativedelta

	period_month_ranges = []

	for start_date, end_date in get_period_date_ranges_columns(period, fiscal_year):
		months_in_this_period = []
		while start_date <= end_date:
			months_in_this_period.append(start_date.strftime("%B"))
			start_date += relativedelta(months=1)
		period_month_ranges.append(months_in_this_period)

	return period_month_ranges

@frappe.whitelist(allow_guest=True)
def get_period_wise_query(bet_dates, trans_date, query_details):
	query_details += """SUM(IF(t1.%(trans_date)s BETWEEN '%(sd)s' AND '%(ed)s',t2.qty*t2.weight_per_unit, NULL)),
					SUM(IF(t1.%(trans_date)s BETWEEN '%(sd)s' AND '%(ed)s', t2.base_net_amount, NULL)),
				""" % {
		"trans_date": trans_date,
		"sd": bet_dates[0],
		"ed": bet_dates[1],
	}
	return query_details




def get_period_date_ranges_columns(period, fiscal_year=None, year_start_date=None):
    from dateutil.relativedelta import relativedelta

    if not year_start_date:
        year_start_date, year_end_date = frappe.db.get_value(
            "Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"]
        )

    increment = {"Monthly": 1, "Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}.get(period)

    period_date_ranges = []
    for i in range(1, 13, increment):
        period_end_date = getdate(year_start_date) + relativedelta(months=increment, days=-1)
        if period_end_date > getdate(year_end_date):
            period_end_date = year_end_date
        period_date_ranges.append([year_start_date, period_end_date])
        year_start_date = period_end_date + relativedelta(days=1)
        if period_end_date == year_end_date:
            break

    return period_date_ranges