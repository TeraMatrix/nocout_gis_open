import json
from django.db.models.query import ValuesQuerySet
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, ModelFormMixin
from django.core.urlresolvers import reverse_lazy
from django_datatables_view.base_datatable_view import BaseDatatableView
from device_group.models import DeviceGroup
from .forms import OrganizationForm
from .models import Organization
from nocout.utils.jquery_datatable_generation import Datatable_Generation
from user_group.models import UserGroup
# Import nocout utils gateway class
from nocout.utils.util import NocoutUtilsGateway
from nocout.mixins.user_action import UserLogDeleteMixin
from nocout.mixins.permissions import PermissionsRequiredMixin
from nocout.mixins.datatable import DatatableSearchMixin, DatatableOrganizationFilterMixin
from nocout.mixins.generics import FormRequestMixin


class OrganizationList(PermissionsRequiredMixin, ListView):
    """
    Class Based View to render Organization List page.
    """

    model = Organization
    template_name = 'organization/organization_list.html'
    required_permissions = ('organization.view_organization',)

    def get_context_data(self, **kwargs):
        """
        Preparing the Context Variable required in the template rendering.
        """
        context=super(OrganizationList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData':'name',                'sTitle' : 'Name',          'sWidth':'auto'},
            {'mData':'alias',               'sTitle' : 'Alias',         'sWidth':'auto'},
            {'mData':'parent__name',        'sTitle' : 'Parent',        'sWidth':'auto'},
            {'mData':'city',                'sTitle' : 'City',          'sWidth':'auto'},
            {'mData':'state',               'sTitle' : 'State',         'sWidth':'auto'},
            {'mData':'country',             'sTitle' : 'Country',       'sWidth':'auto'},
            {'mData':'description',         'sTitle' : 'Description',   'sWidth':'auto','bSortable': False}]

        if 'admin' in self.request.user.userprofile.role.values_list('role_name', flat=True):
            datatable_headers.append({'mData':'actions', 'sTitle':'Actions', 'sWidth':'5%','bSortable': False })

        context['datatable_headers'] = json.dumps(datatable_headers)
        return context


class OrganizationListingTable(PermissionsRequiredMixin, DatatableOrganizationFilterMixin, DatatableSearchMixin, BaseDatatableView):
    """
    Class based View to render Organization Data table.
    """
    model = Organization
    required_permissions = ('organization.view_organization',)
    columns = ['name', 'alias', 'parent__name','city','state','country', 'description']
    order_columns = ['name',  'alias', 'parent__name', 'city', 'state', 'country']
    search_columns = ['name', 'alias', 'parent__name','city','state','country', 'description']
    organization_field = 'id'

    def prepare_results(self, qs):
        """
        Preparing the final result after fetching from the data base to render on the data table.

        :param qs:
        :return qs

        """
        json_data = [ { key: val if val else "" for key, val in dct.items() } for dct in qs ]
        for dct in json_data:
            dct.update(actions='<a href="/organization/{0}/edit/"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/organization/{0}/delete/"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return json_data


class OrganizationDetail(PermissionsRequiredMixin, DetailView):
    """
    Class based view to render the organization detail.
    """
    model = Organization
    required_permissions = ('organization.view_organization',)
    template_name = 'organization/organization_detail.html'


class OrganizationCreate(PermissionsRequiredMixin, FormRequestMixin, CreateView):
    """
    Class based view to create new organization.
    """
    template_name = 'organization/organization_new.html'
    model = Organization
    form_class = OrganizationForm
    success_url = reverse_lazy('organization_list')
    required_permissions = ('organization.add_organization',)


    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        self.object=form.save()
        self.model.objects.rebuild()
        return super(ModelFormMixin, self).form_valid(form)


class OrganizationUpdate(PermissionsRequiredMixin, FormRequestMixin, UpdateView):
    """
    Class based view to update organization.
    """
    template_name = 'organization/organization_update.html'
    model = Organization
    form_class = OrganizationForm
    success_url = reverse_lazy('organization_list')
    required_permissions = ('organization.change_organization',)

    def get_queryset(self):
        # Create instance of 'NocoutUtilsGateway' class
        nocout_utils = NocoutUtilsGateway()
        return nocout_utils.logged_in_user_organizations(self)

    def form_valid(self, form):
        """
        Submit the form and to log the user activity.
        """
        self.object=form.save()
        self.model.objects.rebuild()
        return HttpResponseRedirect( OrganizationUpdate.success_url )


class OrganizationDelete(PermissionsRequiredMixin, UserLogDeleteMixin, DeleteView):
    """
    Class based View to Delete the Organization.
    """
    model = Organization
    template_name = 'organization/organization_delete.html'
    success_url = reverse_lazy('organization_list')
    required_permissions = ('organization.delete_organization',)

    def get_queryset(self):
        # Create instance of 'NocoutUtilsGateway' class
        nocout_utils = NocoutUtilsGateway()
        return nocout_utils.logged_in_user_organizations(self)
