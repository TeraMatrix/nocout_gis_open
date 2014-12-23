# -*- coding: utf-8 -*-
import ast, sys
from copy import deepcopy
import logging
import json
import ujson
from pprint import pprint, pformat
import urllib, datetime
from multiprocessing import Process, Queue
from django.db.models import Q, Count
from django.views.generic.base import View
from django.http import HttpResponse
from inventory.models import BaseStation, Sector, Circuit, SubStation, Customer, LivePollingSettings, \
    ThresholdConfiguration, ThematicSettings, PingThematicSettings
from device.models import Device, DeviceType, DeviceVendor, \
    DeviceTechnology, DeviceModel, State, Country, City
import requests
from nocout.utils import logged_in_user_organizations
from nocout.utils.util import time_it, \
    query_all_gis_inventory, cached_all_gis_inventory, cache_for
from service.models import DeviceServiceConfiguration, Service, ServiceDataSource
from django.contrib.staticfiles.templatetags.staticfiles import static
from site_instance.models import SiteInstance
from performance.models import Topology
from sitesearch.views import prepare_raw_bs_result
from nocout.settings import GIS_MAP_MAX_DEVICE_LIMIT

logger = logging.getLogger(__name__)



@cache_for(600)
def prepare_raw_result(bs_dict = []):
    """

    :param bs_dict: dictionary of base-station objects
    :return: API formatted result
    """

    bs_list = []
    bs_result = {}
    #preparing result by pivoting via basestation id
    if len(bs_dict):
        for bs in bs_dict:
            BSID = bs['BSID']
            if BSID not in bs_list:
                bs_list.append(BSID)
                bs_result[BSID] = []
            bs_result[BSID].append(bs)
    return bs_result


class DeviceStatsApi(View):

    raw_result = prepare_raw_result(cached_all_gis_inventory(query_all_gis_inventory(monitored_only=True)))

    # @time_it()
    def get(self, request):

        self.result = {
            "success": 0,
            "message": "Device Loading Completed",
            "data": {
                "meta": {},
                "objects": None
            }
        }
        # page_number= request.GET['page_number']
        # limit= request.GET['limit']

        organizations = logged_in_user_organizations(self)

        if organizations:
            # for organization in organizations:
            page_number= self.request.GET.get('page_number', None)
            start, offset= None, None
            if page_number:
                #Setting the Start and Offset limit for the Query.
                offset= int(page_number)*GIS_MAP_MAX_DEVICE_LIMIT
                start= offset - GIS_MAP_MAX_DEVICE_LIMIT

            bs_id = BaseStation.objects.prefetch_related(
                'sector', 'backhaul').filter(organization__in=organizations
                )[start:offset].annotate(dcount=Count('name')).values_list('id',flat=True)

            #if the total count key is not in the meta objects then run the query
            total_count=self.request.GET.get('total_count')

            if not int(total_count):
                total_count= BaseStation.objects.filter(
                    organization__in=organizations).annotate(dcount=Count('name')
                ).count()

                self.result['data']['meta']['total_count']= total_count

            else:
                #Otherthan first request the total_count will be echoed back and then can be placed in the result.
                total_count= self.request.GET.get('total_count')
                self.result['data']['meta']['total_count']= total_count

            self.result['data']['meta']['limit']= GIS_MAP_MAX_DEVICE_LIMIT
            self.result['data']['meta']['offset']= offset
            self.result['data']['objects']= {"id" : "mainNode", "name" : "mainNodeName", "data" :
                                                    { "unspiderfy_icon" : "static/img/icons/bs.png" }
                                            }
            self.result['data']['objects']['children']= list()

            for bs in bs_id:
                if bs in self.raw_result:
                    base_station_info= prepare_raw_bs_result(self.raw_result[bs])
                    self.result['data']['objects']['children'].append(base_station_info)


            self.result['data']['meta']['device_count']= len(self.result['data']['objects']['children'])
            self.result['message'] = 'Data Fetched Successfully.'
            self.result['success'] = 1
        return HttpResponse(json.dumps(self.result), content_type="application/json")


class DeviceFilterApi(View):

    def get(self, request):
        self.result = {
            "success": 0,
            "message": "Device Loading Completed",
            "data": {
                "meta": {},
                "objects": {}
            }
        }

        vendor_list = []
        technology_data,vendor_data,state_data,city_data=[],[],[],[]
        for device_technology in DeviceTechnology.objects.all():
            technology_data.append({ 'id':device_technology.id,
                                     'value':device_technology.name })

        self.result['data']['objects']['technology']={'data':technology_data}

        self.result['message']='Data Fetched Successfully.'
        self.result['success']=1

        return HttpResponse(json.dumps(self.result), content_type="application/json")


class LPServicesApi(View):
    """
        API for fetching the services and data sources for list of devices.
        Parameters:
            - devices (list) - list of devices

        Returns:
           - result (dict) - dictionary of devices with associates services and data sources
           {
                "success" : 1,
                "message" : "Services Fetched Successfully",
                "data" : {
                    "device1" : {
                        "services" : [
                            {
                                "name" : "any_service_name2",
                                "value" : "65",
                                "datasource" : [
                                    {
                                        "name" : "any_service_datasource_name1",
                                        "value" : "651"
                                    },
                                    {
                                        "name" : "any_service_datasource_name2",
                                        "value" : "652"
                                    },
                                    {
                                        "name" : "any_service_datasource_name3",
                                        "value" : "653"
                                    }
                                ]
                            },
                            {
                                "name" : "any_service_name3",
                                "value" : "66",
                                "datasource" : [
                                    {
                                        "name" : "any_service_datasource_name4",
                                        "value" : "654"
                                    },
                                    {
                                        "name" : "any_service_datasource_name5",
                                        "value" : "655"
                                    },
                                    {
                                        "name" : "any_service_datasource_name6",
                                        "value" : "656"
                                    }
                                ]
                            }
                        ]
                    },
                    "device2" : {
                        "services" : [
                            {
                                "name" : "any_service_name4",
                                "value" : "6545",
                                "datasource" : [
                                    {
                                        "name" : "any_service_datasource_name7",
                                        "value" : "657"
                                    },
                                    {
                                        "name" : "any_service_datasource_name8",
                                        "value" : "658"
                                    },
                                    {
                                        "name" : "any_service_datasource_name9",
                                        "value" : "659"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
    """

    def get(self, request):
        """Returns json containing devices, services and data sources"""

        result = {
            "success": 0,
            "message": "No Service Data",
            "data": {
            }
        }

        # list of devices for which service and data sources needs to be fetched
        # i.e. ['device1', 'device2']
        try:
            devices = eval(str(self.request.GET.get('devices',None)))
            if devices:
                for dv in devices:
                    device = Device.objects.get(device_name=dv)

                    # fetching all rows form 'service_deviceserviceconfiguration' where device_name is
                    # is name of device currently in loop; to get all associated services
                    device_sdc = DeviceServiceConfiguration.objects.filter(device_name=device.device_name)

                    # initializing dict for current device
                    result['data'][str(dv)] = {}

                    # initializing list for services associated to current device(dv)
                    result['data'][str(dv)]['services'] = []

                    # loop through all services of current device(dv)
                    for dsc in device_sdc:
                        svc_dict = dict()
                        svc_dict['name'] = str(dsc.service_name)
                        svc_dict['value'] = Service.objects.get(name=dsc.service_name).id

                        # initializing list of data sources
                        svc_dict['datasource'] = []

                        # fetching all rows form 'service_deviceserviceconfiguration' where device_name and service_name
                        # are names of current device and service in loop; to get all associated data sources
                        service_data_sources = DeviceServiceConfiguration.objects.filter(device_name=dv, service_name=dsc.service_name)

                        # loop through all the data sources associated with current service(dsc)
                        for sds in service_data_sources:
                            sds_dict = dict()
                            sds_dict['name'] = sds.data_source
                            sds_dict['value'] = ServiceDataSource.objects.get(name=sds.data_source).id
                            # appending data source dict to data sources list for current service(dsc) data source list
                            svc_dict['datasource'].append(sds_dict)

                        # appending service dict to services list of current device(dv)
                        result['data'][str(dv)]['services'].append(svc_dict)
                        result['success'] = 1
                        result['message'] = "Successfully fetched services and data sources."
        except Exception as e:
            result['message'] = e.message
            logger.info(e)

        return HttpResponse(json.dumps(result))


class FetchLPDataApi(View):
    """
        API for fetching the service live polled value
        Parameters:
            - device (list) - list of devices
            - service (list) - list of services
            - datasource (list) - list of data sources

        Returns:
           - result (dict) - dictionary containing list of live polled values and icon urls
            {
                "success" : 1,
                "message" : "Live Polling Data Fetched Successfully",
                "data" : {
                    "value" : ["50"],
                    "icon" : ["static/img/marker/icon1_small.png"]
                }
            }
    """

    def get(self, request):
        """Returns json containing live polling value and icon url"""

        # converting 'json' into python object
        devices = eval(str(self.request.GET.get('device', None)))
        services = eval(str(self.request.GET.get('service', None)))
        datasources = eval(str(self.request.GET.get('datasource', None)))

        result = {
            "success": 0,
            "message": "",
            "data": {
            }
        }

        result['data']['value'] = []
        result['data']['icon'] = []

        try:
            for dv, svc, ds in zip(devices, services, datasources):
                lp_data = dict()
                lp_data['mode'] = "live"
                lp_data['device'] = dv
                lp_data['service'] = svc
                lp_data['ds'] = []
                lp_data['ds'].append(ds)

                device = Device.objects.get(device_name=dv)
                service = Service.objects.get(name=svc)
                data_source = ServiceDataSource.objects.get(name=ds)

                url = "http://{}:{}@{}:{}/{}/check_mk/nocout_live.py".format(device.site_instance.username,
                                                                             device.site_instance.password,
                                                                             device.machine.machine_ip,
                                                                             device.site_instance.web_service_port,
                                                                             device.site_instance.name)

                # encoding 'lp_data'
                encoded_data = urllib.urlencode(lp_data)

                # sending post request to nocout device app to fetch service live polling value
                r = requests.post(url , data=encoded_data)

                # converting post response data into python dict expression
                response_dict = ast.literal_eval(r.text)

                # if response(r) is given by post request than process it further to get success/failure messages
                if r:
                    result['data']['value'].append(response_dict.get('value')[0])

                    # device technology
                    tech = DeviceTechnology.objects.get(pk=device.device_technology)

                    # live polling settings for getting associates service and data sources
                    lps = LivePollingSettings.objects.get(technology=tech, service=service, data_source=data_source)

                    # threshold configuration for getting warning, critical comparison values
                    tc = ThresholdConfiguration.objects.get(live_polling_template=lps)

                    # thematic settings for getting icon url
                    ts = ThematicSettings.objects.get(threshold_template=tc)

                    # comparing threshold values to get icon
                    try:
                        value = int(response_dict.get('value')[0])
                        image_partial = "img/icons/wifi7.png"
                        if abs(int(value)) > abs(int(tc.warning)):
                            image_partial = ts.gt_warning.upload_image
                        elif abs(int(tc.warning)) >= abs(int(value)) >= abs(int(tc.critical)):
                            image_partial = ts.bt_w_c.upload_image
                        elif abs(int(value)) > abs(int(tc.critical)):
                            image_partial = ts.gt_critical.upload_image
                        else:
                            icon = static('img/icons/wifi7.png')
                        img_url = "media/" + str(image_partial) if "uploaded" in str(image_partial) else static(
                            "img/" + image_partial)
                        icon = str(img_url)
                    except Exception as e:
                        icon = static('img/icons/wifi7.png')
                        logger.info(e.message)

                    result['data']['icon'].append(icon)
                    # if response_dict doesn't have key 'success'
                    if not response_dict.get('success'):
                        logger.info(response_dict.get('error_message'))
                        result['message'] += "Failed to fetch data for '%s'." % (svc)
                    else:
                        result['message'] += "Successfully fetch data for '%s'." % (svc)

            result['success'] = 1
        except Exception as e:
            result['message'] = e.message
            logger.info(e)

        return HttpResponse(json.dumps(result))


class FetchLPSettingsApi(View):
    """
        API for fetching the service live polled value
        Parameters:
            - technology (unicode) - id of technology

        Returns:
           - result (dict) - dictionary containing list of live polling settings
            {
                "message": "Successfully fetched live polling settings.",
                "data": {
                    "lp_templates": [
                        {
                            "id": 1,
                            "value": "RadwinUAS"
                        },
                        {
                            "id": 2,
                            "value": "Radwin RSSI"
                        },
                        {
                            "id": 3,
                            "value": "Estimated Throughput"
                        },
                        {
                            "id": 4,
                            "value": "Radwin Uptime"
                        }
                    ]
                },
                "success": 1
            }
    """

    def get(self, request):
        """Returns json containing live polling values and icon urls for bulk devices"""
        # result dictionary to be returned as output of ap1
        result = {
            "success": 0,
            "message": "Failed to fetch live polling settings.",
            "data": {
            }
        }

        # initializing 'lp_templates' list containing live setting templates
        result['data']['lp_templates'] = list()

        # converting 'json' into python object
        technology_id = int(self.request.GET.get('technology', None))

        # technology object
        technology = DeviceTechnology.objects.get(pk=technology_id)

        # get live polling settings corresponding to the technology
        lps = ""
        try:
            lps = LivePollingSettings.objects.filter(technology=technology)
        except Exception as e:
            logger.info(e.message)

        if lps:
            for lp in lps:
                lp_temp = dict()
                lp_temp['id'] = lp.id
                lp_temp['value'] = lp.alias
                result['data']['lp_templates'].append(lp_temp)
            result['message'] = "Successfully fetched live polling settings."
            result['success'] = 1
        return HttpResponse(json.dumps(result))


class FetchThresholdConfigurationApi(View):
    """
        API for fetching the service live polled value
        Parameters:
            - technology (unicode) - id of technology

        Returns:
           - result (dict) - dictionary containing list of threshold configurations
            {
                "message": "Successfully fetched threshold configurations.",
                "data": {
                    "threshold_templates": [
                        {
                            "id": 6,
                            "value": "Radwin UAS"
                        },
                        {
                            "id": 7,
                            "value": "Radwin RSSI Critical"
                        },
                        {
                            "id": 11,
                            "value": "Radwin RSSI Warning"
                        },
                        {
                            "id": 8,
                            "value": "Estimated Throughput"
                        },
                        {
                            "id": 9,
                            "value": "Radwin Uptime"
                        }
                    ]
                },
                "success": 1
            }
    """

    def get(self, request):
        """Returns json containing live polling values and icon urls for bulk devices"""
        # result dictionary to be returned as output of api
        result = {
            "success": 0,
            "message": "Failed to fetch live polling settings.",
            "data": {
            }
        }

        # initializing 'lp_templates' list containing live setting templates
        result['data']['threshold_templates'] = list()

        # converting 'json' into python object
        technology_id = int(self.request.GET.get('technology', None))

        # technology object
        technology = DeviceTechnology.objects.get(pk=technology_id)

        # get live polling settings corresponding to the technology
        lps = ""
        try:
            lps = LivePollingSettings.objects.filter(technology=technology)
        except Exception as e:
            logger.info(e.message)

        if lps:
            tc_temp = dict()
            for lp in lps:
                threshold_configurations = ThresholdConfiguration.objects.filter(live_polling_template=lp)
                if threshold_configurations:
                    for tc in threshold_configurations:
                        tc_temp = dict()
                        tc_temp['id'] = tc.id
                        tc_temp['value'] = tc.alias
                        result['data']['threshold_templates'].append(tc_temp)
            result['message'] = "Successfully fetched threshold configurations."
            result['success'] = 1
        return HttpResponse(json.dumps(result))


class FetchThematicSettingsApi(View):
    """
        API for fetching the service live polled value
        Parameters:
            - technology (unicode) - id of technology

        Returns:
           - result (dict) - dictionary containing list of threshold configurations
            {
                "message": "Successfully fetched threshold configurations.",
                "data": {
                    "threshold_templates": [
                        {
                            "id": 6,
                            "value": "Radwin UAS"
                        },
                        {
                            "id": 7,
                            "value": "Radwin RSSI Critical"
                        },
                        {
                            "id": 11,
                            "value": "Radwin RSSI Warning"
                        },
                        {
                            "id": 8,
                            "value": "Estimated Throughput"
                        },
                        {
                            "id": 9,
                            "value": "Radwin Uptime"
                        }
                    ]
                },
                "success": 1
            }
    """

    def get(self, request):
        """Returns json containing live polling values and icon urls for bulk devices"""
        # result dictionary to be returned as output of api
        result = {
            "success": 0,
            "message": "Failed to fetch thematic settings.",
            "data": {
            }
        }

        # initializing 'lp_templates' list containing live setting templates
        result['data']['thematic_settings'] = list()

        # service type
        service_type = self.request.GET.get('service_type', None)

        # converting 'json' into python object
        technology_id = int(self.request.GET.get('technology', None))

        # technology object
        technology = DeviceTechnology.objects.get(pk=technology_id)

        # get live polling settings corresponding to the technology
        lps = ""
        try:
            lps = LivePollingSettings.objects.filter(technology=technology)
        except Exception as e:
            logger.info(e.message)
        if service_type == 'ping':
            thematic_settings = PingThematicSettings.objects.filter(technology=technology)
            for ts in thematic_settings:
                ts_temp = dict()
                ts_temp['id'] = ts.id
                ts_temp['value'] = ts.alias
                result['data']['thematic_settings'].append(ts_temp)
            result['message'] = "Successfully fetched thematic settings."
            result['success'] = 1
        else:
            if lps:
                for lp in lps:
                    threshold_configurations = ThresholdConfiguration.objects.filter(live_polling_template=lp)
                    if threshold_configurations:
                        for tc in threshold_configurations:
                            thematic_settings = ThematicSettings.objects.filter(threshold_template=tc)
                            if thematic_settings:
                                for ts in thematic_settings:
                                    ts_temp = dict()
                                    ts_temp['id'] = ts.id
                                    ts_temp['value'] = ts.alias
                                    result['data']['thematic_settings'].append(ts_temp)
            result['message'] = "Successfully fetched thematic settings."
            result['success'] = 1
        return HttpResponse(json.dumps(result))


class BulkFetchLPDataApi(View):
    """
        API for fetching the service live polled values
        Parameters:
            - ts_template (unicode) - threshold configuration template id for e.g. 23
            - devices (list) - list of devices for e.g. ["3335","1714","2624","2622"]
            - service_type (unicode) - type of service i.e 'ping' or 'normal'

        Returns:
           - 'result' (dict) - dictionary containing list of live polled values and icon urls
                    {
                        "message": "Successfully fetched.",
                        "data": {
                            "devices": {
                                "2622": {
                                    "message": "Successfully fetch data for '2622'.",
                                    "value": [
                                        "-57"
                                    ],
                                    "icon": "media/uploaded/icons/2014-09-25/2014-09-25-13-59-00_P2P-Green.png"
                                },
                                "2624": {
                                    "message": "Successfully fetch data for '2624'.",
                                    "value": "NA",
                                    "icon": "media/uploaded/icons/2014/09/18/wifi3.png"
                                },
                                "3335": {
                                    "message": "Successfully fetch data for '3335'.",
                                    "value": "NA",
                                    "icon": "media/uploaded/icons/2014/09/18/wifi3.png"
                                },
                                "1714": {
                                    "message": "Successfully fetch data for '1714'.",
                                    "value": [
                                        "-66"
                                    ],
                                    "icon": "media/uploaded/icons/2014-10-26/2014-10-26-14-59-40_SM-Red.png"
                                }
                            }
                        },
                        "success": 1
                    }
    """

    def get(self, request):
        """Returns json containing live polling values and icon urls for bulk devices"""

        # get service type i.e. 'ping' or 'normal'
        service_type = self.request.GET.get('service_type', 'normal')

        # devices list
        devices = eval(str(self.request.GET.get('devices', None)))

        # thematic settings template id
        ts_template_id = int(self.request.GET.get('ts_template', None))

        # exceptional services i.e. 'ss' services which get service data from 'bs' instead from 'ss'
        exceptional_services = ['wimax_dl_cinr', 'wimax_ul_cinr', 'wimax_dl_rssi',
                                'wimax_ul_rssi', 'wimax_ul_intrf', 'wimax_dl_intrf',
                                'wimax_modulation_dl_fec', 'wimax_modulation_ul_fec',
                                'cambium_ul_rssi', 'cambium_ul_jitter', 'cambium_reg_count',
                                'cambium_rereg_count']

        # service for which live polling runs
        service = ""

        # data source for which live polling runs
        data_source = ""

        # live polling template id
        lp_template_id = ""

        # get thematic settings corresponding to the 'service_type'
        if service_type == 'ping':
            # thematic settings (ping)
            ts = PingThematicSettings.objects.get(pk=ts_template_id)
            service = ts.service
            data_source = ts.data_source

            # result dictionary which needs to be returned as an output of api
            result = {
                "success": 0,
                "message": "Failed to fetch thematic settings.",
                "data": {}
            }
        else:
            # thematic settings (normal)
            ts = ThematicSettings.objects.get(pk=ts_template_id)

            # live polling template id
            lp_template_id = ThresholdConfiguration.objects.get(pk=ts.threshold_template.id).live_polling_template.id

            # getting service and data source from live polling settings
            try:
                service = LivePollingSettings.objects.get(pk=lp_template_id).service
                data_source = LivePollingSettings.objects.get(pk=lp_template_id).data_source
            except Exception as e:
                logger.info("No service and data source corresponding to this live polling setting template.")

            # result dictionary which needs to be returned as an output of api
            result = {
                "success": 0,
                "message": "Failed to fetch live polling data.",
                "data": {}
            }

            # bs device to with 'ss' is connected (applied only if 'service' is from 'exceptional_services')
            bs_device, site_name = None, None

        result['data']['devices'] = dict()

        # get machines associated with the current devices
        machine_list = []
        for device in devices:
            try:
                machine = Device.objects.get(device_name=device).machine.id
                machine_list.append(machine)
            except Exception as e:
                logger.info(e.message)

        # remove redundant machine id's from 'machine_list'
        machines = set(machine_list)

        try:
            responses = []
            for machine_id in machines:
                response_dict = {
                    'value': []
                }

                # live polling setting
                if service_type != "ping":
                    lp_template = LivePollingSettings.objects.get(pk=lp_template_id)

                # current machine devices
                current_devices_list = []

                # fetch devices associated with current machine
                for device_name in devices:
                    try:
                        device = Device.objects.get(device_name=device_name)
                        if device.machine.id == machine_id:
                            current_devices_list.append(str(device.device_name))
                    except Exception as e:
                        logger.info(e.message)

                # get site instances associated with the current devices
                site_instances_list = []

                # fetch all site instances associated with the devices in 'current_devices_list'
                for device_name in current_devices_list:
                    try:
                        device = Device.objects.get(device_name=device_name)

                        # if service is from 'exceptional_services'
                        # than get base station and it's device to which 'ss' device is connected from 'Topology'
                        if str(service) in exceptional_services:
                            # mac address of device
                            mac_address = device.mac_address
                            mac = mac_address.lower()

                            # base station device name to which 'ss' is connected
                            bs_device = Topology.objects.get(connected_device_mac=mac)

                            # get base station device
                            device = Device.objects.get(device_name=bs_device.device_name)

                        # append device site instance id in 'site_instances_list' list
                        site_instances_list.append(device.site_instance.id)
                    except Exception as e:
                        logger.info(e.message)

                # remove redundant site instance id's from 'site_instances_list'
                sites = set(site_instances_list)

                site_list = []
                for site_id in sites:
                    # 'bs' and 'ss' macs mapping dictionary
                    # for e.g. 'bs_name_ss_mac_mapping': {
                    #                                     u'1527': [
                    #                                         u'00: 02: 73: 93: 05: 4f',
                    #                                         u'00: 02: 73: 90: 80: 98'
                    #                                    ]}
                    bs_name_ss_mac_mapping = {}

                    # 'ss' name and mac mapping dictionary
                    # for e.g. 'ss_name_mac_mapping': {
                    #                                     u'3597': u'00: 02: 73: 91: 2a: 24',
                    #                                     u'3769': u'00: 02: 73: 93: 06: d3',
                    #                                     u'3594': u'00: 02: 73: 90: 24: 88',
                    #                                     u'3047': u'00: 02: 73: 93: 05: 4f'
                    #                                 }
                    ss_name_mac_mapping = {}

                    # list of devices associated with current site instance
                    devices_in_current_site = []

                    for device_name in current_devices_list:
                        try:
                            device = Device.objects.get(device_name=device_name)
                            if str(service) in exceptional_services:
                                # 'ss' device mac address
                                device_ss_mac = device.mac_address

                                # insert data in 'ss_name_mac_mapping' dictionary
                                ss_name_mac_mapping[device.device_name] = device_ss_mac

                                # get base station device name from 'Topology'
                                bs_device = Topology.objects.get(connected_device_mac=device_ss_mac.lower())

                                # get base station device
                                device = Device.objects.get(device_name=bs_device.device_name)
                                if device.device_name in bs_name_ss_mac_mapping.keys():
                                    bs_name_ss_mac_mapping[device.device_name].append(device_ss_mac)
                                else:
                                    bs_name_ss_mac_mapping[device.device_name] = [device_ss_mac]

                                # base station device site instance id
                                bs_site_id = device.site_instance.id

                                if bs_site_id == site_id and device.device_name not in devices_in_current_site:
                                    devices_in_current_site.append(device.device_name)
                            elif device.site_instance.id == site_id:
                                devices_in_current_site.append(device.device_name)
                        except Exception as e:
                            logger.info(e.message)

                    # live polling data dictionary (payload for nocout.py api call)
                    # for e.g.
                    # lp_data -
                    # {
                    #   'device_list': [u'1598'],
                    #   'bs_name_ss_mac_mapping': {u'1598': [u'00:02:73:90:1f:6e']},
                    #   'service_list': ['wimax_dl_rssi'],
                    #   'ss_name_mac_mapping': {
                    #                              u'2622': u'00:02:73:90:1f:6e',
                    #                              u'2624': u'00:02:73:92:9c:12',
                    #                              u'3335': u'00:02:73:91:99:1d'
                    #                          },
                    #   'mode': 'live',
                    #   'dr_master_slave': {},
                    #   'ds': ['dl_rssi']
                    # }
                    lp_data = dict()
                    lp_data['mode'] = "live"
                    lp_data['bs_name_ss_mac_mapping'] = bs_name_ss_mac_mapping
                    lp_data['ss_name_mac_mapping'] = ss_name_mac_mapping
                    lp_data['device_list'] = devices_in_current_site

                    if service_type == 'ping':
                        lp_data['service_list'] = [str(service)]
                        lp_data['ds'] = [str(data_source)]
                    else:
                        lp_data['service_list'] = [str(lp_template.service.name)]
                        lp_data['ds'] = [str(lp_template.data_source.name)]

                    site = SiteInstance.objects.get(pk=int(site_id))
                    site_list.append({
                        'username': site.username,
                        'password': site.password,
                        'port': site.web_service_port,
                        'machine': site.machine.machine_ip,
                        'site_name': site.name,
                        'lp_data': lp_data
                    })

                # Multiprocessing
                q = Queue()
                jobs = [
                    Process(
                        target=nocout_live_polling,
                        args=(q, site,)
                    ) for site in site_list
                ]

                for j in jobs:
                    j.start()
                for k in jobs:
                    k.join()
                pformat(q)
                while True:
                    if not q.empty():
                        responses.append(q.get())
                    else:
                        break
                for entry in responses:
                    response_dict['value'].extend(entry.get('value'))

                # if response(r) is given by post request than process it further to get success/failure messages
                if len(response_dict):
                    # get devices from 'response_dict'
                    devices_in_response = response_dict.get('value')

                    for device_name in devices:
                        # device object
                        device_obj = ""
                        try:
                            device_obj = Device.objects.get(device_name=device_name)
                        except Exception as e:
                            logger.info("Device not exist. Exception: ", e.message)

                        device_value = "NA"

                        # check whether device present in 'devices_in_response'
                        # if present then fetch it's live polled value
                        for device_dict in devices_in_response:
                            for device, val in device_dict.items():
                                if device_name == device:
                                    device_value = val
                                    continue

                        result['data']['devices'][device_name] = dict()

                        result['data']['devices'][device_name]['value'] = device_value

                        # default icon
                        icon = ""
                        try:
                            icon = DeviceType.objects.get(pk=device_obj.device_type).device_icon
                        except Exception as e:
                            logger.info("No icon for this device. Exception: ", e.message)

                        icon = str(icon)

                        # fetch icon settings for thematics as per thematic type selected i.e. 'ping' or 'normal'
                        th_icon_settings = ""
                        try:
                            th_icon_settings = ts.icon_settings
                        except Exception as e:
                            logger.info("No icon settings for thematic settings. Exception: ", e.message)

                        # fetch thematic ranges as per service type selected i.e. 'ping' or 'normal'
                        th_ranges = ""
                        try:
                            if service_type == "ping":
                                th_ranges = ts
                            else:
                                th_ranges = ts.threshold_template
                        except Exception as e:
                            logger.info("No ranges for thematic settings. Exception: ", e.message)

                        # fetch service type if 'ts_type' is "normal"
                        svc_type = ""
                        try:
                            if service_type != "ping":
                                svc_type = ts.threshold_template.service_type
                        except Exception as e:
                            logger.info("Service Type not exist. Exception: ", e.message)

                        # comparing threshold values to get icon
                        try:
                            if len(device_value):

                                # live polled value of device service
                                try:
                                    value = ast.literal_eval(str(device_value))
                                except Exception as e:
                                    value = device_value
                                    logger.info("Value can't be converted. Exception: ", e.message)

                                # get appropriate icon
                                if service_type == "normal":
                                    if svc_type == "INT":
                                        icon = self.get_icon_for_numeric_service(th_ranges,
                                                                                 th_icon_settings,
                                                                                 value,
                                                                                 icon)
                                    elif svc_type == "STR":
                                        icon = self.get_icon_for_string_service(th_ranges,
                                                                                th_icon_settings,
                                                                                value,
                                                                                icon)
                                    else:
                                        pass
                                elif service_type == "ping":
                                    icon = self.get_icon_for_numeric_service(th_ranges,
                                                                             th_icon_settings,
                                                                             value,
                                                                             icon)
                                else:
                                    pass

                        except Exception as e:
                            logger.info("Icon not exist. Exception: ", e.message)

                        result['data']['devices'][device_name]['icon'] = icon
                        # if response_dict doesn't have key 'success'
                        if device_value and (device_value != "NA"):
                            result['data']['devices'][device_name]['message'] = "Successfully fetch data for '%s'." % \
                                                                                device_name
                        else:
                            result['data']['devices'][device_name]['message'] = "Failed to fetch data for '%s'." % \
                                                                                device_name
            result['success'] = 1
            result['message'] = "Successfully fetched."
        except Exception as e:
            result['message'] = e.message
            logger.info(e)

        return HttpResponse(json.dumps(result))

    def get_icon_for_numeric_service(self, th_ranges=None, th_icon_settings="", value="", icon=""):
        """
            Get device icon corresponding to fetched performance value
            Parameters:
                - th_ranges (<class 'inventory.models.ThresholdConfiguration'>) - threshold configuration object
                                                                                  for e.g. Wimax DL RSSI
                - th_icon_settings (unicode) - icon settings in json format for e.g.
                        [
                            {
                                'icon_settings1': u'uploaded/icons/2014-09-26/2014-09-26-11-56-11_SM-GIF.gif'
                            },
                            {
                                'icon_settings2': u'uploaded/icons/2014-10-26/2014-10-26-14-59-40_SM-Red.png'
                            },
                            {
                                'icon_settings3': u'uploaded/icons/2014-09-25/2014-09-25-13-59-00_P2P-Green.png'
                            }
                        ]
                - value (str) - performance value for e.g "-57"
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"

            Returns:
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"
        """

        # default image to be loaded
        image_partial = icon

        # fetch value from list
        value = value[0]

        if th_ranges and th_icon_settings and len(str(value)):
            try:
                if (float(th_ranges.range1_start)) <= (float(value)) <= (float(th_ranges.range1_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings1' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings1'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range2_start)) <= (float(value)) <= (float(th_ranges.range2_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings2' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings2'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range3_start)) <= (float(value)) <= (float(th_ranges.range3_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings3' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings3'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range4_start)) <= (float(value)) <= (float(th_ranges.range4_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings4' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings4'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range5_start)) <= (float(value)) <= (float(th_ranges.range5_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings5' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings5'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range6_start)) <= (float(value)) <= (float(th_ranges.range6_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings6' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings6'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range7_start)) <= (float(value)) <= (float(th_ranges.range7_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings7' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings7'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range8_start)) <= (float(value)) <= (float(th_ranges.range8_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings8' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings8'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range9_start)) <= (float(value)) <= (float(th_ranges.range9_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings9' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings9'])
            except Exception as e:
                logger.info(e.message)

            try:
                if (float(th_ranges.range10_start)) <= (float(value)) <= (float(th_ranges.range10_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings10' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings10'])
            except Exception as e:
                logger.info(e.message)

        # image url
        img_url = "media/" + str(image_partial) if "uploaded" in str(
            image_partial) else "static/img/" + str(image_partial)

        # icon to be send in response
        icon = str(img_url)

        return icon

    def get_icon_for_string_service(self, th_ranges=None, th_icon_settings="", value="", icon=""):
        """
            Get device icon corresponding to fetched performance value
            Parameters:
                - th_ranges (<class 'inventory.models.ThresholdConfiguration'>) - threshold configuration object
                                                                                  for e.g. Wimax DL RSSI
                - th_icon_settings (unicode) - icon settings in json format for e.g.
                        [
                            {
                                'icon_settings1': u'uploaded/icons/2014-09-26/2014-09-26-11-56-11_SM-GIF.gif'
                            },
                            {
                                'icon_settings2': u'uploaded/icons/2014-10-26/2014-10-26-14-59-40_SM-Red.png'
                            },
                            {
                                'icon_settings3': u'uploaded/icons/2014-09-25/2014-09-25-13-59-00_P2P-Green.png'
                            }
                        ]
                - value (str) - performance value for e.g "-57"
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"

            Returns:
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"
        """

        # default image to be loaded
        image_partial = icon

        # fetch value from list
        value = value[0]

        if th_ranges and th_icon_settings and value:
            try:
                if str(value).lower().strip() == str(th_ranges.range1_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings1' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings1'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range2_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings2' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings2'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range3_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings3' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings3'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range4_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings4' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings4'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range5_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings5' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings5'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range6_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings6' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings6'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range7_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings7' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings7'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range8_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings8' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings8'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range9_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings9' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings9'])
            except Exception as e:
                logger.info(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range10_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings10' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings10'])
            except Exception as e:
                logger.info(e.message)

        # image url
        img_url = "media/" + str(image_partial) if "uploaded" in str(
            image_partial) else "static/img/" + str(image_partial)

        # icon to be send in response
        icon = str(img_url)

        return icon


def nocout_live_polling(q, site):
    # url for nocout.py
    # url = 'http://omdadmin:omd@localhost:90/master_UA/check_mk/nocout.py'
    # url = 'http://<username>:<password>@<domain_name>:<port>/<site_name>/check_mk/nocout.py'
    url = "http://{}:{}@{}:{}/{}/check_mk/nocout_live.py".format(site.get('username'),
                                                                 site.get('password'),
                                                                 site.get('machine'),
                                                                 site.get('port'),
                                                                 site.get('site_name'))
    # encoding 'lp_data'
    encoded_data = urllib.urlencode(site.get('lp_data'))

    # sending post request to nocout device app to fetch service live polling value
    try:
        r = requests.post(url, data=encoded_data)
        response_dict = ast.literal_eval(r.text)
        if len(response_dict):
            temp_dict = deepcopy(response_dict)
            q.put(temp_dict)
    except Exception as e:
        logger.info(e.message)
