/**
 * This library handles the tab click event & load the data as per the selected tab.
 * @class openTabContentLib
 * @event click
 */

var last_clicked_tab = "",
    timeOutId = "",
    ptp_list = ['ptp','p2p'],
    pmp_list = ['pmp'],
    wimax_list = ['wimax','wifi','temp','ulIssue','sectorUtil'],
    other_list = ['temp','p2p'];

$(".nav-tabs li a").click(function (e, isFirst) {

    /*Initialize the timer in seconds.Right now its 1 year*/
    /*86400 is 24 hrs miliseconds*/
    var timer = 86400 * 30 * 12;
    /* 1 Year in seconds */

    /*Clear or Reset Time out*/
    clearTimeout(timeOutId);

    var anchor_id = e.currentTarget.id,
        browser_url_array = window.location.href.split("#"),
        second_condition = "";

    if (isFirst) {
        second_condition = isFirst;
    } else {
        second_condition = false;
    }

    /*Current Tab content id or anchor tab hyperlink*/
    new_url = e.currentTarget.href;


    if (!isFirst) {
        window.location.href = new_url;
    }

    var destroy = false,
        div_id = e.currentTarget.href.split("#")[1],
        table_id = $("#" + div_id).find("table")[0].id,
        ajax_url = e.currentTarget.attributes.data_url.value,
        grid_headers = JSON.parse(e.currentTarget.attributes.data_header.value),
        isTab = $('.nav li.active .hidden-inline-mobile');
    // isTableExists = $.fn.dataTableSettings;

    /*Check that the table is created before or not*/
    // for ( var i=0, iLen=isTableExists.length ; i<iLen ; i++ ) {

    // 	if (isTableExists[i] && (isTableExists[i].nTable.id == table_id)) {

    // 		if(last_clicked_tab != e.currentTarget.id || second_condition) {

    // 			/*Clear the data from existing table*/
    // 			$("#"+table_id).DataTable().fnDestroy();
    // 			// $("#"+table_id).html("");
    // 			destroy = true;
    // 		}
    // 	}
    // }

    if (last_clicked_tab != e.currentTarget.id || second_condition) {
        var tab_id = table_id ? table_id.toLowerCase() : "";

        var isPtp = ptp_list.filter(function(list_val) {
                return tab_id.search(list_val) > -1
            }).length,
            pmpLength = pmp_list.filter(function(list_val) {
                return tab_id.search(list_val) > -1
            }).length,
            wimaxLength = wimax_list.filter(function(list_val) {
                return tab_id.search(list_val) > -1
            }).length,
            isPmpWimax = pmpLength + wimaxLength;

        // If tab is ptp
        if(isPtp > 0) {
            for (var i = 0; i < grid_headers.length; i++) {
                var column = grid_headers[i];
                if (column.mData.indexOf("sector_id") > -1) {
                    if (column.bVisible) {
                        column.sClass = "hide";
                    } else {
                        column["sClass"] = "hide";
                    }
                }
            }
        // If tab is PMP or Wimax
        } else if(isPmpWimax > 0) {
            if(window.location.href.search("customer_live") == -1 && window.location.href.search("customer_detail") == -1) {
                for (var i = 0; i < grid_headers.length; i++) {
                    var column = grid_headers[i];
                    if (column.mData.indexOf("circuit_id") > -1 || column.mData.indexOf("customer_name") > -1) {
                        if (column.bVisible) {
                            column.sClass = "hide";
                        } else {
                            column["sClass"] = "hide";
                        }
                    }
                }
            }
        } else {
            // For other case
            for (var i = 0; i < grid_headers.length; i++) {
                var column = grid_headers[i],
                    condition1 = column.mData.indexOf("sector_id") > -1,
                    condition2 = column.mData.indexOf("circuit_id") > -1,
                    condition3 = column.mData.indexOf("customer_name") > -1;
                if(condition1 || condition2 || condition3) {
                    if (column.bVisible) {
                        column.sClass = "hide";
                    } else {
                        column["sClass"] = "hide";
                    }
                }
            }
        }

        /*Call createDataTable function to create the data table for specified dom element with given data*/
        dataTableInstance.createDataTable(table_id, grid_headers, ajax_url, destroy);
    }

    setTimeout(function() {
        // Update Breadcrumb
        $(".breadcrumb li:last-child").html('<a href="javascript:;"><strong>'+$('.nav li.active .hidden-inline-mobile').text()+'</strong></a>');
    },150);

    /*Save the last clicked tab id in global variable for condition checks*/
    last_clicked_tab = e.currentTarget.id;

    /*Refresh the tab after every given timer. Right now it is 5 minutes*/
    timeOutId = setTimeout(function () {

        $("#" + anchor_id).trigger('click', true);

    }, (+(timer) + "000"));
});