import ast, sys
import json, logging
import urllib
from django.db.models import Q, Count
from django.views.generic.base import View
from django.http import HttpResponse
from inventory.models import BaseStation, Sector, Circuit, SubStation, Customer, LivePollingSettings, \
    ThresholdConfiguration, ThematicSettings
from device.models import Device, DeviceType, DeviceVendor, \
    DeviceTechnology, DeviceModel, State, Country, City
import requests
from nocout.utils import logged_in_user_organizations
from service.models import DeviceServiceConfiguration, Service, ServiceDataSource
from django.contrib.staticfiles.templatetags.staticfiles import static
from sitesearch.views import DeviceSetFilters, prepare_result
from nocout.settings import GIS_MAP_MAX_DEVICE_LIMIT
logger=logging.getLogger(__name__)


class DeviceStatsApi(View):


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

        organizations= logged_in_user_organizations(self)

        if organizations:
            for organization in organizations:
                page_number= self.request.GET.get('page_number', None)
                start, offset= None, None
                if page_number:
                    offset= int(page_number)*GIS_MAP_MAX_DEVICE_LIMIT
                    start= offset - GIS_MAP_MAX_DEVICE_LIMIT

                base_stations_and_sector_configured_on_devices= Sector.objects.filter(sector_configured_on__id__in= \
                organization.device_set.values_list('id', flat=True))[start:offset].values_list('base_station').annotate(dcount=Count('base_station'))
                if base_stations_and_sector_configured_on_devices:
                    total_count= Sector.objects.filter(sector_configured_on__id__in=organization.device_set.values_list('id', flat=True)).count()
                    request_query= self.request.GET.get('filters','')
                    if request_query:
                        return DeviceSetFilters.as_view()(self.request, total_count)

                    else:
                        self.result['data']['meta']['total_count']= total_count
                        self.result['data']['meta']['limit']= GIS_MAP_MAX_DEVICE_LIMIT
                        self.result['data']['objects']= {"id" : "mainNode", "name" : "mainNodeName", "data" :
                                                                { "unspiderfy_icon" : "static/img/marker/slave01.png" }
                                                        }
                        self.result['data']['objects']['children']=list()
                        for base_station_id, dcount in base_stations_and_sector_configured_on_devices:
                            try:
                                base_station_info= prepare_result(base_station_id)
                                self.result['data']['objects']['children'].append(base_station_info)
                            except Exception as e:
                                logger.error("API Error Message: %s"%(e.message), exc_info=True)
                                pass
                    self.result['message']='Data Fetched Successfully.'
                    self.result['success']=1
        return HttpResponse(json.dumps(self.result))

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

        technology_data,vendor_data,state_data,city_data=[],[],[],[]
        for device_technology in DeviceTechnology.objects.all():
            technology_data.append({ 'id':device_technology.id,
                                     'value':device_technology.name })
        for vendor in DeviceVendor.objects.all():
            vendor_data.append({ 'id':vendor.id,
                                     'value':vendor.name })

        for state in State.objects.all():
            state_data.append({ 'id':state.id,
                                     'value':state.state_name })

        for city in City.objects.all():
            city_data.append({ 'id':city.id,
                                     'value':city.city_name })

        self.result['data']['objects']['technology']={'data':technology_data}
        self.result['data']['objects']['vendor']={'data':vendor_data}
        self.result['data']['objects']['state']={'data':state_data}
        self.result['data']['objects']['city']={'data':city_data}
        self.result['message']='Data Fetched Successfully.'
        self.result['success']=1

        return HttpResponse(json.dumps(self.result))


class LPServicesApi(View):
    """
        API for fetching the services and data sources for list of devices.
        :Parameters:
            - 'devices' (list) - list of devices

        :Returns:
           - 'result' (dict) - dictionary of devices with associates services and data sources
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
        :Parameters:
            - 'device' (list) - list of devices
            - 'service' (list) - list of services
            - 'datasource' (list) - list of data sources

        :Returns:
           - 'result' (dict) - dictionary containing list of live polled values and icon urls
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
        :Parameters:
            - 'technology' (unicode) - id of technology

        :Returns:
           - 'result' (dict) - dictionary containing list of live polling settings
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


class BulkFetchLPDataApi(View):
    """
        API for fetching the service live polled value
        :Parameters:
            - 'lp_template' (unicode) - live polling settings template id
            - 'devices' (list) - list of devices

        :Returns:
           - 'result' (dict) - dictionary containing list of live polled values and icon urls
            {
                "message": "Successfully fetched.",
                "data": {
                    "devices": {
                        "115.114.15.188": {
                            "message": "Successfully fetch data for '115.114.15.188'.",
                            "value": "-62",
                            "icon": "/media/uploaded/icons/2014/08/19/blinking_dot.gif"
                        },
                        "121.244.195.36": {
                            "message": "Successfully fetch data for '121.244.195.36'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "121.240.119.108": {
                            "message": "Successfully fetch data for '121.240.119.108'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "115.112.161.68": {
                            "message": "Successfully fetch data for '115.112.161.68'.",
                            "value": "-61",
                            "icon": "/media/uploaded/icons/2014/08/19/blinking_dot.gif"
                        },
                        "121.240.226.243": {
                            "message": "Successfully fetch data for '121.240.226.243'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "115.111.230.212": {
                            "message": "Successfully fetch data for '115.111.230.212'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "ptp_sectorstation": {
                            "message": "Successfully fetch data for 'ptp_sectorstation'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "14.141.83.236": {
                            "message": "Successfully fetch data for '14.141.83.236'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "14.141.37.190": {
                            "message": "Successfully fetch data for '14.141.37.190'.",
                            "value": "",
                            "icon": "/static/img/icons/wifi7.png"
                        },
                        "14.141.111.132": {
                            "message": "Successfully fetch data for '14.141.111.132'.",
                            "value": "-56",
                            "icon": "/media/uploaded/icons/2014/08/19/blinking_dot.gif"
                        }
                    }
                },
                "success": 1
            }
    """

    def get(self, request):
        """Returns json containing live polling values and icon urls for bulk devices"""

        # converting 'json' into python object
        devices = eval(str(self.request.GET.get('devices', None)))
        lp_template_id = int(self.request.GET.get('lp_template', None))
        service = ""
        data_source = ""

        # getting service and data source form live polling settings
        try:
            service = LivePollingSettings.objects.get(pk=lp_template_id).service
            data_source = LivePollingSettings.objects.get(pk=lp_template_id).data_source

        except Exception as e:
            logger.info("No service and data source corresponding to this live pollig setting template.")

        # result dictionary to be returned as output of ap1
        result = {
            "success": 0,
            "message": "Failed to fetch live polling data.",
            "data": {
            }
        }

        result['data']['devices'] = dict()
        try:
            lp_template = LivePollingSettings.objects.get(pk=lp_template_id)

            for device_name in devices:
                result['data']['devices'][device_name] = dict()

                # live polling data dictionary (payload for nocout.py api call)
                lp_data = dict()
                lp_data['mode'] = "live"
                lp_data['device'] = device_name
                lp_data['service'] = str(service.name)
                lp_data['ds'] = list()
                lp_data['ds'].append(str(data_source.name))

                # current device object
                device = Device.objects.get(device_name=device_name)

                # url for nocout.py
                url = "http://{}:{}@{}:{}/{}/check_mk/nocout_live.py".format(device.site_instance.username,
                                                                             device.site_instance.password,
                                                                             device.machine.machine_ip,
                                                                             device.site_instance.web_service_port,
                                                                             device.site_instance.name)

                # encoding 'lp_data'
                encoded_data = urllib.urlencode(lp_data)

                # sending post request to nocout device app to fetch service live polling value
                r = requests.post(url, data=encoded_data)

                # converting post response data into python dict expression
                response_dict = ast.literal_eval(r.text)
                # if response(r) is given by post request than process it further to get success/failure messages
                if r:
                    result['data']['devices'][device_name]['value'] = response_dict.get('value')[0] if response_dict.get('value') else ""

                    # threshold configuration for getting warning, critical comparison values
                    tc = ThresholdConfiguration.objects.get(live_polling_template=lp_template)

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
                        img_url = "/media/" + str(image_partial) if "uploaded" in str(image_partial) else static(
                            "img/" + image_partial)
                        icon = str(img_url)
                    except Exception as e:
                        icon = static('img/icons/wifi7.png')
                        logger.info(e.message)

                    result['data']['devices'][device_name]['icon'] = icon

                    # if response_dict doesn't have key 'success'
                    if not response_dict.get('success'):
                        logger.info(response_dict.get('error_message'))
                        result['data']['devices'][device_name]['message'] = "Failed to fetch data for '%s'." % \
                                                                            device_name
                    else:
                        result['data']['devices'][device_name]['message'] = "Successfully fetch data for '%s'." % \
                                                                            device_name

            result['success'] = 1
            result['message'] = "Successfully fetched."
        except Exception as e:
            result['message'] = e.message
            logger.info(e)
        return HttpResponse(json.dumps(result))
