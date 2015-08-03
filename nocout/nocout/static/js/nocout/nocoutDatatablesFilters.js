/**
 * This file handle the advance filtering feature for datatables.
 */
// Global Variables
var existing_pagesettings_html = '<div class="clearfix"></div>',
	non_filtering_columns = [
		'action',
		'actions',
		'nms_action',
		'nms_actions'
	],
	add_filter_btn_html = '<div class="form-group add_filter_btn_contianer"> \
						   <div class="col-md-12 pull-right" align="right"> \
						   <a href="javascript:;" title="Add Filter Block" onclick="addNewFilters();"> \
						   <i class="fa fa-plus"></i></a></div></div>',
	condition_block_html = '<div class="filters_remove_container"> \
							<h4 title="Remove Filter Block" pk="<1>"><i class="fa fa-times text-danger"></i></h4> \
							</div><hr/><div class="form-group"> \
							<label class="col-sm-3 control-label">Select Condition</label> \
							<div class="col-sm-8"> \
							<select class="form-control condition_box" id="{}"> \
							<option value="">Select Condition</option> \
							<option value="and">AND</option> \
							<option value="or" selected>OR</option> \
							</select></div></div><hr/>',
	global_table_id = '',
	global_grid_headers = '',
	max_fields_length = 0;

/**
 * This function creates advance filters HTML as per the given headers
 * @method nocout_createAdvanceFilter
 * @param headers {Array}, It contains the listing headers array.
 */
function nocout_createAdvanceFilter (headers, tableId) {
	if (!headers || $('#' + tableId + '_advance_filter').length > 0) {
		return true;
	}
	var current_html = $.trim($('.page_settings_container').html());

	if (current_html == existing_pagesettings_html) {
		global_table_id = tableId;
		global_grid_headers = headers;
		var filter_container_id = global_table_id + '_advance_filter',
			form_block_id = filter_container_id + '_form',
			filter_block_html = '';

		filter_block_html += '<div id="' + filter_container_id + '">';
		filter_block_html += '<h4><i class="fa fa-arrow-circle-o-right"> </i> Advance Filter</h4>';
		filter_block_html += '<div id="' + form_block_id + '" class="col-md-9 col-md-offset-1">';
		filter_block_html += '<div class="form-group form-horizontal col-md-12" style="max-height: 300px;overflow: auto;">';
		filter_block_html += createFilterFieldsHtml(1);
		filter_block_html += add_filter_btn_html;
		filter_block_html += '</div></div>';
		filter_block_html += '<div class="col-md-8 col-md-offset-2">';
        filter_block_html += '<button type="button" class="pull-right btn btn-sm btn-danger filter_cancel_btn" \
        					  style="margin-left:10px;" id="' + filter_container_id + '_cancel"> Cancel </button>';
        filter_block_html += '<button type="button" class="pull-right btn btn-sm btn-success \
        					  filter_submit_btn" onclick="applyDatatableAdvanceFilter(this);" \
        					  id="' + filter_container_id + '_submit"> Filter </button>';
		filter_block_html += '</div><div class="clearfix"></div></div>';
		filter_block_html += '<div class="divide-20"></div>';

		$(filter_block_html).insertBefore($('#' + tableId).closest('.box')[0]);
	}
}


/**
 * This function add new selectbox & input for filtering option
 * @method addNewFilters
 */
function addNewFilters() {
	var form_id = global_table_id + '_advance_filter_form',
		select_id_prefix = global_table_id + '_advance_filter_select_',
		select_boxes = $('#' + form_id + ' select[id*="' + select_id_prefix + '"]'),
		total_select_boxes = select_boxes.length,
		field_html = createFilterFieldsHtml(Number(total_select_boxes) + 1);

	$(field_html).insertBefore($('.add_filter_btn_contianer'));
}


/**
 * This function generate HTML of filter fields(select & input) html
 * @method createFilterFieldsHtml
 * @return field_block_html
 */
function createFilterFieldsHtml(counter) {

	if (max_fields_length == counter) {
		$('.add_filter_btn_contianer').addClass('hide');
	}

	var field_block_html = '',
		filter_container_id = global_table_id + '_advance_filter',
		selectbox_id = filter_container_id + '_select_' + String(counter),
		inputbox_id = filter_container_id + '_input_' + String(counter);

	if (counter > 1) {
		var condition_block_id = filter_container_id + '_condition_' + String(counter),
			temp = condition_block_html;
		temp = temp.replace('<1>', String(counter));
		temp = temp.replace('{}', condition_block_id);
		field_block_html += temp;
	}

	field_block_html += '<div class="form-group">';
	field_block_html += '<label class="col-sm-3 control-label">Select Column</label>';
	field_block_html += '<div class="col-sm-8">';
	field_block_html += '<select class="form-control" id="' + selectbox_id + '">';
	field_block_html += '<option value="">Select Column</option>';

	for (var i=0;i<global_grid_headers.length;i++) {
		var columns_name = $.trim(global_grid_headers[i]['mData']),
			columns_title = $.trim(global_grid_headers[i]['sTitle']);

		// If column contains hide class
		if (global_grid_headers[i].hasOwnProperty('sClass') && global_grid_headers[i]['sClass'].indexOf('hide') > -1) {
			continue;
		}

		// If column is not searchable
		if (global_grid_headers[i].hasOwnProperty('bSearchable') && global_grid_headers[i]['bSearchable']) {
			continue;
		}

		// If column exists in 'non_filtering_columns'
		if (non_filtering_columns.indexOf(columns_name.toLowerCase()) > -1) {
			continue;
		}

		if (counter == 1) {
			max_fields_length++;
		}

		field_block_html += '<option value="' + columns_name + '">' + columns_title + '</option>';
	}
	
	field_block_html += '</select></div></div>';
	field_block_html += '<div class="form-group">';
	field_block_html += '<label class="col-sm-3 control-label">Enter Value</label>';
	field_block_html += '<div class="col-sm-8">';
	field_block_html += '<input type="text" class="form-control" id="' + inputbox_id + '" name="' + inputbox_id + '"/>';
	field_block_html += '</div></div>';


	return field_block_html;
}

/**
 * This function remove the given counter filter block from dom
 * @method removeFilterFieldsHtml
 */
function removeFilterFieldsHtml(counter) {
	if (!counter) {
		return ;
	}

	var filter_container_id = global_table_id + '_advance_filter',
		selectbox_id = filter_container_id + '_select_' + String(counter),
		inputbox_id = filter_container_id + '_input_' + String(counter),
		condition_block_id = filter_container_id + '_condition_' + String(counter);

	// Remove HTML blocks
	$('#' + selectbox_id).closest('.form-group').remove();
	$('#' + inputbox_id).closest('.form-group').remove();
	$('#' + condition_block_id).closest('.form-group').prev('hr').remove();
	$('#' + condition_block_id).closest('.form-group').next('hr').remove();
	$('#' + condition_block_id).closest('.form-group').remove();
	$('h4[pk=' + counter + ']').parent('.filters_remove_container').remove();

	if($('.add_filter_btn_contianer').hasClass('hide')) {
		$('.add_filter_btn_contianer').removeClass('hide');
	}
}

/**
 * This function called when 'Filter' button of advance filters form clicked
 * @method applyDatatableAdvanceFilter
 * @param current_object {Object}, It contains current object instance
 */
function applyDatatableAdvanceFilter(current_object) {
	var button_id = current_object.id,
		common_id = button_id ? button_id.split('_submit')[0] : '';
	
	if (!common_id) {
		return;
	}

	var total_select_box = $('select[id^="' + common_id + '_select_"]'),
		total_condition_box = $('select[id^="' + common_id + '_condition_"]'),
		total_input_box = $('input[id^="' + common_id + '"]');
	console.log(total_select_box);
	console.log(total_condition_box);
	console.log(total_input_box);
}


$('body').delegate('.filters_remove_container h4', 'click', function(e) {
	var counter_val = $(this).attr('pk')
	removeFilterFieldsHtml(counter_val);
});