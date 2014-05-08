from string import capitalize
from django import forms
from device.models import Device, DeviceTechnology, DeviceVendor, DeviceModel, DeviceType, DeviceTypeFields
from nocout.widgets import MultipleToSingleSelectionWidget, IntReturnModelChoiceField
from device.models import DeviceTypeFields


# *************************************** Device Form ***********************************************


class DeviceForm(forms.ModelForm):
    device_technology = IntReturnModelChoiceField(queryset=DeviceTechnology.objects.all(),
                                                  required=False
    )
    device_vendor = IntReturnModelChoiceField(queryset=DeviceVendor.objects.all(),
                                              required=False
    )
    device_model = IntReturnModelChoiceField(queryset=DeviceModel.objects.all(),
                                             required=False
    )
    device_type = IntReturnModelChoiceField(queryset=DeviceType.objects.all(),
                                            required=False
    )

    def __init__(self, *args, **kwargs):
        self.base_fields['device_group'].label = 'Device Group'
        self.base_fields['site_instance'].label = 'Site Instance'
        self.base_fields['device_technology'].label = 'Device Technology'
        self.base_fields['device_vendor'].label = 'Device Vendor'
        self.base_fields['device_model'].label = 'Device Model'
        self.base_fields['device_type'].label = 'Device Type'

        super(DeviceForm, self).__init__(*args, **kwargs)

        # to redisplay the extra fields form with already filled values we follow these steps:
        # 1. check that device type exist in 'kwargs' or not
        # 2. if 'device type' value exist then fetch extra fields associated with that 'device type'
        # 3. then we recreates text fields corresponding to each field we fetched in step 2
        try:
            if kwargs['data']['device_type']:
                extra_fields = DeviceTypeFields.objects.filter(device_type_id=kwargs['data']['device_type'])
                for extra_field in extra_fields:
                    self.fields[extra_field.field_name] = forms.CharField(label=extra_field.field_display_name)
                    self.fields.update({
                        extra_field.field_name: forms.CharField(widget=forms.TextInput(), required=False,
                                                                label=extra_field.field_display_name, ),
                    })
                    self.fields[extra_field.field_name].widget.attrs['class'] = 'extra'
            else:
                pass
        except:
            pass

    class Meta:
        model = Device
        widgets = {
            'device_group': MultipleToSingleSelectionWidget,
        }


# ********************************** Device Extra Fields Form ***************************************


class DeviceTypeFieldsForm(forms.ModelForm):
    class Meta:
        model = DeviceTypeFields
        fields = ('field_name', 'field_display_name', 'device_type')


class DeviceTypeFieldsUpdateForm(forms.ModelForm):
    class Meta:
        model = DeviceTypeFields
        fields = ('field_name', 'field_display_name')


# **************************************** Device Technology ****************************************


class DeviceTechnologyForm(forms.ModelForm):
    class Meta:
        model = DeviceTechnology
        fields = ('name', 'alias', 'device_vendors')


# ****************************************** Device Vendor ******************************************


class DeviceVendorForm(forms.ModelForm):
    class Meta:
        model = DeviceVendor
        fields = ('name', 'alias', 'device_models')


# ******************************************* Device Model ******************************************


class DeviceModelForm(forms.ModelForm):
    class Meta:
        model = DeviceModel
        fields = ('name', 'alias', 'device_types')


# ******************************************* Device Type *******************************************


class DeviceTypeForm(forms.ModelForm):
    class Meta:
        model = DeviceType
        fields = ('name', 'alias')
