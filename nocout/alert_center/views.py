#Rad5k
# -*- coding: utf-8 -*-

import datetime
# faster json processing module
import ujson as json
import requests
from django.db.models.query import ValuesQuerySet, Q
from django.db.models import F
from django.core.urlresolvers import reverse
from django.db.models.expressions import RawSQL
from django.views.generic import ListView, View
from django.http import HttpResponse
from copy import deepcopy
from django_datatables_view.base_datatable_view import BaseDatatableView
from device.models import Device, DeviceTechnology, DeviceType, DeviceTicket
from machine.models import Machine
# For SIA Listing
from alert_center.models import CurrentAlarms, ClearAlarms, HistoryAlarms, PlannedEvent, ManualTicketingHistory
from performance.models import EventNetwork, EventService, InventoryStatus, ServiceStatus, UtilizationStatus, PerformanceService
from download_center.models import Customer_Count_Sector

from operator import itemgetter
# Import performance utils gateway class
from performance.utils.util import PerformanceUtilsGateway
from performance.formulae import display_time

# Import inventory utils gateway class
from inventory.utils.util import InventoryUtilsGateway
from inventory.models import Sector, BaseStation, SubStation, Circuit, Backhaul

# Import alert_center utils gateway class
from alert_center.utils.util import AlertCenterUtilsGateway, get_ping_status

# Import scheduling_management utils gateway class
from scheduling_management.utils.util import SchedulingManagementGateway

# Import nocout utils gateway class
from nocout.utils.util import NocoutUtilsGateway

from django.utils.dateformat import format

# nocout project settings # TODO: Remove the HARDCODED technology IDs
from nocout.settings import DATE_TIME_FORMAT, TRAPS_DATABASE, MULTI_PROCESSING_ENABLED, CACHE_TIME, \
SHOW_CUSTOMER_COUNT_IN_ALERT_LIST, SHOW_CUSTOMER_COUNT_IN_NETWORK_ALERT, SHOW_TICKET_NUMBER, \
ENABLE_MANUAL_TICKETING, SHOW_SPRINT3, MANUAL_TICKET_API

# Import advance filtering mixin for BaseDatatableView
from nocout.mixins.datatable import AdvanceFilteringMixin

import logging
logger = logging.getLogger(__name__)

# Create instance of 'InventoryUtilsGateway' class
inventory_utils = InventoryUtilsGateway()

# Create instance of 'AlertCenterUtilsGateway' class
alert_utils = AlertCenterUtilsGateway()

# Create instance of 'AlertCenterUtilsGateway' class
perf_utils = PerformanceUtilsGateway()

# Create instance of 'SchedulingManagementGateway' class
scheduling_utils = SchedulingManagementGateway()

# Create instance of 'NocoutUtilsGateway' class
nocout_utils = NocoutUtilsGateway()

device_technology_dict = {}
device_type_dict = {}
device_type_dict.update(DeviceType.objects.values_list('id', 'name'))
device_technology_list = DeviceTechnology.objects.extra(select={'name' : 'LOWER(name)', 'id':'id'}).values_list('name','id')
device_technology_dict.update(device_technology_list)

INCLUDED_EVENTS_FOR_MANUAL_TICKETING = [
    'ODU1_Lost', 'ODU1_No_Heart_Beat', 'ODU1_Output_RF_TX_Unleveled', 
    'ODU1_Input_IF_TX_Unleveled', 'ODU1_Power_Amplifier_OFF', 'ODU2_Lost', 
    'ODU2_No_Heart_Beat', 'ODU2_Output_RF_TX_Unleveled', 'ODU2_Input_IF_TX_Unleveled', 
    'ODU2_Power_Amplifier_OFF', 'wimax_interfaces_down__synchronization_lost', 'PD_threshold_breach_major',
    'Device_not_reachable', 'gpsNotSynchronised'
]

class AlertCenterListing(ListView):
    """
    Class Based View to render Alert Center Network Listing page with latency, packet drop
    down and service impact alert tabs.

    """
    model = EventNetwork
    template_name = 'alert_center/alerts_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.

        :param kwargs:
        """

        context = super(AlertCenterListing, self).get_context_data(**kwargs)

        page_type = self.kwargs.get('page_type', 'network')

        data_source = self.kwargs.get('data_source', None)

        data_source_title = "Latency Avg (ms) " \
            if data_source == "latency" \
            else ("value".title() if data_source in ["service"] else "packet drop (%)".title())

        if not data_source:
            self.template_name = 'alert_center/customer_alert_details_list.html'
            data_source_title = 'Value'

        severity_headers = [
            {'mData': 'severity', 'sTitle': '', 'sWidth': '40px', 'bSortable': True}
        ]

        ckt_customer_headers = [
            {'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'customer_name', 'sTitle': 'Customer Name', 'sWidth': 'auto', 'bSortable': True}
        ]

        # List of headers which are shown first in grid for PTP Tab in both pages(network & customer)
        ptp_starting_headers = []
        ptp_starting_headers += ckt_customer_headers

        # List of headers which are shown first in grid for PMP & WiMAX Tab in both pages(network & customer)
        pmp_wimax_starting_headers = []
        pmp_wimax_starting_headers += [
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True}
        ]

        rad5_headers = []
        rad5_customer_detail_headers = []
        rad5_polled_col = []

        # Show region column in all Network Alert Tabs
        # if page_type.lower() == 'network':
        #     region_col_visible = True
        # else:
        #     region_col_visible = False

        region_header = [
            {'mData': 'region', 'sTitle': 'Region', 'sWidth': 'auto', 'bSortable': True},
        ]

        rad5_headers += region_header

        # if Network page and data source is latency than add SE to PE min latency column.
        if page_type in ['network','customer'] and data_source == 'latency':
            rad5_headers += [
                {'mData': 'min_latency', 'sTitle': 'Latency (Server to PE) min', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
            ]

        # If customer page then add near end ip column to all stating columns list
        if page_type == 'customer':
            near_ip_column = [{
                'mData': 'near_end_ip',
                'sTitle': 'Near End IP',
                'sWidth': 'auto',
                'bSortable': True
            }]

            ptp_starting_headers += near_ip_column

            pmp_wimax_starting_headers += ckt_customer_headers
            pmp_wimax_starting_headers += near_ip_column



            # For saving if else hassle we have used a dict over here
            rad5_polled_col_dict = {
                'packet_drop':[
                    {'mData': 'dl_uas', 'sTitle': 'UAS DL', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False},
                    {'mData': 'ul_uas', 'sTitle': 'UAS UL', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
                ],
                'latency': [
                    {'mData': 'dl_utilization', 'sTitle': 'Utilisation DL%', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False},
                    {'mData': 'ul_utilization', 'sTitle': 'Utilisation UL%', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
                ],
                'down': [
                    {'mData': 'device_uptime', 'sTitle': 'Device Uptime', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
                ],
            }

            rad5_polled_col += rad5_polled_col_dict.get(data_source, [])

        # List of common headers for all pages of alerts listing
        common_headers = [
            {'mData': 'ip_address', 'sTitle': 'IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'device_type', 'sTitle': 'Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_name', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'site_id', 'sTitle': 'SITE ID', 'sWidth': 'auto', 'bSortable': True, 'bVisible':False},
            {'mData': 'city', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'state', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': True},
        ]

        bh_specific_headers = [
            {'mData': 'bh_connectivity', 'sTitle': 'Onnet/Offnet', 'sWidth': 'auto', 'bSortable': True}
        ]

        # Page specific & polled headers list initialization
        polled_headers = []

        if  not data_source or data_source == 'service':
            polled_headers += [{
                'mData': 'data_source_name',
                'sTitle': 'Data Source',
                'sWidth': 'auto',
                'bSortable': True
            }]

        polled_headers += [{
            'mData': 'current_value',
            'sTitle': '{0}'.format(data_source_title),
            'sWidth': 'auto',
            'bSortable': True,
            "sSortDataType": "dom-text",
            "sType": "numeric"
        }]

        if data_source == "latency":
            polled_headers += [
                {
                    'mData': 'max_value',
                    'sTitle': 'Latency Max (ms)',
                    'sWidth': 'auto',
                    'bSortable': True,
                    "sSortDataType": "dom-text",
                    "sType": "numeric"
                },
                {
                    'mData': 'min_value',
                    'sTitle': 'Latency Min (ms)',
                    'sWidth': 'auto',
                    'bSortable': True,
                    "sSortDataType": "dom-text",
                    "sType": "numeric"
                }
            ]

        other_headers = [
            {'mData': 'sys_timestamp', 'sTitle': 'Timestamp', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'age', 'sTitle': 'Status Since', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'action', 'sTitle': 'Action', 'sWidth': 'auto', 'bSortable': False}
        ]

        # These headers are for Alert Center -> Customer Details -> Radwin5K Tab
        rad5_customer_start_headers = [
            {'mData': 'severity', 'sTitle': '', 'bSortable': True, 'sWidth': '40px'},
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'customer_name', 'sTitle': 'Customer Name', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'near_end_ip', 'sTitle': 'HBS IP', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'ip_address', 'sTitle': 'HSU IP', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'device_type', 'sTitle': 'Type', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'bs_name', 'sTitle': 'BS Name', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'site_id', 'sTitle': 'SITE ID', 'sWidth': 'auto', 'bSortable': True, 'bVisible':False},
            {'mData': 'city', 'sTitle': 'City', 'bSortable': True, 'sWidth': 'auto'},
            {'mData': 'state', 'sTitle': 'State', 'bSortable': True, 'sWidth': 'auto'}
        ]

        rad5_other_headers = [
            {'mData': 'sys_timestamp', 'sTitle': 'Timestamp', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'age', 'sTitle': 'Status Since', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'warning_threshold', 'sTitle': 'Warn', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'action', 'sTitle': 'Action', 'sWidth': 'auto', 'bSortable': False}
        ]


        # Customer Count Header
        customer_count_header = [{
            'mData': 'customer_count',
            'sTitle': 'Customer Count',
            'sWidth': 'auto',
            'bSortable': True
        }]
        
        # Initialize headers list for all tabs
        ptp_datatable_headers = []
        pmp_wimax_datatable_headers = []
        bh_datatable_headers = []

        ptp_datatable_headers += severity_headers
        ptp_datatable_headers += ptp_starting_headers
        ptp_datatable_headers += common_headers
        
        pmp_wimax_datatable_headers += severity_headers
        pmp_wimax_datatable_headers += pmp_wimax_starting_headers
        pmp_wimax_datatable_headers += common_headers
        
        if SHOW_CUSTOMER_COUNT_IN_NETWORK_ALERT and page_type == 'network':
            pmp_wimax_datatable_headers += customer_count_header
            ptp_datatable_headers += customer_count_header

        ptp_datatable_headers += region_header            
        ptp_datatable_headers += polled_headers
        ptp_datatable_headers += other_headers


        if page_type == 'customer':
            # These headers are for Alert Center -> Customer Details -> Radwin5K Tab
            rad5_customer_detail_headers += rad5_customer_start_headers
            rad5_customer_detail_headers += region_header
            rad5_customer_detail_headers += polled_headers
            rad5_customer_detail_headers += rad5_other_headers

        pmp_wimax_datatable_headers += rad5_headers
        pmp_wimax_datatable_headers += polled_headers
        pmp_wimax_datatable_headers += rad5_polled_col

        if SHOW_TICKET_NUMBER and page_type == 'network' and data_source == 'down':
            pmp_wimax_datatable_headers += [{'mData': 'ticket_no', 'sTitle': 'Alarm PB TT No.', 'sWidth': 'auto', 'bSortable': True}]

        pmp_wimax_datatable_headers += other_headers

        # Pass bh_datatable_headers only in case of 'network' page
        if page_type == 'network':
            bh_datatable_headers += severity_headers
            bh_datatable_headers += common_headers

            # Add Customer Count Header in Backhaul Tab
            if SHOW_CUSTOMER_COUNT_IN_NETWORK_ALERT:
                bh_datatable_headers += customer_count_header

            bh_datatable_headers += region_header
            bh_datatable_headers += bh_specific_headers
            bh_datatable_headers += polled_headers
            bh_datatable_headers += other_headers

        displayed_ds_name = " ".join(self.kwargs['data_source'].split('_')).title() \
                            if 'data_source' in self.kwargs else ''

        context['ptp_datatable_headers'] = json.dumps(ptp_datatable_headers)
        context['pmp_wimax_datatable_headers'] = json.dumps(pmp_wimax_datatable_headers)
        context['rad5_customer_detail_headers'] = json.dumps(rad5_customer_detail_headers)
        context['bh_datatable_headers'] = json.dumps(bh_datatable_headers)
        context['data_source'] = displayed_ds_name
        context['url_data_source'] = data_source
        context['page_type'] = page_type
        
        return context


class AlertListingTable(BaseDatatableView, AdvanceFilteringMixin):
    """
    Generic Class Based View for the Alert Center Network Listing Tables.

    """
    is_ordered = False
    is_initialised = True
    is_polled = False
    is_searched = False
    is_rad5 = False

    model = EventNetwork
    columns = []
    order_columns = columns

    polled_columns = [
        "id",
        "ip_address",
        "service_name",
        "data_source",
        "device_name",
        "machine_name",
        "severity",
        "current_value",
        "max_value",
        "min_value",
        "sys_timestamp",
        "age",
        "warning_threshold"
    ]

    polled_value_columns = [
        'current_value',
        'min_value',
        'max_value',
        'avg_value',
        'age',
        'sys_timestamp',
        'customer_count'
    ]

    # For saving if else hassle we have used a dict over here
    rad5_polled_col_dict = {
        'packet_drop':[
            {'mData': 'dl_uas', 'sTitle': 'UAS DL', 'sWidth': 'auto', 'bSortable': True, 'bVisible': False},
            {'mData': 'ul_uas', 'sTitle': 'UAS UL', 'sWidth': 'auto', 'bSortable': True, 'bVisible': False}
        ],
        'latency': [
            {'mData': 'dl_utilization', 'sTitle': 'Utilisation DL%', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False},
            {'mData': 'ul_utilization', 'sTitle': 'Utilisation UL%', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
        ],
        'down': [
            {'mData': 'device_uptime', 'sTitle': 'Device Uptime', 'sWidth': 'auto', 'bSortable': False, 'bVisible': False}
        ]
    }

    main_qs = []

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.

        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        else:

            if not len(self.columns):
                self.prepare_initial_params()

            organizations = nocout_utils.logged_in_user_organizations(self)

            return self.get_initial_query_set_data(organizations=organizations)

    def get_initial_query_set_data(self, **kwargs):
        """
        Generic function required to fetch the initial data with respect to 
        the page_type parameter in the get request requested.

        :param kwargs:
        :return: list of devices
        """

        page_type = self.request.GET.get('page_type', 'network')

        other_type = self.request.GET.get('other_type', None)
        is_rad5 = int(self.request.GET.get('is_rad5', 0))

        self.is_rad5 = is_rad5
        
        device_tab_technology = self.request.GET.get('data_tab')

        required_value_list = ['id', 'machine__name', 'device_name', 'ip_address', 'organization__alias']

        if device_tab_technology == 'all':
            devices = list()
            devices += inventory_utils.filter_devices(
                organizations=kwargs['organizations'],
                data_tab='PMP',
                is_rad5=is_rad5,
                page_type=page_type,
                other_type=other_type,
                required_value_list=required_value_list
            )

            devices += inventory_utils.filter_devices(
                organizations=kwargs['organizations'],
                data_tab='WiMAX',
                page_type=page_type,
                other_type=other_type,
                required_value_list=required_value_list
            )
        else:
            devices = inventory_utils.filter_devices(
                organizations=kwargs['organizations'],
                data_tab=device_tab_technology,
                is_rad5=is_rad5,
                page_type=page_type,
                other_type=other_type,
                required_value_list=required_value_list
            )

        self.main_qs = devices

        #machines dict
        machines = inventory_utils.prepare_machines(
            devices,
            machine_key='machine_name'
        )

        # prepare the polled results, this is query set with complete polled result
        perf_results = self.prepare_polled_results(devices, machine_dict=machines)

        return perf_results

    def prepare_devices(self, qs):
        """

        :param qs:
        :return:
        """
        page_type = self.request.GET.get('page_type')
        ticket_number_required = False
        device_tab_technology = self.request.GET.get('data_tab')
        type_rf = None
        data_source = self.request.GET.get('data_source', '')
        tech_list = DeviceTechnology.objects.all().values_list('name', flat=True)
        if device_tab_technology != 'all' and (device_tab_technology not in tech_list):
            device_tab_technology = None

            if page_type == 'network':
                type_rf = 'sector'
            elif page_type == 'customer':
                type_rf = 'ss'
            else:
                type_rf = None


        if page_type == 'network' and data_source.lower() == 'down':
            ticket_number_required = True

        # Create instance of 'PerformanceUtilsGateway' class
        perf_utils = PerformanceUtilsGateway()

        device_name_list = list()
        device_ip_list = list()

        # GET all device name list and device ip list from the list
        for device in qs:
            device_name_list.append(device.get('device_name'))
            device_ip_list.append(device.get('ip_address'))

        device_indexed_info = perf_utils.indexed_polled_results(self.main_qs)
        # Mapped device id with qs
        for data in qs:
            device_name = data['device_name']
            device_info = device_indexed_info[device_name]
            device_id = device_info.get('id')
            if device_id:
                data.update(id=device_id)

        resultant_data = list()
        if device_tab_technology == 'all':
            resultant_data = perf_utils.prepare_gis_devices_optimized(
                qs,
                page_type=page_type,
                technology='PMP',
                type_rf=type_rf,
                device_name_list=device_name_list,
                device_ip_list=device_ip_list,
                ticket_required=ticket_number_required
            )
            resultant_data = perf_utils.prepare_gis_devices_optimized(
                resultant_data,
                page_type=page_type,
                technology='WiMAX',
                type_rf=type_rf,
                device_name_list=device_name_list,
                device_ip_list=device_ip_list,
                ticket_required=ticket_number_required
            )
        else:
            resultant_data = perf_utils.prepare_gis_devices_optimized(
                qs,
                page_type=page_type,
                technology=device_tab_technology,
                type_rf=type_rf,
                device_name_list=device_name_list,
                device_ip_list=device_ip_list,
                ticket_required=ticket_number_required
            )

        return resultant_data

    def prepare_polled_results(self, qs, machine_dict=None, multi_proc=False):
        """
        preparing polled results
        after creating static inventory first
        :param machine_dict:
        :param qs:
        :param multi_proc: multiprocessing module introduced
        """
        data_source = self.request.GET.get('data_source')
        device_technology = self.request.GET.get('data_tab', '')

        device_list, data_sources_list = list(), list()

        search_table = "performance_networkstatus"
        severity_condition = ' AND `{0}`.`severity` in ("down","warning","critical","warn","crit") '

        extra_query_condition = None
        is_customer_detail_page = False

        secondary_table_info = None

        if data_source in ['latency']:
            extra_query_condition = ' AND (`{0}`.`current_value` > 0 ) '
            extra_query_condition += severity_condition
            data_sources_list = ['rta']
        elif data_source in ['packet_drop']:
            data_sources_list = ['pl']
            extra_query_condition = ' AND (`{0}`.`current_value` BETWEEN 0 AND 99 ) '
            extra_query_condition += severity_condition
        elif data_source in ['down']:
            data_sources_list = ['pl']
            extra_query_condition = ' AND (`{0}`.`current_value` >= 100 ) '
            extra_query_condition += ' AND `{0}`.`severity` in ("down", "critical") '
        elif data_source in ['service', 'customer']:
            is_customer_detail_page = True
            extra_query_condition = severity_condition
            search_table = "performance_servicestatus"

            # In case of Radwin5k Customer details
            # We also have to monitor KPI services from performance_utilizationstatus table
            if self.is_rad5:
                # In case of Radwin5k secondary table info also needs to be passed.
                # Result of this table needs to be unioned with 1st table
                secondary_table_info = {
                    'table_name': 'performance_utilizationstatus',
                    'data_source': ["rad5k_ss_dl_util_kpi", "rad5k_ss_ul_util_kpi"],
                    'condition': severity_condition
                }



        required_data_columns = self.polled_columns

        sorted_device_list = alert_utils.polled_results(
            multi_proc=MULTI_PROCESSING_ENABLED,
            machine_dict=machine_dict,
            table_name=search_table,
            data_sources=data_sources_list,
            columns=required_data_columns,
            condition=extra_query_condition if extra_query_condition else None,
            secondary_table_info=secondary_table_info
        )

        return sorted_device_list

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return queryset
        """
        

        if qs:
            data_unit = "%"
            service_tab = 'down'
            # figure out which tab call is made.
            data_source = self.request.GET.get('data_source', '')
            page_type = self.request.GET.get('page_type')
            if 'latency' == data_source:
                service_tab = 'latency'
                data_unit = "ms"
            elif 'packet_drop' == data_source:
                service_tab = 'packet_drop'
            elif 'service' == data_source:
                data_unit = ''
                service_tab = 'service'

            #figure out which scheduling type should be displayed according to the page type
            if page_type == 'customer':
                scheduling_type = ['devi', 'dety', 'cust']
            elif page_type == 'network' and 'backhaul' not in data_source.lower():
                scheduling_type = ['devi', 'dety', 'netw']
            elif 'backhaul' in data_source.lower():
                scheduling_type = ['devi', 'dety', 'back']
            else:
                scheduling_type = ['devi', 'dety', 'cust', 'netw', 'back']

            is_rad5 = int(self.request.GET.get('is_rad5', 0))
            min_latency = ''
            dl_uas = ''
            ul_uas = ''
            dl_utilization = ''
            ul_utilization = ''
            device_uptime = ''
            for dct in qs:
                try:                
                    dct_device_name = dct.get('device_name')
                    dct_device_type = dct.get('device_type')
                except Exception, err:
                    pass

                perf_utils = PerformanceUtilsGateway()
                # for getting SE to PE min. latency
                if is_rad5:
                    device_id = dct.get('id', 0)


                    min_latency = perf_utils.get_se_to_pe_min_latency(device_id, page_type)

                    # getting extra columns for rad5 devices
                    if page_type == 'customer':
                        try:
                            # machine_name = Machine.objects.get(id=dct.get('machine_id')).name
                            machine_name = dct.get('machine_name')
                        except Exception, e:
                            machine_name = ''

                        if data_source == 'packet_drop':
                            # Machine name for each device
                            # getting UAS DL and UAS UL for each device
                            dl_uas = ServiceStatus.objects.filter(
                                ip_address=dct.get('ip_address', None),
                                service_name='rad5k_ss_dl_uas',
                                data_source='dl_uas'
                            ).using(
                                machine_name
                            )

                            if dl_uas.exists():
                                dl_uas = dl_uas[0].current_value

                            ul_uas = ServiceStatus.objects.filter(
                                    ip_address=dct.get('ip_address', None),
                                    service_name='rad5k_ss_ul_uas',
                                    data_source='ul_uas'
                            ).using(
                                machine_name
                            )

                            if ul_uas.exists():
                                ul_uas = ul_uas[0].current_value

                        elif data_source == 'latency':

                            dl_utilization = UtilizationStatus.objects.filter(
                                    ip_address=dct.get('ip_address', None),
                                    service_name='radwin5k_ss_dl_util_kpi',
                                    data_source='rad5k_ss_dl_util_kpi'
                                ).using(machine_name)

                            if dl_utilization.exists():
                                dl_utilization = dl_utilization[0].current_value

                            ul_utilization = UtilizationStatus.objects.filter(
                                    ip_address=dct.get('ip_address', None),
                                    service_name='radwin5k_ss_ul_util_kpi',
                                    data_source='rad5k_ss_ul_util_kpi'
                                ).using(machine_name)

                            if ul_utilization.exists():
                                ul_utilization = ul_utilization[0].current_value
                        elif data_source == 'down':

                            device_uptime = ServiceStatus.objects.filter(
                                    ip_address=dct.get('ip_address', None),
                                    service_name='rad5k_ss_device_uptime',
                                    data_source='uptime'
                                ).using(machine_name)

                            if device_uptime.exists():
                                device_uptime_raw = device_uptime[0].current_value
                                device_uptime = display_time(device_uptime_raw)
                        else:
                            pass

                showIconBlue = scheduling_utils.get_onDate_status(
                    dct_device_name,
                    dct_device_type,
                    scheduling_type
                )

                try:
                    planned_events = nocout_utils.get_current_planned_event_ips(
                        ip_address=dct['ip_address'],
                        check_sector=False
                    )
                    if planned_events:
                        showIconBlue = True
                except Exception as e:
                    pass

                if showIconBlue:
                    dct.update(severity= 'inDownTime')
                    dct.update(description= 'inDownTime')
                try:
                    dct.update(current_value=float(dct["current_value"]))
                except Exception, e:
                    pass 

                performance_url = reverse(
                    'SingleDevicePerf',
                    kwargs={
                        'page_type': page_type, 
                        'device_id': dct.get('id', 0)
                    },
                    current_app='performance'
                )

                alert_url = reverse(
                    'SingleDeviceAlertsInit',
                    kwargs={
                        'page_type': page_type, 
                        'data_source' : service_tab, 
                        'device_id': dct.get('id', 0)
                    },
                    current_app='alert_center'
                )

                inventory_url = reverse(
                    'device_edit',
                    kwargs={
                        'pk': dct.get('id', 0)
                    },
                    current_app='device'
                )

                try:
                    dct.update(
                        sys_timestamp=datetime.datetime.fromtimestamp(dct.get('sys_timestamp')).strftime(DATE_TIME_FORMAT) if dct.get('sys_timestamp') else "",
                        age=datetime.datetime.fromtimestamp(dct.get('age')).strftime(DATE_TIME_FORMAT) if dct.get('age') else "",
                        min_latency=min_latency if min_latency else 'N/A',
                        dl_uas=dl_uas if dl_uas else 'N/A',
                        ul_uas=ul_uas if ul_uas else 'N/A',
                        dl_utilization=dl_utilization if dl_utilization else 'N/A',
                        ul_utilization=ul_utilization if ul_utilization else 'N/A',
                        device_uptime=device_uptime if device_uptime else 'N/A',
                        action='<a href="' + alert_url + '" title="Device Alerts">\
                                <i class="fa fa-warning text-warning"></i></a>\
                                <a href="' + performance_url + '" title="Device Performance">\
                                <i class="fa fa-bar-chart-o text-info"></i></a>\
                                <a href="' + inventory_url + '" title="Device Inventory">\
                                <i class="fa fa-dropbox text-muted"></i></a>'
                    )
                except Exception, e:
                    dct.update(
                        action='<a href="' + alert_url + '" title="Device Alerts">\
                                <i class="fa fa-warning text-warning"></i></a>\
                                <a href="' + performance_url + '" title="Device Performance">\
                                <i class="fa fa-bar-chart-o text-info"></i></a>\
                                <a href="' + inventory_url + '" title="Device Inventory">\
                                <i class="fa fa-dropbox text-muted"></i></a>'
                    )

                dct = alert_utils.common_prepare_results(dct)

            return qs

        return []

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        :param qs:
        :return result_list:
        """
        sSearch = self.request.GET.get('search[value]', None)
        
        if sSearch:
            self.is_initialised = False
            self.is_searched = True
            result = self.prepare_devices(qs)
            result_list = list()
            for item in result:
                try:
                    dict_values_str_list = [str(i) for i in item.values()]
                    dict_values_string = ', '.join(dict_values_str_list).lower()
                    sSearch = sSearch.lower()
                except Exception, e:
                    dict_values_string = item.values()
                    sSearch = sSearch
                if sSearch in dict_values_string :
                    result_list.append(item)

            return self.advance_filter_queryset(result_list)
        return self.advance_filter_queryset(qs)

    def ordering(self, qs):
        """
        sorting for the table
        :param qs:
        """
        # Number of columns that are used in sorting
        sorting_cols = 0
        if self.pre_camel_case_notation:
            try:
                sorting_cols = int(self._querydict.get('iSortingCols', 0))
            except ValueError:
                sorting_cols = 0
        else:
            sort_key = 'order[{0}][column]'.format(sorting_cols)
            while sort_key in self._querydict:
                sorting_cols += 1
                sort_key = 'order[{0}][column]'.format(sorting_cols)

        order = []
        order_columns = self.get_order_columns()

        sort_using = ''
        reverse = ''

        for i in range(sorting_cols):
            # sorting column
            sort_dir = 'asc'
            try:
                if self.pre_camel_case_notation:
                    sort_col = int(self._querydict.get('iSortCol_{0}'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('sSortDir_{0}'.format(i))
                else:
                    sort_col = int(self._querydict.get('order[{0}][column]'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('order[{0}][dir]'.format(i))
            except ValueError:
                sort_col = 0

            sdir = '-' if sort_dir == 'desc' else ''
            reverse = True if sort_dir == 'desc' else False
            sortcol = order_columns[sort_col]
            sort_using = order_columns[sort_col]

            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('{0}{1}'.format(sdir, sc.replace('.', '__')))
            else:
                order.append('{0}{1}'.format(sdir, sortcol.replace('.', '__')))
        if order and sort_using:
            self.is_initialised = False
            self.is_ordered = True
            try:
                sort_data = self.prepare_devices(qs)
                if sort_using in self.polled_value_columns:
                    sorted_qs = sorted(sort_data, key=lambda data: float(data[sort_using]), reverse=reverse)
                else:
                    sorted_qs = sorted(
                        sort_data,
                        key=lambda data: unicode(data[sort_using]).strip().lower() if data[sort_using] not in [None] else data[sort_using],
                        reverse=reverse
                    )
                return sorted_qs

            except Exception, e:
                self.is_initialised = True
                self.is_ordered = False
                self.is_polled = False
                return qs
        else:
            return qs

    def find_order_columns(self, page_type='network', data_source='packet_drop', data_tab=None):
        """
        This method will return column list in which order sorting will work
        """

        is_rad5 = int(self.request.GET.get('is_rad5', 0))
        
        # Getting key for searching in col_dict 
        if data_tab in ['WiMAX', 'PMP', 'all']:
            # case handling for Customer alert details page, as there is no Data source
            if is_rad5 and data_source == 'customer':
                header_key = 'rad5_customer_detail_headers' if is_rad5 else 'pmp_wimax_datatable_headers'
            else:
                header_key = 'pmp_wimax_datatable_headers'
        elif data_tab == 'P2P':
            header_key = 'ptp_datatable_headers'
        else:
            header_key = 'bh_datatable_headers'

        # Changing data source according to right keys in col_dict in case of Backhaul
        if data_source in ['packet_drop', 'Backhaul_PD']:
            data_source = 'packet_drop'
        elif data_source in ['down', 'Backhaul_Down']:
            data_source = 'down'
        elif data_source in ['latency', 'Backhaul_RTA']:
            data_source = 'latency'
        else:
            # data_source = '' 
            pass

        # Common Network Datatable headers used in ordering
        common_network_ptp_headers = [
            'severity',
            'circuit_id',
            'customer_name',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state',
        ]

        common_network_bh_headers = [
            'severity',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state',
        ]
        
        common_network_pmp_wimax_headers = [
            'severity',
            'sector_id',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state'
        ]
        
        if SHOW_CUSTOMER_COUNT_IN_NETWORK_ALERT:             
            common_network_pmp_wimax_headers += ['customer_count']
            common_network_bh_headers += ['customer_count']
            common_network_ptp_headers += ['customer_count']

        common_network_pmp_wimax_headers += [
            'region',
            'current_value',
        ]

        common_network_ptp_headers += [
            'region'
        ]

        common_network_bh_headers += [   
            'region',
            'bh_connectivity',
            'current_value'
        ]

        # Common Customer Datatable headers used in ordering
        common_customer_ptp_headers = [
            'severity',
            'circuit_id',
            'customer_name',
            'near_end_ip',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state',
            'region',
            'current_value',
        ]

        common_customer_pmp_wimax_headers = [
            'severity',
            'sector_id',
            'circuit_id',
            'customer_name',
            'near_end_ip',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state'
        ]

        region_header = [
            'region',
        ]


        network_pd_and_down_ptp_datatable_headers = common_network_ptp_headers + ['current_value', 'sys_timestamp', 'age', 'action']
        network_pd_and_down_bh_datatable_headers = common_network_bh_headers +  ['sys_timestamp', 'age', 'action']
        customer_pd_and_down_ptp_datatable_headers = common_customer_ptp_headers + ['sys_timestamp', 'age', 'action']

        col_dict = {
            'network' : {
                'packet_drop' : {
                    'ptp_datatable_headers': network_pd_and_down_ptp_datatable_headers,
                    'bh_datatable_headers': network_pd_and_down_bh_datatable_headers,
                    'pmp_wimax_datatable_headers': common_network_pmp_wimax_headers + ['sys_timestamp', 'age', 'action']
                },

                'down' : {
                    'ptp_datatable_headers': network_pd_and_down_ptp_datatable_headers,
                    'bh_datatable_headers': network_pd_and_down_bh_datatable_headers,
                    'pmp_wimax_datatable_headers': common_network_pmp_wimax_headers + ['ticket_no', 'sys_timestamp', 'age', 'action']
                },

                'latency' : {
                    'ptp_datatable_headers': common_network_ptp_headers + ['current_value', 'max_value', 'min_value', 'sys_timestamp', 'age', 'action'],
                    'bh_datatable_headers': common_network_bh_headers + ['max_value', 'min_value', 'sys_timestamp', 'age', 'action'],
                    'pmp_wimax_datatable_headers': common_network_pmp_wimax_headers + ['max_value', 'min_value', 'sys_timestamp', 'age', 'action']
                }
            }, 
            'customer' : {
                # case handling for Customer alert details page, there is no Data source
                'customer' : {
                    'ptp_datatable_headers': common_network_ptp_headers + ['data_source_name', 'current_value', 'sys_timestamp', 'age', 'action'],
                    'bh_datatable_headers': [],
                    'pmp_wimax_datatable_headers': common_customer_pmp_wimax_headers+region_header+['data_source_name', 'current_value', 'sys_timestamp', 'age', 'action'],
                    'rad5_customer_detail_headers': common_customer_pmp_wimax_headers + region_header + [
                                                                                                            'data_source_name', 'current_value',
                                                                                                            'sys_timestamp', 'age', 'warning_threshold', 'action'
                                                                                                        ]
                },
                'packet_drop' : {
                    'ptp_datatable_headers': customer_pd_and_down_ptp_datatable_headers,
                    'bh_datatable_headers': [],
                    'pmp_wimax_datatable_headers': common_customer_pmp_wimax_headers+region_header+ [
                                                                                                        'current_value', 'dl_uas', 'ul_uas',
                                                                                                        'sys_timestamp', 'age', 'action'
                                                                                                    ]
                },
                'down' : {
                    'ptp_datatable_headers': customer_pd_and_down_ptp_datatable_headers,
                    'bh_datatable_headers': [],
                    'pmp_wimax_datatable_headers': common_customer_pmp_wimax_headers+region_header+['current_value', 'device_uptime', 'sys_timestamp', 'age', 'action']
                },
                'latency' : {
                    'ptp_datatable_headers': common_customer_ptp_headers + ['max_value', 'min_value', 'sys_timestamp', 'age', 'action'],
                    'bh_datatable_headers': [],
                    'pmp_wimax_datatable_headers': common_customer_pmp_wimax_headers+region_header+['min_latency', 'current_value', 'max_value', 'min_value', 
                                                                                        'dl_utilization', 'ul_utilization', 'sys_timestamp', 'age', 'action']
                }
            }
        }

        # returning right columns for ordering
        return col_dict.get(page_type, {}).get(data_source, {}).get(header_key)

    def prepare_initial_params(self):
        """
        The function prepares the columns & order_columns as per kwargs & 
        get params used in all function within the class
        """

        page_type = self.request.GET.get('page_type', 'network')
        data_source = self.request.GET.get('data_source', 'packet_drop')
        data_tab = self.request.GET.get('data_tab', 'P2P')

        severity_columns = [
            'severity'
        ]
        ckt_customer_column = [
            'circuit_id',
            'customer_name'
        ]
        common_columns = [
            'ip_address', 
            'device_type', 
            'bs_name', 
            'city', 
            'state'
        ]

        is_rad5 = int(self.request.GET.get('is_rad5', 0))

        rad5_columns = []

        starting_columns = []
        tkt_column = []
        if data_tab in ['P2P', 'PTP', 'PTP-BH', 'PTP_BH']:
            starting_columns += ckt_customer_column
        else:
            starting_columns += ['sector_id']
            if page_type == 'network' and data_source == "down":
                tkt_column += ['ticket_no']

        if page_type == 'customer':
            near_ip_column = ['near_end_ip']

            if data_tab not in ['P2P', 'PTP', 'PTP-BH', 'PTP_BH']:
                starting_columns += ckt_customer_column

            starting_columns += near_ip_column

        polled_columns = []

        # if customer alert detail page
        if not data_source or data_source == "customer":
            polled_columns += ["data_source_name"]

        polled_columns += ['current_value']

        if data_source == "latency":
            polled_columns += [
                'max_value',
                'min_value'
            ]
        other_columns = []
        
        if data_tab in ['PMP', 'WiMAX', 'all'] and SHOW_CUSTOMER_COUNT_IN_NETWORK_ALERT:
            other_columns = ['customer_count']

        other_columns += tkt_column
        other_columns += [
            'sys_timestamp',
            'age',
            'action'
        ]

        if is_rad5:
            rad5_columns += ['region']
 
        self.columns = []
        self.columns += severity_columns
        self.columns += starting_columns
        self.columns += common_columns
        self.columns += rad5_columns
        self.columns += polled_columns
        self.columns += other_columns
        
        self.order_columns = self.find_order_columns(page_type, data_source, data_tab)

        return True

    def get_context_data(self, *args, **kwargs):
        """
        The maine function call to fetch, search, prepare and display the data on the data table.

        :param kwargs:
        :param args:
        """

        request = self.request
        self.initialize(*args, **kwargs)

        if not len(self.columns):
            self.prepare_initial_params()

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = len(qs)

        # filtering the query set
        qs = self.filter_queryset(qs)

        # number of records after filtering
        total_display_records = len(qs)

        # order by column
        qs = self.ordering(qs)

        # pagination enabled
        qs = self.paging(qs)

        if self.is_initialised and not (self.is_searched or self.is_ordered):
            #this function is for mapping to GIS inventory
            qs = self.prepare_devices(qs)


        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret


class NetworkAlertDetailHeaders(ListView):
    """
    A generic class view for the network alert details view

    """
    model = EventNetwork
    template_name = 'alert_center/network_alert_details_list.html'

    def get_context_data(self, **kwargs):

        """

        :param kwargs:
        :return:
        """
        starting_headers = [
            {'mData': 'severity', 'sTitle': '', 'sWidth': '40px', 'bSortable': True}
        ]

        # Region and organization are same but we need two different headers becuase
        # Util Columns are fecthed from Capacity Management module
        region_header = [
            {'mData': 'region', 'sTitle': 'Region', 'sWidth': 'auto', 'bSortable': True}
        ]

        organization_header = [
            {'mData': 'organization__alias', 'sTitle': 'Region', 'sWidth': 'auto', 'bSortable': True}
        ]

        rad5_starting_headers = [
            {'mData': 'device_technology', 'sTitle': 'Technology', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'site_id', 'sTitle': 'Site ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'refer', 'sTitle': 'Affected Sectors', 'sWidth': 'auto', 'bSortable': True},
        ]

        rad5_specific_headers = []

        # rad5_specific_headers += [
        #     {'mData': 'customer_count', 'sTitle': 'Total Customer Count', 'sWidth': 'auto', 'bSortable': True},
        #     {'mData': 'impacted_customer', 'sTitle': 'Impacted Customer Count', 'sWidth': 'auto', 'bSortable': True},
        #     {'mData': 'impacted_customer_percent', 'sTitle': '% Impacted Customer Count', 'sWidth': 'auto', 'bSortable': True},
        # ]

        specific_headers = [
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'customer_name', 'sTitle': 'Customer', 'sWidth': 'auto', 'bSortable': True}
        ]

        ul_issue_specific_headers = [
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'refer', 'sTitle': 'Affected Sectors', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'customer_name', 'sTitle': 'Customer', 'sWidth': 'auto', 'bSortable': True}
            # {'mData': 'customer_count', 'sTitle': 'Customer Count', 'sWidth': 'auto', 'bSortable': True}
        ]

        ul_issue_specific_headers_2 = [
            {'mData': 'customer_count', 'sTitle': 'Customer Count', 'sWidth': 'auto', 'bSortable': True}
        ]

        bh_dt_specific_headers = [
            {'mData': 'bh_alias', 'sTitle': 'BH Alias', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_port', 'sTitle': 'BH Port Name', 'sWidth': 'auto', 'bSortable': True}
        ]

        common_headers = [
            {'mData': 'ip_address', 'sTitle': 'IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'device_type', 'sTitle': 'Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_name', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'city', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'state', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': True}
        ]

        bh_specific_headers = [
            {'mData': 'bh_connectivity', 'sTitle': 'Onnet/Offnet', 'sWidth': 'auto', 'bSortable': True}
        ]

        polled_headers = [
            {'mData': 'data_source_name', 'sTitle': 'Data Source Name', 'sWidth': 'auto', 'bSortable': True},
            # {'mData': 'customer_count', 'sTitle': 'Customer Count', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'current_value', 'sTitle': 'Value', 'sWidth': 'auto',
             'bSortable': True, "sSortDataType": "dom-text", "sType": "numeric"}
        ]

        other_headers = [
            {'mData': 'sys_timestamp', 'sTitle': 'Timestamp', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'age', 'sTitle': 'Status Since', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'action', 'sTitle': 'Action', 'sWidth': 'auto', 'bSortable': False}
        ]

        datatable_headers = []
        datatable_headers += starting_headers
        datatable_headers += specific_headers
        datatable_headers += common_headers
        datatable_headers += region_header
        datatable_headers += polled_headers
        datatable_headers += other_headers

        backhaul_headers = []
        backhaul_headers += starting_headers
        # backhaul_headers += specific_headers
        backhaul_headers += common_headers
        backhaul_headers += region_header
        backhaul_headers += bh_specific_headers
        backhaul_headers += polled_headers
        backhaul_headers += other_headers

        rad5_ul_issue_headers = []
        rad5_ul_issue_headers += starting_headers
        rad5_ul_issue_headers += rad5_starting_headers
        rad5_ul_issue_headers += common_headers
        rad5_ul_issue_headers += region_header
        rad5_ul_issue_headers += rad5_specific_headers
        rad5_ul_issue_headers += polled_headers
        rad5_ul_issue_headers += other_headers

        ul_issue_datatable_headers = []
        ul_issue_datatable_headers += starting_headers
        ul_issue_datatable_headers += ul_issue_specific_headers
        ul_issue_datatable_headers += common_headers
        ul_issue_datatable_headers += region_header
        ul_issue_datatable_headers += polled_headers
        if SHOW_CUSTOMER_COUNT_IN_ALERT_LIST:
            ul_issue_datatable_headers += ul_issue_specific_headers_2
        ul_issue_datatable_headers += other_headers

        bh_dt_headers = []
        bh_dt_headers += starting_headers
        bh_dt_headers += bh_dt_specific_headers
        bh_dt_headers += common_headers
        bh_dt_headers += region_header
        bh_dt_headers += polled_headers
        bh_dt_headers += other_headers

        # Sector Utilization Headers
        sector_util_hidden_headers = [
            {'mData': 'id', 'sTitle': 'Device ID', 'sWidth': 'auto', 'sClass': 'hide', 'bSortable': True},
            {'mData': 'sector__sector_id', 'sTitle': 'Sector', 'sWidth': 'auto', 'sClass': 'hide', 'bSortable': True},
            # {'mData': 'organization__alias', 'sTitle': 'Organization', 'sWidth': 'auto', 'sClass': 'hide', 'bSortable': True},
        ]

        sector_util_headers_1 = [
            {'mData': 'sector__base_station__alias', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sector__base_station__city__city_name', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sector__base_station__state__state_name', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': True},
        ]

        sector_util_headers_2 = [
            {'mData': 'sector__sector_configured_on__ip_address', 'sTitle': 'BS IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sector__sector_configured_on__device_technology', 'sTitle': 'Technology', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sector_sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'current_out_per', 'sTitle': '% UL Utilization', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'current_in_per', 'sTitle': '% DL Utilization', 'sWidth': 'auto', 'bSortable': True},
        ]

        sector_util_headers_3 = [
            {'mData': 'severity', 'sTitle': 'Status', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'age', 'sTitle': 'Aging (seconds)', 'sWidth': 'auto', 'bSortable': True},
        ]

        sector_util_common_headers = sector_util_headers_1 + organization_header + sector_util_headers_2 + sector_util_headers_3

        sector_utils_headers = []
        sector_utils_headers += sector_util_hidden_headers
        sector_utils_headers += sector_util_common_headers

        rad5_sector_util_headers = []
        rad5_sector_util_headers += sector_util_headers_1
        rad5_sector_util_headers += organization_header
        rad5_sector_util_headers += sector_util_headers_2
        rad5_sector_util_headers += [
            {'mData': 'timeslot_dl', 'sTitle': 'DL Time-slot', 'width': 'auto', 'bSortable': True },
            {'mData': 'timeslot_ul', 'sTitle': 'UL Time-slot', 'width': 'auto', 'bSortable': True },
        ]
        rad5_sector_util_headers += sector_util_headers_3
        rad5_sector_util_headers += [{'mData': 'sector__base_station__bs_site_id', 'sTitle': 'Site ID', 'sWidth': 'auto', 'bSortable': True},]

        bh_util_hidden_headers = [
            {'mData': 'id', 'sTitle': 'Device ID', 'sWidth': 'auto', 'sClass': 'hide', 'bSortable': True},
        ]

        bh_util_common_headers_1 = [
            {'mData': 'backhaul__bh_configured_on__ip_address', 'sTitle': 'BH IP', 'sWidth': 'auto', 'bSortable': True},
            # {'mData': 'backhaul__alias', 'sTitle': 'Backhaul', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'basestation__alias', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_port_name', 'sTitle': 'Configured On Port', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'backhaul__bh_configured_on__device_technology', 'sTitle': 'Technology', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'basestation__city__city_name', 'sTitle': 'BS City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'basestation__state__state_name', 'sTitle': 'BS State', 'sWidth': 'auto', 'bSortable': True},
        ]

        bh_util_common_headers_2 = [
            {'mData': 'severity', 'sTitle': 'Status', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'age', 'sTitle': 'Aging', 'sWidth': 'auto', 'bSortable': True},
        ]

        bh_util_common_headers = bh_util_common_headers_1 + organization_header + bh_util_common_headers_2

        bh_utils_headers = []
        bh_utils_headers += bh_util_hidden_headers
        bh_utils_headers += bh_util_common_headers

        context = {
            'datatable_headers': json.dumps(datatable_headers),
            'backhaul_headers': json.dumps(backhaul_headers),
            'bh_utils_headers': json.dumps(bh_utils_headers),
            'ul_issue_headers': json.dumps(ul_issue_datatable_headers),
            'bh_headers': json.dumps(bh_dt_headers),
            'sector_utils_headers': json.dumps(sector_utils_headers),
            'rad5_ul_issue_headers': json.dumps(rad5_ul_issue_headers),
            'rad5_sector_util_headers': json.dumps(rad5_sector_util_headers)
        }

        return context


class GetNetworkAlertDetail(BaseDatatableView, AdvanceFilteringMixin):
    """
    
    Generic Class Based View for the Alert Center Network  Detail Listing Tables.
    """
    is_ordered = False
    is_polled = False
    is_searched = False
    is_initialised = True
    is_rad5 = False
    # Temp flag for distinguishing features of sprint 3(Radwin5K)
    s3_feature = False

    model = EventNetwork
    columns = [
        'device_name',
        'device_type',
        'machine_name',
        'site_name',
        'ip_address',
        'severity',
        'current_value',
        'sys_time',
        'sys_date',
        'description'
    ]

    order_columns = []

    polled_columns = [
        "id",
        "ip_address",
        "service_name",
        "device_name",
        "data_source",
        "severity",
        "current_value",
        "max_value",
        "min_value",
        "sys_timestamp",
        "age",
        "warning_threshold"
    ]

    data_sources = []
    table_name = "performance_servicestatus"

    polled_value_columns = [
        'customer_count',
        'min_value',
        'max_value',
        'current_value',
        'avg_value',
        'age',
        'sys_timestamp'
    ]

    main_qs = []
    NA_list = ['NA', 'N/A', 'na', 'n/a'] 

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.

        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        organizations = nocout_utils.logged_in_user_organizations(self)

        required_value_list = ['id', 'machine__name', 'device_name', 'ip_address', 'organization__alias']

        page_type = self.request.GET.get('page_type', "network")
        include_pe = self.request.GET.get('include_pe', False)

        if self.request.GET.get("data_source"):
            tab_id = self.request.GET.get("data_source")
        else:
            return []

        is_bh = False
        is_other = False
        other_type = "backhaul"

        if tab_id:
            device_list = []
            if tab_id == "P2P":
                technology = [tab_id]
            elif tab_id in "WiMAX":
                technology = [tab_id]
            elif tab_id == "PMP":
                technology = [tab_id]
                self.s3_feature = not SHOW_SPRINT3
            elif tab_id == "Temperature":
                # for handelling the temperature alarms
                # temperature alarms would be for WiMAX
                technology = ["WiMAX"]
                self.data_sources = ['fan_temp', 'acb_temp']
            elif tab_id == "Temperature_bh":
                is_bh = True
                technology = None
                page_type = "other"
                self.data_sources = ['temperature']
            elif tab_id == "WiMAXULIssue":
                # technology = [int(WiMAX.ID), int(PMP.ID)]
                technology = ["WiMAX"]
                self.data_sources = ['pmp1_ul_issue', 'pmp2_ul_issue']
                self.table_name = 'performance_utilizationstatus'
                # Add 'refer column' in case of ULIssue
                self.polled_columns.append('refer')
            elif tab_id == "PMPULIssue":
                # technology = [int(WiMAX.ID), int(PMP.ID)]
                technology = ["PMP"]
                self.data_sources = ['bs_ul_issue']
                self.table_name = 'performance_utilizationstatus'
                self.s3_feature = not SHOW_SPRINT3
                # Add 'refer column' in case of ULIssue
                self.polled_columns.append('refer')
            elif tab_id == "RAD5ULIssue":
                # technology = [int(WiMAX.ID), int(PMP.ID)]
                technology = ["PMP"]
                self.data_sources = ['bs_ul_issue']
                self.table_name = 'performance_utilizationstatus'
                self.is_rad5 = True
                self.s3_feature = not SHOW_SPRINT3
                # Add 'refer column' in case of ULIssue
                self.polled_columns.append('refer')
            elif tab_id in ["Backhaul"]:
                technology = None
                is_bh = True
                page_type = "other"
                self.table_name = 'performance_networkstatus'
                self.data_sources = ''
                # Onnet/Offnet column added for Backhaul tab
                self.columns.append("bh_connectivity")
            elif tab_id in ["Backhaul_Down", "Backhaul_PD", "Backhaul_RTA"]:
                technology = None
                is_bh = True
                page_type = "other"
                is_other = False
                self.table_name = 'performance_networkstatus'
                self.data_sources = ''
                # Onnet/Offnet column added for Backhaul tab
                self.columns.append("bh_connectivity")    
            else:
                return []

            if not is_bh:
                for techno in technology:
                    device_list += inventory_utils.filter_devices(
                        organizations=organizations,
                        is_rad5=self.is_rad5,
                        s3_feature=self.s3_feature,
                        data_tab=techno,
                        page_type=page_type,
                        required_value_list=required_value_list
                    )
            else:
                device_list += inventory_utils.filter_devices(
                    organizations=organizations,
                    data_tab=None,
                    page_type=page_type,
                    required_value_list=required_value_list,
                    other_type=other_type
                )

                device_list += inventory_utils.filter_devices(
                    organizations=organizations,
                    page_type='pe',
                    required_value_list=required_value_list,
                    other_type=other_type
                )

                if is_other:
                    other_type = "other"
                    device_list += inventory_utils.filter_devices(
                        organizations=organizations,
                        data_tab=None,
                        page_type=page_type,
                        required_value_list=required_value_list,
                        other_type=other_type
                    )

            self.main_qs = device_list

            # machines dict
            machines = inventory_utils.prepare_machines(device_list, machine_key='machine_name')

            # prepare the polled results
            perf_results = self.prepare_polled_results(device_list, machine_dict=machines)

            return perf_results

        else:
            return []

    def prepare_polled_results(self, qs, machine_dict=None):
        """
        preparing polled results
        after creating static inventory first
        :param machine_dict:
        :param qs:
        """

        search_table = self.table_name

        extra_query_condition = ' AND `{0}`.`severity` in ("down","warning","critical","warn","crit") '

        # Add extra condition for UL Issues listing
        # if self.data_sources and 'ul_issue' in ', '.join(self.data_sources):
        #     extra_query_condition += " AND `{0}`.`current_value` > 0 "

        get_param = self.request.GET.get("data_source")

        if get_param:
            if get_param in ["Backhaul_Down"]:
                extra_query_condition += " AND `{0}`.`current_value` = 100 AND `{0}`.`data_source` = 'pl'"
            elif get_param in ["Backhaul_PD"]:
                extra_query_condition += " AND `{0}`.`current_value` != 100 AND `{0}`.`data_source` = 'pl'"
            elif get_param in ["Backhaul_RTA"]:
                extra_query_condition += " AND `{0}`.`data_source` = 'rta'"

        sorted_device_list = list()

        sorted_device_list = alert_utils.polled_results(
            multi_proc=MULTI_PROCESSING_ENABLED,
            machine_dict=machine_dict,
            table_name=search_table,
            data_sources=self.data_sources,
            columns=self.polled_columns,
            condition=extra_query_condition if extra_query_condition else None
        )

        return sorted_device_list

    def prepare_devices(self, qs):
        """
        :param perf_results:
        :param qs:
        :return:
        """
        page_type = self.request.GET.get('page_type', "network")
        data_source = self.request.GET.get('data_source')
        type_rf = 'sector'
        device_name_list = list()
        device_tab_technology = ""
        # Flag for checking if customer count has to been shown
        # on basis of Affected Sectors (refer column)
        cust_count_on_affected_sec = False

        if data_source in ['PMPULIssue', 'RAD5ULIssue', 'WiMAXULIssue']:
            cust_count_on_affected_sec = True            

        if data_source in ['PMP', 'P2P', 'WiMAX']:
            device_tab_technology = data_source

        if data_source in ['Temperature', 'WiMAXULIssue']:
            device_tab_technology = 'WiMAX'

        if data_source in ['PMPULIssue', 'RAD5ULIssue']:
            device_tab_technology = 'PMP'

        if data_source in ['Backhaul', 'Temperature_bh', 'Backhaul_PD', 'Backhaul_RTA', 'Backhaul_Down']:
            page_type = 'other'
            type_rf = "backhaul"

        # GET all device name list from the list
        try:
            map(lambda x: device_name_list.append(x['device_name']), qs)
        except Exception, e:
            # logger.info(e.message)
            pass

        # Create instance of 'PerformanceUtilsGateway' class
        perf_utils = PerformanceUtilsGateway()
        device_indexed_info = perf_utils.indexed_polled_results(self.main_qs)
        # Mapped device id with qs
        for data in qs:
            device_name = data['device_name']
            device_info = device_indexed_info[device_name]
            device_id = device_info.get('id')
            if device_id:
                data.update(id=device_id)

        result = perf_utils.prepare_gis_devices_optimized(
            qs,
            page_type=page_type,
            technology=device_tab_technology,
            type_rf=type_rf,
            device_name_list=device_name_list
        )

        if cust_count_on_affected_sec:
            result = self.update_cust_count_for_affected_sector(result)

        return result

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return queryset.
        """
        page_type = self.request.GET.get('page_type', "network")
        ds_param = self.request.GET.get("data_source", '')
        perf_page_type = page_type
        if qs:
            service_tab_name = 'down'
            # In case of backhaul tab update page type to 'other'
            if 'backhaul' in ds_param.lower():
                perf_page_type = 'other'
                try:
                    if ds_param.lower().split("_")[1] == 'rta':
                        service_tab_name = 'latency'
                    elif ds_param.lower().split("_")[1] == 'pl':
                        service_tab_name = 'packet_drop'
                    else:
                        service_tab_name = 'down'
                except Exception, e:
                    service_tab_name = 'down'

            # Get List of IP for which Component is "Sector" in Planned Event Table
            sector_component_ips = PlannedEvent.objects.filter(
                component__iexact='sector'
            ).values_list('resource_name', flat=True)

            for dct in qs:

                # Intialize sector id
                sector_id = ''
                if dct.get('ip_address') in sector_component_ips:
                    # Check sector id is not 'NA'
                    if dct.get('sector_id') not in self.NA_list:
                        sector_id = dct.get('sector_id')

                        # In case of , seperated Sector Id's split it in a list of sector ID
                        # and remove whitespaces
                        sector_id = [x.strip() for x in sector_id.split(',')]

                try:
                    planned_events = nocout_utils.get_current_planned_event_ips(ip_address=dct['ip_address'], sector_id=sector_id)
                    if planned_events:
                        dct['severity'] = 'INDOWNTIME'
                except Exception as e:
                    pass

                dct = alert_utils.common_prepare_results(dct)

                performance_url = reverse(
                    'SingleDevicePerf',
                    kwargs={
                        'page_type': perf_page_type, 
                        'device_id': dct.get('id', 0)
                    },
                    current_app='performance'
                )

                alert_url = reverse(
                    'SingleDeviceAlertsInit',
                    kwargs={
                        'page_type': page_type, 
                        'data_source' : service_tab_name, 
                        'device_id': dct.get('id', 0)
                    },
                    current_app='alert_center'
                )

                inventory_url = reverse(
                    'device_edit',
                    kwargs={
                        'pk': dct.get('id', 0)
                    },
                    current_app='device'
                )

                try:
                    dct.update(
                        sys_timestamp=datetime.datetime.fromtimestamp(dct.get('sys_timestamp')).strftime(DATE_TIME_FORMAT) if dct.get('sys_timestamp') else "",
                        age=datetime.datetime.fromtimestamp(dct.get('age')).strftime(DATE_TIME_FORMAT) if dct.get('age') else "",
                        action='<a href="' + alert_url + '" title="Device Alerts">\
                                <i class="fa fa-warning text-warning"></i></a>\
                                <a href="' + performance_url + '" title="Device Performance">\
                                <i class="fa fa-bar-chart-o text-info"></i></a>\
                                <a href="' + inventory_url + '" title="Device Inventory">\
                                <i class="fa fa-dropbox text-muted"></i></a>'
                    )
                except Exception, e:
                    dct.update(
                        action='<a href="' + alert_url + '" title="Device Alerts">\
                                <i class="fa fa-warning text-warning"></i></a>\
                                <a href="' + performance_url + '" title="Device Performance">\
                                <i class="fa fa-bar-chart-o text-info"></i></a>\
                                <a href="' + inventory_url + '" title="Device Inventory">\
                                <i class="fa fa-dropbox text-muted"></i>\
                                </a>'
                    )

        return qs

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.

        :param qs:
        :return result_list:
        """
        sSearch = self.request.GET.get('search[value]', None)
        if sSearch:
            self.is_initialised = False
            self.is_searched = True
            result = self.prepare_devices(qs)
            result_list = list()
            for search_data in result:
                try:
                    dict_values_str_list = [str(i) for i in search_data.values()]
                    dict_values_string = ', '.join(dict_values_str_list).lower()
                    sSearch = sSearch.lower()
                except Exception, e:
                    dict_values_string = search_data.values()
                    sSearch = sSearch
                if sSearch in dict_values_string :
                    result_list.append(search_data)
            return self.advance_filter_queryset(result_list)
        return self.advance_filter_queryset(qs)

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        :param qs:
        """
        # Initilize order columns variable
        self.prepare_initial_params()

        # Number of columns that are used in sorting
        sorting_cols = 0
        if self.pre_camel_case_notation:
            try:
                sorting_cols = int(self._querydict.get('iSortingCols', 0))
            except ValueError:
                sorting_cols = 0
        else:
            sort_key = 'order[{0}][column]'.format(sorting_cols)
            while sort_key in self._querydict:
                sorting_cols += 1
                sort_key = 'order[{0}][column]'.format(sorting_cols)

        order = []
        order_columns = self.get_order_columns()
        sort_using = ''
        reverse = ''

        for i in range(sorting_cols):
            # sorting column
            sort_dir = 'asc'
            try:
                if self.pre_camel_case_notation:
                    sort_col = int(self._querydict.get('iSortCol_{0}'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('sSortDir_{0}'.format(i))
                else:
                    sort_col = int(self._querydict.get('order[{0}][column]'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('order[{0}][dir]'.format(i))
            except ValueError:
                sort_col = 0

            sdir = '-' if sort_dir == 'desc' else ''
            reverse = True if sort_dir == 'desc' else False
            sortcol = order_columns[sort_col]
            sort_using = order_columns[sort_col]

            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('{0}{1}'.format(sdir, sc.replace('.', '__')))
            else:
                order.append('{0}{1}'.format(sdir, sortcol.replace('.', '__')))

        if order and sort_using:
            sort_data = self.prepare_devices(qs)
            self.is_ordered = True
            try:
                if sort_using in self.polled_value_columns:
                    qs = sorted(sort_data, key=lambda data: float(data[sort_using]), reverse=reverse)
                else:
                    qs = sorted(
                        sort_data,
                        key=lambda data: unicode(data[sort_using]).strip().lower() if data[sort_using] not in [None] else data[sort_using],
                        reverse=reverse
                    )
            except Exception, e:
                pass
        return qs

    def prepare_initial_params(self):
        """
        This function prepares initial params
        """
        data_source = self.request.GET.get('data_source')

        common_network_bh_headers = [
            'severity',
            'ip_address',
            'device_type',
            'bs_name',
            'site_id',
            'city',
            'state',
            'bh_connectivity',
            'current_value'
        ]

        if data_source in ['WiMAXULIssue', 'PMPULIssue']:
            self.order_columns = [
                'severity',
                'sector_id',
                'refer',
                'circuit_id',
                'customer_name',
                'ip_address',
                'device_type',
                'bs_name',
                'city',
                'state',
                'region',
                'data_source_name',
                'current_value',
                'customer_count',
                'sys_timestamp',
                'age'
            ]
        elif data_source in ['RAD5ULIssue']:
            self.order_columns = [
                'severity',
                'device_technology',
                'site_id',
                'sector_id',
                'refer',
                'ip_address',
                'device_type',
                'bs_name',
                'city',
                'state',
                'region',
                # 'customer_count',
                # 'impacted_customer',
                # 'impacted_customer_percent',
                'data_source_name',
                'current_value',
                'sys_timestamp',
                'age',
                'action'
            ]
        elif data_source in ['Backhaul']:
            self.order_columns = [
                'severity',
                'ip_address',
                'device_type',
                'bs_name',
                'city',
                'state',
                'region',
                'bh_connectivity',
                'data_source_name',
                'current_value',
                'sys_timestamp',
                'age'
            ]
        elif data_source in ['Backhaul_PD', 'Backhaul_Down']:
            self.order_columns = common_network_bh_headers + ['sys_timestamp', 'age', 'action']

        elif data_source in ['Backhaul_RTA']:
            self.order_columns = ['sys_timestamp', 'age', 'action'] + ['max_value', 'min_value', 'sys_timestamp', 'age', 'action'],

        elif data_source in ['Temperature_bh']:
            self.order_columns = [
                'severity',
                'bh_alias',
                'bh_port',
                'ip_address',
                'device_type',
                'bs_name',
                'city',
                'state',
                'region',
                'data_source_name',
                'current_value',
                'sys_timestamp',
                'age'
            ]
        else:
            self.order_columns = [
                'severity',
                'sector_id',
                'circuit_id',
                'customer_name',
                'ip_address',
                'device_type',
                'bs_name',
                'city',
                'state',
                'region',
                'data_source_name',
                'current_value',
                'sys_timestamp',
                'age'
            ]

        return True

    def update_cust_count_for_affected_sector(self, qs):
        """
        This function update customer count
        on basis of Affected Sectors
        """

        # Get Queryset to get customer count with respect to sector id's
        customer_count_qs = Customer_Count_Sector.objects.all().values('sector_id', 'count_of_customer')

        for data_row in qs:
            affected_sec_id = data_row.get('refer', '')

            # if there is no Sector ID
            # then do not change customer Count
            if not affected_sec_id:
                continue

            try:
                cust_count = customer_count_qs.get(sector_id=affected_sec_id).get('count_of_customer')
            except Exception, e:
                logger.error('Update Customer Count on basis of Affected Sector error---------------> %s'%e)
                continue

            data_row.update({'customer_count': cust_count})

        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The maine function call to fetch, search, prepare and display the data on the data table.

        :param kwargs:
        :param args:
        """

        request = self.request
        
        self.initialize(*args, **kwargs)

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = len(qs)

        qs = self.filter_queryset(qs)


        # number of records after filtering
        total_display_records = len(qs)

        qs = self.ordering(qs)
        qs = self.paging(qs)

        # if the qs is empty then JSON is unable to serialize the 
        # empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        if not (self.is_ordered or self.is_searched):
            # this function is for mapping to GIS inventory
            qs = self.prepare_devices(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }
        return ret


class SingleDeviceAlertsInit(ListView):
    """
    This class initialize the single device alert page with appropriate params
    """
    model = EventNetwork
    template_name = 'alert_center/single_device_alert.html'

    def get_context_data(self, **kwargs):

        """

        :param kwargs:
        :return:
        """
        data_source = self.kwargs['data_source']
        page_type = self.kwargs['page_type']
        device_id = self.kwargs['device_id']

        context = super(SingleDeviceAlertsInit, self).get_context_data(**kwargs)

        column_list_1 = [
            {"mData": "ip_address", "sTitle": "IP Address", "sWidth": "auto"},
            {"mData": "service_name", "sTitle": "Service Name", "sWidth": "auto"},
        ]

        ds_column_list = [
            {"mData": "data_source", "sTitle": "Data Source", "sWidth": "auto"},
        ]

        polling_alerts_specific_headers = [
            {"mData": "machine_name", "sTitle": "Machine", "sWidth": "auto"},
            {"mData": "site_name", "sTitle": "Site", "sWidth": "auto"},
        ]

        severity_column_list = [
            {"mData": "severity", "sTitle": "Severity", "sWidth": "auto"},
        ]

        current_val_list = [
            {"mData": "current_value", "sTitle": "Current Value", "sWidth": "auto"},
        ]

        column_list_2 = [
            {"mData": "sys_timestamp", "sTitle": "Alert Datetime", "sWidth": "auto"},
            {"mData": "description", "sTitle": "Description", "sWidth": "auto"}
        ]

        ping_specific_columns = [
            {"mData": "latency", "sTitle": "Latency", "sWidth": "auto"},
            {"mData": "packet_loss", "sTitle": "Packet Loss", "sWidth": "auto"},
        ]

        table_headers = []
        table_headers += column_list_1
        table_headers += ds_column_list
        table_headers += severity_column_list
        table_headers += current_val_list
        table_headers += column_list_2

        ping_table_headers = []
        ping_table_headers += column_list_1
        ping_table_headers += severity_column_list
        ping_table_headers += ping_specific_columns
        ping_table_headers += column_list_2

        polling_alerts_table_headers = []
        polling_alerts_table_headers += column_list_1
        polling_alerts_table_headers += polling_alerts_specific_headers
        polling_alerts_table_headers += severity_column_list
        polling_alerts_table_headers += current_val_list
        polling_alerts_table_headers += column_list_2

        device_obj = Device.objects.get(id=device_id)
        device_name = device_obj.device_name
        device_alias = device_obj.device_alias + "(" + device_obj.ip_address + ")"
        #  GET Technology of current device
        device_technology_name = DeviceTechnology.objects.get(id=device_obj.device_technology).name
        
        is_dr_device = device_obj.dr_configured_on.exists()

        is_backhaul = device_obj.backhaul.exists()
        is_backhaul_switch = device_obj.backhaul_switch.exists()
        is_backhaul_pop = device_obj.backhaul_pop.exists()
        is_backhaul_aggregator = device_obj.backhaul_aggregator.exists()
        is_ss = device_obj.substation_set.exists()

        # If device is backhaul or backhaul_switch or backhaul_pop or backhaul_aggregator
        if (is_backhaul or is_backhaul_switch or is_backhaul_pop or is_backhaul_aggregator) and not is_ss:
            page_type = 'other'


        # Create Context Dict
        context['table_headers'] = json.dumps(table_headers)
        context['ping_table_headers'] = json.dumps(ping_table_headers)
        context['polling_alerts_headers'] = json.dumps(polling_alerts_table_headers)
        context['current_device_id'] = device_id
        context['page_type'] = page_type
        context['data_source'] = data_source
        # Device Inventory page url
        context['inventory_page_url'] = reverse(
            'device_edit',
            kwargs={'pk': device_id},
            current_app='device'
        )
        # Single Device perf page url
        context['perf_page_url'] = reverse(
            'SingleDevicePerf',
            kwargs={
                'page_type': page_type,
                'device_id': device_id
            },
            current_app='performance'
        )
        # Inventory device status url
        inventory_status_url = reverse(
            'DeviceStatusUrl',
            kwargs={
                'page_type': page_type,
                'device_id': device_id
            },
            current_app='performance'
        )

        # service status url
        service_status_url = reverse(
            'GetServiceStatus',
            kwargs={
                'service_name': 'ping',
                'service_data_source_type': 'pl',
                'device_id': device_id
            },
            current_app='performance'
        )

        context['get_status_url'] = inventory_status_url
        context['service_status_url'] = service_status_url

        context['device_technology_name'] = device_technology_name
        context['device_alias'] = device_alias
        context['current_device_name'] = device_name

        context['is_dr_device'] = is_dr_device

        return context


class SingleDeviceAlertsListing(BaseDatatableView, AdvanceFilteringMixin):

    model = EventNetwork
    required_columns = [
        "ip_address",
        "service_name",
        "data_source",
        "severity",
        "current_value",
        "sys_timestamp",
        "description"
    ]

    public_params = {}

    order_columns = required_columns

    def filter_queryset(self, qs):
        """ Filter datatable as per requested value
        :param qs:
        """
        sSearch = self.request.GET.get('search[value]', None)

        if sSearch:

            if self.public_params['service_name'] == 'ping':

                # raw query is required here so as to get data
                query = alert_utils.ping_service_query(
                    self.public_params['device_name'],
                    self.public_params['start_date'],
                    self.public_params['end_date']
                )

                condition_str = ''
                final_query = ''

                counter = 0

                for column in self.required_columns:
                    counter += 1

                    if counter == len(self.required_columns):
                        condition_str += " data_tab."+column+" LIKE '"+sSearch+"%' "
                    else:
                        condition_str += " data_tab."+column+" LIKE '"+sSearch+"%' or "

                if condition_str:
                    final_query += 'select data_tab.* from ('+query+') as data_tab where '+condition_str
                else:
                    final_query += query

                qs = nocout_utils.fetch_raw_result(final_query, self.public_params['machine_name'])

            else:
                if self.public_params['service_name'] == 'service':
                    # Update model for 'service'
                    self.model = EventService

                query = []

                # Create query condition string
                pre_condition_query = "("
                pre_condition_query += "Q(device_name="+str(self.public_params['device_name'])+")"

                if self.public_params['service_name'] == 'latency':
                    pre_condition_query += " & Q(data_source='rta')"
                elif self.public_params['service_name'] == 'packet_drop':
                    pre_condition_query += " & Q(data_source='pl')"
                elif self.public_params['service_name'] == 'down':
                    pre_condition_query += " & Q(data_source='pl')"
                    pre_condition_query += " & Q(current_value=100)"
                    pre_condition_query += " & Q(severity='DOWN')"

                pre_condition_query += " & Q({0}__gte={1})".format('sys_timestamp', self.public_params['start_date'])
                pre_condition_query += " & Q({0}__lte={1})".format('sys_timestamp', self.public_params['end_date'])

                pre_condition_query += ")"

                query.append(pre_condition_query)

                # Create the search condition string
                search_condition_query = ''
                exec_query = "qs = %s.objects.filter(" % (self.model.__name__)
                counter = 0
                for column in self.required_columns:
                    counter += 1

                    if counter == len(self.required_columns):
                        search_condition_query += " Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ") "
                    else:
                        search_condition_query += " Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ") | "

                if search_condition_query:
                    search_condition_query = "("+search_condition_query+")"
                    query.append(search_condition_query)

                exec_query += " & ".join(query)
                exec_query += ").values(*" + str(self.required_columns) + ")"
                exec_query += ".using(alias='" + self.public_params['machine_name'] + "')"

                exec exec_query
        # advance filtering the query set
        return self.advance_filter_queryset(qs)

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        if not len(self.public_params):
            self.initialize_params()

        if self.public_params['service_name'] == 'service':

            report_resultset = EventService.objects.filter(
                device_name=self.public_params['device_name'],
                sys_timestamp__gte=self.public_params['start_date'],
                sys_timestamp__lte=self.public_params['end_date']
            ).order_by("-sys_timestamp").values(*self.required_columns).using(
                alias=self.public_params['machine_name']
            )

        elif self.public_params['service_name'] == 'ping':

            # raw query is required here so as to get data
            query = alert_utils.ping_service_query(
                self.public_params['device_name'],
                self.public_params['start_date'],
                self.public_params['end_date']
            )
            report_resultset = nocout_utils.fetch_raw_result(query, self.public_params['machine_name'])

        elif self.public_params['service_name'] == 'latency':

            report_resultset = EventNetwork.objects.filter(
                device_name=self.public_params['device_name'],
                data_source='rta',
                sys_timestamp__gte=self.public_params['start_date'],
                sys_timestamp__lte=self.public_params['end_date']
            ).order_by("-sys_timestamp").values(*self.required_columns).using(
                alias=self.public_params['machine_name']
            )

        elif self.public_params['service_name'] == 'packet_drop':

            report_resultset = EventNetwork.objects.filter(
                device_name=self.public_params['device_name'],
                data_source='pl',
                sys_timestamp__gte=self.public_params['start_date'],
                sys_timestamp__lte=self.public_params['end_date']
            ).order_by("-sys_timestamp").values(*self.required_columns).using(
                alias=self.public_params['machine_name']
            )

        elif self.public_params['service_name'] == 'down':

            report_resultset = EventNetwork.objects.filter(
                device_name=self.public_params['device_name'],
                data_source='pl',
                current_value=100,  # need to show up and down both
                severity='DOWN',
                sys_timestamp__gte=self.public_params['start_date'],
                sys_timestamp__lte=self.public_params['end_date']
            ).order_by("-sys_timestamp").values(*self.required_columns).using(
                alias=self.public_params['machine_name']
            )

        else:

            report_resultset = []

        return report_resultset

    def prepare_results(self, qs):
        """
        Preparing Final dataset for rendering the data table.
        :param qs:
        """

        final_list = list()
        if qs:
            for data in qs:
                single_dict = {}
                single_dict = data
                single_dict['sys_timestamp'] = datetime.datetime.fromtimestamp(
                    float(data["sys_timestamp"])
                ).strftime(DATE_TIME_FORMAT)

                # add data to report_resultset list
                final_list.append(single_dict)
        else:
            final_list = qs

        return final_list

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        :param qs:
        """
        return nocout_utils.nocout_datatable_ordering(self, qs, self.required_columns)

    def initialize_params(self):
        """
        This function initializes global variables used within the class
        """

        device_id = self.kwargs['device_id']
        device_obj = Device.objects.get(id=device_id)
        device_name = device_obj.device_name
        machine_name = device_obj.machine.name
        service_name = self.request.GET.get('service_name', 'ping')

        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')

        if len(start_date) and len(end_date) and 'undefined' not in [start_date, end_date]:
            try:
                start_date = float(start_date)
                end_date = float(end_date)
            except Exception, e:
                start_date_object = datetime.datetime.strptime(start_date, "%d-%m-%Y %H:%M:%S")
                end_date_object = datetime.datetime.strptime(end_date, "%d-%m-%Y %H:%M:%S")
                start_date = format(start_date_object, 'U')
                end_date = format(end_date_object, 'U')
        else:
            # The end date is the end limit we need to make query till.
            end_date_object = datetime.datetime.now()
            # The start date is the last monday of the week we need to calculate from.
            start_date_object = end_date_object - datetime.timedelta(days=end_date_object.weekday())
            # Replacing the time, to start with the 00:00:00 of the last monday obtained.
            start_date_object = start_date_object.replace(hour=00, minute=00, second=00, microsecond=00)
            # Converting the date to epoch time or Unix Timestamp
            end_date = format(end_date_object, 'U')
            start_date = format(start_date_object, 'U')
            isSet = True

        # Prepare columns array as per service name

        if service_name in ['ping']:
            self.required_columns = [
                "ip_address",
                "service_name",
                "severity",
                "latency",
                "packet_loss",
                "sys_timestamp",
                "description"
            ]
        elif service_name in ['service']:
            self.required_columns = [
                "ip_address",
                "service_name",
                "machine_name",
                "site_name",
                "severity",
                "current_value",
                "sys_timestamp",
                "description"
            ]

        self.public_params = {
            'service_name': service_name,
            'device_name': device_name,
            'page_type': self.kwargs['page_type'],
            'machine_name': machine_name,
            'start_date': start_date,
            'end_date': end_date
        }

        return True

    def get_context_data(self, *args, **kwargs):
        """
        The main method call to fetch, search, ordering , prepare and display the data on the data table.
        :param kwargs:
        :param args:
        """

        request = self.request
        self.initialize(*args, **kwargs)

        if not len(self.public_params):
            self.initialize_params()

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = len(qs)

        qs = self.filter_queryset(qs)

        # number of records after filtering
        total_display_records = len(qs)

        qs = self.ordering(qs)
        qs = self.paging(qs)
        
        # if the qs is empty then JSON is unable to serialize 
        # the empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        aaData = self.prepare_results(qs)

        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret


class SIAListing(ListView):
    """
    View to render service impacting alarms page with appropriate column headers.
    """

    # need to associate ListView class with a model here
    model = CurrentAlarms
    template_name = 'alert_center/current_list.html'

    def get_context_data(self, **kwargs):
        """

        :param kwargs:
        :return:
        """
        context = super(SIAListing, self).get_context_data(**kwargs)

        starting_columns = [
            {'mData': 'severity', 'sTitle': 'Severity', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'ip_address', 'sTitle': 'IP', 'sWidth': 'auto', 'bSortable': True},
        ]

        invent_columns = [
            {'mData': 'bs_alias', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_city', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_state', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'region', 'sTitle': 'Region', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_connectivity', 'sTitle': 'BH Connectivity', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_type', 'sTitle': 'BH Type', 'sWidth': 'auto', 'bSortable': True}
        ]

        common_columns = [
            {'mData': 'device_type', 'sTitle': 'Device Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'eventname', 'sTitle': 'Event Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'traptime', 'sTitle': 'Received Time', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'uptime', 'sTitle': 'Uptime', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'alarm_count', 'sTitle': 'Alarm Count', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'first_occurred', 'sTitle': 'First Occurred', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'last_occurred', 'sTitle': 'Last Occurred', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'sia', 'sTitle': 'Service Impacting', 'sWidth': 'auto', 'bSortable': True}
        ]

        specific_invent_columns = [
            {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'customer_count', 'sTitle': 'Customer Count', 'sWidth': 'auto', 'bSortable': True},
        ]

        datatable_headers = list()
        datatable_headers += starting_columns
        datatable_headers += specific_invent_columns
        datatable_headers += invent_columns
        datatable_headers += common_columns

        manual_ticketing_columns = []
        is_manual_column = []
        if ENABLE_MANUAL_TICKETING:
            manual_ticketing_columns = [{
                'mData': 'action',
                'sTitle': 'Manual Ticketing',
                'sWidth': 'auto',
                'bSortable': False
            }]

            datatable_headers.insert(10, {
                'mData': 'ticket_number',
                'sTitle': 'PBI Ticket',
                'sWidth': 'auto',
                'bSortable': True
            })

            # is_manual_column += [{
            #   'mData': 'is_manual',
            #   'sTitle': 'Is Manual',
            #   'sWidth': 'auto',
            #   'bSortable': True
            # }]

        converter_datatable_headers = list()
        converter_datatable_headers += starting_columns
        converter_datatable_headers += invent_columns
        converter_datatable_headers += common_columns


        context['datatable_headers'] = json.dumps(manual_ticketing_columns + datatable_headers)
        # context['converter_datatable_headers'] = json.dumps(converter_datatable_headers)
        context['clear_history_headers'] = json.dumps(datatable_headers + is_manual_column)

        return context


class SIAListingTable(BaseDatatableView, AdvanceFilteringMixin):
    """
    View to render service impacting alarms;
    namely history, current and clear alarms for all the devices.
    """

    model = None
    alarm_type = None
    tech_name = None
    columns = [
        'severity', 'ip_address', 'eventname', 'traptime',
        'alarm_count','first_occurred','last_occurred',
        'customer_count', 'sia', 'id', 'is_manual', 'ticket_number'
    ]
    
    order_columns = [
        'severity', 'ip_address', 'bs_alias', 'bs_city', 'bs_state',
        'region', 'bh_connectivity', 'bh_type', 'eventname', 'ticket_number', 'traptime', 'uptime',
        'alarm_count', 'first_occurred','last_occurred', 'customer_count', 
        'sia'
    ]

    other_columns = [
        'bs_alias', 'bs_city', 'bs_state', 'region',
        'sector_id','device_type', 'bh_connectivity', 'bh_type', 'customer_count'
    ]

    excluded_events = [
        'PD_threshold_breach', 'PD_threshold_breach_warning', 'PD_threshold_breach_major',
        'Latency_Threshold_Breach', 'Latency_Threshold_Breach_warning', 'Latency_Threshold_Breach_major',
        'Uplink_Issue_threshold_Breach', 'Uplink_Issue_threshold_Breach_warning', 'Uplink_Issue_threshold_Breach_major',
        'Device_not_reachable'
    ]

    is_ordered = False
    is_searched = False
    NA_list = ['NA', 'N/A', 'na', 'n/a'] 

    up_since_format_array = [
        'Day',
        'Hour',
        'Minute',
        'Second',
        'Mili Second'
    ]

    def get_initial_queryset(self):
        """

        :return: :raise NotImplementedError:
        """
        if not (self.model and self.alarm_type and self.tech_name):
            self.prepare_initial_params()

        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        filter_condition = False
        ip_address_list = list()
        # If any advance filter is applied
        if self.request.GET.get('is_filter_applied', False):
            filter_condition = self.prepare_filtering_condition()

        model_columns = self.columns

        if self.tech_name == 'all':
            tech_name_list = ['pmp', 'wimax', 'rad5k']
        else:
            tech_name_list = [self.tech_name]
        tech_name_id = list()

        active_filter_condition = ''
        if self.alarm_type in ['current', 'clear']:
            active_filter_condition = ' Q(is_active= 1)'

        for tech_name in tech_name_list:                
            if tech_name in device_technology_dict:
                tech_name_id.append(device_technology_dict.get(tech_name))

        not_condition_sign = ''
        if self.tech_name not in ['pmp', 'rad5k', 'wimax', 'all']:
            tech_name_list = ['pmp', 'wimax']
            not_condition_sign = '~'

            for tech_name in tech_name_list:
                if tech_name in device_technology_dict:
                    tech_name_id.append(device_technology_dict.get(tech_name))

        self.is_rad5 = int(self.request.GET.get('is_rad5k', 0))

        if self.tech_name == 'all':
            tech_type_filter_condition = ''
            not_condition_sign = ''
        else:
            tech_type_filter_condition = 'Q(technology__iexact="{0}"),'.format(self.tech_name)

        if filter_condition:
            query = "queryset = self.model.objects.exclude( \
                            eventname__in=self.excluded_events \
                        ).filter( \
                            {0}{4}\
                            ({1}) ,\
                            {3}\
                        ).using(TRAPS_DATABASE).order_by('-traptime').values(*{2})".format(
                            not_condition_sign,
                            filter_condition,
                            model_columns,
                            active_filter_condition,
                            tech_type_filter_condition
                        )
        else:
            query = "queryset = self.model.objects.exclude( \
                    eventname__in=self.excluded_events \
                ).filter( \
                    {0}{3}\
                    {2}\
                ).using(TRAPS_DATABASE).order_by('-traptime').values(*{1})".format(
                    not_condition_sign,
                    model_columns,
                    active_filter_condition,
                    tech_type_filter_condition
                )
        exec query

        # Case Handling if Technology is coming "pmp" for rad5 devices
        # if SHOW_SPRINT3:
        #     # Filter for rad5 devices
        #     if self.tech_name in ["PMP", "pmp"]:
        #         if self.is_rad5:
        #             # Getting all devices ip list of devicetype 'Radwin5KBS'
        #             device_ip_qs = Device.objects.filter(device_type=DeviceType.objects.get(name='Radwin5KBS').id).values_list('ip_address', flat=True)

        #             # Filtering Alarms for radwin5k
        #             queryset = queryset.filter(ip_address__in=device_ip_qs)
        #     else:
        #         pass

        return queryset

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.

        :param qs:
        :return result_list:
        """
        sSearch = self.request.GET.get('search[value]', None)
        if sSearch:
            self.is_searched = True
            if type(qs) == type(list()):
                result = qs
            else:
                result = self.prepare_devices(qs)

            result_list = list()
            for search_data in result:
                # Convert the dict to string & check the search text in that string
                try:
                    dict_values_str_list = [str(i) for i in search_data.values()]
                    dict_values_string = ', '.join(dict_values_str_list).lower()
                    sSearch = sSearch.lower()
                except Exception, e:
                    dict_values_string = search_data.values()
                    sSearch = sSearch
                if sSearch in dict_values_string :
                    result_list.append(search_data)
            # advance filtering the query set
            return self.advance_filter_queryset(result_list)
        else:
            if self.request.GET.get('advance_filter', None):
                self.is_searched = True
                if type(qs) == type(list()):
                    qs = qs
                else:
                    qs = self.prepare_devices(qs)
            else:
                self.is_searched = False

        return self.advance_filter_queryset(qs)

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """

        if self.tech_name in ['pmp', 'wimax', 'all']:
            if ENABLE_MANUAL_TICKETING:
                self.order_columns = [
                    'severity', 'ip_address', 'sector_id', 'customer_count',
                    'bs_alias', 'bs_city', 'bs_state', 'region', 'bh_connectivity', 'bh_type',
                    'ticket_number', 'device_type', 'eventname', 'traptime', 'uptime',
                    'alarm_count', 'first_occurred', 'last_occurred', 'sia'
                ]

                if self.alarm_type in ['current']:
                    self.order_columns = ['action'] + self.order_columns
            else:
                self.order_columns = [
                    'severity', 'ip_address', 'sector_id', 'customer_count',
                    'bs_alias', 'bs_city', 'bs_state', 'region', 'bh_connectivity', 'bh_type',
                    'device_type', 'eventname', 'traptime', 'uptime','alarm_count',
                    'first_occurred', 'last_occurred', 'sia'
                ]

        # Number of columns that are used in sorting
        sorting_cols = 0
        if self.pre_camel_case_notation:
            try:
                sorting_cols = int(self._querydict.get('iSortingCols', 0))
            except ValueError:
                sorting_cols = 0
        else:
            sort_key = 'order[{0}][column]'.format(sorting_cols)
            while sort_key in self._querydict:
                sorting_cols += 1
                sort_key = 'order[{0}][column]'.format(sorting_cols)

        order = []
        order_columns = self.order_columns
        reverse = False
        sort_using = ''

        for i in range(sorting_cols):
            # sorting column
            sort_dir = 'asc'
            try:
                if self.pre_camel_case_notation:
                    sort_col = int(self._querydict.get('iSortCol_{0}'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('sSortDir_{0}'.format(i))
                else:
                    sort_col = int(self._querydict.get('order[{0}][column]'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('order[{0}][dir]'.format(i))
            except ValueError:
                sort_col = 0


            sdir = '-' if sort_dir == 'desc' else ''
            reverse = True if sort_dir == 'desc' else False
            sortcol = order_columns[sort_col]

            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('{0}{1}'.format(sdir, sc.replace('.', '__')))
                    sort_using = sc
            else:
                order.append('{0}{1}'.format(sdir, sortcol.replace('.', '__')))
                sort_using = sortcol

        if sort_using and sort_using in order_columns:
            # If sorting request is from other columns 
            if type(qs) == type(list()) or sort_using in self.other_columns:
                # Update the 'is_ordered' flag
                self.is_ordered = True
                # prepare result as per the complete queryset
                if self.is_searched or type(qs) == type(list()):
                    prepared_result = qs
                else:
                    prepared_result = self.prepare_devices(qs)

                try:
                    # Sort the prepared result list
                    sorted_qs = sorted(
                        prepared_result,
                        key=lambda data: unicode(data[sort_using]).strip().lower() if data[sort_using] not in [None] else data[sort_using],
                        reverse=reverse
                    )
                except Exception, e:
                    sorted_qs = prepared_result
                return sorted_qs
            else:
                # Update the 'is_ordered' flag
                self.is_ordered = False
                return qs.order_by(*order)
        return qs
    
    def prepare_filtering_condition(self):
        """
        This function prepares query condition as per the applied filters
        """
        # Initialize variables
        filtering_condition = ''

        # Ip address filtering
        ip_address = self.request.GET.get('ip_address', False)
        ip_address_list = ip_address.split('|') if ip_address else False

        if ip_address_list:
            if filtering_condition:
                filtering_condition += ' | Q(ip_address__in={0}) '.format(ip_address_list)
            else:
                filtering_condition += ' Q(ip_address__in={0}) '.format(ip_address_list)

        # event name filtering
        eventname = self.request.GET.get('eventname', False)
        eventname_list = eventname.split('|') if eventname else False

        if eventname_list:
            if filtering_condition:
                filtering_condition += ' | Q(eventname__in={0}) '.format(eventname_list)
            else:
                filtering_condition += ' Q(eventname__in={0}) '.format(eventname_list)

        # trap start_date & end_date filtering
        start_date = self.request.GET.get('start_date', False)
        end_date = self.request.GET.get('end_date', False)

        if start_date and end_date:
            if filtering_condition:
                filtering_condition += ' | Q(traptime__range=("{0}", "{1}")) '.format(start_date, end_date)
            else:
                filtering_condition += 'Q(traptime__range=("{0}", "{1}")) '.format(start_date, end_date)

        # severity filtering
        severity = self.request.GET.get('severity', False)
        severity_list = severity.split('|') if severity else False

        if severity_list:
            if filtering_condition:
                filtering_condition += ' | Q(severity__in={0}) '.format(severity_list)
            else:
                filtering_condition += ' Q(severity__in={0}) '.format(severity_list)

        return filtering_condition

    def prepare_initial_params(self):
        """
        This function initializes params as per the querystring
        """
        self.alarm_type = self.request.GET.get('alarm_type', 'current')
        self.tech_name = self.request.GET.get('tech_name', 'all')
        # set model as per alarm type
        if self.alarm_type in ['current']:
            self.model = CurrentAlarms
        elif self.alarm_type in ['clear']:
            self.model = ClearAlarms
        else:
            self.model = HistoryAlarms
        return True

    def prepare_devices(self, qs):
        """
        """
        return prepare_snmp_gis_data(qs, self.tech_name)

    def format_uptime_value(self, uptime):
        """
        This function format uptime value
        """
        splitted_uptime = uptime.split(':')

        formatted_string = ''

        for i in range(len(splitted_uptime)):
            suffix_val = str(self.up_since_format_array[i])
            timestamp_val = splitted_uptime[i]
            try:
                if not int(timestamp_val):
                    continue
            except Exception, e:
                pass

            try:
                if int(timestamp_val) > 1:
                    suffix_val += 's'
            except Exception, e:
                pass
            formatted_string += ' {} {} '.format(str(timestamp_val), suffix_val)

        return formatted_string

    def prepare_results(self, qs):
        """
        This function format resultant qs as per the GUI display
        """
        if not qs:
            return list(qs)
        else:
            current_user_roles = map(lambda name: str(name).lower(), list(self.request.user.groups.all().values_list(
                'name', flat=True
            )))

            is_admin_operator = 'admin' in current_user_roles or 'operator' in current_user_roles

            # Get List of IP for which Component is "Sector" in Planned Event Table
            sector_component_ips = PlannedEvent.objects.filter(
                component__iexact='sector'
            ).values_list('resource_name', flat=True)

            for dct in  qs:
                pk = dct.get('id')
                ip_address = dct.get('ip_address')
                severity = dct.get('severity')

                # Intialize sector id
                sector_id = ''
                # Flag if there is single Sector ID or More than one
                multiple_sec_id = False

                if ip_address in sector_component_ips:
                    # Check sector id is not 'NA'
                    if dct.get('sector_id') not in self.NA_list:
                        sector_id = dct.get('sector_id')

                        # In case of , seperated Sector Id's split it in a list of sector ID
                        # and remove whitespaces
                        sector_id = [x.strip() for x in sector_id.split(',')]

                        # In Case of Multiple sec id in one row, we need to check it device wise
                        # not Sector wise
                        if len(sector_id) > 1:
                            sector_id = ''
                            multiple_sec_id = True

                try:
                    planned_events = nocout_utils.get_current_planned_event_ips(
                        ip_address=ip_address,
                        sector_id=sector_id,
                        check_sector= not multiple_sec_id
                    )
                    if planned_events:
                        severity = 'INDOWNTIME'
                except Exception as e:
                    pass

                event_name = dct.get('eventname')
                severity_icon = alert_utils.common_get_severity_icon(severity)
                uptime = dct.get('uptime')
                ticket_number = dct.get('ticket_number')
                is_manual = dct.get('is_manual')
                action = ''
                formatted_uptime = uptime

                try:
                    is_manual = int(is_manual)
                except Exception as e:
                    is_manual = 0

                try:
                    condition2 = event_name in INCLUDED_EVENTS_FOR_MANUAL_TICKETING
                    condition3 = dct.get('device_name')
                    condition4 = self.alarm_type == 'current'
                    condition5 = str(severity).lower() != 'indowntime'
                    manual_action_condition = ENABLE_MANUAL_TICKETING and condition2 and condition3 and condition4 and condition5 and is_admin_operator
                    has_ticket_number = ticket_number and ticket_number not in ['NA', 'N/A', 'na', 'n/a']
                    
                    if manual_action_condition:
                        if not (has_ticket_number and is_manual):
                            action += '<a href="javascript:;" class="manual_ticketing_btn" data-ip="{0}" data-severity="{1}" \
                                       data-alarm="{2}" data-pk="{3}" title="Generate Manual Ticket"> \
                                       <i class="fa fa-sign-in"></i></a>&nbsp;&nbsp;'.format(ip_address, severity, event_name, pk)

                    if is_manual and has_ticket_number:
                        ticket_number += '<i class="fa fa-ticket text-success" title="Manual Ticket"></i>'
                except Exception, e:
                    pass

                try:
                    first_occurred = dct.get('first_occurred').strftime(DATE_TIME_FORMAT + ':%S')
                except Exception, e:
                    first_occurred = dct.get('first_occurred')

                try:
                    last_occurred = dct.get('last_occurred').strftime(DATE_TIME_FORMAT + ':%S')
                except Exception, e:
                    last_occurred = dct.get('last_occurred')

                if uptime:
                    formatted_uptime = self.format_uptime_value(uptime)

                dct.update(
                    action=action,
                    severity=severity_icon,
                    uptime=formatted_uptime,
                    first_occurred=first_occurred,
                    last_occurred=last_occurred,
                    is_manual=is_manual,
                    ticket_number=ticket_number
                )

            return qs
    
    def get_context_data(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return:
        """
        request = self.request
        self.initialize(*args, **kwargs)

        if not (self.model and self.alarm_type and self.tech_name):
            self.prepare_initial_params()

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = qs.count()

        qs = self.filter_queryset(qs)

        # number of records after filtering
        if self.is_searched:
            total_display_records = len(qs)
        else:
            total_display_records = qs.count()

        qs = self.ordering(qs)
        qs = self.paging(qs)
        if not (self.is_ordered or self.is_searched):
            qs = self.prepare_devices(qs)
        
        aaData = self.prepare_results(qs)

        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret


class GetSiaFiltersData(View):
    """
    """
    def get(self, *args, **kwargs):
        """
        """
        result = {
            "success" : 0,
            "message" : "No Record Found",
            "data" : []
        }
        fetched_columns = ['id', 'text']
        item_type = self.request.GET.get('item_type')
        search_txt = self.request.GET.get('search_txt')
        alarm_type = self.request.GET.get('alarm_type', 'current')
        tab_id = self.request.GET.get('tab_id', 'all')
        model = None
        suggestions_max_limit = 40

        if item_type and search_txt:
            # Select model as per the alarm type
            if alarm_type in ['clear','current']:
                model = CurrentAlarms
            else:
                model = HistoryAlarms
            # else:
            #     model = CurrentAlarms

            try:
                column_alias = {
                    'text' : item_type,
                    'id' : item_type
                }
                if tab_id and tab_id != 'all':
                    not_condition_sign = ''
                    tech_name_list = [tab_id]
                    tech_name_id = list()

                    for tech_name in tech_name_list:
                        if tech_name in device_technology_dict:
                            tech_name_id.append(device_technology_dict.get(tech_name))

                    if tab_id not in ['pmp', 'wimax']:
                        not_condition_sign = '~'
                        tech_name_list = ['pmp', 'wimax']

                    for tech_name in tech_name_list:
                        if tech_name in device_technology_dict:
                            tech_name_id.append(device_technology_dict.get(tech_name))

                    if alarm_type in ['clear']:
                        where_condition = "{0}Q(ip_address__in=(Device.objects.filter(device_technology__in = {1}).values_list('ip_address'))), Q({2}__istartswith='{3}'),Q(severity__in = ['informational'])".format(
                            not_condition_sign,
                            tech_name_id,
                            item_type,
                            search_txt
                        )
                    else:
                        where_condition = "{0}Q(ip_address__in=(Device.objects.filter(device_technology__in = {1}).values_list('ip_address'))), Q({2}__istartswith='{3}')".format(
                            not_condition_sign,
                            tech_name_id,
                            item_type,
                            search_txt
                        )
                else:
                    if alarm_type in ['clear']:
                        where_condition = "Q({0}__istartswith='{1}'),Q(severity__in = ['informational'])".format(item_type, search_txt)
                    else:
                        where_condition = "Q({0}__istartswith='{1}')".format(item_type, search_txt)                    

                # Django ORM query as per the GET params
                query = "resultset = {0}.objects.extra(select={1}).filter({2}).values(*{3}).distinct()[:40]".format(
                            model.__name__,
                            column_alias,
                            where_condition,
                            fetched_columns
                        )

                exec query

                result['success'] = 1
                result['data'] = list(resultset)
                result['message'] = "Data Fetched Successfully"
            except Exception, e:
                # logger.info(e.message)
                pass

        return HttpResponse(json.dumps(result))


class AllSiaListing(ListView):
    """
    View to render service impacting alarms page with appropriate column headers.
    """

    # need to associate ListView class with a model here
    model = CurrentAlarms
    template_name = 'alert_center/all_list.html'

    def get_context_data(self, **kwargs):
        """

        :param kwargs:
        :return:
        """
        context = super(AllSiaListing, self).get_context_data(**kwargs)
        data_source = self.kwargs.get('data_source', None)

        try:
            data_source_title = data_source.replace('_',' ').title()
        except Exception, e:
            data_source_title = data_source

        starting_columns = [
            {'mData': 'severity', 'sTitle': 'Severity', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'traptime', 'sTitle': 'Received Time', 'sWidth': 'auto', 'bSortable': True},
            # {'mData': 'eventname', 'sTitle': 'Event Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'ip_address', 'sTitle': 'IP', 'sWidth': 'auto', 'bSortable': True},
            # {'mData': 'sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'device_type', 'sTitle': 'Device Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_alias', 'sTitle': 'BS Name', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_status', 'sTitle': 'BH Status', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_state', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_city', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'circle', 'sTitle': 'Circle', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'customer_count', 'sTitle': 'Customer Count', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'ticket_number', 'sTitle': 'PB TT No.', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_connectivity', 'sTitle': 'BH Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_type', 'sTitle': 'BH Media Type', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_ckt_id', 'sTitle': 'TCL BH CKT ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bh_ttsl_ckt_id', 'sTitle': 'BH BSO CKT ID', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'bs_conv_ip', 'sTitle': 'BS Convertor IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'pop_conv_ip', 'sTitle': 'POP Convertor IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'aggr_sw_ip', 'sTitle': 'Aggregation Switch IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'pe_ip', 'sTitle': 'PE IP', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'alarm_count', 'sTitle': 'Alarm Count', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'first_occurred', 'sTitle': 'First Occurred', 'sWidth': 'auto', 'bSortable': True},
            {'mData': 'last_occurred', 'sTitle': 'Last Occurred', 'sWidth': 'auto', 'bSortable': True},
            # {'mData': 'sia', 'sTitle': 'Service Impacting', 'sWidth': 'auto', 'bSortable': True}
        ]

        
        action_columns = [
            {'mData': 'action', 'sTitle': 'Action', 'sWidth': 'auto', 'bSortable': False}
        ]

        datatable_headers = list()
        datatable_headers += starting_columns

        context['datatable_headers'] = json.dumps(action_columns + datatable_headers)
        context['clear_history_headers'] = json.dumps(action_columns + datatable_headers)
        context['data_source'] = data_source
        context['data_source_title'] = data_source_title

        return context


class AllSiaListingTable(BaseDatatableView, AdvanceFilteringMixin):
    """
    View to render service impacting alarms;
    namely history, current and clear alarms for all the devices.
    """

    model = None
    alarm_type = None
    tech_name = None
    columns = [
        'severity', 'ip_address', 'eventname', 'traptime',
        'alarm_count','first_occurred','last_occurred',
        'customer_count', 'sia', 'ticket_number', 'is_manual', 'id'
    ]
    
    order_columns = [
        'severity', 'ip_address', 'bs_alias', 'bs_city', 'bs_state',
        'bh_connectivity', 'bh_type', 'eventname','traptime','uptime',
        'alarm_count', 'first_occurred','last_occurred', 'customer_count', 'sia'
    ]

    other_columns = [
        'bs_alias', 'bs_city', 'bs_state', 'circle',
        'sector_id','device_type', 'bh_connectivity', 'bh_type',
        'bh_ckt_id', 'bh_ttsl_ckt_id', 'bs_conv_ip', 
        'pop_conv_ip', 'aggr_sw_ip', 'pe_ip', 'bh_status', 'ticket_number'
    ]

    # excluded_events = [
    #     'Latency_Threshold_Breach', 'Uplink_Issue_threshold_Breach',
    #     'Device_not_reachable', 'PD_threshold_breach'
    # ]

    is_ordered = False
    is_searched = False

    severity_icon_dict = {
        'latency': {
            'warning': 'orange-dot',
            'major': 'red-dot',
            'clear': 'green-dot',
            'indowntime': 'blue-dot'
        },
        'packet_drop': {
            'warning': 'orange-dot',
            'major': 'red-dot',
            'clear': 'green-dot',
            'indowntime': 'blue-dot'
        },
        'down': {
            'critical': 'red-dot',
            'clear': 'green-dot',
            'indowntime': 'blue-dot'
        }
    }

    up_since_format_array = [
        'Day',
        'Hour',
        'Minute',
        'Second',
        'Mili Second'
    ]

    manual_ticketing_bh_ips = []

    def get_initial_queryset(self):
        """

        :return: :raise NotImplementedError:
        """
        if not (self.model and self.alarm_type and self.tech_name):
            self.prepare_initial_params()

        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        # Fetch PTP-BH, PMP, WiMAX & BH Congfigured on devices ips from our inventory
        pmp_wimax_ips = list(Sector.objects.exclude(
            sector_id__iexact=''
        ).filter(
            sector_id__isnull=False,
            sector_configured_on__ip_address__isnull=False
        ).values_list('sector_configured_on__ip_address', flat=True))

        wimax_dr_ips = list(Sector.objects.exclude(
           sector_id__iexact=''
        ).filter(
           sector_id__isnull=False,
           dr_configured_on__ip_address__isnull=False
        ).values_list('dr_configured_on__ip_address', flat=True))

        bh_conf_ips = list(Backhaul.objects.filter(
            bh_configured_on__isnull=False,
            bh_configured_on__ip_address__isnull=False
        ).values_list('bh_configured_on__ip_address', flat=True))

        included_bh_dtype_ids = list(DeviceType.objects.filter(
            name__in=['PINE', 'RiCi', 'Converter']
        ).values_list('id', flat=True))

        specific_bh_ips = list(Backhaul.objects.filter(
            bh_configured_on__isnull=False,
            bh_configured_on__device_type__in=included_bh_dtype_ids,
            bh_configured_on__ip_address__isnull=False
        ).values_list('bh_configured_on__ip_address', flat=True))

        ptp_bh_ips = list(Circuit.objects.filter(
            circuit_type__iexact='backhaul',
            sector__sector_configured_on__ip_address__isnull=False
        ).values_list('sector__sector_configured_on__ip_address', flat=True))

        ptp_bh_ss_ips = list(Circuit.objects.filter(
            circuit_type__iexact='backhaul',
            sub_station__device__ip_address__isnull=False
        ).values_list('sub_station__device__ip_address', flat=True))

        inventory_ips_list = pmp_wimax_ips + wimax_dr_ips + bh_conf_ips + ptp_bh_ips + ptp_bh_ss_ips

        self.manual_ticketing_bh_ips = pmp_wimax_ips + wimax_dr_ips + specific_bh_ips + ptp_bh_ips + ptp_bh_ss_ips

        filter_condition = False
        ip_address_list = list()
        # If any advance filter is applied
        if self.request.GET.get('is_filter_applied', False):
            filter_condition = self.prepare_filtering_condition()

        data_source = (self.request.GET.get('data_source', None))

        model_columns = self.columns

        # set filter condition according to the data source
        if data_source and data_source.lower() in ['packet_drop']:
            eventname_list = ['PD_threshold_breach_warning', 'PD_threshold_breach_major']
        elif data_source and data_source.lower() in ['latency']:
            eventname_list = ['Latency_Threshold_Breach_warning', 'Latency_Threshold_Breach_major']
        elif data_source and data_source.lower() in ['down']:
            eventname_list = ['Device_not_reachable']
        else:
            eventname_list = []

        # Event name condition for filtering
        eventname_condition = 'Q(eventname__in={0})'.format(eventname_list)

        if self.tech_name == 'all':
            tech_name_list = ['pmp', 'wimax']
        else:
            tech_name_list = [self.tech_name]
        tech_name_id = list()

        active_filter_condition = ''
        if self.alarm_type in ['current', 'clear']:
            active_filter_condition = ' Q(is_active= 1),'
            # three_month_filter_condition = ''
            three_month_before_date = 0
        else:
            current_date = datetime.datetime.now()
            three_month_before_date = current_date - datetime.timedelta(days=90)
            # three_month_filter_condition = Q(traptime__gte=three_month_before_date)

        for tech_name in tech_name_list:                
            if tech_name in device_technology_dict:
                tech_name_id.append(device_technology_dict.get(tech_name))

        not_condition_sign = ''
        if self.tech_name not in ['pmp', 'wimax', 'all']:
            tech_name_list = ['pmp', 'wimax']
            not_condition_sign = '~'

            for tech_name in tech_name_list:
                if tech_name in device_technology_dict:
                    tech_name_id.append(device_technology_dict.get(tech_name))

        if self.tech_name == 'all':
            tech_type_filter_condition = ''
            not_condition_sign = ''
        else:
            # ip_address_list = list(Device.objects.filter(
            #     device_technology__in=tech_name_id
            # ).values_list('ip_address', flat=True))
            tech_type_filter_condition = 'Q(technology__iexact="{0}"),'.format(self.tech_name)

        str_to_date_condition = "STR_TO_DATE(traptime, '%%Y-%%m-%%d %%H:%%i:%%S')"
        field_name = {
            "traptime": str_to_date_condition
        }
        if filter_condition:
            query = "queryset = self.model.objects.extra({6}).filter(\
                            {0}{4}\
                            ({1}) ,\
                            {3}\
                            {5},\
                            ip_address__in=inventory_ips_list\
                        ).using(TRAPS_DATABASE).order_by('-traptime').values(*{2})".format(
                            not_condition_sign,
                            filter_condition,
                            model_columns,
                            active_filter_condition,
                            tech_type_filter_condition,
                            eventname_condition,
                            field_name
                        )

        else:
            try:
                query = "queryset = self.model.objects.extra({5}).filter(\
                                {0}{3}\
                                {2}\
                                {4},\
                                ip_address__in=inventory_ips_list\
                            ).using(TRAPS_DATABASE).order_by('-traptime').values(*{1})".format(
                                not_condition_sign,
                                model_columns,
                                active_filter_condition,
                                tech_type_filter_condition,
                                eventname_condition,
                                field_name,
                            )                   
            except Exception, e:
                logger.error(e)
                pass
        
        exec query

        # filtering queryset for 3 only last 3 months traps
        if self.alarm_type == 'history':
            queryset = queryset.filter(traptime__gte=three_month_before_date)
        
        return queryset

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.

        :param qs:
        :return result_list:
        """
        sSearch = self.request.GET.get('search[value]', None)
        if sSearch:
            self.is_searched = True
            if type(qs) == type(list()):
                result = qs
            else:
                result = self.prepare_devices(qs)

            result_list = list()
            for search_data in result:
                # Convert the dict to string & check the search text in that string
                try:
                    dict_values_str_list = [str(i) for i in search_data.values()]
                    dict_values_string = ', '.join(dict_values_str_list).lower()
                    sSearch = sSearch.lower()
                except Exception, e:
                    dict_values_string = search_data.values()
                    sSearch = sSearch
                if sSearch in dict_values_string :
                    result_list.append(search_data)
            # advance filtering the query set
            return self.advance_filter_queryset(result_list)
        else:
            if self.request.GET.get('advance_filter', None):
                self.is_searched = True
                if type(qs) == type(list()):
                    qs = qs
                else:
                    qs = self.prepare_devices(qs)
            else:
                self.is_searched = False

        return self.advance_filter_queryset(qs)

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        inventory_columns = []
        if self.tech_name in ['pmp', 'wimax', 'all']:
            self.order_columns = []

            self.order_columns += [
                'action', 'severity', 'traptime', 'ip_address',
                'device_type', 'bs_alias', 'bh_status', 'bs_state',
                'bs_city', 'circle', 'customer_count', 'ticket_number',
                'bh_connectivity', 'bh_type', 'bh_ckt_id', 'bh_ttsl_ckt_id',
                'bs_conv_ip', 'pop_conv_ip', 'aggr_sw_ip', 'pe_ip',
                'alarm_count', 'first_occurred', 'last_occurred'
            ]

        # Number of columns that are used in sorting
        sorting_cols = 0
        if self.pre_camel_case_notation:
            try:
                sorting_cols = int(self._querydict.get('iSortingCols', 0))
            except ValueError:
                sorting_cols = 0
        else:
            sort_key = 'order[{0}][column]'.format(sorting_cols)
            while sort_key in self._querydict:
                sorting_cols += 1
                sort_key = 'order[{0}][column]'.format(sorting_cols)

        order = []
        order_columns = self.order_columns
        reverse = False
        sort_using = ''

        for i in range(sorting_cols):
            # sorting column
            sort_dir = 'asc'
            try:
                if self.pre_camel_case_notation:
                    sort_col = int(self._querydict.get('iSortCol_{0}'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('sSortDir_{0}'.format(i))
                else:
                    sort_col = int(self._querydict.get('order[{0}][column]'.format(i)))
                    # sorting order
                    sort_dir = self._querydict.get('order[{0}][dir]'.format(i))
            except ValueError:
                sort_col = 0

            sdir = '-' if sort_dir == 'desc' else ''
            reverse = True if sort_dir == 'desc' else False
            sortcol = order_columns[sort_col]

            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('{0}{1}'.format(sdir, sc.replace('.', '__')))
                    sort_using = sc
            else:
                order.append('{0}{1}'.format(sdir, sortcol.replace('.', '__')))
                sort_using = sortcol
        if sort_using and sort_using in order_columns:
            # If sorting request is from other columns 
            if type(qs) == type(list()) or sort_using in self.other_columns:
                # Update the 'is_ordered' flag
                self.is_ordered = True
                # prepare result as per the complete queryset
                if self.is_searched or type(qs) == type(list()):
                    prepared_result = qs
                else:
                    prepared_result = self.prepare_devices(qs)
                try:
                    # Sort the prepared result list
                    sorted_qs = sorted(
                        prepared_result,
                        key=lambda data: unicode(data[sort_using]).strip().lower() if data[sort_using] not in [None] else data[sort_using],
                        reverse=reverse
                    )
                except Exception, e:
                    sorted_qs = prepared_result
                return sorted_qs
            else:
                # Update the 'is_ordered' flag
                self.is_ordered = False
                return qs.order_by(*order)
        return qs
    
    def prepare_filtering_condition(self):
        """
        This function prepares query condition as per the applied filters
        """
        # Initialize variables
        filtering_condition = ''

        # Ip address filtering
        ip_address = self.request.GET.get('ip_address', False)
        ip_address_list = ip_address.split('|') if ip_address else False

        if ip_address_list:
            if filtering_condition:
                filtering_condition += ' | Q(ip_address__in={0}) '.format(ip_address_list)
            else:
                filtering_condition += ' Q(ip_address__in={0}) '.format(ip_address_list)

        # event name filtering
        eventname = self.request.GET.get('eventname', False)
        eventname_list = eventname.split('|') if eventname else False

        if eventname_list:
            if filtering_condition:
                filtering_condition += ' | Q(eventname__in={0}) '.format(eventname_list)
            else:
                filtering_condition += ' Q(eventname__in={0}) '.format(eventname_list)

        # trap start_date & end_date filtering
        start_date = self.request.GET.get('start_date', False)
        end_date = self.request.GET.get('end_date', False)

        if start_date and end_date:
            if filtering_condition:
                filtering_condition += ' | Q(traptime__range=("{0}", "{1}")) '.format(start_date, end_date)
            else:
                filtering_condition += 'Q(traptime__range=("{0}", "{1}")) '.format(start_date, end_date)

        # severity filtering
        severity = self.request.GET.get('severity', False)
        severity_list = severity.split('|') if severity else False

        if severity_list:
            if filtering_condition:
                filtering_condition += ' | Q(severity__in={0}) '.format(severity_list)
            else:
                filtering_condition += ' Q(severity__in={0}) '.format(severity_list)

        return filtering_condition

    def prepare_initial_params(self):
        """
        This function initializes params as per the querystring
        """
        self.alarm_type = self.request.GET.get('alarm_type', 'current')
        self.tech_name = self.request.GET.get('tech_name', 'all')
        # set model as per alarm type
        if self.alarm_type in ['current']:
            self.model = CurrentAlarms
        elif self.alarm_type in ['clear']:
            self.model = ClearAlarms
        else:
            self.model = HistoryAlarms
        return True

    def prepare_devices(self, qs):
        """
        """
        return prepare_snmp_gis_data_all_tab(qs, self.tech_name)

    def format_uptime_value(self, uptime):
        """
        This function format uptime value
        """
        splitted_uptime = uptime.split(':')

        formatted_string = ''

        for i in range(len(splitted_uptime)):
            suffix_val = str(self.up_since_format_array[i])
            timestamp_val = splitted_uptime[i]
            try:
                if not int(timestamp_val):
                    continue
            except Exception, e:
                pass

            try:
                if int(timestamp_val) > 1:
                    suffix_val += 's'
            except Exception, e:
                pass
            formatted_string += ' {} {} '.format(str(timestamp_val), suffix_val)

        return formatted_string

    def prepare_results(self, qs):
        """
        This function format resultant qs as per the GUI display
        """
        if not qs:
            return list(qs)
        else:
            current_user_roles = map(lambda name: str(name).lower(), list(self.request.user.groups.all().values_list(
                'name', flat=True
            )))

            is_admin_operator = 'admin' in current_user_roles or 'operator' in current_user_roles
            for dct in  qs:
                pk = dct.get('id')
                uptime = dct.get('uptime')
                severity = dct.get('severity')
                event_name = dct.get('eventname')
                ip_address = dct.get('ip_address')

                try:
                    planned_events = nocout_utils.get_current_planned_event_ips(
                        ip_address=ip_address,
                        check_sector=False
                    )

                    if planned_events:
                        severity = 'indowntime'
                except Exception as e:
                    pass
                is_manual = dct.get('is_manual')
                ticket_number = dct.get('ticket_number')
                action = ''
                formatted_uptime = uptime
                data_source = (self.request.GET.get('data_source', None))

                # Parse to integer
                try:
                    is_manual = int(is_manual)
                except Exception as e:
                    is_manual = 0

                # severity icon according to user requirement
                # Change Color "RED" in Current and "Green" in Clear. Same in History Tab
                dot_color = self.severity_icon_dict.get(data_source, {}).get(severity, 'grey-dot')
                severity_icon = '<i class="fa fa-circle {1}" title="{0}">\
                                    <span style="display:none">{0}</span></i>'.format(severity, dot_color)

                try:
                    condition2 = event_name in INCLUDED_EVENTS_FOR_MANUAL_TICKETING
                    condition3 = dct.get('device_name')
                    condition4 = self.alarm_type == 'current'
                    condition5 = ip_address in self.manual_ticketing_bh_ips
                    condition6 = str(severity).lower() != 'indowntime'
                    manual_action_condition = ENABLE_MANUAL_TICKETING and condition2 and condition3 and condition4 and condition5 and condition6 and is_admin_operator
                    has_ticket_number = ticket_number and ticket_number not in ['NA', 'N/A', 'na', 'n/a']
                    
                    if manual_action_condition:
                        if not has_ticket_number and not is_manual:
                            action += '<a href="javascript:;" class="manual_ticketing_btn" data-ip="{0}" data-severity="{1}" \
                                       data-alarm="{2}" data-pk="{3}" title="Generate Manual Ticket"> \
                                       <i class="fa fa-sign-in"></i></a>&nbsp;&nbsp;'.format(ip_address, severity, event_name, pk)

                    if is_manual and has_ticket_number:
                        ticket_number += '<i class="fa fa-ticket text-success" title="Manual Ticket"></i>'
                except Exception, e:
                    pass

                try:
                    first_occurred = dct.get('first_occurred').strftime(DATE_TIME_FORMAT + ':%S')
                except Exception, e:
                    first_occurred = dct.get('first_occurred')

                try:
                    last_occurred = dct.get('last_occurred').strftime(DATE_TIME_FORMAT + ':%S')
                except Exception, e:
                    last_occurred = dct.get('last_occurred')

                if uptime:
                    formatted_uptime = self.format_uptime_value(uptime)
                performance_url = alert_url = inventory_url = ''
                dct['action'] = ''
                
                if dct.get('device_id'):
                    performance_url = reverse(
                        'SingleDevicePerf',
                        kwargs={
                            'page_type': dct.get('page_type', 'network'), 
                            'device_id': dct.get('device_id', 0)
                        },
                        current_app='performance'
                    )

                    alert_url = reverse(
                        'SingleDeviceAlertsInit',
                        kwargs={
                            'page_type': dct.get('page_type', 'network'), 
                            'data_source' : data_source.lower(), 
                            'device_id': dct.get('device_id', 0)
                        },
                        current_app='alert_center'
                    )
        
                    inventory_url = reverse(
                        'device_edit',
                        kwargs={
                            'pk': dct.get('device_id', 0)
                        },
                        current_app='device'
                    )

                    action += '<a href="' + alert_url + '" title="Device Alerts">\
                                <i class="fa fa-warning text-warning"></i></a>\
                                <a href="' + performance_url + '" title="Device Performance">\
                                <i class="fa fa-bar-chart-o text-info"></i></a>\
                                <a href="' + inventory_url + '" title="Device Inventory">\
                                <i class="fa fa-dropbox text-muted"></i></a>'

                dct.update(
                    action=action,
                    ticket_number=ticket_number,
                    severity=severity_icon,
                    uptime=formatted_uptime,
                    first_occurred=first_occurred,
                    last_occurred=last_occurred
                )
            return qs
    
    def get_context_data(self, *args, **kwargs):
        """

        :param args:
        :param kwargs:
        :return:
        """
        request = self.request
        self.initialize(*args, **kwargs)

        if not (self.model and self.alarm_type and self.tech_name):
            self.prepare_initial_params()

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = qs.count()

        qs = self.filter_queryset(qs)

        # number of records after filtering
        if self.is_searched:
            total_display_records = len(qs)
        else:
            total_display_records = qs.count()

        qs = self.ordering(qs)
        qs = self.paging(qs)
        if not (self.is_ordered or self.is_searched):
            qs = self.prepare_devices(qs)
        
        aaData = self.prepare_results(qs)

        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret


# @nocout_utils.cache_for(CACHE_TIME.get('INVENTORY', 300))
def prepare_snmp_gis_data(qs, tech_name):
    """
    This function fetched GIS Inventory data as per the given param & 
    map it with given queryset
    :param qs, It contains model query of SNMP model 
    :param tech_name, It contains tech_name pass to API
    """
    if type(qs) == type(list()):
        qs_list = qs
    else:
        qs_list = list(qs.values())

    # Get IP address list from qs
    ip_address_list = [x['ip_address'] for x in qs_list]

    # Get Queryset to get customer count with respect to sector id's
    # customer_count_qs = Customer_Count_Sector.objects.all().values('sector_id', 'count_of_customer')
    # # Indexed customer count With respect to Sector id
    # mapped_customer_count = list_to_key_value_dict(customer_count_qs, 'sector_id', 'count_of_customer')

    sectors_data_qs, dr_data_qs = '', ''
    converter_mapped_data = {}
    if tech_name in ['pmp', 'rad5k', 'wimax', 'all']:
        sectors_data_qs =  Sector.objects.filter(
            sector_configured_on__ip_address__in=ip_address_list
        ).annotate(
            region=F('sector_configured_on__organization__alias'),
        ).extra(
            select={'device_type' : 'device_device.device_type'}
        ).values(
            'sector_id',
            'sector_configured_on__ip_address',
            'sector_configured_on_port__name',
            'base_station__alias',
            'base_station__city__city_name',
            'base_station__state__state_name',
            'base_station__backhaul__bh_type',
            'base_station__backhaul__bh_connectivity',
            'device_type',
            'region'
        ).distinct()

        # If wimax only then check for DR device
        if tech_name in ['wimax', 'all']:
            dr_data_qs =  Sector.objects.filter(
                dr_configured_on__ip_address__in=ip_address_list
            ).annotate(
                region=F('sector_configured_on__organization__alias'),
            ).extra(
                select={'device_type' : 'device_device.device_type'}
            ).values(
                'sector_id',
                'base_station__alias',
                'base_station__city__city_name',
                'base_station__state__state_name',
                'dr_configured_on__ip_address',
                'sector_configured_on_port__name',
                'device_type',
                'region'
            ).distinct()

    # If requert from converter or all tab only then check Backhaul model
    if tech_name in ['switch', 'converter', 'all']:

        bh_conf_data_qs =  BaseStation.objects.annotate(
            region=F('backhaul__bh_configured_on__organization__alias'),
        ).extra(
            select={
                'base_station__alias' : 'inventory_basestation.alias',
                'base_station__city__city_name' : 'device_city.city_name',
                'base_station__state__state_name' : 'device_state.state_name',
                'device_type': 'device_device.device_type'
            }
        ).filter(
            backhaul__bh_configured_on__ip_address__in=ip_address_list
        ).values(
            'base_station__alias',
            'base_station__city__city_name',
            'city__city_name',
            'base_station__state__state_name',
            'state__state_name',
            'backhaul__bh_configured_on__ip_address',
            'device_type',
            'region'
        ).distinct()

        bh_switch_data_qs =  BaseStation.objects.annotate(
            region=F('backhaul__bh_switch__organization__alias'),
        ).extra(
            select={
                'base_station__alias' : 'inventory_basestation.alias',
                'base_station__city__city_name' : 'device_city.city_name',
                'base_station__state__state_name' : 'device_state.state_name',
                'device_type': 'device_device.device_type'
            }
        ).filter(
            backhaul__bh_configured_on__isnull=False,
            backhaul__bh_switch__ip_address__in=ip_address_list
        ).values(
            'base_station__alias',
            'base_station__city__city_name',
            'city__city_name',
            'base_station__state__state_name',
            'state__state_name',
            'backhaul__bh_switch__ip_address',
            'device_type',
            'region'
        ).distinct()

        pop_data_qs =  BaseStation.objects.annotate(
            region=F('backhaul__pop__organization__alias'),
        ).extra(
            select={
                'base_station__alias' : 'inventory_basestation.alias',
                'base_station__city__city_name' : 'device_city.city_name',
                'base_station__state__state_name' : 'device_state.state_name',
                'device_type': 'device_device.device_type'
            }
        ).filter(
            backhaul__bh_configured_on__isnull=False,
            backhaul__pop__ip_address__in=ip_address_list
        ).values(
            'base_station__alias',
            'base_station__city__city_name',
            'city__city_name',
            'base_station__state__state_name',
            'state__state_name',
            'backhaul__pop__ip_address',
            'device_type',
            'region'
        ).distinct()

        aggr_data_qs =  BaseStation.objects.annotate(
            region=F('backhaul__aggregator__organization__alias'),
        ).extra(
            select={
                'base_station__alias' : 'inventory_basestation.alias',
                'base_station__city__city_name' : 'device_city.city_name',
                'base_station__state__state_name' : 'device_state.state_name',
                'device_type': 'device_device.device_type'
            }
        ).filter(
            backhaul__bh_configured_on__isnull=False,
            backhaul__aggregator__ip_address__in=ip_address_list
        ).values(
            'base_station__alias',
            'base_station__city__city_name',
            'city__city_name',
            'base_station__state__state_name',
            'state__state_name',
            'backhaul__aggregator__ip_address',
            'device_type',
            'region'
        ).distinct()

        # mapped_bh_conf_result = inventory_utils.list_to_indexed_dict(
        mapped_bh_conf_result = list_to_indexed_dict_alerts(
            list(bh_conf_data_qs),
            'backhaul__bh_configured_on__ip_address'
        )

        # mapped_bh_switch_result = inventory_utils.list_to_indexed_dict(
        mapped_bh_switch_result = list_to_indexed_dict_alerts(
            list(bh_switch_data_qs),
            'backhaul__bh_switch__ip_address'
        )

        # mapped_pop_result = inventory_utils.list_to_indexed_dict(
        mapped_pop_result = list_to_indexed_dict_alerts(
            list(pop_data_qs),
            'backhaul__pop__ip_address'
        )

        # mapped_aggr_result = inventory_utils.list_to_indexed_dict(
        mapped_aggr_result = list_to_indexed_dict_alerts(
            list(aggr_data_qs),
            'backhaul__aggregator__ip_address'
        )

        converter_mapped_data = mapped_bh_conf_result.copy()
        converter_mapped_data.update(mapped_bh_switch_result)
        converter_mapped_data.update(mapped_pop_result)
        converter_mapped_data.update(mapped_aggr_result)

    # mapped_sector_result = inventory_utils.list_to_indexed_dict(
    mapped_sector_result = list_to_indexed_dict_alerts(
        list(sectors_data_qs),
        'sector_configured_on__ip_address',
        is_wimax=True
    )

    # mapped_dr_result = inventory_utils.list_to_indexed_dict(
    mapped_dr_result = list_to_indexed_dict_alerts(
        list(dr_data_qs),
        'dr_configured_on__ip_address',
        is_wimax=True
    )

    mapped_result = mapped_sector_result.copy()
    mapped_result.update(mapped_dr_result)
    mapped_result.update(converter_mapped_data)

    try:
        starmax_idu_id = DeviceType.objects.get(name__iexact='starmaxidu').id
    except Exception as e:
        starmax_idu_id = None



    for data in qs_list:
        ip_address = data.get('ip_address')
        eventname = data.get('eventname')
        data.update(
            # customer_count = 'NA',
            bs_alias='NA',
            bs_city='NA',
            bs_state='NA',
            region='NA',
            sector_id='NA',
            device_type='NA',
            bh_connectivity='NA',
            bh_type='NA',
        )
        if not ip_address:
            continue

        sector_dct = None
        try:
            sector_dct_original = mapped_result[ip_address]
            sector_dct = deepcopy(sector_dct_original)
           
            if sector_dct:

                # Because of this snippet a need of DeepCopy occured.
                # because when in case of ELSE ',' seperated ID has been updated in 1st dict
                # eg. eventname = 'wimax_interfaces_down__synchronization_lost' , ELSE cond.
                # Before sector_dct 
                # [
                #     {
                #         --- some key values were here -- 
                #         'sector_id': u'00:0a:10:09:00:12',
                #         'sector_configured_on__ip_address': u'10.172.7.3',
                #         'base_station__backhaul__bh_type': u'Dark Fibre',
                #         --- some key values were here -- 
                #     },
                #     {
                #         --- some key values were here -- 
                #         'sector_id': u'00:0a:10:09:00:14',
                #         'sector_configured_on__ip_address': u'10.172.7.3',
                #         'base_station__backhaul__bh_type': u'Dark Fibre',
                #         --- some key values were here -- 
                #     }
                # ]
                # after ELSE: 
                # [
                #     {
                #         --- some key values were here -- 
                #         'sector_id': u'00:0a:10:09:00:12, 00:0a:10:09:00:14',
                #         'sector_configured_on__ip_address': u'10.172.7.3',
                #         'base_station__backhaul__bh_type': u'Dark Fibre',
                #         --- some key values were here -- 
                #     },
                #     {
                #         --- some key values were here -- 
                #         'sector_id': u'00:0a:10:09:00:14',
                #         'sector_configured_on__ip_address': u'10.172.7.3',
                #         'base_station__backhaul__bh_type': u'Dark Fibre',
                #         --- some key values were here -- 
                #     }
                # ]
                if starmax_idu_id == sector_dct[0].get('device_type'):
                    if 'odu1' in eventname.lower() or 'pmp1' in eventname.lower():
                        try:
                            sector_dct = filter(lambda x: x.get('sector_configured_on_port__name') == 'pmp1', sector_dct)[0]
                        except Exception as e:
                            sector_dct = sector_dct[0]
                    elif 'odu2' in eventname.lower() or 'pmp2' in eventname.lower():
                        try:
                            sector_dct = filter(lambda x: x.get('sector_configured_on_port__name') == 'pmp2', sector_dct)[0]
                        except Exception as e:
                            sector_dct = sector_dct[0]
                    else:
                        try:
                            sector_dct[0]['sector_id'] = sector_dct[0].get('sector_id', 'NA') + ', '+ sector_dct[1].get('sector_id', 'NA')
                            sector_dct = sector_dct[0]
                        except Exception as e:
                            sector_dct = sector_dct[0]
                else:
                    sector_dct = sector_dct[0]
        except Exception, e:
            continue
        if sector_dct:
            data.update(
                sector_id=sector_dct.get('sector_id', 'NA'),
                bs_alias=sector_dct.get('base_station__alias', 'NA'),
                bs_city=sector_dct.get('base_station__city__city_name', 'NA'),
                bs_state=sector_dct.get('base_station__state__state_name', 'NA'),
                bh_connectivity=sector_dct.get('base_station__backhaul__bh_connectivity', 'NA'),
                bh_type=sector_dct.get('base_station__backhaul__bh_type', 'NA'),
                device_type=device_type_dict.get(sector_dct.get('device_type')),
                region=sector_dct.get('region')
            )

            # Update customer count only if it is updated on basis of sector id else let it be
            # if sector_dct.get('customer_count'):
            #     data.update(customer_count=sector_dct.get('customer_count'))

    return qs_list

def prepare_snmp_gis_data_all_tab(qs, tech_name):
    """
    This function fetched GIS Inventory data as per the given param & 
    map it with given queryset
    :param qs, It contains model query of SNMP model 
    :param tech_name, It contains tech_name pass to API
    """
    if type(qs) == type(list()):
        qs_list = qs
    else:
        qs_list = list(qs.values())

    # Get IP address list from qs
    ip_address_list = [x['ip_address'] for x in qs_list]

    sectors_data_qs, dr_data_qs = '', ''
    converter_mapped_data = {}

    # device_list = []
    bh_device_list = []

    if tech_name in ['pmp', 'wimax', 'all']:
        sectors_data_qs =  Sector.objects.filter(
            sector_configured_on__ip_address__in=ip_address_list
        ).annotate(
            machine_name=F('sector_configured_on__machine__name'),
            device_name=F('sector_configured_on__device_name'),
            bh_device_name=F('base_station__backhaul__bh_configured_on__device_name'),
            bh_machine_name=F('base_station__backhaul__bh_configured_on__machine__name'),
            device_type=F('sector_configured_on__device_type'),
            device_id=F('sector_configured_on_id'),
            circle=F('sector_configured_on__organization__alias'),
            page_type=RawSQL('SELECT "network"', ())
        ).values(
            'sector_id',
            'sector_configured_on__ip_address',
            'base_station__alias',
            'base_station__city__city_name',
            'base_station__state__state_name',
            'machine_name',
            'device_name',
            'bh_device_name',
            'bh_machine_name',
            # 'base_station__backhaul__bh_configured_on__device_name',
            # 'base_station__backhaul__bh_configured_on__machine__name',
            'base_station__backhaul__bh_type',
            'base_station__backhaul__bh_connectivity',
            'base_station__backhaul__bh_circuit_id',
            'base_station__backhaul__ttsl_circuit_id',
            'base_station__backhaul__bh_switch__ip_address',
            'base_station__backhaul__pop__ip_address',
            'base_station__backhaul__aggregator__ip_address',
            'base_station__backhaul__pe_ip__ip_address',
            'device_type',
            'device_id',
            'page_type',
            'circle'
        ).distinct()

        #device_list += sectors_data_qs.values('machine_name', 'device_name')
        bh_device_list += sectors_data_qs.values('bh_device_name', 'bh_machine_name')


        # Checking for SS Devices
        ss_id_list =  SubStation.objects.filter(
            device__ip_address__in=ip_address_list
        ).values_list('id', flat=True)

        ss_data_qs = Circuit.objects.filter(
            circuit_type__iexact='backhaul',
            sub_station__id__in=ss_id_list
        ).annotate(
            machine_name=F('sub_station__device__machine__name'),
            device_name=F('sub_station__device__device_name'),
            device_type=F('sub_station__device__device_type'),
            device_id=F('sub_station__device__id'),
            circle=F('sub_station__device__organization__alias'),
            page_type=RawSQL('SELECT "customer"', ()),
            bh_device_name=F('sector__base_station__backhaul__bh_configured_on__device_name'),
            bh_machine_name=F('sector__base_station__backhaul__bh_configured_on__machine__name'),
            base_station__alias=F('sector__base_station__alias'),
            base_station__city__city_name=F('sector__base_station__city__city_name'),
            base_station__state__state_name=F('sector__base_station__state__state_name'),
            base_station__backhaul__bh_type=F('sector__base_station__backhaul__bh_type'),
            base_station__backhaul__bh_connectivity=F('sector__base_station__backhaul__bh_connectivity'),
            base_station__backhaul__bh_circuit_id=F('sector__base_station__backhaul__bh_circuit_id'),
            base_station__backhaul__ttsl_circuit_id=F('sector__base_station__backhaul__ttsl_circuit_id'),
            base_station__backhaul__bh_switch__ip_address=F('sector__base_station__backhaul__bh_switch__ip_address'),
            base_station__backhaul__pop__ip_address=F('sector__base_station__backhaul__pop__ip_address'),
            base_station__backhaul__aggregator__ip_address=F('sector__base_station__backhaul__aggregator__ip_address'),
            base_station__backhaul__pe_ip__ip_address=F('sector__base_station__backhaul__pe_ip__ip_address'),
            sector_id=F('sector__sector_id'),
            sector_configured_on__ip_address=F('sector__sector_configured_on__ip_address'),
        ).values(
            'sector_id',
            'sector_configured_on__ip_address',
            'base_station__alias',
            'sub_station__device__ip_address',
            'machine_name',
            'device_name',
            'bh_device_name',
            'bh_machine_name',
            'base_station__city__city_name',
            'base_station__state__state_name',
            'base_station__backhaul__bh_type',
            'base_station__backhaul__bh_connectivity',
            'base_station__backhaul__bh_circuit_id',
            'base_station__backhaul__ttsl_circuit_id',
            'base_station__backhaul__bh_switch__ip_address',
            'base_station__backhaul__pop__ip_address',
            'base_station__backhaul__aggregator__ip_address',
            'base_station__backhaul__pe_ip__ip_address',
            'device_type',
            'device_id',
            'circle',
            'page_type'
        ).distinct()
    
        #device_list += ss_data_qs.values('machine_name', 'device_name')
        bh_device_list += ss_data_qs.values('bh_device_name', 'bh_machine_name')
    
        if tech_name in ['wimax', 'all']:
            dr_data_qs =  Sector.objects.filter(
                dr_configured_on__ip_address__in=ip_address_list
            ).annotate(
                machine_name=F('dr_configured_on__machine__name'),
                device_name=F('dr_configured_on__device_name'),
                device_type=F('dr_configured_on__device_type'),
                bh_device_name=F('base_station__backhaul__bh_configured_on__device_name'),
                bh_machine_name=F('base_station__backhaul__bh_configured_on__machine__name'),
                device_id=F('dr_configured_on_id'),
                page_type=RawSQL('SELECT "network"', ()),
                circle=F('dr_configured_on__organization__alias'),
            ).values(
                'sector_id',
                'base_station__alias',
                'base_station__city__city_name',
                'base_station__state__state_name',
                'dr_configured_on__ip_address',
                'machine_name',
                'device_name',
                'bh_device_name',
                'bh_machine_name',
                'base_station__backhaul__bh_type',
                'base_station__backhaul__bh_connectivity',
                'base_station__backhaul__bh_circuit_id',
                'base_station__backhaul__ttsl_circuit_id',
                'base_station__backhaul__bh_switch__ip_address',
                'base_station__backhaul__pop__ip_address',
                'base_station__backhaul__aggregator__ip_address',
                'base_station__backhaul__pe_ip__ip_address',
                'device_type',
                'device_id',
                'page_type',
                'circle'
            ).distinct()

        #device_list += dr_data_qs.values('machine_name', 'device_name')
        bh_device_list += dr_data_qs.values('bh_device_name', 'bh_machine_name')

    

    # If requert from converter or all tab only then check Backhaul model
    if tech_name in ['switch', 'converter', 'all']:

        # annotate is being used for renaming the fields to maintain the same keys
        # throughout the code. i.e keys are from line #3360 to #3365

        bh_conf_data_qs =  BaseStation.objects.extra(
            select={
                'base_station__alias' : 'inventory_basestation.alias',
                'base_station__city__city_name' : 'device_city.city_name',
                'base_station__state__state_name' : 'device_state.state_name',
                #'device_type': 'device_device.device_type'
            }
        ).annotate(
            base_station__backhaul__bh_circuit_id=F('backhaul__bh_circuit_id'),
            base_station__backhaul__ttsl_circuit_id=F('backhaul__ttsl_circuit_id'),
            base_station__backhaul__bh_switch__ip_address=F('backhaul__bh_switch__ip_address'),
            base_station__backhaul__pop__ip_address=F('backhaul__pop__ip_address'),
            base_station__backhaul__aggregator__ip_address=F('backhaul__aggregator__ip_address'),
            base_station__backhaul__pe_ip__ip_address=F('backhaul__pe_ip__ip_address') ,
            base_station__backhaul__bh_type=F('backhaul__bh_type'),
            base_station__backhaul__bh_connectivity=F('backhaul__bh_connectivity'),
            machine_name=F('backhaul__bh_configured_on__machine__name'),
            device_name=F('backhaul__bh_configured_on__device_name'),
            bh_machine_name=F('backhaul__bh_configured_on__machine__name'),
            bh_device_name=F('backhaul__bh_configured_on__device_name'),
            device_type=F('backhaul__bh_configured_on__device_type'),
            device_id=F('backhaul__bh_configured_on_id'),
            page_type=RawSQL('SELECT "other"', ()),
            circle=F('backhaul__bh_configured_on__organization__alias'),
        ).filter(
            backhaul__bh_configured_on__ip_address__in=ip_address_list
        ).values(
            'base_station__alias',
            'base_station__city__city_name',
            'city__city_name',
            'base_station__state__state_name',
            'state__state_name',
            'machine_name',
            'device_name',
            'bh_device_name',
            'bh_machine_name',
            'base_station__backhaul__bh_type',
            'base_station__backhaul__bh_connectivity',
            'backhaul__bh_configured_on__ip_address',
            'base_station__backhaul__bh_circuit_id',
            'base_station__backhaul__ttsl_circuit_id',
            'base_station__backhaul__bh_switch__ip_address',
            'base_station__backhaul__pop__ip_address',
            'base_station__backhaul__aggregator__ip_address',
            'base_station__backhaul__pe_ip__ip_address',
            'device_type',
            'device_id',
            'page_type',
            'circle'
        ).distinct()

        #device_list += bh_conf_data_qs.values('machine_name', 'device_name')
        bh_device_list += bh_conf_data_qs.values('bh_device_name', 'bh_machine_name')

        # bh_switch_data_qs =  BaseStation.objects.extra(
        #     select={
        #         'base_station__alias' : 'inventory_basestation.alias',
        #         'base_station__city__city_name' : 'device_city.city_name',
        #         'base_station__state__state_name' : 'device_state.state_name',
        #         # 'device_type': 'T4.device_type'
        #     }
        # ).annotate(
        #     base_station__backhaul__bh_circuit_id=F('backhaul__bh_circuit_id'),
        #     base_station__backhaul__ttsl_circuit_id=F('backhaul__ttsl_circuit_id'),
        #     base_station__backhaul__bh_switch__ip_address=F('backhaul__bh_switch__ip_address'),
        #     base_station__backhaul__pop__ip_address=F('backhaul__pop__ip_address'),
        #     base_station__backhaul__aggregator__ip_address=F('backhaul__aggregator__ip_address'),
        #     base_station__backhaul__pe_ip__ip_address=F('backhaul__pe_ip__ip_address'),
        #     base_station__backhaul__bh_type=F('backhaul__bh_type'),
        #     base_station__backhaul__bh_connectivity=F('backhaul__bh_connectivity') ,
        #     machine_name=F('backhaul__bh_switch__machine__name'),
        #     device_name=F('backhaul__bh_switch__device_name'),
        #     device_type=F('backhaul__bh_switch__device_type'),
        #     device_id=F('backhaul__bh_switch_id'),
        #     page_type=RawSQL('SELECT "other"', ()),
        #     circle=F('backhaul__bh_switch__organization__alias'),
        # ).filter(
        #     backhaul__bh_configured_on__isnull=False,
        #     backhaul__bh_switch__ip_address__in=ip_address_list
        # ).values(
        #     'base_station__alias',
        #     'base_station__city__city_name',
        #     'city__city_name',
        #     'base_station__state__state_name',
        #     'state__state_name',
        #     'machine_name',
        #     'device_name',
        #     'base_station__backhaul__bh_type',
        #     'base_station__backhaul__bh_connectivity',
        #     'backhaul__bh_switch__ip_address',
        #     'base_station__backhaul__bh_circuit_id',
        #     'base_station__backhaul__ttsl_circuit_id',
        #     'base_station__backhaul__bh_switch__ip_address',
        #     'base_station__backhaul__pop__ip_address',
        #     'base_station__backhaul__aggregator__ip_address',
        #     'base_station__backhaul__pe_ip__ip_address',
        #     'device_type',
        #     'device_id',
        #     'page_type',
        #     'circle'
        # ).distinct()

        # device_list += bh_switch_data_qs.values('machine_name', 'device_name')

        # pop_data_qs =  BaseStation.objects.extra(
        #     select={
        #         'base_station__alias' : 'inventory_basestation.alias',
        #         'base_station__city__city_name' : 'device_city.city_name',
        #         'base_station__state__state_name' : 'device_state.state_name',
        #         # 'device_type': 'device_device.device_type'
        #     }
        # ).annotate(
        #     base_station__backhaul__bh_circuit_id=F('backhaul__bh_circuit_id'),
        #     base_station__backhaul__ttsl_circuit_id=F('backhaul__ttsl_circuit_id'),
        #     base_station__backhaul__bh_switch__ip_address=F('backhaul__bh_switch__ip_address'),
        #     base_station__backhaul__pop__ip_address=F('backhaul__pop__ip_address'),
        #     base_station__backhaul__aggregator__ip_address=F('backhaul__aggregator__ip_address'),
        #     base_station__backhaul__pe_ip__ip_address=F('backhaul__pe_ip__ip_address'),
        #     base_station__backhaul__bh_type=F('backhaul__bh_type'),
        #     base_station__backhaul__bh_connectivity=F('backhaul__bh_connectivity') ,
        #     machine_name=F('backhaul__pop__machine__name'),
        #     device_name=F('backhaul__pop__device_name'),
        #     device_type=F('backhaul__pop__device_type'),
        #     device_id=F('backhaul__pop_id'),
        #     page_type=RawSQL('SELECT "other"', ()),
        #     circle=F('backhaul__pop__organization__alias'),
        # ).filter(
        #     backhaul__bh_configured_on__isnull=False,
        #     backhaul__pop__ip_address__in=ip_address_list
        # ).values(
        #     'base_station__alias',
        #     'base_station__city__city_name',
        #     'city__city_name',
        #     'base_station__state__state_name',
        #     'state__state_name',
        #     'machine_name',
        #     'device_name',
        #     'backhaul__pop__ip_address',
        #     'base_station__backhaul__bh_type',
        #     'base_station__backhaul__bh_connectivity',
        #     'base_station__backhaul__bh_circuit_id',
        #     'base_station__backhaul__ttsl_circuit_id',
        #     'base_station__backhaul__bh_switch__ip_address',
        #     'base_station__backhaul__pop__ip_address',
        #     'base_station__backhaul__aggregator__ip_address',
        #     'base_station__backhaul__pe_ip__ip_address',
        #     'device_type',
        #     'device_id',
        #     'page_type',
        #     'circle'
        # ).distinct()

        # device_list += pop_data_qs.values('machine_name', 'device_name')

        # aggr_data_qs =  BaseStation.objects.extra(
        #     select={
        #         'base_station__alias' : 'inventory_basestation.alias',
        #         'base_station__city__city_name' : 'device_city.city_name',
        #         'base_station__state__state_name' : 'device_state.state_name',
        #         # 'device_type': 'T4.device_type'
        #     }
        # ).annotate(
        #     base_station__backhaul__bh_circuit_id=F('backhaul__bh_circuit_id'),
        #     base_station__backhaul__ttsl_circuit_id=F('backhaul__ttsl_circuit_id'),
        #     base_station__backhaul__bh_switch__ip_address=F('backhaul__bh_switch__ip_address'),
        #     base_station__backhaul__pop__ip_address=F('backhaul__pop__ip_address'),
        #     base_station__backhaul__aggregator__ip_address=F('backhaul__aggregator__ip_address'),
        #     base_station__backhaul__pe_ip__ip_address=F('backhaul__pe_ip__ip_address'),
        #     base_station__backhaul__bh_type=F('backhaul__bh_type'),
        #     base_station__backhaul__bh_connectivity=F('backhaul__bh_connectivity') ,
        #     machine_name=F('backhaul__aggregator__machine__name'),
        #     device_name=F('backhaul__aggregator__device_name'),
        #     device_type=F('backhaul__aggregator__device_type'),
        #     device_id=F('backhaul__aggregator_id'),
        #     page_type=RawSQL('SELECT "other"', ()),
        #     circle=F('backhaul__aggregator__organization__alias'),
        # ).filter(
        #     backhaul__bh_configured_on__isnull=False,
        #     backhaul__aggregator__ip_address__in=ip_address_list
        # ).values(
        #     'base_station__alias',
        #     'base_station__city__city_name',
        #     'city__city_name',
        #     'base_station__state__state_name',
        #     'state__state_name',
        #     'backhaul__aggregator__ip_address',
        #     'base_station__backhaul__bh_circuit_id',
        #     'base_station__backhaul__bh_type',
        #     'base_station__backhaul__bh_connectivity',
        #     'machine_name',
        #     'device_name',
        #     'base_station__backhaul__ttsl_circuit_id',
        #     'base_station__backhaul__bh_switch__ip_address',
        #     'base_station__backhaul__pop__ip_address',
        #     'base_station__backhaul__aggregator__ip_address',
        #     'base_station__backhaul__pe_ip__ip_address',
        #     'device_type',
        #     'device_id',
        #     'page_type',
        #     'circle'
        # ).distinct()

        # device_list += aggr_data_qs.values('machine_name', 'device_name')
    
        mapped_bh_conf_result = inventory_utils.list_to_indexed_dict(
            list(bh_conf_data_qs),
            'backhaul__bh_configured_on__ip_address'
        )

        # mapped_bh_switch_result = inventory_utils.list_to_indexed_dict(
        #     list(bh_switch_data_qs),
        #     'backhaul__bh_switch__ip_address'
        # )

        # mapped_pop_result = inventory_utils.list_to_indexed_dict(
        #     list(pop_data_qs),
        #     'backhaul__pop__ip_address'
        # )

        # mapped_aggr_result = inventory_utils.list_to_indexed_dict(
        #     list(aggr_data_qs),
        #     'backhaul__aggregator__ip_address'
        # )
    
        converter_mapped_data = mapped_bh_conf_result.copy()
        #converter_mapped_data.update(mapped_bh_switch_result)
        #converter_mapped_data.update(mapped_pop_result)
        #converter_mapped_data.update(mapped_aggr_result)

    mapped_sector_result = inventory_utils.list_to_indexed_dict(
        list(sectors_data_qs),
        'sector_configured_on__ip_address'
    )

    
    mapped_dr_result = inventory_utils.list_to_indexed_dict(
        list(dr_data_qs),
        'dr_configured_on__ip_address'
    )

    mapped_ss_result = inventory_utils.list_to_indexed_dict(
        list(ss_data_qs),
        'sub_station__device__ip_address',
    )

    machine_device_dict = inventory_utils.prepare_machines(bh_device_list, 'bh_machine_name', 'bh_device_name')

    perf_result = {}
    for machine_name in machine_device_dict:
        if machine_name and machine_device_dict[machine_name]:
            result = perf_utils.get_performance_data(machine_device_dict[machine_name], machine_name, None)
            perf_result.update(result)

    mapped_result = mapped_sector_result.copy()
    mapped_result.update(mapped_dr_result)
    mapped_result.update(mapped_ss_result)
    mapped_result.update(converter_mapped_data)
   
    for data in qs_list:
        ip_address = data.get('ip_address', '').strip()

        data.update(
            bs_alias='NA',
            bs_city='NA',
            bs_state='NA',
            sector_id='NA',
            device_type='NA',
            bh_connectivity='NA',
            bh_type='NA',
            bh_status='NA',
            bh_ckt_id='NA',
            bh_ttsl_ckt_id='NA',
            bs_conv_ip='NA',
            pop_conv_ip='NA',
            aggr_sw_ip='NA',
            pe_ip='NA',
            page_type='network',
            circle='NA'
        )

        if not ip_address:
            continue

        try:
            sector_dct = mapped_result[ip_address]
        except Exception, e:
            sector_dct = None
            pass

        if sector_dct:
            pe_ip = sector_dct.get('base_station__backhaul__pe_ip__ip_address') if sector_dct.get('base_station__backhaul__pe_ip__ip_address') else 'NA'
            bh_ckt_id= sector_dct.get('base_station__backhaul__bh_circuit_id') if sector_dct.get('base_station__backhaul__bh_circuit_id') else 'NA'
            bh_ttsl_ckt_id= sector_dct.get('base_station__backhaul__ttsl_circuit_id') if sector_dct.get('base_station__backhaul__ttsl_circuit_id') else 'NA'
            bs_conv_ip= sector_dct.get('base_station__backhaul__bh_switch__ip_address') if sector_dct.get('base_station__backhaul__bh_switch__ip_address') else 'NA'
            pop_conv_ip= sector_dct.get('base_station__backhaul__pop__ip_address') if sector_dct.get('base_station__backhaul__pop__ip_address') else 'NA'
            aggr_sw_ip= sector_dct.get('base_station__backhaul__aggregator__ip_address') if sector_dct.get('base_station__backhaul__aggregator__ip_address') else 'NA'
            device_name = sector_dct.get('device_name', 'NA')
            bh_device_name = sector_dct.get('bh_device_name', 'NA')

            packet_loss = perf_result.get(bh_device_name, {}).get('packet_loss', None)
            bh_status = ('DOWN' if packet_loss == 100 else 'UP') if packet_loss not in [None, ''] else "NA"


            # Set Customer Count to 'NA' if there is no Customer count in Alarms table
            # Skip the case where customer count = 0
            # (In Python 0 is considered as False)
            cust_count = data.get('customer_count')
            if cust_count != 0 and not cust_count:
                data.update(customer_count='NA')

            data.update(
                sector_id=sector_dct.get('sector_id', 'NA'),
                bs_alias=sector_dct.get('base_station__alias', 'NA'),
                bs_city=sector_dct.get('base_station__city__city_name', 'NA'),
                bs_state=sector_dct.get('base_station__state__state_name', 'NA'),
                bh_connectivity=sector_dct.get('base_station__backhaul__bh_connectivity', 'NA'),
                bh_status=bh_status,
                bh_type=sector_dct.get('base_station__backhaul__bh_type', 'NA'),
                device_type=device_type_dict.get(sector_dct.get('device_type')),
                bh_ckt_id= bh_ckt_id,
                bh_ttsl_ckt_id= bh_ttsl_ckt_id,
                bs_conv_ip= bs_conv_ip,
                pop_conv_ip= pop_conv_ip,
                aggr_sw_ip= aggr_sw_ip,
                pe_ip=pe_ip,
                page_type=sector_dct.get('page_type', 'network'),
                circle=sector_dct.get('circle', 'NA'),
                device_id=sector_dct.get('device_id', 0),
            )

    return qs_list


class PlannedEventsInit(ListView):
    """
    View to render planned events page.
    """

    # need to associate ListView class with a model here
    model = CurrentAlarms
    template_name = 'alert_center/pe_events.html'

    def get_context_data(self, **kwargs):
        """

        :param kwargs:
        :return:
        """
        context = super(PlannedEventsInit, self).get_context_data(**kwargs)
        page_type = self.kwargs.get('page_type', None)

        page_type_info_dict = {
            "next": "Next 24 Hours",
            "week": "Week",
            "history": "History",
            "upcoming": "All Future PE's"
        }

        try:
            page_type_title = page_type_info_dict.get(page_type, page_type)
            if not page_type_title:
                page_type_title = page_type
        except Exception, e:
            page_type_title = page_type

        datatable_headers = [
            {'mData': 'resource_name', 'sTitle': 'Resource Name', 'bSortable': True}, 
            {'mData': 'startdate', 'sTitle': 'Start Datetime', 'bSortable': True}, 
            {'mData': 'enddate', 'sTitle': 'End  Datetime', 'bSortable': True}, 
            {'mData': 'event_type', 'sTitle': 'SA/NSA', 'bSortable': True}, 
            {'mData': 'technology__alias', 'sTitle': 'Technnology', 'bSortable': True}, 
            # {'mData': 'device_type__alias', 'sTitle': 'Device Type', 'bSortable': True}, 
            {'mData': 'owner_details', 'sTitle': 'PE Owner Details', 'bSortable': True}, 
            {'mData': 'change_coordinator', 'sTitle': 'Executor', 'bSortable': True}, 
            {'mData': 'pettno', 'sTitle': 'PE TT No.', 'bSortable': True}, 
            {'mData': 'sr_number', 'sTitle': 'Sr No', 'bSortable': True}, 
            {'mData': 'impacted_customer', 'sTitle': 'Impacted Customer Count', 'bSortable': True}, 
            {'mData': 'timing', 'sTitle': 'Emergency/Normal', 'bSortable': True}, 
            {'mData': 'summary', 'sTitle': 'Summary', 'bSortable': True}, 
            {'mData': 'status', 'sTitle': 'Status', 'bSortable': True}, 
            {'mData': 'impacted_domain', 'sTitle': 'Impacted Domain', 'bSortable': True}, 
            {'mData': 'component', 'sTitle': 'Component', 'bSortable': True}, 
            {'mData': 'sectorid', 'sTitle': 'Sector ID', 'bSortable': True}, 
            {'mData': 'service_ids', 'sTitle': 'SIA', 'bSortable': True}, 
            {'mData': 'nia', 'sTitle': 'NIA', 'bSortable': True}
        ]

        context['datatable_headers'] = json.dumps(datatable_headers)
        context['page_type'] = page_type
        context['page_type_title'] = page_type_title

        return context


class PlannedEventsListing(BaseDatatableView, AdvanceFilteringMixin):
    """
    Generic Class Based View for the Alert Center Network Listing Tables.

    """
    model = PlannedEvent
    columns = [
        'resource_name',
        'startdate',
        'enddate',
        'event_type',
        'technology__alias',
        # 'device_type__alias',
        'owner_details',
        'change_coordinator',
        'pettno',
        'sr_number',
        'impacted_customer',
        'timing',
        'summary',
        'status',
        'impacted_domain',
        'component',
        'sectorid',
        'service_ids',
        'nia',
    ]
    order_columns = columns

    def filter_queryset(self, qs):
        """
        Filter datatable as per requested value
        """
        sSearch = self.request.GET.get('search[value]', None)

        if sSearch:
            query = []
            exec_query = "qs = qs.filter("
            for column in self.columns[:-1]:
                # avoid search on 'added_on'
                if column == 'added_on':
                    continue
                query.append("Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ")")

            exec_query += " | ".join(query)
            exec_query += ").values(*" + str(self.columns) + ")"
            exec exec_query
        return self.advance_filter_queryset(qs)

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        page_type = self.kwargs.get('page_type', 'next')
        
        now_datetime = datetime.datetime.now()
        end_date = float(format(now_datetime, 'U'))
        where_condition = Q()

        # Prepare where condition on the basis of page type
        if page_type == 'next':
            start_date = float(format(now_datetime + datetime.timedelta(hours=24), 'U'))
            where_condition &= Q(startdate__lte=start_date)
            where_condition &= Q(enddate__gte=end_date)
        elif page_type == 'week':
            start_date = float(format(now_datetime + datetime.timedelta(days=7), 'U'))
            where_condition &= Q(startdate__lte=start_date)
            where_condition &= Q(enddate__gte=end_date)
        elif page_type == 'history':
            where_condition &= Q(enddate__lte=end_date)
        elif page_type == 'upcoming':
            where_condition &= Q(enddate__gte=end_date)

        qs = self.model.objects.filter(
            where_condition
        ).values(*self.columns)

        return qs

    def prepare_results(self, qs):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        resultset = list()
        for dct in json_data:
            start_date = dct.get('startdate', '')
            end_date = dct.get('enddate', '')

            try:
                dct['service_ids'] = ', '.join(dct['service_ids'].split(','))
            except Exception as e:
                pass

            try:
                dct['nia'] = ', '.join(dct['nia'].split(','))
            except Exception as e:
                pass

            try:
                start_datetime_obj = datetime.datetime.fromtimestamp(start_date)
                formatted_startdate = start_datetime_obj.strftime(DATE_TIME_FORMAT)
            except Exception as e:
                formatted_startdate = ''

            try:
                end_datetime_obj = datetime.datetime.fromtimestamp(end_date)
                formatted_enddate = end_datetime_obj.strftime(DATE_TIME_FORMAT)
            except Exception as e:
                formatted_enddate = ''

            dct.update(
                startdate=formatted_startdate,
                enddate=formatted_enddate
            )

            # resultset.append(dct)

        return json_data

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        return nocout_utils.nocout_datatable_ordering(self, qs, self.order_columns)

    def get_context_data(self, *args, **kwargs):
        """
        The main method call to fetch, search, ordering , prepare and display the data on the data table.
        """

        request = self.request
        self.initialize(*args, **kwargs)

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = qs.count()

        qs = self.filter_queryset(qs)

        # number of records after filtering
        total_display_records = qs.count()

        qs = self.ordering(qs)
        qs = self.paging(qs)
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        aaData = self.prepare_results(qs)
        
        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret


class GenerateManualTicket(View):
    """
    This class calls API to generate manual ticket for specific IP trap
    """
    def post(self, *args, **kwargs):

        pk = self.request.POST.get('pk')
        ip_address = self.request.POST.get('ip_address')
        severity = self.request.POST.get('severity')
        alarm_name = self.request.POST.get('alarm_name')
        result = {
            'success': 0,
            'message': 'Ticket generate request not sent.'
        }
        traptime = None
        current_instance = None
        try:
            current_instance = CurrentAlarms.objects.filter(
                id=pk,
                is_active=1
            ).using(TRAPS_DATABASE)

            if current_instance.exists():
                current_instance = current_instance[0]
                traptime = current_instance.traptime
        except Exception as e:
            result.update(
                message='Invalid primary key.'
            )
            current_instance = None

        if current_instance and ip_address and alarm_name:

            # Encoding data.
            encoded_data = {
                'ip_address': ip_address, 
                'severity': severity, 
                'alarm_name': alarm_name,
                'traptime': traptime
            }

            # Sending post request to nocout device app to start given IP ping stability testing
            try:
                logger.error(' ----- Manual Ticketing API ----- ')
                logger.error('url --> {0}'.format(MANUAL_TICKET_API))
                logger.error(encoded_data)
                logger.error(' ----- Manual Ticketing API ----- ')
                
                request_instance = requests.post(MANUAL_TICKET_API, data=json.dumps(encoded_data))
                # response_dict = ast.literal_eval(request_instance.text)

                # Create entry in ManualTicketingHistory
                try:
                    ticket_history_instance = ManualTicketingHistory(
                        ip_address=ip_address,
                        eventname=alarm_name,
                        user_profile_id=self.request.user.id
                    )
                    ticket_history_instance.save()
                except Exception as e:
                    logger.error('Ticket history create exception for {0} - {1}'.format(ip_address, alarm_name))
                    logger.error(e)
                    pass

                
                # Update is_manual flag in current traps
                try:
                    current_instance.is_manual = True
                    current_instance.save()
                except Exception as e:
                    logger.error('is_manual not updated')
                    logger.error(e)
                    pass

                result.update(
                    success=1,
                    message='Manual ticket generate request sent.'
                )
            except Exception as e:
                result.update(
                    message=e.message
                )
                logger.error('Manual Ticketing Request Exception')
                logger.error(e)
                pass

        else:
            result.update(
                message='Invalid API params'
            )

        return HttpResponse(json.dumps(result))


class ManualTicketsInit(ListView):
    """
    View to render manual tickets history page.
    """

    # need to associate ListView class with a model here
    model = ManualTicketingHistory
    template_name = 'alert_center/manual_events.html'

    def get_context_data(self, **kwargs):
        """

        :param kwargs:
        :return:
        """
        context = super(ManualTicketsInit, self).get_context_data(**kwargs)

        datatable_headers = [
            {'mData': 'ip_address', 'sTitle': 'IP Address', 'bSortable': True}, 
            {'mData': 'eventname', 'sTitle': 'Event Name', 'bSortable': True}, 
            {'mData': 'ticket_number', 'sTitle': 'PBI Ticket', 'bSortable': True}, 
            {'mData': 'user_profile__username', 'sTitle': 'Created By', 'bSortable': True}, 
            {'mData': 'created_at', 'sTitle': 'Created At', 'bSortable': True}
        ]

        context['datatable_headers'] = json.dumps(datatable_headers)

        return context


class ManualTicketsListing(BaseDatatableView, AdvanceFilteringMixin):
    """
    Generic Class Based View for the Alert Center Network Listing Tables.

    """
    model = ManualTicketingHistory
    columns = [
        'ip_address',
        'eventname',
        'ticket_number',
        'user_profile__username',
        'created_at'
    ]
    order_columns = columns

    def filter_queryset(self, qs):
        """
        Filter datatable as per requested value
        """
        sSearch = self.request.GET.get('search[value]', None)

        if sSearch:
            query = []
            exec_query = "qs = qs.filter("
            for column in self.columns[:-1]:
                # avoid search on 'added_on'
                if column == 'added_on':
                    continue
                query.append("Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ")")

            exec_query += " | ".join(query)
            exec_query += ").values(*" + str(self.columns) + ")"
            exec exec_query
        return self.advance_filter_queryset(qs)

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        qs = self.model.objects.values(*self.columns).order_by(
            '-created_at'
        ) #.using(TRAPS_DATABASE)

        return qs

    def prepare_results(self, qs):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        resultset = list()
        for dct in json_data:
            created_at = dct.get('created_at')
            if created_at:
                dct.update(
                    created_at=created_at.strftime(DATE_TIME_FORMAT)
                )

        return json_data

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        return nocout_utils.nocout_datatable_ordering(self, qs, self.order_columns)

    def get_context_data(self, *args, **kwargs):
        """
        The main method call to fetch, search, ordering , prepare and display the data on the data table.
        """

        request = self.request
        self.initialize(*args, **kwargs)

        qs = self.get_initial_queryset()

        # number of records before filtering
        total_records = qs.count()

        qs = self.filter_queryset(qs)

        # number of records after filtering
        total_display_records = qs.count()

        qs = self.ordering(qs)
        qs = self.paging(qs)
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        aaData = self.prepare_results(qs)
        
        ret = {
            'sEcho': int(request.REQUEST.get('sEcho', 0)),
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': total_display_records,
            'aaData': aaData
        }

        return ret

def list_to_indexed_dict_alerts(inventory_list=None, key='ip_address', is_wimax=False):
    '''

    '''
    inventory_dict = dict()
    # wimax_id = DeviceTechnology.objects.get()
    for device_info in inventory_list:
        if device_info[key] not in inventory_dict:
            inventory_dict[device_info[key]] = []
        if is_wimax:
            inventory_dict[device_info[key]].append(device_info)
        else:
            inventory_dict[device_info[key]] = [device_info]

    return inventory_dict


def list_to_key_value_dict(invent_list=None, key_str='', val_str=''):
    """Convert given list of dict into dictionary with given "key" and "value" keys
    @param invent_list : To be converted list
    @param key_str : Key to be used as key in returned dict(Key-Value pair)
    @param val_str : Key to be used as value in returned dict(Key-Value pair)

    eg : invent_list = [
                            {'count_of_customer': u'5', 'sector_id': u'00:0a:10:02:00:72'},
                            {'count_of_customer': u'12', 'sector_id': u'00:0a:10:02:00:75'},
                            {'count_of_customer': u'14', 'sector_id': u'00:0a:15:02:00:81'}
                       ]
         key_str = 'sector_id'
         val_str = 'count_of_customer'

         return {
                    '00:0a:10:02:00:72' : '5',
                    '00:0a:10:02:00:75' : '12',
                    '00:0a:15:02:00:81' : '14',
         }
    """

    invent_dict = dict()

    if invent_list and key_str and val_str:
        for item in invent_list:
            try:
                dict_key = item.get(key_str)
                dict_val = item.get(val_str)
                
                invent_dict[dict_key] = dict_val
            except Exception, e:
                continue

    return invent_dict
