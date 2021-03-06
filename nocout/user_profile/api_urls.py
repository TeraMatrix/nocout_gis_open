from django.conf.urls import url
import api

urlpatterns = [
    url(r'^user_soft_delete_display_data/(?P<value>\d+)/$', api.UserSoftDeleteDisplayData.as_view(),
        name='user_soft_delete_display_data'),
    url(r'^user_soft_delete/(?P<value>\d+)/(?P<new_parent_id>\d+)/$', api.UserSoftDelete.as_view(),
        name='user_soft_delete'),
    url(r'^restore_user/(?P<value>\d+)/$', api.RestoreUser.as_view(), name='restore_user'),
    url(r'^delete_user/(?P<value>\d+)/$', api.DeleteUser.as_view(), name='delete_user'),
    url(r'^reset_user_permissions/(?P<value>\d+)/$', api.ResetUserPermissions.as_view(), name='reset_user_permissions'),
    url(r'^permissions_on_group_change/(?P<gid>\d+)/$', api.PermissonsOnGroupChange.as_view(),
        name='permissions_on_group_change'),
    url(r'^parent_on_organization_change/(?P<oid>\d+)/$', api.ParentOnOrganizationChange.as_view(),
        name='parent_on_organization_change'),
    url(r'^reset_admin_users_permissions/$', api.ResetAdminUsersPermissions.as_view(),
        name='reset_admin_users_permissions'),
    url(r'^get_user_organizations/$', api.GetUserOrganizations.as_view(),
        name='get_user_organizations'),
]
