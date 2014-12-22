from django.conf.urls import patterns, url
from inventory import views

urlpatterns = patterns('',
  url(r'^$', views.BackhaulList.as_view(), name='backhauls_list'),
  url(r'^(?P<pk>\d+)/$', views.BackhaulDetail.as_view(), name='backhaul_detail'),
  url(r'^new/$', views.BackhaulCreate.as_view(), name='backhaul_new'),
  url(r'^(?P<pk>\d+)/edit/$', views.BackhaulUpdate.as_view(), name='backhaul_edit'),
  url(r'^(?P<pk>\d+)/delete/$', views.BackhaulDelete.as_view(), name='backhaul_delete'),
  url(r'^Backhaullistingtable/', views.BackhaulListingTable.as_view(), name='BackhaulListingTable'),
  url(r'^select2/elements/$', views.SelectBackhaulListView.as_view(), name='select2-backhaul-elements'),
)
