/**
 * This library is used to show & hide the spinner
 * @uses spin.js
 */

/*Spinner configuration object*/
var spinner_options = {
        lines: 20, // The number of lines to draw
        length: 40, // The length of each line
        width: 2, // The line thickness
        radius: 30, // The radius of the inner circle
        corners: 1, // Corner roundness (0..1)
        rotate: 0, // The rotation offset
        direction: 1, // 1: clockwise, -1: counterclockwise
        color: '#111', // #rgb or #rrggbb or array of colors
        speed: 1, // Rounds per second
        trail: 45, // Afterglow percentage
        shadow: false, // Whether to render a shadow
        hwaccel: false, // Whether to use hardware acceleration
        className: 'spinner', // The CSS class to assign to the spinner
        zIndex: 2e9, // The z-index (defaults to 2000000000)
        top: '50%', // Top position relative to parent
        left: '50%' // Left position relative to parent
    },
    backdrop_html = '<div class="modal-backdrop fade in" id="ajax_backdrop"></div>';
/*Spinner DOM Element*/
var dom_target = document.getElementById('ajax_spinner');
/*Initialize spinner object*/
var spinner = new Spinner(spinner_options).spin(dom_target);
/**
 * This funtion show the spinner
 */
function showSpinner() {
	
	if($("#ajax_spinner").hasClass("hide")) {
        /*Show ajax_spinner div*/
        $("#ajax_spinner").removeClass("hide");
        /*If ajax_backdrop div not exist then appent it to body */
        if($("#ajax_backdrop").length == 0) {
            $("#page_content_div").append(backdrop_html);
        }            
    }
}

/**
 * This funtion hide the spinner
 */
function hideSpinner() {
	
	/*Remove backdrop div & hide spinner*/
    $("#ajax_backdrop").remove();
    if(!($("#ajax_spinner").hasClass("hide"))) {
        /*Hide ajax_spinner div*/
        $("#ajax_spinner").addClass("hide");
    }
}


function createPaginateTabs() {
    if($('.top_perf_tabs').length) {
        // console.log($('.top_perf_tabs li'));
        // console.log($('.top_perf_tabs li').length);
    }
}