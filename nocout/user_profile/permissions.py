"""
Define permissions for following roles:

    - Admin
    - Operator
    - Viewer

On updating this config file. Following command should be run for expected behavior:

    ./manage.py fix_group_permission
"""


admin_perms = [
    'activity_stream.view_useraction',
    'auth.add_user',
    'auth.change_user',
    'auth.delete_user',
    'auth.view_user',
    'device.change_device',
    'device.view_device',
    'device.view_devicefrequency',
    'inventory.change_antenna',
    'inventory.view_antenna',
    'inventory.change_backhaul',
    'inventory.view_backhaul',
    'inventory.change_basestation',
    'inventory.view_basestation',
    'inventory.change_circuit',
    'inventory.view_circuit',
    'inventory.change_customer',
    'inventory.view_customer',
    'inventory.view_iconsettings',
    'inventory.view_livepollingsettings',
    'inventory.change_sector',
    'inventory.view_sector',
    'inventory.change_substation',
    'inventory.view_substation',
    'inventory.view_thematicsettings',
    'inventory.view_thresholdconfiguration',
    'organization.add_organization',
    'organization.change_organization',
    'organization.delete_organization',
    'organization.view_organization',
    'user_profile.add_userprofile',
    'user_profile.change_userprofile',
    'user_profile.view_userprofile',
    'user_profile.delete_userprofile',
    'alarm_escalation.add_escalationlevel',
    'alarm_escalation.change_escalationlevel',
    'alarm_escalation.delete_escalationlevel',
    'alarm_escalation.view_escalationlevel',
]


operator_perms = [
    'activity_stream.view_useraction',
    'auth.view_user',
    'device.view_device',
    'device.view_devicefrequency',
    'inventory.change_antenna',
    'inventory.view_antenna',
    'inventory.change_backhaul',
    'inventory.view_backhaul',
    'inventory.change_basestation',
    'inventory.view_basestation',
    'inventory.change_circuit',
    'inventory.view_circuit',
    'inventory.change_customer',
    'inventory.view_customer',
    'inventory.view_iconsettings',
    'inventory.view_livepollingsettings',
    'inventory.change_sector',
    'inventory.view_sector',
    'inventory.change_substation',
    'inventory.view_substation',
    'inventory.view_thematicsettings',
    'inventory.view_thresholdconfiguration',
    'organization.view_organization',
    'user_profile.view_userprofile',
    'alarm_escalation.view_escalationlevel',
]


viewer_perms = [
    'device.view_device',
    'device.view_devicefrequency',
    'inventory.view_antenna',
    'inventory.view_backhaul',
    'inventory.view_basestation',
    'inventory.view_circuit',
    'inventory.view_customer',
    'inventory.view_iconsettings',
    'inventory.view_livepollingsettings',
    'inventory.view_sector',
    'inventory.view_substation',
    'inventory.view_thematicsettings',
    'inventory.view_thresholdconfiguration',
    'alarm_escalation.view_escalationlevel',
]
