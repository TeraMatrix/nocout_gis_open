"""
=========================================================================================
Module contains url configuration specific to 'device technology' module in 'device' app.
=========================================================================================

Location:
* /nocout_gis/nocout/device/device_technology_urls.py
"""

from django.conf.urls import patterns, url
from device import views

urlpatterns = patterns('',
                       url(r'^$', views.DeviceTechnologyList.as_view(), name='device_technology_list'),
                       url(r'^(?P<pk>\d+)/$', views.DeviceTechnologyDetail.as_view(), name='device_technology_detail'),
                       url(r'^new/$', views.DeviceTechnologyCreate.as_view(), name='device_technology_new'),
                       url(r'^(?P<pk>\d+)/edit/$', views.DeviceTechnologyUpdate.as_view(),
                           name='device_technology_edit'),
                       url(r'^(?P<pk>\d+)/delete/$', views.DeviceTechnologyDelete.as_view(),
                           name='device_technology_delete'),
                       url(r'^devicetechnologylistingtable/', views.DeviceTechnologyListingTable.as_view(),
                           name='DeviceTechnologyListingTable'),
                       )