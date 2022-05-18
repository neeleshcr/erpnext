// Copyright (c) 2022, VPS Consultancy and contributors
// For license information, please see license.txt
/* eslint-disable */

// frappe.query_reports["Custom Sales invoice trends"] = {
// 	"filters": [

// 	]
// };


frappe.require("assets/erpnext/js/sales_trends_filters.js", function() {
	frappe.query_reports["Custom Sales invoice trends"] = {
		filters: erpnext.get_sales_trends_filters()
	}
});

