
frappe.ui.form.on("POS Invoice Item", {
	item_code: function(frm,cdt,cdn) {
        setTimeout(() => {
            let row = locals[cdt][cdn]

            frappe.call({
                method:'raviproducts.raviproducts.py.item.get_batch',
                args:{
                    'warehouse':row.warehouse,
                    'item_code':row.item_code
                },
                callback:function(res){
                    frappe.model.set_value(row.doctype,row.name,'batch_no',res.message)
                    frm.refresh_field('items')
                }
            })
        }, 220);
    }
})
