# -*- coding: utf-8 -*-

import json
from operator import itemgetter
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.query import ValuesQuerySet
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.core.urlresolvers import reverse_lazy
from django_datatables_view.base_datatable_view import BaseDatatableView
from device.models import Device, DeviceType, DeviceTypeFields, DeviceTypeFieldsValue, DeviceTechnology, \
    TechnologyVendor, DeviceVendor, VendorModel, DeviceModel, ModelType, DevicePort, Country, State, City, \
    DeviceFrequency
from forms import DeviceForm, DeviceTypeFieldsForm, DeviceTypeFieldsUpdateForm, DeviceTechnologyForm, \
    DeviceVendorForm, DeviceModelForm, DeviceTypeForm, DevicePortForm, DeviceFrequencyForm
from nocout.utils.util import DictDiffer
from django.http.response import HttpResponseRedirect
from organization.models import Organization
from service.models import Service
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings                                      # Importing settings for logger
from site_instance.models import SiteInstance
from inventory.models import Backhaul, SubStation, Sector
from django.contrib.staticfiles.templatetags.staticfiles import static
from nocout.utils import logged_in_user_organizations
from nocout.mixins.user_action import UserLogDeleteMixin
from nocout.mixins.permissions import PermissionsRequiredMixin
from nocout.mixins.generics import FormRequestMixin


from django.views.decorators.csrf import csrf_exempt

import logging

logger = logging.getLogger(__name__)

# ***************************************** Device Views ********************************************


class DeviceList(PermissionsRequiredMixin, ListView):
    """
    Render list of devices
    """
    model = Device
    template_name = 'device/devices_list.html'
    required_permissions = ('device.view_device',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'status_icon', 'sTitle': '', 'sWidth': 'auto', },
            {'mData': 'organization__name', 'sTitle': 'Organization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device_name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'site_instance__name', 'sTitle': 'Site Instance', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'machine__name', 'sTitle': 'Machine', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device_technology__name', 'sTitle': 'Device Technology', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'device_type__name', 'sTitle': 'Device Type', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'host_state', 'sTitle': 'Host State', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'ip_address', 'sTitle': 'IP Address', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'mac_address', 'sTitle': 'MAC Address', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'state__name', 'sTitle': 'State', 'sWidth': 'auto', 'sClass': 'hidden-xs', 'bSortable': False}, ]

        #if the user role is Admin or superadmin then the action column will appear on the datatable
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True) or self.request.user.is_superuser:
            datatable_headers.append(
                {'mData': 'actions', 'sTitle': 'Device Actions', 'sWidth': '9%', 'bSortable': False})
            datatable_headers.append(
                {'mData': 'nms_actions', 'sTitle': 'NMS Actions', 'sWidth': '8%', 'bSortable': False})

        datatable_headers_no_nms_actions = [
            {'mData': 'status_icon', 'sTitle': '', 'sWidth': 'auto', },
            {'mData': 'organization__name', 'sTitle': 'Organization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device_name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'site_instance__name', 'sTitle': 'Site Instance', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'machine__name', 'sTitle': 'Machine', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device_technology__name', 'sTitle': 'Device Technology', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'device_type__name', 'sTitle': 'Device Type', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'host_state', 'sTitle': 'Host State', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'ip_address', 'sTitle': 'IP Address', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'mac_address', 'sTitle': 'MAC Address', 'sWidth': 'auto', 'sClass': 'hidden-xs',
             'bSortable': False},
            {'mData': 'state__name', 'sTitle': 'State', 'sWidth': 'auto', 'sClass': 'hidden-xs', 'bSortable': False}, ]

        #if the user role is Admin then the action column will appear on the datatable
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True) or self.request.user.is_superuser:
            datatable_headers_no_nms_actions.append(
                {'mData': 'actions', 'sTitle': 'Device Actions', 'sWidth': '15%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        context['datatable_headers_no_nms_actions'] = json.dumps(datatable_headers_no_nms_actions)
        return context


def create_device_tree(request):
    """
    Render tree structure for devices
    """
    templateData = {
        'username': request.user.username
    }

    return render_to_response('device/devices_tree_view.html', templateData, context_instance=RequestContext(request))


class OperationalDeviceListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing operational devices only
    """
    model = Device
    required_permissions = ('device.view_device',)
    columns = ['device_name', 'site_instance__name', 'machine__name', 'organization__name', 'device_technology',
               'device_type', 'host_state', 'ip_address', 'mac_address', 'state']
    order_columns = ['organization__name', 'device_alias', 'site_instance__name', 'machine__name']

    def pop_filter_keys(self, dct):
        """
        Filtering device fields
        """
        keys_list = ['device_type__name', 'device_technology__name', 'state__name']
        for k in keys_list:
            dct.pop(k)

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()

            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                try:
                    dictionary['device_type__name'] = DeviceType.objects.get(pk=int(dictionary['device_type'])).name \
                        if dictionary['device_type'] else ''
                except Exception as device_type_exp:
                    dictionary['device_type__name'] = ""

                try:
                    dictionary['device_technology__name'] = DeviceTechnology.objects.get(
                        pk=int(dictionary['device_technology'])).name \
                        if dictionary['device_technology'] else ''
                except Exception as device_tech_exp:
                    dictionary['device_technology__name'] = ""

                try:
                    dictionary['state__name'] = State.objects.get(pk=int(dictionary['state'])).state_name if dictionary[
                        'state'] else ''
                except Exception as device_state_exp:
                    dictionary['state__name'] = ""

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
                map(lambda x: dictionary.pop(x) if x in dictionary else None,
                    ['device_type__name', 'device_technology__name', 'state__name'])

            return result_list

        return qs

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col - 1]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:

            if settings.DEBUG:
                logger.error("Need to provide a model or implement get_initial_queryset!",
                             extra={'stack': True, 'request': self.request})

            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        return Device.objects.filter(organization__in=logged_in_user_organizations(self),
                                     is_deleted=0,
                                     is_added_to_nms__in=[1, 2]).values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device_name' in dct:
                    device_alias = Device.objects.get(pk=dct['id']).device_alias
                    device_ip = Device.objects.get(pk=dct['id']).ip_address
                    dct['device_name'] = "{} ({})".format(device_alias, device_ip)
            except Exception as e:
                logger.exception("Device not present. Exception: ", e.message)

            # current device in loop

            current_device = Device.objects.get(pk=dct['id'])

            try:
                dct['device_type__name'] = DeviceType.objects.get(pk=int(dct['device_type'])).name if dct[
                    'device_type'] else ''
            except Exception as device_type_exp:
                dct['device_type__name'] = ""

            try:
                dct['device_technology__name'] = DeviceTechnology.objects.get(pk=int(dct['device_technology'])).name \
                    if dct['device_technology'] else ''
            except Exception as device_tech_exp:
                dct['device_technology__name'] = ""

            try:
                dct['state__name'] = State.objects.get(pk=int(dct['state'])).state_name if dct['state'] else ''
            except Exception as device_state_exp:
                dct['state__name'] = ""

            # img_url = static('img/nms_icons/circle_green.png')
            # dct.update(status_icon='<img src="{0}">'.format(img_url))
            if current_device.is_monitored_on_nms == 1:
                status_icon_color = "green-dot"
                dct.update(status_icon='<i class="fa fa-circle {0}"></i>'.format(status_icon_color))
            else:
                status_icon_color = "light-green-dot"
                dct.update(status_icon='<i class="fa fa-circle {0}"></i>'.format(status_icon_color))

            # There are two set of links in device list table
            # 1. Device Actions --> device detail, edit, delete from inventory. They are always present in device table if user role is 'Admin'
            # 2. NMS Actions --> device add, sync, service add etc. form nocout nms core. They are only present
            # in device table if device id one of the following:
            # a. backhaul configured on (from model Backhaul)
            # b. sector configures on (from model Sector)
            # c. sub-station configured on (from model SubStation)
            detail_action = '<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>&nbsp&nbsp'.format(dct['id'])
            if self.request.user.has_perm('device.change_device'):
                edit_action = '<a href="/device/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>&nbsp&nbsp'.format(dct['id'])
            else:
                edit_action = ''
            if self.request.user.has_perm('device.delete_device'):
                delete_action = '<a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>'.format(dct['id'])
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action)

            dct.update(nms_actions='')

            # device is monitored only if it's a backhaul configured on, sector configured on or sub-station
            # checking whether device is 'backhaul configured on' or not
            try:
                if len(Backhaul.objects.filter(bh_configured_on=current_device)):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-info" title="Services Status"></i></a>\
                                            <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-info" title="Delete Device"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-info" title="Add Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-info" title="Edit Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-info" title="Delete Services"></i></a>\
                                            <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-info" title="Sync Device"></i></a>'.format(
                        dct['id']))
                    try:
                        if current_device.is_added_to_nms == 2:
                            dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-info" title="Services Status"></i></a>\
                                                    <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-info" title="Delete Device"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-info" title="Add Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-info" title="Edit Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-info" title="Delete Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_device_in_nms_core(device_edit_message, {{\'device_id\': {0}}})"><i class="fa fa-share-square text-dark" title="Edit Device"></i></a>\
                                                    <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-info" title="Sync Device"></i></a>'.format(dct['id']))
                    except Exception as e:
                        logger.exception(e.message)
            except Exception as e:
                logger.exception("Device is not a backhaul %s" %e.message)

            # checking whether device is 'sector configured on' or not
            try:
                if len(Sector.objects.filter(sector_configured_on=current_device)):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-success" title="Services Status"></i></a>\
                                            <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-success" title="Delete Device"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-success" title="Edit Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-success" title="Delete Services"></i></a>\
                                            <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-success" title="Sync Device"></i></a>'.format(
                        dct['id']))
                    try:
                        if current_device.is_added_to_nms == 2:
                            dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-success" title="Services Status"></i></a>\
                                                    <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-success" title="Delete Device"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-success" title="Edit Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-success" title="Delete Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_device_in_nms_core(device_edit_message, {{\'device_id\': {0}}})"><i class="fa fa-share-square text-success" title="Edit Device"></i></a>\
                                                    <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-success" title="Sync Device"></i></a>'.format(dct['id']))
                    except Exception as e:
                        logger.exception(e.message)
            except Exception as e:
                logger.exception("Device is not sector configured on. %s" % e.message)

            # checking whether device is 'sub station' or not
            try:
                if SubStation.objects.get(device=current_device):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-danger" title="Services Status"></i></a>\
                                            <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-danger" title="Delete Device"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-danger" title="Add Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-danger" title="Edit Services"></i></a>\
                                            <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-danger" title="Delete Services"></i></a>\
                                            <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-danger" title="Sync Device"></i></a>'.format(
                        dct['id']))
                    try:
                        if current_device.is_added_to_nms == 2:
                            dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.device_services_status(device_services_status_frame, {{\'device_id\': {0}}})"><i class="fa fa-list-alt text-danger" title="Services Status"></i></a>\
                                                    <a href="javascript:;" onclick="delete_device({0});"><i class="fa fa-minus-square text-danger" title="Delete Device"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-danger" title="Add Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_service_form(get_service_edit_form, {{\'value\': {0}}})"><i class="fa fa-pencil text-danger" title="Edit Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.delete_service_form(get_service_delete_form, {{\'value\': {0}}})"><i class="fa fa-minus text-danger" title="Delete Services"></i></a>\
                                                    <a href="javascript:;" onclick="Dajaxice.device.edit_device_in_nms_core(device_edit_message, {{\'device_id\': {0}}})"><i class="fa fa-share-square text-dark" title="Edit Device"></i></a>\
                                                    <a href="javascript:;" onclick="sync_devices();"><i class="fa fa-refresh text-danger" title="Sync Device"></i></a>'.format(dct['id']))
                    except Exception as e:
                        logger.exception(e.message)
            except Exception as e:
                logger.exception("Device is not a substation. %s" % e.message)
        return json_data

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData,
        }
        return ret


class NonOperationalDeviceListingTable(BaseDatatableView):
    """
    Render JQuery datatables for listing non-operational devices only
    """
    model = Device
    columns = ['device_name', 'site_instance__name', 'machine__name', 'organization__name', 'device_technology',
               'device_type', 'host_state', 'ip_address', 'mac_address', 'state']
    order_columns = ['organization__name', 'device_alias', 'site_instance__name', 'machine__name']

    def pop_filter_keys(self, dct):
        """
        Filtering device fields
        """
        keys_list = ['device_type__name', 'device_technology__name', 'state__name']
        for k in keys_list:
            dct.pop(k)

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()

            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                try:
                    dictionary['device_type__name'] = DeviceType.objects.get(pk=int(dictionary['device_type'])).name \
                        if dictionary['device_type'] else ''
                except Exception as device_type_exp:
                    dictionary['device_type__name'] = ""

                try:
                    dictionary['device_technology__name'] = DeviceTechnology.objects.get(
                        pk=int(dictionary['device_technology'])).name \
                        if dictionary['device_technology'] else ''
                except Exception as device_tech_exp:
                    dictionary['device_technology__name'] = ""

                try:
                    dictionary['state__name'] = State.objects.get(pk=int(dictionary['state'])).state_name if dictionary[
                        'state'] else ''
                except Exception as device_state_exp:
                    dictionary['state__name'] = ""

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)

                map(lambda x: dictionary.pop(x) if x in dictionary else None,
                    ['device_type__name', 'device_technology__name', 'state__name'])

            return result_list

        return qs

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col - 1]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:

            if settings.DEBUG:
                logger.error("Need to provide a model or implement get_initial_queryset!",
                             extra={'stack': True, 'request': self.request})

            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        return Device.objects.filter(organization__in=logged_in_user_organizations(self),
                                     is_deleted=0,
                                     is_monitored_on_nms=0,
                                     is_added_to_nms=0,
                                     host_state="Enable").values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device_name' in dct:
                    device_alias = Device.objects.get(pk=dct['id']).device_alias
                    device_ip = Device.objects.get(pk=dct['id']).ip_address
                    dct['device_name'] = "{} ({})".format(device_alias, device_ip)
            except Exception as e:
                logger.exception("Device not present. Exception: ", e.message)

            # current device in loop
            current_device = Device.objects.get(pk=dct['id'])

            try:
                dct['device_type__name'] = DeviceType.objects.get(pk=int(dct['device_type'])).name if dct[
                    'device_type'] else ''
            except Exception as device_type_exp:
                dct['device_type__name'] = ""

            try:
                dct['device_technology__name'] = DeviceTechnology.objects.get(pk=int(dct['device_technology'])).name \
                    if dct['device_technology'] else ''
            except Exception as device_tech_exp:
                dct['device_technology__name'] = ""

            try:
                dct['state__name'] = State.objects.get(pk=int(dct['state'])).state_name if dct['state'] else ''
            except Exception as device_state_exp:
                dct['state__name'] = ""

            # img_url = static('img/nms_icons/circle_orange.png')
            # dct.update(status_icon='<img src="{0}">'.format(img_url))

            dct.update(status_icon='<i class="fa fa-circle orange-dot"></i>')

            # There are two set of links in device list table
            # 1. Device Actions --> device detail, edit, delete from inventory. They are always present in device table if user role is 'Admin'
            # 2. NMS Actions --> device add, sync, service add etc. form nocout nms core. They are only present
            # in device table if device id one of the following:
            # a. backhaul configured on (from model Backhaul)
            # b. sector configures on (from model Sector)
            # c. sub-station configured on (from model SubStation)
            # dct.update(actions='<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>\
            #    <a href="/device/edit/{0}"><i class="fa fa-pencil text-dark" title="Edit"></i></a>\
            #    <a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title=" Soft Delete"></i></a>'.format(
            #     dct['id']))
            detail_action = '<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>&nbsp&nbsp'.format(dct['id'])
            if self.request.user.has_perm('device.change_device'):
                edit_action = '<a href="/device/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>&nbsp&nbsp'.format(dct['id'])
            else:
                edit_action = ''
            if self.request.user.has_perm('device.delete_device'):
                delete_action = '<a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>'.format(dct['id'])
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action)

            dct.update(nms_actions='')
            # device is monitored only if it's a backhaul configured on, sector configured on or sub-station
            # checking whether device is 'backhaul configured on' or not
            try:
                if Backhaul.objects.get(bh_configured_on=current_device):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.add_device_to_nms_core_form(add_device_form, {{\'device_id\': {0}}})"><i class="fa fa-plus-square text-info" title="Add Device"></i></a>'.format(
                        dct['id']))
            except Exception as e:
                logger.exception("Device is not a backhaul. %s " % e.message)

            # checking whether device is 'sector configured on' or not
            try:
                if len(Sector.objects.filter(sector_configured_on=current_device)):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.add_device_to_nms_core_form(add_device_form, {{\'device_id\': {0}}})"><i class="fa fa-plus-square text-success" title="Add Device"></i></a>'.format(
                        dct['id']))
            except Exception as e:
                logger.exception("Device is not sector configured on. %s " % e.message)

            # checking whether device is 'sub station' or not
            try:
                if SubStation.objects.get(device=current_device):
                    dct.update(nms_actions='<a href="javascript:;" onclick="Dajaxice.device.add_device_to_nms_core_form(add_device_form, {{\'device_id\': {0}}})"><i class="fa fa-plus-square text-danger"></i></a>'.format(
                        dct['id']))
            except Exception as e:
                logger.exception("Device is not a substation. %s" % e.message)
        return json_data

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data

        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData,
        }
        return ret


class DisabledDeviceListingTable(BaseDatatableView):
    """
    Render JQuery datatables for listing disabled devices only
    """
    model = Device
    columns = ['device_name', 'site_instance__name', 'machine__name', 'organization__name', 'device_technology',
               'device_type', 'host_state', 'ip_address', 'mac_address', 'state']
    order_columns = ['organization__name', 'device_alias', 'site_instance__name', 'machine__name']

    def pop_filter_keys(self, dct):
        """
        Filtering device fields
        """
        keys_list = ['device_type__name', 'device_technology__name', 'state__name']
        for k in keys_list:
            dct.pop(k)

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()

            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                try:
                    dictionary['device_type__name'] = DeviceType.objects.get(pk=int(dictionary['device_type'])).name \
                        if dictionary['device_type'] else ''
                except Exception as device_type_exp:
                    dictionary['device_type__name'] = ""

                try:
                    dictionary['device_technology__name'] = DeviceTechnology.objects.get(
                        pk=int(dictionary['device_technology'])).name \
                        if dictionary['device_technology'] else ''
                except Exception as device_tech_exp:
                    dictionary['device_technology__name'] = ""

                try:
                    dictionary['state__name'] = State.objects.get(pk=int(dictionary['state'])).state_name if dictionary[
                        'state'] else ''
                except Exception as device_state_exp:
                    dictionary['state__name'] = ""

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
                map(lambda x: dictionary.pop(x) if x in dictionary else None,
                    ['device_type__name', 'device_technology__name', 'state__name'])

            return result_list

        return qs

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col - 1]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs


    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:

            if settings.DEBUG:
                logger.error("Need to provide a model or implement get_initial_queryset!",
                             extra={'stack': True, 'request': self.request})

            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        return Device.objects.filter(organization__in=logged_in_user_organizations(self), is_deleted=0, host_state="Disable") \
            .values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device_name' in dct:
                    device_alias = Device.objects.get(pk=dct['id']).device_alias
                    device_ip = Device.objects.get(pk=dct['id']).ip_address
                    dct['device_name'] = "{} ({})".format(device_alias, device_ip)
            except Exception as e:
                logger.exception("Device not present. Exception: ", e.message)

            # current device in loop
            current_device = Device.objects.get(pk=dct['id'])

            try:
                dct['device_type__name'] = DeviceType.objects.get(pk=int(dct['device_type'])).name if dct[
                    'device_type'] else ''
            except Exception as device_type_exp:
                dct['device_type__name'] = ""

            try:
                dct['device_technology__name'] = DeviceTechnology.objects.get(pk=int(dct['device_technology'])).name \
                    if dct['device_technology'] else ''
            except Exception as device_tech_exp:
                dct['device_technology__name'] = ""

            try:
                dct['state__name'] = State.objects.get(pk=int(dct['state'])).state_name if dct['state'] else ''
            except Exception as device_state_exp:
                dct['state__name'] = ""

            # img_url = static('img/nms_icons/circle_grey.png')
            # dct.update(status_icon='<img src="{0}">'.format(img_url))

            dct.update(status_icon='<i class="fa fa-circle grey-dot"></i>')

            # There are two set of links in device list table
            # 1. Device Actions --> device detail, edit, delete from inventory. They are always present in device table if user role is 'Admin'
            # 2. NMS Actions --> device add, sync, service add etc. form nocout nms core. They are only present
            # in device table if device id one of the following:
            # a. backhaul configured on (from model Backhaul)
            # b. sector configures on (from model Sector)
            # c. sub-station configured on (from model SubStation)
            # dct.update(actions='<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>\
            #    <a href="/device/edit/{0}"><i class="fa fa-pencil text-dark" title="Edit"></i></a>\
            #    <a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>'.format(
            #     dct['id']))
            detail_action = '<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>&nbsp&nbsp'.format(dct['id'])
            if self.request.user.has_perm('device.change_device'):
                edit_action = '<a href="/device/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>&nbsp&nbsp'.format(dct['id'])
            else:
                edit_action = ''
            if self.request.user.has_perm('device.delete_device'):
                delete_action = '<a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>'.format(dct['id'])
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action)
            dct.update(nms_actions='')
            # # device is monitored only if it's a backhaul configured on, sector configured on or sub-station
            # # checking whether device is 'backhaul configured on' or not
            # try:
            #     if Backhaul.objects.get(bh_configured_on=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not basestation")
            #
            # # checking whether device is 'sector configured on' or not
            # try:
            #     if Sector.objects.get(sector_configured_on=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not basestation")
            #
            # # checking whether device is 'sub station' or not
            # try:
            #     if SubStation.objects.get(device=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not substation.")
        return json_data

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData,
        }
        return ret


class ArchivedDeviceListingTable(BaseDatatableView):
    """
    Render JQuery datatables for listing archived devices only
    """
    model = Device
    columns = ['device_name', 'site_instance__name', 'machine__name', 'organization__name', 'device_technology',
               'device_type', 'host_state', 'ip_address', 'mac_address', 'state']
    order_columns = ['organization__name', 'device_alias', 'site_instance__name', 'machine__name']

    def pop_filter_keys(self, dct):
        """
        Filtering device fields
        """
        keys_list = ['device_type__name', 'device_technology__name', 'state__name']
        for k in keys_list:
            dct.pop(k)


    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()

            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                try:
                    dictionary['device_type__name'] = DeviceType.objects.get(pk=int(dictionary['device_type'])).name \
                        if dictionary['device_type'] else ''
                except Exception as device_type_exp:
                    dictionary['device_type__name'] = ""

                try:
                    dictionary['device_technology__name'] = DeviceTechnology.objects.get(
                        pk=int(dictionary['device_technology'])).name \
                        if dictionary['device_technology'] else ''
                except Exception as device_tech_exp:
                    dictionary['device_technology__name'] = ""

                try:
                    dictionary['state__name'] = State.objects.get(pk=int(dictionary['state'])).state_name if dictionary[
                        'state'] else ''
                except Exception as device_state_exp:
                    dictionary['state__name'] = ""

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
                map(lambda x: dictionary.pop(x) if x in dictionary else None,
                    ['device_type__name', 'device_technology__name', 'state__name'])

            return result_list

        return qs

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col - 1]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs



    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:

            if settings.DEBUG:
                logger.error("Need to provide a model or implement get_initial_queryset!",
                             extra={'stack': True, 'request': self.request})

            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        return Device.objects.filter(organization__in=logged_in_user_organizations(self), is_deleted=1) \
            .values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device_name' in dct:
                    device_alias = Device.objects.get(pk=dct['id']).device_alias
                    device_ip = Device.objects.get(pk=dct['id']).ip_address
                    dct['device_name'] = "{} ({})".format(device_alias, device_ip)
            except Exception as e:
                logger.exception("Device not present. Exception: ", e.message)

            # current device in loop
            current_device = Device.objects.get(pk=dct['id'])

            try:
                dct['device_type__name'] = DeviceType.objects.get(pk=int(dct['device_type'])).name if dct[
                    'device_type'] else ''
            except Exception as device_type_exp:
                dct['device_type__name'] = ""

            try:
                dct['device_technology__name'] = DeviceTechnology.objects.get(pk=int(dct['device_technology'])).name \
                    if dct['device_technology'] else ''
            except Exception as device_tech_exp:
                dct['device_technology__name'] = ""

            try:
                dct['state__name'] = State.objects.get(pk=int(dct['state'])).state_name if dct['state'] else ''
            except Exception as device_state_exp:
                dct['state__name'] = ""

            # img_url = static('img/nms_icons/circle_red.png')
            # dct.update(status_icon='<img src="{0}">'.format(img_url))

            dct.update(status_icon='<i class="fa fa-circle red-dot"></i>')

            # There are two set of links in device list table
            # 1. Device Actions --> device detail, edit, delete from inventory. They are always present in device table if user role is 'Admin'
            # 2. NMS Actions --> device add, sync, service add etc. form nocout nms core. They are only present
            # in device table if device id one of the following:
            # a. backhaul configured on (from model Backhaul)
            # b. sector configures on (from model Sector)
            # c. sub-station configured on (from model SubStation)
            # dct.update(actions='<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>\
            #    <a href="/device/edit/{0}"><i class="fa fa-pencil text-dark" title="Edit"></i></a>\
            #    <a href="/device/delete/{0}"><i class="fa fa-minus text-danger" title="Hard Delete"></i></a>\
            #    <a href="javascript:;" onclick="Dajaxice.device.device_restore_form(get_restore_device_form, {{\'value\': {0}}})"><i class="fa fa-plus green-dot" title="Restore"></i></a>'.format(dct['id']))
            if self.request.user.is_superuser:
                add_action = '<a href="javascript:;" onclick="Dajaxice.device.device_restore_form(get_restore_device_form, {{\'value\': {0}}})"><i class="fa fa-plus green-dot" title="Restore"></i></a>'.format(dct['id'])
            else:
                add_action = ''
            detail_action = '<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>&nbsp&nbsp'.format(dct['id'])
            if self.request.user.has_perm('device.change_device'):
                edit_action = '<a href="/device/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(dct['id'])
            else:
                edit_action = ''
            if self.request.user.has_perm('device.delete_device'):
                delete_action = '<a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>&nbsp'.format(dct['id'])
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action+add_action)
            # dct.update(nms_actions='')
            # # device is monitored only if it's a backhaul configured on, sector configured on or sub-station
            # # checking whether device is 'backhaul configured on' or not
            # try:
            #     if Backhaul.objects.get(bh_configured_on=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not basestation")
            #
            # # checking whether device is 'sector configured on' or not
            # try:
            #     if Sector.objects.get(sector_configured_on=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not basestation")
            #
            # # checking whether device is 'sub station' or not
            # try:
            #     if SubStation.objects.get(device=current_device):
            #         dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
            #             <a href="javascript:;" onclick="sync_devices({0});"><i class="fa fa-share-square-o text-success" title="Sync device for monitoring"></i></a>\
            #             <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(dct['id']))
            # except:
            #     logger.info("Device is not substation.")
        return json_data

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData,
        }
        return ret


class AllDeviceListingTable(BaseDatatableView):
    """
    Render JQuery datatables for listing of all devices
    """
    model = Device
    columns = ['device_name', 'site_instance__name', 'machine__name', 'organization__name', 'device_technology',
               'device_type', 'host_state', 'ip_address', 'mac_address', 'state']
    order_columns = ['organization__name', 'device_alias', 'site_instance__name', 'machine__name']

    def pop_filter_keys(self, dct):
        """
        Filtering device fields
        """
        keys_list = ['device_type__name', 'device_technology__name', 'state__name']
        for k in keys_list:
            dct.pop(k)


    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()

            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                try:
                    dictionary['device_type__name'] = DeviceType.objects.get(pk=int(dictionary['device_type'])).name \
                        if dictionary['device_type'] else ''
                except Exception as device_type_exp:
                    dictionary['device_type__name'] = ""

                try:
                    dictionary['device_technology__name'] = DeviceTechnology.objects.get(
                        pk=int(dictionary['device_technology'])).name \
                        if dictionary['device_technology'] else ''
                except Exception as device_tech_exp:
                    dictionary['device_technology__name'] = ""

                try:
                    dictionary['state__name'] = State.objects.get(pk=int(dictionary['state'])).state_name if dictionary[
                        'state'] else ''
                except Exception as device_state_exp:
                    dictionary['state__name'] = ""

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
                map(lambda x: dictionary.pop(x) if x in dictionary else None,
                    ['device_type__name', 'device_technology__name', 'state__name'])

            return result_list

        return qs

    def ordering(self, qs):
        """
        Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col - 1]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:

            if settings.DEBUG:
                logger.error("Need to provide a model or implement get_initial_queryset!",
                             extra={'stack': True, 'request': self.request})

            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        return Device.objects.filter(organization__in=logged_in_user_organizations(self), is_deleted=0) \
            .values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device_name' in dct:
                    device_alias = Device.objects.get(pk=dct['id']).device_alias
                    device_ip = Device.objects.get(pk=dct['id']).ip_address
                    dct['device_name'] = "{} ({})".format(device_alias, device_ip)
            except Exception as e:
                logger.exception("Device not present. Exception: ", e.message)

            # current device in loop
            current_device = Device.objects.get(pk=dct['id'])

            try:
                dct['device_type__name'] = DeviceType.objects.get(pk=int(dct['device_type'])).name if dct[
                    'device_type'] else ''
            except Exception as device_type_exp:
                dct['device_type__name'] = ""

            try:
                dct['device_technology__name'] = DeviceTechnology.objects.get(pk=int(dct['device_technology'])).name \
                    if dct['device_technology'] else ''
            except Exception as device_tech_exp:
                dct['device_technology__name'] = ""

            try:
                dct['state__name'] = State.objects.get(pk=int(dct['state'])).state_name if dct['state'] else ''
            except Exception as device_state_exp:
                dct['state__name'] = ""

            # if device is already added to nms core than show icon in device table
            icon = ""
            try:
                if current_device.is_added_to_nms == 0 and current_device.host_state == "Enable":
                    icon = '<i class="fa fa-circle orange-dot"></i>'
                elif current_device.is_added_to_nms == 0 and current_device.host_state == "Disable":
                    icon = '<i class="fa fa-circle grey-dot"></i>'
                elif current_device.is_added_to_nms == 1:
                    icon = '<i class="fa fa-circle green-dot"></i>'
                elif current_device.is_added_to_nms == 2:
                    icon = '<i class="fa fa-circle green-dot"></i>'
                dct.update(status_icon=icon)
            except Exception as e:
                logger.exception(e.message)
                dct.update(status_icon='<img src="">')

            # There are two set of links in device list table
            # 1. Device Actions --> device detail, edit, delete from inventory.
            # They are always present in device table if user role is 'Admin'
            # 2. NMS Actions --> device add, sync, service add etc. form nocout nms core. They are only present
            # in device table if device id one of the following:
            # a. backhaul configured on (from model Backhaul)
            # b. sector configures on (from model Sector)
            # c. sub-station configured on (from model SubStation)
            # dct.update(actions='<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>\
            #    <a href="/device/edit/{0}"><i class="fa fa-pencil text-dark" title="Edit"></i></a>\
            #    <a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})">\
            #    <i class="fa fa-trash-o text-danger" title="Delete"></i></a>'.format(
            #     dct['id']))
            detail_action = '<a href="/device/{0}"><i class="fa fa-list-alt text-info" title="Detail"></i></a>&nbsp&nbsp'.format(dct['id'])
            if self.request.user.has_perm('device.change_device'):
                edit_action = '<a href="/device/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>&nbsp&nbsp'.format(dct['id'])
            else:
                edit_action = ''
            if self.request.user.has_perm('device.delete_device'):
                delete_action = '<a href="javascript:;" onclick="Dajaxice.device.device_soft_delete_form(get_soft_delete_form, {{\'value\': {0}}})"><i class="fa fa-trash-o text-danger" title="Soft Delete"></i></a>'.format(dct['id'])
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action)
            dct.update(nms_actions='')
            # device is monitored only if it's a backhaul configured on, sector configured on or sub-station
            # checking whether device is 'backhaul configured on' or not
            try:
                if Backhaul.objects.get(bh_configured_on=current_device):
                    dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
                        <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(
                        dct['id']))
            except:
                logger.exception("Device is not basestation")

            # checking whether device is 'sector configured on' or not
            try:
                if len(Sector.objects.filter(sector_configured_on=current_device)):
                    dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
                        <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(
                        dct['id']))
            except:
                logger.exception("Device is not basestation")

            # checking whether device is 'sub station' or not
            try:
                if SubStation.objects.get(device=current_device):
                    dct.update(nms_actions='<a href="javascript:;" onclick="add_device({0});"><i class="fa fa-plus-square text-warning"></i></a>\
                        <a href="javascript:;" onclick="Dajaxice.device.add_service_form(get_service_add_form, {{\'value\': {0}}})"><i class="fa fa-plus text-success" title="Add Service"></i></a>'.format(
                        dct['id']))
            except:
                logger.exception("Device is not substation.")
        return json_data

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData,
        }
        return ret


class DeviceDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for device
    """
    model = Device
    required_permissions = ('device.view_device',)
    template_name = 'device/device_detail.html'

    def get_context_data(self, **kwargs):

        context = super(DeviceDetail, self).get_context_data(**kwargs)

        try:
            if kwargs['object'].device_technology:
                context['device_technology'] = DeviceTechnology.objects.get(pk=kwargs['object'].device_technology).alias
            if kwargs['object'].device_vendor:
                context['device_vendor'] = DeviceVendor.objects.get(pk=kwargs['object'].device_vendor).alias
            if kwargs['object'].device_model:
                context['device_model'] = DeviceModel.objects.get(pk=kwargs['object'].device_model).alias
            if kwargs['object'].device_type:
                context['device_type'] = DeviceType.objects.get(pk=kwargs['object'].device_type).alias
            if kwargs['object'].country:
                context['country'] = Country.objects.get(pk=kwargs['object'].country).country_name
            if kwargs['object'].state:
                context['state'] = State.objects.get(pk=kwargs['object'].state).state_name
            if kwargs['object'].city:
                context['city'] = City.objects.get(pk=kwargs['object'].city).city_name
        except Exception as e:
            logger.exception(e.message)

        return context


class DeviceCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Render device create view
    """
    template_name = 'device/device_new.html'
    model = Device
    form_class = DeviceForm
    success_url = reverse_lazy('device_list')
    required_permissions = ('device.add_device',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        # post_fields: it contains form post data
        # for e.g. <QueryDict: {u'tower_height': [u''], u'qos_bw': [u'fevefvef']}>
        post_fields = self.request.POST

        # all_non_empty_post_fields: it's a list which contains all non empty fields
        # for e.g. [u'qos_bw', u'device_group', u'device_type', u'timezone', u'device_technology']
        all_non_empty_post_fields = []

        # It inserts all non empty fields keys from 'post_fields' into 'all_non_empty_post_fields'
        # except 'csrf' hidden field
        for key, value in post_fields.iteritems():
            if key == "csrfmiddlewaretoken": continue
            if value != "":
                all_non_empty_post_fields.append(key)

        # id of last inserted row in 'device' model
        device_latest_id = 1

        # get device latest inserted in schema
        try:
            id_list = [Device.objects.latest('id').id, int(Device.objects.latest('id').device_name)]
            device_latest_id = max(id_list) + 1
        except Exception as e:
            logger.exception("No device is added in database till now. Exception: ", e.message)

        # saving device data
        device = Device()
        device.device_name = device_latest_id
        device.device_alias = form.cleaned_data['device_alias']
        device.machine = form.cleaned_data['machine']
        device.site_instance = form.cleaned_data['site_instance']
        device.organization_id = form.cleaned_data['organization'].id
        device.device_technology = form.cleaned_data['device_technology']
        device.device_vendor = form.cleaned_data['device_vendor']
        device.device_model = form.cleaned_data['device_model']
        device.device_type = form.cleaned_data['device_type']
        device.parent = form.cleaned_data['parent']
        device.ip_address = form.cleaned_data['ip_address']
        device.mac_address = form.cleaned_data['mac_address']
        device.netmask = form.cleaned_data['netmask']
        device.gateway = form.cleaned_data['gateway']
        device.dhcp_state = form.cleaned_data['dhcp_state']
        device.host_priority = form.cleaned_data['host_priority']
        device.host_state = form.cleaned_data['host_state']
        device.latitude = form.cleaned_data['latitude']
        device.longitude = form.cleaned_data['longitude']
        device.timezone = form.cleaned_data['timezone']
        device.country = form.cleaned_data['country']
        device.state = form.cleaned_data['state']
        device.city = form.cleaned_data['city']
        device.address = form.cleaned_data['address']
        device.description = form.cleaned_data['description']
        device.save()

        # saving associated ports  --> M2M Relation (Model: DevicePort)
        for port in form.cleaned_data['ports']:
            device_port = DevicePort.objects.get(name=port)
            device.ports.add(device_port)
            device.save()

        # fetching device extra fields associated with 'device type'
        try:
            device_type = DeviceType.objects.get(id=int(self.request.POST.get('device_type')))
            # it gives all device fields associated with device_type object
            device_type.devicetypefields_set.all()
        except Exception as e:
            logger.exception(e.message)

        # saving eav relation data i.e. device extra fields those depends on device type
        for field in all_non_empty_post_fields:
            try:
                # dtf: device type field object
                # dtfv: device type field value object
                dtf = DeviceTypeFields.objects.filter(field_name=field,
                                                      device_type_id=int(self.request.POST.get('device_type')))
                dtfv = DeviceTypeFieldsValue()
                dtfv.device_type_field = dtf[0]
                dtfv.field_value = self.request.POST.get(field)
                dtfv.device_id = device.id
                dtfv.save()
            except Exception as e:
                logger.exception(e.message)
        return HttpResponseRedirect(DeviceCreate.success_url)


class DeviceUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Render device update view
    """
    template_name = 'device/device_update.html'
    model = Device
    form_class = DeviceForm
    success_url = reverse_lazy('device_list')
    required_permissions = ('device.change_device',)

    def get_queryset(self):
        return Device.objects.filter(organization__in=logged_in_user_organizations(self))

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """

        # post_fields: it contains form post data
        # for e.g. <QueryDict: {u'tower_height': [u''], u'qos_bw': [u'fevefvef']}>
        post_fields = self.request.POST

        # all_non_empty_post_fields: it's a list which contains all non empty fields
        # for e.g. [u'qos_bw', u'device_group', u'device_type', u'timezone', u'device_technology']
        all_non_empty_post_fields = []

        # It inserts all non empty fields keys from 'post_fields' into 'all_non_empty_post_fields'
        # except 'csrf' hidden field
        for key, value in post_fields.iteritems():
            if key == "csrfmiddlewaretoken": continue
            if value != "":
                all_non_empty_post_fields.append(key)

        # saving device data
        # self.object.device_name = form.cleaned_data['device_name']
        self.object.device_alias = form.cleaned_data['device_alias']
        self.object.machine = form.cleaned_data['machine']
        self.object.site_instance = form.cleaned_data['site_instance']
        self.object.organization_id = form.cleaned_data['organization']
        self.object.device_technology = form.cleaned_data['device_technology']
        self.object.device_vendor = form.cleaned_data['device_vendor']
        self.object.device_model = form.cleaned_data['device_model']
        self.object.device_type = form.cleaned_data['device_type']
        self.object.parent = form.cleaned_data['parent']
        self.object.ip_address = form.cleaned_data['ip_address']
        self.object.mac_address = form.cleaned_data['mac_address']
        self.object.netmask = form.cleaned_data['netmask']
        self.object.gateway = form.cleaned_data['gateway']
        self.object.dhcp_state = form.cleaned_data['dhcp_state']
        self.object.host_priority = form.cleaned_data['host_priority']
        self.object.host_state = form.cleaned_data['host_state']
        self.object.latitude = form.cleaned_data['latitude']
        self.object.longitude = form.cleaned_data['longitude']
        self.object.timezone = form.cleaned_data['timezone']
        self.object.country = form.cleaned_data['country']
        self.object.state = form.cleaned_data['state']
        self.object.city = form.cleaned_data['city']
        self.object.address = form.cleaned_data['address']
        self.object.description = form.cleaned_data['description']
        self.object.organization = form.cleaned_data['organization']
        self.object.save()

        # delete old ports
        self.object.ports.clear()

        # saving associated ports  --> M2M Relation (Model: DevicePort)
        for port in form.cleaned_data['ports']:
            device_port = DevicePort.objects.get(name=port)
            self.object.ports.add(device_port)
            self.object.save()

        # deleting old device extra field values
        try:
            DeviceTypeFieldsValue.objects.filter(device_id=self.object.id).delete()
        except Exception as e:
            logger.exception(e.message)

        # fetching device extra fields associated with 'device type'
        try:
            device_type = DeviceType.objects.get(id=int(self.request.POST.get('device_type')))
            # it gives all device fields associated with device_type object
            device_type.devicetypefields_set.all()
        except Exception as e:
            logger.exception(e.message)

        # saving eav relation data i.e. device extra fields those depends on device type
        for field in all_non_empty_post_fields:
            try:
                # dtf: device type field object
                # dtfv: device type field value object
                dtf = DeviceTypeFields.objects.filter(field_name=field,
                                                      device_type_id=int(self.request.POST.get('device_type')))
                dtfv = DeviceTypeFieldsValue()
                dtfv.device_type_field = dtf[0]
                dtfv.field_value = self.request.POST.get(field)
                dtfv.device_id = self.object.id
                dtfv.save()
            except Exception as e:
                logger.exception(e.message)

        # dictionary containing old values of current device
        initial_field_dict = form.initial

        # if 'site_instance' value is changed and 'is_added_to_nms' is 1 than set 'is_added_to_nms' to 2
        try:
            if (initial_field_dict['site_instance'] != form.cleaned_data['site_instance'].id) and (self.object.is_added_to_nms == 1):
                self.object.is_added_to_nms = 2
                self.object.save()
        except Exception as e:
            logger.exception(e.message)

        # if 'ip_address' value is changed and 'is_added_to_nms' is 1 than set 'is_added_to_nms' to 2
        try:
            if (initial_field_dict['ip_address'] != form.cleaned_data['ip_address']) and (self.object.is_added_to_nms == 1):
                self.object.is_added_to_nms = 2
                self.object.save()
        except Exception as e:
            logger.exception(e.message)


        def cleaned_data_field():
            """
            Clean data after submitting the form
            """
            cleaned_data_field_dict = {}
            for field in form.cleaned_data.keys():
                if field in ('parent', 'site_instance', 'organization'):
                    cleaned_data_field_dict[field] = form.cleaned_data[field].pk if form.cleaned_data[field] else None
                elif field in ('device_model', 'device_type', 'device_vendor', 'device_technology') and \
                        form.cleaned_data[field]:
                    cleaned_data_field_dict[field] = int(form.cleaned_data[field])
                else:
                    cleaned_data_field_dict[field] = form.cleaned_data[field]

            return cleaned_data_field_dict

        cleaned_data_field_dict = cleaned_data_field()
        changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
        try:
            if changed_fields_dict:
                initial_field_dict['parent'] = Device.objects.get(pk=initial_field_dict['parent']).device_name \
                    if initial_field_dict['parent'] else str(None)
                initial_field_dict['organization'] = Organization.objects.get(
                    pk=initial_field_dict['organization']).name \
                    if initial_field_dict['organization'] else str(None)
                initial_field_dict['site_instance'] = SiteInstance.objects.get(
                    pk=initial_field_dict['site_instance']).name \
                    if initial_field_dict['site_instance'] else str(None)
                initial_field_dict['device_model'] = DeviceModel.objects.get(pk=initial_field_dict['device_model']).name \
                    if initial_field_dict['device_model'] else str(None)
                initial_field_dict['device_type'] = DeviceType.objects.get(pk=initial_field_dict['device_type']).name \
                    if initial_field_dict['device_type'] else str(None)
                initial_field_dict['device_vendor'] = DeviceVendor.objects.get(
                    pk=initial_field_dict['device_vendor']).name \
                    if initial_field_dict['device_vendor'] else str(None)
                initial_field_dict['device_technology'] = DeviceTechnology.objects.get(
                    pk=initial_field_dict['device_technology']).name \
                    if initial_field_dict['device_technology'] else str(None)

                cleaned_data_field_dict['parent'] = Device.objects.get(pk=cleaned_data_field_dict['parent']).device_name \
                    if cleaned_data_field_dict['parent'] else str(None)
                cleaned_data_field_dict['organization'] = Organization.objects.get(
                    pk=cleaned_data_field_dict['organization']).name \
                    if cleaned_data_field_dict['organization'] else str(None)
                cleaned_data_field_dict['site_instance'] = SiteInstance.objects.get(
                    pk=cleaned_data_field_dict['site_instance']).name \
                    if cleaned_data_field_dict['site_instance'] else str(None)
                cleaned_data_field_dict['device_model'] = DeviceModel.objects.get(
                    pk=cleaned_data_field_dict['device_model']).name \
                    if cleaned_data_field_dict['device_model'] else str(None)
                cleaned_data_field_dict['device_type'] = DeviceType.objects.get(
                    pk=cleaned_data_field_dict['device_type']).name \
                    if cleaned_data_field_dict['device_type'] else str(None)
                cleaned_data_field_dict['device_vendor'] = DeviceVendor.objects.get(
                    pk=cleaned_data_field_dict['device_vendor']).name \
                    if cleaned_data_field_dict['device_vendor'] else str(None)
                cleaned_data_field_dict['device_technology'] = DeviceTechnology.objects.get(
                    pk=cleaned_data_field_dict['device_technology']).name \
                    if cleaned_data_field_dict['device_technology'] else str(None)

                verb_string = 'Changed values of Device %s from initial values ' % (
                    self.object.device_name) + ', '.join(['%s: %s' % (k, initial_field_dict[k]) \
                                                          for k in changed_fields_dict]) + \
                              ' to ' + \
                              ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])
                if len(verb_string) >= 255:
                    verb_string = verb_string[:250] + '...'

        except Exception as user_audit_exeption:
            logger.exception(user_audit_exeption.message)

        return HttpResponseRedirect(DeviceCreate.success_url)


class DeviceDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device delete view
    """
    model = Device
    required_permissions = ('device.delete_device',)
    template_name = 'device/device_delete.html'
    success_url = reverse_lazy('device_list')
    obj_alias = 'device_alias'


# ******************************** Device Type Form Fields Views ************************************


class DeviceTypeFieldsList(PermissionsRequiredMixin, ListView):
    """
    Render list of device type extra fields
    """
    model = DeviceTypeFields
    template_name = 'device_extra_fields/device_extra_fields_list.html'
    required_permissions = ('device.view_devicetypefields',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceTypeFieldsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'field_name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'field_display_name', 'sTitle': 'Field Display Name', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device_type__name', 'sTitle': 'Device Type', 'sWidth': 'auto'},
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceTypeFieldsListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device type fields
    """
    model = DeviceTypeFields
    required_permissions = ('device.view_devicetypefields',)
    columns = ['field_name', 'field_display_name', 'device_type__name']
    order_columns = ['field_name', 'field_display_name', 'device_type__name']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()
            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
            return result_list
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        return DeviceTypeFields.objects.values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/device_fields/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                        <a href="/device_fields/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                dct.pop('id')))
        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceTypeFieldsDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for device extra field
    """
    model = DeviceTypeFields
    required_permissions = ('device.view_devicetypefields',)
    template_name = 'device_extra_fields/device_extra_field_detail.html'


class DeviceTypeFieldsCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device type field create view
    """
    template_name = 'device_extra_fields/device_extra_field_new.html'
    model = DeviceTypeFields
    form_class = DeviceTypeFieldsForm
    success_url = reverse_lazy('device_extra_field_list')
    required_permissions = ('device.add_devicetypefieldsvalue',)


class DeviceTypeFieldsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device type fields update view
    """
    template_name = 'device_extra_fields/device_extra_field_update.html'
    model = DeviceTypeFields
    form_class = DeviceTypeFieldsUpdateForm
    success_url = reverse_lazy('device_extra_field_list')
    required_permissions = ('device.change_devicetypefieldsvalue',)


class DeviceTypeFieldsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device type field delete view
    """
    model = DeviceTypeFields
    template_name = 'device_extra_fields/device_extra_field_delete.html'
    success_url = reverse_lazy('device_extra_field_list')
    required_permissions = ('device.delete_devicetypefieldsvalue',)
    obj_alias = 'field_display_name'


# **************************************** Device Technology ****************************************

class DeviceTechnologyList(PermissionsRequiredMixin, ListView):
    """
    Render list of technologies
    """
    model = DeviceTechnology
    template_name = 'device_technology/device_technology_list.html'
    required_permissions = ('device.view_devicetechnology',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceTechnologyList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto'},
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto'},
            {'mData': 'device_vendor', 'sTitle': 'Device Vendor', 'sWidth': '10%'},
            {'mData': 'device_vendor__model__name', 'sTitle': 'Device Model', 'sWidth': '10%', },
            {'mData': 'device_vendor__model_type__name', 'sTitle': 'Device Type', 'sWidth': '10%', }
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceTechnologyListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device technologies
    """
    model = DeviceTechnology
    required_permissions = ('device.view_devicetechnology',)
    columns = ['name', 'alias', 'device_vendor', 'device_vendor__model__name', 'device_vendor__model_type__name']
    order_columns = ['name', 'alias', 'device_vendor', 'device_vendor__model__name', 'device_vendor__model_type__name']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()
            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
            return result_list
        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        qs_query = DeviceTechnology.objects.prefetch_related()
        qs = list()
        for dtechnology in qs_query:
            dct = dict()
            for dtechnology_vendor in dtechnology.device_vendors.values_list('name', flat=True):
                dct = {
                    'id': dtechnology.id, 'name': dtechnology.name, 'alias': dtechnology.alias,
                    'device_vendor': dtechnology_vendor
                }
                dvendor = DeviceVendor.objects.get(name=dtechnology_vendor)

                dct['device_vendor__model__name'] = ', '.join(dvendor.device_models.values_list('name', flat=True))

                for dmodel in dvendor.device_models.prefetch_related():
                    dct['device_vendor__model_type__name'] = ', '.join(
                        dmodel.device_types.values_list('name', flat=True))

                qs.append(dct)
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/technology/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                        <a href="/technology/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                dct.pop('id')))
        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceTechnologyDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for technology
    """
    model = DeviceTechnology
    required_permissions = ('device.view_devicetechnology',)
    template_name = 'device_technology/device_technology_detail.html'


class DeviceTechnologyCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device technology create view
    """
    template_name = 'device_technology/device_technology_new.html'
    model = DeviceTechnology
    form_class = DeviceTechnologyForm
    success_url = reverse_lazy('device_technology_list')
    required_permissions = ('device.add_devicetechnology',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        device_technology = DeviceTechnology()
        device_technology.name = form.cleaned_data['name']
        device_technology.alias = form.cleaned_data['alias']
        device_technology.save()

        # saving device_vendors --> M2M Relation (Model: TechnologyVendor)
        for device_vendor in form.cleaned_data['device_vendors']:
            tv = TechnologyVendor()
            tv.technology = device_technology
            tv.vendor = device_vendor
            tv.save()
        return HttpResponseRedirect(DeviceTechnologyCreate.success_url)


class DeviceTechnologyUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device technology update view
    """
    template_name = 'device_technology/device_technology_update.html'
    model = DeviceTechnology
    form_class = DeviceTechnologyForm
    success_url = reverse_lazy('device_technology_list')
    required_permissions = ('device.change_devicetechnology',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        self.object.name = form.cleaned_data['name']
        self.object.alias = form.cleaned_data['alias']
        self.object.save()

        # delete old relationship exist in technology-vendor
        TechnologyVendor.objects.filter(technology=self.object).delete()

        # updating device_vendors --> M2M Relation (Model: TechnologyVendor)
        for device_vendor in form.cleaned_data['device_vendors']:
            tv = TechnologyVendor()
            tv.technology = self.object
            tv.vendor = device_vendor
            tv.save()
        try:
            initial_field_dict = {field: form.initial[field] for field in form.initial.keys()}

            cleaned_data_field_dict = {field: map(lambda obj: obj.pk, form.cleaned_data[field])
            if field in ('device_vendors') and form.cleaned_data[field] else form.cleaned_data[field] for field in
                                       form.cleaned_data.keys()}

            changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
            if changed_fields_dict:
                initial_field_dict['device_vendors'] = ', '.join(
                    [DeviceVendor.objects.get(pk=vendor).name for vendor in initial_field_dict['device_vendors']])
                cleaned_data_field_dict['device_vendors'] = ', '.join(
                    [DeviceVendor.objects.get(pk=vendor).name for vendor in cleaned_data_field_dict['device_vendors']])

                verb_string = 'Changed values of Device Technology : %s from initial values ' % (self.object.name) \
                              + ', '.join(['%s: %s' % (k, initial_field_dict[k]) for k in changed_fields_dict]) \
                              + ' to ' + \
                              ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])
                if len(verb_string) >= 255:
                    verb_string = verb_string[:250] + '...'

        except Exception as activity:
            pass

        return HttpResponseRedirect(DeviceTechnologyUpdate.success_url)


class DeviceTechnologyDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device technology delete view
    """
    model = DeviceTechnology
    template_name = 'device_technology/device_technology_delete.html'
    success_url = reverse_lazy('device_technology_list')
    required_permissions = ('device.delete_devicetechnology',)


# ************************************* Device Vendor ***********************************************
class DeviceVendorList(PermissionsRequiredMixin, ListView):
    """
    Render list of vendors
    """
    model = DeviceVendor
    template_name = 'device_vendor/device_vendor_list.html'
    required_permissions = ('device.view_devicevendor',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceVendorList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'device_models', 'sTitle': 'Device Models', 'sWidth': 'auto', },
            {'mData': 'device_types', 'sTitle': 'Device Types', 'sWidth': 'auto', },
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceVendorListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device vendors
    """
    model = DeviceVendor
    required_permissions = ('device.view_devicevendor',)
    columns = ['name', 'alias', 'device_models', 'device_types']
    order_columns = ['name', 'alias', 'device_models', 'device_types']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()
            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
            return result_list

        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        qs = list()

        qs_query = DeviceVendor.objects.prefetch_related()
        for dvendor in qs_query:
            dct = dict()
            dct = {
                'id': dvendor.id,
                'name': dvendor.name,
                'alias': dvendor.alias,
                'device_models': ', '.join(dvendor.device_models.values_list('name', flat=True)),
            }
            for dmodels in dvendor.device_models.prefetch_related():
                dct['device_types'] = ', '.join(dmodels.device_types.values_list('name', flat=True))
            qs.append(dct)

        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/vendor/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                        <a href="/vendor/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceVendorDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for vendor
    """
    model = DeviceVendor
    required_permissions = ('device.view_devicevendor',)
    template_name = 'device_vendor/device_vendor_detail.html'


class DeviceVendorCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device vendor create view
    """
    template_name = 'device_vendor/device_vendor_new.html'
    model = DeviceVendor
    form_class = DeviceVendorForm
    success_url = reverse_lazy('device_vendor_list')
    required_permissions = ('device.add_devicevendor',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        device_vendor = DeviceVendor()
        device_vendor.name = form.cleaned_data['name']
        device_vendor.alias = form.cleaned_data['alias']
        device_vendor.save()

        # saving device_models --> M2M Relation (Model: VendorModel)
        for device_model in form.cleaned_data['device_models']:
            vm = VendorModel()
            vm.vendor = device_vendor
            vm.model = device_model
            vm.save()
        return HttpResponseRedirect(DeviceVendorCreate.success_url)


class DeviceVendorUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device vendor update view
    """
    template_name = 'device_vendor/device_vendor_update.html'
    model = DeviceVendor
    form_class = DeviceVendorForm
    success_url = reverse_lazy('device_vendor_list')
    required_permissions = ('device.change_devicevendor',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        self.object.name = form.cleaned_data['name']
        self.object.alias = form.cleaned_data['alias']
        self.object.save()

        # delete old relationship exist in vendor-model
        VendorModel.objects.filter(vendor=self.object).delete()

        # updating device_models --> M2M Relation (Model: VendorModel)
        for device_model in form.cleaned_data['device_models']:
            vm = VendorModel()
            vm.vendor = self.object
            vm.model = device_model
            vm.save()

        try:
            initial_field_dict = {field: form.initial[field] for field in form.initial.keys()}

            cleaned_data_field_dict = {field: map(lambda obj: obj.pk, form.cleaned_data[field])
            if field in ('device_models') and form.cleaned_data[field] else form.cleaned_data[field]
                                       for field in form.cleaned_data.keys()}

            changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
            if changed_fields_dict:
                initial_field_dict['device_models'] = ', '.join(
                    [DeviceModel.objects.get(pk=vendor).name for vendor in initial_field_dict['device_models']])
                cleaned_data_field_dict['device_models'] = ', '.join(
                    [DeviceModel.objects.get(pk=vendor).name for vendor in cleaned_data_field_dict['device_models']])

                verb_string = 'Changed values of Device Vendor : %s from initial values ' % (self.object.name) \
                              + ', '.join(['%s: %s' % (k, initial_field_dict[k]) for k in changed_fields_dict]) \
                              + ' to ' + \
                              ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])

                if len(verb_string) >= 255:
                    verb_string = verb_string[:250] + '...'

        except Exception as activity:
            pass

        return HttpResponseRedirect(DeviceVendorUpdate.success_url)


class DeviceVendorDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device vendor delete view
    """
    model = DeviceVendor
    template_name = 'device_vendor/device_vendor_delete.html'
    success_url = reverse_lazy('device_vendor_list')
    required_permissions = ('device.delete_devicevendor',)


# ****************************************** Device Model *******************************************


class DeviceModelList(PermissionsRequiredMixin, ListView):
    """
    Render list of models
    """
    model = DeviceModel
    template_name = 'device_model/device_model_list.html'
    required_permissions = ('device.view_devicemodel',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceModelList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'device_types', 'sTitle': 'Device Types', 'sWidth': 'auto', }
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceModelListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device models
    """
    model = DeviceModel
    required_permissions = ('device.view_devicemodel',)
    columns = ['name', 'alias', 'device_types']
    order_columns = ['name', 'alias', 'device_types']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()
            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
            return result_list

        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        qs_query = DeviceModel.objects.prefetch_related()
        qs = list()
        for dmodel in qs_query:
            dct = dict()
            dct = {
                'id': dmodel.id,
                'name': dmodel.name,
                'alias': dmodel.alias,
                'device_types': ', '.join(dmodel.device_types.values_list('name', flat=True)),
            }
            qs.append(dct)
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/model/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                        <a href="/model/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                dct.pop('id')))
        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs


    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceModelDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for model
    """
    model = DeviceModel
    required_permissions = ('device.view_devicemodel',)
    template_name = 'device_model/device_model_detail.html'


class DeviceModelCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device model create view
    """
    template_name = 'device_model/device_model_new.html'
    model = DeviceModel
    form_class = DeviceModelForm
    success_url = reverse_lazy('device_model_list')
    required_permissions = ('device.add_devicemodel',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        device_model = DeviceModel()
        device_model.name = form.cleaned_data['name']
        device_model.alias = form.cleaned_data['alias']
        device_model.save()

        # saving device_types --> M2M Relation (Model: ModelType)
        for device_type in form.cleaned_data['device_types']:
            mt = ModelType()
            mt.model = device_model
            mt.type = device_type
            mt.save()

        return HttpResponseRedirect(DeviceModelCreate.success_url)


class DeviceModelUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device model update view
    """
    template_name = 'device_model/device_model_update.html'
    model = DeviceModel
    form_class = DeviceModelForm
    success_url = reverse_lazy('device_model_list')
    required_permissions = ('device.change_devicemodel',)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        self.object.name = form.cleaned_data['name']
        self.object.alias = form.cleaned_data['alias']
        self.object.save()

        # delete old relationship exist in model-type
        ModelType.objects.filter(model=self.object).delete()

        # updating model_types --> M2M Relation (Model: ModelType)
        for device_type in form.cleaned_data['device_types']:
            mt = ModelType()
            mt.model = self.object
            mt.type = device_type
            mt.save()

        return HttpResponseRedirect(DeviceModelUpdate.success_url)


class DeviceModelDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device model delete view
    """
    model = DeviceModel
    template_name = 'device_model/device_model_delete.html'
    success_url = reverse_lazy('device_model_list')
    required_permissions = ('device.delete_devicemodel',)


# ****************************************** Device Type *******************************************


class DeviceTypeList(PermissionsRequiredMixin, ListView):
    """
    Render list of device types
    """
    model = DeviceType
    template_name = 'device_type/device_type_list.html'
    required_permissions = ('device.view_devicetype',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceTypeList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'agent_tag', 'sTitle': 'Agent tag', 'sWidth': 'auto', },
            {'mData': 'packets', 'sTitle': 'Packets', 'sWidth': 'auto'},
            {'mData': 'timeout', 'sTitle': 'Timeout', 'sWidth': 'auto'},
            {'mData': 'normal_check_interval', 'sTitle': 'Normal Check Interval', 'sWidth': 'auto'},
            {'mData': 'rta_warning', 'sTitle': 'RTA Warining', 'sWidth': 'auto'},
            {'mData': 'rta_critical', 'sTitle': 'RTA Critical', 'sWidth': 'auto'},
            {'mData': 'pl_warning', 'sTitle': 'PL Warning', 'sWidth': 'auto'},
            {'mData': 'pl_critical', 'sTitle': 'PL Critical', 'sWidth': 'auto'},
            {'mData': 'device_icon', 'sTitle': 'Device Icon', 'sWidth': 'auto'},
            {'mData': 'device_gmap_icon', 'sTitle': 'Device GMap Icon', 'sWidth': 'auto'},
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '5%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceTypeListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device types
    """
    model = DeviceType
    required_permissions = ('device.view_devicetype',)
    columns = ['name', 'alias', 'agent_tag', 'packets', 'timeout', 'normal_check_interval',
               'rta_warning', 'rta_critical', 'pl_warning', 'pl_critical', 'device_icon', 'device_gmap_icon']
    order_columns = ['name', 'alias', 'agent_tag', 'packets', 'timeout', 'normal_check_interval',
               'rta_warning', 'rta_critical', 'pl_warning', 'pl_critical', 'device_icon', 'device_gmap_icon']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            result_list = list()
            for dictionary in qs:

                x = json.dumps(dictionary)
                dictionary = json.loads(x)

                for dict in dictionary:
                    if dictionary[dict]:
                        if (isinstance(dictionary[dict], unicode) or isinstance(dictionary[dict], str)) and (
                            dictionary not in result_list
                        ):
                            if sSearch.encode('utf-8').lower() in dictionary[dict].encode('utf-8').lower():
                                result_list.append(dictionary)
                        else:
                            if sSearch == dictionary[dict] and dictionary not in result_list:
                                result_list.append(dictionary)
            return result_list

        return qs

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        return DeviceType.objects.values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            try:
                device_icon_img_url = "/media/"+ (dct['device_icon']) if \
                    "uploaded" in dct['device_icon'] \
                    else static("img/" + dct['device_icon'])
                dct.update(device_icon='<img src="{0}" style="float:left; display:block; height:25px; width:25px;">'.format(device_icon_img_url))
            except Exception as e:
                logger.exception(e)

            try:
                device_gmap_icon_img_url = "/media/"+ (dct['device_gmap_icon']) if \
                    "uploaded" in dct['device_gmap_icon'] \
                    else static("img/" + dct['device_gmap_icon'])
                dct.update(device_gmap_icon='<img src="{0}" style="float:left; display:block; height:25px; width:25px;">'.format(device_gmap_icon_img_url))
            except Exception as e:
                logger.exception(e)

            dct.update(actions='<a href="/type/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                        <a href="/type/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def ordering(self, qs):
        """ Get parameters from the request and prepare order by clause
        """
        request = self.request
        # Number of columns that are used in sorting
        try:
            i_sorting_cols = int(request.REQUEST.get('iSortingCols', 0))
        except ValueError:
            i_sorting_cols = 0

        order = []
        order_columns = self.get_order_columns()
        for i in range(i_sorting_cols):
            # sorting column
            try:
                i_sort_col = int(request.REQUEST.get('iSortCol_%s' % i))
            except ValueError:
                i_sort_col = 0
            # sorting order
            s_sort_dir = request.REQUEST.get('sSortDir_%s' % i)

            sdir = '-' if s_sort_dir == 'desc' else ' '

            sortcol = order_columns[i_sort_col]
            if isinstance(sortcol, list):
                for sc in sortcol:
                    order.append('%s%s' % (sdir, sc))
            else:
                order.append('%s%s' % (sdir, sortcol))
        if order:
            return sorted(qs, key=itemgetter(order[0][1:]), reverse=True if '-' in order[0] else False)
        return qs


    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceTypeDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for device type
    """
    model = DeviceType
    required_permissions = ('device.view_devicetype',)
    template_name = 'device_type/device_type_detail.html'


class DeviceTypeCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device type create view
    """
    template_name = 'device_type/device_type_new.html'
    model = DeviceType
    form_class = DeviceTypeForm
    success_url = reverse_lazy('device_type_list')
    required_permissions = ('device.add_devicetype',)


class DeviceTypeUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device type update view
    """
    template_name = 'device_type/device_type_update.html'
    model = DeviceType
    form_class = DeviceTypeForm
    success_url = reverse_lazy('device_type_list')
    required_permissions = ('device.change_devicetype',)


class DeviceTypeDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device type delete view
    """
    model = DeviceType
    template_name = 'device_type/device_type_delete.html'
    success_url = reverse_lazy('device_type_list')
    required_permissions = ('device.delete_devicetype',)


# ****************************************** Device Type *******************************************
class DevicePortList(PermissionsRequiredMixin, ListView):
    """
    Render list of ports
    """
    model = DevicePort
    template_name = 'device_port/device_ports_list.html'
    required_permissions = ('device.view_deviceport',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DevicePortList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'value', 'sTitle': 'Value', 'sWidth': 'auto', },
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DevicePortListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device ports
    """
    model = DevicePort
    required_permissions = ('device.view_deviceport',)
    columns = ['name', 'alias', 'value']
    order_columns = ['name', 'alias', 'value']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            query = []
            exec_query = "qs = %s.objects.filter(" % (self.model.__name__)
            for column in self.columns[:-1]:
                query.append("Q(%s__contains=" % column + "\"" + sSearch + "\"" + ")")

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
        return DevicePort.objects.values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/device_port/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/device_port/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DevicePortDetail(PermissionsRequiredMixin, DetailView):
    """
    Render detail view for device port
    """
    model = DevicePort
    required_permissions = ('device.view_deviceport',)
    template_name = 'device_port/device_port_detail.html'


class DevicePortCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device port create view
    """
    template_name = 'device_port/device_port_new.html'
    model = DevicePort
    form_class = DevicePortForm
    success_url = reverse_lazy('device_ports_list')
    required_permissions = ('device.add_deviceport',)


class DevicePortUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device port update view
    """
    template_name = 'device_port/device_port_update.html'
    model = DevicePort
    form_class = DevicePortForm
    success_url = reverse_lazy('device_ports_list')
    required_permissions = ('device.change_deviceport',)


class DevicePortDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device port delete view
    """
    model = DevicePort
    template_name = 'device_port/device_port_delete.html'
    success_url = reverse_lazy('device_ports_list')
    required_permissions = ('device.delete_deviceport',)


class DeviceFrequencyListing(PermissionsRequiredMixin, ListView):
    """
    Render list of device frequencies list
    """
    model = DeviceFrequency
    template_name = 'device_frequency/device_frequency_list.html'
    required_permissions = ('device.view_devicefrequency',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(DeviceFrequencyListing, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'value', 'sTitle': 'Value', 'sWidth': 'auto', },
            {'mData': 'color_hex_value', 'sTitle': 'Hex Value', 'sWidth': 'auto', },
            {'mData': 'frequency_radius', 'sTitle': 'Frequency Radius (Km)', 'sWidth': 'auto', }
        ]
        if self.request.user.is_superuser:
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DeviceFrequencyListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Render JQuery datatables for listing of device frequencies
    """
    model = DeviceFrequency
    required_permissions = ('device.view_devicefrequency',)
    columns = ['value', 'color_hex_value', 'frequency_radius']
    order_columns = ['value', 'color_hex_value', 'frequency_radius']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch and len(str(sSearch).strip()) >= 3:
            sSearch = sSearch.replace("\\","")
            query = []
            exec_query = "qs = %s.objects.filter(" % (self.model.__name__)
            for column in self.columns:
                query.append("Q(%s__contains=" % column + "\"" + sSearch + "\"" + ")")

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
        return DeviceFrequency.objects.values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            if "color_hex_value" in dct:
                dct.update(value = dct["value"] + " MHz")

                dct.update(
                    color_hex_value="<div style='float:left; display:block; height:20px; width:20px; background:{0}'>"
                                    "</div>" \
                                    "<span style='margin-left: 5px;'>{0}</span>".
                    format(dct["color_hex_value"]))

                dct.update(frequency_radius = "N/A"
                            if not dct['frequency_radius']
                            else dct['frequency_radius']
                )

            dct.update(actions='<a href="/frequency/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/frequency/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
        """
        The main function call to fetch, search, ordering , prepare and display the data on the data table.
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
        #if the qs is empty then JSON is unable to serialize the empty ValuesQuerySet.
        # Therefore changing its type to list.
        if not qs and isinstance(qs, ValuesQuerySet):
            qs = list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class DeviceFrequencyCreate(PermissionsRequiredMixin, CreateView):
    """
    Render device frequency create view
    """
    template_name = 'device_frequency/device_frequency_new.html'
    model = DeviceFrequency
    form_class = DeviceFrequencyForm
    success_url = reverse_lazy('device_frequency_list')
    required_permissions = ('device.add_devicefrequency',)


class DeviceFrequencyUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Render device frequency update view
    """
    template_name = 'device_frequency/device_frequency_update.html'
    model = DeviceFrequency
    form_class = DeviceFrequencyForm
    success_url = reverse_lazy('device_frequency_list')
    required_permissions = ('device.change_devicefrequency',)


class DeviceFrequencyDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Render device frequency delete view
    """
    model = DeviceFrequency
    template_name = 'device_frequency/device_frequency_delete.html'
    success_url = reverse_lazy('device_frequency_list')
    required_permissions = ('device.delete_devicefrequency',)
    obj_alias = 'value'

