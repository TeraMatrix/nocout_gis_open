from django.db import models
from django.contrib.auth.models import User, UserManager
from django.db.models.signals import post_save
from mptt.models import MPTTModel, TreeForeignKey
from organization.models import Organization
import signals as user_signals


# user profile class
class UserProfile(MPTTModel, User):
    """
    user Profile columns declared
    """
    parent = TreeForeignKey('self', null=True, blank=True, related_name='user_children')
    role = models.ManyToManyField('Roles')
    organization = models.ForeignKey(Organization)
    phone_number = models.CharField('Phone No.', max_length=15, null=True, blank=True)
    company = models.CharField('Company', max_length=100, null=True, blank=True)
    designation = models.CharField('Designation', max_length=100, null=True, blank=True)
    address = models.CharField('Address', max_length=150, null=True, blank=True)
    comment = models.TextField('Comment', null=True, blank=True)
    is_deleted = models.IntegerField('Is Deleted', max_length=1, default=0)
    password_changed_at = models.DateTimeField('Password changed at', null=True, blank=True)
    user_invalid_attempt = models.IntegerField('Invalid attempt', null=True, blank=True, default=0)
    user_invalid_attempt_at = models.DateTimeField('Invalid attemp at', null=True, blank=False)

# user roles class
class Roles(models.Model):
    """
    User Roles columns declared.
    """
    role_name = models.CharField('Role Name', max_length=100, null=True, blank=True)
    role_description = models.CharField('Role Description', max_length=250, null=True, blank=True)

    def __unicode__(self):
        return self.role_description

class UserPasswordRecord(models.Model):
    """
    To keep the record of the password used by user.
    """
    user_id = models.IntegerField('User Id', null=True, blank=True)
    password_used = models.CharField('Password', max_length=100, null=True, blank=True)
    password_used_on = models.DateTimeField('Password Used On', auto_now_add=True)

# ************************************ USER PROFILE SIGNALS ************************************
# set site instance 'is_device_change' bit on device type service modified or created
post_save.connect(user_signals.assign_default_thematics_to_user, sender=UserProfile)
