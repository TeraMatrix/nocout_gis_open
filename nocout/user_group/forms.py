from django import forms

from organization.models import Organization
from user_group.models import UserGroup
from user_profile.models import UserProfile


class UserGroupForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        initial = kwargs.setdefault('initial',{})
        if kwargs['instance']:
            initial['organization']= kwargs['instance'].organization.id
        elif Organization.objects.all():
            initial['organization']=Organization.objects.all()[0].id
        else:
            initial['organization']=None

        super(UserGroupForm, self).__init__(*args, **kwargs)
        self.fields['parent'].empty_label = 'Select'
        self.fields['organization'].empty_label = 'Select'
        organization_id=None
        if kwargs['instance']:
            self.fields['name'].widget.attrs['readonly'] = True
            organization_id=initial['organization']
        elif Organization.objects.all():
            organization_id=Organization.objects.all()[0].id
        if organization_id:
            organization_descendants_ids= Organization.objects.get(id= organization_id).get_descendants(include_self=True).values_list('id', flat=True)
            self.fields['users'].queryset= UserProfile.objects.filter( organization__in = organization_descendants_ids, is_deleted=0)

        for name, field in self.fields.items():
            if field.widget.attrs.has_key('class'):
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs.update({'class':'form-control'})

    class Meta:
        model = UserGroup
        fields = ('name', 'alias', 'parent', 'location', 'address', 'organization','users',)
