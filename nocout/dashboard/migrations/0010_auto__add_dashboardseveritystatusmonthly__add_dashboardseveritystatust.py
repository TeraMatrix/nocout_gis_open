# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'DashboardSeverityStatusMonthly'
        db.create_table(u'dashboard_dashboardseveritystatusmonthly', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusMonthly'])

        # Adding model 'DashboardSeverityStatusTimely'
        db.create_table(u'dashboard_dashboardseveritystatustimely', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusTimely'])

        # Adding model 'DashboardSeverityStatusHourly'
        db.create_table(u'dashboard_dashboardseveritystatushourly', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusHourly'])

        # Adding model 'DashboardSeverityStatusYearly'
        db.create_table(u'dashboard_dashboardseveritystatusyearly', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusYearly'])

        # Adding model 'DashboardSeverityStatusWeekly'
        db.create_table(u'dashboard_dashboardseveritystatusweekly', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusWeekly'])

        # Adding model 'DashboardSeverityStatusDaily'
        db.create_table(u'dashboard_dashboardseveritystatusdaily', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('dashboard_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sector_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')()),
            ('warning', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('critical', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('ok', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('down', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('unknown', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal(u'dashboard', ['DashboardSeverityStatusDaily'])


    def backwards(self, orm):
        # Deleting model 'DashboardSeverityStatusMonthly'
        db.delete_table(u'dashboard_dashboardseveritystatusmonthly')

        # Deleting model 'DashboardSeverityStatusTimely'
        db.delete_table(u'dashboard_dashboardseveritystatustimely')

        # Deleting model 'DashboardSeverityStatusHourly'
        db.delete_table(u'dashboard_dashboardseveritystatushourly')

        # Deleting model 'DashboardSeverityStatusYearly'
        db.delete_table(u'dashboard_dashboardseveritystatusyearly')

        # Deleting model 'DashboardSeverityStatusWeekly'
        db.delete_table(u'dashboard_dashboardseveritystatusweekly')

        # Deleting model 'DashboardSeverityStatusDaily'
        db.delete_table(u'dashboard_dashboardseveritystatusdaily')


    models = {
        u'command.command': {
            'Meta': {'object_name': 'Command'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'command_line': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'dashboard.dashboardrangestatusdaily': {
            'Meta': {'object_name': 'DashboardRangeStatusDaily'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardrangestatushourly': {
            'Meta': {'object_name': 'DashboardRangeStatusHourly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardrangestatusmonthly': {
            'Meta': {'object_name': 'DashboardRangeStatusMonthly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardrangestatustimely': {
            'Meta': {'object_name': 'DashboardRangeStatusTimely'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardrangestatusweekly': {
            'Meta': {'object_name': 'DashboardRangeStatusWeekly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardrangestatusyearly': {
            'Meta': {'object_name': 'DashboardRangeStatusYearly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'device_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'range1': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range10': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range2': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range3': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range4': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range5': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range6': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range7': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range8': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'range9': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardsetting': {
            'Meta': {'unique_together': "(('name', 'page_name', 'technology', 'is_bh'),)", 'object_name': 'DashboardSetting'},
            'dashboard_type': ('django.db.models.fields.CharField', [], {'max_length': '3'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_bh': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'page_name': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'range10_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range10_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range10_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range1_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range1_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range1_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range2_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range2_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range2_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range3_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range3_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range3_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range4_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range4_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range4_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range5_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range5_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range5_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range6_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range6_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range6_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range7_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range7_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range7_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range8_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range8_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range8_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range9_color_hex_value': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'range9_end': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'range9_start': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'technology': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceTechnology']", 'null': 'True', 'blank': 'True'})
        },
        u'dashboard.dashboardseveritystatusdaily': {
            'Meta': {'object_name': 'DashboardSeverityStatusDaily'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardseveritystatushourly': {
            'Meta': {'object_name': 'DashboardSeverityStatusHourly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardseveritystatusmonthly': {
            'Meta': {'object_name': 'DashboardSeverityStatusMonthly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardseveritystatustimely': {
            'Meta': {'object_name': 'DashboardSeverityStatusTimely'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardseveritystatusweekly': {
            'Meta': {'object_name': 'DashboardSeverityStatusWeekly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dashboardseveritystatusyearly': {
            'Meta': {'object_name': 'DashboardSeverityStatusYearly'},
            'created_on': ('django.db.models.fields.DateTimeField', [], {}),
            'critical': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'dashboard_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'down': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ok': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sector_name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'unknown': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'warning': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'dashboard.dfrprocessed': {
            'Meta': {'object_name': 'DFRProcessed'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'processed_for': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard.MFRDFRReports']"}),
            'processed_key': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'processed_on': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'processed_report_path': ('django.db.models.fields.TextField', [], {}),
            'processed_value': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'dashboard.mfrcausecode': {
            'Meta': {'object_name': 'MFRCauseCode'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'processed_for': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard.MFRDFRReports']"}),
            'processed_key': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'processed_on': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'processed_value': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'dashboard.mfrdfrreports': {
            'Meta': {'object_name': 'MFRDFRReports'},
            'absolute_path': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_processed': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'process_for': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '8'}),
            'upload_to': ('django.db.models.fields.files.FileField', [], {'max_length': '512'})
        },
        u'dashboard.mfrprocessed': {
            'Meta': {'object_name': 'MFRProcessed'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'processed_for': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['dashboard.MFRDFRReports']"}),
            'processed_key': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'processed_on': ('django.db.models.fields.DateField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'processed_value': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'device.devicemodel': {
            'Meta': {'object_name': 'DeviceModel'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'device_types': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['device.DeviceType']", 'null': 'True', 'through': u"orm['device.ModelType']", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'device.deviceport': {
            'Meta': {'object_name': 'DevicePort'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'value': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        u'device.devicetechnology': {
            'Meta': {'object_name': 'DeviceTechnology'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'device_vendors': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['device.DeviceVendor']", 'null': 'True', 'through': u"orm['device.TechnologyVendor']", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'device.devicetype': {
            'Meta': {'object_name': 'DeviceType'},
            'agent_tag': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'device_gmap_icon': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'device_icon': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'device_port': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['device.DevicePort']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'normal_check_interval': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'packets': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'pl_critical': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'pl_warning': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rta_critical': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rta_warning': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'service': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['service.Service']", 'null': 'True', 'through': u"orm['device.DeviceTypeService']", 'blank': 'True'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'device.devicetypeservice': {
            'Meta': {'object_name': 'DeviceTypeService'},
            'device_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'parameter': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.ServiceParameters']"}),
            'service': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.Service']"}),
            'service_data_sources': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['service.ServiceDataSource']", 'through': u"orm['device.DeviceTypeServiceDataSource']", 'symmetrical': 'False'})
        },
        u'device.devicetypeservicedatasource': {
            'Meta': {'object_name': 'DeviceTypeServiceDataSource'},
            'critical': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'device_type_service': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceTypeService']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'service_data_sources': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.ServiceDataSource']"}),
            'warning': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        u'device.devicevendor': {
            'Meta': {'object_name': 'DeviceVendor'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'device_models': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['device.DeviceModel']", 'null': 'True', 'through': u"orm['device.VendorModel']", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        u'device.modeltype': {
            'Meta': {'object_name': 'ModelType'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceModel']"}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceType']"})
        },
        u'device.technologyvendor': {
            'Meta': {'object_name': 'TechnologyVendor'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'technology': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceTechnology']"}),
            'vendor': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceVendor']"})
        },
        u'device.vendormodel': {
            'Meta': {'object_name': 'VendorModel'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceModel']"}),
            'vendor': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['device.DeviceVendor']"})
        },
        u'service.protocol': {
            'Meta': {'object_name': 'Protocol'},
            'auth_password': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'auth_protocol': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'port': ('django.db.models.fields.IntegerField', [], {}),
            'private_pass_phase': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'private_phase': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'protocol_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'read_community': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'security_level': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'security_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'write_community': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        u'service.service': {
            'Meta': {'object_name': 'Service'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'command': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['command.Command']", 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parameters': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.ServiceParameters']"}),
            'service_data_sources': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['service.ServiceDataSource']", 'through': u"orm['service.ServiceSpecificDataSource']", 'symmetrical': 'False'})
        },
        u'service.servicedatasource': {
            'Meta': {'object_name': 'ServiceDataSource'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'chart_color': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'chart_type': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'critical': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'data_source_type': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'formula': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_inverted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'show_gis': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'show_max': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_min': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'show_performance_center': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'valuesuffix': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'valuetext': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'warning': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        },
        u'service.serviceparameters': {
            'Meta': {'object_name': 'ServiceParameters'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_check_attempts': ('django.db.models.fields.IntegerField', [], {}),
            'normal_check_interval': ('django.db.models.fields.IntegerField', [], {}),
            'parameter_description': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'protocol': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.Protocol']"}),
            'retry_check_interval': ('django.db.models.fields.IntegerField', [], {})
        },
        u'service.servicespecificdatasource': {
            'Meta': {'object_name': 'ServiceSpecificDataSource'},
            'critical': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'service': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.Service']"}),
            'service_data_sources': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['service.ServiceDataSource']"}),
            'warning': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['dashboard']