from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.core.urlresolvers import reverse_lazy
from device.models import Device, Inventory, DeviceType, DeviceTypeFields, DeviceTypeFieldsValue, DeviceTechnology, \
                          TechnologyVendor, DeviceVendor, VendorModel, DeviceModel, ModelType
from forms import DeviceForm, DeviceTypeFieldsForm, DeviceTypeFieldsUpdateForm, DeviceTechnologyForm, \
                  DeviceVendorForm, DeviceModelForm
from site_instance.models import SiteInstance
from django.http.response import HttpResponseRedirect
from service.models import Service


# ***************************************** Device Views *******************************************


class DeviceList(ListView):
    model = Device
    template_name = 'devices_list.html'
    

class DeviceDetail(DetailView):
    model = Device
    template_name = 'device_detail.html'
    
    
class DeviceCreate(CreateView):
    template_name = 'device_new.html'
    model = Device
    form_class = DeviceForm
    success_url = reverse_lazy('device_list')
    
    def form_invalid(self, form):
        print form
        return CreateView.form_invalid(self, form)
    
    def form_valid(self, form):
        print "***************************************"
        print "Enter in form_valid()."
        print len(self.request.POST)
        print "***************************************"
        post_fields = self.request.POST
        all_non_empty_post_fields = []
        
        for key, value in post_fields.iteritems():
            if key == "csrfmiddlewaretoken": continue
            if value != "":
                all_non_empty_post_fields.append(key)
        
        print "***************************************"        
        print all_non_empty_post_fields
        print "***************************************"
        print len(all_non_empty_post_fields)
        print "***************************************"
        
            
        try:
            site = SiteInstance.objects.get(pk=form.cleaned_data['instance'])
            service = Service.objects.get(pk=form.cleaned_data['service'])
        except:
            site = None
            service = None
            
        self.object = form.save(commit=False)
        device = Device()
        device.device_name = form.cleaned_data['device_name']
        device.device_alias = form.cleaned_data['device_alias']
        device.device_technology = form.cleaned_data['device_technology']
        device.device_vendor = form.cleaned_data['device_vendor']
        device.device_model = form.cleaned_data['device_model']
        device.device_type = form.cleaned_data['device_type']
        device.ip_address = form.cleaned_data['ip_address']
        device.mac_address = form.cleaned_data['mac_address']
        device.netmask = form.cleaned_data['netmask']
        device.gateway = form.cleaned_data['gateway']
        device.dhcp_state = form.cleaned_data['dhcp_state']
        device.host_priority = form.cleaned_data['host_priority']
        device.host_state = form.cleaned_data['host_state']
        device.address = form.cleaned_data['address']
        device.city = form.cleaned_data['city']
        device.state = form.cleaned_data['state']
        device.timezone = form.cleaned_data['timezone']
        device.latitude = form.cleaned_data['latitude']
        device.longitude= form.cleaned_data['longitude']
        device.description = form.cleaned_data['description']
        device.save()
        try:
            device_type = DeviceType.objects.get(id=int(self.request.POST.get('device_type')))
            device_type.devicetypefields_set.all()
        except:
            print "No device type exists."
        try:
            device.service.add(service)
            device.save()
        except:
            print "No service to add."
        try:
            device.instance = site
            device.save()
        except:
            print "No instance to add."
        print "Device ID: %d" % device.id
        
        for field in all_non_empty_post_fields:
            try:
                dtf = DeviceTypeFields.objects.filter(field_name=field, device_type_id=int(self.request.POST.get('device_type')))
                print self.request.POST.get('device_type')
                print dtf
                print dtf[0]
                dtfv = DeviceTypeFieldsValue()
                dtfv.device_type_field = dtf[0]
                dtfv.field_value = self.request.POST.get(field)
                dtfv.device_id = device.id
                dtfv.save()
            except:
                pass
        
        for dg in form.cleaned_data['device_group']:
            inventory = Inventory()
            inventory.device = device
            inventory.device_group = dg
            inventory.save()
        return HttpResponseRedirect(DeviceCreate.success_url)
    
    
class DeviceUpdate(UpdateView):
    template_name = 'device_update.html'
    model = Device
    form_class = DeviceForm
    success_url = reverse_lazy('device_list')


class DeviceDelete(DeleteView):
    model = Device
    template_name = 'device_delete.html'
    success_url = reverse_lazy('device_list')

    
# ************************** Device Type Form Fields Views **********************************


class DeviceTypeFieldsList(ListView):
    model = DeviceTypeFields
    template_name = 'device_type_form_field_list.html'


class DeviceTypeFieldsDetail(DetailView):
    model = DeviceTypeFields
    template_name = 'device_type_form_field_detail.html'
    
    
class DeviceTypeFieldsCreate(CreateView):
    template_name = 'device_type_form_field_new.html'
    model = DeviceTypeFields
    form_class = DeviceTypeFieldsForm
    success_url = reverse_lazy('device_type_form_field_list')
    
    
class DeviceTypeFieldsUpdate(UpdateView):
    template_name = 'device_type_form_field_update.html'
    model = DeviceTypeFields
    form_class = DeviceTypeFieldsUpdateForm
    success_url = reverse_lazy('device_type_form_field_list')
    

class DeviceTypeFieldsDelete(DeleteView):
    model = DeviceTypeFields
    template_name = 'device_type_form_field_delete.html'
    success_url = reverse_lazy('device_type_form_field_list')
    

# ************************************* Device Technology *************************************


class DeviceTechnologyList(ListView):
    model = DeviceTechnology
    template_name = 'device_technology_list.html'


class DeviceTechnologyDetail(DetailView):
    model = DeviceTechnology
    template_name = 'device_technology_detail.html'
    
    
class DeviceTechnologyCreate(CreateView):
    template_name = 'device_technology_new.html'
    model = DeviceTechnology
    form_class = DeviceTechnologyForm
    success_url = reverse_lazy('device_technology_list')
    
    def form_valid(self, form):
        device_technology = DeviceTechnology()
        device_technology.name = form.cleaned_data['name']
        device_technology.alias= form.cleaned_data['alias']
        device_technology.save()
        
        # saving device_vendors --> M2M Relation (Model: TechnologyVendor)
        for device_vendor in form.cleaned_data['device_vendors']:
            tv = TechnologyVendor()
            tv.technology = device_technology
            tv.vendor = device_vendor
            tv.save()
        return HttpResponseRedirect(DeviceTechnologyCreate.success_url)
    
    
class DeviceTechnologyUpdate(UpdateView):
    template_name = 'device_technology_update.html'
    model = DeviceTechnology
    form_class = DeviceTechnologyForm
    success_url = reverse_lazy('device_technology_list')
    
    def form_valid(self, form):
        # restrict form from updating
        self.object = form.save(commit=False)
        
        # delete old relationship exist in technologyvendor
        TechnologyVendor.objects.filter(technology=self.object).delete()
        
        # updating device_vendors --> M2M Relation (Model: TechnologyVendor)
        for device_vendor in form.cleaned_data['device_vendors']:
            tv = TechnologyVendor()
            tv.technology = self.object
            tv.vendor = device_vendor
            tv.save()
        return HttpResponseRedirect(DeviceTechnologyUpdate.success_url)


class DeviceTechnologyDelete(DeleteView):
    model = DeviceTechnology
    template_name = 'device_technology_delete.html'
    success_url = reverse_lazy('device_technology_list')
    
    
# ************************************* Device Vendor *************************************


class DeviceVendorList(ListView):
    model = DeviceVendor
    template_name = 'device_vendor_list.html'


class DeviceVendorDetail(DetailView):
    model = DeviceVendor
    template_name = 'device_vendor_detail.html'
    
    
class DeviceVendorCreate(CreateView):
    template_name = 'device_vendor_new.html'
    model = DeviceVendor
    form_class = DeviceVendorForm
    success_url = reverse_lazy('device_vendor_list')
    
    def form_valid(self, form):
        device_vendor = DeviceVendor()
        device_vendor.name = form.cleaned_data['name']
        device_vendor.alias= form.cleaned_data['alias']
        device_vendor.save()
        
        # saving device_models --> M2M Relation (Model: VendorModel)
        for device_model in form.cleaned_data['device_models']:
            vm = VendorModel()
            vm.vendor = device_vendor
            vm.model = device_model
            vm.save()
        return HttpResponseRedirect(DeviceVendorCreate.success_url)
    

class DeviceVendorUpdate(UpdateView):
    template_name = 'device_vendor_update.html'
    model = DeviceVendor
    form_class = DeviceVendorForm
    success_url = reverse_lazy('device_vendor_list')
    
    def form_valid(self, form):
        # restrict form from updating
        self.object = form.save(commit=False)
        
        # delete old relationship exist in vendormodel
        VendorModel.objects.filter(vendor=self.object).delete()
        
        # updating device_models --> M2M Relation (Model: VendorModel)
        for device_model in form.cleaned_data['device_models']:
            vm = VendorModel()
            vm.vendor = self.object
            vm.model = device_model
            vm.save()
        return HttpResponseRedirect(DeviceVendorUpdate.success_url)


class DeviceVendorDelete(DeleteView):
    model = DeviceVendor
    template_name = 'device_vendor_delete.html'
    success_url = reverse_lazy('device_vendor_list')
    
    
# ************************************* Device Model *************************************


class DeviceModelList(ListView):
    model = DeviceModel
    template_name = 'device_model_list.html'


class DeviceModelDetail(DetailView):
    model = DeviceModel
    template_name = 'device_model_detail.html'
    
    
class DeviceModelCreate(CreateView):
    template_name = 'device_model_new.html'
    model = DeviceModel
    form_class = DeviceModelForm
    success_url = reverse_lazy('device_model_list')
    
    def form_valid(self, form):
        device_model = DeviceModel()
        device_model.name = form.cleaned_data['name']
        device_model.alias= form.cleaned_data['alias']
        device_model.save()
        
        # saving device_types --> M2M Relation (Model: ModelType)
        for device_type in form.cleaned_data['device_types']:
            mt = ModelType()
            mt.model = device_model
            mt.type = device_type
            mt.save()
        return HttpResponseRedirect(DeviceModelCreate.success_url)
    

class DeviceModelUpdate(UpdateView):
    template_name = 'device_model_update.html'
    model = DeviceModel
    form_class = DeviceModelForm
    success_url = reverse_lazy('device_model_list')
    
    def form_valid(self, form):
        # restrict form from updating
        self.object = form.save(commit=False)
        
        # delete old relationship exist in modeltype
        ModelType.objects.filter(model=self.object).delete()
        
        # updating model_types --> M2M Relation (Model: ModelType)
        for device_type in form.cleaned_data['device_types']:
            mt = ModelType()
            mt.model = self.object
            mt.type = device_type
            mt.save()
        return HttpResponseRedirect(DeviceModelUpdate.success_url)


class DeviceModelDelete(DeleteView):
    model = DeviceModel
    template_name = 'device_model_delete.html'
    success_url = reverse_lazy('device_model_list')
        
