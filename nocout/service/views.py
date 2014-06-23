import json
from actstream import action
from django.db.models.query import ValuesQuerySet
from django.http import HttpResponseRedirect
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.core.urlresolvers import reverse_lazy
from django_datatables_view.base_datatable_view import BaseDatatableView
from models import Service, ServiceParameters, ServiceDataSource
from .forms import ServiceForm, ServiceParametersForm, ServiceDataSourceForm
from nocout.utils.util import DictDiffer


class ServiceList(ListView):
    model = Service
    template_name = 'service/services_list.html'

    def get_context_data(self, **kwargs):
        context=super(ServiceList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData':'service_name',     'sTitle' : 'Service',       'sWidth':'null',},
            {'mData':'alias',            'sTitle' : 'Alias',         'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'command',          'sTitle' : 'Command',       'sWidth':'null',},
            {'mData':'description',      'sTitle' : 'Description',   'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'actions',          'sTitle' : 'Actions',       'sWidth':'10%' ,}
            ]
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context

class ServiceListingTable(BaseDatatableView):
    model = ServiceList
    columns = ['service_name', 'alias', 'command', 'description']
    order_columns = ['service_name', 'alias', 'command', 'description']

    def filter_queryset(self, qs):
        sSearch = self.request.GET.get('sSearch', None)
        ##TODO:Need to optimise with the query making login.
        if sSearch:
            query=[]
            exec_query = "qs = %s.objects.filter("%(self.model.__name__)
            for column in self.columns[:-1]:
                query.append("Q(%s__contains="%column + "\"" +sSearch +"\"" +")")

            exec_query += " | ".join(query)
            exec_query += ").values(*"+str(self.columns+['id'])+")"
            # qs=qs.filter( reduce( lambda q, column: q | Q(column__contains=sSearch), self.columns, Q() ))
            # qs = qs.filter(Q(username__contains=sSearch) | Q(first_name__contains=sSearch) | Q() )
            exec exec_query

        return qs

    def get_initial_queryset(self):
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        return Service.objects.values(*self.columns+['id'])

    def prepare_results(self, qs):
        if qs:
            qs = [ { key: val if val else "" for key, val in dct.items() } for dct in qs ]
        for dct in qs:
            dct.update(actions='<a href="/service/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/service/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
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
            qs=list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
               }
        return ret

class ServiceDetail(DetailView):
    model = Service
    template_name = 'service/service_detail.html'


class ServiceCreate(CreateView):
    template_name = 'service/service_new.html'
    model = Service
    form_class = ServiceForm
    success_url = reverse_lazy('services_list')

    def form_valid(self, form):
        self.object=form.save()
        action.send(self.request.user, verb='Created', action_object = self.object)
        return HttpResponseRedirect(ServiceCreate.success_url)


class ServiceUpdate(UpdateView):
    template_name = 'service/service_update.html'
    model = Service
    form_class = ServiceForm
    success_url = reverse_lazy('services_list')


    def form_valid(self, form):
        initial_field_dict = { field : form.initial[field] for field in form.initial.keys() }

        cleaned_data_field_dict = { field : map(lambda obj: obj.pk, form.cleaned_data[field])
        if field in ('parameters') and  form.cleaned_data[field] else form.cleaned_data[field] for field in form.cleaned_data.keys() }

        changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
        if changed_fields_dict:
            initial_field_dict['parameters'] = ', '.join([ServiceParameters.objects.get(pk=paramter).parameter_description
                                               for paramter in initial_field_dict['parameters']])
            cleaned_data_field_dict['parameters'] = ', '.join([ServiceParameters.objects.get(pk=paramter).parameter_description
                                                     for paramter in cleaned_data_field_dict['parameters']])

            verb_string = 'Changed values of Service : %s from initial values '%(self.object.service_name) + ', '.join(['%s: %s' %(k, initial_field_dict[k]) \
                               for k in changed_fields_dict])+\
                               ' to '+\
                               ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])
            self.object=form.save()
            action.send( self.request.user, verb=verb_string )
        return HttpResponseRedirect( ServiceUpdate.success_url )

class ServiceDelete(DeleteView):
    model = Service
    template_name = 'service/service_delete.html'
    success_url = reverse_lazy('services_list')


class ServiceParametersList(ListView):
    model = ServiceParameters
    template_name = 'service_parameter/services_parameter_list.html'

    def get_context_data(self, **kwargs):
        context=super(ServiceParametersList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData':'parameter_description',     'sTitle' : 'Parameter Description', 'sWidth':'null',},
            {'mData':'max_check_attempts',        'sTitle' : 'Max Check Attempts',    'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'check_interval',            'sTitle' : 'Check Intervals',       'sWidth':'null',},
            {'mData':'retry_interval',            'sTitle' : 'Retry Interval',        'sWidth':'null',},
            {'mData':'check_period',              'sTitle' : 'Check Period',          'sWidth':'null',},
            {'mData':'notification_interval',     'sTitle' : 'Notification Interval', 'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'notification_period',       'sTitle' : 'Notification Period',   'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'actions',                   'sTitle' : 'Actions',               'sWidth':'5%' ,}
            ]
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context

class ServiceParametersListingTable(BaseDatatableView):
    model = ServiceParameters
    columns = ['parameter_description', 'max_check_attempts', 'check_interval', 'retry_interval','check_period',
                'notification_interval','notification_period']
    order_columns = ['parameter_description', 'max_check_attempts', 'check_interval', 'retry_interval','check_period',
                     'notification_interval','notification_period']

    def filter_queryset(self, qs):
        sSearch = self.request.GET.get('sSearch', None)
        ##TODO:Need to optimise with the query making login.
        if sSearch:
            query=[]
            exec_query = "qs = %s.objects.filter("%(self.model.__name__)
            for column in self.columns[:-1]:
                query.append("Q(%s__contains="%column + "\"" +sSearch +"\"" +")")

            exec_query += " | ".join(query)
            exec_query += ").values(*"+str(self.columns+['id'])+")"
            # qs=qs.filter( reduce( lambda q, column: q | Q(column__contains=sSearch), self.columns, Q() ))
            # qs = qs.filter(Q(username__contains=sSearch) | Q(first_name__contains=sSearch) | Q() )
            exec exec_query

        return qs

    def get_initial_queryset(self):
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        return ServiceParameters.objects.values(*self.columns+['id'])

    def prepare_results(self, qs):
        if qs:
            qs = [ { key: val if val else "" for key, val in dct.items() } for dct in qs ]
        for dct in qs:
            dct.update(actions='<a href="/service_parameter/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/service_parameter/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
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
            qs=list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
               }
        return ret

class ServiceParametersDetail(DetailView):
    model = ServiceParameters
    template_name = 'service_parameter/service_parameter_detail.html'


class ServiceParametersCreate(CreateView):
    template_name = 'service_parameter/service_parameter_new.html'
    model = ServiceParameters
    form_class = ServiceParametersForm
    success_url = reverse_lazy('services_parameter_list')

    def form_valid(self, form):
        self.object=form.save()
        action.send(self.request.user, verb='Created', action_object = self.object)
        return HttpResponseRedirect(ServiceParametersCreate.success_url)

class ServiceParametersUpdate(UpdateView):
    template_name = 'service_parameter/service_parameter_update.html'
    model = ServiceParameters
    form_class = ServiceParametersForm
    success_url = reverse_lazy('services_parameter_list')

    def form_valid(self, form):
        initial_field_dict = { field : form.initial[field] for field in form.initial.keys() }

        cleaned_data_field_dict = { field : form.cleaned_data[field]  for field in form.cleaned_data.keys() }

        changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
        if changed_fields_dict:

            verb_string = 'Changed values of Service Paramters: %s from initial values '%(self.object.parameter_description)\
                          + ', '.join(['%s: %s' %(k, initial_field_dict[k]) for k in changed_fields_dict])\
                          +  ' to '\
                          + ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])
            self.object=form.save()
            action.send( self.request.user, verb=verb_string )
        return HttpResponseRedirect( ServiceParametersUpdate.success_url )



class ServiceParametersDelete(DeleteView):
    model = ServiceParameters
    template_name = 'service_parameter/service_parameter_delete.html'
    success_url = reverse_lazy('services_parameter_list')
    
    
class ServiceDataSourceList(ListView):
    model = ServiceDataSource
    template_name = 'service_data_source/service_data_sources_list.html'

    def get_context_data(self, **kwargs):
        context=super(ServiceDataSourceList, self).get_context_data(**kwargs)
        datatable_headers = [
            {'mData':'data_source_name',        'sTitle' : 'Name',                'sWidth':'null',},
            {'mData':'data_source_alias',       'sTitle' : 'Alias',               'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'warning',                 'sTitle' : 'Warning',             'sWidth':'null',},
            {'mData':'critical',                'sTitle' : 'Critical',            'sWidth':'null','sClass':'hidden-xs'},
            {'mData':'actions',                 'sTitle' : 'Actions',             'sWidth':'10%' ,}
            ]
        context['datatable_headers'] = json.dumps(datatable_headers)
        return context

class ServiceDataSourceListingTable(BaseDatatableView):
    model = ServiceDataSourceList
    columns = ['data_source_name', 'data_source_alias', 'warning', 'critical']
    order_columns = ['data_source_name', 'data_source_alias', 'warning', 'critical']

    def filter_queryset(self, qs):
        sSearch = self.request.GET.get('sSearch', None)
        ##TODO:Need to optimise with the query making login.
        if sSearch:
            query=[]
            exec_query = "qs = %s.objects.filter("%(self.model.__name__)
            for column in self.columns[:-1]:
                query.append("Q(%s__contains="%column + "\"" +sSearch +"\"" +")")

            exec_query += " | ".join(query)
            exec_query += ").values(*"+str(self.columns+['id'])+")"
            # qs=qs.filter( reduce( lambda q, column: q | Q(column__contains=sSearch), self.columns, Q() ))
            # qs = qs.filter(Q(username__contains=sSearch) | Q(first_name__contains=sSearch) | Q() )
            exec exec_query

        return qs

    def get_initial_queryset(self):
        if not self.model:
            raise NotImplementedError("Need to provide a model or implement get_initial_queryset!")
        return ServiceDataSource.objects.values(*self.columns+['id'])

    def prepare_results(self, qs):
        if qs:
            qs = [ { key: val if val else "" for key, val in dct.items() } for dct in qs ]
        for dct in qs:
            dct.update(actions='<a href="/service_data_source/edit/{0}"><i class="fa fa-pencil text-dark"></i></a>\
                <a href="/service_data_source/delete/{0}"><i class="fa fa-trash-o text-danger"></i></a>'.format(dct.pop('id')))
        return qs

    def get_context_data(self, *args, **kwargs):
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
            qs=list(qs)

        # prepare output data
        aaData = self.prepare_results(qs)
        ret = {'sEcho': int(request.REQUEST.get('sEcho', 0)),
               'iTotalRecords': total_records,
               'iTotalDisplayRecords': total_display_records,
               'aaData': aaData
               }
        return ret

class ServiceDataSourceDetail(DetailView):
    model = ServiceDataSource
    template_name = 'service_data_source/service_data_source_detail.html'


class ServiceDataSourceCreate(CreateView):
    template_name = 'service_data_source/service_data_source_new.html'
    model = ServiceDataSource
    form_class = ServiceDataSourceForm
    success_url = reverse_lazy('service_data_sources_list')

    def form_valid(self, form):
        self.object=form.save()
        action.send(self.request.user, verb='Created', action_object = self.object)
        return HttpResponseRedirect(ServiceDataSourceCreate.success_url)


class ServiceDataSourceUpdate(UpdateView):
    template_name = 'service_data_source/service_data_source_update.html'
    model = ServiceDataSource
    form_class = ServiceDataSourceForm
    success_url = reverse_lazy('service_data_sources_list')


    def form_valid(self, form):
        initial_field_dict = { field : form.initial[field] for field in form.initial.keys() }

        cleaned_data_field_dict = { field : form.cleaned_data[field]  for field in form.cleaned_data.keys() }

        print "************************************************************"
        print 'initial_field_dict', initial_field_dict
        print 'cleaned_data_field_dict', cleaned_data_field_dict

        changed_fields_dict = DictDiffer(initial_field_dict, cleaned_data_field_dict).changed()
        if changed_fields_dict:
            verb_string = 'Changed values of ServiceDataSource : %s from initial values '%(self.object.name) + ', '.join(['%s: %s' %(k, initial_field_dict[k]) \
                               for k in changed_fields_dict])+\
                               ' to '+\
                               ', '.join(['%s: %s' % (k, cleaned_data_field_dict[k]) for k in changed_fields_dict])
            self.object=form.save()
            action.send( self.request.user, verb=verb_string )
        return HttpResponseRedirect( ServiceDataSourceUpdate.success_url )

class ServiceDataSourceDelete(DeleteView):
    model = ServiceDataSource
    template_name = 'service_data_source/service_data_source_delete.html'
    success_url = reverse_lazy('service_data_sources_list')
    
