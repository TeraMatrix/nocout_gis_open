"""
Contain Gis Inventory Views.

- Provide views to List, Create, Update and Delete Gis Inventory Models.
- Provide views to Bulk Upload inventory data using Excel Sheets.
- Provide Gis Wizard to manage inventory in easier way.
"""
import os
import re
import time
import json
import xlrd
import xlwt

from operator import itemgetter
from datetime import datetime

from django.db.models import Count, Q
from django.db.models.query import ValuesQuerySet
from django.core.urlresolvers import reverse_lazy, reverse

from django.views.generic import ListView, DetailView, View, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, render_to_response
from django.template import RequestContext

from django.contrib.auth.models import User
from django.contrib.staticfiles.templatetags.staticfiles import static

from django_datatables_view.base_datatable_view import BaseDatatableView

from nocout.settings import GISADMIN, NOCOUT_USER, MEDIA_ROOT, MEDIA_URL, DATE_TIME_FORMAT
from nocout.mixins.permissions import PermissionsRequiredMixin
from nocout.mixins.generics import FormRequestMixin
from nocout.mixins.user_action import UserLogDeleteMixin
from nocout.mixins.datatable import DatatableOrganizationFilterMixin, DatatableSearchMixin, ValuesQuerySetMixin
from nocout.mixins.select2 import Select2Mixin
from nocout.utils import logged_in_user_organizations
from nocout.utils.util import DictDiffer, cache_for, cache_get_key, convert_utc_to_local_timezone

from organization.models import Organization
from user_profile.models import UserProfile
from user_group.models import UserGroup
from device_group.models import DeviceGroup
from device.models import Country, State, City, Device, DeviceType, DeviceTechnology
from performance.models import ServiceStatus, InventoryStatus, NetworkStatus, Status

from inventory.models import (Antenna, BaseStation, Backhaul, Sector, Customer, SubStation, Circuit, Inventory,
        IconSettings, LivePollingSettings, ThresholdConfiguration, ThematicSettings, GISInventoryBulkImport,
        UserThematicSettings, CircuitL2Report, PingThematicSettings, UserPingThematicSettings, GISExcelDownload)
from inventory.forms import (AntennaForm, BaseStationForm, BackhaulForm, SectorForm, CustomerForm, SubStationForm,
        CircuitForm, CircuitL2ReportForm, InventoryForm, IconSettingsForm, LivePollingSettingsForm,
        ThresholdConfigurationForm, ThematicSettingsForm, GISInventoryBulkImportForm, GISInventoryBulkImportEditForm,
        PingThematicSettingsForm,  ServiceThematicSettingsForm, ServiceThresholdConfigurationForm,
        ServiceLivePollingSettingsForm, WizardBaseStationForm, WizardBackhaulForm, WizardSectorForm, WizardAntennaForm,
        WizardSubStationForm, WizardCustomerForm, WizardCircuitForm, WizardPTPSubStationAntennaFormSet,
        DownloadSelectedBSInventoryEditForm)
from inventory.tasks import (validate_gis_inventory_excel_sheet, bulk_upload_ptp_inventory, bulk_upload_pmp_sm_inventory,
        bulk_upload_pmp_bs_inventory, bulk_upload_ptp_bh_inventory, bulk_upload_wimax_bs_inventory,
        bulk_upload_wimax_ss_inventory, bulk_upload_backhaul_inventory, generate_gis_inventory_excel)

import logging
logger = logging.getLogger(__name__)

##caching
from django.core.cache import cache
##caching

from django.views.decorators.csrf import csrf_exempt


# **************************************** Inventory *********************************************
def inventory(request):
    """
    Render the inventory page.
    """
    return render(request, 'inventory/inventory.html')


class InventoryListing(PermissionsRequiredMixin, ListView):
    """
    Class Based Inventory View to render list page.
    """
    model = Inventory
    template_name = 'inventory/inventory_list.html'
    required_permissions = ('inventory.view_inventory',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(InventoryListing, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'user_group__name', 'sTitle': 'User Group', 'sWidth': 'auto', },
            {'mData': 'organization__name', 'sTitle': 'Organization', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', },]

        #if the user role is Admin then the action column will appear on the datatable
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '5%', })

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class InventoryListingTable(PermissionsRequiredMixin, BaseDatatableView):
    """
    Class based View to render Inventory Data table.
    """

    model = Inventory
    required_permissions = ('inventory.view_inventory',)
    columns = ['alias', 'user_group__name', 'organization__name', 'description']
    order_columns = ['alias', 'user_group__name', 'organization__name', 'description']

    def filter_queryset(self, qs):
        """
        The filtering of the queryset with respect to the search keyword entered.

        :param qs:
        :return qs:
        """
        sSearch = self.request.GET.get('sSearch', None)
        if sSearch:
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
        organization_descendants_ids = self.request.user.userprofile.organization.get_descendants(
            include_self=True).values_list('id', flat=True)
        return Inventory.objects.filter(organization__in=organization_descendants_ids).values(*self.columns + ['id'])

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        if qs:
            qs = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in qs:
            dct.update(actions='<a href="/inventory/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                       <a href="/inventory/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                dct.pop('id')))

        return qs

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

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
        }
        return ret


class InventoryCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new Inventory.
    """

    template_name = 'inventory/inventory_new.html'
    model = Inventory
    form_class = InventoryForm
    success_url = reverse_lazy('InventoryList')
    required_permissions = ('inventory.add_inventory',)


class InventoryUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update new Inventory.
    """
    template_name = 'inventory/inventory_update.html'
    model = Inventory
    form_class = InventoryForm
    success_url = reverse_lazy('InventoryList')
    required_permissions = ('inventory.change_inventory',)


class InventoryDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Inventory

    """
    model = Inventory
    template_name = 'inventory/inventory_delete.html'
    success_url = reverse_lazy('InventoryList')
    required_permissions = ('inventory.delete_inventory',)


def inventory_details_wrt_organization(request):
    """
    Inventory details organization as a get organization parameter.
    """
    organization_id = request.GET['organization']
    organization_descendants_ids = Organization.objects.get(id=organization_id).get_descendants(
        include_self=True).values_list('id', flat=True)
    user_group = UserGroup.objects.filter(organization__in=organization_descendants_ids, is_deleted=0).values_list('id',
                                                                                                                   'name')
    device_groups = DeviceGroup.objects.filter(organization__in=organization_descendants_ids, is_deleted=0).values_list(
        'id', 'name')
    response_device_groups = response_user_group = ''
    for index in range(len(device_groups)):
        response_device_groups += '<option value={0}>{1}</option>'.format(*map(str, device_groups[index]))
    for index in range(len(user_group)):
        response_user_group += '<option value={0}>{1}</option>'.format(*map(str, user_group[index]))

    return HttpResponse(
        json.dumps({'response': {'device_groups': response_device_groups, 'user_groups': response_user_group}}), \
        content_type='application/json')


#**************************************** Antenna *********************************************
class SelectAntennaListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = Antenna


class AntennaList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Antenna data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """

    template_name = 'antenna/antenna_list.html'
    required_permissions = ('inventory.view_antenna',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(AntennaList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'height', 'sTitle': 'Height', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'polarization', 'sTitle': 'Polarization', 'sWidth': 'auto', },
            {'mData': 'tilt', 'sTitle': 'Tilt', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'beam_width', 'sTitle': 'Beam Width', 'sWidth': '10%', },
            {'mData': 'azimuth_angle', 'sTitle': 'Azimuth Angle', 'sWidth': '10%', }, ]

        #if the user role is Admin or operator or superuser then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role or self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class AntennaListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Antenna Data table.
    """
    model = Antenna
    columns = ['alias', 'height', 'polarization', 'tilt', 'beam_width', 'azimuth_angle']
    order_columns = ['alias', 'height', 'polarization', 'tilt', 'beam_width', 'azimuth_angle']
    required_permissions = ('inventory.view_antenna',)

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]

        for dct in json_data:
            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_antenna'):
                edit_action = '<a href="/antenna/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_antenna'):
                delete_action = '<a href="/antenna/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class AntennaDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the antenna detail.
    """
    model = Antenna
    template_name = 'antenna/antenna_detail.html'
    required_permissions = ('inventory.view_antenna',)


class AntennaCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new Antenna.
    """
    template_name = 'antenna/antenna_new.html'
    model = Antenna
    form_class = AntennaForm
    success_url = reverse_lazy('antennas_list')
    required_permissions = ('inventory.add_antenna',)


class AntennaUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Antenna .
    """
    template_name = 'antenna/antenna_update.html'
    model = Antenna
    form_class = AntennaForm
    success_url = reverse_lazy('antennas_list')
    required_permissions = ('inventory.change_antenna',)

    def get_queryset(self):
        return Antenna.objects.filter(organization__in=logged_in_user_organizations(self))


class AntennaDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Antenna.
    """
    model = Antenna
    template_name = 'antenna/antenna_delete.html'
    success_url = reverse_lazy('antennas_list')
    required_permissions = ('inventory.delete_antenna',)


#****************************************** Base Station ********************************************
class SelectBaseStationListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = BaseStation


class BaseStationList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Base Station data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'base_station/base_stations_list.html'
    required_permissions = ('inventory.view_basestation',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(BaseStationList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            # {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'bs_site_id', 'sTitle': 'Site ID', 'sWidth': 'auto', },
            {'mData': 'bs_switch__id', 'sTitle': 'BS Switch', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'backhaul__name', 'sTitle': 'Backhaul', 'sWidth': 'auto', },
            {'mData': 'bs_type', 'sTitle': 'BS Type', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'building_height', 'sTitle': 'Building Height', 'sWidth': 'auto', },
            {'mData': 'tower_height', 'sTitle': 'Tower Height', 'sWidth': 'auto', },
            {'mData': 'bh_capacity', 'sTitle': 'BH Capacity', 'sWidth': 'auto', },
            {'mData': 'state__state_name', 'sTitle': 'State', 'sWidth': 'auto', },
            {'mData': 'city__city_name', 'sTitle': 'City', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            ]
        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class BaseStationListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Base Station Data table.
    """
    model = BaseStation
    required_permissions = ('inventory.view_basestation',)
    columns = ['alias', 'bs_site_id', 'state__state_name', 'city__city_name', 'bh_capacity', 'tower_height',
               'bs_switch__id', 'backhaul__name', 'bs_type', 'building_height', 'description']
    order_columns = ['alias', 'bs_site_id', 'state__state_name', 'city__city_name', 'bh_capacity', 'tower_height',
                     'bs_switch__id', 'backhaul__name', 'bs_type', 'building_height', 'description']


    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'bs_switch__id' in dct:
                    bs_device_alias = Device.objects.get(id=dct['bs_switch__id']).device_alias
                    bs_device_ip = Device.objects.get(id=dct['bs_switch__id']).ip_address
                    dct['bs_switch__id'] = "{} ({})".format(bs_device_alias, bs_device_ip)
            except Exception as e:
                logger.info("BS Switch not present. Exception: ", e.message)

            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_basestation'):
                edit_action = '<a href="/base_station/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_basestation'):
                delete_action = '<a href="/base_station/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class BaseStationDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Base Station detail.
    """
    model = BaseStation
    template_name = 'base_station/base_station_detail.html'
    required_permissions = ('inventory.view_basestation',)


class BaseStationCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new Base Station.
    """
    template_name = 'base_station/base_station_new.html'
    model = BaseStation
    form_class = BaseStationForm
    success_url = reverse_lazy('base_stations_list')
    required_permissions = ('inventory.add_basestation',)


class BaseStationUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Base Station.
    """
    template_name = 'base_station/base_station_update.html'
    model = BaseStation
    form_class = BaseStationForm
    success_url = reverse_lazy('base_stations_list')
    required_permissions = ('inventory.change_basestation',)

    def get_queryset(self):
        return BaseStation.objects.filter(organization__in=logged_in_user_organizations(self))


class BaseStationDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Base Station.
    """
    model = BaseStation
    template_name = 'base_station/base_station_delete.html'
    success_url = reverse_lazy('base_stations_list')
    required_permissions = ('inventory.delete_basestation',)


#**************************************** Backhaul *********************************************
class SelectBackhaulListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = Backhaul


class BackhaulList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Backhaul data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'backhaul/backhauls_list.html'
    required_permissions = ('inventory.view_backhaul',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(BackhaulList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto'},
            {'mData': 'bh_configured_on__id', 'sTitle': 'Backhaul Configured On', 'sWidth': 'auto'},
            {'mData': 'bh_port', 'sTitle': 'Backhaul Port', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'bh_type', 'sTitle': 'Backhaul Type', 'sWidth': 'auto', },
            {'mData': 'pop__id', 'sTitle': 'POP', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'pop_port', 'sTitle': 'POP Port', 'sWidth': 'auto', },
            {'mData': 'bh_connectivity', 'sTitle': 'Connectivity', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'bh_circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto', },
            {'mData': 'bh_capacity', 'sTitle': 'Capacity', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            ]

        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class BackhaulListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Backhaul Data table.
    """
    model = Backhaul
    required_permissions = ('inventory.view_backhaul',)
    columns = ['alias', 'bh_configured_on__id', 'bh_port', 'bh_type', 'pop__id', 'pop_port',
               'bh_connectivity', 'bh_circuit_id', 'bh_capacity']
    order_columns = ['alias', 'bh_configured_on__id', 'bh_port', 'bh_type', 'pop__id',
                     'pop_port', 'bh_connectivity', 'bh_circuit_id', 'bh_capacity']

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'bh_configured_on__id' in dct:
                    bh_device_alias = Device.objects.get(id=dct['bh_configured_on__id']).device_alias
                    bh_device_ip = Device.objects.get(id=dct['bh_configured_on__id']).ip_address
                    dct['bh_configured_on__id'] = "{} ({})".format(bh_device_alias, bh_device_ip)
            except Exception as e:
                logger.info("Backhaul configured on not present. Exception: ", e.message)

            try:
                if 'pop__id' in dct:
                    pop_device_alias = Device.objects.get(id=dct['pop__id']).device_alias
                    pop_device_ip = Device.objects.get(id=dct['pop__id']).ip_address
                    dct['pop__id'] = "{} ({})".format(pop_device_alias, pop_device_ip)
            except Exception as e:
                logger.info("POP not present. Exception: ", e.message)

            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_backhaul'):
                edit_action = '<a href="/backhaul/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_backhaul'):
                delete_action = '<a href="/backhaul/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class BackhaulDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Backhaul detail.
    """
    model = Backhaul
    required_permissions = ('inventory.view_backhaul',)
    template_name = 'backhaul/backhaul_detail.html'


class BackhaulCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new backhaul..
    """
    template_name = 'backhaul/backhaul_new.html'
    model = Backhaul
    form_class = BackhaulForm
    success_url = reverse_lazy('backhauls_list')
    required_permissions = ('inventory.add_backhaul',)


class BackhaulUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Backhaul.
    """
    template_name = 'backhaul/backhaul_update.html'
    model = Backhaul
    form_class = BackhaulForm
    success_url = reverse_lazy('backhauls_list')
    required_permissions = ('inventory.change_backhaul',)

    def get_queryset(self):
        return Backhaul.objects.filter(organization__in=logged_in_user_organizations(self))


class BackhaulDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Backhaul.
    """
    model = Backhaul
    template_name = 'backhaul/backhaul_delete.html'
    success_url = reverse_lazy('backhauls_list')
    required_permissions = ('inventory.delete_backhaul',)


#**************************************** Sector *********************************************
class SelectSectorListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = Sector


class SectorList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Sector data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'sector/sectors_list.html'
    required_permissions = ('inventory.view_sector',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(SectorList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'sector_id', 'sTitle': 'ID', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'sector_configured_on__id', 'sTitle': 'Sector Configured On', 'sWidth': 'auto', },
            {'mData': 'sector_configured_on_port__alias', 'sTitle': 'Sector Configured On Port', 'sWidth': 'auto',
             'sClass': 'hidden-xs'},
            {'mData': 'base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'antenna__alias', 'sTitle': 'Antenna', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'mrc', 'sTitle': 'MRC', 'sWidth': 'auto', },
            {'mData': 'dr_site', 'sTitle': 'DR Site', 'sWidth': 'auto', },
            {'mData': 'dr_configured_on__id', 'sTitle': 'DR Configured On', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            ]

        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class SectorListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Sector Data Table.
    """
    model = Sector
    required_permissions = ('inventory.view_sector',)
    columns = ['alias', 'bs_technology__alias', 'sector_id', 'sector_configured_on__id', 'dr_configured_on__id', 'dr_site',
               'base_station__alias', 'sector_configured_on_port__alias', 'antenna__alias', 'mrc', 'description']
    order_columns = ['alias', 'bs_technology__alias', 'sector_id', 'sector_configured_on__id', 'dr_configured_on__id', 'dr_site',
                     'base_station__alias', 'sector_configured_on_port__alias', 'antenna__alias', 'mrc', 'description']

    def get_initial_queryset(self):
        qs = super(SectorListingTable, self).get_initial_queryset()

        if 'tab' in self.request.GET:
            if self.request.GET.get('tab') == 'corrupted':
                qs = qs.annotate(num_circuit=Count('circuit')).filter(
                        Q(sector_configured_on__isnull=True) | Q(base_station__isnull=True) | Q(bs_technology__in=[3,4], sector_id__isnull=True)
                        | Q(bs_technology__id=3 , sector_configured_on_port__isnull=True) | Q(num_circuit__gt=1))
            elif self.request.GET.get('tab') == 'unused':
                qs = qs.annotate(num_circuit=Count('circuit')).filter(num_circuit=0)

        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'sector_configured_on__id' in dct:
                    sector_device_alias = Device.objects.get(id=dct['sector_configured_on__id']).device_alias
                    sector_device_ip = Device.objects.get(id=dct['sector_configured_on__id']).ip_address
                    dct['sector_configured_on__id'] = "{} ({})".format(sector_device_alias, sector_device_ip)
            except Exception as e:
                logger.info("Sector Configured On not present. Exception: ", e.message)
            try:
                if 'dr_configured_on__id' in dct:
                    dr_device_alias = Device.objects.get(id=dct['dr_configured_on__id']).device_alias
                    dr_device_ip = Device.objects.get(id=dct['dr_configured_on__id']).ip_address
                    dct['dr_configured_on__id'] = "{} ({})".format(dr_device_alias, dr_device_ip)
            except Exception as e:
                logger.info("DR Configured On not present. Exception: ", e.message)

            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_sector'):
                edit_action = '<a href="/sector/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_sector'):
                delete_action = '<a href="/sector/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class SectorDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Sector detail.
    """
    model = Sector
    required_permissions = ('inventory.view_sector',)
    template_name = 'sector/sector_detail.html'


class SectorCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new Sector.
    """
    template_name = 'sector/sector_new.html'
    model = Sector
    form_class = SectorForm
    success_url = reverse_lazy('sectors_list')
    required_permissions = ('inventory.add_sector',)


class SectorUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Sector.
    """
    template_name = 'sector/sector_update.html'
    model = Sector
    form_class = SectorForm
    success_url = reverse_lazy('sectors_list')
    required_permissions = ('inventory.change_sector',)

    def get_queryset(self):
        return Sector.objects.filter(organization__in=logged_in_user_organizations(self))


class SectorDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Sector.
    """
    model = Sector
    template_name = 'sector/sector_delete.html'
    success_url = reverse_lazy('sectors_list')
    required_permissions = ('inventory.delete_sector',)


#**************************************** Customer *********************************************
class SelectCustomerListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = Customer


class CustomerList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Customer data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'customer/customers_list.html'
    required_permissions = ('inventory.view_customer',)

    def get_context_data(self, **kwargs):
        context = super(CustomerList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'address', 'sTitle': 'Address', 'sWidth': 'auto', 'sClass': 'hidden-xs','bSortable': False},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'bSortable': False},
            ]
        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class CustomerListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Customer Data table.
    """
    model = Customer
    required_permissions = ('inventory.view_customer',)
    columns = ['alias', 'address', 'description']
    order_columns = ['alias']

    def get_initial_queryset(self):
        qs = super(CustomerListingTable, self).get_initial_queryset()

        if 'tab' in self.request.GET and self.request.GET.get('tab') == 'unused':
            qs = qs.filter(circuit__isnull=True)

        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_customer'):
                edit_action = '<a href="/customer/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_customer'):
                delete_action = '<a href="/customer/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class CustomerDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the customer detail.
    """
    model = Customer
    required_permissions = ('inventory.view_customer',)
    template_name = 'customer/customer_detail.html'


class CustomerCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new customer.
    """
    template_name = 'customer/customer_new.html'
    model = Customer
    form_class = CustomerForm
    success_url = reverse_lazy('customers_list')
    required_permissions = ('inventory.add_customer',)


class CustomerUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Customer.
    """
    template_name = 'customer/customer_update.html'
    model = Customer
    form_class = CustomerForm
    success_url = reverse_lazy('customers_list')
    required_permissions = ('inventory.change_customer',)

    def get_queryset(self):
        return Customer.objects.filter(organization__in=logged_in_user_organizations(self))


class CustomerDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Customer.
    """
    model = Customer
    template_name = 'customer/customer_delete.html'
    success_url = reverse_lazy('customers_list')
    required_permissions = ('inventory.delete_customer',)


#**************************************** Sub Station *********************************************
class SelectSubStationListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = SubStation


class SubStationList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Sub Station data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'sub_station/sub_stations_list.html'
    required_permissions = ('inventory.view_substation',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(SubStationList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'device__id', 'sTitle': 'Device Alias', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'device__ip_address', 'sTitle': 'Device IP', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'antenna__alias', 'sTitle': 'Antenna', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'version', 'sTitle': 'Version', 'sWidth': 'auto', },
            {'mData': 'serial_no', 'sTitle': 'Serial No.', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'building_height', 'sTitle': 'Building Height', 'sWidth': 'auto', },
            {'mData': 'tower_height', 'sTitle': 'Tower Height', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'city__city_name', 'sTitle': 'City', 'sWidth': 'auto'},
            {'mData': 'state__state_name', 'sTitle': 'State', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'address', 'sTitle': 'Address', 'sWidth': 'auto', 'bSortable': False},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs','bSortable': False},
            ]

        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class SubStationListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Sub Station Data table.
    """
    model = SubStation
    required_permissions = ('inventory.view_substation',)
    columns = ['alias', 'device__id', 'device__ip_address', 'antenna__alias', 'version', 'serial_no', 'building_height',
               'tower_height', 'city__city_name', 'state__state_name', 'address', 'description']
    order_columns = ['alias', 'device__id', 'device__ip_address', 'antenna__alias', 'version', 'serial_no', 'building_height',
                     'tower_height', 'city__city_name', 'state__state_name']

    def get_initial_queryset(self):
        qs = super(SubStationListingTable, self).get_initial_queryset()

        if 'tab' in self.request.GET:
            if self.request.GET.get('tab') == 'corrupted':
                qs = qs.annotate(num_circuit=Count('circuit')).filter(Q(device__isnull=True) | Q(num_circuit__gt=1))
            elif self.request.GET.get('tab') == 'unused':
                qs = qs.annotate(num_circuit=Count('circuit')).filter(num_circuit=0)

        return qs


    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device__id' in dct:
                    ss_device_alias = Device.objects.get(id=dct['device__id']).device_alias
                    dct['device__id'] = "{}".format(ss_device_alias)
            except Exception as e:
                logger.info("Sub Station Device not present. Exception: ", e.message)

            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_substation'):
                edit_action = '<a href="/sub_station/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_substation'):
                delete_action = '<a href="/sub_station/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                dct.update(actions= edit_action+delete_action)
        return json_data


class SubStationDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Sub Station detail.
    """
    model = SubStation
    required_permissions = ('inventory.view_substation',)
    template_name = 'sub_station/sub_station_detail.html'


class SubStationCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new Sub Station.
    """
    template_name = 'sub_station/sub_station_new.html'
    model = SubStation
    form_class = SubStationForm
    success_url = reverse_lazy('sub_stations_list')
    required_permissions = ('inventory.add_substation',)


class SubStationUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update the Sub Station.
    """
    template_name = 'sub_station/sub_station_update.html'
    model = SubStation
    form_class = SubStationForm
    success_url = reverse_lazy('sub_stations_list')
    required_permissions = ('inventory.change_substation',)

    def get_queryset(self):
        return SubStation.objects.filter(organization__in=logged_in_user_organizations(self))


class SubStationDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Sub Station.
    """
    model = SubStation
    template_name = 'sub_station/sub_station_delete.html'
    success_url = reverse_lazy('sub_stations_list')
    required_permissions = ('inventory.delete_substation',)


#**************************************** Circuit *********************************************
class SelectCircuitListView(Select2Mixin, ListView):
    """
    Provide selector data for jquery select2 when loading data from Remote.
    """
    model = Circuit


class CircuitList(PermissionsRequiredMixin, TemplateView):
    """
    Class Based View for the Circuit data table rendering.

    In this view no data is passed to datatable while rendering template.
    Another ajax call is made to fill in datatable.
    """
    template_name = 'circuit/circuits_list.html'
    required_permissions = ('inventory.view_circuit',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(CircuitList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'Alias', 'sWidth': 'auto', },
            {'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto'},
            {'mData': 'sector__base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto'},
            {'mData': 'sector__alias', 'sTitle': 'Sector', 'sWidth': 'auto', },
            {'mData': 'sector__sector_configured_on__ip_address', 'sTitle': 'Sector Configured On', 'sWidth': 'auto', },
            {'mData': 'customer__alias', 'sTitle': 'Customer', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'sub_station__alias', 'sTitle': 'Sub Station', 'sWidth': 'auto', },
            {'mData': 'sub_station__device__ip_address', 'sTitle': 'Sub Station Configured On', 'sWidth': 'auto', },
            {'mData': 'date_of_acceptance', 'sTitle': 'Date of Acceptance', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto',  'sClass': 'hidden-xs'}
        ]
        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class CircuitListingTable(PermissionsRequiredMixin,
        DatatableOrganizationFilterMixin,
        DatatableSearchMixin,
        BaseDatatableView,
    ):
    """
    Class based View to render Circuit Data table.
    """
    model = Circuit
    required_permissions = ('inventory.view_circuit',)
    columns = ['alias', 'circuit_id','sector__base_station__alias', 'sector__alias',
               'sector__sector_configured_on__ip_address', 'customer__alias',
               'sub_station__alias', 'sub_station__device__ip_address', 'date_of_acceptance', 'description']
    order_columns = ['alias', 'circuit_id','sector__base_station__alias', 'sector__alias',
                     'sector__sector_configured_on__ip_address', 'customer__alias',
                     'sub_station__alias', 'sub_station__device__ip_address', 'date_of_acceptance', 'description']
    search_columns = ['alias', 'circuit_id','sector__base_station__alias', 'sector__alias',
                      'sector__sector_configured_on__ip_address', 'customer__alias',
               'sub_station__alias', 'sub_station__device__ip_address']

    def get_initial_queryset(self):
        qs = super(CircuitListingTable, self).get_initial_queryset()

        if 'tab' in self.request.GET and self.request.GET.get('tab') == 'unused':
            qs = qs.filter( Q(sub_station__isnull=True) | Q(sector__isnull=True) | Q(customer__isnull=True))

        return qs

    def prepare_results(self, qs):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            device_id = dct.pop('id')
            if self.request.user.has_perm('inventory.change_circuit'):
                edit_action = '<a href="/circuit/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>&nbsp&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_circuit'):
                delete_action = '<a href="/circuit/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>&nbsp&nbsp'.format(device_id)
            else:
                delete_action = ''
            if edit_action or delete_action:
                actions = edit_action + delete_action
            else:
                actions = ''
            actions = actions + '<a href="/circuit/{0}/l2_reports/"><i class="fa fa-sign-in text-info" title="View L2 reports for circuit"\
                            alt="View L2 reports for circuit"></i></a>'.format(device_id)
            dct.update(actions=actions, date_of_acceptance=dct['date_of_acceptance'].strftime("%Y-%m-%d") if dct['date_of_acceptance'] != "" else "")

        return json_data


class CircuitDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Circuit detail.
    """
    model = Circuit
    required_permissions = ('inventory.view_circuit',)
    template_name = 'circuit/circuit_detail.html'


class CircuitCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new Circuit.
    """

    template_name = 'circuit/circuit_new.html'
    model = Circuit
    form_class = CircuitForm
    success_url = reverse_lazy('circuits_list')
    required_permissions = ('inventory.add_circuit',)


class CircuitUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update Cicuit.
    """
    template_name = 'circuit/circuit_update.html'
    model = Circuit
    form_class = CircuitForm
    success_url = reverse_lazy('circuits_list')
    required_permissions = ('inventory.change_circuit',)

    def get_queryset(self):
        return Circuit.objects.filter(organization__in=logged_in_user_organizations(self))


class CircuitDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Circuit.
    """
    model = Circuit
    template_name = 'circuit/circuit_delete.html'
    success_url = reverse_lazy('circuits_list')
    required_permissions = ('inventory.delete_circuit',)


#********************************* Circuit L2 Reports*******************************************

class CircuitL2Report_Init(ListView):
    """
    Class Based View to render Circuit based L2 reports List Page.
    """
    model = CircuitL2Report
    template_name = 'circuit_l2/circuit_l2_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(CircuitL2Report_Init, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'name', 'sTitle': 'Name', 'sWidth': 'auto', },
            {'mData': 'file_name', 'sTitle': 'Report', 'sWidth': 'auto', },
            {'mData': 'added_on', 'sTitle': 'Uploaded On', 'sWidth': 'auto'},
            {'mData': 'user_id', 'sTitle': 'Uploaded By', 'sWidth': 'auto'},
        ]
        if not ('circuit_id' in self.kwargs):
            datatable_headers.append({'mData': 'circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto', });

        #if the user role is Admin or operator then the action column will appear on the datatable
        user_role = self.request.user.userprofile.role.values_list('role_name', flat=True)
        if 'admin' in user_role or 'operator' in user_role:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)
        if 'circuit_id' in self.kwargs:
            context['circuit_id'] = self.kwargs['circuit_id']
            context['page_type'] = 'individual'
        else:
            context['circuit_id'] = 0
            context['page_type'] = 'all'

        return context

## This class load L2 reports datatable for particular circuit_id
class L2ReportListingTable(BaseDatatableView):
    """
    Class based View to render Circuit Data table.
    """
    model = CircuitL2Report
    columns = ['name', 'file_name', 'added_on', 'user_id']
    order_columns = ['name', 'file_name', 'added_on']

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

    def get_initial_queryset(self,circuit_id):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        condition = ""

        if int(circuit_id) > 0:
            circuit_instance = Circuit.objects.filter(id=circuit_id)
            # condition to fetch l2 reports data from db
            condition = (Q(user_id=self.request.user) | Q(is_public=1)) & (Q(circuit_id=circuit_instance))
        else:
            condition = (Q(user_id=self.request.user) | Q(is_public=1))
            self.columns.append('circuit_id')

        # Query to fetch L2 reports data from db
        l2ReportsResult = CircuitL2Report.objects.filter(condition).values(*self.columns + ['id'])

        report_resultset = []
        for data in l2ReportsResult:
            report_object = {}
            report_object['name'] = data['name'].title()
            filename_str_array = data['file_name'].split('/')
            report_object['file_name'] = filename_str_array[len(filename_str_array)-1]
            report_object['file_url'] = data['file_name']
            report_object['added_on'] = data['added_on']
            username = UserProfile.objects.filter(id=data['user_id']).values('username')
            # Append Circuit Alias when all listing is shown
            if int(circuit_id) == 0:
                circuit_alias = Circuit.objects.filter(id=data['circuit_id']).values('alias')
                report_object['circuit_id'] = circuit_alias[0]['alias'].title()

            report_object['user_id'] = username[0]['username'].title()
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

        if len(qs) > 0:
            if('circuit_id' in qs[0]):
                for dct in qs:
                    dct.update(actions='<a href="../../../media/'+dct['file_url']+'" target="_blank" title="Download Report">\
                        <i class="fa fa-arrow-circle-o-down text-info"></i></a>\
                        '.format(dct.pop('id')),
                       added_on=dct['added_on'].strftime("%Y-%m-%d") if dct['added_on'] != "" else "")
            else:
                for dct in qs:
                    dct.update(actions='<a href="../../../media/'+dct['file_url']+'" target="_blank" title="Download Report">\
                        <i class="fa fa-arrow-circle-o-down text-info"></i></a>\
                        <a class="delete_l2report" style="cursor:pointer;" title="Delete Report" url="{0}/delete/">\
                        <i class="fa fa-trash-o text-danger"></i></a>\
                        '.format(dct.pop('id')),
                       added_on=dct['added_on'].strftime("%Y-%m-%d") if dct['added_on'] != "" else "")

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

        if 'circuit_id' in self.kwargs:
            ckt_id = self.kwargs['circuit_id']
        else:
            ckt_id = 0

        qs = self.get_initial_queryset(ckt_id)

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

## This class load all L2 reports datatable
class AllL2ReportListingTable(BaseDatatableView):
    """
    Class based View to render Circuit Data table.
    """
    model = CircuitL2Report
    columns = ['name', 'file_name', 'added_on', 'user_id']
    order_columns = ['name', 'file_name', 'added_on']

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

    def get_initial_queryset(self,circuit_id):
        """
        Preparing  Initial Queryset for the for rendering the data table.
        """
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")

        # condition to fetch l2 reports data from db
        condition = (Q(user_id=self.request.user) | Q(is_public=1))
        # Query to fetch L2 reports data from db
        l2ReportsResult = CircuitL2Report.objects.filter(condition).values(*self.columns + ['id'])

        report_resultset = []
        for data in l2ReportsResult:
            report_object = {}
            report_object['name'] = data['name'].title()
            filename_str_array = data['file_name'].split('/')
            report_object['file_name'] = filename_str_array[len(filename_str_array)-1]
            report_object['file_url'] = data['file_name']
            report_object['added_on'] = data['added_on']
            username = UserProfile.objects.filter(id=data['user_id']).values('username')
            report_object['user_id'] = username[0]['username'].title()
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

        ckt_id = self.kwargs['circuit_id']

        qs = self.get_initial_queryset(ckt_id)

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

class CircuitL2ReportCreate(CreateView):
    """
    Class based view to create new Circuit.
    """

    template_name = 'circuit_l2/circuit_l2_new.html'
    model = CircuitL2Report
    form_class = CircuitL2ReportForm

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        self.object = form.save(commit=False)
        self.object.user_id =  UserProfile.objects.get(id=self.request.user.id)
        self.object.circuit_id =  Circuit.objects.get(id=self.kwargs['circuit_id'])

        self.object.save()
        return HttpResponseRedirect(reverse_lazy('circuit_l2_report', kwargs = {'circuit_id' : self.kwargs['circuit_id']}))

class CircuitL2ReportDelete(DeleteView):

    def dispatch(self, *args, **kwargs):
        """
        The request dispatch method restricted with the permissions.
        """
        return super(CircuitL2ReportDelete, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        report_id = self.kwargs['l2_id']
        file_name = lambda x: MEDIA_ROOT + x
        # l2 report object
        l2_obj = CircuitL2Report.objects.filter(id=report_id).values()

        # remove original file if it exists
        try:
            os.remove(file_name(l2_obj[0]['file_name']))
        except Exception as e:
            logger.info(e.message)

        # delete entry from database
        CircuitL2Report.objects.filter(id=report_id).delete()
        return HttpResponseRedirect(reverse_lazy('circuit_l2_report', kwargs = {'circuit_id' : self.kwargs['circuit_id']}))

#**************************************** IconSettings *********************************************
class IconSettingsList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render IconSettings List Page.
    """
    model = IconSettings
    template_name = 'icon_settings/icon_settings_list.html'
    required_permissions = ('inventory.view_iconsettings',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(IconSettingsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',            'sTitle': 'Alias',              'sWidth': 'auto'},
            {'mData': 'upload_image',     'sTitle': 'Image',       'sWidth': 'auto'},
            ]
        #if the user is superuser action column can be appeared in datatable.
        if self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', })

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class IconSettingsListingTable(PermissionsRequiredMixin, DatatableSearchMixin, ValuesQuerySetMixin, BaseDatatableView):
    """
    Class based View to render IconSettings Data table.
    """
    model = IconSettings
    required_permissions = ('inventory.view_iconsettings',)
    columns = ['alias', 'upload_image']
    order_columns = ['alias', 'upload_image']

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            try:
                img_url = "/media/"+ (dct['upload_image']) if \
                    "uploaded" in dct['upload_image'] \
                    else static("img/" + dct['upload_image'])
                dct.update(upload_image='<img src="{0}" style="float:left; display:block; height:25px; width:25px;">'.format(img_url))
            except Exception as e:
                logger.info(e)

            dct.update(actions='<a href="/icon_settings/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/icon_settings/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return json_data


class IconSettingsDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the IconSettings detail.
    """
    model = IconSettings
    required_permissions = ('inventory.view_iconsettings',)
    template_name = 'icon_settings/icon_settings_detail.html'


class IconSettingsCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new IconSettings.
    """
    template_name = 'icon_settings/icon_settings_new.html'
    model = IconSettings
    form_class = IconSettingsForm
    success_url = reverse_lazy('icon_settings_list')
    required_permissions = ('inventory.add_iconsettings',)


class IconSettingsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update IconSettings.
    """
    template_name = 'icon_settings/icon_settings_update.html'
    model = IconSettings
    form_class = IconSettingsForm
    success_url = reverse_lazy('icon_settings_list')
    required_permissions = ('inventory.change_iconsettings',)


class IconSettingsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the machine
    """
    model = IconSettings
    template_name = 'icon_settings/icon_settings_delete.html'
    success_url = reverse_lazy('icon_settings_list')
    required_permissions = ('inventory.delete_iconsettings',)


#**************************************** LivePollingSettings *********************************************
class LivePollingSettingsList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render LivePollingSettings List Page.
    """
    model = LivePollingSettings
    template_name = 'live_polling_settings/live_polling_settings_list.html'
    required_permissions = ('inventory.view_livepollingsettings',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(LivePollingSettingsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',                   'sTitle': 'Alias',             'sWidth': 'auto'},
            {'mData': 'technology__alias',       'sTitle': 'Technology',        'sWidth': 'auto'},
            {'mData': 'service__alias',          'sTitle': 'Service',           'sWidth': 'auto'},
            {'mData': 'data_source__alias',      'sTitle': 'Data Source',       'sWidth': 'auto'},
            ]
        user_id = self.request.user.id
        #if user is superadmin or gisadmin
        if user_id in [1,2]:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', })

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class LivePollingSettingsListingTable(PermissionsRequiredMixin,
        ValuesQuerySetMixin,
        DatatableSearchMixin,
        BaseDatatableView
    ):
    """
    Class based View to render LivePollingSettings Data table.
    """
    model = LivePollingSettings
    required_permissions = ('inventory.view_livepollingsettings',)
    columns = ['alias', 'technology__alias', 'service__alias', 'data_source__alias']
    order_columns = ['alias', 'technology__alias', 'service__alias', 'data_source__alias']

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            dct.update(actions='<a href="/live_polling_settings/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/live_polling_settings/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return json_data


class LivePollingSettingsDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the LivePollingSettings detail.
    """
    model = LivePollingSettings
    required_permissions = ('inventory.view_livepollingsettings',)
    template_name = 'live_polling_settings/live_polling_settings_detail.html'


class LivePollingSettingsCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new LivePollingSettings.
    """
    template_name = 'live_polling_settings/live_polling_settings_new.html'
    model = LivePollingSettings
    form_class = LivePollingSettingsForm
    success_url = reverse_lazy('live_polling_settings_list')
    required_permissions = ('inventory.add_livepollingsettings',)


class LivePollingSettingsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update LivePollingSettings.
    """
    template_name = 'live_polling_settings/live_polling_settings_update.html'
    model = LivePollingSettings
    form_class = LivePollingSettingsForm
    success_url = reverse_lazy('live_polling_settings_list')
    required_permissions = ('inventory.change_livepollingsettings',)


class LivePollingSettingsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the LivePollingSettings
    """
    model = LivePollingSettings
    template_name = 'live_polling_settings/live_polling_settings_delete.html'
    success_url = reverse_lazy('live_polling_settings_list')
    required_permissions = ('inventory.delete_livepollingsettings',)


# **************************************** ThresholdConfiguration *********************************************
class ThresholdConfigurationList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render ThresholdConfiguration List Page.
    """
    model = ThresholdConfiguration
    template_name = 'threshold_configuration/threshold_configuration_list.html'
    required_permissions = ('inventory.view_thresholdconfiguration',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(ThresholdConfigurationList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',                          'sTitle': 'Alias',                  'sWidth': 'auto'},
            {'mData': 'live_polling_template__alias',   'sTitle': 'Live Polling Template',  'sWidth': 'auto'},
            ]
        user_id = self.request.user.id
        # if user is superadmin or gisadmin
        if self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', })

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class ThresholdConfigurationListingTable(PermissionsRequiredMixin, DatatableSearchMixin, ValuesQuerySetMixin, BaseDatatableView):
    """
    Class based View to render ThresholdConfiguration Data table.
    """
    model = ThresholdConfiguration
    required_permissions = ('inventory.view_thresholdconfiguration',)
    columns = ['alias', 'live_polling_template__alias']
    order_columns = ['alias', 'live_polling_template__alias']
    tab_search = {
                   "tab_kwarg": 'technology',
                   "tab_attr": "live_polling_template__technology__name",
                 }

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            dct.update(actions='<a href="/threshold_configuration/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/threshold_configuration/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return json_data


class ThresholdConfigurationDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Threshold Configuration detail.
    """
    model = ThresholdConfiguration
    required_permissions = ('inventory.view_thresholdconfiguration',)
    template_name = 'threshold_configuration/threshold_configuration_detail.html'


class ThresholdConfigurationCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new Threshold Configuration.
    """
    template_name = 'threshold_configuration/threshold_configuration_new.html'
    model = ThresholdConfiguration
    form_class = ThresholdConfigurationForm
    success_url = reverse_lazy('threshold_configuration_list')
    required_permissions = ('inventory.add_threshold_configuration',)


class ThresholdConfigurationUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update Threshold Configuration.
    """
    template_name = 'threshold_configuration/threshold_configuration_update.html'
    model = ThresholdConfiguration
    form_class = ThresholdConfigurationForm
    success_url = reverse_lazy('threshold_configuration_list')
    required_permissions = ('inventory.change_threshold_configuration',)


class ThresholdConfigurationDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Threshold Configuration.
    """
    model = ThresholdConfiguration
    template_name = 'threshold_configuration/threshold_configuration_delete.html'
    success_url = reverse_lazy('threshold_configuration_list')
    required_permissions = ('inventory.delete_threshold_configuration',)


#**************************************** ThematicSettings *********************************************
class ThematicSettingsList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render ThematicSettings List Page.
    """
    model = ThematicSettings
    template_name = 'thematic_settings/thematic_settings_list.html'
    required_permissions = ('inventory.view_thematicsettings',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(ThematicSettingsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',                   'sTitle': 'Alias',                     'sWidth': 'auto'},
            {'mData': 'threshold_template',      'sTitle': 'Threshold Template',        'sWidth': 'auto'},
            {'mData': 'icon_settings',           'sTitle': 'Icons Range',               'sWidth': 'auto',     'bSortable': False},
            {'mData': 'user_selection',          'sTitle': 'Setting Selection',         'sWidth': 'auto',     'bSortable': False},]

        # user_id = self.request.user.id

        #if user is superadmin or gisadmin
        if self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)

        is_global = False
        if 'admin' in self.request.path:
            is_global = True

        context['is_global'] = json.dumps(is_global)

        return context


class ThematicSettingsListingTable(PermissionsRequiredMixin, ValuesQuerySetMixin, DatatableSearchMixin, BaseDatatableView):
    """
    Class based View to render Thematic Settings Data table.
    """
    model = ThematicSettings
    required_permissions = ('inventory.view_thematicsettings',)
    columns = ['alias', 'threshold_template', 'icon_settings']
    order_columns = ['alias', 'threshold_template']
    search_columns = ['alias', 'icon_settings']

    tab_search = {
        "tab_kwarg": 'technology',
        "tab_attr": "threshold_template__live_polling_template__technology__name",
    }

    def get_initial_queryset(self):
        is_global = 1
        if self.request.GET.get('admin'):
            is_global = 0

        qs = super(ThematicSettingsListingTable, self).get_initial_queryset()

        return qs.filter(is_global=is_global)

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            threshold_config = ThresholdConfiguration.objects.get(id=int(dct['threshold_template']))
            image_string, range_text, full_string='','',''
            if dct['icon_settings'] and dct['icon_settings'] !='NULL':
                ###@nishant-teatrix. PLEASE SHOW THE RANGE MIN < ICON < RANGE MAX
                for d in eval(dct['icon_settings']):
                    img_url = str("/media/"+ (d.values()[0]) if "uploaded" in d.values()[0] else static("img/" + d.values()[0]))
                    image_string= '<img src="{0}" style="height:25px; width:25px">'.format(img_url.strip())
                    range_id_groups = re.match(r'[a-zA-Z_]+(\d+)', d.keys()[0])
                    if range_id_groups:
                        range_id = range_id_groups.groups()[-1]
                        range_text= ' Range '+ range_id +', '
                        range_start = 'range' + range_id +'_start'
                        range_end = 'range' + range_id +'_end'
                        range_start_value = getattr(threshold_config, range_start)
                        range_end_value = getattr(threshold_config, range_end)
                    else:
                        range_text = ''
                        range_start_value = ''
                        range_end_value = ''

                    full_string += image_string + range_text + "(" + range_start_value + ", " + range_end_value + ")" + "</br>"
            else:
                full_string='N/A'
            user_current_thematic_setting= self.request.user.id in ThematicSettings.objects.get(id=dct['id']).user_profile.values_list('id', flat=True)
            checkbox_checked_true='checked' if user_current_thematic_setting else ''
            dct.update(
                threshold_template=threshold_config.name,
                icon_settings= full_string,
                user_selection='<input type="checkbox" class="check_class" '+ checkbox_checked_true +' name="setting_selection" value={0}><br>'.format(dct['id']),
                actions='<a href="/thematic_settings/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/thematic_settings/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return json_data


class ThematicSettingsDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Thematic Settings detail.
    """
    model = ThematicSettings
    required_permissions = ('inventory.view_thematicsettings',)
    template_name = 'thematic_settings/thematic_settings_detail.html'


class ThematicSettingsCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new ThematicSettings.
    """
    template_name = 'thematic_settings/thematic_settings_new.html'
    model = ThematicSettings
    form_class = ThematicSettingsForm
    success_url = reverse_lazy('thematic_settings_list')
    required_permissions = ('inventory.add_thematicsettings',)

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        icon_settings_keys= list(set(form.data.keys())-set(form.cleaned_data.keys()+['csrfmiddlewaretoken']))
        icon_settings_values_list=[ { key: form.data[key] }  for key in icon_settings_keys if form.data[key]]
        self.object = form.save()
        self.object.icon_settings=icon_settings_values_list
        self.object.save()
        return HttpResponseRedirect(ThematicSettingsCreate.success_url)


class ThematicSettingsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update Thematic Settings.
    """
    template_name = 'thematic_settings/thematic_settings_update.html'
    model = ThematicSettings
    form_class = ThematicSettingsForm
    success_url = reverse_lazy('thematic_settings_list')
    required_permissions = ('inventory.change_thematicsettings',)

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        icon_settings_keys= list(set(form.data.keys())-set(form.cleaned_data.keys()+['csrfmiddlewaretoken']))
        icon_settings_values_list=[ { key: form.data[key] }  for key in icon_settings_keys if form.data[key]]
        self.object = form.save()
        self.object.icon_settings=icon_settings_values_list
        self.object.save()
        # self.object = form.save()
        return HttpResponseRedirect(ThematicSettingsUpdate.success_url)


class ThematicSettingsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Thematic Settings.
    """
    model = ThematicSettings
    template_name = 'thematic_settings/thematic_settings_delete.html'
    success_url = reverse_lazy('thematic_settings_list')
    required_permissions = ('inventory.delete_thematicsettings',)


class Get_Threshold_Ranges_And_Icon_For_Thematic_Settings(View):
    """
    The Class Based View to Response the Ajax call on click to return the respective
    ranges for the  threshold_template_id selected in the template.
    """

    def get(self, request):

        self.result = {
            "success": 0,
            "message": "Threshold range not fetched.",
            "data": {
                "meta": None,
                "objects": {}
            }
        }

        threshold_template_id= self.request.GET.get('threshold_template_id','')
        thematic_setting_name= self.request.GET.get('thematic_setting_name','')
        if threshold_template_id:
           threshold_configuration_selected=ThresholdConfiguration.objects.get(id=int(threshold_template_id))
           self.get_all_ranges(threshold_configuration_selected)
           if self.result['data']['objects']['range_list']:
              self.get_icon_details()
              self.result['success']=1


        if thematic_setting_name:
            thematic_setting_object= ThematicSettings.objects.get(name=thematic_setting_name)
            thematic_icon_setting= thematic_setting_object.icon_settings
            thematic_icon_setting= '[]' if thematic_icon_setting =='NULL' or thematic_icon_setting =='' else thematic_icon_setting
            thematic_icon_setting= eval(thematic_icon_setting)
            if thematic_icon_setting:
               icon_details, icon_details_selected=list(), dict()

               for icon_setting in thematic_icon_setting:
                   # range_list.append('Range ' + icon_setting.keys()[0][-1])
                   icon_details_selected['Range ' + icon_setting.keys()[0][-1]] = icon_setting.values()[0]

               # self.result['data']['objects']['range_list'] = range_list
               self.result['data']['objects']['icon_details_selected'] = icon_details_selected
               # self.get_icon_details()
               # self.result['success']=1

        return HttpResponse(json.dumps(self.result))

    def get_all_ranges(self, threshold_configuration_object):
        range_list=list()
        for ran in range(1, 11):

            range_start= None

            query= "range_start= threshold_configuration_object.range{0}_{1}".format(ran, 'start')
            exec query
            if range_start:
               range_list.append('Range {0}'.format(ran))

        self.result['data']['objects']['range_list'] = range_list

    def get_icon_details(self):
        icon_details= IconSettings.objects.all().values('id','name', 'upload_image')
        self.result['data']['objects']['icon_details'] =list(icon_details)


class Update_User_Thematic_Setting(View):
    """
    The Class Based View to Response the Ajax call on click to bind the user with the thematic setting.
    """
    def get(self, request):
        self.result = {
            "success": 0,
            "message": "Thematic Setting Not Bind to User",
            "data": {
                "meta": None,
                "objects": {}
            }
        }

        thematic_setting_id= self.request.GET.get('threshold_template_id',None)
        user_profile_id = self.request.user.id
        if thematic_setting_id:


            ts_obj = ThematicSettings.objects.get(id= int(thematic_setting_id))
            user_obj = UserProfile.objects.get(id= user_profile_id)
            tech_obj = ts_obj.threshold_template.live_polling_template.technology

            to_delete = UserThematicSettings.objects.filter(user_profile=user_obj, thematic_technology=tech_obj)
            if len(to_delete):
                to_delete.delete()

            uts = UserThematicSettings(user_profile= user_obj,
                                       thematic_template=ts_obj,
                                       thematic_technology=tech_obj
            )
            uts.save()
            self.result['success']=1
            self.result['message']='Service Thematic Setting Bind to User Successfully'
            self.result['data']['objects']['username']=self.request.user.userprofile.username
            self.result['data']['objects']['thematic_setting_name']= ThematicSettings.objects.get(id=int(thematic_setting_id)).name

        return HttpResponse(json.dumps(self.result))

#************************************ Service Thematic Settings ******************************************
class ServiceThematicSettingsList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render ServiceThematicSettings List Page.
    """
    model = ThematicSettings
    template_name = 'service_thematic_settings/service_thematic_settings_list.html'
    required_permissions = ('inventory.view_thematicsettings',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(ServiceThematicSettingsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',                   'sTitle': 'Alias',                     'sWidth': 'auto'},
            {'mData': 'threshold_template',      'sTitle': 'Threshold Template',        'sWidth': 'auto'},
            {'mData': 'icon_settings',           'sTitle': 'Icons Range',               'sWidth': 'auto',   'bSortable': False},
            {'mData': 'user_selection',          'sTitle': 'Setting Selection',         'sWidth': 'auto',   'bSortable': False},]

        # user_id = self.request.user.id

        #if user is superadmin or gisadmin
        if self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False})

        context['datatable_headers'] = json.dumps(datatable_headers)

        is_global = False
        is_admin = False
        if 'admin' in self.request.path:
            is_global = True
            is_admin = True

        context['is_global'] = json.dumps(is_global)
        context['is_admin'] = is_admin

        return context


class ServiceThematicSettingsListingTable(PermissionsRequiredMixin, ValuesQuerySetMixin, DatatableSearchMixin, BaseDatatableView):
    """
    Class based View to render Thematic Settings Data table.
    """
    model = ThematicSettings
    required_permissions = ('inventory.view_thematicsettings',)
    columns = ['alias', 'threshold_template', 'icon_settings']
    order_columns = ['alias', 'threshold_template']
    search_columns = ['alias', 'icon_settings']

    tab_search = {
        "tab_kwarg": 'technology',
        "tab_attr": "threshold_template__live_polling_template__technology__name",
    }

    def get_initial_queryset(self):
        is_global = 1
        if self.request.GET.get('admin'):
            is_global = 0

        qs = super(ServiceThematicSettingsListingTable, self).get_initial_queryset()

        return qs.filter(is_global=is_global)

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            obj_id = dct.pop('id')
            if self.request.GET.get('admin'):
                actions='<a href="/serv_thematic_settings/admin/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/serv_thematic_settings/admin/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(obj_id)
            else:
                actions='<a href="/serv_thematic_settings/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/serv_thematic_settings/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(obj_id)
            threshold_config = ThresholdConfiguration.objects.get(id=int(dct['threshold_template']))
            image_string, range_text, full_string='','',''
            if dct['icon_settings'] and dct['icon_settings'] !='NULL':
                ###@nishant-teatrix. PLEASE SHOW THE RANGE MIN < ICON < RANGE MAX
                for d in eval(dct['icon_settings']):
                    img_url = str("/media/"+ (d.values()[0]) if "uploaded" in d.values()[0] else static("img/" + d.values()[0]))
                    image_string= '<img src="{0}" style="height:25px; width:25px">'.format(img_url.strip())
                    range_id_groups = re.match(r'[a-zA-Z_]+(\d+)', d.keys()[0])
                    if range_id_groups:
                        range_id = range_id_groups.groups()[-1]
                        range_text= ' Range '+ range_id +', '
                        range_start = 'range' + range_id +'_start'
                        range_end = 'range' + range_id +'_end'
                        range_start_value = getattr(threshold_config, range_start)
                        range_end_value = getattr(threshold_config, range_end)
                    else:
                        range_text = ''
                        range_start_value = ''
                        range_end_value = ''

                    full_string += image_string + range_text + "(" + range_start_value + ", " + range_end_value + ")" + "</br>"
            else:
                full_string='N/A'
            user_current_thematic_setting= self.request.user.id in ThematicSettings.objects.get(id=obj_id).user_profile.values_list('id', flat=True)
            checkbox_checked_true='checked' if user_current_thematic_setting else ''
            dct.update(
                threshold_template=threshold_config.alias,
                icon_settings= full_string,
                user_selection='<input type="checkbox" class="check_class" '+ checkbox_checked_true +' name="setting_selection" value={0}><br>'.format(obj_id),
                actions=actions)
        return json_data


class ServiceThematicSettingsDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the Service Thematic Settings detail.
    """
    model = ThematicSettings
    required_permissions = ('inventory.view_thematicsettings',)
    template_name = 'service_thematic_settings/service_thematic_settings_detail.html'


class ServiceThematicSettingsCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new ServiceThematicSettings.
    """
    template_name = 'service_thematic_settings/service_thematic_settings_new.html'
    model = ThematicSettings
    form_class = ThematicSettingsForm
    success_url = reverse_lazy('service_thematic_settings_list')
    required_permissions = ('inventory.add_thematicsettings',)
    icon_settings_keys = ( 'icon_settings1', 'icon_settings2', 'icon_settings3', 'icon_settings4', 'icon_settings5',
                           'icon_settings6', 'icon_settings7', 'icon_settings8', 'icon_settings9', 'icon_settings10'
            )

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates blank versions of the form
        and its inline formsets.
        """
        self.object = None
        is_admin = False
        form_class = self.get_form_class()
        form = ServiceThematicSettingsForm()
        icon_settings = IconSettings.objects.all()
        threshold_configuration_form = ServiceThresholdConfigurationForm()
        live_polling_settings_form = ServiceLivePollingSettingsForm()
        if 'admin' in self.request.path:
            is_admin = True
        return self.render_to_response(
            self.get_context_data(form=form,
                                  threshold_configuration_form=threshold_configuration_form,
                                  live_polling_settings_form=live_polling_settings_form,
                                  icon_settings=icon_settings,
                                  is_admin=is_admin))

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance and its inline
        formsets with the passed POST variables and then checking them for
        validity.
        """
        self.object = None
        form_class = self.get_form_class()
        form = ServiceThematicSettingsForm(self.request.POST)
        threshold_configuration_form = ServiceThresholdConfigurationForm(self.request.POST)
        live_polling_settings_form = ServiceLivePollingSettingsForm(self.request.POST)
        if (form.is_valid() and threshold_configuration_form.is_valid() and live_polling_settings_form.is_valid()):
            return self.form_valid(form, threshold_configuration_form, live_polling_settings_form)
        else:
            return self.form_invalid(form, threshold_configuration_form, live_polling_settings_form)

    def form_valid(self, form, threshold_configuration_form, live_polling_settings_form):
        """
        Called if all forms are valid. Creates a ThematicSettings, LivePollingSettings and IconSettings.
        """
        name = form.instance.name
        alias = form.instance.alias
        live_polling_settings_form.instance.name = name
        live_polling_settings_form.instance.alias = alias
        live_polling_object = live_polling_settings_form.save()
        threshold_configuration_form.instance.name = name
        threshold_configuration_form.instance.alias = alias
        threshold_configuration_form.instance.live_polling_template = live_polling_object
        threshold_configuration_object = threshold_configuration_form.save()
        form.instance.threshold_template = threshold_configuration_object
        icon_settings_values_list = [ { key: form.data[key] }  for key in self.icon_settings_keys if form.data[key]]
        form.instance.icon_settings = icon_settings_values_list
        self.object = form.save()

        if 'admin' in self.request.path:
            return HttpResponseRedirect(reverse_lazy('service-admin-thematic-settings-list'))

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, threshold_configuration_form, live_polling_settings_form):
        """
        Called if a form is invalid. Re-renders the context data with the
        data-filled forms and errors.
        """
        icon_settings = IconSettings.objects.all()
        is_admin = False
        icon_details_selected = dict()
        if 'admin' in self.request.path:
            is_admin = True
        icon_settings_values_list = [ { key: form.data[key] }  for key in self.icon_settings_keys if form.data[key]]
        for icon_setting in icon_settings_values_list:
            icon_details_selected['range_' + icon_setting.keys()[0][-1]] = icon_setting.values()[0]
        return self.render_to_response(
            self.get_context_data(form=form,
                                  threshold_configuration_form=threshold_configuration_form,
                                  live_polling_settings_form=live_polling_settings_form,
                                  icon_settings=icon_settings,
                                  icon_details_selected=icon_details_selected,
                                  is_admin=is_admin))


class ServiceThematicSettingsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update Service Thematic Settings.
    """
    template_name = 'service_thematic_settings/service_thematic_settings_update.html'
    model = ThematicSettings
    form_class = ServiceThematicSettingsForm
    success_url = reverse_lazy('service_thematic_settings_list')
    required_permissions = ('inventory.change_thematicsettings',)
    icon_settings_keys = ( 'icon_settings1', 'icon_settings2', 'icon_settings3', 'icon_settings4', 'icon_settings5',
                           'icon_settings6', 'icon_settings7', 'icon_settings8', 'icon_settings9', 'icon_settings10'
            )

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates blank versions of the form
        and its inline formsets.
        """
        self.object = self.get_object()
        is_admin = False
        form_class = self.get_form_class()
        form = ServiceThematicSettingsForm(instance=self.object)
        icon_settings = IconSettings.objects.all()
        threshold_configuration_form = ServiceThresholdConfigurationForm(instance=self.object.threshold_template)
        icon_details = list()
        icon_details_selected = dict()
        if 'admin' in self.request.path:
            is_admin = True
        if form.instance.icon_settings!='NULL':
            form.instance.icon_settings
            form.instance.icon_settings = eval(form.instance.icon_settings)
            for icon_setting in form.instance.icon_settings:
                icon_details_selected['range_' + icon_setting.keys()[0][-1]] = icon_setting.values()[0]
        live_polling_settings_form = ServiceLivePollingSettingsForm(instance=self.object.threshold_template.live_polling_template)
        return self.render_to_response(
            self.get_context_data(form=form,
                                  threshold_configuration_form=threshold_configuration_form,
                                  live_polling_settings_form=live_polling_settings_form,
                                  icon_settings=icon_settings,
                                  icon_details_selected=icon_details_selected,
                                  is_admin=is_admin))

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance and its inline
        formsets with the passed POST variables and then checking them for
        validity.
        """
        self.object = self.get_object()
        form_class = self.get_form_class()
        form = ServiceThematicSettingsForm(self.request.POST, instance=self.object)
        threshold_configuration_form = ServiceThresholdConfigurationForm(self.request.POST, instance=self.object.threshold_template)
        live_polling_settings_form = ServiceLivePollingSettingsForm(self.request.POST, instance=self.object.threshold_template.live_polling_template)
        if (form.is_valid() and threshold_configuration_form.is_valid() and live_polling_settings_form.is_valid()):
            return self.form_valid(form, threshold_configuration_form, live_polling_settings_form)
        else:
            return self.form_invalid(form, threshold_configuration_form, live_polling_settings_form)

    def form_valid(self, form, threshold_configuration_form, live_polling_settings_form):
        """
        Called if all forms are valid. Updates ThematicSettings, LivePollingSettings and IconSettings.
        """
        self.object = self.get_object()
        name = form.instance.name
        alias = form.instance.alias
        icon_settings_values_list = [ { key: form.data[key] }  for key in self.icon_settings_keys if form.data[key]]
        form.instance.icon_settings = icon_settings_values_list
        form.save()
        threshold_configuration_form.instance.name = name
        threshold_configuration_form.instance.alias = alias
        threshold_configuration_form.save()
        live_polling_settings_form.instance.name = name
        live_polling_settings_form.instance.alias = alias
        live_polling_settings_form.save()
        if 'admin' in self.request.path:
            return HttpResponseRedirect(reverse_lazy('service-admin-thematic-settings-list'))
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, threshold_configuration_form, live_polling_settings_form):
        """
        Called if a form is invalid. Re-renders the context data with the
        data-filled forms and errors.
        """
        icon_settings = IconSettings.objects.all()
        is_admin = False
        icon_details = list()
        if 'admin' in self.request.path:
            is_admin = True
        icon_details_selected = dict()
        if form.instance.icon_settings!='NULL':
            form.instance.icon_settings = eval(form.instance.icon_settings)
            for icon_setting in form.instance.icon_settings:
                icon_details_selected['range_' + icon_setting.keys()[0][-1]] = icon_setting.values()[0]
        return self.render_to_response(
            self.get_context_data(form=form,
                                  threshold_configuration_form=threshold_configuration_form,
                                  live_polling_settings_form=live_polling_settings_form,
                                  icon_settings=icon_settings,
                                  icon_details_selected=icon_details_selected,
                                  is_admin=is_admin))


class ServiceThematicSettingsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Thematic Settings.
    """
    model = ThematicSettings
    template_name = 'service_thematic_settings/service_thematic_settings_delete.html'
    success_url = reverse_lazy('service_thematic_settings_list')
    required_permissions = ('inventory.delete_thematicsettings',)

    def delete(self, request, *args, **kwargs):
        """
        Calls the delete() method on the fetched object and then
        redirects to the success URL.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.threshold_template.live_polling_template.delete()
        if 'admin' in self.request.path:
            return HttpResponseRedirect(reverse_lazy('service-admin-thematic-settings-list'))
        return HttpResponseRedirect(success_url)


# ************************************ GIS Inventory Bulk Upload ******************************************
class GISInventoryBulkImportView(FormView):
    template_name = 'bulk_import/gis_bulk_import.html'
    success_url = '/bulk_import/'
    form_class = GISInventoryBulkImportForm

    def form_valid(self, form):
        # get uploaded file
        uploaded_file = self.request.FILES['file_upload']
        description = self.request.POST['description']
        timestamp = time.time()
        full_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d-%H-%M-%S')

        # if directory for uploaded excel sheets didn't exist than create one
        if not os.path.exists(MEDIA_ROOT + 'inventory_files/original'):
            os.makedirs(MEDIA_ROOT + 'inventory_files/original')

        filepath = MEDIA_ROOT + 'inventory_files/original/{}_{}'.format(full_time, uploaded_file.name)
        relative_filepath = 'inventory_files/original/{}_{}'.format(full_time, uploaded_file.name)
        # used in checking headers of excel sheet
        # dictionary containing all 'pts bs' fields
        ptp_bs_fields = ['City', 'State', 'Circuit ID', 'Circuit Type', 'Customer Name', 'BS Address', 'BS Name',
                         'QOS (BW)', 'Latitude', 'Longitude', 'Antenna Height', 'Polarization', 'Antenna Type',
                         'Antenna Gain', 'Antenna Mount Type', 'Ethernet Extender', 'Building Height',
                         'Tower/Pole Height', 'Cable Length', 'RSSI During Acceptance',
                         'Throughput During Acceptance', 'Date Of Acceptance', 'BH BSO', 'IP', 'MAC', 'HSSU Used',
                         'BS Switch IP', 'Aggregation Switch', 'Aggregation Switch Port', 'BS Converter IP',
                         'POP Converter IP', 'Converter Type', 'BH Configured On Switch/Converter',
                         'Switch/Converter Port', 'BH Capacity', 'BH Offnet/Onnet', 'Backhaul Type',
                         'BH Circuit ID', 'PE Hostname', 'PE IP', 'BSO Circuit ID', 'Site ID', 'HSSU Port']

        # dictionary containing all 'pmp bs' fields
        pmp_bs_fields = ['City', 'State', 'Address', 'BS Name', 'Type Of BS (Technology)', 'Site Type',
                         'Infra Provider', 'Site ID', 'Building Height', 'Tower Height', 'Latitude', 'Longitude',
                         'ODU IP', 'Sector Name', 'Make Of Antenna', 'Polarization', 'Antenna Tilt',
                         'Antenna Height', 'Antenna Beamwidth', 'Azimuth', 'Sync Splitter Used',
                         'Type Of GPS', 'BS Switch IP', 'Aggregation Switch', 'Aggregation Switch Port',
                         'BS Converter IP', 'POP Converter IP', 'Converter Type', 'BH Configured On Switch/Converter',
                         'Switch/Converter Port', 'BH Capacity', 'BH Offnet/Onnet', 'Backhaul Type', 'BH Circuit ID',
                         'PE Hostname', 'PE IP', 'DR Site', 'BSO Circuit ID']

        # dictionary containing all 'wimax bs' fields
        wimax_bs_fields = ['City', 'State', 'Address', 'BS Name', 'Type Of BS (Technology)', 'Site Type',
                           'Infra Provider', 'Site ID', 'Building Height', 'Tower Height', 'Latitude', 'Longitude',
                           'IDU IP', 'Sector Name', 'PMP', 'Make Of Antenna', 'Polarization', 'Antenna Tilt',
                           'Antenna Height', 'Antenna Beamwidth', 'Azimuth', 'Installation Of Splitter',
                           'Type Of GPS', 'BS Switch IP', 'Aggregation Switch', 'Aggregation Switch Port',
                           'BS Converter IP', 'POP Converter IP', 'Converter Type', 'BH Configured On Switch/Converter',
                           'Switch/Converter Port', 'BH Capacity', 'BH Offnet/Onnet', 'Backhaul Type', 'BH Circuit ID',
                           'PE Hostname', 'PE IP', 'DR Site', 'BSO Circuit ID']

        # dictionary containing all 'ptp ss' fields
        ptp_ss_fields = ['SS City', 'SS State', 'SS Circuit ID', 'SS Customer Name', 'SS Customer Address',
                         'SS BS Name', 'SS QOS (BW)', 'SS Latitude', 'SS Longitude', 'SS MIMO/Diversity',
                         'SS Antenna Height', 'SS Polarization', 'SS Antenna Type', 'SS Antenna Gain',
                         'SS Antenna Mount Type', 'SS Ethernet Extender', 'SS Building Height', 'SS Tower/Pole Height',
                         'SS Cable Length', 'SS RSSI During Acceptance', 'SS Throughput During Acceptance',
                         'SS Date Of Acceptance', 'SS BH BSO', 'SS IP', 'SS MAC']

        # dictionary containing all 'pmp ss' fields
        pmp_ss_fields = ['Customer Name', 'Circuit ID', 'QOS (BW)', 'Latitude', 'Longitude', 'Building Height',
                         'Tower/Pole Height', 'Antenna Height', 'Polarization', 'Antenna Type', 'SS Mount Type',
                         'Ethernet Extender', 'Cable Length', 'RSSI During Acceptance', 'CINR During Acceptance',
                         'Customer Address', 'Date Of Acceptance', 'SS IP', 'Lens/Reflector', 'Antenna Beamwidth']

        # dictionary containing all 'wimax ss' fields
        wimax_ss_fields = ['Customer Name', 'Circuit ID', 'QOS (BW)', 'Latitude', 'Longitude', 'Building Height',
                           'Tower/Pole Height', 'Antenna Height', 'Polarization', 'Antenna Type', 'SS Mount Type',
                           'Ethernet Extender', 'Cable Length', 'RSSI During Acceptance',
                           'CINR During Acceptance', 'Customer Address', 'Date Of Acceptance', 'SS IP']

        # initialize variables for bs sheet name, ss sheet name, ptp sheet name
        bs_sheet = ""
        ss_sheet = ""
        ptp_sheet = ""
        backhaul_sheet = ""
        technology = ""

        # fetching values form POST
        try:
            bs_sheet = self.request.POST['bs_sheet'] if self.request.POST['bs_sheet'] else ""
            ss_sheet = self.request.POST['ss_sheet'] if self.request.POST['ss_sheet'] else ""
            ptp_sheet = self.request.POST['ptp_sheet'] if self.request.POST['ptp_sheet'] else ""
            backhaul_sheet = self.request.POST['backhaul_sheet'] if self.request.POST['backhaul_sheet'] else ""
        except Exception as e:
            logger.info(e.message)

        # reading workbook using 'xlrd' module
        try:
            book = xlrd.open_workbook(uploaded_file.name, file_contents=uploaded_file.read(), formatting_info=True)
        except Exception as e:
            logger.info("Workbook not uploaded. Exception: ", e.message)
            return render_to_response('bulk_import/gis_bulk_validator.html', {'headers': "",
                                                                              'filename': uploaded_file.name,
                                                                              'sheet_name': "",
                                                                              'valid_rows': "",
                                                                              'invalid_rows': "",
                                                                              'error_message': "There is some internel error in sheet."},
                                      context_instance=RequestContext(self.request))

        # execute only if a valid sheet is selected from form
        if bs_sheet or ss_sheet or ptp_sheet or backhaul_sheet:
            if bs_sheet:
                sheet = book.sheet_by_name(bs_sheet)
                sheet_name = bs_sheet
            elif ss_sheet:
                sheet = book.sheet_by_name(ss_sheet)
                sheet_name = ss_sheet
            elif ptp_sheet:
                sheet = book.sheet_by_name(ptp_sheet)
                sheet_name = ptp_sheet
            elif backhaul_sheet:
                sheet = book.sheet_by_name(backhaul_sheet)
                sheet_name = backhaul_sheet
            else:
                sheet = ""
                sheet_name = ""

            # get the technology of uploaded inventory sheet
            if "Wimax" in sheet_name:
                technology = "Wimax"
            elif "PMP" in sheet_name:
                technology = "PMP"
            elif "PTP" in sheet_name:
                technology = "PTP"
            elif "Backhaul" in sheet_name:
                technology = "Backhaul"
            elif "Converter" in sheet_name:
                technology = "Converter"
            else:
                technology = "Unknown"

            keys = [sheet.cell(0, col_index).value for col_index in xrange(sheet.ncols) if sheet.cell(0, col_index).value]

            keys_list = [x.encode('utf-8').strip() for x in keys]

            complete_d = list()
            for row_index in xrange(1, sheet.nrows):
                d = {keys[col_index].encode('utf-8').strip(): sheet.cell(row_index, col_index).value
                     for col_index in xrange(len(keys))}
                complete_d.append(d)

            # book_to_upload = xlcopy(book)
            destination = open(filepath, 'wb+')
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
            destination.close()
            #xlsave(book, filepath)
            gis_bulk_obj = GISInventoryBulkImport()
            gis_bulk_obj.original_filename = relative_filepath
            gis_bulk_obj.status = 0
            gis_bulk_obj.sheet_name = sheet_name
            gis_bulk_obj.technology = technology
            gis_bulk_obj.description = description
            gis_bulk_obj.uploaded_by = self.request.user
            gis_bulk_obj.save()
            gis_bulk_id = gis_bulk_obj.id

            result = validate_gis_inventory_excel_sheet.delay(gis_bulk_id, complete_d, sheet_name, keys_list, full_time, uploaded_file.name)
            return HttpResponseRedirect('/bulk_import/')
        else:
            logger.info("No sheet is selected.")

        return super(GISInventoryBulkImportView, self).get(self, form)


class ExcelWriterRowByRow(View):
    def get(self, request):
        filename = request.GET['filename'].split(".")[0]
        sheetname = request.GET['sheetname']
        sheettype = request.GET['sheettype']

        if sheettype == repr('valid'):
            content = request.session['valid_rows_lists']
            filename = "valid_{}_{}.xls".format(sheetname.lower().replace(" ", "_"), filename.lower().replace(" ", "_"))
        elif sheettype == repr('invalid'):
            content = request.session['invalid_rows_lists']
            filename = "invalid_{}_{}.xls".format(sheetname.lower().replace(" ", "_"),
                                                  filename.lower().replace(" ", "_"))
        else:
            content = ""

        wb = xlwt.Workbook()
        ws = wb.add_sheet(sheetname)

        style = xlwt.easyxf('pattern: pattern solid, fore_colour tan;')
        style_errors = xlwt.easyxf('pattern: pattern solid, fore_colour red;' 'font: colour white, bold True;')

        try:
            for i, col in enumerate(request.session['headers']):
                if col != 'Errors':
                    ws.write(0, i, col, style)
                else:
                    ws.write(0, i, col, style_errors)
        except Exception as e:
            logger.info(e.message)

        try:
            for i, l in enumerate(content):
                i += 1
                for j, col in enumerate(l):
                    ws.write(i, j, col)
        except Exception as e:
            logger.info(e.message)

        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)

        wb.save(response)

        return response


class BulkUploadValidData(View):
    def get(self, request, *args, **kwargs):
        # user organization
        organization = ''

        try:
            # user organization id
            organization_id = UserProfile.objects.get(username=self.request.user).organization.id
            organization = Organization.objects.get(pk=organization_id)

            # update data import status in GISInventoryBulkImport model
            try:
                gis_obj = GISInventoryBulkImport.objects.get(pk=kwargs['id'])
                gis_obj.upload_status = 1
                gis_obj.save()
            except Exception as e:
                logger.info(e.message)

            if 'sheetname' in kwargs:
                if kwargs['sheetname'] == 'PTP':
                    result = bulk_upload_ptp_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'PTP BH':
                    result = bulk_upload_ptp_bh_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'PMP BS':
                    result = bulk_upload_pmp_bs_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'PMP SM':
                    result = bulk_upload_pmp_sm_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'Wimax BS':
                    result = bulk_upload_wimax_bs_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'Wimax SS':
                    result = bulk_upload_wimax_ss_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                elif kwargs['sheetname'] == 'Backhaul':
                    result = bulk_upload_backhaul_inventory.delay(kwargs['id'], organization, kwargs['sheettype'])
                else:
                    result = ""
        except Exception as e:
            logger.info("Current User Organization:", e.message)
        ##we are using caching for GIS inventory
        ## we need to reset caching, as soon as
        ##user bulk uploads
        try:
            # cached_functions = ['prepare_raw_gis_info',
            #                     'organization_backhaul_devices',
            #                     'organization_network_devices',
            #                     'organization_customer_devices',
            #                     'ptp_device_circuit_backhaul',
            #                     'perf_gis_raw_inventory'
            #                     ]
            # keys = []
            # for cf in cached_functions:
            #     keys.append(cache_get_key(cf))
            # cache.delete_many(keys)
            cache.clear() #delete GIS cache on bulk upload
        except Exception as caching_exp:
            logger.exception(caching_exp.message)
        return HttpResponseRedirect('/bulk_import/')


class GISInventoryBulkImportList(ListView):
    """
    Generic Class based View to List the GISInventoryBulkImports.
    """

    model = GISInventoryBulkImport
    template_name = 'bulk_import/gis_inventory_bulk_imports_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.

        """
        context = super(GISInventoryBulkImportList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'original_filename', 'sTitle': 'Inventory Sheet', 'sWidth': 'auto', },
            {'mData': 'valid_filename', 'sTitle': 'Valid Sheet', 'sWidth': 'auto', },
            {'mData': 'invalid_filename', 'sTitle': 'Invalid Sheet', 'sWidth': 'auto', },
            {'mData': 'status', 'sTitle': 'Status', 'sWidth': 'auto', },
            {'mData': 'sheet_name', 'sTitle': 'Sheet Name', 'sWidth': 'auto', },
            {'mData': 'technology', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'upload_status', 'sTitle': 'Upload Status', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', },
            {'mData': 'uploaded_by', 'sTitle': 'Uploaded By', 'sWidth': 'auto', },
            {'mData': 'added_on', 'sTitle': 'Added On', 'sWidth': 'auto', },
            {'mData': 'modified_on', 'sTitle': 'Modified On', 'sWidth': 'auto', },
        ]
        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        if self.request.user.is_superuser:
            datatable_headers.append({'mData':'bulk_upload_actions', 'sTitle':'Inventory Upload', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class GISInventoryBulkImportListingTable(DatatableSearchMixin, ValuesQuerySetMixin, BaseDatatableView):
    """
    A generic class based view for the gis inventory bulk import data table rendering.

    """
    model = GISInventoryBulkImport
    columns = ['original_filename', 'valid_filename', 'invalid_filename', 'status', 'sheet_name', 'technology', 'upload_status', 'description', 'uploaded_by', 'added_on', 'modified_on']
    order_columns = ['original_filename', 'valid_filename', 'invalid_filename', 'status', 'sheet_name', 'technology', 'upload_status', 'description', 'uploaded_by', 'added_on', 'modified_on']
    search_columns = ['sheet_name', 'technology', 'description', 'uploaded_by']

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            try:
                excel_green = static("img/ms-office-icons/excel_2013_green.png")
                excel_grey = static("img/ms-office-icons/excel_2013_grey.png")
                excel_red = static("img/ms-office-icons/excel_2013_red.png")
                excel_light_green = static("img/ms-office-icons/excel_2013_light_green.png")
                # excel_blue = static("img/ms-office-icons/excel_2013_blue.png")

                # show 'Success', 'Pending' and 'Failed' in upload status
                try:
                    if not dct.get('status'):
                        dct.update(status='Pending')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 0:
                        dct.update(status='Pending')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 1:
                        dct.update(status='Success')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 2:
                        dct.update(status='Failed')
                except Exception as e:
                    logger.info(e.message)

                # show 'Not Yet', 'Pending', 'Success', 'Failed' in import status
                try:
                    if not dct.get('upload_status'):
                        dct.update(upload_status='Not Yet')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('upload_status') == 0:
                        dct.update(upload_status='Not Yet')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('upload_status') == 1:
                        dct.update(upload_status='Pending')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('upload_status') == 2:
                        dct.update(upload_status='Success')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('upload_status') == 3:
                        dct.update(upload_status='Failed')
                except Exception as e:
                    logger.info(e.message)

                # show icon instead of url in data tables view
                try:
                    dct.update(original_filename='<a href="{}{}"><img src="{}" style="float:left; display:block; height:25px; width:25px;">'.format(MEDIA_URL, dct.pop('original_filename'), excel_light_green))
                except Exception as e:
                    logger.info(e.message)
                try:
                    if dct.get('status') == "Success":
                        dct.update(valid_filename='<a href="{}{}"><img src="{}" style="float:left; display:block; height:25px; width:25px;">'.format(MEDIA_URL, dct.pop('valid_filename'), excel_green))
                    else:
                        dct.update(valid_filename='<img src="{0}" style="float:left; display:block; height:25px; width:25px;">'.format(excel_grey))
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == "Success":
                        dct.update(invalid_filename='<a href="{}{}"><img src="{}" style="float:left; display:block; height:25px; width:25px;">'.format(MEDIA_URL, dct.pop('invalid_filename'), excel_red))
                    else:
                        dct.update(invalid_filename='<img src="{0}" style="float:left; display:block; height:25px; width:25px;">'.format(excel_grey))
                except Exception as e:
                    logger.info(e.message)

                # show user full name in uploded by field
                try:
                    if dct.get('uploaded_by'):
                        user = User.objects.get(username=dct.get('uploaded_by'))
                        dct.update(uploaded_by='{} {}'.format(user.first_name, user.last_name))
                except Exception as e:
                    logger.info(e.message)

            except Exception as e:
                logger.info(e)

            # added on field timezone conversion from 'utc' to 'local'
            try:
                dct['added_on'] = convert_utc_to_local_timezone(dct['added_on'])
            except Exception as e:
                logger.error("Timezone conversion not possible. Exception: ", e.message)

            # modified on field timezone conversion from 'utc' to 'local'
            try:
                dct['modified_on'] = convert_utc_to_local_timezone(dct['modified_on'])
            except Exception as e:
                logger.error("Timezone conversion not possible. Exception: ", e.message)

            dct.update(actions='<a href="/bulk_import/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                                <a href="/bulk_import/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.get('id')))
            try:
                sheet_names_list = ['PTP', 'PMP BS', 'PMP SM', 'PTP BH', 'Wimax BS', 'Wimax SS', 'Backhaul']
                if dct.get('sheet_name'):
                    if dct.get('sheet_name') in sheet_names_list:
                        dct.update(bulk_upload_actions='<a href="/bulk_import/bulk_upload_valid_data/valid/{0}/{1}" class="bulk_import_link" title="Upload Valid Inventory"><i class="fa fa-upload text-success"></i></a>\
                                                        <a href="/bulk_import/bulk_upload_valid_data/invalid/{0}/{1}" class="bulk_import_link" title="Upload Invalid Inventory"><i class="fa fa-upload text-danger"></i></a>'.format(dct.get('id'), dct.get('sheet_name')))
                    else:
                        dct.update(bulk_upload_actions='')
            except Exception as e:
                logger.info()
        return json_data


class GISInventoryBulkImportDelete(DeleteView):
    """
    Class based View to delete the GISInventoryBulkImport
    """
    model = GISInventoryBulkImport
    template_name = 'bulk_import/gis_bulk_import_delete.html'
    success_url = reverse_lazy('gis_inventory_bulk_import_list')

    def delete(self, request, *args, **kwargs):
        file_name = lambda x: MEDIA_ROOT + x
        # bulk import object
        bi_obj = self.get_object()

        # remove original file if it exists
        try:
            os.remove(file_name(bi_obj.original_filename))
        except Exception as e:
            logger.info(e.message)

        # remove valid rows file if it exists
        try:
            os.remove(file_name(bi_obj.valid_filename))
        except Exception as e:
            logger.info(e.message)

        # remove invalid rows file if it exists
        try:
            os.remove(file_name(bi_obj.invalid_filename))
        except Exception as e:
            logger.info(e.message)

        # delete entry from database
        bi_obj.delete()
        return HttpResponseRedirect(GISInventoryBulkImportDelete.success_url)


class GISInventoryBulkImportUpdate(UpdateView):
    """
    Class based view to update GISInventoryBulkImport .
    """
    template_name = 'bulk_import/gis_bulk_import_update.html'
    model = GISInventoryBulkImport
    form_class = GISInventoryBulkImportEditForm
    success_url = reverse_lazy('gis_inventory_bulk_import_list')


#**************************************** Ping Thematic Settings *********************************************
class PingThematicSettingsList(ListView):
    """
    Class Based View to render PingThematicSettings List Page.
    """
    model = PingThematicSettings
    template_name = 'ping_thematic_settings/ping_thematic_settings_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(PingThematicSettingsList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias',                   'sTitle': 'Alias',                     'sWidth': 'auto'},
            {'mData': 'service',                 'sTitle': 'Service',                   'sWidth': 'auto'},
            {'mData': 'data_source',             'sTitle': 'Data Source',               'sWidth': 'auto'},
            {'mData': 'icon_settings',           'sTitle': 'Icons Range',               'sWidth': 'auto'},
            {'mData': 'user_selection',          'sTitle': 'Setting Selection',         'sWidth': 'auto'}]

        # user_id = self.request.user.id

        #if user is superadmin or gisadmin
        if self.request.user.is_superuser:
            datatable_headers.append({'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', })

        context['datatable_headers'] = json.dumps(datatable_headers)

        is_global = False
        if 'admin' in self.request.path:
            is_global = True

        context['is_global'] = json.dumps(is_global)

        return context


class PingThematicSettingsListingTable(ValuesQuerySetMixin, DatatableSearchMixin, BaseDatatableView):
    """
    Class based View to render Thematic Settings Data table.
    """
    model = PingThematicSettings
    columns = ['alias', 'service', 'data_source', 'icon_settings']
    order_columns = ['alias', 'service', 'data_source']
    tab_search = {
        "tab_kwarg": 'technology',
        "tab_attr": "technology__name",
    }

    def get_initial_queryset(self):
        is_global = 1
        if self.request.GET.get('admin'):
            is_global = 0

        qs = super(PingThematicSettingsListingTable, self).get_initial_queryset()

        return qs.filter(is_global=is_global)

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify 'icon_setting' field for display in datatables i.e. format: "start_range > icon > end_range"
            icon_settings_display_field = ""

            # after converting 'icon_settings' string in list of icon_setting dictionaries using eval, loop on it
            for d in eval(dct['icon_settings']):
                r = d.keys()[0]

                # fetching number from dictionary key for e.g. 4 from 'icon_settings4'
                s = ''.join(x for x in r if x.isdigit())

                # range fields corresponding to current icon setting
                range_start_field = "range{}_start".format(s)
                range_end_field = "range{}_end".format(s)

                # initialize start and end range
                start_range, end_range = [''] * 2

                # start range
                try:
                    start_range = PingThematicSettings.objects.filter(id=dct['id']).values(range_start_field)[0].values()[0]
                    if not start_range:
                        start_range = "N/A"
                except Exception as e:
                    logger.info("Start Range Exception: ", e.message)

                # end range
                try:
                    end_range = PingThematicSettings.objects.filter(id=dct['id']).values(range_end_field)[0].values()[0]
                    if not end_range:
                        end_range = "N/A"
                except Exception as e:
                    logger.info("End Range Exception: ", e.message)

                # image url
                img_url = str("/media/" + (d.values()[0])
                              if "uploaded" in d.values()[0]
                              else static("img/" + d.values()[0]))

                # image html content
                image_string = '<img src="{0}" style="height:25px; width:25px">'.format(img_url.strip())

                # icon settings content to be displayed in datatable
                icon_settings_display_field += " {} > {} > {} <br />".format(start_range, image_string, end_range)

            user_current_thematic_setting = self.request.user.id in PingThematicSettings.objects.get(
                id=dct['id']).user_profile.values_list('id', flat=True)
            checkbox_checked_true = 'checked' if user_current_thematic_setting else ''
            dct.update(
                icon_settings=icon_settings_display_field,
                user_selection='<input type="checkbox" class="check_class" ' + checkbox_checked_true +
                               ' name="setting_selection" value={0}><br>'.format(dct['id']),
                actions='<a href="/ping_thematic_settings/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/ping_thematic_settings/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(
                    dct.pop('id')))
        return json_data


class PingThematicSettingsDetail(DetailView):
    """
    Class based view to render the Thematic Settings detail.
    """
    model = PingThematicSettings
    template_name = 'ping_thematic_settings/ping_thematic_settings_detail.html'


class PingThematicSettingsCreate(PermissionsRequiredMixin, CreateView):
    """
    Class based view to create new PingThematicSettings.
    """
    template_name = 'ping_thematic_settings/ping_thematic_settings_new.html'
    model = PingThematicSettings
    form_class = PingThematicSettingsForm
    success_url = reverse_lazy('ping_thematic_settings_list')
    required_permissions = ('inventory.add_pingthematicsettings',)

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        icon_settings_keys = list(set(form.data.keys()) - set(
            [key for key in form.cleaned_data.keys() if "icon" not in key] + ['csrfmiddlewaretoken']))

        # sorting icon settings list
        icon_settings_keys = sorted(icon_settings_keys, key=lambda r: int(''.join(x for x in r if x.isdigit())))

        icon_settings_values_list = [{key: form.data[key]} for key in icon_settings_keys if form.data[key]]
        self.object = form.save()
        self.object.icon_settings = icon_settings_values_list
        self.object.save()
        return HttpResponseRedirect(PingThematicSettingsCreate.success_url)


class PingThematicSettingsUpdate(PermissionsRequiredMixin, UpdateView):
    """
    Class based view to update Thematic Settings.
    """
    template_name = 'ping_thematic_settings/ping_thematic_settings_update.html'
    model = PingThematicSettings
    form_class = PingThematicSettingsForm
    success_url = reverse_lazy('ping_thematic_settings_list')
    required_permissions = ('inventory.change_pingthematicsettings',)

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        icon_settings_keys = list(set(form.data.keys()) - set(
            [key for key in form.cleaned_data.keys() if "icon" not in key] + ['csrfmiddlewaretoken']))

        # sorting icon settings list
        icon_settings_keys = sorted(icon_settings_keys, key=lambda r: int(''.join(x for x in r if x.isdigit())))

        icon_settings_values_list = [{key: form.data[key]} for key in icon_settings_keys if form.data[key]]
        self.object = form.save()
        self.object.icon_settings = icon_settings_values_list
        self.object.save()
        # self.object = form.save()
        return HttpResponseRedirect(PingThematicSettingsUpdate.success_url)


class PingThematicSettingsDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to delete the Thematic Settings.
    """
    model = PingThematicSettings
    template_name = 'ping_thematic_settings/ping_thematic_settings_delete.html'
    success_url = reverse_lazy('ping_thematic_settings_list')
    required_permissions = ('inventory.delete_pingthematicsettings',)


class Ping_Update_User_Thematic_Setting(View):
    """
    The Class Based View to Response the Ajax call on click to bind the user with the thematic setting.
    """

    def get(self, request):
        result = {
            "success": 0,
            "message": "Thematic Setting Not Bind to User",
            "data": {
                "meta": None,
                "objects": {}
            }
        }

        thematic_setting_id = self.request.GET.get('ts_template_id', None)
        user_profile_id = self.request.user.id
        if thematic_setting_id:
            ts_obj = PingThematicSettings.objects.get(id=int(thematic_setting_id))
            user_obj = UserProfile.objects.get(id=user_profile_id)
            tech_obj = ts_obj.technology
            to_delete = UserPingThematicSettings.objects.filter(user_profile=user_obj, thematic_technology=tech_obj)

            if len(to_delete):
                to_delete.delete()

            uts = UserPingThematicSettings(user_profile=user_obj,
                                           thematic_template=ts_obj,
                                           thematic_technology=tech_obj)
            uts.save()

            result['success'] = 1
            result['message'] = 'Thematic Setting Bind to User Successfully'
            result['data']['objects']['username'] = self.request.user.userprofile.username
            result['data']['objects']['thematic_setting_name'] = PingThematicSettings.objects.get(
                id=int(thematic_setting_id)).name

        return HttpResponse(json.dumps(result))


class DownloadSelectedBSInventory(View):
    """ Download GIS Inventory excel sheet of selected Base Stations

        :Parameters:
            - 'base_stations' (str) - list of base stations in form of string i.e. [1, 2, 3, 4]

        :Returns:
           - 'file' (file) - inventory excel sheet
    """

    def post(self, request):
        # get base stations id's as js array
        base_stations = self.request.POST.get('base_stations', None)

        # result
        result = {
            'success': 0,
            'message': "Something wrong with inventory download."
        }

        # convert base stations id's string to a python list
        bs_ids = eval(str(base_stations))
        timestamp = time.time()
        fulltime = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d-%H-%M-%S')

        # current user's username
        username = self.request.user.username

        # create 'GISExcelDownload' object
        gis_excel_download = GISExcelDownload()
        gis_excel_download.status = 0
        gis_excel_download.base_stations = base_stations
        gis_excel_download.description = "Started downloading inventory on {}.".format(fulltime)
        gis_excel_download.downloaded_by = username
        gis_excel_download.save()

        # gis excel download id
        gis_excel_download_id = gis_excel_download.id

        try:
            task = generate_gis_inventory_excel.delay(bs_ids, username, fulltime, gis_excel_download_id)
            result['success'] = 1
            result['message'] = "Inventory download started. Please check status \
                                 <a href='/gis_downloaded_inventories/' target='_blank'>Here</a>."
        except Exception as e:
            logger.info("Something wrong with inventory download. Exception: ", e.message)

        return HttpResponse(json.dumps(result))

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(DownloadSelectedBSInventory, self).dispatch(*args, **kwargs)


class DownloadSelectedBSInventoryList(ListView):
    """
    Generic Class based View to List the GISInventoryBulkImports.
    """

    model = GISExcelDownload
    template_name = 'gis_inventory_download/gis_inventory_download_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.

        """
        context = super(DownloadSelectedBSInventoryList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'file_path', 'sTitle': 'Inventory Sheet', 'sWidth': 'auto', },
            {'mData': 'status', 'sTitle': 'Status', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', },
            {'mData': 'downloaded_by', 'sTitle': 'Requested By', 'sWidth': 'auto', },
            {'mData': 'added_on', 'sTitle': 'Requested On Timestamp', 'sWidth': 'auto', },
            {'mData': 'modified_on', 'sTitle': 'Request Completion Timestamp', 'sWidth': 'auto', },
        ]

        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%', 'bSortable': False})
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class DownloadSelectedBSInventoryListingTable(DatatableSearchMixin, ValuesQuerySetMixin, BaseDatatableView):
    """
    A generic class based view for the gis inventory bulk import data table rendering.

    """
    model = GISExcelDownload
    columns = ['file_path', 'status', 'description', 'downloaded_by', 'added_on', 'modified_on']
    order_columns = ['file_path', 'status', 'description', 'downloaded_by', 'added_on', 'modified_on']
    search_columns = ['file_path', 'status', 'description', 'downloaded_by']

    def get_initial_queryset(self):
        """
        Preparing  Initial Queryset for the for rendering the data table.

        """

        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        # queryset
        queryset = GISExcelDownload.objects.filter(downloaded_by=self.request.user.username).values(*self.columns+['id'])

        # if self.request.user.is_superuser:
        #     queryset = GISExcelDownload.objects.filter().values(*self.columns+['id'])
        return queryset

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """

        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            try:
                excel_green = static("img/ms-office-icons/excel_2013_green.png")
                excel_grey = static("img/ms-office-icons/excel_2013_grey.png")
                excel_red = static("img/ms-office-icons/excel_2013_red.png")
                excel_light_green = static("img/ms-office-icons/excel_2013_light_green.png")
                # excel_blue = static("img/ms-office-icons/excel_2013_blue.png")

                # show 'Success', 'Pending' and 'Failed' in upload status
                try:
                    if not dct.get('status'):
                        dct.update(status='Pending')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 0:
                        dct.update(status='Pending')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 1:
                        dct.update(status='Success')
                except Exception as e:
                    logger.info(e.message)

                try:
                    if dct.get('status') == 2:
                        dct.update(status='Failed')
                except Exception as e:
                    logger.info(e.message)

                # show icon instead of url in data tables view
                try:
                    if dct.get('status') == "Success":
                        dct.update(file_path='<a href="{}{}"><img src="{}" style="float:left; display:block; \
                        height:25px; width:25px;">'.format(MEDIA_URL, dct.pop('file_path'), excel_green))
                    else:
                        dct.update(file_path='<img src="{0}" style="float:left; display:block; \
                        height:25px; width:25px;">'.format(excel_grey))
                except Exception as e:
                    logger.info(e.message)

                # show user full name in uploded by field
                try:
                    if dct.get('downloaded_by'):
                        user = User.objects.get(username=dct.get('downloaded_by'))
                        dct.update(downloaded_by='{} {}'.format(user.first_name, user.last_name))
                except Exception as e:
                    logger.info(e.message)

            except Exception as e:
                logger.info(e)

            # added on field timezone conversion from 'utc' to 'local'
            try:
                dct['added_on'] = convert_utc_to_local_timezone(dct['added_on'])
            except Exception as e:
                logger.error("Timezone conversion not possible. Exception: ", e.message)

            # modified on field timezone conversion from 'utc' to 'local'
            try:
                dct['modified_on'] = convert_utc_to_local_timezone(dct['modified_on'])
            except Exception as e:
                logger.error("Timezone conversion not possible. Exception: ", e.message)

            dct.update(actions='<a href="/gis_downloaded_inventories/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                                <a href="/gis_downloaded_inventories/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.get('id')))

        return json_data


class DownloadSelectedBSInventoryDelete(DeleteView):
    """
    Class based View to delete the GISInventoryBulkImport
    """
    model = GISExcelDownload
    template_name = 'gis_inventory_download/gis_inventory_download_delete.html'
    success_url = reverse_lazy('gis_selected_bs_inventories_list')

    def delete(self, request, *args, **kwargs):
        file_name = lambda x: MEDIA_ROOT + x
        # gis excel download object
        gis_excel_obj = self.get_object()

        # remove inventory file if it exists
        try:
            os.remove(file_name(gis_excel_obj.file_path))
        except Exception as e:
            logger.info(e.message)

        # delete entry from database
        gis_excel_obj.delete()
        return HttpResponseRedirect(DownloadSelectedBSInventoryDelete.success_url)


class DownloadSelectedBSInventoryUpdate(UpdateView):
    """
    Class based view to update GISInventoryBulkImport .
    """
    template_name = 'gis_inventory_download/gis_inventory_download_update.html'
    model = GISExcelDownload
    form_class = DownloadSelectedBSInventoryEditForm
    success_url = reverse_lazy('gis_selected_bs_inventories_list')


#**************************************** GIS Wizard ****************************************#

class GisWizardListView(BaseStationList):
    template_name = 'gis_wizard/wizard_list.html'

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context = super(GisWizardListView, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData': 'alias', 'sTitle': 'BS Name', 'sWidth': 'auto', },
            {'mData': 'city__city_name', 'sTitle': 'City', 'sWidth': 'auto', },
            {'mData': 'state__state_name', 'sTitle': 'State', 'sWidth': 'auto', },
            # {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'bs_site_id', 'sTitle': 'Site ID', 'sWidth': 'auto', },
            {'mData': 'bs_switch__id', 'sTitle': 'BS Switch IP', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'backhaul__bh_configured_on__ip_address', 'sTitle': 'Backhaul IP', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'sector_configured_on', 'sTitle': 'Sector Configured On', 'sWidth': 'auto', 'sClass': 'hidden-xs', 'bSortable': False},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs', 'bSortable': False},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False},
        ]
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class GisWizardListingTable(BaseStationListingTable):
    columns = ['alias', 'city__city_name', 'state__state_name', 'bs_site_id', 'bs_switch__id', 'backhaul__bh_configured_on__ip_address', 'description']
    order_columns = ['alias', 'city__city_name', 'state__state_name', 'bs_site_id', 'bs_switch__id', 'backhaul__bh_configured_on__ip_address']

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:

            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'bs_switch__id' in dct:
                    bs_device_ip = Device.objects.get(id=dct['bs_switch__id']).ip_address
                    dct['bs_switch__id'] = "{}".format(bs_device_ip)
            except Exception as e:
                logger.info("BS Switch not present. Exception: ", e.message)

            device_id = dct.pop('id')

            sector_configured_on = Sector.objects.filter(base_station_id=device_id, sector_configured_on__isnull=False,
                    bs_technology__in=[3, 4]).distinct().values_list('sector_configured_on__ip_address', flat=True)
            sector_configured_on = ', '.join(sector_configured_on)
            dct.update(sector_configured_on=sector_configured_on)

            detail_action = '<a href="/gis-wizard/base-station/{0}/details/"><i class="fa fa-list-alt text-info"></i></a>&nbsp'.format(device_id)
            if self.request.user.has_perm('inventory.change_basestation'):
                edit_action = '<a href="/gis-wizard/base-station/{0}/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(device_id)
            else:
                edit_action = ''
            if self.request.user.has_perm('inventory.delete_basestation'):
                delete_action = '<a href="/base_station/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(device_id)
            else:
                delete_action = ''
            delete_action = ''
            if edit_action or delete_action:
                dct.update(actions=detail_action+edit_action+delete_action)
            else:
                dct.update(actions=detail_action)
        return json_data


class GisWizardBaseStationDetailView(BaseStationDetail):
    template_name = 'gis_wizard/base_station_detail.html'


def gis_wizard_base_station_select(request):
    return render(request, 'gis_wizard/base_station.html', {'select_view': True})


class GisWizardBaseStationMixin(object):
    form_class = WizardBaseStationForm
    template_name = 'gis_wizard/base_station.html'

    def get_success_url(self):
        if self.request.GET.get('show', None):
            return reverse('gis-wizard-base-station-update', kwargs={'pk': self.object.id})
        if self.object.backhaul:
            return reverse('gis-wizard-backhaul-update', kwargs={'bs_pk': self.object.id, 'pk': self.object.backhaul.id})
        else:
            return reverse('gis-wizard-backhaul-select', kwargs={'bs_pk': self.object.id})

    def get_context_data(self, **kwargs):
        context = super(GisWizardBaseStationMixin, self).get_context_data(**kwargs)
        if 'pk' in self.kwargs: # Update View

            base_station = BaseStation.objects.get(id=self.kwargs['pk'])
            if base_station.backhaul:
                skip_url = reverse('gis-wizard-backhaul-update', kwargs={'bs_pk': base_station.id, 'pk': base_station.backhaul.id})
            else:
                skip_url = reverse('gis-wizard-backhaul-select', kwargs={'bs_pk': base_station.id})

            save_text = 'Update'
            context['skip_url'] = skip_url
        else: # Create View
            save_text = 'Save'

        context['save_text'] = save_text
        return context

    def form_valid(self, form):
        alias = re.compile(r'[^\w]').sub("_", form.cleaned_data['alias'])
        city = form.cleaned_data['city'].city_name[:3]
        state = form.cleaned_data['state'].state_name[:3]
        form.instance.name = alias + "_" + city + "_" + state
        return super(GisWizardBaseStationMixin, self).form_valid(form)


class GisWizardBaseStationCreateView(GisWizardBaseStationMixin, BaseStationCreate):
    pass


class GisWizardBaseStationUpdateView(GisWizardBaseStationMixin, BaseStationUpdate):
    pass


class GisWizardBackhaulDetailView(BackhaulDetail):
    template_name = 'gis_wizard/backhaul_detail.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardBackhaulDetailView, self).get_context_data(**kwargs)
        context['base_station'] = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        return context


def gis_wizard_backhaul_select(request, bs_pk):
    base_station = BaseStation.objects.get(id=bs_pk)
    if base_station.backhaul:
        return HttpResponseRedirect(reverse('gis-wizard-backhaul-update', kwargs={'bs_pk': bs_pk, 'pk': base_station.backhaul.id}))

    return render(request, 'gis_wizard/backhaul.html',
        {
            'select_view': True,
            'bs_pk': bs_pk,
            'organization': base_station.organization,
            'base_station': base_station,
        }
    )


def gis_wizard_backhaul_delete(request, bs_pk):
    base_station = BaseStation.objects.get(id=bs_pk)
    if base_station.backhaul:
        base_station.backhaul = None
        base_station.bh_port_name = None
        base_station.bh_port = None
        base_station.bh_capacity = None
        base_station.save()
    return HttpResponseRedirect(reverse('gis-wizard-backhaul-create', kwargs={'bs_pk': bs_pk}))


class GisWizardBackhaulMixin(object):
    form_class = WizardBackhaulForm
    template_name = 'gis_wizard/backhaul.html'

    def get_success_url(self):
        if self.request.GET.get('show', None):
            return reverse('gis-wizard-backhaul-update', kwargs={'bs_pk': self.kwargs['bs_pk'], 'pk': self.object.id})
        return reverse('gis-wizard-sector-list', kwargs = {
            'bs_pk': self.kwargs['bs_pk']
        })

    def form_valid(self, form):
        ip_address = form.cleaned_data['bh_configured_on'].ip_address
        form.instance.name = ip_address
        form.instance.alias = ip_address
        form.instance.dr_site = 'No'
        response = super(GisWizardBackhaulMixin, self).form_valid(form)

        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        base_station.backhaul = self.object
        base_station.bh_port_name = self.object.bh_port_name
        base_station.bh_port = self.object.bh_port
        base_station.bh_capacity = self.object.bh_capacity
        base_station.save()

        return response

    def get_context_data(self, **kwargs):
        context = super(GisWizardBackhaulMixin, self).get_context_data(**kwargs)
        context['bs_pk'] = self.kwargs['bs_pk']
        base_station = BaseStation.objects.get(id=context['bs_pk'])
        context['base_station'] = base_station
        if base_station.backhaul:
            context['base_station_has_backhaul'] = True
        else:
            context['base_station_has_backhaul'] = False
        if 'pk' in self.kwargs: # Update View
            save_text = 'Update'
        else: # Create View
            save_text = 'Save'
        context['save_text'] = save_text
        return context


class GisWizardBackhaulCreateView(GisWizardBackhaulMixin, BackhaulCreate):
    pass


class GisWizardBackhaulUpdateView(GisWizardBackhaulMixin, BackhaulUpdate):
    pass


class GisWizardSectorListView(SectorList):
    template_name = 'gis_wizard/sectors_list.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardSectorListView, self).get_context_data(**kwargs)
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        context['base_station'] = base_station

        p2p_datatable_headers = [
            {'mData': 'sector_configured_on__ip_address', 'sTitle': 'Near End', 'sWidth': 'auto', },
            {'mData': 'circuit__sub_station__device__ip_address', 'sTitle': 'Far End', 'sWidth': 'auto', },
            {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'circuit__customer__alias', 'sTitle': 'Customer Name', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'circuit__circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto'},
            {'mData': 'frequency__value', 'sTitle': 'Frequency', 'sWidth': 'auto', },
            {'mData': 'base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False},
        ]

        pmp_datatable_headers = [
            {'mData': 'sector_id', 'sTitle': 'ID', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'sector_configured_on__ip_address', 'sTitle': 'Sector Configured On', 'sWidth': 'auto', },
            {'mData': 'frequency__value', 'sTitle': 'Frequency', 'sWidth': 'auto', },
            {'mData': 'base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'antenna__polarization', 'sTitle': 'Antenna Polarization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False},
        ]

        wimax_datatable_headers = [
            {'mData': 'sector_id', 'sTitle': 'ID', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'bs_technology__alias', 'sTitle': 'Technology', 'sWidth': 'auto', },
            {'mData': 'sector_configured_on__ip_address', 'sTitle': 'Sector Configured On', 'sWidth': 'auto', },
            {'mData': 'sector_configured_on_port__alias', 'sTitle': 'PMP Port', 'sWidth': 'auto',
             'sClass': 'hidden-xs'},
            {'mData': 'frequency__value', 'sTitle': 'Frequency', 'sWidth': 'auto', },
            {'mData': 'base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'antenna__polarization', 'sTitle': 'Antenna Polarization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'mrc', 'sTitle': 'MRC', 'sWidth': 'auto', },
            {'mData': 'dr_configured_on__ip_address', 'sTitle': 'DR Configured On', 'sWidth': 'auto', },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False},
        ]

        context['p2p_datatable_headers'] = json.dumps(p2p_datatable_headers)
        context['pmp_datatable_headers'] = json.dumps(pmp_datatable_headers)
        context['wimax_datatable_headers'] = json.dumps(wimax_datatable_headers)
        return context


class GisWizardSectorListingMixin(object):

    def get_initial_queryset(self):
        qs = super(GisWizardSectorListingMixin, self).get_initial_queryset()
        qs = qs.filter(base_station_id=self.kwargs['bs_pk'], bs_technology_id=self.kwargs['selected_technology'])
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:

            sector_id = dct.pop('id')
            kwargs = {key: self.kwargs[key] for key in ['bs_pk', 'selected_technology']}
            kwargs.update({'pk': sector_id})
            detail_action = '<a href="' + reverse('gis-wizard-sector-detail', kwargs=kwargs) + '"><i class="fa fa-list-alt text-info"></i></a>&nbsp'
            if self.request.user.has_perm('inventory.change_sector'):
                edit_url = reverse('gis-wizard-sector-update', kwargs=kwargs)
                edit_action = '<a href="' + edit_url + '"><i class="fa fa-pencil text-dark"></i></a>&nbsp'
            else:
                edit_action = ''
            dct.update(actions=detail_action+edit_action)
        return json_data


class GisWizardP2PSectorListing(GisWizardSectorListingMixin, SectorListingTable):
    columns = ['sector_configured_on__ip_address', 'circuit__sub_station__device__ip_address', 'bs_technology__alias',
            'circuit__customer__alias', 'circuit__circuit_id', 'frequency__value', 'base_station__alias', 'description']
    order_columns = ['sector_configured_on__ip_address', 'circuit__sub_station__device__ip_address', 'bs_technology__alias',
            'circuit__customer__alias', 'circuit__circuit_id', 'frequency__value', 'base_station__alias', 'description']


class GisWizardPMPSectorListing(GisWizardSectorListingMixin, SectorListingTable):
    columns = ['sector_id', 'bs_technology__alias', 'sector_configured_on__ip_address', 'frequency__value', 'base_station__alias',
            'antenna__polarization', 'description']
    order_columns = ['sector_id', 'bs_technology__alias', 'sector_configured_on__ip_address', 'frequency__value', 'base_station__alias',
            'antenna__polarization', 'description']


class GisWizardWiMAXSectorListing(GisWizardSectorListingMixin, SectorListingTable):
    columns = ['sector_id', 'bs_technology__alias', 'sector_configured_on__ip_address', 'sector_configured_on_port__alias',
            'frequency__value', 'base_station__alias', 'antenna__polarization', 'mrc', 'dr_configured_on__ip_address', 'description']
    order_columns = ['sector_id', 'bs_technology__alias', 'sector_configured_on__ip_address', 'sector_configured_on_port__alias',
            'frequency__value', 'base_station__alias', 'antenna__polarization', 'mrc', 'dr_configured_on__ip_address', 'description']


class GisWizardSectorDetailView(SectorDetail):
    template_name = 'gis_wizard/sector_detail.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardSectorDetailView, self).get_context_data(**kwargs)
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        context['selected_technology'] = self.kwargs['selected_technology']
        context['base_station'] = base_station
        if self.object:
            if self.object.antenna:
                context['sector_antenna'] = self.object.antenna
            if int(self.kwargs['selected_technology']) == 2: # Technology is P2P
                if len(self.object.circuit_set.all()) == 1:
                    circuit = self.object.circuit_set.all()[0]
                    context['circuit'] = circuit
                    if circuit.sub_station:
                        context['sub_station'] = circuit.sub_station
                        if circuit.sub_station.antenna:
                            context['sub_station_antenna'] = circuit.sub_station.antenna
                    if circuit.customer:
                        context['customer'] = circuit.customer

        if self.kwargs['selected_technology'] == '2':
            context['sector_text'] = 'Near End'
        else:
            context['sector_text'] = 'Sector'

        return context


def gis_wizard_sector_select(request, bs_pk, selected_technology):
     base_station = BaseStation.objects.get(id=bs_pk)
     technologies = DeviceTechnology.objects.filter(name__in=['P2P', 'WiMAX', 'PMP'])
     return render(request, 'gis_wizard/sector.html',
         {
             'select_view': True,
             'bs_pk': bs_pk,
             'selected_technology': selected_technology,
             'technologies': technologies,
             'base_station': base_station,
         }
     )


def gis_wizard_sector_delete(request, bs_pk, pk):
    sector = Sector.objects.get(id=pk)
    sector.base_station = None
    sector.save()
    return HttpResponseRedirect(reverse('gis-wizard-sector-create', kwargs={'bs_pk': bs_pk, 'selected_technology': sector.bs_technology_id}))


class GisWizardSectorMixin(object):
    form_class = WizardSectorForm
    antenna_form_class = WizardAntennaForm
    sub_station_form_class = WizardSubStationForm
    customer_form_class = WizardCustomerForm
    circuit_form_class = WizardCircuitForm
    template_name = 'gis_wizard/sector.html'
    success_url = reverse_lazy('gis-wizard-base-station-list')

    def get_success_url(self):
        technology_id = self.kwargs['selected_technology']
        if self.request.GET.get('show', None):
            return reverse('gis-wizard-sector-update', kwargs={'bs_pk': self.kwargs['bs_pk'], 'pk': self.object.id,
                'selected_technology': technology_id})
        if int(technology_id) == 2:
            return self.success_url

        return reverse('gis-wizard-sub-station-list', kwargs = {
            'bs_pk': self.kwargs['bs_pk'], 'selected_technology': technology_id, 'sector_pk': self.object.id
        })

    def get_form_kwargs(self):
        """
        Returns the keyword arguments with the request object for instantiating the form.
        """
        form_kwargs = super(GisWizardSectorMixin, self).get_form_kwargs()
        technology = DeviceTechnology.objects.get(id=self.kwargs['selected_technology'])
        form_kwargs.update({'technology': technology.name})
        return form_kwargs

    def get_context_data(self, **kwargs):
        context = super(GisWizardSectorMixin, self).get_context_data(**kwargs)
        technologies = DeviceTechnology.objects.filter(name__in=['P2P', 'WiMAX', 'PMP'])
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        context['bs_pk'] = self.kwargs['bs_pk']
        context['selected_technology'] = self.kwargs['selected_technology']
        context['technologies'] = technologies
        context['base_station'] = base_station
        if self.object:
            form_kwargs = self.get_form_kwargs()
            if self.object.antenna:
                form_kwargs.update({'instance': self.object.antenna})
                context['sector_antenna_form'] = self.antenna_form_class(**form_kwargs)

            ## If technology is P2P and method is GET; Then provide sub station, antenna, circuit and customer forms in context.
            if int(self.kwargs['selected_technology']) == 2 and self.request.method == 'GET': # Technology is P2P
                if len(self.object.circuit_set.all()) == 1:
                    circuit = self.object.circuit_set.all()[0]
                    form_kwargs.update({'instance': circuit})
                    context['circuit_form'] = self.circuit_form_class(**form_kwargs)
                    if circuit.sub_station:
                        form_kwargs.update({'instance': circuit.sub_station})
                        context['sub_station_form'] = self.sub_station_form_class(**form_kwargs)
                        if circuit.sub_station.antenna: # Use formset as there are two antenna to avoid name conflicts
                            form_kwargs.pop('instance')
                            queryset = Antenna.objects.filter(id=circuit.sub_station.antenna.id)
                            formset = WizardPTPSubStationAntennaFormSet(queryset=queryset, **form_kwargs)
                            context['sub_station_antenna_form'] = formset
                    if circuit.customer:
                        form_kwargs.update({'instance': circuit.customer})
                        context['customer_form'] = self.customer_form_class(**form_kwargs)

        ## Create Skip URL and Delete & Show URL
        skip_url = reverse('gis-wizard-base-station-list')
        if self.object and self.object.base_station == base_station:
            context['base_station_has_sector'] = True
            context['delete_url'] = reverse('gis-wizard-sector-delete', kwargs={'bs_pk': base_station.id, 'pk': self.object.id})
            if self.object.bs_technology_id != 2:
                skip_url = reverse('gis-wizard-sub-station-list', kwargs={'bs_pk': base_station.id,
                    'selected_technology': self.kwargs['selected_technology'], 'sector_pk': self.object.id})
        else:
            context['base_station_has_sector'] = False
        context['skip_url'] = skip_url

        if 'pk' in self.kwargs: # Update View
            save_text = 'Update'
        else: # Create View
            save_text = 'Save'
        context['save_text'] = save_text
        return context

    def post(self, request, *args, **kwargs):
        """
        Save sector and antenna.
        """

        try: # if update view
            self.object = self.get_object()
        except AttributeError as e: # if create view
            self.object = None

        form_kwargs = self.get_form_kwargs()
        if self.object and self.object.antenna:
            antenna_instance = self.object.antenna
        elif request.POST.get('sector_antenna_radio') == 'existing' and request.POST.get('sector_antenna'):
            antenna_id = request.POST.get('sector_antenna')
            antenna_instance = Antenna.objects.get(id=antenna_id)
        else:
            antenna_instance = None

        sector_form = self.get_form(self.get_form_class())

        form_kwargs.update({'instance': antenna_instance})
        antenna_form = self.antenna_form_class(**form_kwargs)

        technology = self.kwargs['selected_technology']
        if int(technology) == 2:
            if request.POST.get('sub_station_radio') == 'existing' and request.POST.get('sub_station'):
                sub_station_id = request.POST.get('sub_station')
                sub_station_instance = SubStation.objects.get(id=sub_station_id)
            else:
                sub_station_instance = None
            if request.POST.get('sub_station_customer_radio') == 'existing' and request.POST.get('sub_station_customer'):
                customer_id = request.POST.get('sub_station_customer')
                customer_instance = Customer.objects.get(id=customer_id)
            else:
                customer_instance = None
            if request.POST.get('sub_station_circuit_radio') == 'existing' and request.POST.get('sub_station_circuit'):
                circuit_id = request.POST.get('sub_station_circuit')
                circuit_instance = Circuit.objects.get(id=circuit_id)
            else:
                circuit_instance = None
            if self.object and len(self.object.circuit_set.all()) == 1:
                circuit = self.object.circuit_set.all()[0]
                circuit_instance = circuit
                if circuit.sub_station:
                    sub_station_instance = circuit.sub_station
                if circuit.customer:
                    customer_instance = circuit.customer

            form_kwargs.update({'instance': sub_station_instance})
            sub_station_form = self.sub_station_form_class(**form_kwargs)

            # form_kwargs.update({'instance': antenna_instance})
            form_kwargs.pop('instance')
            sub_station_antenna_formset = WizardPTPSubStationAntennaFormSet(**form_kwargs)

            form_kwargs.update({'instance': customer_instance})
            customer_form = self.customer_form_class(**form_kwargs)

            form_kwargs.update({'instance': circuit_instance})
            circuit_form = self.circuit_form_class(**form_kwargs)

            if (sector_form.is_valid() and antenna_form.is_valid() and sub_station_form.is_valid()
                and sub_station_antenna_formset.is_valid() and customer_form.is_valid() and circuit_form.is_valid()):
                return self.form_valid(sector_form, antenna_form, sub_station_form, sub_station_antenna_formset, customer_form, circuit_form)
            else:
                return self.form_invalid(sector_form, antenna_form, sub_station_form, sub_station_antenna_formset, customer_form, circuit_form)
        else:

            if (sector_form.is_valid() and antenna_form.is_valid()):
                return self.form_valid(sector_form, antenna_form)
            else:
                return self.form_invalid(sector_form, antenna_form)

    def form_valid(self, sector_form, antenna_form, sub_station_form=None, sub_station_antenna_formset=None, customer_form=None, circuit_form=None):
        form_kwargs = self.get_form_kwargs()
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        technology = self.kwargs['selected_technology']
        sector_configured_on_id = form_kwargs['data']['sector_configured_on']
        sector_configured_on = Device.objects.get(id=sector_configured_on_id)

        antenna = antenna_form.save(commit=False)
        antenna.name = sector_configured_on.ip_address
        antenna.alias = sector_configured_on.ip_address
        antenna.organization = base_station.organization
        antenna.save()

        self.object = sector_form.save(commit=False)
        self.object.name = sector_configured_on.ip_address

        # Alias: the IP address of the device for P2P; FOR PMP and WIMAX this would be Sector ID.
        if int(technology) == 2:
            self.object.alias = sector_configured_on.ip_address
        else:
            self.object.alias = form_kwargs['data']['sector_id']
        self.object.bs_technology_id = technology
        self.object.organization = base_station.organization
        self.object.base_station = base_station
        self.object.antenna = antenna
        self.object.save()

        if int(technology) == 2:
            device_id = form_kwargs['data']['device']
            device = Device.objects.get(id=device_id)

            sub_station_antenna = sub_station_antenna_formset[0].save(commit=False)
            sub_station_antenna.name = device.ip_address
            sub_station_antenna.alias = device.ip_address
            sub_station_antenna.organization = base_station.organization
            sub_station_antenna.save()

            sub_station = sub_station_form.save(commit=False)
            sub_station.name = device.ip_address
            sub_station.alias = device.ip_address
            sub_station.organization = base_station.organization
            sub_station.antenna = sub_station_antenna # Far End Antenna.
            sub_station.save()

            customer = customer_form.save(commit=False)
            customer.name = form_kwargs['data']['alias']
            customer.organization = base_station.organization
            customer.save()

            circuit = circuit_form.save(commit=False)
            circuit.name = form_kwargs['data']['circuit_id']
            circuit.alias = form_kwargs['data']['circuit_id']
            circuit.organization = base_station.organization
            circuit.sector = self.object
            circuit.customer = customer
            circuit.sub_station = sub_station
            circuit.save()

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, sector_form, antenna_form, sub_station_form=None, sub_station_antenna_formset=None, customer_form=None, circuit_form=None):
        return self.render_to_response(self.get_context_data(form=sector_form, antenna_form=antenna_form, sub_station_form=sub_station_form, sub_station_antenna_form=sub_station_antenna_formset, customer_form=customer_form, circuit_form=circuit_form))


class GisWizardSectorCreateView(GisWizardSectorMixin, SectorCreate):
    pass


class GisWizardSectorUpdateView(GisWizardSectorMixin, SectorUpdate):
    pass


def get_wizard_form(request):
    model_str = request.GET.get('model')
    form_class = {
                'antenna': WizardAntennaForm,
                'sub_station': WizardSubStationForm,
                'customer': WizardCustomerForm,
                'circuit': WizardCircuitForm,
        }[model_str]
    model = {
            'antenna': Antenna,
            'sub_station': SubStation,
            'customer': Customer,
            'circuit': Circuit,
        }[model_str]
    technology = DeviceTechnology.objects.get(id=request.GET.get('technology')).name
    form_kwargs = {'request': request, 'technology': technology}
    if 'pk' in request.GET:
        pk = request.GET.get('pk')
        instance = model.objects.get(id=pk)
        form = form_class(instance=instance, **form_kwargs)
    else:
        form = form_class(**form_kwargs)

    return render(request, 'gis_wizard/form.html', {'form': form})


def get_ptp_sub_station_antenna_wizard_form(request):
    technology = DeviceTechnology.objects.get(id=2).name
    form_kwargs = {'request': request, 'technology': technology}
    if 'pk' in request.GET:
        pk = request.GET.get('pk')
        queryset = Antenna.objects.filter(id=pk)
        formset = WizardPTPSubStationAntennaFormSet(queryset=queryset, **form_kwargs)
    else:
        formset = WizardPTPSubStationAntennaFormSet(queryset=Antenna.objects.none(), **form_kwargs)

    return render(request, 'gis_wizard/ptp_sub_station_antenna_form.html', {'formset': formset})


class GisWizardSectorSubStationListView(SubStationList):
    """
    """
    template_name = 'gis_wizard/sub_stations_list.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardSectorSubStationListView, self).get_context_data(**kwargs)
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        context['base_station'] = base_station
        sector = Sector.objects.get(id=self.kwargs['sector_pk'])
        context['sector'] = sector
        context['selected_technology'] = self.kwargs['selected_technology']

        datatable_headers = [
            {'mData': 'device__ip_address', 'sTitle': 'SS IP', 'sWidth': 'auto', },
            {'mData': 'device__device_technology', 'sTitle': 'Device Technology', 'sWidth': 'auto', },
            {'mData': 'circuit__customer__alias', 'sTitle': 'Customer Name', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'circuit__circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto'},
            {'mData': 'circuit__sector__sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto'},
            {'mData': 'antenna__polarization', 'sTitle': 'Antenna Polarization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'city__city_name', 'sTitle': 'City', 'sWidth': 'auto'},
            {'mData': 'state__state_name', 'sTitle': 'State', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs','bSortable': False},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False}
        ]

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class GisWizardSubStationListing(SubStationListingTable):
    """
    Class based View to render Sub Station Data table.
    """
    columns = ['device__ip_address', 'device__device_technology', 'circuit__customer__alias', 'circuit__circuit_id',
            'circuit__sector__sector_id', 'antenna__polarization', 'city__city_name', 'state__state_name', 'description']
    order_columns = ['device__ip_address', 'device__device_technology', 'circuit__customer__alias', 'circuit__circuit_id',
            'circuit__sector__sector_id', 'antenna__polarization', 'city__city_name', 'state__state_name']

    def get_initial_queryset(self):
        qs = super(GisWizardSubStationListing, self).get_initial_queryset()
        qs = qs.filter(circuit__sector=self.kwargs['sector_pk'])
        qs = qs.filter(device__device_technology=self.kwargs['selected_technology'])
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:


            #if dct['device__device_technology']: Always is 3 and 4 as in self.kwargs['selected_technology']
            dct['device__device_technology'] = DeviceTechnology.objects.get(pk=int(dct['device__device_technology'])).alias

            sub_station_id = dct.pop('id')
            kwargs = {key: self.kwargs[key] for key in ['bs_pk', 'selected_technology', 'sector_pk']}
            kwargs.update({'pk': sub_station_id})
            detail_action = '<a href="' + reverse('gis-wizard-sub-station-detail', kwargs=kwargs) + '"><i class="fa fa-list-alt text-info"></i></a>&nbsp'
            if self.request.user.has_perm('inventory.change_substation'):
                edit_url = reverse('gis-wizard-sub-station-update', kwargs=kwargs)
                edit_action = '<a href="' + edit_url + '"><i class="fa fa-pencil text-dark"></i></a>&nbsp'
            else:
                edit_action = ''
            dct.update(actions=detail_action+edit_action)
        return json_data


def gis_wizard_sub_station_select(request, bs_pk, selected_technology, sector_pk):
    technologies = DeviceTechnology.objects.order_by('-name').filter(name__in=['WiMAX', 'PMP'])
    return render(request, 'gis_wizard/sub_station.html',
        {
            'select_view': True,
            'bs_pk': bs_pk,
            'selected_technology': selected_technology,
            'sector_pk': sector_pk,
            'technologies': technologies,
            'organization': BaseStation.objects.get(id=bs_pk).organization
        }
    )


class GisWizardSubStationDetailView(SubStationDetail):
    template_name = 'gis_wizard/sub_station_detail.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardSubStationDetailView, self).get_context_data(**kwargs)
        context['selected_technology'] = self.kwargs['selected_technology']
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        context['base_station'] = base_station
        context['sector_pk'] = self.kwargs['sector_pk']
        if self.object.antenna:
            context['sub_station_antenna'] = self.object.antenna
        if len(self.object.circuit_set.all()) == 1:
            circuit = self.object.circuit_set.all()[0]
            context['circuit'] = circuit
            if circuit.customer:
                context['customer'] = circuit.customer
        return context


def gis_wizard_sub_station_delete(request, bs_pk, selected_technology, sector_pk, pk):
    circuit = Circuit.objects.get(sub_station_id=pk)
    circuit.sector = None
    circuit.save()
    return HttpResponseRedirect(reverse('gis-wizard-sub-station-create', kwargs={'bs_pk': bs_pk,
        'selected_technology': selected_technology, 'sector_pk': sector_pk}))


class GisWizardSubStationMixin(object):
    form_class = WizardSubStationForm
    antenna_form_class = WizardAntennaForm
    customer_form_class = WizardCustomerForm
    circuit_form_class = WizardCircuitForm
    template_name = 'gis_wizard/sub_station.html'
    success_url = reverse_lazy('gis-wizard-base-station-list')

    def get_success_url(self):
        if self.request.GET.get('show', None):
            return reverse('gis-wizard-sub-station-update', kwargs={'bs_pk': self.kwargs['bs_pk'], 'pk': self.object.id,
                'selected_technology': self.kwargs['selected_technology'], 'sector_pk': self.kwargs['sector_pk']})

        return self.success_url

    def get_form_kwargs(self):
        """
        Returns the keyword arguments with the request object for instantiating the form.
        """
        form_kwargs = super(GisWizardSubStationMixin, self).get_form_kwargs()
        technology = DeviceTechnology.objects.get(id=self.kwargs['selected_technology'])
        form_kwargs.update({'technology': technology.name})
        return form_kwargs

    def get_context_data(self, **kwargs):
        context = super(GisWizardSubStationMixin, self).get_context_data(**kwargs)
        technologies = DeviceTechnology.objects.order_by('-name').filter(name__in=['WiMAX', 'PMP'])
        context['bs_pk'] = self.kwargs['bs_pk']
        context['selected_technology'] = self.kwargs['selected_technology']
        context['sector_pk'] = self.kwargs['sector_pk']
        context['technologies'] = technologies
        context['organization'] = BaseStation.objects.get(id=self.kwargs['bs_pk']).organization
        if self.object:
            form_kwargs = self.get_form_kwargs()
            context['sub_station_antenna_id'] = self.object.antenna.id if self.object.antenna else ''
            # context['sub_station_customer_id'] = self.object.customer.id if self.object.customer else ''
            # context['sub_station_circuit_id'] = self.object.circuit.id if self.object.circuit else ''

            ## If method is GET; Then provide antenna, circuit and customer forms in context.
            if self.request.method == 'GET':
                if self.object.antenna:
                    form_kwargs.update({'instance': self.object.antenna})
                    context['sub_station_antenna_form'] = self.antenna_form_class(**form_kwargs)
                if len(self.object.circuit_set.all()) == 1:
                    circuit = self.object.circuit_set.all()[0]
                    form_kwargs.update({'instance': circuit})
                    context['circuit_form'] = self.circuit_form_class(**form_kwargs)
                    if circuit.customer:
                        form_kwargs.update({'instance': circuit.customer})
                        context['customer_form'] = self.customer_form_class(**form_kwargs)
        if self.object and Circuit.objects.filter(sector_id=self.kwargs['sector_pk'], sub_station_id=self.object.id).exists():
            context['sector_has_sub_station'] = True
        else:
            context['sector_has_sub_station'] = False

        if 'pk' in self.kwargs: # Update View
            save_text = 'Update'
        else: # Create View
            save_text = 'Save'
        context['save_text'] = save_text
        return context

    def post(self, request, *args, **kwargs):
        """
        Save sub_station, antenna, customer and circuit for WiMAX and PMP.
        """

        try: # if update view
            self.object = self.get_object()
        except AttributeError as e: # if create view
            self.object = None

        form_kwargs = self.get_form_kwargs()
        if self.object and self.object.antenna:
            antenna_instance = self.object.antenna
        elif request.POST.get('sub_station_antenna_radio') == 'existing':
            antenna_id = request.POST.get('sub_station_antenna')
            antenna_instance = Antenna.objects.get(id=antenna_id)
        else:
            antenna_instance = None
        if request.POST.get('sub_station_customer_radio') == 'existing' and request.POST.get('sub_station_customer'):
            customer_id = request.POST.get('sub_station_customer')
            customer_instance = Customer.objects.get(id=customer_id)
        else:
            customer_instance = None
        if request.POST.get('sub_station_circuit_radio') == 'existing' and request.POST.get('sub_station_circuit'):
            circuit_id = request.POST.get('sub_station_circuit')
            circuit_instance = Circuit.objects.get(id=circuit_id)
        else:
            circuit_instance = None

        if self.object and len(self.object.circuit_set.all()) == 1:
            circuit = self.object.circuit_set.all()[0]
            circuit_instance = circuit
            if circuit.sub_station:
                sub_station_instance = circuit.sub_station
            if circuit.customer:
                customer_instance = circuit.customer

        sub_station_form = self.get_form(self.get_form_class())

        form_kwargs.update({'instance': antenna_instance})
        antenna_form = self.antenna_form_class(**form_kwargs)

        form_kwargs.update({'instance': customer_instance})
        customer_form = self.customer_form_class(**form_kwargs)

        form_kwargs.update({'instance': circuit_instance})
        circuit_form = self.circuit_form_class(**form_kwargs)

        if (sub_station_form.is_valid() and antenna_form.is_valid() and customer_form.is_valid() and circuit_form.is_valid()):
            return self.form_valid(sub_station_form, antenna_form, customer_form, circuit_form)
        else:
            return self.form_invalid(sub_station_form, antenna_form, customer_form, circuit_form)

    def form_valid(self, sub_station_form, antenna_form, customer_form, circuit_form):
        form_kwargs = self.get_form_kwargs()
        base_station = BaseStation.objects.get(id=self.kwargs['bs_pk'])
        sector = Sector.objects.get(id=self.kwargs['sector_pk'])
        technology = self.kwargs['selected_technology']
        device_id = form_kwargs['data']['device']
        device = Device.objects.get(id=device_id)

        antenna = antenna_form.save(commit=False)
        antenna.name = device.ip_address
        antenna.alias = device.ip_address
        antenna.organization = base_station.organization
        antenna.save()

        self.object = sub_station_form.save(commit=False)
        self.object.name = device.ip_address
        self.object.alias = device.ip_address
        self.object.organization = base_station.organization
        self.object.antenna = antenna
        self.object.save()

        customer = customer_form.save(commit=False)
        customer.name = form_kwargs['data']['alias']
        customer.organization = base_station.organization
        customer.save()

        circuit = circuit_form.save(commit=False)
        circuit.name = form_kwargs['data']['circuit_id']
        circuit.alias = form_kwargs['data']['circuit_id']
        circuit.organization = base_station.organization
        circuit.sector = sector
        circuit.customer = customer
        circuit.sub_station = self.object
        circuit.save()

        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, sub_station_form, antenna_form, customer_form, circuit_form):
        return self.render_to_response(self.get_context_data(form=sub_station_form, sub_station_antenna_form=antenna_form, customer_form=customer_form, circuit_form=circuit_form))


class GisWizardSubStationCreateView(GisWizardSubStationMixin, SubStationCreate):
    pass


class GisWizardSubStationUpdateView(GisWizardSubStationMixin, SubStationUpdate):
    pass

#************************************** Gis Wizard Start With PTP ****************************

class GisWizardPTPListView(SectorList):
    template_name = 'gis_wizard/wizard_list_ptp.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardPTPListView, self).get_context_data(**kwargs)

        datatable_headers = [
            {'mData': 'sector_configured_on__ip_address', 'sTitle': 'Near End IP', 'sWidth': 'auto', },
            {'mData': 'circuit__sub_station__device__ip_address', 'sTitle': 'Far End IP', 'sWidth': 'auto', },
            {'mData': 'circuit__customer__alias', 'sTitle': 'Customer Name', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'circuit__circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto'},
            {'mData': 'frequency__value', 'sTitle': 'Frequency', 'sWidth': 'auto', },
            {'mData': 'base_station__alias', 'sTitle': 'Base Station', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'sector_configured_on__country', 'sTitle': 'Country', 'sWidth': 'auto', 'bSortable': False, },
            {'mData': 'sector_configured_on__state', 'sTitle': 'State', 'sWidth': 'auto', 'bSortable': False, },
            {'mData': 'sector_configured_on__city', 'sTitle': 'City', 'sWidth': 'auto', 'bSortable': False, },
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False},
        ]

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class GisWizardPTPListingTable(SectorListingTable):
    columns = ['sector_configured_on__ip_address', 'circuit__sub_station__device__ip_address', 'circuit__customer__alias',
            'circuit__circuit_id', 'frequency__value', 'base_station__alias', 'sector_configured_on__country',
            'sector_configured_on__state', 'sector_configured_on__city', 'description']
    order_columns = ['sector_configured_on__ip_address', 'circuit__sub_station__device__ip_address', 'circuit__customer__alias',
            'circuit__circuit_id', 'frequency__value', 'base_station__alias', 'sector_configured_on__country',
            'sector_configured_on__state', 'sector_configured_on__city', 'description']

    def get_initial_queryset(self):
        qs=super(GisWizardPTPListingTable, self).get_initial_queryset()
        qs = qs.filter(bs_technology__name='P2P')
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            if dct['sector_configured_on__country']:
                dct['sector_configured_on__country'] = Country.objects.get(id=dct['sector_configured_on__country']).country_name
            if dct['sector_configured_on__state']:
                dct['sector_configured_on__state'] = State.objects.get(id=dct['sector_configured_on__state']).state_name
            if dct['sector_configured_on__city']:
                dct['sector_configured_on__city'] = City.objects.get(id=dct['sector_configured_on__city']).city_name

            device_id = dct.pop('id')
            sector = Sector.objects.get(id=device_id)
            kwargs = {'bs_pk': sector.base_station.id, 'selected_technology': sector.bs_technology.id , 'pk': sector.id}
            detail_action = '<a href="' + reverse('gis-wizard-sector-detail', kwargs=kwargs) + '"><i class="fa fa-list-alt text-info"></i></a>&nbsp'
            if self.request.user.has_perm('inventory.change_sector'):
                edit_action = '<a href="/gis-wizard/base-station/{0}/technology/{1}/sector/{2}/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(sector.base_station.id, sector.bs_technology.id , device_id)
            else:
                edit_action = ''
            dct.update(actions=detail_action+edit_action)
        return json_data


class GisWizardSubStationListView(SubStationList):
    template_name = 'gis_wizard/wizard_list_sub-station.html'

    def get_context_data(self, **kwargs):
        context = super(GisWizardSubStationListView, self).get_context_data(**kwargs)

        datatable_headers = [
            {'mData': 'device__ip_address', 'sTitle': 'SS IP', 'sWidth': 'auto', },
            {'mData': 'device__device_technology', 'sTitle': 'Device Technology', 'sWidth': 'auto', },
            {'mData': 'circuit__customer__alias', 'sTitle': 'Customer Name', 'sWidth': 'auto',
             'sClass': 'hidden-xs'},
            {'mData': 'circuit__circuit_id', 'sTitle': 'Circuit ID', 'sWidth': 'auto'},
            {'mData': 'circuit__sector__sector_id', 'sTitle': 'Sector ID', 'sWidth': 'auto'},
            {'mData': 'antenna__polarization', 'sTitle': 'Antenna Polarization', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'city__city_name', 'sTitle': 'City', 'sWidth': 'auto'},
            {'mData': 'state__state_name', 'sTitle': 'State', 'sWidth': 'auto', 'sClass': 'hidden-xs'},
            {'mData': 'description', 'sTitle': 'Description', 'sWidth': 'auto', 'sClass': 'hidden-xs','bSortable': False},
            {'mData': 'actions', 'sTitle': 'Actions', 'sWidth': '10%', 'bSortable': False}
        ]

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class GisWizardSubStationListingTable(SubStationListingTable):
    columns = ['device__ip_address', 'device__device_technology', 'circuit__customer__alias', 'circuit__circuit_id',
            'circuit__sector__sector_id', 'antenna__polarization', 'city__city_name', 'state__state_name', 'description']
    order_columns = ['device__ip_address', 'device__device_technology', 'circuit__customer__alias', 'circuit__circuit_id',
            'circuit__sector__sector_id', 'antenna__polarization', 'city__city_name', 'state__state_name']

    def get_initial_queryset(self):

        qs = super(GisWizardSubStationListingTable, self).get_initial_queryset()
        qs = qs.filter(device__device_technology__in=[3,4])
        return qs

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs
        """
        json_data = [{key: val if val else "" for key, val in dct.items()} for dct in qs]
        for dct in json_data:
            # modify device name format in datatable i.e. <device alias> (<device ip>)
            try:
                if 'device__id' in dct:
                    ss_device_alias = Device.objects.get(id=dct['device__id']).device_alias
                    ss_device_ip = Device.objects.get(id=dct['device__id']).ip_address
                    dct['device__id'] = "{} ({})".format(ss_device_alias, ss_device_ip)
            except Exception as e:
                logger.info("Sub Station Device not present. Exception: ", e.message)

            #if dct['device__device_technology']: Always is 3 and 4 as in get_initial_queryset
            dct['device__device_technology'] = DeviceTechnology.objects.get(pk=int(dct['device__device_technology'])).alias
            device_id = dct.pop('id')
            sub_station = SubStation.objects.get(id=device_id)
            detail_action = ''
            edit_action = ''
            if len(sub_station.circuit_set.all()) == 1 and sub_station.circuit_set.all()[0].sector and sub_station.device:
                sector = sub_station.circuit_set.all()[0].sector
                kwargs = {'bs_pk': sector.base_station.id, 'selected_technology': sub_station.device.device_technology,
                        'sector_pk': sector.id, 'pk': device_id}
                detail_action = '<a href="' + reverse('gis-wizard-sub-station-detail', kwargs=kwargs) + '"><i class="fa fa-list-alt text-info"></i></a>&nbsp'
                if self.request.user.has_perm('inventory.change_substation'):
                    edit_action = '<a href="/gis-wizard/base-station/{0}/technology/{1}/sector/{2}/sub-station/{3}/"><i class="fa fa-pencil text-dark"></i></a>&nbsp'.format(sub_station.circuit_set.all()[0].sector.base_station.id, sub_station.circuit_set.all()[0].sector.bs_technology.id, sub_station.circuit_set.all()[0].sector.id, device_id)
            dct.update(actions=detail_action+edit_action)
        return json_data
