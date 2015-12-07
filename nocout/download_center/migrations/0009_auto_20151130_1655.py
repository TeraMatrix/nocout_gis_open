# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('download_center', '0008_auto_20151020_1658'),
    ]

    operations = [
        migrations.AddField(
            model_name='bsoutagemasterdaily',
            name='s_no',
            field=models.CharField(max_length=128, null=True, verbose_name=b'S. No.', blank=True),
        ),
        migrations.AddField(
            model_name='bsoutagemastermonthly',
            name='s_no',
            field=models.CharField(max_length=128, null=True, verbose_name=b'S. No.', blank=True),
        ),
        migrations.AddField(
            model_name='bsoutagemasterweekly',
            name='s_no',
            field=models.CharField(max_length=128, null=True, verbose_name=b'S. No.', blank=True),
        ),
    ]
