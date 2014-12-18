import json
import os, datetime
from django.http import HttpResponseRedirect, HttpResponse
from operator import itemgetter
from django.db.models.query import ValuesQuerySet
from django.shortcuts import render_to_response
from django.template import RequestContext
import logging
from zipfile import ZipFile
import glob
from nocout.settings import MEDIA_ROOT, MEDIA_URL
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, TemplateView, View
from django_datatables_view.base_datatable_view import BaseDatatableView
from forms import KmzReportForm
from django.views.generic.edit import CreateView, DeleteView
from device.models import Device, DeviceFrequency, DeviceTechnology, DeviceType
from django.db.models import Q
from inventory.models import ThematicSettings, UserThematicSettings, BaseStation, SubStation, UserPingThematicSettings, \
    PingThematicSettings, Circuit, CircuitL2Report
from performance.models import InventoryStatus, NetworkStatus, ServiceStatus, PerformanceStatus, PerformanceInventory, \
    PerformanceNetwork, PerformanceService, Status, Topology
from user_profile.models import UserProfile
from devicevisualization.models import GISPointTool, KMZReport
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse_lazy
import re, ast
from activity_stream.models import UserAction

#update the service data sources
from service.utils.util import service_data_sources

logger=logging.getLogger(__name__)

##execute this globally
SERVICE_DATA_SOURCE = service_data_sources()
##execute this globally


def locate_devices(request , device_name = "default_device_name"):
    """
    Returns the Context Variable to GIS Map page.
    """
    template_data = { 'username' : request.user.username,
                    'device_name' : device_name,
                    'get_filter_api': get_url(request, 'GET'),
                    'set_filter_api': get_url(request, 'POST')
                    }

    return render_to_response('devicevisualization/locate_devices.html',
                                template_data,
                                context_instance=RequestContext(request))

def load_google_earth(request, device_name = "default_device_name"):

    """
    Returns the Context Variable for google earth.
    """
    template_data = { 'username' : request.user.username,
                    'device_name' : device_name,
                    'get_filter_api': get_url(request, 'GET'),
                    'set_filter_api': get_url(request, 'POST')
                    }

    return render_to_response('devicevisualization/google_earth_template.html',
                                template_data,
                                context_instance=RequestContext(request))

def load_earth(request):
    """
    Returns the Context Variable for google earth.
    """
    template_data = {}

    return render_to_response('devicevisualization/locate_devices_earth.html',
                                template_data,
                                context_instance=RequestContext(request))


def load_white_background(request , device_name = "default_device_name"):
    """
    Returns the Context Variable to GIS Map page.
    """
    template_data = { 'username' : request.user.username,
                    'device_name' : device_name,
                    'get_filter_api': get_url(request, 'GET'),
                    'set_filter_api': get_url(request, 'POST')
                    }

    return render_to_response('devicevisualization/locate_devices_white_map.html',
                                template_data,
                                context_instance=RequestContext(request))


def get_url(req, method):
    """
    Return Url w.r.t to the request type.
    """
    url = None
    if method == 'GET':
        url = "/gis/get_filters/"
    elif method == 'POST':
        url = "/gis/set_filters/"

    return url


class Gis_Map_Performance_Data(View):
        """
        The request data will be
        {
            'basestation':{'id':<BS_ID>
               'sector':{
                        'device_name':<device_name>
                        'substation':{
                                'device_name':<device_name>
                            }
               }


               }
        }

        """
        @method_decorator(csrf_exempt)
        def dispatch(self, *args, **kwargs):
            return super(Gis_Map_Performance_Data, self).dispatch(*args, **kwargs)

        def post(self, request):
            request_data = self.request.body
            # request_data.replace('\n','')
            if request_data:
                request_data = json.loads(request_data)
                request_data_sectors = request_data['param']['sector']
                for sector in request_data_sectors:
                    sector['performance_data'] = self.get_device_performance(sector['device_name'])
                    substations = sector['sub_station']
                    for substation in substations:
                        substation['performance_data'] = self.get_device_performance(substation['device_name'])
                #logger.debug(request_data)
                return HttpResponse(json.dumps(request_data))

            return HttpResponse(json.dumps({'result': 'No Performance Data'}))

        def tech_info(self, device_technology):
            """

            :param device_technology: technology for the device
            :return: the list of data sources to be checked
            """
            return []

        def get_device_performance(self, device_name):
            device_performance_value = ''
            device_frequency = ''
            device_pl = ''
            device_link_color = None
            freeze_time = self.request.GET.get('freeze_time', '0')
            sector_info = {
                'azimuth_angle': "",
                'beam_width': "",
                'radius': "",
                'frequency': device_frequency
            }
            performance_data = {
                'frequency': device_frequency,
                'pl': device_pl,
                'color': device_link_color,
                'performance_paramter': "",
                'performance_value': device_performance_value,
                'performance_icon': "",
                'device_info': [
                    {
                        "name": "",
                        "title": "",
                        "show": 0,
                        "value": ""
                    },
                ],
                'sector_info': sector_info
            }
            try:
                device = Device.objects.get(device_name=device_name, is_added_to_nms=1, is_deleted=0)

                device_technology = DeviceTechnology.objects.get(id=device.device_technology)
                user_obj = UserProfile.objects.get(id=self.request.user.id)

                uts = UserThematicSettings.objects.get(user_profile=user_obj,
                                                       thematic_technology=device_technology)

                thematic_settings = uts.thematic_template
                threshold_template = thematic_settings.threshold_template
                live_polling_template = threshold_template.live_polling_template

                device_service_name = live_polling_template.service.name
                device_service_data_source = live_polling_template.data_source.name
                device_machine_name = device.machine.name
                try:
                    if int(freeze_time):
                        device_frequency= PerformanceInventory.objects.filter(device_name=device_name,
                                                                              data_source='frequency',
                                                                              sys_timestamp__lte=int(freeze_time)/1000).\
                                                                              using(alias=device_machine_name).\
                                                                              order_by('-sys_timestamp')[:1]
                        if len(device_frequency):
                            device_frequency = device_frequency[0].current_value
                        else:
                            device_frequency = ''

                    else:
                        device_frequency= InventoryStatus.objects.filter(device_name=device_name,
                                                                         data_source='frequency').\
                                                                         using(alias=device_machine_name)\
                                                                        .order_by('-sys_timestamp')[:1]
                        if len(device_frequency):
                            device_frequency = device_frequency[0].current_value
                        else:
                            device_frequency = ''
                    performance_data.update({
                    'frequency':device_frequency
                    })
                except Exception as e:
                    logger.info(device)
                    logger.info(e.message)
                    device_frequency=''
                    pass

                try:
                    if int(freeze_time):
                        device_pl= PerformanceNetwork.objects.filter(device_name=device_name,
                                                                     service_name='ping',
                                                                     data_source='pl',
                                                                     sys_timestamp__lte=int(freeze_time)/1000).\
                                                                     using(alias=device_machine_name).\
                                                                     order_by('-sys_timestamp')[:1]
                        if len(device_pl):
                            device_pl = device_pl[0].current_value
                        else:
                            device_pl = ''
                    else:
                        device_pl= NetworkStatus.objects.filter(device_name= device_name,
                                                                service_name= 'ping',
                                                                data_source= 'pl').\
                                                                using(alias= device_machine_name).\
                                                                order_by('-sys_timestamp')[:1]
                        if len(device_pl):
                            device_pl = device_pl[0].current_value
                        else:
                            device_pl = ''

                except Exception as e:
                    logger.info(device)
                    logger.info(e.message)
                    device_pl=''
                    pass

                try:
                    if len(device_frequency):
                        corrected_dev_freq = device_frequency

                        try:
                            chek_dev_freq = ast.literal_eval(device_frequency)
                            if int(chek_dev_freq) > 10:
                                corrected_dev_freq = chek_dev_freq
                        except Exception as e:
                            logger.info(device)
                            logger.exception("Frequency is Empty : %s" %(e.message))

                        device_frequency_objects = DeviceFrequency.objects.filter(value__icontains=str(corrected_dev_freq))
                        device_frequency_color= DeviceFrequency.objects.filter(value__icontains=str(corrected_dev_freq)).\
                                                                               values_list('color_hex_value', flat=True)

                        device_frequency_object = None
                        if len(device_frequency_objects):
                            device_frequency_object = device_frequency_objects[0]

                        if len(device_frequency_color):
                            device_link_color= device_frequency_color[0]

                        if device.sector_configured_on.exists():
                            ##device is sector device
                            device_sector_objects = device.sector_configured_on.filter()
                            if len(device_sector_objects):
                                sector = device_sector_objects[0]
                                antenna = sector.antenna
                                azimuth_angle = sector.antenna.azimuth_angle if antenna else 'N/A'
                                beam_width = sector.antenna.beam_width if antenna else 'N/A'
                                radius = device_frequency_object.frequency_radius if (
                                    device_frequency_object
                                    and
                                    device_frequency_object.frequency_radius
                                ) else 0
                                performance_data.update({
                                    'azimuth_angle': azimuth_angle,
                                    'beam_width': beam_width,
                                    'radius': radius,
                                    'frequency':device_frequency
                                })

                    if len(device_pl) and int(ast.literal_eval(device_pl))==100:
                        device_link_color='rgb(0,0,0)'

                except Exception as e:

                    if len(device_pl) and int(ast.literal_eval(device_pl))==100:
                        device_link_color='rgb(0,0,0)'

                    else:
                        device_link_color=''
                    logger.info(device)
                    logger.info(e.message)
                    pass

                try:
                    device_performance_value=''
                    if int(freeze_time):
                        device_performance_value= PerformanceService.objects.filter(device_name= device_name,
                                                                               service_name= device_service_name,
                                                                               data_source= device_service_data_source,
                                                                               sys_timestamp__lte= int(freeze_time)/1000).\
                                                                               using(alias=device_machine_name).\
                                                                               order_by('-sys_timestamp')[:1]
                        if len(device_performance_value):
                            device_performance_value = device_performance_value[0].current_value
                        else:
                            device_performance_value = ''
                    else:

                        device_performance_value= ServiceStatus.objects.filter(device_name= device_name,
                                                                               service_name= device_service_name,
                                                                               data_source= device_service_data_source)\
                                                                               .using(alias=device_machine_name)\
                                                                               .order_by('-sys_timestamp')[:1]
                        if len(device_performance_value):
                            device_performance_value = device_performance_value[0].current_value
                        else:
                            device_performance_value = ''

                except Exception as e:
                    device_performance_value=''
                    logger.info(device)
                    logger.info(e.message)
                    pass

                performance_icon=''
                if len(str(device_performance_value)):
                    corrected_device_performance_value = ast.literal_eval(str(device_performance_value))
                    icon_settings_json_string= thematic_settings.icon_settings if thematic_settings.icon_settings!='NULL' else None
                    if icon_settings_json_string:
                        icon_settings_json= eval(icon_settings_json_string)
                        range_start, range_end= None, None
                        for data in icon_settings_json:
                            try:
                                range_number=''.join(re.findall("[0-9]", data.keys()[0]))
                                exec 'range_start=threshold_template.range'+str(range_number)+ '_start'
                                exec 'range_end=threshold_template.range'+str(range_number)+ '_end'
                                ##known bug: the complete range should be checked and not just the values
                                ##between two ranges for example : range 1 = 0,2
                                ##range 2 = 3,5
                                ## value should be checked if it in in range 1
                                ## value should be checked if between range 2 (that is 3,5)
                                if (float(range_start)) <= float(corrected_device_performance_value) <= (float(range_end)):
                                    performance_icon= data.values()[0]
                            except Exception as e:
                                logger.info(device)
                                logger.exception(e.message)
                                continue

                device_info = []
                try:
                    #to update the info window with all the services
                    device_performance_info = ServiceStatus.objects.filter(device_name=device_name).values(
                        'data_source','current_value','sys_timestamp'
                    ).using(alias=device_machine_name)

                    device_inventory_info = InventoryStatus.objects.filter(device_name=device_name).values(
                        'data_source','current_value','sys_timestamp'
                    ).using(alias=device_machine_name)

                    device_status_info = Status.objects.filter(device_name=device_name).values(
                        'data_source','current_value','sys_timestamp'
                    ).using(alias=device_machine_name)

                    device_network_info = NetworkStatus.objects.filter(device_name=device_name).values(
                        'data_source','current_value','sys_timestamp'
                    ).using(alias=device_machine_name)

                    for perf in device_performance_info:
                        perf_info = {
                                "name": perf['data_source'],
                                "title": " ".join(perf['data_source'].split("_")).title(),
                                "show": 1,
                                "value": perf['current_value'],
                            }
                        device_info.append(perf_info)

                    for perf in device_inventory_info:
                        perf_info = {
                                "name": perf['data_source'],
                                "title": " ".join(perf['data_source'].split("_")).title(),
                                "show": 1,
                                "value": perf['current_value'],
                            }
                        device_info.append(perf_info)

                    for perf in device_status_info:
                        perf_info = {
                                "name": perf['data_source'],
                                "title": " ".join(perf['data_source'].split("_")).title(),
                                "show": 1,
                                "value": perf['current_value'],
                            }

                        device_info.append(perf_info)

                    for perf in device_network_info:
                        perf_info = {
                                "name": perf['data_source'],
                                "title": "Latency" if ("rta" in perf['data_source'].lower()) else "Packet Loss",
                                "show": 1,
                                "value": perf['current_value'],
                            }

                        device_info.append(perf_info)

                except Exception as e:
                    logger.info(device)
                    logger.exception(e.message)
                    pass

                performance_data.update({
                    'frequency':device_frequency,
                    'pl':device_pl,
                    'color':device_link_color,
                    'performance_paramter':device_service_name,
                    'performance_value':device_performance_value,
                    'performance_icon':"media/"+str(performance_icon)
                                        if "uploaded" in str(performance_icon)
                                        else ("static/img/" + str(performance_icon) if len(str(performance_icon)) else ""),
                    'device_info' : device_info,
                    'sector_info' : sector_info
                })
                #logger.info(performance_data)
            except Exception as e:
                logger.info(e.message, exc_info=True)
                pass
            return performance_data


" This class is used to add, update or delete point tool data"
class PointToolClass(View):

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(PointToolClass, self).dispatch(*args, **kwargs)

    def post(self, request):
        result = {
            "success": 0,
            "message": "Point can not be saved. Please Try Again.",
            "data": {
                "point_id":0,
            }
        }
        point_data= self.request.body
        if point_data:
            point_data = json.loads(point_data)
            # point_data = json_loads(point_data)
            if(int(point_data["is_delete_req"]) > 0) :
                GISPointTool.objects.filter(pk=point_data['point_id']).delete()
                result["data"]["point_id"] = 0
                result["success"] = 1
                result["message"] = "Point Removed Successfully"

            elif(int(point_data["is_update_req"]) > 0) :

                current_row = GISPointTool.objects.get(pk=point_data['point_id'])
                current_row.name = point_data['name']
                current_row.description = point_data['desc']
                current_row.connected_lat = point_data['connected_lat']
                current_row.connected_lon = point_data['connected_lon']
                current_row.connected_point_type=point_data['connected_point_type']
                current_row.connected_point_info=point_data['connected_point_info']
                # update row with new values
                current_row.save()

                result["data"]["point_id"] = point_data['point_id']
                result["success"] = 1
                result["message"] = "Point Updated Successfully"

            else:
                try:
                    # check that the name already exist in db or not
                    existing_rows_count = len(GISPointTool.objects.filter(name=point_data['name']))

                    if(existing_rows_count == 0):
                        new_row_obj = GISPointTool(
                            name=point_data['name'],
                            description=point_data['desc'],
                            latitude=float(point_data['lat']),
                            longitude=float(point_data['lon']),
                            icon_url=point_data['icon_url'],
                            connected_lat=0,
                            connected_lon=0,
                            connected_point_type='',
                            connected_point_info='',
                            user_id=self.request.user.id
                        )
                        new_row_obj.save()
                        inserted_id = new_row_obj.id
                        result["data"]["point_id"] = inserted_id
                        result["success"] = 1
                        result["message"] = "Point Saved Successfully"
                    else:
                        result["message"] = "Name already exist. Please enter another"

                except Exception as e:
                    logger.info(e.message)
            return HttpResponse(json.dumps(result))
        return HttpResponse(json.dumps(result))

" This class retruns gmap tools(point,line,etc.) data"
class GetToolsData(View):

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(GetToolsData, self).dispatch(*args, **kwargs)

    def get(self, request):

        # initialize exchange format
        result = {
            "success": 0,
            "message": "Data not fetched",
            "data": {
                "points": [],
                "ruler": []
            }
        }
        try:
            # list of columns to be fetched
            required_columns = [
                'id',
                'name',
                'description',
                'icon_url',
                'latitude',
                'longitude',
                'connected_lat',
                'connected_lon',
                'connected_point_type',
                'connected_point_info'
            ]

            # Fetch all the points info associated with logged in user
            point_data_obj = GISPointTool.objects.filter(user_id=request.user.id).values(*required_columns)

            # Loop fetched result & append it to points list
            for point_data in point_data_obj :
                data_object = {
                    "point_id" : "",
                    "lat" : "",
                    "lon" : "",
                    "name" : "",
                    "icon_url" : "",
                    "desc" : "",
                    "connected_lat" : "",
                    "connected_lon" : "",
                    "connected_point_type" : "",
                    "connected_point_info" : ""
                }
                data_object['point_id'] = point_data['id']
                data_object['lat'] = point_data['latitude']
                data_object['lon'] = point_data['longitude']
                data_object['name'] = point_data['name']
                data_object['icon_url'] = point_data['icon_url']
                data_object['desc'] = point_data['description']
                data_object['connected_lat'] = point_data['connected_lat']
                data_object['connected_lon'] = point_data['connected_lon']
                data_object['connected_point_type'] = point_data['connected_point_type']
                data_object['connected_point_info'] = point_data['connected_point_info']

                # Append data to point list
                result["data"]["points"].append(data_object)

            result["success"] = 1
            result["message"] = "Tools Data Fetched Successfully"
        except Exception as e:
            logger.info(e.message)
            result["success"] = 0
            result["data"]["points"] = []
            result["data"]["ruler"] = []
            result["message"] = "Data not Fetched."

        return HttpResponse(json.dumps(result))


##************************************* KMZ Report****************************************##

class KmzListing(ListView):

    model = KMZReport
    template_name = 'devicevisualization/kmz.html'

    def get_context_data(self, **kwargs):

        context = super(KmzListing, self).get_context_data(**kwargs)
        table_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'filename', 'sTitle': 'KMZ', 'sWidth': 'auto', },
            {'mData': 'added_on', 'sTitle': 'Uploaded On', 'sWidth': 'auto'},
            {'mData': 'user', 'sTitle': 'Uploaded By', 'sWidth': 'auto'},
        ]
        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            table_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['table_headers'] = json.dumps(table_headers)
        return context


class Kmzreport_listingtable(BaseDatatableView):

    model = KMZReport
    columns = ['name', 'filename', 'added_on', 'user']
    order_columns = ['name', 'filename', 'added_on', 'user']

    def filter_queryset(self, qs):
        """ Filter datatable as per requested value """

        sSearch = self.request.GET.get('sSearch', None)

        if sSearch:
            query = []
            exec_query = "qs = %s.objects.filter(" % (self.model.__name__)
            for column in self.columns[:-1]:
                # avoid search on 'added_on'
                if column == 'added_on':
                    continue
                query.append("Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ")")

            exec_query += " | ".join(query)
            exec_query += ").values(*" + str(self.columns + ['id']) + ")"
            exec exec_query
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        # condition to fetch KMZ Report data from database
        condition = (Q(user=self.request.user) | Q(is_public=1))
        # Query to fetch L2 reports data from db
        kmzreportresult = KMZReport.objects.filter(condition).values(*self.columns + ['id'])

        report_resultset = []
        for data in kmzreportresult:
            report_object = {}
            report_object['name'] = data['name'].title()
            filename_str_array = data['filename'].split('/')
            report_object['filename'] = filename_str_array[len(filename_str_array)-1]
            report_object['added_on'] = data['added_on']
            username = UserProfile.objects.filter(id=data['user']).values('username')
            report_object['user'] = username[0]['username'].title()
            report_object['id'] = data['id']
            #add data to report_resultset list
            report_resultset.append(report_object)
        return report_resultset

    def prepare_results(self, qs):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            dct.update(actions='<a style="cursor:pointer;" url="{0}" class="delete_kmzreport" title="Delete kmz" >\
                <i class="fa fa-trash-o text-danger"></i></a>\
                <a href="{0}/gmap/view/" title="view on google map">\
                <i class="fa fa-globe"></i></a>\
                <a href="{0}/google_earth/view/" title="view on google earth">\
                <i class="fa fa-globe"></i></a>\
                <a href="{0}/white_background/view/" title="view on white background">\
                <i class="fa fa-globe"></i></a>\
                '.format(dct.pop('id')),
               added_on=dct['added_on'].strftime("%Y-%m-%d") if dct['added_on'] != "" else "")

        return json_data

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except Exception:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except Exception:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ''

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            key_name=order[0][1:] if '-' in order[0] else order[0]
            sorted_device_data = sorted(qs, key=itemgetter(key_name), reverse= True if '-' in order[0] else False)
            return sorted_device_data
        return qs


    def get_context_data(self, *args, **kwargs):
        """
        The main method call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret



class KmzDelete(DeleteView):

    def get(self, request, *args, **kwargs):
        report_id = self.kwargs['kmz_id']
        filename = lambda x: MEDIA_ROOT + x
        # KMZ report object
        kmz_obj = KMZReport.objects.filter(id=report_id).values()
        # remove original file if it exists
        try:
            os.remove(filename(kmz_obj[0]['filename']))
            UserAction.objects.create(user_id=self.request.user.id, module='Kmz Report',
                        action='A kmz report is deleted - {}'.format(kmz_obj[0]['name']))

        except Exception as e:
            logger.info(e.message)
        # delete entry from database
        KMZReport.objects.filter(id=report_id).delete()
        return HttpResponseRedirect(reverse_lazy('kmz_list'))

# class for view kmz file on google map , google earth , white background

class KmzViewAction(View):

    template = ''

    def get(self, request, *args, **kwargs):
        context_data = {}
        page_type = self.kwargs['page_type']
        kmz_id = self.kwargs['kmz_id']

        kmz_resultset = KMZReport.objects.filter(pk=kmz_id).values()
        context_data['file_url'] = kmz_resultset[0]['filename']

        # If page_type is other than google earth & file type is kmz then extract kmz file & pass kml file url
        if page_type != 'google_earth':
            if context_data['file_url'].find(".kmz") > -1 :
                try:
                    kmz_file = ZipFile(str(MEDIA_ROOT+"/"+context_data['file_url']))
                    kml_file_instance = kmz_file.extractall(str(MEDIA_ROOT+"uploaded/kml/"+kmz_resultset[0]['name']+"/"))
                    kml_file = glob.glob(str(MEDIA_ROOT+"uploaded/kml/"+kmz_resultset[0]['name']+"/*.kml"))[0]
                    context_data['file_url'] = "uploaded/kml/"+kmz_resultset[0]['name']+"/"+kml_file[kml_file.rfind("/") + 1:len(kml_file)]
                except Exception, e:
                    logger.info(e.message)

        if page_type == 'white_background':
            template = 'devicevisualization/kmz_whitebg.html'
        elif page_type == 'google_earth':
            template = 'devicevisualization/kmz_earth.html'
        else:
            template = 'devicevisualization/kmz_gmap.html'

        return render_to_response(template,
                context_data,
                context_instance=RequestContext(request))

##************************************ Create KMZ File class **************************************##
class KmzCreate(CreateView):

    template_name = 'devicevisualization/kmzuploadnew.html'
    model = KMZReport
    form_class = KmzReportForm

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        self.object = form.save(commit=False)
        self.object.user =  UserProfile.objects.get(id=self.request.user.id)

        self.object.save()
        return HttpResponseRedirect(reverse_lazy('kmz_list'))


##################################### Points Listing #################################
class PointListingInit(ListView):

    model = GISPointTool
    template_name = 'devicevisualization/points_listing.html'

    def get_context_data(self, **kwargs):

        context = super(PointListingInit, self).get_context_data(**kwargs)
        table_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', },
            {'mData': 'icon_url', 'sTitle': 'Icon', 'sWidth': 'auto', },
            {'mData': 'latitude', 'sTitle': 'Lattitude', 'sWidth': 'auto'},
            {'mData': 'longitude', 'sTitle': 'Longitude', 'sWidth': 'auto'},
            {'mData': 'connected_lat', 'sTitle': 'Connected Lattitude', 'sWidth': 'auto'},
            {'mData': 'connected_lon', 'sTitle': 'Connected Longitude', 'sWidth': 'auto'}
        ]

        context['table_headers'] = json.dumps(table_headers)
        return context


class PointListingTable(BaseDatatableView):

    model = GISPointTool
    columns = ['name', 'description', 'icon_url', 'latitude', 'longitude', 'connected_lat', 'connected_lon']
    order_columns = ['name', 'description', 'latitude', 'longitude', 'connected_lat', 'connected_lon']

    def filter_queryset(self, qs):
        """ Filter datatable as per requested value """

        sSearch = self.request.GET.get('sSearch', None)

        if sSearch:
            query = []
            exec_query = "qs = %s.objects.filter(" % (self.model.__name__)
            for column in self.columns[:-1]:
                # avoid search on 'added_on'
                if column == 'added_on':
                    continue
                query.append("Q(%s__icontains=" % column + "\"" + sSearch + "\"" + ")")

            exec_query += " | ".join(query)
            exec_query += ").values(*" + str(self.columns + ['id']) + ")"
            exec exec_query
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        # Query to fetch L2 reports data from db
        pointsresult = GISPointTool.objects.filter(user_id=self.request.user.id).values(*self.columns + ['id'])

        report_resultset = []
        for data in pointsresult:
            report_object = {}
            report_object['name'] = data['name'].title()
            report_object['description'] = data['description'].title()
            report_object['icon_url'] = "<img src='../../"+data['icon_url']+"' width='32px' height='37px'/>"
            report_object['latitude'] = data['latitude']
            report_object['longitude'] = data['longitude']
            report_object['connected_lat'] = data['connected_lat']
            report_object['connected_lon'] = data['connected_lon']
            report_object['id'] = data['id']
            #add data to report_resultset list
            report_resultset.append(report_object)
        return report_resultset

    def prepare_results(self, qs):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]

        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except Exception:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except Exception:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ''

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            key_name=order[0][1:] if '-' in order[0] else order[0]
            sorted_device_data = sorted(qs, key=itemgetter(key_name), reverse= True if '-' in order[0] else False)
            return sorted_device_data
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main method call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class GISPerfData(View):
    """ GIS Inventory performance data

        Parameters:
            - base_stations (str) - list of base stations in form of string i.e. [1, 2, 3, 4]

        URL:
            - "/network_maps/perf_data/?base_stations=[3019]"

        Returns:
            - performance_data (dictionary) - dictionary containing perf data
                        [
                            {
                                "bs_name": "jaisalmar_jai_raj",
                                "bhSeverity": "NA",
                                "param": {
                                    "sector": [
                                        {
                                            "perf_info": [
                                                {
                                                    "title": "Uas",
                                                    "name": "uas",
                                                    "value": "0",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Management Port On Odu",
                                                    "name": "Management_Port_on_Odu",
                                                    "value": "0.0063",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Radio Interface",
                                                    "name": "Radio_Interface",
                                                    "value": "0.0000",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Uptime",
                                                    "name": "uptime",
                                                    "value": "30127212",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Service Throughput",
                                                    "name": "service_throughput",
                                                    "value": "1.61",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Rssi",
                                                    "name": "rssi",
                                                    "value": "-61",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Site Sync State",
                                                    "name": "site_sync_state",
                                                    "value": "independentUnit",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "2",
                                                    "name": "2",
                                                    "value": "Auto",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "3",
                                                    "name": "3",
                                                    "value": "Auto",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "1",
                                                    "name": "1",
                                                    "value": "forcefullDuplex100Mb",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "4",
                                                    "name": "4",
                                                    "value": "unknown_port_ode",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Latency",
                                                    "name": "rta",
                                                    "value": "45.133",
                                                    "show": 1
                                                },
                                                {
                                                    "title": "Packet Loss",
                                                    "name": "pl",
                                                    "value": "0",
                                                    "show": 1
                                                }
                                            ],
                                            "sector_id": 59,
                                            "color": "",
                                            "polled_frequency": "",
                                            "radius": "",
                                            "perf_value": "-61",
                                            "ip_address": "115.112.159.195",
                                            "beam_width": null,
                                            "icon": "media/uploaded/icons/2014-09-25/2014-09-25-13-59-00_P2P-Green.png",
                                            "sub_station": [
                                                {
                                                    "device_name": "221",
                                                    "data": {
                                                        "substation_device_ip_address": "115.112.159.196",
                                                        "lat": 26.91775,
                                                        "antenna_height": 12,
                                                        "perf_value": "-52",
                                                        "markerUrl": "media/uploaded/icons/2014-09-25/2014-09-25-13-59-00_P2P-Green.png",
                                                        "link_color": "rgba(255, 216, 3, 0.98)",
                                                        "lon": 70.9458611111111,
                                                        "param": {
                                                            "sub_station": [
                                                                {
                                                                    "title": "SS IP",
                                                                    "name": "ss_ip",
                                                                    "value": "115.112.159.196",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "SS MAC",
                                                                    "name": "ss_mac",
                                                                    "value": "00:15:67:2e:94:0e",
                                                                    "show": 0
                                                                },
                                                                {
                                                                    "title": "SS Name",
                                                                    "name": "name",
                                                                    "value": "091jais030007856076",
                                                                    "show": 0
                                                                },
                                                                {
                                                                    "title": "Circuit ID",
                                                                    "name": "cktid",
                                                                    "value": "091JAIS030007856076",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "QOS(BW)",
                                                                    "name": "qos_bandwidth",
                                                                    "value": 2048,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Latitude",
                                                                    "name": "latitude",
                                                                    "value": 26.91775,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Longitude",
                                                                    "name": "longitude",
                                                                    "value": 70.9458611111111,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Antenna Height",
                                                                    "name": "antenna_height",
                                                                    "value": 12,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Polarisation",
                                                                    "name": "polarisation",
                                                                    "value": "NULL",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Technology",
                                                                    "name": "ss_technology",
                                                                    "value": "P2P",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Building Height",
                                                                    "name": "building_height",
                                                                    "value": null,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "tower_height",
                                                                    "name": "tower_height",
                                                                    "value": 40,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "SS MountType",
                                                                    "name": "mount_type",
                                                                    "value": "NULL",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Alias",
                                                                    "name": "alias",
                                                                    "value": "091JAIS030007856076",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "SS Device ID",
                                                                    "name": "ss_device_id",
                                                                    "value": 221,
                                                                    "show": 0
                                                                },
                                                                {
                                                                    "title": "Antenna Type",
                                                                    "name": "antenna_type",
                                                                    "value": "NULL",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Ethernet Extender",
                                                                    "name": "ethernet_extender",
                                                                    "value": "",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Cable Length",
                                                                    "name": "cable_length",
                                                                    "value": null,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Customer Address",
                                                                    "name": "customer_address",
                                                                    "value": "Taj Jaisalmer Jodhpur Jaisalmer Road,, Jaisalmer, Rajasthan 345001,prasitha@dvois.com,Jaisalmer,Rajasthan India 345001",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Date of Acceptance",
                                                                    "name": "date_of_acceptance",
                                                                    "value": "2013-04-01",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "RSSI During Acceptance",
                                                                    "name": "dl_rssi_during_acceptance",
                                                                    "value": null,
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Planned Frequency",
                                                                    "name": "planned_frequency",
                                                                    "value": "",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Service Throughput",
                                                                    "name": "service_throughput",
                                                                    "value": "2.14",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Uas",
                                                                    "name": "uas",
                                                                    "value": "0",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Management Port On Odu",
                                                                    "name": "Management_Port_on_Odu",
                                                                    "value": "0.0045",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Radio Interface",
                                                                    "name": "Radio_Interface",
                                                                    "value": "0.0000",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Uptime",
                                                                    "name": "uptime",
                                                                    "value": "1174212",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Rssi",
                                                                    "name": "rssi",
                                                                    "value": "-52",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Cbw",
                                                                    "name": "cbw",
                                                                    "value": "5000",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Frequency",
                                                                    "name": "frequency",
                                                                    "value": "5855",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Idu Sn",
                                                                    "name": "idu_sn",
                                                                    "value": "unknown_value",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Link Distance",
                                                                    "name": "link_distance",
                                                                    "value": "3300",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Mimo Diversity",
                                                                    "name": "mimo_diversity",
                                                                    "value": "unknown_value",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Producttype",
                                                                    "name": "producttype",
                                                                    "value": "WL1000-ACCESS/F58/ID",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Ssid",
                                                                    "name": "ssid",
                                                                    "value": "SELUCREH091JAIS03000",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Site Sync State",
                                                                    "name": "site_sync_state",
                                                                    "value": "notSupported",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "2",
                                                                    "name": "2",
                                                                    "value": "Auto",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "3",
                                                                    "name": "3",
                                                                    "value": "Auto",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "1",
                                                                    "name": "1",
                                                                    "value": "Auto",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "4",
                                                                    "name": "4",
                                                                    "value": "unknown_port_ode",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Latency",
                                                                    "name": "rta",
                                                                    "value": "56.952",
                                                                    "show": 1
                                                                },
                                                                {
                                                                    "title": "Packet Loss",
                                                                    "name": "pl",
                                                                    "value": "0",
                                                                    "show": 1
                                                                }
                                                            ]
                                                        }
                                                    },
                                                    "id": 221,
                                                    "name": "091jais030007856076"
                                                }
                                            ],
                                            "device_name": "220",
                                            "azimuth_angle": 0,
                                            "pl": "0"
                                        }
                                    ]
                                },
                                "bh_info": [
                                    {
                                        "show": 1,
                                        "name": "pl",
                                        "value": "NA",
                                        "title": "Packet Drop"
                                    },
                                    {
                                        "show": 1,
                                        "name": "rta",
                                        "value": "NA",
                                        "title": "Latency"
                                    }
                                ],
                                "bs_id": 57,
                                "bs_alias": "Jaisalmar",
                                "message": "Successfully fetched performance data."
                            }
                        ]
    """

    def get(self, request):
        # get base stations id's list
        bs_ids = eval(str(self.request.GET.get('base_stations', None)))
        print "###################################### bs_ids - ", bs_ids

        # performance data dictionary
        performance_data = list()

        # loop through all base stations having id's in bs_ids list
        try:
            for bs_id in bs_ids:
                print "################################## bs_id - ", bs_id
                # base station data dictionary
                bs_dict = dict()

                # base station
                bs = ""
                try:
                    bs = BaseStation.objects.get(pk=bs_id)
                    bs_dict['bs_name'] = bs.name
                    bs_dict['bs_alias'] = bs.alias
                    bs_dict['bs_id'] = bs_id
                    bs_dict['message'] = "Failed to fetch performance data."
                    bs_dict['param'] = dict()
                    bs_dict['param']['sector'] = list()
                except Exception as e:
                    logger.exception("Base Station not exist. Exception: ", e.message)

                # if base station exist
                if bs:
                    # get all sectors associated with base station (bs)
                    sectors = bs.sector.all()
                    print "################################### sectors - ", sectors

                    # backhaul device
                    backhaul_device = ""
                    try:
                        backhaul_device = bs.backhaul.bh_configured_on
                    except Exception as e:
                        logger.exception("No backhaul device found. Exception: ", e.message)

                    # backhaul data
                    if backhaul_device and backhaul_device.is_added_to_nms == 1:
                        backhaul_data = self.get_backhaul_info(backhaul_device)
                        bs_dict['bh_info'] = backhaul_data['bh_info'] if 'bh_info' in backhaul_data else []
                        bs_dict['bhSeverity'] = backhaul_data['bhSeverity'] if 'bhSeverity' in backhaul_data else "NA"

                    # loop through all sectors
                    for sector_obj in sectors:
                        # sector
                        sector = sector_obj

                        # sector configured on device
                        sector_device = sector.sector_configured_on

                        # get performance data
                        sector_performance_data = self.get_sector_performance_info(sector_device)
                        print "###################################### sector_performance_data - ", sector_performance_data

                        # sector dictionary
                        sector_dict = dict()
                        sector_dict['device_name'] = sector_device.device_name
                        sector_dict['sector_id'] = sector.id
                        sector_dict['ip_address'] = sector_device.ip_address
                        sector_dict['azimuth_angle'] = sector_performance_data['azimuth_angle']
                        sector_dict['beam_width'] = sector_performance_data['beam_width']
                        sector_dict['radius'] = sector_performance_data['radius']
                        sector_dict['color'] = sector_performance_data['color']
                        sector_dict['polled_frequency'] = sector_performance_data['polled_frequency']
                        sector_dict['pl'] = sector_performance_data['pl']
                        sector_dict['perf_value'] = sector_performance_data['perf_value']
                        sector_dict['icon'] = sector_performance_data['icon']
                        sector_dict['perf_info'] = sector_performance_data['perf_info']
                        sector_dict['sub_station'] = list()

                        # get all substations associated with sector from 'Topology' model in performance
                        # replaceing topology code
                        # as the topology is auto-updated
                        # using celery beat
                        subs = SubStation.objects.filter(id__in=sector.circuit_set.values_list('sub_station', flat=True))
                        # topolopies_for_ss = Topology.objects.filter(sector_id=sector.id)

                        # list of all associated substations ip's
                        # substations_ips_list = list()
                        # for topology in topolopies_for_ss:
                        #     substations_ips_list.append(topology.connected_device_ip)

                        # loop through all substations using ips in 'substations_ips_list'
                        for ss in subs:
                            # substation
                            substation = None
                            substation = ss
                            # try:
                            #     substation = SubStation.objects.get(device__ip_address=ss_ip)
                            # except Exception as e:
                            #     logger.exception("Sub Station not exist. Exception: ", e.message)

                            # substation device
                            substation_device = None
                            try:
                                substation_device = ss.device
                                # Device.objects.get(ip_address=ss_ip)
                            except Exception as e:
                                logger.exception("Sub Station device not exist. Exception: ", e.message)

                            ss_dict = dict()
                            if substation and substation_device:
                                # substation default line color
                                ss_default_link_color = sector_performance_data['color']
                                ss_dict['device_name'] = substation_device.device_name
                                ss_dict['id'] = substation_device.id
                                ss_dict['name'] = substation.name
                                ss_dict['data'] = self.get_substation_info(substation,
                                                                           substation_device,
                                                                           ss_default_link_color)

                            # append substation dictionary to 'sub_station' list
                            sector_dict['sub_station'].append(ss_dict)
                            print "################################# sector_dict - ", sector_dict

                        # append 'sector_dict' to 'sector' list
                        bs_dict['param']['sector'].append(sector_dict)
                if bs_dict:
                    bs_dict['message'] = "Successfully fetched performance data."
                    performance_data.append(bs_dict)
        except Exception as e:
            logger.exception("Last Exception - ", e.message)
            performance_data = {'message': "No Base Station to fetch performance data."}

        return HttpResponse(json.dumps(eval(str(performance_data))))

    def get_backhaul_info(self, bh_device):
        """ Get Sector performance info

            Parameters:
                - bh_device (<class 'device.models.Device'>) - backhaul device for e.g. 10.175.102.3

            Returns:
               - backhaul_data (dictionary) - dictionary containing backhaul performance data
                                                {
                                                    'bhSeverity': 'NA',
                                                    'bh_info': [
                                                        {
                                                            'title': 'PacketDrop',
                                                            'name': 'pl',
                                                            'value': 'NA',
                                                            'show': 1
                                                        },
                                                        {
                                                            'title': 'Latency',
                                                            'name': 'rta',
                                                            'value': 'NA',
                                                            'show': 1
                                                        }
                                                    ]
                                                }
        """

        # backhaul data
        backhaul_data = dict()
        backhaul_data['bh_info'] = list()
        backhaul_data['bhSeverity'] = "NA"

        # backhaul pl dictionary
        pl_dict = dict()
        pl_dict['name'] = "pl"
        pl_dict['show'] = 1
        pl_dict['title'] = "Packet Drop"

        # backhaul rta dictionary
        rta_dict = dict()
        rta_dict['name'] = "rta"
        rta_dict['show'] = 1
        rta_dict['title'] = "Latency"

        # pl
        try:
            pl_dict['value'] = NetworkStatus.objects.filter(device_name=bh_device,
                                                            data_source='pl').using(
                                                            alias=bh_device.machine.name)[0].current_value
        except Exception as e:
            pl_dict['value'] = "NA"
            logger.exception("PL not exist for backhaul device ({}). Exception: ".format(bh_device.device_name,
                                                                                    e.message))

        # rta
        try:
            rta_dict['value'] = NetworkStatus.objects.filter(device_name=bh_device,
                                                            data_source='rta').using(
                                                            alias=bh_device.machine.name)[0].current_value
        except Exception as e:
            rta_dict['value'] = "NA"
            logger.exception("RTA not exist for backhaul device ({}). Exception: ".format(bh_device.device_name,
                                                                                     e.message))

        # bh severity
        try:
            backhaul_data['bhSeverity'] = NetworkStatus.objects.filter(device_name=bh_device).using(
                                                                       alias=bh_device.machine.name)[0].severity
        except Exception as e:
            logger.exception("BH Severity not exist for backhaul device ({}). Exception: ".format(bh_device.device_name,
                                                                                             e.message))

        # append 'pl_dict' to 'bh_info' list
        backhaul_data['bh_info'].append(pl_dict)

        # append 'rta_dict' to 'bh_info' list
        backhaul_data['bh_info'].append(rta_dict)

        return backhaul_data

    def get_sector_performance_info(self, device):
        """ Get Sector performance info

            Parameters:
                - device (<class 'device.models.Device'>) - device name

            Returns:
               - performance_data (dictionary) - dictionary containing sector performance data
                                                    {
                                                        'perf_info': [

                                                        ],
                                                        'color': '',
                                                        'polled_frequency': '',
                                                        'radius': '',
                                                        'beam_width': None,
                                                        'icon': 'static/img/icons/mobilephonetower10.png',
                                                        'azimuth_angle': 0.0,
                                                        'pl': '',
                                                        'perf_value': [

                                                        ]
                                                    }
        """
        print "@@@@@@@@@@@@@@@@@@@@@@@@@@@ Enter in sector_performance - ."
        # device name
        device_name = device.device_name

        # machine name
        machine_name = device.machine.name

        print "********************************* device_name - ", device_name
        print "********************************* machine_name - ", machine_name

        # performance dictionary
        performance_data = dict()
        performance_data['azimuth_angle'] = ""
        performance_data['beam_width'] = ""
        performance_data['radius'] = ""
        performance_data['color'] = ""
        performance_data['polled_frequency'] = ""
        performance_data['pl'] = ""
        performance_data['perf_value'] = ""
        performance_data['icon'] = ""
        try:
            performance_data['perf_info'] = self.get_device_info(device, machine_name)
        except Exception as e:
            print "^^^^^^^^^^^^^^^^^^^^^^^^^^^ DEVICE INFO EXCEPTION ^^^^^^^^^^^^^^^^^^^^^^^^^^"
            logger.exception(e.message)
        print "************************************ performance_data['perf_info'] - ", performance_data['perf_info']

        # freeze time (data fetched from freeze time to latest time)
        freeze_time = self.request.GET.get('freeze_time', '0')

        # type of thematic settings needs to be fetched
        ts_type = self.request.GET.get('ts', 'normal')

        # device technology
        try:
            device_technology = DeviceTechnology.objects.get(id=device.device_technology)
        except Exception as e:
            device_technology = ""
            logger.exception("Device technology not exist. Exception: ", e.message)

        # thematic settings for current user
        user_thematics = self.get_thematic_settings(device_technology)

        # service & data source
        service = ""
        data_source = ""
        try:
            if ts_type == "normal":
                service = user_thematics.thematic_template.threshold_template.live_polling_template.service.name
                data_source = user_thematics.thematic_template.threshold_template.live_polling_template.data_source.name
            elif ts_type == "ping":
                service = user_thematics.thematic_template.service
                data_source = user_thematics.thematic_template.data_source
        except Exception as e:
            logger.exception("No thematic setting for device {}. Exception: ".format(device_name, e.message))

        # device frequency
        device_frequency = self.get_device_polled_frequency(device_name, machine_name, freeze_time)

        # update device frequency
        performance_data['polled_frequency'] = device_frequency

        # device pl
        device_pl = self.get_device_pl(device_name, machine_name, freeze_time)

        # update device pl
        performance_data['pl'] = device_pl

        # device link/frequency color
        device_link_color = self.get_frequency_color_and_radius(device_frequency, device_pl)[0]

        # update performance color
        performance_data['color'] = device_link_color

        # antenna polarization, azimuth angle, beam width and radius
        polarization = ""
        azimuth_angle = ""
        beam_width = ""
        radius = ""
        try:
            # if device is a 'sector configured on' device; than fetch antenna info too
            if device.sector_configured_on.exists():
                # sector to which device is associated
                device_sector_objects = device.sector_configured_on.filter()

                if len(device_sector_objects):
                    sector = device_sector_objects[0]
                    # sector antenna
                    antenna = sector.antenna
                    # azimuth angle
                    azimuth_angle = sector.antenna.azimuth_angle if antenna else 'N/A'
                    # beam width
                    beam_width = sector.antenna.beam_width if antenna else 'N/A'
                    # radius
                    radius = self.get_frequency_color_and_radius(device_frequency, device_pl)[1]
        except Exception as e:
            logger.exception(logger.exception("Device is not sector configured on or not exist. Exception: ", e.message))

        # update azimuth_angle, beam_width, radius
        performance_data['azimuth_angle'] = azimuth_angle
        performance_data['beam_width'] = beam_width
        performance_data['radius'] = radius
        performance_value = ""

        # performance value
        perf_payload = {
            'device_name': device_name,
            'machine_name': machine_name,
            'freeze_time': freeze_time,
            'device_service_name': service,
            'device_service_data_source': data_source

        }
        performance_value = self.get_performance_value(perf_payload, ts_type)

        if user_thematics:
            # icon
            icon = ""

            # device type
            device_type = DeviceType.objects.get(pk=device.device_type)

            try:
                icon = "media/" + str(device_type.device_icon)
            except Exception as e:
                logger.exception("No icon for device type ({}). Exception: {}".format(device_type.alias, e.message))

            # fetch icon settings for thematics as per thematic type selected i.e. 'ping' or 'normal'
            th_icon_settings = ""
            try:
                th_icon_settings = user_thematics.thematic_template.icon_settings
            except Exception as e:
                logger.exception("No icon settings for thematic settings. Exception: ", e.message)

            # fetch thematic ranges as per thematic type selected i.e. 'ping' or 'normal'
            th_ranges = ""
            try:
                if ts_type == "ping":
                    th_ranges = user_thematics.thematic_template
                elif ts_type == "normal":
                    th_ranges = user_thematics.thematic_template.threshold_template
                else:
                    pass
            except Exception as e:
                logger.exception("No ranges for thematic settings. Exception: ", e.message)

            # fetch service type if 'ts_type' is "normal"
            service_type = ""
            try:
                if ts_type == "normal":
                    service_type = user_thematics.thematic_template.threshold_template.service_type
            except Exception as e:
                logger.exception("Service Type not exist. Exception: ", e.message)

            # comparing threshold values to get icon
            try:
                if len(performance_value):
                    # live polled value of device service
                    value = ast.literal_eval(str(performance_value))

                    # get appropriate icon
                    if ts_type == "normal":
                        if service_type == "INT":
                            icon = self.get_icon_for_numeric_service(th_ranges, th_icon_settings, value)
                        elif service_type == "STR":
                            icon = self.get_icon_for_string_service(th_ranges, th_icon_settings, value)
                        else:
                            pass
                    elif ts_type == "ping":
                        icon = self.get_icon_for_numeric_service(th_ranges, th_icon_settings, value)
                    else:
                        pass
            except Exception as e:
                logger.exception("Icon not exist. Exception: ", e.message)

            # update performance value
            performance_data['perf_value'] = performance_value

            # update performance icon
            performance_data['icon'] = icon

        return performance_data

    def get_icon_for_numeric_service(self, th_ranges=None, th_icon_settings=None, value=None):
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

            Returns:
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"
        """
        # default image to be loaded
        image_partial = "icons/mobilephonetower10.png"

        if th_ranges and th_icon_settings and len(str(value)):
            try:
                if (float(th_ranges.range1_start)) <= (float(value)) <= (float(th_ranges.range1_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings1' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings1'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range2_start)) <= (float(value)) <= (float(th_ranges.range2_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings2' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings2'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range3_start)) <= (float(value)) <= (float(th_ranges.range3_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings3' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings3'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range4_start)) <= (float(value)) <= (float(th_ranges.range4_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings4' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings4'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range5_start)) <= (float(value)) <= (float(th_ranges.range5_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings5' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings5'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range6_start)) <= (float(value)) <= (float(th_ranges.range6_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings6' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings6'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range7_start)) <= (float(value)) <= (float(th_ranges.range7_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings7' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings7'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range8_start)) <= (float(value)) <= (float(th_ranges.range8_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings8' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings8'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range9_start)) <= (float(value)) <= (float(th_ranges.range9_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings9' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings9'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if (float(th_ranges.range10_start)) <= (float(value)) <= (float(th_ranges.range10_end)):
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings10' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings10'])
            except Exception as e:
                logger.exception(e.message)

        # image url
        img_url = "media/" + str(image_partial) if "uploaded" in str(
            image_partial) else "static/img/" + str(image_partial)

        # icon to be send in response
        icon = str(img_url)

        return icon

    def get_icon_for_string_service(self, th_ranges=None, th_icon_settings=None, value=None):
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

            Returns:
                - icon (str) - icon location i.e "media/uploaded/icons/2014/09/18/wifi3.png"
        """

        # default image to be loaded
        image_partial = "icons/mobilephonetower10.png"

        if th_ranges and th_icon_settings and value:
            try:
                if str(value).lower().strip() == str(th_ranges.range1_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings1' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings1'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range2_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings2' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings2'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range3_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings3' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings3'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range4_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings4' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings4'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range5_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings5' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings5'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range6_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings6' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings6'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range7_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings7' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings7'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range8_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings8' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings8'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range9_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings9' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings9'])
            except Exception as e:
                logger.exception(e.message)

            try:
                if str(value).lower().strip() == str(th_ranges.range10_start).lower().strip():
                    icon_settings = eval(th_icon_settings)
                    for icon_setting in icon_settings:
                        if 'icon_settings10' in icon_setting.keys():
                            image_partial = str(icon_setting['icon_settings10'])
            except Exception as e:
                logger.exception(e.message)

        # image url
        img_url = "media/" + str(image_partial) if "uploaded" in str(
            image_partial) else "static/img/" + str(image_partial)

        # icon to be send in response
        icon = str(img_url)

        return icon

    def get_device_info(self, device_obj, machine_name, device_pl="", substation=False):
        """ Get Sector/Sub Station device information

            Parameters:
                - device_name (unicode) - device name
                - machine_name (unicode) - machine name
                - substation (bool) - tell whether device is substation device or not

            Returns:
                - device_info (list) - list of dictionaries containing device static or polled data
                                                    [
                                                        {
                                                            'show': 1,
                                                            'name': u'uptime',
                                                            'value': u'6.0082333333',
                                                            'title': u'Uptime'
                                                        },
                                                        {
                                                            'show': 1,
                                                            'name': u'frequency',
                                                            'value': u'5830',
                                                            'title': u'Frequency'
                                                        },
                                                        {
                                                            'show': 1,
                                                            'name': u'pl',
                                                            'value': u'4',
                                                            'title': 'PacketLoss'
                                                        }
                                                    ]
        """
        # device info dictionary
        device_info = list()
        # is device is a substation device than add static inventory parameters in list
        if substation:
            # substation
            substation = ""
            try:
                substation = SubStation.objects.get(device=device_obj)
            except Exception as e:
                logger.exception("Sub Station not exist. Exception: ", e.message)

            # substation device
            substation_device = ""
            try:
                substation_device = device_obj
            except Exception as e:
                logger.exception("Sub Station device not exist. Exception: ", e.message)

            # substation technology
            substation_technology = ""
            try:
                substation_technology = DeviceTechnology.objects.get(id=substation_device.device_technology).name
            except Exception as e:
                logger.exception("Sub Station has no technology. Exception: ", e.message)

            # circuit id
            circuit_id = ""
            try:
                circuit_id = substation.circuit_set.all()[0].circuit_id
            except Exception as e:
                logger.exception("Circuit ID not exist. Exception: ", e.message)

            # qos bandwidth
            qos = ""
            try:
                qos = substation.circuit_set.all()[0].qos_bandwidth
            except Exception as e:
                logger.exception("QOS not exist. Exception: ", e.message)

            # customer address
            customer_address = ""
            try:
                customer_address = substation.circuit_set.all()[0].customer.address
            except Exception as e:
                logger.exception("Customer Address not exist. Exception: ", e.message)

            # date of acceptance
            date_of_acceptance = ""
            try:
                date_of_acceptance = str(substation.circuit_set.all()[0].date_of_acceptance)
            except Exception as e:
                logger.exception("Date Of Acceptance not exist. Exception: ", e.message)

            # dl rssi during acceptance
            dl_rssi_during_acceptance = ""
            try:
                dl_rssi_during_acceptance = substation.circuit_set.all()[0].dl_rssi_during_acceptance
            except Exception as e:
                logger.exception("DL RSSI During Acceptance not exist. Exception: ", e.message)

            # ss sector frequency
            ss_sector_frequency = ""
            try:
                ss_sector_frequency = substation.circuit_set.all()[0].sector.frequency.value
            except Exception as e:
                logger.exception("SS Sector Frequency not exist. Exception: ", e.message)

            # antenna height
            antenna_height = ""
            try:
                antenna_height = substation.antenna.height
            except Exception as e:
                logger.exception("Antenna Height not exist. Exception: ", e.message)

            # antenna polarization
            antenna_polarization = ""
            try:
                antenna_polarization = substation.antenna.polarization
            except Exception as e:
                logger.exception("Antenna Polarization not exist. Exception: ", e.message)

            # antenna mount type
            antenna_mount_type = ""
            try:
                antenna_mount_type = substation.antenna.mount_type

            except Exception as e:
                logger.exception("Antenna Type not exist. Exception: ", e.message)

            # antenna type
            antenna_type = ""
            try:
                antenna_type = substation.antenna.antenna_type

            except Exception as e:
                logger.exception("Antenna Type not exist. Exception: ", e.message)

            # adding gis inventory static parameters to device info
            device_info = [
                {
                    'name': 'ss_ip',
                    'title': 'SS IP',
                    'show': 1,
                    'value': substation_device.ip_address
                },
                {
                    'name': 'ss_mac',
                    'title': 'SS MAC',
                    'show': 0,
                    'value': substation_device.mac_address
                },
                {
                    'name': 'name',
                    'title': 'SS Name',
                    'show': 0,
                    'value': substation.name
                },
                {
                    'name': 'cktid',
                    'title': 'Circuit ID',
                    'show': 1,
                    'value': circuit_id
                },
                {
                    'name': 'qos_bandwidth',
                    'title': 'QOS(BW)',
                    'show': 1,
                    'value': qos
                },
                {
                    'name': 'latitude',
                    'title': 'Latitude',
                    'show': 1,
                    'value': substation.latitude
                },
                {
                    'name': 'longitude',
                    'title': 'Longitude',
                    'show': 1,
                    'value': substation.longitude
                },
                {
                    'name': 'antenna_height',
                    'title': 'Antenna Height',
                    'show': 1,
                    'value': antenna_height
                },
                {
                    'name': 'polarisation',
                    'title': 'Polarisation',
                    'show': 1,
                    'value': antenna_polarization
                },
                {
                    'name': 'ss_technology',
                    'title': 'Technology',
                    'show': 1,
                    'value': substation_technology
                },
                {
                    'name': 'building_height',
                    'title': 'Building Height',
                    'show': 1,
                    'value': substation.building_height
                },
                {
                    'name': 'tower_height',
                    'title': 'tower_height',
                    'show': 1,
                    'value': substation.tower_height
                },
                {
                    'name': 'mount_type',
                    'title': 'SS MountType',
                    'show': 1,
                    'value': antenna_mount_type
                },
                {
                    'name': 'alias',
                    'title': 'Alias',
                    'show': 1,
                    'value': substation.alias
                },
                {
                    'name': 'ss_device_id',
                    'title': 'SS Device ID',
                    'show': 0,
                    'value': substation_device.id
                },
                {
                    'name': 'antenna_type',
                    'title': 'Antenna Type',
                    'show': 1,
                    'value': antenna_type
                },
                {
                    'name': 'ethernet_extender',
                    'title': 'Ethernet Extender',
                    'show': 1,
                    'value': substation.ethernet_extender
                },
                {
                    'name': 'cable_length',
                    'title': 'Cable Length',
                    'show': 1,
                    'value': substation.cable_length
                },
                {
                    'name': 'customer_address',
                    'title': 'Customer Address',
                    'show': 1,
                    'value': customer_address
                },
                {
                    'name': 'date_of_acceptance',
                    'title': 'Date of Acceptance',
                    'show': 1,
                    'value': date_of_acceptance
                },
                {
                    'name': 'dl_rssi_during_acceptance',
                    'title': 'RSSI During Acceptance',
                    'show': 1,
                    'value': dl_rssi_during_acceptance
                },
                {
                    'name': 'planned_frequency',
                    'title': 'Planned Frequency',
                    'show': 1,
                    'value': ss_sector_frequency
                }
            ]

        # if device is down than don't show any performance data
        if device_pl != "100":
            print "******************************** ENTER IN PL = 100 "
            # get device name
            device_name = device_obj.device_name
            print "******************************** DEVICE NAME - ", device_name
            
            # get device id (used to make url for perf api data)
            device_id = device_obj.id

            # to update the info window with all the services
            # device performance info
            device_performance_info = ServiceStatus.objects.filter(device_name=device_name).values(
                'data_source', 'current_value', 'sys_timestamp'
            ).using(alias=machine_name)

            # device inventory info
            device_inventory_info = InventoryStatus.objects.filter(device_name=device_name).values(
                'data_source', 'current_value', 'sys_timestamp'
            ).using(alias=machine_name)

            # device status info
            device_status_info = Status.objects.filter(device_name=device_name).values(
                'data_source', 'current_value', 'sys_timestamp'
            ).using(alias=machine_name)

            # device network info
            device_network_info = NetworkStatus.objects.filter(device_name=device_name).values(
                'data_source', 'current_value', 'sys_timestamp'
            ).using(alias=machine_name)

            processed = {}

            for perf in device_performance_info:
                res, name, title = self.sanatize_datasource(perf['data_source'])
                if not res:
                    continue
                if perf['data_source'] in processed:
                    continue
                processed[perf['data_source']] = []

                service_name = ""

                if name in ['pl', 'rta']:
                    service_name = 'ping'
                else:
                    service_name = name

                perf_info = {
                    "name": name,
                    "title": title,
                    "show": 1,
                    "url": "performance/service/" + service_name + "/service_data_source/" + name + "/device/" + str(device_id) + "?start_date=&end_date=",
                    "value": perf['current_value'],
                }
                device_info.append(perf_info)

            for perf in device_inventory_info:
                res, name, title = self.sanatize_datasource(perf['data_source'])
                if not res:
                    continue
                if perf['data_source'] in processed:
                    continue
                processed[perf['data_source']] = []

                if name in ['pl', 'rta']:
                    service_name = 'ping'
                else:
                    service_name = name

                perf_info = {
                    "name": name,
                    "title": title,
                    "show": 1,
                    "url": "performance/service/" + service_name + "/service_data_source/" + name + "/device/" + str(device_id) + "?start_date=&end_date=",
                    "value": perf['current_value'],
                }
                device_info.append(perf_info)

            for perf in device_status_info:
                res, name, title = self.sanatize_datasource(perf['data_source'])
                if not res:
                    continue
                if perf['data_source'] in processed:
                    continue
                processed[perf['data_source']] = []

                if name in ['pl', 'rta']:
                    service_name = 'ping'
                else:
                    service_name = name

                perf_info = {
                    "name": name,
                    "title": title,
                    "show": 1,
                    "url": "performance/service/" + service_name + "/service_data_source/" + name + "/device/" + str(device_id) + "?start_date=&end_date=",
                    "value": perf['current_value'],
                }
                device_info.append(perf_info)

            for perf in device_network_info:
                res, name, title = self.sanatize_datasource(perf['data_source'])
                if not res:
                    continue
                if perf['data_source'] in processed:
                    continue
                processed[perf['data_source']] = []

                if name in ['pl', 'rta']:
                    service_name = 'ping'
                else:
                    service_name = name

                perf_info = {
                    "name": name,
                    "title": title,
                    "show": 1,
                    "url": "performance/service/" + service_name + "/service_data_source/" + name + "/device/" + str(device_id) + "?start_date=&end_date=",
                    "value": perf['current_value'],
                }
                device_info.append(perf_info)

        # remove duplicate dictionaries in list
        device_info = remove_duplicate_dict_from_list(device_info)

        return device_info

    def sanatize_datasource(self, data_source):
        """

        :return: False is condition does not match else return name,title
        """
        if data_source and data_source[:1].isalpha():
            title = " ".join(data_source.split("_")).title()
            name = data_source.strip().lower()
            try:
                title = SERVICE_DATA_SOURCE[name]['display_name']
            except:
                pass
            return True, name, title
        return False, False, False

    def get_substation_info(self, substation, substation_device, ss_default_link_color):
        """ Get Sub Station information

            Parameters:
                - substation (<class 'inventory.models.SubStation'>) - substation object
                - substation_device (<class 'device.models.Device'>) - substation device object

            Returns:
               - substation_info (dict) - dictionary containing substation data
                                                    {
                                                        'antenna_height': 33.0,
                                                        'link_color': u'rgba(255,
                                                        192,
                                                        0,
                                                        0.97)',
                                                        'lon': 75.8075,
                                                        'param': {
                                                            'sub_station': [
                                                                {
                                                                    'show': 1,
                                                                    'name': 'ss_ip',
                                                                    'value': u'10.75.165.227',
                                                                    'title': 'SSIP'
                                                                },
                                                                {
                                                                    'show': 0,
                                                                    'name': 'ss_mac',
                                                                    'value': u'00: 15: 67: 51: 5e: 34',
                                                                    'title': 'SSMAC'
                                                                },
                                                                {
                                                                    'show': 0,
                                                                    'name': 'name',
                                                                    'value': u'091jaip623009280393',
                                                                    'title': 'SSName'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'cktid',
                                                                    'value': u'091JAIP623009280393',
                                                                    'title': 'CircuitID'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'qos_bandwidth',
                                                                    'value': 512.0,
                                                                    'title': 'QOS(BW)'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'latitude',
                                                                    'value': 26.9138611111111,
                                                                    'title': 'Latitude'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'longitude',
                                                                    'value': 75.8075,
                                                                    'title': 'Longitude'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'antenna_height',
                                                                    'value': 33.0,
                                                                    'title': 'AntennaHeight'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'polarisation',
                                                                    'value': None,
                                                                    'title': 'Polarisation'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'ss_technology',
                                                                    'value': u'P2P',
                                                                    'title': 'Technology'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'building_height',
                                                                    'value': None,
                                                                    'title': 'BuildingHeight'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'tower_height',
                                                                    'value': None,
                                                                    'title': 'tower_height'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'mount_type',
                                                                    'value': None,
                                                                    'title': 'SSMountType'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'alias',
                                                                    'value': u'091JAIP623009280393',
                                                                    'title': 'Alias'
                                                                },
                                                                {
                                                                    'show': 0,
                                                                    'name': 'ss_device_id',
                                                                    'value': 15864L,
                                                                    'title': 'SSDeviceID'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'antenna_type',
                                                                    'value': None,
                                                                    'title': 'AntennaType'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'ethernet_extender',
                                                                    'value': None,
                                                                    'title': 'EthernetExtender'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'cable_length',
                                                                    'value': None,
                                                                    'title': 'CableLength'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'customer_address',
                                                                    'value': u'IDBIFederalLifeInsuranceCo.Ltd.
                                                                               OfficeNO.802at8thFloorE-2,
                                                                               KJTower,, AshokMarg, C-Scheme,
                                                                               Jaipur, RajasthanIndia302001',
                                                                    'title': 'CustomerAddress'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'date_of_acceptance',
                                                                    'value': None,
                                                                    'title': 'DateofAcceptance'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'dl_rssi_during_acceptance',
                                                                    'value': None,
                                                                    'title': 'RSSIDuringAcceptance'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': 'planned_frequency',
                                                                    'value': '',
                                                                    'title': 'PlannedFrequency'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': u'uptime',
                                                                    'value': u'6.0082333333',
                                                                    'title': u'Uptime'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': u'frequency',
                                                                    'value': u'5830',
                                                                    'title': u'Frequency'
                                                                },
                                                                {
                                                                    'show': 1,
                                                                    'name': u'pl',
                                                                    'value': u'4',
                                                                    'title': 'PacketLoss'
                                                                }
                                                            ]
                                                        },
                                                        'substation_device_ip_address': u'10.75.165.227',
                                                        'markerUrl': '/home/priyesh/Documents/Workspace/nocout_gis/
                                                           nocout/media/uploaded/icons/2014/09/25/P2P-loading4_3.png',
                                                        'perf_value': u'6.0082333333',
                                                        'lat': 26.9138611111111
                                                    }
        """
        # device name
        device_name = substation_device.device_name

        # machine name
        machine_name = substation_device.machine.name

        # freeze time (data fetched from freeze time to latest time)
        freeze_time = self.request.GET.get('freeze_time', '0')

        # type of thematic settings needs to be fetched
        ts_type = self.request.GET.get('ts', 'normal')

        # device technology
        device_technology = ""
        try:
            device_technology = DeviceTechnology.objects.get(id=substation_device.device_technology)
        except Exception as e:
            logger.exception("Device technology not exist. Exception: ", e.message)

        # thematic settings for current user
        user_thematics = self.get_thematic_settings(device_technology)

        # service & data source
        service = ""
        data_source = ""
        try:
            if ts_type == "normal":
                service = user_thematics.thematic_template.threshold_template.live_polling_template.service.name
                data_source = user_thematics.thematic_template.threshold_template.live_polling_template.data_source.name
            elif ts_type == "ping":
                service = user_thematics.thematic_template.service
                data_source = user_thematics.thematic_template.data_source
        except Exception as e:
            logger.exception("No user thematics for device {}. Exception: ".format(device_name, e.message))

        # device frequency
        device_frequency = self.get_device_polled_frequency(device_name, machine_name, freeze_time)

        # device pl
        device_pl = self.get_device_pl(device_name, machine_name, freeze_time)

        # device link/frequency color
        device_link_color = self.get_frequency_color_and_radius(device_frequency, device_pl)[0]

        if not device_link_color:
            device_link_color = ss_default_link_color

        # performance value
        perf_payload = {
            'device_name': device_name,
            'machine_name': machine_name,
            'freeze_time': freeze_time,
            'device_service_name': service,
            'device_service_data_source': data_source

        }
        performance_value = self.get_performance_value(perf_payload, ts_type)

        # sector info dict
        substation_info = dict()

        substation_info['antenna_height'] = substation.antenna.height
        substation_info['lat'] = substation.latitude
        substation_info['lon'] = substation.longitude
        substation_info['perf_value'] = performance_value
        substation_info['link_color'] = device_link_color
        substation_info['param'] = dict()
        substation_info['param']['sub_station'] = self.get_device_info(substation_device, machine_name, device_pl, substation)

        if user_thematics:
            # fetch icon settings for thematics as per thematic type selected i.e. 'ping' or 'normal'
            th_icon_settings = ""
            try:
                th_icon_settings = user_thematics.thematic_template.icon_settings
            except Exception as e:
                logger.exception("No icon settings for thematic settings. Exception: ", e.message)

            # fetch thematic ranges as per thematic type selected i.e. 'ping' or 'normal'
            th_ranges = ""
            try:
                if ts_type == "ping":
                    th_ranges = user_thematics.thematic_template
                elif ts_type == "normal":
                    th_ranges = user_thematics.thematic_template.threshold_template
                else:
                    pass
            except Exception as e:
                logger.exception("No ranges for thematic settings. Exception: ", e.message)

            # fetch service type if 'ts_type' is "normal"
            service_type = ""
            try:
                if ts_type == "normal":
                    service_type = user_thematics.thematic_template.threshold_template.service_type
            except Exception as e:
                logger.exception("Service Type not exist. Exception: ", e.message)

            # icon
            icon = ""

            # device type
            device_type = DeviceType.objects.get(pk=substation_device.device_type)

            try:
                icon = "media/" + str(device_type.device_icon)
            except Exception as e:
                logger.exception("No icon for device type ({}). Exception: {}".format(device_type.alias, e.message))

            # comparing threshold values to get icon
            try:
                if len(performance_value):
                    # live polled value of device service
                    value = ast.literal_eval(str(performance_value))

                    # get appropriate icon
                    if ts_type == "normal":
                        if service_type == "INT":
                            icon = self.get_icon_for_numeric_service(th_ranges, th_icon_settings, value)
                        elif service_type == "STR":
                            icon = self.get_icon_for_string_service(th_ranges, th_icon_settings, value)
                        else:
                            pass
                    elif ts_type == "ping":
                        icon = self.get_icon_for_numeric_service(th_ranges, th_icon_settings, value)
                    else:
                        pass
            except Exception as e:
                logger.exception("Icon not exist. Exception: ", e.message)

            substation_info['markerUrl'] = icon

        substation_info['substation_device_ip_address'] = substation_device.ip_address

        return substation_info

    def get_device_polled_frequency(self, device_name, machine_name, freeze_time):
        """ Get device polled frequency

            Parameters:
                - device_name (unicode) - device name
                - machine_name (unicode) - machine name
                - freeze_time (str) - freeze time i.e. '0'

            Returns:
               - device_frequency (str) - device frequency, e.g. "34525"
        """

        # device frequency
        device_frequency = ""
        try:
            if int(freeze_time):
                device_frequency = PerformanceInventory.objects.filter(device_name=device_name, data_source='frequency',
                                                                       sys_timestamp__lte=int(freeze_time) / 1000)\
                                                                       .using(alias=machine_name)\
                                                                       .order_by('-sys_timestamp')[:1]
                if len(device_frequency):
                    device_frequency = device_frequency[0].current_value
                else:
                    device_frequency = ""
            else:
                device_frequency = InventoryStatus.objects.filter(device_name=device_name, data_source='frequency')\
                                                                  .using(alias=machine_name)\
                                                                  .order_by('-sys_timestamp')[:1]
                if len(device_frequency):
                    device_frequency = device_frequency[0].current_value
                else:
                    device_frequency = ""
        except Exception as e:
            logger.exception("Device frequency not exist. Exception: ", e.message)

        return device_frequency

    def get_device_pl(self, device_name, machine_name, freeze_time):
        """ Get device pl

            Parameters:
                - device_name (unicode) - device name
                - machine_name (unicode) - machine name
                - freeze_time (str) - freeze time i.e. '0'

            Returns:
               - device_frequency (str) - device frequency, e.g. "34525"
        """

        # device packet loss
        device_pl = ""

        try:
            if int(freeze_time):
                device_pl = PerformanceNetwork.objects.filter(device_name=device_name, service_name='ping',
                                                              data_source='pl',
                                                              sys_timestamp__lte=int(freeze_time) / 1000)\
                                                              .using(alias=machine_name)\
                                                              .order_by('-sys_timestamp')[:1]
                if len(device_pl):
                    device_pl = device_pl[0].current_value
                else:
                    device_pl = ""
            else:
                device_pl = NetworkStatus.objects.filter(device_name=device_name,
                                                         service_name='ping',
                                                         data_source='pl')\
                                                         .using(alias=machine_name).order_by('-sys_timestamp')[:1]
                if len(device_pl):
                    device_pl = device_pl[0].current_value
                else:
                    device_pl = ""

        except Exception as e:
            logger.exception("Device PL not exist. Exception: ", e.message)

        return device_pl

    def get_frequency_color_and_radius(self, device_frequency, device_pl):
        """ Get device pl

            Parameters:
                - device_frequency (unicode) - device frequency, e.g 5830
                - device_pl (unicode) - device pl (packet loss) value, e.g. 4

            Returns:
                - device_link_color (unicode) - device link color, e.g. rgba(255,192,0,0.97)
                - radius (float) - radius, e.g 2.0
        """

        # device link color
        device_link_color = ""

        # radius
        radius = ""

        try:
            if len(device_frequency):
                corrected_dev_freq = device_frequency
                try:
                    chek_dev_freq = ast.literal_eval(device_frequency)
                    if int(chek_dev_freq) > 10:
                        corrected_dev_freq = chek_dev_freq
                except Exception as e:
                    logger.exception("Device frequency not exist. Exception: ", e.message)

                device_frequency_objects = DeviceFrequency.objects.filter(value__icontains=str(corrected_dev_freq))
                device_frequency_color = DeviceFrequency.objects.filter(value__icontains=str(corrected_dev_freq))\
                                                                        .values_list('color_hex_value', flat=True)
                device_frequency_object = None
                if len(device_frequency_objects):
                    device_frequency_object = device_frequency_objects[0]
                radius = device_frequency_object.frequency_radius if (
                    device_frequency_object
                    and
                    device_frequency_object.frequency_radius
                ) else 0
                if len(device_frequency_color):
                    device_link_color = device_frequency_color[0]
            if len(device_pl) and int(ast.literal_eval(device_pl)) == 100:
                device_link_color = 'rgb(0,0,0)'
        except Exception as e:
            if len(device_pl) and int(ast.literal_eval(device_pl)) == 100:
                device_link_color = 'rgb(0,0,0)'
            logger.exception("Frequency color not exist. Exception: ", e.message)

        return device_link_color, radius

    def get_thematic_settings(self, device_technology):
        """ Get device pl

            Parameters:
                - device_technology (<class 'device.models.DeviceTechnology'>) - device technology object
                - ts_type (unicode) - thematic settings type i.e 'ping' or 'normal'

            Returns:
               - user_thematics (<class 'inventory.models.UserPingThematicSettings'>) - thematic settings object
        """

        # thematic settings type i.e. 'ping' or 'normal'
        ts_type = self.request.GET.get('ts', 'normal')

        # current user
        try:
            current_user = UserProfile.objects.get(id=self.request.user.id)
        except Exception as e:
            current_user = ""
            logger.exception("User Profile not exist. Exception: ", e.message)

        # device technology
        device_technology = device_technology

        # fetch thematic settings for current user
        user_thematics = ""
        if ts_type == "normal":
            try:
                user_thematics = UserThematicSettings.objects.get(user_profile=current_user,
                                                                  thematic_technology=device_technology)
            except Exception as e:
                logger.exception("User thematic settings not exist. Exception: ", e.message)
        elif ts_type == "ping":
            try:
                user_thematics = UserPingThematicSettings.objects.get(user_profile=current_user,
                                                                      thematic_technology=device_technology)
            except Exception as e:
                logger.exception("User thematic settings not exist. Exception: ", e.message)

        return user_thematics

    def get_performance_value(self, perf_payload, ts_type):
        """ Get device pl

            Parameters:
                - perf_payload (dict) - performance payload dictionary
                                            {
                                                'device_service_name': u'radwin_uptime',
                                                'machine_name': u'default',
                                                'freeze_time': '0',
                                                'device_service_data_source': u'uptime',
                                                'device_name': u'1'
                                            }
                - ts_type (unicode) - thematic settings type i.e 'ping' or 'normal'

            Returns:
                - performance_value (unicode) - performance value, e.g. 6.0082333333
        """

        # device name
        device_name = perf_payload['device_name']

        # machine name
        machine_name = perf_payload['machine_name']

        # freeze time
        freeze_time = perf_payload['freeze_time']

        # service name
        device_service_name = perf_payload['device_service_name']

        # service data source
        device_service_data_source = perf_payload['device_service_data_source']

        # performance value
        performance_value = ""
        try:
            if ts_type == "normal":
                if int(freeze_time):
                    performance_value = PerformanceService.objects.filter(device_name=device_name,
                                                                          service_name=device_service_name,
                                                                          data_source=device_service_data_source,
                                                                          sys_timestamp__lte=int(freeze_time) / 1000)\
                                                                          .using(alias=machine_name)\
                                                                          .order_by('-sys_timestamp')[:1]
                    if len(performance_value):
                        performance_value = performance_value[0].current_value
                    else:
                        performance_value = ""
                else:
                    performance_value = ServiceStatus.objects.filter(device_name=device_name,
                                                                     service_name=device_service_name,
                                                                     data_source=device_service_data_source)\
                                                                     .using(alias=machine_name)\
                                                                     .order_by('-sys_timestamp')[:1]
                    if len(performance_value):
                        performance_value = performance_value[0].current_value
                    else:
                        performance_value = ""
            elif ts_type == "ping":
                if int(freeze_time):
                    performance_value = PerformanceNetwork.objects.filter(device_name=device_name,
                                                                          service_name=device_service_name,
                                                                  data_source=device_service_data_source,
                                                                  sys_timestamp__lte=int(freeze_time) / 1000)\
                                                                  .using(alias=machine_name)\
                                                                  .order_by('-sys_timestamp')[:1]
                    if len(performance_value):
                        performance_value = performance_value[0].current_value
                    else:
                        performance_value = ""
                else:
                    performance_value = NetworkStatus.objects.filter(device_name=device_name,
                                                         service_name=device_service_name,
                                                         data_source=device_service_data_source)\
                                                         .using(alias=machine_name).order_by('-sys_timestamp')[:1]
                    if len(performance_value):
                        performance_value = performance_value[0].current_value
                    else:
                        performance_value = ""
        except Exception as e:
            performance_value = ""
            logger.exception("Performance value not exist. Exception: ", e.message)

        return performance_value


def remove_duplicate_dict_from_list(input_list=None):
    """ Remove duplicate dictionaries from list of dictionaries

        :Parameters:
            - 'input_list' (list) - list of dictionaries for e.g.
                                        [
                                            {
                                                'City': u'Kolkata',
                                                'AntennaHeight': 27.0,
                                                'BHCircuitID': u'COPF-5712',
                                                'PEIP': u'192.168.216.37',
                                                'TypeOfBS(Technology)': u'WIMAX',
                                                'Polarization': u'Vertical',
                                                'State': u'WestBengal',
                                                'InfraProvider': u'WTTIL',
                                                'Latitude': 22.572833333333,
                                                'SiteType': u'RTT',
                                                'PMP': u'1',
                                                'BHConfiguredOnSwitch/Converter': u'10.175.132.67',
                                                'TypeOfGPS': u'AQtime',
                                                'IDUIP': u'10.172.72.2',
                                                'Address': u'35,
                                                CollegeSt.Kolkata,
                                                NearCalcuttaMedicalCollegeHospital',
                                                'BHOffnet/Onnet': u'ONNET',
                                                'MakeOfAntenna': u'Xhat',
                                                'SectorName': u'1',
                                                'BSName': u'BBGanguly',
                                                'Longitude': 88.362472222222,
                                                'TowerHeight': 13.0,
                                                'Azimuth': 30.0,
                                                'AntennaTilt': 2.0,
                                                'BHCapacity': 1000L,
                                                'AggregationSwitchPort': u'Ring',
                                                'Switch/ConverterPort': u'Gi0/1',
                                                'DRSite': u'No',
                                                'BackhaulType': u'DarkFibre',
                                                'BSOCircuitID': None,
                                                'SectorID': u'00: 0A: 10: 09: 00: 61',
                                                'InstallationOfSplitter': None,
                                                'PEHostname': u'kk-tcn-tcn-mi01-rt01',
                                                'BSSwitchIP': u'10.175.132.67',
                                                'BuildingHeight': 18.0,
                                                'AntennaBeamwidth': 60.0
                                            },
                                            {
                                                'City': u'Kolkata',
                                                'AntennaHeight': 27.0,
                                                'BHCircuitID': u'COPF-5712',
                                                'PEIP': u'192.168.216.37',
                                                'TypeOfBS(Technology)': u'WIMAX',
                                                'Polarization': u'Vertical',
                                                'State': u'WestBengal',
                                                'InfraProvider': u'WTTIL',
                                                'Latitude': 22.572833333333,
                                                'SiteType': u'RTT',
                                                'PMP': u'1',
                                                'BHConfiguredOnSwitch/Converter': u'10.175.132.67',
                                                'TypeOfGPS': u'AQtime',
                                                'IDUIP': u'10.172.72.2',
                                                'Address': u'35,
                                                CollegeSt.Kolkata,
                                                NearCalcuttaMedicalCollegeHospital',
                                                'BHOffnet/Onnet': u'ONNET',
                                                'MakeOfAntenna': u'Xhat',
                                                'SectorName': u'1',
                                                'BSName': u'BBGanguly',
                                                'Longitude': 88.362472222222,
                                                'TowerHeight': 13.0,
                                                'Azimuth': 30.0,
                                                'AntennaTilt': 2.0,
                                                'BHCapacity': 1000L,
                                                'AggregationSwitchPort': u'Ring',
                                                'Switch/ConverterPort': u'Gi0/1',
                                                'DRSite': u'No',
                                                'BackhaulType': u'DarkFibre',
                                                'BSOCircuitID': None,
                                                'SectorID': u'00: 0A: 10: 09: 00: 61',
                                                'InstallationOfSplitter': None,
                                                'PEHostname': u'kk-tcn-tcn-mi01-rt01',
                                                'BSSwitchIP': u'10.175.132.67',
                                                'BuildingHeight': 18.0,
                                                'AntennaBeamwidth': 60.0
                                            },
                                            {
                                                'City': u'Kolkata',
                                                'AntennaHeight': 27.0,
                                                'BHCircuitID': u'COPF-5712',
                                                'PEIP': u'192.168.216.37',
                                                'TypeOfBS(Technology)': u'WIMAX',
                                                'Polarization': u'Vertical',
                                                'State': u'WestBengal',
                                                'InfraProvider': u'WTTIL',
                                                'Latitude': 22.572833333333,
                                                'SiteType': u'RTT',
                                                'PMP': u'1',
                                                'BHConfiguredOnSwitch/Converter': u'10.175.132.67',
                                                'TypeOfGPS': u'AQtime',
                                                'IDUIP': u'10.172.72.2',
                                                'Address': u'35,
                                                CollegeSt.Kolkata,
                                                NearCalcuttaMedicalCollegeHospital',
                                                'BHOffnet/Onnet': u'ONNET',
                                                'MakeOfAntenna': u'Xhat',
                                                'SectorName': u'1',
                                                'BSName': u'BBGanguly',
                                                'Longitude': 88.362472222222,
                                                'TowerHeight': 13.0,
                                                'Azimuth': 30.0,
                                                'AntennaTilt': 2.0,
                                                'BHCapacity': 1000L,
                                                'AggregationSwitchPort': u'Ring',
                                                'Switch/ConverterPort': u'Gi0/1',
                                                'DRSite': u'No',
                                                'BackhaulType': u'DarkFibre',
                                                'BSOCircuitID': None,
                                                'SectorID': u'00: 0A: 10: 09: 00: 61',
                                                'InstallationOfSplitter': None,
                                                'PEHostname': u'kk-tcn-tcn-mi01-rt01',
                                                'BSSwitchIP': u'10.175.132.67',
                                                'BuildingHeight': 18.0,
                                                'AntennaBeamwidth': 60.0
                                            }
                                        ]

        :Returns:
           - 'result_list' (list) - list of dictionaries containing unique dictionaries for e.g.
                                        [
                                            {
                                                'City': u'Kolkata',
                                                'AntennaHeight': 27.0,
                                                'BHCircuitID': u'COPF-5712',
                                                'PEIP': u'192.168.216.37',
                                                'TypeOfBS(Technology)': u'WIMAX',
                                                'Polarization': u'Vertical',
                                                'State': u'WestBengal',
                                                'InfraProvider': u'WTTIL',
                                                'Latitude': 22.572833333333,
                                                'SiteType': u'RTT',
                                                'PMP': u'1',
                                                'BHConfiguredOnSwitch/Converter': u'10.175.132.67',
                                                'TypeOfGPS': u'AQtime',
                                                'IDUIP': u'10.172.72.2',
                                                'Address': u'35,
                                                CollegeSt.Kolkata,
                                                NearCalcuttaMedicalCollegeHospital',
                                                'BHOffnet/Onnet': u'ONNET',
                                                'MakeOfAntenna': u'Xhat',
                                                'SectorName': u'1',
                                                'BSName': u'BBGanguly',
                                                'Longitude': 88.362472222222,
                                                'TowerHeight': 13.0,
                                                'Azimuth': 30.0,
                                                'AntennaTilt': 2.0,
                                                'BHCapacity': 1000L,
                                                'AggregationSwitchPort': u'Ring',
                                                'Switch/ConverterPort': u'Gi0/1',
                                                'DRSite': u'No',
                                                'BackhaulType': u'DarkFibre',
                                                'BSOCircuitID': None,
                                                'SectorID': u'00: 0A: 10: 09: 00: 61',
                                                'InstallationOfSplitter': None,
                                                'PEHostname': u'kk-tcn-tcn-mi01-rt01',
                                                'BSSwitchIP': u'10.175.132.67',
                                                'BuildingHeight': 18.0,
                                                'AntennaBeamwidth': 60.0
                                            }
                                        ]
    """

    # list of dictionaries to be returned as a result
    result_list = []

    # temporary set containing dictionaries values in tuples for e.g
    # set([((key, value), (key, value), (key, value)), ((key, value), (key, value), (key, value))]

    temp_set = set()

    # loop through input list (list of dictionaries which needs to be filtered)
    for d in input_list:
        # t is set of dictionary values tuple for e.g
        # ((key, value), (key, value), (key, value), (key, value))
        # (('City', u'Kolkata'), ('Antenna Height', 29.0), ('BH Circuit ID', u'COPF-571'), ('PE IP', u'192.168.216.37'))
        t = tuple(d.items())
        if t not in temp_set:
            # adding tuple 't' to 'temp_set'
            temp_set.add(t)
            # append dictionary 'd' to 'result_list'
            result_list.append(d)

    return result_list


## This function returns the latest l2 report url for given circuit id.
def getL2Report(request, ckt_id = 'no'):

    result = {
        "message" : "No L2 Report",
        "success" : 0,
        "data" : []
    }

    try:
        circuit_instance = Circuit.objects.filter(alias=ckt_id)
        report_list = CircuitL2Report.objects.filter(circuit_id=circuit_instance).values()[:1]
        if len(report_list) > 0:
            file_url = report_list[0]['file_name']
            file_url_dict = {
                "url" : "media/"+file_url
            }
            result['data'].append(file_url_dict)
            result['success'] = 1
            result['message'] = "L2 report fetched successfully"
    except Exception, e:
        logger.exception(e.message)
    return HttpResponse(json.dumps(result))
